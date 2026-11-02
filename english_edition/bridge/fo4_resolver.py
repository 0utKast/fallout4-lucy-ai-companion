"""Fallout 4 FormID Resolver for Vanilla (Non-F4SE) Papyrus Snapshots.

Extracts and caches English display names and EditorIDs for LCTN, CELL, WRLD,
WTHR, WEAP, NPC_, and RACE records from Fallout4.esm + Fallout4_en.STRINGS,
and enriches raw Papyrus FormID snapshots into rich human-readable snapshots.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
CACHE_FILE = HERE / "fo4_forms.json"

ANIMAL_KEYWORDS = (
    "dog",
    "brahmin",
    "radroach",
    "mole rat",
    "molerat",
    "radscorpion",
    "deathclaw",
    "mirelurk",
    "yao guai",
    "bloatfly",
    "bloodbug",
    "stingwing",
    "radstag",
    "cat",
    "mutant hound",
    "fev hound",
    "gorilla",
)

WEATHER_CLASS_NAMES = {
    -1: "Clear Commonwealth Sky",
    0: "Clear & Sunny Sky",
    1: "Overcast Wasteland Sky",
    2: "Radioactive Rain",
    3: "Dusty Overcast Sky",
}

_FORMS_DB: dict | None = None
_LAST_LOCATION: str = ""
_LAST_RAD_STORM: bool = False


def build_or_load_forms_db() -> dict:
    global _FORMS_DB
    if _FORMS_DB is not None:
        return _FORMS_DB
    if CACHE_FILE.exists():
        _FORMS_DB = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return _FORMS_DB
    _FORMS_DB = {
        "0": "Unarmed",
        "20": "Sole Survivor",
        str(0x01000813): "Vault 33 Jumpsuit",
        str(0x01000820): "Lucy MacLean",
    }
    return _FORMS_DB


def resolve_fid(fid: int | None, default: str = "") -> str:
    if not fid:
        return default
    db = build_or_load_forms_db()
    # Mask plugin load-order byte if from Fallout4.esm (0x00xxxxxx)
    if (fid >> 24) == 0:
        return db.get(str(fid), default)
    # Check custom plugin ID normalized to 0x01xxxxxx
    norm_custom = 0x01000000 | (fid & 0x00FFFFFF)
    return db.get(str(norm_custom), db.get(str(fid & 0x00FFFFFF), default))


def enrich_papyrus_snapshot(snapshot: dict) -> dict:
    """Enriches a raw Papyrus FormID snapshot into a full human-readable snapshot."""
    global _LAST_LOCATION, _LAST_RAD_STORM
    if "loc_fid" not in snapshot and "weather_fid" not in snapshot:
        return snapshot

    snap = dict(snapshot)
    recent_events = list(snap.get("recent_events") or [])

    # 1. Location & Worldspace
    loc_name = (
        resolve_fid(snap.get("loc_fid"))
        or resolve_fid(snap.get("cell_fid"))
        or resolve_fid(snap.get("ws_fid"))
        or "Commonwealth Wasteland"
    )
    if snap.get("interior") and "Interior" not in loc_name and "Vault" not in loc_name:
        loc_name = f"{loc_name} (Interior)"
    snap["location_name"] = loc_name
    if loc_name and loc_name != _LAST_LOCATION:
        if _LAST_LOCATION:
            recent_events.append(f"Entered {loc_name} (from {_LAST_LOCATION})")
        _LAST_LOCATION = loc_name

    # 2. Weather & Radiation Storm detection
    if snap.get("interior"):
        weather_str = "Indoor Facility"
        is_rad_storm = False
    else:
        w_fid = snap.get("weather_fid", 0)
        w_cls = snap.get("weather_class", 0)
        weather_str = resolve_fid(w_fid) or WEATHER_CLASS_NAMES.get(w_cls, "Clear Sky")
        is_rad_storm = "Radiation Storm" in weather_str or "Glowing Sea" in loc_name
    snap["weather"] = weather_str

    if is_rad_storm and not _LAST_RAD_STORM:
        recent_events.append("A green Commonwealth Radiation Storm just rolled in!")
        if snap.get("event") == "heartbeat":
            snap["event"] = "radiation_storm"
    _LAST_RAD_STORM = is_rad_storm

    # 3. Player weapon & stats
    player = dict(snap.get("player") or {})
    if "weapon_fid" in player:
        w_fid = player.get("weapon_fid", 0)
        player["weapon"] = resolve_fid(w_fid, "Unarmed" if w_fid == 0 else "Firearm")
    snap["player"] = player

    # 4. Nearby actors, humans, animals & combat enemies
    nearby_raw = snap.get("nearby_raw") or []
    nearby_humans = []
    nearby_animals = []
    combat_enemies = []

    for item in nearby_raw:
        base_name = resolve_fid(item.get("base_fid"))
        race_name = resolve_fid(item.get("race_fid"))
        name = base_name or race_name or "Wastelander"
        if name in ("Lucy MacLean", "Player", "Sole Survivor"):
            continue
        dist_m = round(float(item.get("dist_m", 5.0)), 1)
        dead = bool(item.get("dead", False))
        hostile = bool(item.get("hostile", False))
        in_combat = bool(item.get("in_combat", False))

        low_check = f"{name} {race_name}".lower()
        is_animal = any(k in low_check for k in ANIMAL_KEYWORDS)

        if (hostile or in_combat) and not dead:
            combat_enemies.append(f"{name} ({dist_m}m)")

        if is_animal:
            nearby_animals.append(
                {
                    "kind": name,
                    "distance_m": dist_m,
                    "dead": dead,
                }
            )
        else:
            disp = "dead" if dead else ("hostile" if hostile else "friendly/neutral")
            nearby_humans.append(
                {
                    "kind": name,
                    "distance_m": dist_m,
                    "dead": dead,
                    "disposition": disp,
                }
            )

    if nearby_humans and not snap.get("nearby_humans"):
        snap["nearby_humans"] = nearby_humans
    if nearby_animals and not snap.get("nearby_animals"):
        snap["nearby_animals"] = nearby_animals
    if combat_enemies and not snap.get("combat_enemies"):
        snap["combat_enemies"] = combat_enemies

    snap["world"] = {
        "location": loc_name,
        "weather": weather_str,
        "time": snap.get("game_hour", "12:00"),
        "interior": bool(snap.get("interior", False)),
    }

    ev = snap.get("event", "heartbeat")
    weap_name = player.get("weapon", "weapon")
    if ev == "what_do_you_think":
        snap["event"] = "hotkey"
        snap["hotkey"] = "what_do_you_think"
        recent_events.append(
            f"The Sole Survivor turns to you at {loc_name} ({weather_str}, armed with {weap_name}) and asks what you think right now."
        )
    elif ev == "wait_here":
        snap["event"] = "hotkey"
        snap["hotkey"] = "wait_here"
        recent_events.append(
            f"The Sole Survivor asks you to wait here at {loc_name} and keep watch."
        )
    elif ev == "follow_me":
        snap["event"] = "hotkey"
        snap["hotkey"] = "follow_me"
        recent_events.append(
            f"The Sole Survivor signals for you to follow them again through {loc_name}."
        )
    elif ev == "campfire":
        recent_events.append(
            f"Taking a breather at {loc_name}. The Sole Survivor asks you to tell a story about Vault 33, your dad Hank, The Ghoul, Maximus, or Vault-Tec lore."
        )
    elif ev == "summoned":
        recent_events.append(
            f"You just joined the Sole Survivor of Vault 111 at {loc_name} ({weather_str}). Greet them warmly!"
        )
    elif ev == "combat_start":
        enemies_str = ", ".join(combat_enemies) if combat_enemies else "hostile Wasteland creatures"
        recent_events.append(
            f"Combat just started at {loc_name} against {enemies_str}!"
        )
    elif ev == "combat_end":
        recent_events.append(
            f"The fight at {loc_name} just ended and the threat is neutralized."
        )
    elif ev == "companion_hurt":
        recent_events.append(
            f"You are badly hurt and bleeding out during the fight at {loc_name}!"
        )
    elif ev == "companion_recovered":
        recent_events.append(
            f"You just recovered and got back on your feet at {loc_name}."
        )
    elif not recent_events:
        recent_events.append(
            f"Walking through {loc_name} ({weather_str}) with the Sole Survivor (carrying {weap_name})."
        )

    snap["recent_events"] = recent_events[-5:]
    return snap
