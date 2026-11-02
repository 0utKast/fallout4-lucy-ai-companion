@echo off
chcp 65001 > nul
title Vault-Tec Pip-Boy Comms - Live Chat with Lucy MacLean (F8) [English Edition]
cd /d "%~dp0"
python bridge\chat_lucy.py
