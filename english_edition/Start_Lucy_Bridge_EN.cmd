@echo off
chcp 65001 > nul
title Lucy MacLean (Vault 33) - Local AI Bridge for Fallout 4 [English Edition]
echo ============================================================================
echo   LUCY MACLEAN (VAULT 33) - 100%% LOCAL AI COMPANION [ENGLISH EDITION]
echo ============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Fallout4Custom.ini logging configuration...
python bridge\setup_fo4_ini.py

echo [2/3] Checking local Ollama server (127.0.0.1:11434)...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; Write-Host '[Ollama] Server active and ready.' } catch { Write-Host '[Ollama] Starting local Ollama server...'; Start-Process -FilePath \"$env:LOCALAPPDATA\Programs\Ollama\ollama.exe\" -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep -Seconds 3 }"

echo [3/3] Starting Lucy MacLean AI Bridge Server (English Edition)...
echo.
python bridge\server.py
pause
