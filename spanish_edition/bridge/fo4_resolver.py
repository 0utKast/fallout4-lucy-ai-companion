"""Resolución de FormIDs de Fallout 4 para Snapshots Papyrus (Edición 100% Español)."""

import json
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
    "perro",
    "albóndiga",
    "brahmin",
    "brahmán",
    "radroach",
    "mutaracha",
    "mole rat",
    "molerat",
    "rata topo",
    "radscorpion",
    "radescorpión",
    "deathclaw",
    "sanguinario",
    "mirelurk",
    "yao guai",
    "bloatfly",
    "moscas",
    "bloodbug",
    "chupasangre",
    "stingwing",
    "aguijoneador",
    "radstag",
    "ciervo",
    "cat",
    "gato",
    "mutant hound",
    "sabueso",
    "fev hound",
    "gorilla",
)

WEATHER_CLASS_NAMES = {
    -1: "Cielo despejado en la Commonwealth",
    0: "Cielo soleado y despejado",
    1: "Cielo encapotado del Yermo",
    2: "Lluvia radiactiva",
    3: "Cielo polvoriento",
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
            if nm.lower() in ("strings\\fallout4_es.strings", "strings\\fallout4_en.strings"):
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
        "0": "Desarmado",
        "20": "Único Superviviente",
        str(0x01000813): "Mono del Refugio 33",
        str(0x01000820): "Lucy MacLean",
    }
    CACHE_FILE.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
    _FORMS_DB = db
    return _FORMS_DB


def resolve_fid(fid: int | None, default: str = "") -> str:
    if not fid:
        return default
    db = build_or_load_forms_db()
    if (fid >> 24) == 0:
        return db.get(str(fid), default)
    norm_custom = 0x01000000 | (fid & 0x00FFFFFF)
    return db.get(str(norm_custom), db.get(str(fid & 0x00FFFFFF), default))


def enrich_papyrus_snapshot(snapshot: dict) -> dict:
    """Enriquece el snapshot de Papyrus con descripciones de eventos en español."""
    global _LAST_LOCATION, _LAST_RAD_STORM
    if "loc_fid" not in snapshot and "weather_fid" not in snapshot:
        return snapshot

    snap = dict(snapshot)
    recent_events = list(snap.get("recent_events") or [])

    loc_name = (
        resolve_fid(snap.get("loc_fid"))
        or resolve_fid(snap.get("cell_fid"))
        or resolve_fid(snap.get("ws_fid"))
        or "Yermo de la Commonwealth"
    )
    if snap.get("interior") and "Interior" not in loc_name and "Vault" not in loc_name and "Refugio" not in loc_name:
        loc_name = f"{loc_name} (Interior)"
    snap["location_name"] = loc_name
    if loc_name and loc_name != _LAST_LOCATION:
        if _LAST_LOCATION:
            recent_events.append(f"Habéis entrado en {loc_name} (viniendo de {_LAST_LOCATION})")
        _LAST_LOCATION = loc_name

    if snap.get("interior"):
        weather_str = "Instalación interior"
        is_rad_storm = False
    else:
        w_fid = snap.get("weather_fid", 0)
        w_cls = snap.get("weather_class", 0)
        raw_w = resolve_fid(w_fid) or WEATHER_CLASS_NAMES.get(w_cls, "Cielo despejado")
        w_map = {
            "Clear Sky": "Cielo despejado",
            "Overcast Sky": "Cielo nublado",
            "Commonwealth Rain": "Lluvia en la Commonwealth",
            "Radioactive Fog": "Niebla radiactiva",
            "Radiation Storm": "Tormenta radiactiva",
        }
        weather_str = w_map.get(raw_w, raw_w)
        is_rad_storm = "Tormenta radiactiva" in weather_str or "Radiation Storm" in raw_w or "Glowing Sea" in loc_name
    snap["weather"] = weather_str

    if is_rad_storm and not _LAST_RAD_STORM:
        recent_events.append("¡Acaba de desatarse una tormenta radiactiva verde en la Commonwealth!")
        if snap.get("event") == "heartbeat":
            snap["event"] = "radiation_storm"
    _LAST_RAD_STORM = is_rad_storm

    player = dict(snap.get("player") or {})
    if "weapon_fid" in player:
        w_fid = player.get("weapon_fid", 0)
        player["weapon"] = resolve_fid(w_fid, "Desarmado" if w_fid == 0 else "Arma de fuego")
    snap["player"] = player

    nearby_raw = snap.get("nearby_raw") or []
    nearby_humans = []
    nearby_animals = []
    combat_enemies = []

    for item in nearby_raw:
        base_name = resolve_fid(item.get("base_fid"))
        race_name = resolve_fid(item.get("race_fid"))
        name = base_name or race_name or "Habitante del Yermo"
        if name in ("Lucy MacLean", "Player", "Sole Survivor", "Único Superviviente"):
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
            nearby_animals.append({"kind": name, "distance_m": dist_m, "dead": dead})
        else:
            disp = "muerto" if dead else ("hostil" if hostile else "neutral")
            nearby_humans.append({"kind": name, "distance_m": dist_m, "dead": dead, "disposition": disp})

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
    weap_name = player.get("weapon", "arma")
    if ev == "what_do_you_think":
        snap["event"] = "hotkey"
        snap["hotkey"] = "what_do_you_think"
        recent_events.append(
            f"El Único Superviviente se gira hacia ti en {loc_name} ({weather_str}, armado con {weap_name}) y te pregunta qué opinas ahora mismo."
        )
    elif ev == "wait_here":
        snap["event"] = "hotkey"
        snap["hotkey"] = "wait_here"
        recent_events.append(f"El Único Superviviente te pide que esperes aquí en {loc_name} y vigiles.")
    elif ev == "follow_me":
        snap["event"] = "hotkey"
        snap["hotkey"] = "follow_me"
        recent_events.append(f"El Único Superviviente te hace una señal para que vuelvas a seguirle por {loc_name}.")
    elif ev == "campfire":
        recent_events.append(
            f"Descansando un momento en {loc_name}. El Único Superviviente te pide que cuentes una historia sobre el Refugio 33, tu padre Hank, El Necrófago, Maximus o los secretos de Vault-Tec."
        )
    elif ev == "summoned":
        recent_events.append(
            f"Acabas de unirte al Único Superviviente del Refugio 111 en {loc_name} ({weather_str}). ¡Salúdale con alegría!"
        )
    elif ev == "combat_start":
        enemies_str = ", ".join(combat_enemies) if combat_enemies else "criaturas hostiles del Yermo"
        recent_events.append(f"¡Acaba de empezar un combate en {loc_name} contra {enemies_str}!")
    elif ev == "combat_end":
        recent_events.append(f"El combate en {loc_name} acaba de terminar y la amenaza ha sido neutralizada.")
    elif ev == "companion_hurt":
        recent_events.append(f"¡Estás gravemente herida durante el combate en {loc_name}!")
    elif ev == "companion_recovered":
        recent_events.append(f"Te acabas de recuperar y volver a poner en pie en {loc_name}.")
    elif not recent_events:
        recent_events.append(
            f"Caminando por {loc_name} ({weather_str}) junto al Único Superviviente (que lleva {weap_name})."
        )

    snap["recent_events"] = recent_events[-5:]
    return snap
