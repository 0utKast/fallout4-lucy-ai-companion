"""Fallout 4 FormID Resolver for Vanilla (Non-F4SE) Papyrus Snapshots.

Extracts and caches English display names and EditorIDs for LCTN, CELL, WRLD,
WTHR, WEAP, NPC_, and RACE records from Fallout4.esm + Fallout4_en.STRINGS,
and enriches raw Papyrus FormID snapshots into rich human-readable snapshots.
"""

import json
import os
import re
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).parent
CACHE_FILE = HERE / "fo4_forms.json"

FO4_DATA_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout 4\Data")
FO4_ESM = FO4_DATA_DIR / "Fallout4.esm"
FO4_INTERFACE_BA2 = FO4_DATA_DIR / "Fallout4 - Interface.ba2"

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


def _camel_to_words(edid: str) -> str:
    s = re.sub(r"^(LCTN|WTHR|WEAP|NPC|RACE|enc|lvl| DLC\d+)[_]*", "", edid, flags=re.IGNORECASE)
    s = re.sub(r"Location$", "", s)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = s.replace("_", " ").strip()
    return s or edid


def _load_en_strings() -> dict[int, str]:
    if not FO4_INTERFACE_BA2.exists():
        return {}
    sraw = b""
    with FO4_INTERFACE_BA2.open("rb") as f:
        _m, _v, _t, nf, ntbl = struct.unpack("<4sI4sIQ", f.read(24))
        f.seek(ntbl)
        names = [
            f.read(struct.unpack("<H", f.read(2))[0]).decode("utf-8", "replace")
            for _ in range(nf)
        ]
        f.seek(24)
        for nm in names:
            _nh, _ext, _dh, _unk, ofs, pk, unpk, _al = struct.unpack("<I4sIIQIII", f.read(36))
            if nm.lower() == "strings\\fallout4_en.strings":
                f.seek(ofs)
                sraw = zlib.decompress(f.read(pk)) if pk > 0 else f.read(unpk)
                break
    if not sraw:
        return {}
    cnt, _dsz = struct.unpack_from("<II", sraw, 0)
    strings: dict[int, str] = {}
    base_data = 8 + cnt * 8
    for i in range(cnt):
        sid, off = struct.unpack_from("<II", sraw, 8 + i * 8)
        start = base_data + off
        end = sraw.find(b"\x00", start)
        if end != -1:
            strings[sid] = sraw[start:end].decode("utf-8", "replace")
    return strings


def build_or_load_forms_db() -> dict:
    global _FORMS_DB
    if _FORMS_DB is not None:
        return _FORMS_DB
    if CACHE_FILE.exists():
        _FORMS_DB = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return _FORMS_DB

    db: dict[str, str] = {
        "0": "Unarmed",
        "20": "Sole Survivor",
        str(0x01000813): "Vault 33 Jumpsuit",
        str(0x01000820): "Lucy MacLean",
        str(0x01001102): "Colt 6520 10mm Pistol",
        str(0x01001105): ".223 Pistol",
        str(0x01001108): "Wattz 2000 Laser Rifle",
        str(0x0100110B): "Winchester P94 Turbo Plasma Rifle",
        str(0x0100110E): "Vindicator Minigun",
        str(0x01002000): "Vault-Tec Mnemosyne Quantum Archive",
        str(0x01002100): "Vault 13 — Operations Sector & Overseer Jacoren's Office (2161)",
        str(0x01002200): "Vault 13 Entrance Cavern (Mount Whitney, 2161)",
        str(0x01002500): "Vault 15 Buried Ruins & Khans Stronghold (2161)",
        str(0x01002900): "Necropolis — Vault 12 Water Purification Station (2161)",
        str(0x01002A00): "Necropolis Underground & Vault 12 Watershed (2161)",
        str(0x01002B00): "Lost Hills — Brotherhood of Steel Bunker (2161)",
        str(0x01002C00): "Mariposa Military Base — FEV Vats (2161)",
        str(0x01002D00): "The Cathedral — Lair of The Master (2161)",
        str(0x01002E00): "Necropolis — Hall of the Dead (Set's Domain, 2161)",
        str(0x01002F00): "Necropolis Central Sewers (2161)",
    }

    if FO4_ESM.exists():
        strings = _load_en_strings()
        target_rts = {b"LCTN", b"CELL", b"WRLD", b"WTHR", b"WEAP", b"NPC_", b"RACE"}
        with FO4_ESM.open("rb") as f:
            data = f.read()
        p = 0
        n = len(data)
        while p < n:
            rt = data[p : p + 4]
            if rt == b"GRUP":
                p += 24
                continue
            sz, fl, fid, _rev, _fver, _v2 = struct.unpack("<IIIIHH", data[p + 4 : p + 24])
            if rt in target_rts:
                body = data[p + 24 : p + 24 + sz]
                if fl & 0x00040000:
                    try:
                        body = zlib.decompress(body[4:])
                    except Exception:
                        body = b""
                sp = 0
                edid = ""
                full_name = ""
                next_sz32 = None
                while sp + 6 <= len(body):
                    st = body[sp : sp + 4]
                    ss = struct.unpack_from("<H", body, sp + 4)[0]
                    if next_sz32 is not None:
                        ss = next_sz32
                        next_sz32 = None
                    if st == b"XXXX" and ss == 4:
                        next_sz32 = struct.unpack_from("<I", body, sp + 6)[0]
                        sp += 10
                        continue
                    if st == b"OBTE":
                        break
                    if st == b"EDID" and not edid:
                        edid = body[sp + 6 : sp + 6 + ss].rstrip(b"\x00").decode("utf-8", "replace")
                    elif st == b"FULL" and not full_name:
                        if ss == 4:
                            sid = struct.unpack_from("<I", body, sp + 6)[0]
                            full_name = strings.get(sid, "")
                        elif ss > 1:
                            full_name = (
                                body[sp + 6 : sp + 6 + ss].rstrip(b"\x00").decode("utf-8", "replace")
                            )
                    if edid and full_name:
                        break
                    sp += 6 + ss
                label = full_name.strip() or _camel_to_words(edid)
                if rt == b"WTHR" and edid:
                    low_e = edid.lower()
                    if "radstorm" in low_e or "gsweather" in low_e or "glowingsea" in low_e:
                        label = "Radiation Storm"
                    elif "rain" in low_e:
                        label = "Commonwealth Rain"
                    elif "mist" in low_e or "fog" in low_e:
                        label = "Radioactive Fog"
                    elif "overcast" in low_e or "cloudy" in low_e:
                        label = "Overcast Sky"
                    elif "clear" in low_e or "pleasant" in low_e:
                        label = "Clear Sky"
                if label:
                    db[str(fid)] = label
            p += 24 + sz

    CACHE_FILE.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    _FORMS_DB = db
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
