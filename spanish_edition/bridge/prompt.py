"""Construye los mensajes de sistema y usuario 100% en español con Control Estricto de Tema, Desambiguación de Pronombres y RAG Multi-Turno."""

import re
from pathlib import Path

import personas
from lore_rag import get_lore_rag

HERE = Path(__file__).parent
RULES = HERE / "prompts" / "rules.md"

_LOCATION_QUESTION_WORDS = ("donde", "dónde", "lugar", "sitio", "estamos", "aqui", "aquí", "ciudad", "sanctuary", "commonwealth")


def persona_text() -> str:
    text = (personas.current()["dir"] / "persona.md").read_text(encoding="utf-8")
    return re.sub(r"## Notas\b.*?(?=\n## |\Z)", "", text, flags=re.S).rstrip()


def system_prompt() -> str:
    return RULES.read_text(encoding="utf-8").rstrip() + "\n" + persona_text()


def user_message(state: dict, snapshot: dict) -> str:
    event = snapshot.get("event", "heartbeat")
    latest_event = (snapshot.get("recent_events") or [""])[-1]
    loc = snapshot.get("world", {}).get("location") or snapshot.get("location_name") or "Commonwealth"
    weather = snapshot.get("world", {}).get("weather") or snapshot.get("weather") or "Cielo despejado"
    player = snapshot.get("player") or {}
    comp = snapshot.get("companion") or {}
    weapon = player.get("weapon") or "desarmado"
    in_combat = bool(player.get("in_combat") or comp.get("in_combat"))
    allow_okey = bool(snapshot.get("allow_okey_dokey", False))
    style_instr = snapshot.get("line_style") or "Reacciona con naturalidad en tu papel."
    style_key = snapshot.get("line_style_key") or ""
    player_text = (snapshot.get("player_text") or "").strip()
    chat_history = snapshot.get("chat_history") or []

    nearby_items = []
    nearby_names = []
    for key in ("nearby_humans", "nearby_animals"):
        for item in (snapshot.get(key) or [])[:3]:
            kind = item.get("kind") or item.get("role") or "criatura"
            nearby_names.append(kind)
            status = "muerto" if item.get("dead") else ("hostil" if item.get("hostile") or item.get("in_combat") else "cerca")
            nearby_items.append(f"{kind} ({status}, {item.get('distance_m', 5)}m)")

    rag = get_lore_rag()
    lines: list[str] = []

    if event == "player_chat" and player_text:
        p_low = player_text.lower()
        asks_about_location = any(w in p_low for w in _LOCATION_QUESTION_WORDS)
        if asks_about_location:
            lines.append(f"UBICACIÓN ACTUAL EN EL JUEGO: {loc} ({weather})")

        prev_player_query = ""
        if chat_history:
            for turn in reversed(chat_history):
                if "Lucy" not in turn.get("speaker", ""):
                    prev_player_query = turn.get("text", "")
                    break
            lines.append("ÚLTIMO INTERCAMBIO DE LA CHARLA (Contexto de seguimiento):")
            for turn in chat_history[-2:]:
                lines.append(f"  - {turn['speaker']}: {turn['text']}")

        rag_docs = rag.retrieve(
            query=player_text,
            prev_query=prev_player_query,
            location_name="",
            nearby_names=[],
            top_k=2,
            is_chat=True,
        )
        if rag_docs:
            lines.append("\n=== MEMORIA CANÓNICA DE LUCY PARA ESTA PREGUNTA (¡USA ESTOS HECHOS EXACTOS!) ===")
            for doc in rag_docs:
                lines.append(f"* [{doc['title']}]: {doc['content']}")

        lines.append(f'\nEL JUGADOR TE DICE A TI (LUCY): "{player_text}"')
        lines.append(
            "REGLA CRÍTICA DE PRONOMBRES Y SUJETOS: Cuando el jugador dice 'te', 'tu', 'tus' o 'vuestra' (por ejemplo, 'te cortó un dedo' o 'vuestra relación'), se refiere A TI (Lucy MacLean). "
            "Fue Cooper Howard (El Necrófago) quien ME CORTÓ EL DEDO A MÍ (a Lucy) frente al Super Duper Mart en California y me vendió a Snip-Snip; ¡JAMÁS digas que tú le cortaste un dedo al jugador ni que ocurrió en el Refugio 111! "
            f'TAREA: Responde a "{player_text}" en primera persona ("yo", "a mí", "mi") como la verdadera Lucy MacLean usando los hechos y emociones exactas de MEMORIA CANÓNICA DE LUCY (2 a 4 frases en español, 40-70 palabras).'
        )
        return "\n".join(lines)

    # Eventos ambientales del juego (heartbeat, hotkey, campfire, combate)
    lines.append(f"EVENTO: {event} | COMBATE: {in_combat} | PERMITIR_OKEY_DOKEY: {allow_okey}")
    lines.append(f"LUGAR: {loc} ({weather}) | ARMA_JUGADOR: {weapon} (Salud {player.get('hp', 100)}%)")
    if nearby_items:
        lines.append(f"ENTORNO CERCANO: {', '.join(nearby_items)}")

    if event == "campfire":
        rag_docs = rag.retrieve(query="quien eres refugio 33", location_name="", top_k=1, is_chat=False)
        if rag_docs:
            lines.append(f"MEMORIA CANÓNICA: {rag_docs[0]['content']}")
        lines.append(f"SITUACIÓN: {latest_event}")
        lines.append(
            "ESTILO: Cuenta una anécdota de 40 a 60 palabras en español sobre tu vida en el Refugio 33 o tu viaje por California y New Vegas."
        )
    else:
        if style_key in ("tv_callback", "fallout_lore"):
            rag_docs = rag.retrieve(query="refugio 33 cooper maximus", location_name="", nearby_names=[], top_k=1, is_chat=False)
            if rag_docs:
                lines.append(f"MEMORIA CANÓNICA: {rag_docs[0]['content']}")
        lines.append(f"SITUACIÓN: {latest_event}")
        lines.append(f"ESTILO: {style_instr} (1-2 frases cortas en español, máximo 24 palabras, sin spoilers de Fallout 4).")

    recent = (snapshot.get("recent_lines") or [])[-2:]
    if recent:
        lines.append("NO REPITAS: " + " | ".join(recent))

    return "\n".join(lines)
