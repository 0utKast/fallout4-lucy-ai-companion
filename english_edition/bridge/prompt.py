"""Builds context-rich English system and user messages with Strict Topic Control, Pronoun Disambiguation & Multi-Turn RAG."""

import re
from pathlib import Path

import personas
from lore_rag import get_lore_rag

HERE = Path(__file__).parent
RULES = HERE / "prompts" / "rules.md"

_LOCATION_QUESTION_WORDS = ("where", "place", "location", "here", "town", "city", "sanctuary", "commonwealth")


def persona_text() -> str:
    text = (personas.current()["dir"] / "persona.md").read_text(encoding="utf-8")
    return re.sub(r"## Notes\b.*?(?=\n## |\Z)", "", text, flags=re.S).rstrip()


def system_prompt() -> str:
    return (
        "You are Lucy MacLean from Vault 33 (Santa Monica, California), now traveling as a companion to the Sole Survivor (Vault 111) across the Commonwealth (Fallout 4).\n"
        "Always speak in natural American English in first person ('I', 'me', 'my'), with polite Vault-girl optimism ('Okey-dokey!'), the Golden Rule, and hard-earned Wasteland maturity.\n"
        "Canonical facts: history teacher and council member in Vault 33; daughter of Hank MacLean and Rose (turned into a ghoul at Shady Sands), sister of Norm, cousin of Chet. "
        "Left Vault 33 in 2296 after Lee Moldaver kidnapped your dad Hank; your fake husband Monty tried to kill you; Cooper Howard (The Ghoul) captured you, cut off your index finger outside the Super Duper Mart in California, and sold you to the robot Snip-Snip; "
        "traveled with Maximus (Brotherhood of Steel) and the dog CX404 to Griffith Observatory and toward New Vegas in Season 2.\n"
        "Never confuse Cooper Howard or the player with yourself: when the player says 'you' or 'your', they mean you (Lucy)."
    )


def user_message(state: dict, snapshot: dict) -> str:
    event = snapshot.get("event", "heartbeat")
    latest_event = (snapshot.get("recent_events") or [""])[-1]
    loc = snapshot.get("world", {}).get("location") or snapshot.get("location_name") or "Commonwealth"
    weather = snapshot.get("world", {}).get("weather") or snapshot.get("weather") or "Clear"
    player = snapshot.get("player") or {}
    comp = snapshot.get("companion") or {}
    weapon = player.get("weapon") or "unarmed"
    in_combat = bool(player.get("in_combat") or comp.get("in_combat"))
    allow_okey = bool(snapshot.get("allow_okey_dokey", False))
    style_instr = snapshot.get("line_style") or "React naturally in character."
    style_key = snapshot.get("line_style_key") or ""
    player_text = (snapshot.get("player_text") or "").strip()
    chat_history = snapshot.get("chat_history") or []

    nearby_items = []
    nearby_names = []
    for key in ("nearby_humans", "nearby_animals"):
        for item in (snapshot.get(key) or [])[:3]:
            kind = item.get("kind") or item.get("role") or "creature"
            nearby_names.append(kind)
            status = "dead" if item.get("dead") else ("hostile" if item.get("hostile") or item.get("in_combat") else "nearby")
            nearby_items.append(f"{kind} ({status}, {item.get('distance_m', 5)}m)")

    rag = get_lore_rag()
    lines: list[str] = []

    if event == "player_chat" and player_text:
        p_low = player_text.lower()
        asks_about_location = any(w in p_low for w in _LOCATION_QUESTION_WORDS)
        if asks_about_location:
            lines.append(f"CURRENT IN-GAME LOCATION: {loc} ({weather})")

        prev_player_query = ""
        if chat_history:
            for turn in reversed(chat_history):
                if "Lucy" not in turn.get("speaker", ""):
                    prev_player_query = turn.get("text", "")
                    break
            lines.append("RECENT EXCHANGE (Follow-up context):")
            for turn in chat_history[-2:]:
                lines.append(f"  - {turn['speaker']}: {turn['text']}")

        rag_docs = rag.retrieve(
            query=player_text,
            prev_query=prev_player_query,
            location_name="",
            nearby_names=[],
            top_k=1,
            is_chat=True,
        )
        if rag_docs:
            lines.append("\n=== LUCY'S CANONICAL MEMORY ===")
            for doc in rag_docs:
                lines.append(f"* [{doc['title']}]: {doc['content'][:480]}")

        lines.append(f'\nPLAYER SAYS TO YOU (LUCY): "{player_text}"')
        lines.append(
            f'TASK: Answer "{player_text}" in first person ("I", "me", "my") as Lucy MacLean in 2 to 3 natural sentences in English (30-55 words).'
        )
        return "\n".join(lines)

    # Ambient game events (heartbeat, hotkey, campfire, combat)
    lines.append(f"EVENT: {event} | COMBAT: {in_combat} | ALLOW_OKEY_DOKEY: {allow_okey}")
    lines.append(f"LOCATION: {loc} ({weather}) | PLAYER_WEAPON: {weapon} (HP {player.get('hp', 100)}%)")
    if nearby_items:
        lines.append(f"NEARBY: {', '.join(nearby_items)}")

    if event == "campfire":
        rag_docs = rag.retrieve(query="who are you vault 33", location_name="", top_k=1, is_chat=False)
        if rag_docs:
            lines.append(f"CANONICAL MEMORY: {rag_docs[0]['content']}")
        lines.append(f"SITUATION: {latest_event}")
        lines.append(
            "STYLE: Tell a vivid 40-to-60-word story in English about your life in Vault 33 or your journey across California and New Vegas."
        )
    else:
        if style_key in ("tv_callback", "fallout_lore"):
            rag_docs = rag.retrieve(query="vault 33 cooper maximus", location_name="", nearby_names=[], top_k=1, is_chat=False)
            if rag_docs:
                lines.append(f"CANONICAL MEMORY: {rag_docs[0]['content']}")
        lines.append(f"SITUATION: {latest_event}")
        lines.append(f"STYLE: {style_instr} (1-2 short sentences in English, max 24 words, zero Fallout 4 spoilers).")

    recent = (snapshot.get("recent_lines") or [])[-2:]
    if recent:
        lines.append("DO NOT REPEAT: " + " | ".join(recent))

    return "\n".join(lines)
