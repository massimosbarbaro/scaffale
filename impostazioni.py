#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dove sta cosa, su questo computer.

I percorsi non sono scritti nel codice: si cercano da soli e, se serve, si
correggono in `scaffale.ini`, che sta accanto a questo file. Così il programma
gira su una macchina diversa da quella su cui è stato scritto senza toccare
una riga di codice.
"""
import configparser
import os
import shutil

QUI = os.path.dirname(os.path.abspath(__file__))
INI = os.path.join(QUI, "scaffale.ini")

PREDEFINITI = {
    "tesseract": "",          # vuoto = cercalo da solo
    "tessdata": "",           # vuoto = usa quello dentro il pacchetto, poi quello di sistema
    "lingue_ocr": "ita+lat+eng+hrv+slv+deu+fra+ell+grc",
    "ollama": "http://localhost:11434",
    "modello": "bge-m3:latest",
    # La seconda lettura delle scansioni. Vuoto = GLM-OCR dentro Ollama, come
    # sempre. Se il computer ha di meglio gia acceso — un server compatibile
    # OpenAI, llama.cpp o vLLM, con un modello che vede le immagini — qui si
    # mette il suo indirizzo e il nome del modello, e Scaffale chiede a lui.
    "server_ocr": "",
    "modello_ocr": "",
    "porta": "8000",
    "dpi_ocr": "300",
}

CANDIDATI_TESSERACT = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract",
    # Dove l'utente non ha la password di amministratore, Tesseract si mette in
    # casa propria con micromamba invece che con apt: su ALDHI sta qui.
    "/data/envs/tesseract/bin/tesseract",
    os.path.expanduser("~/.local/bin/tesseract"),
    os.path.expanduser("~/micromamba/envs/tesseract/bin/tesseract"),
]


def _config():
    c = configparser.ConfigParser()
    c["scaffale"] = dict(PREDEFINITI)
    if os.path.exists(INI):
        c.read(INI, encoding="utf-8")
    return c


def scrivi_esempio():
    c = _config()
    with open(INI, "w", encoding="utf-8") as fh:
        fh.write("# Percorsi e preferenze di Scaffale.\n"
                 "# Lascia vuoto un valore per farlo cercare da solo.\n")
        c.write(fh)
    return INI


def valore(chiave):
    return _config()["scaffale"].get(chiave, PREDEFINITI.get(chiave, ""))


def tesseract():
    """Il percorso dell'eseguibile, o stringa vuota se non c'è."""
    dichiarato = valore("tesseract")
    if dichiarato and os.path.exists(dichiarato):
        return dichiarato
    trovato = shutil.which("tesseract")
    if trovato:
        return trovato
    for c in CANDIDATI_TESSERACT:
        if c and os.path.exists(c):
            return c
    return ""


def tessdata():
    """I dizionari OCR: prima quelli del pacchetto, poi quelli di sistema."""
    dichiarato = valore("tessdata")
    if dichiarato and os.path.isdir(dichiarato):
        return dichiarato
    interno = os.path.join(QUI, "tessdata")
    if os.path.isdir(interno) and any(f.endswith(".traineddata") for f in os.listdir(interno)):
        return interno
    exe = tesseract()
    if exe:
        # Su Windows i dizionari stanno accanto all'eseguibile; con i pacchetti
        # Unix (apt, homebrew, micromamba) stanno in `share/tessdata`, un piano
        # piu' su. Si guarda in tutti e due i posti, se no le lingue spariscono
        # pur essendoci, e `lingue_ocr()` torna vuota.
        bin_ = os.path.dirname(exe)
        for accanto in (os.path.join(bin_, "tessdata"),
                        os.path.join(os.path.dirname(bin_), "share", "tessdata")):
            if os.path.isdir(accanto) and any(f.endswith(".traineddata")
                                              for f in os.listdir(accanto)):
                return accanto
    return ""


def lingue_disponibili():
    """Quali dizionari ci sono davvero, così non si chiede l'impossibile."""
    d = tessdata()
    if not d:
        return []
    return sorted(f[:-12] for f in os.listdir(d) if f.endswith(".traineddata"))


def lingue_ocr():
    """Le lingue richieste, ridotte a quelle presenti."""
    volute = [x for x in valore("lingue_ocr").split("+") if x]
    ci_sono = set(lingue_disponibili())
    usabili = [x for x in volute if x in ci_sono]
    return "+".join(usabili) if usabili else ("eng" if "eng" in ci_sono else "")


def ollama():
    return os.environ.get("OLLAMA_HOST") or valore("ollama")


def modello():
    return os.environ.get("SCAFFALE_MODELLO") or valore("modello")


def server_ocr():
    """L'indirizzo del server che rilegge le scansioni, se non e Ollama."""
    return (os.environ.get("SCAFFALE_SERVER_OCR") or valore("server_ocr")).rstrip("/")


def modello_ocr():
    """Il modello della seconda lettura, se e stato scelto a mano."""
    return os.environ.get("SCAFFALE_MODELLO_OCR") or valore("modello_ocr")


def porta():
    try:
        return int(valore("porta"))
    except ValueError:
        return 8000


def dpi_ocr():
    try:
        return int(valore("dpi_ocr"))
    except ValueError:
        return 300


def diagnosi():
    """Che cosa c'è e che cosa manca: la usa prepara.py e la pagina di stato."""
    exe = tesseract()
    d = tessdata()
    return {
        "tesseract": exe or None,
        "tessdata": d or None,
        "lingue": lingue_disponibili(),
        "lingue_usate": lingue_ocr(),
        "ollama": ollama(),
        "modello": modello(),
        "ini": INI if os.path.exists(INI) else None,
    }
