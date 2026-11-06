"""Motor de voz local por cláusulas en tiempo real compatible con Kokoro-ONNX (82M) y KoboldCpp (audio.cpp TTS).

Se ejecuta 100% en local sin consumo de VRAM para Fallout 4 y Fallout 4 VR.
Divide cada frase en cláusulas naturales para que la primera cláusula empiece a sonar en ~180 ms
mientras las siguientes se sintetizan en paralelo en segundo plano.
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

# Asegura que eSpeak NG esté configurado en Windows antes de importar kokoro_onnx
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

# Divide en límites de oración (. ! ?) o tras coma/punto y coma cuando la primera cláusula es corta
CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=[,;—])\s+")


def split_into_clauses(text: str) -> list[str]:
    """Divide una frase en cláusulas para que el primer fragmento sea corto (~2-7 palabras) y suene al instante (<220 ms)."""
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
    """Escala el volumen de un WAV PCM de 16 bits usando únicamente la librería estándar de Python."""
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
        self.lang = cfg.get("language", "es")
        self.tts_backend = cfg.get("tts_backend", "auto")
        self.koboldcpp_url = cfg.get("koboldcpp_url", "http://127.0.0.1:5001")
        self.kokoro = None
        self.voice_style = None
        self.use_kobold_tts = False

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
                f"[LocalVoice-ES] Configuración inicial: descargando {fname} desde la release oficial de kokoro-onnx...",
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
                    print(f"[LocalVoice-ES] Guardado {dst.name} ({dst.stat().st_size // (1024 * 1024)} MB).", flush=True)
            except Exception as e:
                print(f"[LocalVoice-ES] Aviso en descarga automática de {fname}: {e}", flush=True)

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
        """Sintetiza una cláusula en WAV mediante los endpoints TTS audio.cpp unificados de KoboldCpp."""
        voice_id = "ef_dora" if self.voice_name == "lucy_blend" else self.voice_name
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
                f"[LocalVoice-ES] Streaming TTS por HTTP con KoboldCpp (audio.cpp) activo en {self.koboldcpp_url} (voz='{self.voice_name}').",
                flush=True,
            )
            return

        # Primero intenta Kokoro-ONNX local
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
                    f"[LocalVoice-ES] Kokoro-ONNX listo para streaming síncrono (voz='{self.voice_name}', idioma='{self.lang}').",
                    flush=True,
                )
                self.play_bark_fast("¡Oki-doki, vamos al lío!", distance_m=2.0)
                return
        except Exception as e:
            print(f"[LocalVoice-ES] Aviso al inicializar Kokoro-ONNX: {e}", flush=True)

        # Fallback automático a KoboldCpp audio.cpp TTS cuando tts_backend == "auto"
        if self.tts_backend == "auto":
            self.use_kobold_tts = True
            threading.Thread(target=self._synth_worker, daemon=True).start()
            print(
                f"[LocalVoice-ES] Archivos de Kokoro-ONNX no encontrados; activado automáticamente KoboldCpp (audio.cpp) TTS en {self.koboldcpp_url} "
                f"(o coloca kokoro-v1.0.int8.onnx y voices-v1.0.bin en {LOCAL_MODELS_DIR}).",
                flush=True,
            )
        else:
            print("[LocalVoice-ES] Archivos de modelo Kokoro no encontrados; usando modo de barks pre-cacheados + subtítulos HUD.", flush=True)

    def resolve_voice(self, name: str):
        """Devuelve un vector mezclado personalizado ('lucy_blend') o un estilo de voz estándar de Kokoro."""
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
        """Reproduce una frase icónica pre-cacheada en disco con latencia 0.00s (o la sintetiza al vuelo si aún no está en caché)."""
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
        """Pre-genera y guarda en disco todos los WAVs de las frases icónicas de Lucy para reproducción en 0.00s."""
        if not self.kokoro:
            return
        try:
            from barks import BARKS_ES, bark_cache_path

            built = 0
            for lines in BARKS_ES.values():
                for line in lines:
                    cf = bark_cache_path(line, self.voice_name)
                    if not cf.exists():
                        samples, sr = self.kokoro.create(line, voice=self.voice_style, speed=1.04, lang=self.lang)
                        wav_bytes = _float_to_wav(samples, sr, gain=self.volume)
                        cf.write_bytes(wav_bytes)
                        built += 1
            if built > 0:
                print(f"[LocalVoice-ES] Pre-cacheados {built} audios de frases icónicas (barks 0.00s).", flush=True)
        except Exception as e:
            print(f"[LocalVoice-ES] Aviso en prewarm de barks: {e}", flush=True)

    def speak_clause(self, clause: str, distance_m: float = 2.0) -> None:
        """Encola inmediatamente una cláusula individual para síntesis y reproducción (usado por el streaming de tokens)."""
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
        """Transmite `text` cláusula por cláusula. Devuelve el tiempo hasta el primer audio (ms) si `block=True`."""
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
                    print(f"[LocalVoice-ES] Error de síntesis en cláusula: {e}", flush=True)

    def _play_worker(self) -> None:
        while True:
            wav_bytes = self._play_queue.get()
            try:
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
            except Exception as e:
                print(f"[LocalVoice-ES] Error de reproducción de audio: {e}", flush=True)
