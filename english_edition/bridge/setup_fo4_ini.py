"""Ensures Fallout4Custom.ini (and Fallout4VrCustom.ini) has Papyrus logging enabled (bEnableTrace=1)
and Fallout4Prefs.ini is configured for Borderless Windowed Fullscreen (bBorderless=1, bFull Screen=0)
so the In-Game Pip-Boy Chat & Subtitle HUD Overlay renders directly inside Fallout 4 without minimizing."""

import configparser
from pathlib import Path
import re


def _enable_papyrus_in_file(custom_ini: Path) -> None:
    cfg = configparser.ConfigParser(strict=False)
    cfg.optionxform = str  # preserve case

    if custom_ini.exists():
        try:
            cfg.read(custom_ini, encoding="utf-8")
        except Exception:
            cfg.read(custom_ini, encoding="latin-1")

    if "Papyrus" not in cfg:
        cfg["Papyrus"] = {}

    changed = False
    for key in ("bEnableLogging", "bEnableTrace", "bLoadDebugInformation"):
        if cfg["Papyrus"].get(key) != "1":
            cfg["Papyrus"][key] = "1"
            changed = True

    if changed or not custom_ini.exists():
        with custom_ini.open("w", encoding="utf-8") as f:
            cfg.write(f, space_around_delimiters=False)
        print(f"[INI] Enabled Papyrus logging support in {custom_ini}", flush=True)
    else:
        print(f"[INI] Papyrus logging support already active in {custom_ini}", flush=True)


def _ensure_borderless_in_prefs(prefs_ini: Path) -> None:
    if not prefs_ini.exists():
        return
    try:
        raw = prefs_ini.read_text(encoding="utf-8")
        enc = "utf-8"
    except Exception:
        raw = prefs_ini.read_text(encoding="latin-1")
        enc = "latin-1"

    new_raw = re.sub(r"(?im)^(\s*bBorderless\s*=\s*)0\s*$", r"\g<1>1", raw)
    new_raw = re.sub(r"(?im)^(\s*bFull Screen\s*=\s*)1\s*$", r"\g<1>0", new_raw)

    if new_raw != raw:
        prefs_ini.write_text(new_raw, encoding=enc)
        print(
            f"[INI] Enabled Borderless Fullscreen (bBorderless=1, bFull Screen=0) in {prefs_ini} for Seamless In-Game HUD Overlay.",
            flush=True,
        )
    else:
        print(
            f"[INI] Borderless Fullscreen already active in {prefs_ini} (In-Game HUD Overlay ready).",
            flush=True,
        )


def ensure_papyrus_trace() -> None:
    home = Path.home()
    doc_roots = [home / "Documents" / "My Games", home / "OneDrive" / "Documents" / "My Games"]
    found_any = False

    for root in doc_roots:
        for game_folder, ini_names in (
            ("Fallout4", ("Fallout4Custom.ini",)),
            ("Fallout4VR", ("Fallout4Custom.ini", "Fallout4VrCustom.ini")),
        ):
            ini_dir = root / game_folder
            if ini_dir.exists():
                found_any = True
                for ini_name in ini_names:
                    _enable_papyrus_in_file(ini_dir / ini_name)
                if game_folder == "Fallout4":
                    _ensure_borderless_in_prefs(ini_dir / "Fallout4Prefs.ini")

    if not found_any:
        print("[INI] Could not find My Games/Fallout4 or My Games/Fallout4VR yet.", flush=True)


if __name__ == "__main__":
    ensure_papyrus_trace()
