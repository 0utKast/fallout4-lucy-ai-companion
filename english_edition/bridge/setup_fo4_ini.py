"""Asegura que Fallout4Custom.ini tenga activado el registro Papyrus (bEnableTrace=1)
para que Fallout 4 pueda enviar los snapshots JSON al bridge local de Lucy."""

import configparser
from pathlib import Path


def ensure_papyrus_trace() -> None:
    ini_dir = Path.home() / "Documents" / "My Games" / "Fallout4"
    if not ini_dir.exists():
        print(f"[INI] Carpeta {ini_dir} no encontrada todavía.", flush=True)
        return

    custom_ini = ini_dir / "Fallout4Custom.ini"
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

    if changed:
        with custom_ini.open("w", encoding="utf-8") as f:
            cfg.write(f, space_around_delimiters=False)
        print(f"[INI] Activado soporte de logs Papyrus en {custom_ini}", flush=True)
    else:
        print(f"[INI] Soporte de logs Papyrus ya estaba activo en {custom_ini}", flush=True)


if __name__ == "__main__":
    ensure_papyrus_trace()
