"""Synchronous Clause-Streaming Local Voice Engine powered by Kokoro-ONNX (82M).

Runs 100% on CPU (0 MB VRAM overhead for Fallout 4 & Ollama) at ~5x real-time speed.
Splits each companion line into natural clauses so the first clause ("Okey-dokey!",
"Oh, sugar!", etc.) finishes synthesizing in ~180 ms and begins playing immediately
while subsequent clauses synthesize in parallel in the background.
"""

import os
import queue
import re
import struct
import threading
import time
import winsound
from pathlib import Path

# Ensure eSpeak NG path is configured on Windows before importing kokoro_onnx
if "PHONEMIZER_ESPEAK_PATH" not in os.environ and Path(r"C:\Program Files\eSpeak NG").exists():
    os.environ["PHONEMIZER_ESPEAK_PATH"] = r"C:\Program Files\eSpeak NG"

import numpy as np
import personas

HERE = Path(__file__).parent
LOCAL_MODELS_DIR = HERE / "models" / "kokoro"
FALLBACK_MODELS_DIR = Path(r"C:\proyectos_python\MisApps\Texto_a_voz")

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


def _float_to_wav(samples: np.ndarray, sample_rate: int, gain: float = 1.0) -> bytes:
    arr = np.clip(samples * gain, -1.0, 1.0)
    pcm16 = (arr * 32767.0).astype(np.int16).tobytes()
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm16)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(pcm16))
    return header + pcm16


class LocalVoice:
    def __init__(self, enabled: bool | None = None, voice_name: str | None = None):
        cfg = personas.current()
        self.enabled = cfg["voice_enabled"] if enabled is None else enabled
        self.voice_name = voice_name or cfg["kokoro_voice"]
        self.volume = cfg["voice_volume"]
        self.lang = cfg.get("language", "en-us")
        self.kokoro = None
        self.voice_style = None

        # Two-stage pipeline for synchronous streaming:
        # 1. _synth_queue receives (clauses, distance_m) and synthesizes clause-by-clause
        # 2. _play_queue receives ready WAV bytes and plays them back-to-back with zero gap
        self._synth_queue: queue.Queue = queue.Queue(maxsize=16)
        self._play_queue: queue.Queue = queue.Queue(maxsize=16)

        if self.enabled:
            self._init_kokoro()

    def _find_model_files(self) -> tuple[Path | None, Path | None]:
        for base in (LOCAL_MODELS_DIR, FALLBACK_MODELS_DIR):
            m = base / "kokoro-v1.0.onnx"
            v = base / "voices-v1.0.bin"
            if m.exists() and v.exists():
                return m, v
        LOCAL_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        print(
            f"[LocalVoice] Place kokoro-v1.0.onnx and voices-v1.0.bin inside {LOCAL_MODELS_DIR} to enable neural voice synthesis.",
            flush=True,
        )
        return None, None

    def _init_kokoro(self) -> None:
        try:
            from kokoro_onnx import Kokoro

            model_path, voices_path = self._find_model_files()
            if not model_path or not voices_path:
                print("[LocalVoice] Kokoro model files not found; running in HUD-subtitle-only mode.", flush=True)
                self.enabled = False
                return

            self.kokoro = Kokoro(str(model_path), str(voices_path))
            self.voice_style = self.resolve_voice(self.voice_name)
            # Warmup synthesis so the ONNX session is hot
            self.kokoro.create("Okey-dokey.", voice=self.voice_style, speed=1.05, lang=self.lang)

            threading.Thread(target=self._synth_worker, daemon=True).start()
            threading.Thread(target=self._play_worker, daemon=True).start()
            threading.Thread(target=self._prewarm_barks_worker, daemon=True).start()
            print(
                f"[LocalVoice] Kokoro-ONNX synchronous streaming ready (voice='{self.voice_name}', lang='{self.lang}').",
                flush=True,
            )
        except Exception as e:
            print(f"[LocalVoice] Failed to initialize Kokoro-ONNX ({e}); using HUD subtitles only.", flush=True)
            self.enabled = False

    def resolve_voice(self, name: str):
        """Returns either a custom blended style vector ('lucy_blend') or a standard Kokoro voice style."""
        if not self.kokoro:
            return name
        if name == "lucy_blend":
            # Custom Ella Purnell / Lucy MacLean blend:
            # 60% af_heart (warm, expressive Grade-A American)
            # + 25% af_bella (bright, enthusiastic Vault-girl energy)
            # + 15% bf_emma (subtle crisp articulation)
            return (
                0.60 * self.kokoro.get_voice_style("af_heart")
                + 0.25 * self.kokoro.get_voice_style("af_bella")
                + 0.15 * self.kokoro.get_voice_style("bf_emma")
            ).astype(np.float32)
        if name in self.kokoro.get_voices():
            return self.kokoro.get_voice_style(name)
        return self.kokoro.get_voice_style("af_heart")

    def play_bark_fast(self, text: str, distance_m: float = 2.0) -> float:
        """Plays a pre-cached iconic bark from disk in 0.00s latency (or streams it if not cached yet)."""
        if not self.enabled or not self.kokoro or not text or distance_m > 40.0:
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
        self.speak(text, distance_m=distance_m, block=False)
        return 0.18

    def _prewarm_barks_worker(self) -> None:
        """Pre-synthesizes and caches all iconic Lucy barks on disk for 0.00s instant playback."""
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
        if not self.enabled or not self.kokoro or not clause or distance_m > 40.0:
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
        if not self.enabled or not self.kokoro or not text or distance_m > 40.0:
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
                samples, sr = self.kokoro.create(clause, voice=self.voice_style, speed=1.04, lang=self.lang)
                wav_bytes = _float_to_wav(samples, sr, gain=gain)
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
                    samples, sr = self.kokoro.create(clause, voice=self.voice_style, speed=1.04, lang=self.lang)
                    wav_bytes = _float_to_wav(samples, sr, gain=gain)
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
