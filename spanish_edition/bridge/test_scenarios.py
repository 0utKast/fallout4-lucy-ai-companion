"""Live English Scenario Suite for Lucy MacLean (Vault 33) — Local Ollama + Synchronous Kokoro Voice."""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

import memory
import server
from voice_local import LocalVoice, split_into_clauses

SCENARIOS = [
    {
        "title": "1. First Meeting at Vault 111 Elevator (Sanctuary Hills)",
        "snapshot": {
            "event": "summoned",
            "world": {
                "location": "Vault 111 Exterior (Sanctuary Hills)",
                "region": "Commonwealth",
                "time": "09:15",
                "weather": "Clear",
            },
            "player": {
                "health_pct": 100,
                "rads": 0,
                "in_power_armor": False,
                "weapon_drawn": False,
                "activity": "exploring",
            },
            "companion": {"health_pct": 100, "distance_m": 2.5, "current_action": "follow"},
            "nearby": [],
            "recent_events": [
                "The Sole Survivor just stepped off the Vault 111 elevator platform and Lucy MacLean joins them."
            ],
        },
    },
    {
        "title": "2. Ambush Inside Lexington Super Duper Mart (Feral Ghouls & Mister Handy)",
        "snapshot": {
            "event": "combat_start",
            "world": {
                "location": "Super Duper Mart (Lexington)",
                "region": "Commonwealth",
                "time": "14:30",
                "weather": "Overcast",
            },
            "player": {
                "health_pct": 88,
                "rads": 45,
                "in_power_armor": False,
                "weapon_drawn": True,
                "activity": "fighting",
            },
            "companion": {"health_pct": 95, "distance_m": 4.0, "current_action": "guard"},
            "nearby": [
                {"id": "ghoul_1", "kind": "Starving Feral Ghoul", "doing": "charging", "hostile": True, "distance_m": 8.0},
                {"id": "handy_1", "kind": "Damaged Mister Handy robot", "doing": "patrolling", "hostile": False, "distance_m": 12.0},
            ],
            "recent_events": [
                "You entered an abandoned Super Duper Mart and feral ghouls crawled out of the aisles while a Mister Handy buzzes nearby."
            ],
        },
    },
    {
        "title": "3. Player Steps Into T-60 Power Armor & Asks 'What do you think?'",
        "snapshot": {
            "event": "hotkey",
            "hotkey": "what_do_you_think",
            "world": {
                "location": "Museum of Freedom (Concord)",
                "region": "Commonwealth",
                "time": "16:10",
                "weather": "Clear",
            },
            "player": {
                "health_pct": 100,
                "rads": 15,
                "in_power_armor": True,
                "weapon_drawn": True,
                "activity": "idle",
            },
            "companion": {"health_pct": 100, "distance_m": 3.0, "current_action": "follow"},
            "nearby": [],
            "recent_events": [
                "Your Vault 111 companion just slammed a Fusion Core into a suit of T-60 Power Armor and asked Lucy what she thinks."
            ],
        },
    },
    {
        "title": "4. Asking Lucy About Vault 13, Shady Sands, and Vault-Tec Secrets",
        "snapshot": {
            "event": "hotkey",
            "hotkey": "tell_lore",
            "world": {
                "location": "Vault-Tec Regional HQ (Boston)",
                "region": "Commonwealth",
                "time": "18:45",
                "weather": "Radiation Storm",
            },
            "player": {
                "health_pct": 75,
                "rads": 120,
                "in_power_armor": True,
                "weapon_drawn": False,
                "activity": "exploring",
            },
            "companion": {"health_pct": 82, "distance_m": 2.0, "current_action": "follow"},
            "nearby": [],
            "recent_events": [
                "Inside Vault-Tec Regional HQ during a radstorm, the player asks Lucy what she knows about Vault 13, Shady Sands, or Vault 31."
            ],
        },
    },
    {
        "title": "5. Campfire Story in Sanctuary Hills with Dogmeat (CX404 callback)",
        "snapshot": {
            "event": "campfire",
            "world": {
                "location": "Sanctuary Hills Campfire",
                "region": "Commonwealth",
                "time": "22:30",
                "weather": "Starry Night",
            },
            "player": {
                "health_pct": 100,
                "rads": 0,
                "in_power_armor": False,
                "weapon_drawn": False,
                "activity": "at_campfire",
            },
            "companion": {"health_pct": 100, "distance_m": 1.8, "current_action": "idle"},
            "nearby": [
                {"id": "dogmeat", "kind": "Dogmeat (German Shepherd)", "doing": "resting by the fire", "hostile": False, "distance_m": 2.0}
            ],
            "recent_events": [
                "You sat down by the campfire with Dogmeat (who looks just like CX404) after a long day in the Wasteland."
            ],
        },
    },
]


def main():
    print("==========================================================================")
    print(" LIVE TEST: LUCY MACLEAN (VAULT 33) - ENGLISH + KOKORO SYNC STREAMING")
    print("==========================================================================\n")

    voice = LocalVoice(enabled=True, voice_name="lucy_blend")

    for sc in SCENARIOS:
        print(f"--- {sc['title']} ---")
        res = server.process_snapshot(sc["snapshot"], hud=None, voice=None)
        if res.error or res.problems:
            print(f"  [ERROR] {res.error} | Problems: {res.problems}")
            continue
        d = res.decision
        clauses = split_into_clauses(d["say"])
        ttfa_ms = 0.0
        if clauses and voice.kokoro:
            import time
            t0 = time.perf_counter()
            voice.kokoro.create(clauses[0], voice=voice.voice_style, speed=1.04, lang="en-us")
            ttfa_ms = (time.perf_counter() - t0) * 1000.0
        print(
            f"  LLM Latency : {res.latency_s:.2f} s ({res.tokens_per_s} tok/s) | "
            f"Kokoro 1st-Clause TTFA: {ttfa_ms:.0f} ms ({len(clauses)} clause(s))"
        )
        print(f"  Action/Mood : {d['action']} / {d['mood']} | Trust Δ: {d['trust_delta']} | Respect Δ: {d['respect_delta']}")
        print(f"  LUCY SAYS   : \"{d['say']}\"\n")

    print("--- Testing Session Memory Recap (memory.recap) ---")
    turns = memory.turns_after("")
    if turns:
        state = server.load_state()
        updated = memory.recap(state, turns)
        server.save_state(updated)
        print(f"  Lucy's Session Summary: \"{updated['last_session']['summary']}\"")
        print("  Updated Journal:")
        for idx, entry in enumerate(updated["journal"], 1):
            print(f"    {idx}. {entry}")


if __name__ == "__main__":
    main()
