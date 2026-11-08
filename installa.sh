#!/usr/bin/env bash
# Installa tutto quello che serve a Scaffale su Linux (Ubuntu/Debian, Fedora, Arch).
#
#   ./installa.sh
#
# Fa, nell'ordine:
#   1. i programmi di sistema: Python con venv e tkinter, Tesseract, unixODBC, gio, curl
#   2. un ambiente Python tutto suo, in .venv dentro questa cartella, con i pacchetti
#      di requisiti.txt (il Python di sistema non si tocca)
#   3. Ollama (se manca, con lo script ufficiale di ollama.com) e i tre modelli:
#      bge-m3, qwen3:8b, glm-ocr
#   4. il controllo finale (prepara.py) e l'icona nel menu e sul desktop
# Quello che c'è già lo lascia com'è. Si può rilanciare: rifà solo quello che manca.
set -u
cd "$(dirname "$(readlink -f "$0")")" || exit 1
QUI="$(pwd)"
PROBLEMI=()

titolo() { printf "\n  \033[36m%s\033[0m\n  %s\n" "$1" "$(printf '%*s' "${#1}" '' | tr ' ' '-')"; }
ok()     { printf "  \033[32m[ok]\033[0m      %s\n" "$1"; }
manca()  { printf "  \033[33m[manca]\033[0m   %s\n" "$1"; PROBLEMI+=("$1"); }
dice()   { printf "            %s\n" "$1"; }

printf "\n  \033[36mSCAFFALE — installazione su Linux\033[0m\n"
echo "  Ci vogliono da 30 a 60 minuti, quasi tutti di download (circa 10 GB)."
echo "  Serve internet adesso; dopo, Scaffale lavora senza."
echo "  Alcuni passi chiedono la password di amministratore (sudo): è normale."

case "$QUI" in
  *OneDrive*|*onedrive*)
    echo
    printf "  \033[33mAttenzione:\033[0m questa cartella sta dentro OneDrive.\n"
    echo "  Scaffale tiene qui la sua base dati, e OneDrive la sincronizzerebbe mentre"
    echo "  Scaffale la scrive (e un altro computer potrebbe aprirla nello stesso momento)."
    echo "  Copia la cartella Scaffale fuori da OneDrive, per esempio in ~/Scaffale,"
    echo "  e lancia l'installazione da lì. I tuoi documenti invece possono restare in OneDrive."
    read -r -p "  Continuo lo stesso? [s/N] " r; [[ "$r" =~ ^[sS] ]] || exit 1 ;;
esac

# --- spazio libero ---
LIBERI=$(df -Pk "$QUI" | awk 'NR==2 {printf "%d", $4/1024/1024}')
if [ "${LIBERI:-0}" -lt 15 ]; then manca "spazio libero: ${LIBERI} GB, ne servono almeno 15"; fi

# --- 1. programmi di sistema ---
titolo "1. Programmi di sistema"
if command -v apt-get >/dev/null; then
  sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip python3-tk \
    tesseract-ocr unixodbc libglib2.0-bin xdg-utils curl zstd
elif command -v dnf >/dev/null; then
  sudo dnf install -y python3 python3-pip python3-tkinter tesseract unixODBC glib2 xdg-utils curl zstd
elif command -v pacman >/dev/null; then
  sudo pacman -S --needed --noconfirm python python-pip tk tesseract unixodbc glib2 xdg-utils curl zstd
else
  manca "non riconosco il gestore dei pacchetti: installa a mano python3 (con venv e tkinter), tesseract, curl"
fi
command -v python3 >/dev/null && ok "Python $(python3 -c 'import sys; print(sys.version.split()[0])')" \
  || { manca "python3"; exit 1; }
command -v tesseract >/dev/null && ok "Tesseract $(tesseract --version 2>&1 | head -1 | awk '{print $2}') (i dizionari delle lingue sono già in Scaffale/tessdata)" \
  || manca "Tesseract (senza, le scansioni restano senza testo)"

# --- 2. l'ambiente Python di Scaffale ---
titolo "2. I pacchetti Python di Scaffale (in .venv)"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv || { manca "python3-venv: non riesco a creare .venv"; exit 1; }; fi
.venv/bin/python -m pip install --disable-pip-version-check -r requisiti.txt \
  && ok "pacchetti installati in $QUI/.venv" \
  || manca "alcuni pacchetti Python (vedi sopra; rilancia: spesso è la rete)"

# --- 3. Ollama e i modelli ---
titolo "3. Ollama e i tre modelli"
risponde() { curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null; }
if ! command -v ollama >/dev/null; then
  dice "Installo Ollama con lo script ufficiale di ollama.com (chiede la password)."
  curl -fsSL https://ollama.com/install.sh | sh
fi
if command -v ollama >/dev/null; then
  ok "Ollama $(ollama --version 2>/dev/null | awk '{print $NF}')"
  if ! risponde; then
    sudo systemctl start ollama 2>/dev/null || (nohup ollama serve >/dev/null 2>&1 &)
    for i in $(seq 1 30); do risponde && break; sleep 2; done
  fi
  if risponde; then
    PRESENTI=$(curl -s http://127.0.0.1:11434/api/tags | tr 'A-Z' 'a-z')
    for m in "bge-m3|la ricerca per senso, circa 1,2 GB" "qwen3:8b|riassunti e risposte, circa 5 GB" \
             "glm-ocr|i .md verificati, circa 2 GB"; do
      nome="${m%%|*}"; a="${m#*|}"
      if echo "$PRESENTI" | grep -q "\"$nome"; then ok "$nome c'è già ($a)"; continue; fi
      dice "Scarico $nome: $a…"
      ollama pull "$nome" && ok "$nome scaricato" || manca "il modello $nome (rilancia: riprende da dove era)"
    done
  else
    manca "Ollama installato ma spento: prova «sudo systemctl start ollama» e rilancia"
  fi
else
  manca "Ollama (senza: niente ricerca per senso, riassunti, domande, .md verificati)"
fi

# --- 4. controllo finale e icona ---
titolo "4. Controllo finale"
.venv/bin/python prepara.py </dev/null
chmod +x avvia.sh crea_collegamento.sh 2>/dev/null
./crea_collegamento.sh >/dev/null && ok "icona «Scaffale» nel menu delle applicazioni e sul desktop"

echo
if [ ${#PROBLEMI[@]} -eq 0 ]; then
  printf "  \033[32mTUTTO PRONTO.\033[0m Per usare Scaffale: l'icona «Scaffale», oppure  ./avvia.sh\n"
else
  printf "  \033[33mQUASI PRONTO. Manca ancora:\033[0m\n"
  for p in "${PROBLEMI[@]}"; do printf "    - %s\n" "$p"; done
  echo "  Rilancia ./installa.sh: rifà solo quello che manca."
fi
