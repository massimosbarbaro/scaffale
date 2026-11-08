@echo off
chcp 65001 >nul
title Scaffale
cd /d "%~dp0"

echo.
echo   SCAFFALE
echo   ------------------------------------------------------------
echo.

rem --- c'e' Python? ---
where python >nul 2>&1
if errorlevel 1 (
  echo   Python non risulta installato, o non e' nel PATH.
  echo.
  echo   Scaricalo da  https://www.python.org/downloads/
  echo   e durante l'installazione spunta "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

rem --- i pacchetti ci sono? ---
python -c "import fastapi, uvicorn, fitz" >nul 2>&1
if errorlevel 1 (
  echo   Manca qualcosa. Avvio la preparazione...
  echo.
  python prepara.py
  echo.
)

rem --- Ollama: se e' installato ma spento, lo accendo ---
where ollama >nul 2>&1
if not errorlevel 1 (
  python -c "import urllib.request; urllib.request.urlopen('http://localhost:11434/api/tags', timeout=3)" >nul 2>&1
  if errorlevel 1 (
    echo   Accendo Ollama per la ricerca semantica...
    start "" /min ollama serve
    timeout /t 4 /nobreak >nul
  )
)

echo   Un attimo: il browser si apre da solo appena Scaffale e' pronto.
echo.

python scaffale.py servi

rem --- chiuso bene: la finestra se ne va da sola. Con un errore resta,
rem --- perche' si possa leggere che cosa e' successo.
if errorlevel 1 (
  echo.
  echo   Scaffale si e' fermato per un errore: leggi qui sopra che cosa e' successo.
  echo.
  pause
)
