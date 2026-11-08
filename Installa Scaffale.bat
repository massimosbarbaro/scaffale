@echo off
chcp 65001 >nul
title Scaffale - installazione
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installa.ps1" %*
echo.
pause
