"""100% Local Decision Engine via Ollama (CPU P-Core Streaming Mode for Zero Fallout 4 GPU Contention)."""

import json
import os
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

FALLBACK_ACTION = {
    "reason": "default local fallback",
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


def decide(
    state: dict,
    snapshot: dict,
    model: str | None = None,
    timeout_s: float = 25.0,
    on_clause: Callable[[str], None] | None = None,
) -> Result:
    """Streams decision from local Ollama on CPU P-cores (num_gpu=0) and emits voice clauses in real time."""
    model_name = model or personas.current()["ollama_model"]
    ev = snapshot.get("event")
    is_story = ev == "campfire"
    is_chat = ev == "player_chat"
    max_tokens = 200 if (is_story or is_chat) else 90
    max_say = 850 if (is_story or is_chat) else 320
    allow_okey = bool(snapshot.get("allow_okey_dokey", False))

    # Keep system message 100% static across all events so Ollama's KV cache never invalidates
    json_hint = (
        '\nRespond ONLY with a single JSON object putting "say" FIRST: '
        '{"say": "...", "action": "follow", "mood": "cheerful"} '
        'where "say" MUST be written in American English in first person ("I", "my") as Lucy MacLean from Vault 33, '
        'answering ONLY the exact topic asked without mixing unrelated topics.'
    )
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt() + json_hint},
            {"role": "user", "content": user_message(state, snapshot)},
        ],
        "format": "json",
        "stream": True,
        "keep_alive": -1,
        "options": {
            "num_gpu": 0,
            "num_thread": 8,
            "num_ctx": 2048,
            "num_predict": max_tokens,
            "temperature": 0.55,
            "top_p": 0.88,
        },
    }

    started = time.perf_counter()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    content_parts: list[str] = []
    eval_count = 0
    eval_duration_ns = 0
    spoken_len = 0
    say_finished = False
    ttfa_s = 0.0
    streamed_any = False

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                chunk = json.loads(line)
                token_str = chunk.get("message", {}).get("content", "")
                if token_str:
                    content_parts.append(token_str)
                    if on_clause is not None and not say_finished:
                        buf = "".join(content_parts)
                        m = _SAY_PARTIAL_RE.search(buf)
                        if m:
                            raw_say = m.group(1)
                            closed = m.group(2) == '"'
                            if not allow_okey and not closed and len(raw_say) < 14:
                                pass
                            else:
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
                if chunk.get("done"):
                    eval_count = chunk.get("eval_count", 0)
                    eval_duration_ns = chunk.get("eval_duration", 0)
                    break
    except Exception as e:
        return Result(
            dict(FALLBACK_ACTION),
            model_name,
            time.perf_counter() - started,
            error=f"{type(e).__name__}: {e}",
        )

    latency = time.perf_counter() - started
    tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
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
