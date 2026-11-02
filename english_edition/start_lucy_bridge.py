"""Pure Python Launcher for the Lucy MacLean (Vault 33) Local AI Bridge [English Edition].

1. Verifies Fallout4Custom.ini Papyrus logging settings (`bEnableTrace=1`).
2. Starts the local HTTP/RAG/Voice Bridge server on 127.0.0.1:7777.
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
