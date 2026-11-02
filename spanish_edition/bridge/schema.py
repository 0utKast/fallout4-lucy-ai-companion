"""Structured decision contract between local Ollama LLM and Fallout 4."""

ACTIONS = [
    "follow",
    "wait_here",
    "scout_ahead",
    "guard",
    "attack",
    "stay_out",
    "flee",
    "idle",
]

MOODS = [
    "cheerful",
    "optimistic",
    "polite_shock",
    "nervous",
    "horrified",
    "curious",
    "determined",
    "compassionate",
    "disappointed",
    "sarcastic",
]

DELTAS = [-2, -1, 0, 1, 2]

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ACTIONS,
        },
        "target": {
            "type": "string",
        },
        "mood": {
            "type": "string",
            "enum": MOODS,
        },
        "say": {
            "type": "string",
            "description": "What Lucy MacLean says out loud in English about what is happening right now in the SNAPSHOT.",
        },
        "trust_delta": {
            "type": "integer",
            "enum": DELTAS,
        },
        "respect_delta": {
            "type": "integer",
            "enum": DELTAS,
        },
    },
    "required": [
        "action",
        "target",
        "mood",
        "say",
        "trust_delta",
        "respect_delta",
    ],
    "additionalProperties": False,
}


def validate(decision: dict, max_say: int = 440) -> list[str]:
    problems = []
    if not isinstance(decision, dict):
        return ["decision is not a dict"]
    if decision.get("action") not in ACTIONS:
        decision["action"] = "follow"
    if not isinstance(decision.get("target"), str):
        decision["target"] = ""
    if decision.get("mood") not in MOODS:
        decision["mood"] = "optimistic"
    for key in ("trust_delta", "respect_delta"):
        val = decision.get(key, 0)
        if not isinstance(val, int) or val not in DELTAS:
            decision[key] = max(-2, min(2, int(val) if isinstance(val, (int, float)) else 0))
    say = decision.get("say", "")
    if not isinstance(say, str):
        problems.append("say is not a string")
    elif len(say) > max_say:
        problems.append(f"say line too long ({len(say)} > {max_say})")
    return problems
