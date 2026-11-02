@echo off
chcp 65001 >nul
title Servidor Puente IA Local — Lucy MacLean (Edicion Espanol + Voz ef_dora)
cd /d "%~dp0bridge"
python -u server.py
pause
