#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla che il computer abbia tutto, e installa quello che può installare.

Si lancia una volta sola, prima di usare Scaffale:

    python prepara.py

Dice che cosa c'è, installa da sé i pacchetti Python mancanti, e per le due
cose che non può installare da solo — Tesseract e Ollama — spiega dove
prenderle e a che cosa servono. Senza Tesseract Scaffale funziona lo stesso:
non riconosce le scansioni. Senza Ollama funziona lo stesso: niente ricerca
semantica, restano quella esatta e quella per tesauro.
"""
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

PACCHETTI = [
    ("fitz", "pymupdf", "leggere i PDF"),
    ("fastapi", "fastapi", "l'app web"),
    ("uvicorn", "uvicorn", "il server dell'app"),
    ("numpy", "numpy", "i confronti fra vettori"),
    ("requests", "requests", "parlare con Ollama"),
]

# Servono ai formati che un archivio vecchio contiene e che nessuno prevede.
# Senza, quei file restano nell'indice ma muti: Scaffale li elenca e dichiara
# che cosa gli manca per leggerli, invece di far finta che siano vuoti.
PACCHETTI_FORMATI = [
    ("striprtf", "striprtf", "i vecchi .rtf"),
    ("xlrd", "xlrd", "i fogli .xls fino al 2003"),
    ("openpyxl", "openpyxl", "i fogli .xlsx"),
    ("access_parser", "access-parser", "i database Access .mdb e .accdb"),
]

# Il driver Access di Microsoft esiste solo su Windows: su Linux e su Mac non
# c'e' niente che pyodbc possa trovare, e chiederlo manda a cercare un
# amministratore per un lavoro che access-parser fa da solo, senza driver.
# Dove il driver c'e', pero', e' piu' svelto: li' pyodbc si chiede ancora.
if os.name == "nt":
    PACCHETTI_FORMATI.insert(3, ("pyodbc", "pyodbc",
                                 "i database Access, per la via svelta del driver"))


# Il terzo giudice dei numeri nei .md: dove Tesseract e GLM-OCR non concordano,
# PaddleOCR decide a maggioranza. Senza, restano da guardare a mano più righe.
PACCHETTI_VERIFICA = [
    ("rapidocr", "rapidocr", "PaddleOCR, il terzo giudice dei numeri nei .md"),
    ("onnxruntime", "onnxruntime", "il motore su cui gira PaddleOCR"),
]


def verde(t):
    return f"  [ok]      {t}"


def giallo(t):
    return f"  [manca]   {t}"


# Un pacchetto Python può esserci e non aprirsi lo stesso, perché gli manca una
# libreria del sistema: su Linux pyodbc senza unixodbc è il caso tipico.
# Reinstallarlo non servirebbe a niente, quindi si dice che cosa manca davvero.
LIBRERIE_DI_SISTEMA = {
    "pyodbc": "unixodbc — su Ubuntu o Debian: sudo apt install unixodbc.\n"
              "            Ma su Linux non serve: i .mdb li legge access-parser.",
}


def _controlla(elenco, senza_questi):
    """Elenca che cosa c'è, e propone di installare il resto."""
    mancanti = []
    for modulo, pacchetto, a_che_serve in elenco:
        try:
            __import__(modulo)
            print(verde(f"{pacchetto} — {a_che_serve}"))
        except ModuleNotFoundError:
            print(giallo(f"{pacchetto} — {a_che_serve}"))
            mancanti.append(pacchetto)
        except ImportError as errore:
            print(giallo(f"{pacchetto} — {a_che_serve}"))
            print(f"            c'è, ma non si apre: {errore}")
            print("            manca " + LIBRERIE_DI_SISTEMA.get(pacchetto, "una libreria del sistema"))
    if not mancanti:
        return
    try:
        risposta = input(f"\nInstallo {', '.join(mancanti)}? [s/N] ").strip().lower()
    except EOFError:                 # lanciato senza tastiera (installa.sh): non installo
        risposta = "n"
        print()
    if risposta.startswith("s"):
        subprocess.run([sys.executable, "-m", "pip", "install", *mancanti])
    else:
        print(f"  Salto. {senza_questi}")


def main():
    print("Scaffale — controllo del computer\n")
    print(f"Python {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 9):
        print("  ATTENZIONE: serve Python 3.9 o successivo.")
        return

    # 1) pacchetti Python
    print("\nPacchetti Python")
    _controlla(PACCHETTI, "Senza questi pacchetti l'app non parte.")

    # 1bis) i formati oltre il PDF
    print("\nFormati oltre il PDF")
    _controlla(PACCHETTI_FORMATI,
               "Quei file resteranno nell'indice senza contenuto cercabile.")
    print("  I .csv, i .odt, i .ods e i .pptx si leggono senza installare niente.")

    # 1ter) il terzo giudice dei numeri
    print("\nVerifica dei numeri nei .md (circa 280 MB)")
    _controlla(PACCHETTI_VERIFICA,
               "I numeri si leggeranno due volte invece di tre: più righe da guardare a mano.")

    import impostazioni
    d = impostazioni.diagnosi()

    # 2) Tesseract
    print("\nOCR — Tesseract")
    if d["tesseract"]:
        print(verde(d["tesseract"]))
        print(f"            dizionari in {d['tessdata']}")
        print(f"            lingue presenti: {', '.join(d['lingue']) or 'nessuna'}")
        if d["lingue_usate"] and d["lingue_usate"] != "eng":
            print(f"            userò: {d['lingue_usate']}")
        elif d["lingue"] and set(d["lingue"]) <= {"eng", "osd"}:
            print("            solo inglese: per l'italiano, il croato e il latino")
            print("            scarica i dizionari da github.com/tesseract-ocr/tessdata")
            print("            e mettili nella cartella tessdata\\ di Scaffale.")
    elif impostazioni.server_ocr() and impostazioni.modello_ocr():
        print(giallo("non trovato, ma le pagine le legge " + impostazioni.modello_ocr()))
        print("            i riquadri delle righe li dà PaddleOCR, che è già qui")
        print("            Tesseract resta meglio dove c'è: su Linux, apt install tesseract-ocr")
        print("            Senza password di amministratore, va bene micromamba:")
        print("            micromamba create -p /data/envs/tesseract -c conda-forge tesseract")
    else:
        print(giallo("non trovato — le scansioni resteranno senza testo"))
        print("            Windows: github.com/UB-Mannheim/tesseract/wiki")
        print("            macOS:   brew install tesseract")
        print("            Linux:   apt install tesseract-ocr")
        print("            Linux senza password di amministratore, in casa propria:")
        print("              micromamba create -p /data/envs/tesseract -c conda-forge tesseract")
        print("              (porta con se' 125 dizionari, ita_old compreso)")
        print("            Se è installato altrove, scrivi il percorso in scaffale.ini")

    # 3) Ollama
    print("\nRicerca semantica — Ollama")
    try:
        import semantica
        if semantica.acceso():
            modelli = semantica.modelli()
            print(verde(f"in ascolto su {d['ollama']}"))
            if any(m.startswith("bge-m3") for m in modelli):
                print(verde(f"modello {d['modello']} presente"))
            else:
                print(giallo(f"manca il modello {d['modello']}"))
                print(f"            prendilo con:  ollama pull {d['modello'].split(':')[0]}")
                print(f"            modelli presenti: {', '.join(modelli[:6]) or 'nessuno'}")
            # i riassunti li scrive un altro modello, sempre sul computer
            import biblioteca
            scrittore = biblioteca._modello_per_riassunti()
            if scrittore:
                print(verde(f"riassunti: li scrive {scrittore}"))
            else:
                print(giallo("nessun modello per scrivere i riassunti"))
                print("            prendilo con:  ollama pull qwen3:8b   (circa 5 GB)")
                print("            Senza, tutto il resto funziona: mancano solo i riassunti.")
            # i .md verificati: GLM-OCR rilegge i numeri e le righe delle stampe antiche
            import verifica_numeri
            if verifica_numeri.modello():
                print(verde(f".md verificati: la seconda lettura la fa {verifica_numeri.modello()}"))
                if impostazioni.server_ocr() and verifica_numeri.modello() == impostazioni.modello_ocr():
                    print(f"            non in Ollama, ma sul server {impostazioni.server_ocr()}")
            else:
                print(giallo("manca GLM-OCR: i .md si farebbero con una lettura sola, senza verifica"))
                print("            prendilo con:  ollama pull glm-ocr   (circa 2 GB)")
        else:
            print(giallo(f"non risponde su {d['ollama']}"))
            print("            installalo da ollama.com, poi:  ollama serve")
            print(f"            e poi:  ollama pull {d['modello'].split(':')[0]}")
            print("            Senza, restano la ricerca esatta e quella per tesauro.")
    except ImportError:
        print(giallo("controllo saltato: mancano ancora dei pacchetti Python"))

    # 4) il file delle impostazioni
    print("\nImpostazioni")
    if d["ini"]:
        print(verde(d["ini"]))
    else:
        percorso = impostazioni.scrivi_esempio()
        print(verde(f"creato {percorso}"))
        print("            aprilo se devi correggere un percorso a mano")

    print("\nPer cominciare:\n    python scaffale.py servi")
    print("Si apre nel browser e la prima schermata chiede la cartella da indicizzare.")


if __name__ == "__main__":
    main()
