"""Lanzador Python para el Puente IA Local de Lucy MacLean (Refugio 33) [Edición Español v1.0.1].

1. Comprueba los ajustes de registro Papyrus en Fallout4Custom.ini (`bEnableTrace=1`).
2. Inicia el servidor local HTTP/RAG/Voz en 127.0.0.1:7777.
"""

import sys
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parent / "bridge"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

import setup_fo4_ini
import server


def main() -> None:
    setup_fo4_ini.ensure_papyrus_trace()
    server.run_server()


if __name__ == "__main__":
    main()
