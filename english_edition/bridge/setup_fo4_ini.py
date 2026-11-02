"""Ensures Fallout4Custom.ini (and Fallout4VrCustom.ini for Fallout 4 VR) has Papyrus logging enabled
(bEnableTrace=1) so both Fallout 4 and Fallout 4 VR can send live JSON snapshots to Lucy's local bridge."""

import configparser
from pathlib import Path


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
        print(f"[INI] Enabled Papyrus log support in {custom_ini}", flush=True)
    else:
        print(f"[INI] Papyrus log support already active in {custom_ini}", flush=True)


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

    if not found_any:
        print("[INI] Neither My Games/Fallout4 nor My Games/Fallout4VR found yet.", flush=True)


if __name__ == "__main__":
    ensure_papyrus_trace()
