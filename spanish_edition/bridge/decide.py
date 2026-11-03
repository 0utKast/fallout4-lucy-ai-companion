"""Motor de decisión 100% local compatible con Ollama (:11434) y KoboldCpp (:5001) con streaming por cláusulas."""

import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

import personas
from prompt import system_prompt, user_message
from schema import validate

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
_ollama_autostart_lock = False


def ensure_ollama_running() -> bool:
    """Comprueba si Ollama responde en 127.0.0.1:11434 y, si está apagado, inicia la app oficial de bandeja."""
    global _ollama_autostart_lock
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1.5) as r:
            if r.status == 200:
                return True
    except Exception:
        pass

    if _ollama_autostart_lock:
        return False
    _ollama_autostart_lock = True
    try:
        ollama_dir = Path.home() / "AppData" / "Local" / "Programs" / "Ollama"
        started_any = False
        if hasattr(os, "startfile") and ollama_dir.is_dir():
            for entry in sorted(ollama_dir.iterdir()):
                if entry.stem.lower() == "ollama app":
                    print("[Ollama] Servicio local apagado. Iniciando Ollama automáticamente...", flush=True)
                    os.startfile(str(entry))
                    started_any = True
                    break
        if not started_any:
            return False

        for _ in range(24):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1.5) as r:
                    if r.status == 200:
                        print("[Ollama] Servicio local activo en 127.0.0.1:11434.", flush=True)
                        return True
            except Exception:
                pass
    except Exception as e:
        print(f"[Ollama] No se pudo auto-iniciar Ollama: {e}", flush=True)
    finally:
        _ollama_autostart_lock = False
    return False

FALLBACK_ACTION = {
    "reason": "fallback local por defecto",
    "action": "follow",
    "target": "",
    "say": "",
    "mood": "optimistic",
    "trust_delta": 0,
    "respect_delta": 0,
    "memory_note": "",
}

_SAY_PARTIAL_RE = re.compile(r'"say"\s*:\s*"((?:[^"\\]|\\.)*)(")?')
_CLAUSE_BOUNDARY_RE = re.compile(r"^(.+?[.!?])(\s+)|^((?:\S+\s+){2,}\S+[,;—])(\s+)")


@dataclass
class Result:
    decision: dict
    model: str
    latency_s: float
    eval_count: int = 0
    tokens_per_s: float = 0.0
    ttfa_s: float = 0.0
    streamed_voice: bool = False
    problems: list = None
    error: str = ""

    def __post_init__(self):
        if self.problems is None:
            self.problems = []


def _trim_say(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        for sep in (".", "!", "?"):
            if text.endswith(sep):
                return text
    cut = text[:max_chars]
    for sep in (". ", "! ", "? ", ".", "!", "?"):
        idx = cut.rfind(sep)
        if idx > 35:
            return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0].strip() + "."


def _clean_partial_say(raw_escaped: str, allow_okey: bool) -> str:
    text = raw_escaped.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
    text = re.sub(r"[^\x00-\xFF¡¿«»—–’'\"…]+", "", text)
    text = re.sub(r"\s{2,}", " ", text).lstrip()
    if not allow_okey and len(text) > 12:
        text = re.sub(r"^(okey[- ]?dokey|oki[- ]?doki)[!.,]?\s*", "", text, flags=re.IGNORECASE).lstrip()
        if text:
            text = text[0].upper() + text[1:]
    return text


def _stream_koboldcpp(
    kobold_url: str,
    messages: list[dict],
    max_tokens: int,
    timeout_s: float,
    on_token: Callable[[str], None],
) -> tuple[int, float]:
    """Transmite tokens desde el endpoint compatible con OpenAI /v1/chat/completions de KoboldCpp."""
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.55,
        "top_p": 0.88,
        "response_format": {"type": "json_object"},
        "stream": True,
    }
    req = urllib.request.Request(
        f"{kobold_url}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    token_count = 0
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    pkt = json.loads(data_str)
                except Exception:
                    continue
                choices = pkt.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or choices[0].get("message") or {}
                    tok = delta.get("content") or ""
                    if tok:
                        token_count += 1
                        on_token(tok)
            elif line.startswith("{"):
                try:
                    pkt = json.loads(line)
                    choices = pkt.get("choices") or []
                    if choices:
                        msg = choices[0].get("message") or {}
                        tok = msg.get("content") or ""
                        if tok:
                            token_count += max(1, len(tok.split()))
                            on_token(tok)
                except Exception:
                    pass
    dt = max(0.001, time.perf_counter() - t0)
    return token_count, token_count / dt


def decide(
    state: dict,
    snapshot: dict,
    model: str | None = None,
    timeout_s: float = 25.0,
    on_clause: Callable[[str], None] | None = None,
) -> Result:
    """Genera la respuesta en streaming desde Ollama (:11434) o KoboldCpp (:5001) y emite cláusulas de voz en español."""
    cfg = personas.current()
    model_name = model or cfg["ollama_model"]
    llm_backend = cfg.get("llm_backend", "auto")
    kobold_url = cfg.get("koboldcpp_url", "http://127.0.0.1:5001")

    ev = snapshot.get("event")
    is_story = ev == "campfire"
    is_chat = ev == "player_chat"
    max_tokens = 115 if (is_story or is_chat) else 75
    max_say = 520 if (is_story or is_chat) else 260
    allow_okey = bool(snapshot.get("allow_okey_dokey", False))

    # Mensaje system 100% estático para que la caché KV nunca se invalide
    json_hint = (
        '\nResponde ÚNICAMENTE con un objeto JSON poniendo "say" PRIMERO: '
        '{"say": "...", "action": "follow", "mood": "cheerful"} '
        'donde "say" DEBE estar escrito 100% en español natural en primera persona ("yo", "mi") como Lucy MacLean del Refugio 33, '
        'respondiendo exclusivamente a lo que se te pregunta sin mezclar otros temas.'
    )
    messages = [
        {"role": "system", "content": system_prompt() + json_hint},
        {"role": "user", "content": user_message(state, snapshot)},
    ]

    started = time.perf_counter()
    content_parts: list[str] = []
    eval_count = 0
    eval_duration_ns = 0
    spoken_len = 0
    say_finished = False
    ttfa_s = 0.0
    streamed_any = False

    def _on_token(token_str: str) -> None:
        nonlocal spoken_len, say_finished, ttfa_s, streamed_any
        content_parts.append(token_str)
        if on_clause is not None and not say_finished:
            buf = "".join(content_parts)
            m = _SAY_PARTIAL_RE.search(buf)
            if m:
                raw_say = m.group(1)
                closed = m.group(2) == '"'
                if not allow_okey and not closed and len(raw_say) < 14:
                    return
                clean_say = _clean_partial_say(raw_say, allow_okey)
                while True:
                    rem = clean_say[spoken_len:]
                    cm = _CLAUSE_BOUNDARY_RE.match(rem)
                    if not cm:
                        break
                    clause = (cm.group(1) or cm.group(3)).strip()
                    spoken_len += len(cm.group(0))
                    if clause:
                        if ttfa_s == 0.0:
                            ttfa_s = time.perf_counter() - started
                        on_clause(clause)
                        streamed_any = True
                if closed:
                    rem = clean_say[spoken_len:].strip()
                    if rem:
                        if ttfa_s == 0.0:
                            ttfa_s = time.perf_counter() - started
                        on_clause(rem)
                        streamed_any = True
                    say_finished = True

    tps = 0.0
    try:
        if llm_backend == "koboldcpp":
            model_name = "koboldcpp"
            eval_count, tps = _stream_koboldcpp(kobold_url, messages, max_tokens, timeout_s, _on_token)
        else:
            payload = {
                "model": model_name,
                "messages": messages,
                "format": "json",
                "stream": True,
                "keep_alive": -1,
                "options": {
                    "num_gpu": 99,
                    "num_ctx": 1024,
                    "num_predict": max_tokens,
                    "temperature": 0.55,
                    "top_p": 0.88,
                },
            }
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token_str = chunk.get("message", {}).get("content", "")
                        if token_str:
                            _on_token(token_str)
                        if chunk.get("done"):
                            eval_count = chunk.get("eval_count", 0)
                            eval_duration_ns = chunk.get("eval_duration", 0)
                            break
                tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
            except urllib.error.URLError:
                if ensure_ollama_running():
                    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                        for raw_line in resp:
                            line = raw_line.decode("utf-8", errors="replace").strip()
                            if not line:
                                continue
                            chunk = json.loads(line)
                            token_str = chunk.get("message", {}).get("content", "")
                            if token_str:
                                _on_token(token_str)
                            if chunk.get("done"):
                                eval_count = chunk.get("eval_count", 0)
                                eval_duration_ns = chunk.get("eval_duration", 0)
                                break
                    tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
                elif llm_backend == "auto":
                    model_name = "koboldcpp"
                    eval_count, tps = _stream_koboldcpp(kobold_url, messages, max_tokens, timeout_s, _on_token)
                else:
                    raise
    except Exception as e:
        return Result(
            dict(FALLBACK_ACTION),
            model_name,
            time.perf_counter() - started,
            error=f"{type(e).__name__}: {e}",
        )

    latency = time.perf_counter() - started
    content = "".join(content_parts)

    try:
        decision = json.loads(content)
    except json.JSONDecodeError as e:
        m = _SAY_PARTIAL_RE.search(content)
        if m and m.group(1).strip():
            recovered = _trim_say(_clean_partial_say(m.group(1), allow_okey), max_say)
            decision = {
                "say": recovered,
                "action": "follow",
                "target": "",
                "mood": "optimistic",
            }
        else:
            return Result(
                dict(FALLBACK_ACTION),
                model_name,
                latency,
                eval_count=eval_count,
                tokens_per_s=round(tps, 1),
                ttfa_s=round(ttfa_s, 3),
                streamed_voice=streamed_any,
                error=f"bad JSON: {e}",
            )

    if isinstance(decision.get("say"), str):
        decision["say"] = _trim_say(decision["say"], max_say)
    problems = validate(decision, max_say=max_say)
    if problems:
        return Result(
            dict(FALLBACK_ACTION),
            model_name,
            latency,
            eval_count=eval_count,
            tokens_per_s=round(tps, 1),
            ttfa_s=round(ttfa_s, 3),
            streamed_voice=streamed_any,
            problems=problems,
        )

    return Result(
        decision=decision,
        model=model_name,
        latency_s=latency,
        eval_count=eval_count,
        tokens_per_s=round(tps, 1),
        ttfa_s=round(ttfa_s, 3),
        streamed_voice=streamed_any,
    )
