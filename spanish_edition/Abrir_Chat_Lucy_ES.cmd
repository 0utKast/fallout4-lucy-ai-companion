@echo off
chcp 65001 >nul
title Comunicaciones Pip-Boy Vault-Tec — Lucy MacLean (Edicion Espanol F8)
cd /d "%~dp0bridge"
python -u chat_lucy.py
pause
