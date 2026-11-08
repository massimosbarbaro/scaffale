#!/usr/bin/env bash
# Apre Scaffale: controlla che ci sia tutto, accende Ollama se è spento, e apre il
# browser appena Scaffale è pronto. La finestra del terminale resta aperta: è il
# programma che gira. Si chiude da sola quando si chiude Scaffale nel browser.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
echo
echo "  SCAFFALE"
echo "  ------------------------------------------------------------"
echo
PY=.venv/bin/python
if [ ! -x "$PY" ] || ! "$PY" -c "import fastapi, uvicorn, fitz" 2>/dev/null; then
  echo "  Manca qualcosa: lancia prima  ./installa.sh"
  read -r -p "  Premi Invio per chiudere. " _
  exit 1
fi
if command -v ollama >/dev/null && ! curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "  Accendo Ollama per la ricerca semantica..."
  (nohup ollama serve >/dev/null 2>&1 &)
  sleep 4
fi
echo "  Un attimo: il browser si apre da solo appena Scaffale è pronto."
echo
"$PY" scaffale.py servi
if [ $? -ne 0 ]; then
  echo
  echo "  Scaffale si è fermato per un errore: leggi qui sopra che cosa è successo."
  read -r -p "  Premi Invio per chiudere. " _
fi
