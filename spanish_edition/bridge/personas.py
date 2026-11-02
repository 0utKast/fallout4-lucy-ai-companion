"""Carga el perfil del compañero activo desde bridge/companions/<id>/companion.ini."""

import configparser
import os
from pathlib import Path

HERE = Path(__file__).parent
COMPANIONS_DIR = HERE / "companions"

NAME = os.environ.get("FO4_COMPANION", "lucy").strip().lower()


def load(companion_id: str | None = None) -> dict:
    cid = (companion_id or NAME).strip().lower()
    cdir = COMPANIONS_DIR / cid
    if not cdir.exists():
        cdir = COMPANIONS_DIR / "lucy"
        cid = "lucy"
    ini_path = cdir / "companion.ini"
    cfg = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    if ini_path.exists():
        cfg.read(ini_path, encoding="utf-8")
    sec = cfg["companion"] if "companion" in cfg else {}
    return {
        "id": cid,
        "dir": cdir,
        "name": sec.get("name", "Lucy").strip(),
        "full_name": sec.get("full_name", "Lucy MacLean (Refugio 33)").strip(),
        "language": sec.get("language", "es").strip(),
        "llm_backend": (os.environ.get("LLM_BACKEND") or sec.get("llm_backend", "auto")).strip().lower(),
        "ollama_model": os.environ.get("OLLAMA_MODEL") or sec.get("ollama_model", "qwen2.5:3b").strip(),
        "koboldcpp_url": (os.environ.get("KOBOLDCPP_URL") or sec.get("koboldcpp_url", "http://127.0.0.1:5001")).strip().rstrip("/"),
        "comment_cooldown_s": int(sec.get("comment_cooldown_s", "45")),
        "variety_mode": sec.get("variety_mode", "yes").strip().lower() in ("yes", "true", "1"),
        "voice_enabled": (os.environ.get("VOICE_ENABLED") or sec.get("voice_enabled", "yes")).strip().lower() in ("yes", "true", "1"),
        "tts_backend": (os.environ.get("TTS_BACKEND") or sec.get("tts_backend", "auto")).strip().lower(),
        "kokoro_voice": os.environ.get("KOKORO_VOICE") or sec.get("kokoro_voice", "ef_dora").strip(),
        "voice_volume": float(os.environ.get("VOICE_VOLUME") or sec.get("voice_volume", "0.85")),
    }


_CURRENT = None


def current() -> dict:
    global _CURRENT
    if _CURRENT is None:
        _CURRENT = load()
    return _CURRENT
