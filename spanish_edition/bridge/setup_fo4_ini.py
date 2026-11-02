"""Asegura que Fallout4Custom.ini (y Fallout4VrCustom.ini en Fallout 4 VR) tenga activado el registro Papyrus
(bEnableTrace=1) para que tanto Fallout 4 como Fallout 4 VR puedan enviar los snapshots JSON al bridge local de Lucy."""

import configparser
from pathlib import Path


def _enable_papyrus_in_file(custom_ini: Path) -> None:
    cfg = configparser.ConfigParser(strict=False)
    cfg.optionxform = str  # preserva mayúsculas/minúsculas

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
        print(f"[INI] Activado soporte de logs Papyrus en {custom_ini}", flush=True)
    else:
        print(f"[INI] Soporte de logs Papyrus ya estaba activo en {custom_ini}", flush=True)


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
        print("[INI] No se encontró todavía My Games/Fallout4 ni My Games/Fallout4VR.", flush=True)


if __name__ == "__main__":
    ensure_papyrus_trace()
