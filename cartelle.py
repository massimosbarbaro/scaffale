#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scegliere una cartella senza doverne scrivere il percorso.

Due strade, perché nessuna delle due funziona sempre:

  1. la finestra di sistema, quella a cui tutti sono abituati. Va aperta dal
     computer su cui gira il programma — che qui è lo stesso di chi lo usa —
     e richiede tkinter, che su Windows e macOS c'è sempre, su Linux talvolta no.
  2. un navigatore dentro l'app: elenca dischi e sottocartelle e si scende di
     cartella in cartella. Più lento, ma non dipende da nulla.

La prima si prova, e se non c'è resta la seconda.
"""
import os
import string
import sys
import threading


def unita():
    """I dischi disponibili. Su Windows le lettere, altrove la radice."""
    if os.name != "nt":
        return ["/"]
    fuori = []
    for lettera in string.ascii_uppercase:
        percorso = f"{lettera}:" + os.sep
        if os.path.exists(percorso):
            fuori.append(percorso)
    return fuori


def scorciatoie():
    """I posti da cui si comincia quasi sempre."""
    casa = os.path.expanduser("~")
    voci = [("Home", casa)]
    for nome, sotto in (("Documenti", "Documents"), ("Desktop", "Desktop"),
                        ("Scaricati", "Downloads")):
        p = os.path.join(casa, sotto)
        if os.path.isdir(p):
            voci.append((nome, p))
    # OneDrive, che su queste macchine contiene quasi sempre il materiale
    for nome in os.listdir(casa) if os.path.isdir(casa) else []:
        if nome.lower().startswith("onedrive"):
            voci.append((nome, os.path.join(casa, nome)))
    return voci


def elenca(percorso=""):
    """Le sottocartelle di un percorso, con le briciole per risalire."""
    if not percorso:
        return {"percorso": "", "su": None, "briciole": [],
                "cartelle": [{"nome": u, "percorso": u} for u in unita()],
                "scorciatoie": [{"nome": n, "percorso": p} for n, p in scorciatoie()]}
    percorso = os.path.abspath(percorso)
    if not os.path.isdir(percorso):
        return {"errore": f"non è una cartella: {percorso}"}
    cartelle = []
    try:
        for voce in sorted(os.scandir(percorso), key=lambda e: e.name.lower()):
            if not voce.is_dir():
                continue
            if voce.name.startswith((".", "$")) or voce.name.lower() in (
                    "system volume information", "windows", "$recycle.bin"):
                continue
            cartelle.append({"nome": voce.name, "percorso": voce.path})
    except PermissionError:
        return {"errore": "non ho il permesso di leggere questa cartella"}
    except OSError as exc:
        return {"errore": f"{type(exc).__name__}"}

    briciole, resto = [], percorso
    while True:
        genitore = os.path.dirname(resto)
        if genitore == resto:
            briciole.insert(0, {"nome": resto, "percorso": resto})
            break
        briciole.insert(0, {"nome": os.path.basename(resto) or resto, "percorso": resto})
        resto = genitore
    su = os.path.dirname(percorso)
    nome_breve = os.path.basename(percorso.rstrip("\\/")) or percorso
    return {"percorso": percorso, "nome_breve": nome_breve,
            "su": su if su != percorso else "",
            "briciole": briciole, "cartelle": cartelle,
            "scorciatoie": [{"nome": n, "percorso": p} for n, p in scorciatoie()],
            "quanti": conta(percorso)}


def conta(percorso, tetto=4000):
    """Quanti documenti ci sono là sotto: dà un'idea prima di lanciarsi."""
    from estrattori import DOCUMENTI, IMMAGINI
    doc = img = 0
    for radice, sotto, file in os.walk(percorso):
        sotto[:] = [d for d in sotto if not d.startswith((".", "$"))]
        for f in file:
            e = os.path.splitext(f)[1].lower()
            if e in DOCUMENTI:
                doc += 1
            elif e in IMMAGINI:
                img += 1
        if doc + img > tetto:
            return {"documenti": f"più di {tetto}", "immagini": ""}
    return {"documenti": doc, "immagini": img}


_SCELTA = {}


def finestra_di_sistema(titolo="Scegli la cartella con i tuoi file"):
    """Apre la finestra del sistema operativo. Restituisce il percorso o ''."""
    try:
        import tkinter
        from tkinter import filedialog
    except Exception:
        return None          # None = non disponibile, diverso da '' = annullato

    esito = {"percorso": ""}

    def apri():
        try:
            radice = tkinter.Tk()
            radice.withdraw()
            radice.attributes("-topmost", True)
            esito["percorso"] = filedialog.askdirectory(title=titolo) or ""
            radice.destroy()
        except Exception:
            esito["percorso"] = ""

    # tkinter vuole il proprio thread, e su Windows dev'essere quello che lo crea
    t = threading.Thread(target=apri)
    t.start()
    t.join(timeout=300)
    p = esito["percorso"]
    return os.path.normpath(p) if p else ""


def disponibile_finestra():
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False
