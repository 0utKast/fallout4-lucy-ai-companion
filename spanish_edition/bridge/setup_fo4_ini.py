"""Asegura que Fallout4Custom.ini (y Fallout4VrCustom.ini) tenga activado el registro Papyrus (bEnableTrace=1)
y que Fallout4Prefs.ini esté en modo Ventana sin Bordes (bBorderless=1, bFull Screen=0) para que el
HUD de Subtítulos y Chat Pip-Boy en Pantalla se dibuje directamente dentro de Fallout 4 sin minimizar el juego."""

import configparser
from pathlib import Path
import re


def _enable_papyrus_in_file(custom_ini: Path) -> None:
    cfg = configparser.ConfigParser(strict=False)
    cfg.optionxform = str  # preserva mayúsculas/minúsculas

    if custom_ini.exists():
        try:
            cfg.read(custom_ini, encoding="utf-8")
        except Exception:
            cfg.read(custom_ini, encoding="latin-1")

    if "General" not in cfg:
        cfg["General"] = {}

    if "Papyrus" not in cfg:
        cfg["Papyrus"] = {}

    changed = False
    if cfg["General"].get("bAlwaysActive") != "1":
        cfg["General"]["bAlwaysActive"] = "1"
        changed = True

    for key in ("bEnableLogging", "bEnableTrace", "bLoadDebugInformation"):
        if cfg["Papyrus"].get(key) != "1":
            cfg["Papyrus"][key] = "1"
            changed = True

    if changed or not custom_ini.exists():
        with custom_ini.open("w", encoding="utf-8") as f:
            cfg.write(f, space_around_delimiters=False)
        print(f"[INI] Activado soporte Papyrus y bAlwaysActive=1 (el juego no se pausa al abrir el Chat HUD) en {custom_ini}", flush=True)
    else:
        print(f"[INI] Soporte Papyrus y bAlwaysActive=1 ya estaban activos en {custom_ini}", flush=True)


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
            f"[INI] Activado modo Pantalla Completa sin Bordes (bBorderless=1, bFull Screen=0) en {prefs_ini} para el HUD integrado en el juego.",
            flush=True,
        )
    else:
        print(
            f"[INI] Modo Pantalla Completa sin Bordes ya activo en {prefs_ini} (HUD integrado en pantalla listo).",
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
        print("[INI] No se encontró todavía My Games/Fallout4 ni My Games/Fallout4VR.", flush=True)


if __name__ == "__main__":
    ensure_papyrus_trace()
