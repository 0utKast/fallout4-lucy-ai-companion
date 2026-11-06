"""Synchronous Clause-Streaming Local Voice Engine supporting both Kokoro-ONNX (82M) and KoboldCpp (audio.cpp TTS).

Runs 100% locally with zero GPU contention for Fallout 4 & Fallout 4 VR.
Splits each companion line into natural clauses so the first clause ("Okey-dokey!",
"Oh, sugar!", etc.) finishes synthesizing in ~180 ms and begins playing immediately
while subsequent clauses synthesize in parallel in the background.
"""

from array import array
import json
import os
import queue
import re
import struct
import threading
import time
import urllib.error
import urllib.request
import winsound
from pathlib import Path

# Ensure eSpeak NG path is configured on Windows before importing kokoro_onnx
if "PHONEMIZER_ESPEAK_PATH" not in os.environ and Path(r"C:\Program Files\eSpeak NG").exists():
    os.environ["PHONEMIZER_ESPEAK_PATH"] = r"C:\Program Files\eSpeak NG"

try:
    import numpy as np
except ImportError:
    np = None

import personas

HERE = Path(__file__).parent
LOCAL_MODELS_DIR = HERE / "models" / "kokoro"
FALLBACK_MODELS_DIR = Path(r"C:\proyectos_python\MisApps\Texto_a_voz")

KOKORO_RELEASE_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_AUTO_FILES = (
    ("voices-v1.0.bin", f"{KOKORO_RELEASE_BASE}/voices-v1.0.bin"),
    ("kokoro-v1.0.int8.onnx", f"{KOKORO_RELEASE_BASE}/kokoro-v1.0.int8.onnx"),
)

# Split on sentence boundaries (. ! ?) or after a comma/semicolon when the first clause is short
CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=[,;—])\s+")


def split_into_clauses(text: str) -> list[str]:
    """Splits a line into clauses so the first chunk is short (~2-7 words) for instant TTFA (<220 ms)."""
    raw = [c.strip() for c in CLAUSE_SPLIT_RE.split(text.strip()) if c.strip()]
    if not raw:
        return []
    clauses: list[str] = []
    buf = ""
    for part in raw:
        if not buf:
            buf = part
        elif len(buf.split()) < 3 and not buf.endswith(("!", "?", ".")):
            buf = f"{buf} {part}"
        else:
            clauses.append(buf)
            buf = part
    if buf:
        clauses.append(buf)
    return clauses


def _float_to_wav(samples, sample_rate: int, gain: float = 1.0) -> bytes:
    if np is not None:
        arr = np.clip(samples * gain, -1.0, 1.0)
        pcm16 = (arr * 32767.0).astype(np.int16).tobytes()
    else:
        pcm = array("h", (max(-32768, min(32767, int(s * gain * 32767.0))) for s in samples))
        pcm16 = pcm.tobytes()
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm16)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(pcm16))
    return header + pcm16


def _scale_wav_bytes(wav_bytes: bytes, gain: float) -> bytes:
    """Scales 16-bit PCM WAV bytes by `gain` using pure Python standard library."""
    if abs(gain - 1.0) < 0.03 or not wav_bytes.startswith(b"RIFF"):
        return wav_bytes
    idx = wav_bytes.find(b"data")
    if idx < 0 or idx + 8 > len(wav_bytes):
        return wav_bytes
    data_offset = idx + 8
    header = wav_bytes[:data_offset]
    raw_pcm = wav_bytes[data_offset:]
    if len(raw_pcm) % 2 != 0:
        raw_pcm = raw_pcm[:-1]
    samples = array("h")
    samples.frombytes(raw_pcm)
    for i in range(len(samples)):
        val = int(samples[i] * gain)
        samples[i] = 32767 if val > 32767 else (-32768 if val < -32768 else val)
    return header + samples.tobytes()


class LocalVoice:
    def __init__(self, enabled: bool | None = None, voice_name: str | None = None):
        cfg = personas.current()
        self.enabled = cfg["voice_enabled"] if enabled is None else enabled
        self.voice_name = voice_name or cfg["kokoro_voice"]
        self.volume = cfg["voice_volume"]
        self.lang = cfg.get("language", "en-us")
        self.tts_backend = cfg.get("tts_backend", "auto")
        self.koboldcpp_url = cfg.get("koboldcpp_url", "http://127.0.0.1:5001")
        self.kokoro = None
        self.voice_style = None
        self.use_kobold_tts = False

        # Two-stage pipeline for synchronous streaming:
        # 1. _synth_queue receives (clauses, distance_m) and synthesizes clause-by-clause
        # 2. _play_queue receives ready WAV bytes and plays them back-to-back with zero gap
        self._synth_queue: queue.Queue = queue.Queue(maxsize=16)
        self._play_queue: queue.Queue = queue.Queue(maxsize=16)
        self._workers_started = False

        if self.enabled:
            threading.Thread(target=self._play_worker, daemon=True).start()
            self._init_voice_engine()

    def _auto_download_kokoro_models(self) -> None:
        LOCAL_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        for fname, url in KOKORO_AUTO_FILES:
            dst = LOCAL_MODELS_DIR / fname
            if dst.exists() and dst.stat().st_size > 1_000_000:
                continue
            tmp_dst = LOCAL_MODELS_DIR / f"{fname}.part"
            print(
                f"[LocalVoice] First-time setup: downloading {fname} from official kokoro-onnx release...",
                flush=True,
            )
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=180.0) as resp:
                    total = int(resp.headers.get("Content-Length") or 0)
                    downloaded = 0
                    last_pct = -10
                    with tmp_dst.open("wb") as wf:
                        while True:
                            chunk = resp.read(1024 * 512)
                            if not chunk:
                                break
                            wf.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = int(downloaded * 100 / total)
                                if pct >= last_pct + 20:
                                    last_pct = pct
                                    mb_done = downloaded / (1024 * 1024)
                                    mb_tot = total / (1024 * 1024)
                                    print(
                                        f"  -> {fname}: {pct}% ({mb_done:.1f} / {mb_tot:.1f} MB)",
                                        flush=True,
                                    )
                if tmp_dst.exists() and tmp_dst.stat().st_size > 1_000_000:
                    tmp_dst.replace(dst)
                    print(f"[LocalVoice] Saved {dst.name} ({dst.stat().st_size // (1024 * 1024)} MB).", flush=True)
            except Exception as e:
                print(f"[LocalVoice] Auto-download warning for {fname}: {e}", flush=True)

    def _find_model_files(self) -> tuple[Path | None, Path | None]:
        for base in (LOCAL_MODELS_DIR, FALLBACK_MODELS_DIR):
            v = base / "voices-v1.0.bin"
            for m_name in ("kokoro-v1.0.onnx", "kokoro-v1.0.int8.onnx"):
                m = base / m_name
                if m.exists() and v.exists():
                    return m, v
        self._auto_download_kokoro_models()
        v = LOCAL_MODELS_DIR / "voices-v1.0.bin"
        for m_name in ("kokoro-v1.0.onnx", "kokoro-v1.0.int8.onnx"):
            m = LOCAL_MODELS_DIR / m_name
            if m.exists() and v.exists():
                return m, v
        return None, None

    def _synth_koboldcpp_wav(self, text: str, gain: float = 1.0) -> bytes | None:
        """Synthesizes a clause into WAV bytes via KoboldCpp's unified audio.cpp TTS endpoints."""
        voice_id = "af_bella" if self.voice_name == "lucy_blend" else self.voice_name
        for endpoint, payload in (
            (
                f"{self.koboldcpp_url}/api/extra/tts",
                {"input": text, "voice": voice_id},
            ),
            (
                f"{self.koboldcpp_url}/v1/audio/speech",
                {"input": text, "voice": voice_id, "response_format": "wav"},
            ),
        ):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    wav_bytes = resp.read()
                    if wav_bytes and wav_bytes.startswith(b"RIFF"):
                        return _scale_wav_bytes(wav_bytes, gain)
            except Exception:
                continue
        return None

    def _init_voice_engine(self) -> None:
        if self.tts_backend == "koboldcpp":
            self.use_kobold_tts = True
            threading.Thread(target=self._synth_worker, daemon=True).start()
            print(
                f"[LocalVoice] KoboldCpp (audio.cpp) HTTP TTS streaming ready at {self.koboldcpp_url} (voice='{self.voice_name}').",
                flush=True,
            )
            return

        # Try local Kokoro-ONNX first
        try:
            from kokoro_onnx import Kokoro

            model_path, voices_path = self._find_model_files()
            if model_path and voices_path:
                self.kokoro = Kokoro(str(model_path), str(voices_path))
                self.voice_style = self.resolve_voice(self.voice_name)
                self.kokoro.create("Okey-dokey.", voice=self.voice_style, speed=1.05, lang=self.lang)

                threading.Thread(target=self._synth_worker, daemon=True).start()
                threading.Thread(target=self._prewarm_barks_worker, daemon=True).start()
                print(
                    f"[LocalVoice] Kokoro-ONNX synchronous streaming ready (voice='{self.voice_name}', lang='{self.lang}').",
                    flush=True,
                )
                self.play_bark_fast("Okey-dokey, let's get to it!", distance_m=2.0)
                return
        except Exception as e:
            print(f"[LocalVoice] Kokoro-ONNX init warning: {e}", flush=True)

        # Automatic fallback to KoboldCpp audio.cpp TTS when tts_backend == "auto"
        if self.tts_backend == "auto":
            self.use_kobold_tts = True
            threading.Thread(target=self._synth_worker, daemon=True).start()
            print(
                f"[LocalVoice] Local Kokoro-ONNX files not found; auto-enabled KoboldCpp (audio.cpp) TTS fallback at {self.koboldcpp_url} "
                f"(or place kokoro-v1.0.int8.onnx & voices-v1.0.bin in {LOCAL_MODELS_DIR}).",
                flush=True,
            )
        else:
            print("[LocalVoice] Kokoro model files not found; running in pre-cached barks + HUD mode.", flush=True)

    def resolve_voice(self, name: str):
        """Returns either a custom blended style vector ('lucy_blend') or a standard Kokoro voice style."""
        if not self.kokoro:
            return name
        if name == "lucy_blend" and np is not None:
            return (
                0.60 * self.kokoro.get_voice_style("af_heart")
                + 0.25 * self.kokoro.get_voice_style("af_bella")
                + 0.15 * self.kokoro.get_voice_style("bf_emma")
            ).astype(np.float32)
        if name in self.kokoro.get_voices():
            return self.kokoro.get_voice_style(name)
        return self.kokoro.get_voice_style("af_heart")

    def _synthesize_single_clause(self, clause: str, gain: float) -> bytes | None:
        if self.kokoro is not None:
            samples, sr = self.kokoro.create(clause, voice=self.voice_style, speed=1.04, lang=self.lang)
            return _float_to_wav(samples, sr, gain=gain)
        if self.use_kobold_tts:
            return self._synth_koboldcpp_wav(clause, gain=gain)
        return None

    def play_bark_fast(self, text: str, distance_m: float = 2.0) -> float:
        """Plays a pre-cached iconic bark from disk in 0.00s latency (or streams it if not cached yet)."""
        if not self.enabled or not text or distance_m > 40.0:
            return 0.0
        try:
            from barks import bark_cache_path

            cache_f = bark_cache_path(text, self.voice_name)
            if cache_f.exists():
                wav_bytes = cache_f.read_bytes()
                try:
                    self._play_queue.put_nowait(wav_bytes)
                except queue.Full:
                    pass
                return 0.0
        except Exception:
            pass
        if not self.kokoro and not self.use_kobold_tts:
            return 0.0
        self.speak(text, distance_m=distance_m, block=False)
        return 0.18

    def _prewarm_barks_worker(self) -> None:
        """Pre-synthesizes and caches all iconic Lucy barks on disk for 0.00s instant playback."""
        if not self.kokoro:
            return
        try:
            from barks import BARKS_EN, bark_cache_path

            built = 0
            for lines in BARKS_EN.values():
                for line in lines:
                    cf = bark_cache_path(line, self.voice_name)
                    if not cf.exists():
                        samples, sr = self.kokoro.create(line, voice=self.voice_style, speed=1.04, lang=self.lang)
                        wav_bytes = _float_to_wav(samples, sr, gain=self.volume)
                        cf.write_bytes(wav_bytes)
                        built += 1
            if built > 0:
                print(f"[LocalVoice-EN] Pre-cached {built} iconic voice barks (0.00s latency).", flush=True)
        except Exception as e:
            print(f"[LocalVoice-EN] Bark prewarm note: {e}", flush=True)

    def speak_clause(self, clause: str, distance_m: float = 2.0) -> None:
        """Immediately queues a single clause for synthesis and playback (used by token streaming)."""
        if not self.enabled or (not self.kokoro and not self.use_kobold_tts) or not clause or distance_m > 40.0:
            return
        clause = clause.strip()
        if not clause:
            return
        try:
            self._synth_queue.put_nowait(([clause], distance_m))
        except queue.Full:
            pass

    def speak(self, text: str, distance_m: float = 2.0, block: bool = False) -> float:
        """Streams `text` clause-by-clause. Returns time-to-first-audio (ms) if `block=True`."""
        if not self.enabled or (not self.kokoro and not self.use_kobold_tts) or not text or distance_m > 40.0:
            return 0.0
        clauses = split_into_clauses(text)
        if not clauses:
            return 0.0

        if not block:
            try:
                self._synth_queue.put_nowait((clauses, distance_m))
            except queue.Full:
                pass
            return 0.0

        # Synchronous blocking mode with TTFA measurement (great for testing/demos)
        dist_factor = 1.0 if distance_m <= 8.0 else max(0.25, 1.0 - 0.75 * (distance_m - 8.0) / 32.0)
        gain = self.volume * dist_factor
        local_q: queue.Queue = queue.Queue()
        ttfa_ms = 0.0
        t0 = time.perf_counter()

        def producer():
            nonlocal ttfa_ms
            for idx, clause in enumerate(clauses):
                wav_bytes = self._synthesize_single_clause(clause, gain=gain)
                if wav_bytes:
                    if idx == 0:
                        ttfa_ms = (time.perf_counter() - t0) * 1000.0
                    local_q.put(wav_bytes)
            local_q.put(None)

        threading.Thread(target=producer, daemon=True).start()
        while True:
            wav = local_q.get()
            if wav is None:
                break
            winsound.PlaySound(wav, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        return ttfa_ms

    def _synth_worker(self) -> None:
        while True:
            clauses, distance_m = self._synth_queue.get()
            dist_factor = 1.0 if distance_m <= 8.0 else max(0.25, 1.0 - 0.75 * (distance_m - 8.0) / 32.0)
            gain = self.volume * dist_factor
            for clause in clauses:
                try:
                    wav_bytes = self._synthesize_single_clause(clause, gain=gain)
                    if wav_bytes:
                        self._play_queue.put(wav_bytes)
                except Exception as e:
                    print(f"[LocalVoice] Clause synth error: {e}", flush=True)

    def _play_worker(self) -> None:
        while True:
            wav_bytes = self._play_queue.get()
            try:
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
            except Exception as e:
                print(f"[LocalVoice] Audio playback error: {e}", flush=True)
