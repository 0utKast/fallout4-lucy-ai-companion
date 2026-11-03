"""100% Local Bridge Server for Lucy MacLean in Fallout 4 (English Edition + Live Chat F8).

- Connects to local Ollama (127.0.0.1:11434) in CPU P-Core Streaming Mode (num_gpu=0) for zero GPU contention with Fallout 4.
- Interactive Pip-Boy Live Chat Overlay (Press F8 anytime in Fallout 4 to type free-form questions/comments to Lucy).
- Streams clauses in real time from Ollama tokens directly into Kokoro-ONNX (af_bella), the HUD, and `/chat_stream`.
- Maintains multi-turn conversation history (`chat_history`) and persistent state (`state/lucy.json`).
"""

import json
import random
import re
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

import memory
import personas
from barks import is_bark_event, pick_bark_text
from decide import FALLBACK_ACTION, Result, decide
from fo4_resolver import build_or_load_forms_db, enrich_papyrus_snapshot
from hud_subtitle import SubtitleHUD
from lore_rag import get_lore_rag
from voice_local import LocalVoice

HOST, PORT = "127.0.0.1", 7777
HERE = Path(__file__).parent
STATE_FILE = HERE / "state" / f"{personas.current()['id']}.json"
LOG_DIR = HERE / "logs"

FO4_USER_LOGS = [
    root / game_dir / "Logs" / "Script" / "User" / "LucyCompanionBridge.0.log"
    for root in (
        Path.home() / "Documents" / "My Games",
        Path.home() / "OneDrive" / "Documents" / "My Games",
    )
    for game_dir in ("Fallout4", "Fallout4VR")
]
FO4_USER_LOG = FO4_USER_LOGS[0]

DEFAULT_STATE = {
    "trust": 55,
    "respect": 40,
    "companion_name": "Lucy MacLean",
    "vault_origin": "Vault 33",
    "player_title": "Sole Survivor of Vault 111",
    "journal": [
        "I left Vault 33 in Santa Monica searching for my dad Hank, survived The Ghoul (Cooper Howard), traveled with Maximus and CX404, and followed Vault-Tec's trail to the Commonwealth.",
        "Here I met a fellow Vault Dweller from Vault 111—it is such a relief to travel with someone who actually knows how to use a Pip-Boy and doesn't try to harvest my organs!",
    ],
    "sessions": 0,
}

# Lucy MacLean's 10 weighted line styles
LINE_STYLES = {
    "vault_rule": (
        3,
        "Compare what is happening right now to an innocent Vault 33 rule, committee vote, Jell-O cake, or hygiene manual.",
    ),
    "tv_callback": (
        3,
        "Connect the current situation to one specific memory from the Fallout TV show (The Ghoul/Cooper Howard, Maximus in his T-60 Power Armor, your brother Norm, Bud Askins' brain-on-a-Roomba in Vault 31, Snip-Snip at the Super Duper Mart, or one-eyed Overseer Benjamin in Vault 4).",
    ),
    "golden_rule": (
        2,
        "Apply (or cheerfully bend) the Golden Rule ('Do unto others...') to what you and your Vault 111 partner are doing right now.",
    ),
    "fallout_lore": (
        2,
        "Recall a piece of history you taught in Vault 33 classes about California (such as Shady Sands or Vault-Tec's experiments), without confusing it with the current Commonwealth location.",
    ),
    "polite_horror": (
        2,
        "React with wholesome, scandalized Vault-girl politeness ('Oh, sugar!', 'Goodness gracious!') to something gross, irradiated, or violent nearby.",
    ),
    "okey_dokey": (
        2,
        "A short, gutsy reaction that starts or ends with your signature 'Okey-dokey!'.",
    ),
    "player_tease": (
        2,
        "Gently rib your Vault 111 companion about what they are doing right now.",
    ),
    "body_complaint": (
        1,
        "A polite complaint about keeping your blue-and-gold Vault 33 jumpsuit clean, blisters, Geiger counter clicking, or missing Vault 33 beds.",
    ),
    "naive_question": (
        1,
        "Ask one short, disarmingly innocent question about surface habits.",
    ),
    "callback": (
        2,
        "Make a natural callback to one of the memories in your journal.",
    ),
}

STYLE_EXEMPT = {"campfire", "reunion", "player_chat"}
recent_styles: list[str] = []
said_lately: list[str] = []
chat_history: list[dict] = []
last_live_snapshot: dict = {
    "location_name": "Sanctuary Hills",
    "weather": "Clear Sky",
    "player": {"hp": 100, "in_combat": False, "weapon": "10mm Pistol"},
    "companion": {"hp": 100, "in_combat": False, "distance_m": 2.0, "stance": "following"},
    "world": {"location": "Sanctuary Hills", "weather": "Clear Sky", "time": "12:00", "interior": False},
}
last_comment_at = float("-inf")
last_chat_at = float("-inf")
greeted = False
_decide_lock = threading.Lock()


def load_state() -> dict:
    if STATE_FILE.exists():
        return {**DEFAULT_STATE, **json.loads(STATE_FILE.read_text(encoding="utf-8"))}
    return dict(DEFAULT_STATE)


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def apply_decision(state: dict, d: dict) -> dict:
    state["trust"] = max(0, min(100, state["trust"] + int(d.get("trust_delta", 0))))
    state["respect"] = max(0, min(100, state["respect"] + int(d.get("respect_delta", 0))))
    return state


def pick_line_style(state: dict) -> str:
    names = [n for n in LINE_STYLES if n not in recent_styles[-2:]]
    if not state.get("journal"):
        names = [n for n in names if n != "callback"]
    style = random.choices(names, weights=[LINE_STYLES[n][0] for n in names])[0]
    recent_styles.append(style)
    del recent_styles[:-4]
    return style


def _ngrams(text: str, n: int = 4) -> set:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def repeats(line: str, earlier: list[str]) -> bool:
    grams = _ngrams(line)
    return bool(grams) and any(grams & _ngrams(e) for e in earlier)


def log_turn(entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def process_snapshot(
    snapshot: dict,
    hud: SubtitleHUD | None = None,
    voice: LocalVoice | None = None,
    stream_cb: Callable[[str], None] | None = None,
) -> Result:
    global last_comment_at, last_chat_at, greeted, last_live_snapshot
    ev = snapshot.get("event", "heartbeat")
    is_chat = ev == "player_chat"
    if not is_chat:
        snapshot = enrich_papyrus_snapshot(snapshot)
        last_live_snapshot = dict(snapshot)
    else:
        last_chat_at = time.monotonic()

    if ev == "open_chat":
        last_chat_at = time.monotonic()
        if hud:
            hud.open_chat()
        return Result(dict(FALLBACK_ACTION), personas.current()["ollama_model"], 0.0)

    # If Lucy has not been recruited yet, suppress ambient heartbeat exploration lines
    if ev == "heartbeat" and snapshot.get("companion", {}).get("recruited") is False:
        return Result(dict(FALLBACK_ACTION), personas.current()["ollama_model"], 0.0)

    # Instant pre-cached iconic voice barks (0.00s latency): "Okey-dokey, let's get to it!", "All dispatched!", Affinity reactions, etc.
    if is_bark_event(ev):
        bark_text = pick_bark_text(ev)
        if bark_text:
            dist = snapshot.get("companion", {}).get("distance_m", 2.0)
            speaker_name = personas.current()["name"]
            if hud:
                hud.show(speaker_name, bark_text)
            ttfa_b = voice.play_bark_fast(bark_text, distance_m=dist) if voice else 0.0
            last_comment_at = time.monotonic()
            mood_map = {
                "combat_start": "alert",
                "combat_end": "cheerful",
                "companion_hurt": "worried",
                "affinity_dislike": "worried",
                "affinity_hate": "protective",
            }
            bark_dec = {
                "say": bark_text,
                "mood": mood_map.get(ev, "cheerful"),
                "action": "none",
                "trust_delta": 2 if ev in ("recruited", "affinity_like", "affinity_love", "affinity_max_perk") else (-2 if ev in ("affinity_dislike", "affinity_hate") else 0),
                "respect_delta": 1 if ev in ("combat_end", "affinity_like", "affinity_love") else 0,
                "memory_note": "",
            }
            with memory._lock:
                st = apply_decision(load_state(), bark_dec)
                comp_aff = snapshot.get("companion", {}).get("affinity")
                if comp_aff is not None:
                    st["affinity"] = int(comp_aff)
                save_state(st)
            res_bark = Result(bark_dec, "kokoro_bark_cache_en", 0.0, ttfa_s=ttfa_b, streamed_voice=True)
            log_turn(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "model": res_bark.model,
                    "snapshot": snapshot,
                    "decision": bark_dec,
                    "latency_s": 0.0,
                    "ttfa_s": ttfa_b,
                    "tokens_per_s": 0.0,
                    "error": None,
                    "problems": [],
                }
            )
            return res_bark

    # If the player is actively using Live Chat (within the last 120s), suppress ambient heartbeat comments
    if ev == "heartbeat" and ((hud and hud.chat_open) or (time.monotonic() - last_chat_at) < 120.0):
        return Result(dict(FALLBACK_ACTION), personas.current()["ollama_model"], 0.0)

    cooldown = personas.current()["comment_cooldown_s"]
    if snapshot.get("event") == "heartbeat" and (time.monotonic() - last_comment_at) < cooldown:
        return Result(dict(FALLBACK_ACTION), personas.current()["ollama_model"], 0.0)

    with _decide_lock:
        state = load_state()

        if snapshot.get("event") == "summoned" and state.get("sessions") and not greeted:
            snapshot = {
                **snapshot,
                "event": "reunion",
                "last_together": memory.since_last_session(state),
            }

        if snapshot.get("event") in ("summoned", "reunion"):
            greeted = True

        lines = snapshot.get("recent_lines") or []
        snapshot = {
            **snapshot,
            "recent_lines": (said_lately + [l for l in lines if l not in said_lately])[-6:],
            "chat_history": list(chat_history[-4:]),
        }

        if personas.current()["variety_mode"] and snapshot.get("event") not in STYLE_EXEMPT:
            style_key = pick_line_style(state)
            allow_okey = style_key == "okey_dokey" or snapshot.get("event") == "combat_start"
            snapshot = {
                **snapshot,
                "line_style_key": style_key,
                "line_style": LINE_STYLES[style_key][1],
                "allow_okey_dokey": allow_okey,
            }
        else:
            allow_okey = True if snapshot.get("event") in ("summoned", "reunion", "player_chat") else False
            snapshot = {**snapshot, "allow_okey_dokey": allow_okey}

        dist = snapshot.get("companion", {}).get("distance_m", 2.0)
        speaker_name = personas.current()["name"]
        streamed_clauses: list[str] = []

        def _on_clause(clause: str) -> None:
            streamed_clauses.append(clause)
            partial_text = " ".join(streamed_clauses)
            if hud:
                hud.show(speaker_name, partial_text)
            if voice:
                voice.speak_clause(clause, distance_m=dist)
            if stream_cb:
                stream_cb(partial_text)

        result = decide(
            state,
            snapshot,
            timeout_s=15.0 if is_chat else 12.0,
            on_clause=_on_clause if (voice or hud or stream_cb) else None,
        )

        # Keep ASCII + Latin-1 characters (including á, é, í, ó, ú, ñ, ü) and strip only emojis
        say_raw = (result.decision.get("say") or "").strip()
        say_raw = re.sub(r"[^\x00-\xFF¡¿«»—–’'\"…]+", "", say_raw).strip()
        say_raw = re.sub(r"\s{2,}", " ", say_raw)
        if not allow_okey and say_raw:
            say_raw = re.sub(r"^(okey[- ]?dokey|oki[- ]?doki)[!.,]?\s*", "", say_raw, flags=re.IGNORECASE).strip()
            if say_raw:
                say_raw = say_raw[0].upper() + say_raw[1:]
        result.decision["say"] = say_raw

        say_text = (result.decision.get("say") or "").strip()
        if say_text:
            said_lately.append(say_text)
            del said_lately[:-10]
            last_comment_at = time.monotonic()
            if is_chat and snapshot.get("player_text"):
                chat_history.append({"speaker": "Sole Survivor (Vault 111)", "text": snapshot["player_text"]})
                chat_history.append({"speaker": "Lucy MacLean", "text": say_text})
                del chat_history[:-8]

        if not result.error and not result.problems:
            with memory._lock:
                st = apply_decision(load_state(), result.decision)
                if is_chat and snapshot.get("player_text") and say_text:
                    note = f"Chat at {snapshot.get('location_name', 'Commonwealth')}: My Vault 111 partner asked \"{snapshot['player_text'][:80]}\" and I answered \"{say_text[:100]}\"."
                    journal = st.get("journal", [])
                    journal.append(note)
                    st["journal"] = journal[-10:]
                save_state(st)
            if say_text:
                if hud:
                    hud.show(speaker_name, say_text)
                    if is_chat:
                        hud.add_chat_message(
                            "status",
                            "",
                            "● Ready — Type your next message to Lucy and press ENTER (or ESC/F8 to return to Fallout 4).",
                        )
                if voice and not result.streamed_voice:
                    voice.speak(say_text, distance_m=dist)

        log_turn(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "model": result.model,
                "snapshot": snapshot,
                "decision": result.decision,
                "latency_s": round(result.latency_s, 3),
                "ttfa_s": result.ttfa_s,
                "tokens_per_s": result.tokens_per_s,
                "error": result.error,
                "problems": result.problems,
            }
        )
        return result


def handle_player_chat(
    player_text: str,
    hud: SubtitleHUD | None = None,
    voice: LocalVoice | None = None,
    stream_cb: Callable[[str], None] | None = None,
) -> Result:
    """Processes a free-form text message typed by the player in the F8 Live Chat overlay."""
    player_text = (player_text or "").strip()
    if not player_text:
        return Result(dict(FALLBACK_ACTION), personas.current()["ollama_model"], 0.0)
    chat_snap = {
        **last_live_snapshot,
        "event": "player_chat",
        "player_text": player_text,
        "recent_events": [f'The Sole Survivor says to you: "{player_text}"'],
    }
    res = process_snapshot(chat_snap, hud=hud, voice=voice, stream_cb=stream_cb)
    if res.decision.get("say"):
        print(
            f"\n[CHAT | TTFA {res.ttfa_s:.2f}s | Total {res.latency_s:.2f}s | {res.tokens_per_s} tok/s]\n"
            f"  You : \"{player_text}\"\n"
            f"  Lucy: \"{res.decision['say']}\"",
            flush=True,
        )
    return res


class BridgeHandler(BaseHTTPRequestHandler):
    hud: SubtitleHUD = None
    voice: LocalVoice = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

        if self.path == "/open_chat":
            if self.hud:
                self.hud.open_chat()
            payload = json.dumps({"ok": True, "hud_active": bool(self.hud)}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path == "/chat_stream":
            text = body.get("text", "")
            if self.hud:
                self.hud.add_chat_message("player", "You (Vault 111)", text)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.end_headers()

            def _send_partial(partial_say: str) -> None:
                try:
                    line = json.dumps({"type": "partial", "say": partial_say}, ensure_ascii=False) + "\n"
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass

            res = handle_player_chat(text, hud=self.hud, voice=self.voice, stream_cb=_send_partial)
            try:
                done_line = (
                    json.dumps(
                        {"type": "done", "decision": res.decision, "ttfa_s": res.ttfa_s, "latency_s": res.latency_s},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                self.wfile.write(done_line.encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass
            return

        if self.path == "/chat":
            text = body.get("text", "")
            if self.hud:
                self.hud.add_chat_message("player", "You (Vault 111)", text)
            res = handle_player_chat(text, hud=self.hud, voice=self.voice)
        elif self.path == "/decide":
            snapshot = body.get("snapshot", body)
            res = process_snapshot(snapshot, hud=self.hud, voice=self.voice)
        else:
            self.send_error(404)
            return
        payload = json.dumps(res.decision, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def _parse_snap_line(line: str, marker: str) -> dict | None:
    try:
        json_part = line.split(marker, 1)[1].strip()
        json_part = re.sub(r":\s*True\b", ":true", json_part)
        json_part = re.sub(r":\s*False\b", ":false", json_part)
        json_part = re.sub(r":\s*None\b", ":null", json_part)
        return json.loads(json_part)
    except Exception:
        return None


def _snap_priority(snap: dict) -> int:
    ev = snap.get("event", "heartbeat")
    if ev in ("hotkey", "open_chat"):
        return 3
    if ev != "heartbeat":
        return 2
    return 1


def watch_papyrus_log(hud: SubtitleHUD, voice: LocalVoice) -> None:
    marker = "[LUCY_SNAPSHOT]"
    last_sizes: dict[Path, int] = {
        log_path: (log_path.stat().st_size if log_path.exists() else 0)
        for log_path in FO4_USER_LOGS
    }
    print(
        "[Watcher] Watching Fallout 4 & Fallout 4 VR Papyrus logs:\n  - "
        + "\n  - ".join(str(p) for p in FO4_USER_LOGS[:2]),
        flush=True,
    )

    while True:
        time.sleep(0.05)
        for log_path in FO4_USER_LOGS:
            if not log_path.exists():
                continue
            size = log_path.stat().st_size
            last_size = last_sizes.get(log_path, 0)
            if size < last_size:
                last_size = 0
            if size == last_size:
                continue
            try:
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_size)
                    new_text = f.read()
                    last_sizes[log_path] = f.tell()
                snap_lines = [line for line in new_text.splitlines() if marker in line]
                if snap_lines:
                    parsed = [s for s in (_parse_snap_line(l, marker) for l in snap_lines) if s is not None]
                    if not parsed:
                        continue
                    best_snap = parsed[-1]
                    best_prio = _snap_priority(best_snap)
                    for s in reversed(parsed):
                        p = _snap_priority(s)
                        if p > best_prio:
                            best_snap = s
                            best_prio = p
                    res = process_snapshot(best_snap, hud=hud, voice=voice)
                    if res.decision.get("say"):
                        print(
                            f"\n[TTFA {res.ttfa_s:.2f}s | Total {res.latency_s:.2f}s | {res.tokens_per_s} tok/s | {res.decision['mood']}] "
                            f"Lucy: \"{res.decision['say']}\"",
                            flush=True,
                        )
            except Exception as e:
                print(f"[Watcher] Log parse error ({log_path.name}): {e}", flush=True)


def run_server() -> None:
    cfg = personas.current()
    print(
        f"=== Local AI Bridge: {cfg['full_name']} | Ollama Model: {cfg['ollama_model']} (CPU P-Core Streaming + Live Chat) ===",
        flush=True,
    )
    forms_db = build_or_load_forms_db()
    print(f"[Resolver] Loaded {len(forms_db)} Fallout 4 FormID names.", flush=True)
    rag_db = get_lore_rag()
    print(f"[LoreRAG] Persistent SQLite RAG ready ({len(rag_db._docs)} lore packs active).", flush=True)
    voice = LocalVoice()
    hud = SubtitleHUD(
        enabled=True,
        on_player_chat=lambda msg: handle_player_chat(msg, hud=hud, voice=voice),
    )
    BridgeHandler.hud = hud
    BridgeHandler.voice = voice

    # Warm up the active model on CPU P-cores (num_gpu=0) so the KV cache is pre-filled (<1.2s TTFA)
    try:
        w_res = decide(load_state(), {"event": "summoned", "recent_events": ["Warmup."]}, timeout_s=20.0)
        print(
            f"[Warmup] Model {cfg['ollama_model']} hot on CPU P-cores (num_gpu=0, 0% GPU contention): "
            f"{w_res.latency_s:.2f}s ({w_res.tokens_per_s} tok/s).",
            flush=True,
        )
    except Exception as e:
        print(f"[Warmup] Note: {e}", flush=True)

    threading.Thread(target=watch_papyrus_log, args=(hud, voice), daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), BridgeHandler)
    print(f"Server ready on http://{HOST}:{PORT}/decide & /chat_stream", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
