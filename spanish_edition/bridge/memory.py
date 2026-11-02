"""Episodic cross-session memory for Lucy MacLean using local Ollama."""

import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import personas
from decide import OLLAMA_URL
from prompt import persona_text

HERE = Path(__file__).parent
LOG_DIR = HERE / "logs"
RECAP_RULES = HERE / "prompts" / "recap.md"
SESSION_GAP_S = 20 * 60
JOURNAL_MAX = 15
USED_LINES_MAX = 50
_lock = threading.Lock()

RECAP_SCHEMA = {
    "type": "object",
    "properties": {
        "session_summary": {
            "type": "string",
            "description": "1 or 2 sentences in English in Lucy's voice summarizing this play session.",
        },
        "journal": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of key first-person memories in English (max 15 short sentences).",
        },
        "trust_delta": {"type": "integer", "enum": [-3, -2, -1, 0, 1, 2, 3]},
        "respect_delta": {"type": "integer", "enum": [-3, -2, -1, 0, 1, 2, 3]},
    },
    "required": ["session_summary", "journal", "trust_delta", "respect_delta"],
    "additionalProperties": False,
}


def _at(entry: dict) -> float:
    return datetime.fromisoformat(entry["at"]).timestamp()


def turns_after(stamp: str) -> list[dict]:
    turns = []
    if not LOG_DIR.exists():
        return turns
    for path in sorted(LOG_DIR.glob("20*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry["at"] > stamp:
                turns.append(entry)
    return turns


def split_sessions(turns: list[dict]) -> list[list[dict]]:
    sessions = []
    for t in turns:
        if sessions and _at(t) - _at(sessions[-1][-1]) < SESSION_GAP_S:
            sessions[-1].append(t)
        else:
            sessions.append([t])
    return sessions


def _transcript(turns: list[dict]) -> str:
    lines = []
    for t in turns[-150:]:
        s, d = t["snapshot"], t["decision"]
        when = datetime.fromisoformat(t["at"]).astimezone().strftime("%H:%M")
        what = s.get("event") or ""
        if s.get("hotkey"):
            what += f" ({s['hotkey']})"
        latest = (s.get("recent_events") or [""])[-1]
        world = s.get("world", {})
        place = world.get("location") or world.get("region") or ""
        row = f"{when} [{what}] {place}: {latest}"
        if d.get("say"):
            row += f' | Lucy said: "{d["say"]}"'
        lines.append(row)
    return "\n".join(lines)


def recap(state: dict, turns: list[dict], model: str | None = None) -> dict:
    model_name = model or personas.current()["ollama_model"]
    system = RECAP_RULES.read_text(encoding="utf-8").rstrip() + "\n\n# Persona\n\n" + persona_text()
    known = {k: state.get(k) for k in ("trust", "respect", "journal", "last_session", "sessions")}
    body = (
        "WHAT SHE REMEMBERS SO FAR\n"
        + json.dumps(known, indent=1, ensure_ascii=False)
        + "\n\nTHE SESSION JUST ENDED\n"
        + _transcript(turns)
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": body},
        ],
        "format": RECAP_SCHEMA,
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": 0.6, "repeat_penalty": 1.18, "num_ctx": 8192, "num_predict": 450},
    }

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45.0) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    r = json.loads(raw["message"]["content"])
    said = [t["decision"]["say"] for t in turns if t["decision"].get("say")]
    ended = datetime.fromisoformat(turns[-1]["at"]).astimezone()

    state["trust"] = max(0, min(100, state["trust"] + int(r.get("trust_delta", 0))))
    state["respect"] = max(0, min(100, state["respect"] + int(r.get("respect_delta", 0))))
    state["journal"] = [j for j in r.get("journal", []) if j.strip()][-JOURNAL_MAX:]
    state["used_lines"] = (state.get("used_lines", []) + said)[-USED_LINES_MAX:]
    state["sessions"] = state.get("sessions", 0) + 1
    state["last_session"] = {
        "ended": ended.strftime("%Y-%m-%d %H:%M"),
        "summary": r.get("session_summary", ""),
    }
    state["summarized_through"] = turns[-1]["at"]

    LOG_DIR.mkdir(exist_ok=True)
    with (LOG_DIR / "recaps.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"at": datetime.now(timezone.utc).isoformat(), "turns": len(turns), "recap": r},
                ensure_ascii=False,
            )
            + "\n"
        )
    return state


def since_last_session(state: dict) -> str:
    last = state.get("last_session")
    if not last:
        return ""
    gap = datetime.now() - datetime.strptime(last["ended"], "%Y-%m-%d %H:%M")
    if gap.days >= 1:
        return f"{gap.days} day{'s' if gap.days > 1 else ''} ago"
    hours = gap.seconds // 3600
    if hours:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    minutes = max(1, gap.seconds // 60)
    return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
