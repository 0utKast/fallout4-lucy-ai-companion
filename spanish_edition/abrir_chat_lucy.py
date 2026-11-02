"""Lanzador Python para la Ventana de Comunicaciones Pip-Boy Vault-Tec [Edición Español]."""

import sys
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parent / "bridge"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

import chat_lucy

if __name__ == "__main__":
    chat_lucy.main()
