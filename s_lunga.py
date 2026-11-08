#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La s lunga delle stampe antiche (ſ), che l'OCR legge f: «fopra», «quefto», «effere».

Due rimedi, uno dopo l'altro. Il primo è il dizionario ita_old di Tesseract,
addestrato sulle stampe antiche: la ſ la riconosce come tale, e qui diventa s.
Il secondo è per quello che resta: una parola con la f che in italiano e in
latino non esiste, mentre con una o più di quelle f lette s è una parola
italiana, si corregge («poffa» → «possa»). Una parola che esiste così com'è —
«offerta», «fama», «fecit» — non si tocca mai.

Le parole vengono dai dizionari di Tesseract stessi (tessdata/parole_ita.txt.gz,
parole_lat.txt.gz), estratti una volta con dawg2wordlist.
"""
import gzip
import itertools
import os
import re

import impostazioni

RX_PAROLA = re.compile(r"[^\W\d_]+")
RX_FT = re.compile(r"f[tc]")
MAX_F = 4
_dizionari = None


def _carica(nome):
    for cartella in (impostazioni.tessdata(), os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")):
        f = os.path.join(cartella or "", nome)
        if os.path.exists(f):
            return set(gzip.open(f, "rt", encoding="utf-8").read().split())
    return set()


def dizionari():
    """(italiano, tutte le parole note): vuoti se i file mancano, e allora non si corregge niente."""
    global _dizionari
    if _dizionari is None:
        import coppie
        ita = _carica("parole_ita.txt.gz")
        # le parole delle altre lingue dell'archivio si proteggono anche loro
        # («fifteenth», «Jahreshefte»), meno quelle che sono proprio la s lunga
        # sbagliata («fia», «fue» esistono in croato o in francese antico)
        note = ita | _carica("parole_lat.txt.gz") | _carica("parole_altre.txt.gz")
        _dizionari = (ita, note - coppie.S_LUNGA)
    return _dizionari


SOGLIA_PER_MILLE = 1.5


def per_mille(testo):
    """Le parole con la s lunga letta f ogni mille, contate come coppie.esamina."""
    import coppie
    parole = RX_PAROLA.findall(testo or "")
    return 1000 * sum(1 for w in parole if w.lower() in coppie.S_LUNGA) / max(len(parole), 1)


def antica(md):
    """Il .md che c'è viene da una stampa antica letta col dizionario moderno?
    Lo si vede dalla s lunga: quella che coppie.esamina conta («fopra», «quefto»)."""
    import coppie
    if not md or not os.path.exists(md):
        return False
    return coppie.esamina(md)["dati"].get("s_lunga_per_mille", 0) > SOGLIA_PER_MILLE


def pdf_antico(percorso):
    """Il testo che il PDF ha già dentro — l'OCR di altri — ha la s lunga letta f?
    Falso per un PDF senza testo, o che non è un PDF."""
    if not percorso.lower().endswith(".pdf"):
        return False
    try:
        import fitz
        with fitz.open(percorso) as d:
            testo = " ".join(pg.get_text() for pg in d)
    except Exception:
        return False
    return len(testo) > 2000 and per_mille(testo) > SOGLIA_PER_MILLE


def lingue_antiche(lingue):
    """Le lingue per una stampa antica: italiano antico e latino, e basta.
    Provato sulla Relatione del Botero (1605): con tutte e nove le lingue
    impostate Tesseract mette lettere greche nel testo italiano («{στ», «ὁ») e
    sbaglia di più; con ita_old+lat no."""
    ci_sono = set(impostazioni.lingue_disponibili())
    if "ita_old" not in ci_sono:
        return lingue
    return "+".join(["ita_old"] + (["lat"] if "lat" in ci_sono else []))


def _con_maiuscole(come, parola):
    if come.isupper() and len(come) > 1:
        return parola.upper()
    if come[:1].isupper():
        return parola[:1].upper() + parola[1:]
    return parola


RX_U_FRA_VOCALI = re.compile(r"(?<=[aeiou])u(?=[aeiou])")


def _esiste(w, ita):
    """La parola è italiana, anche scritta all'antica: la u per la v fra due
    vocali («hauesse», «sapeua»), il «si» attaccato al verbo («rallegrandosi»)."""
    if w in ita or RX_U_FRA_VOCALI.sub("v", w) in ita:
        return True
    # le forme di avere con la h («hauesse», «haueua»)
    if w.startswith("ha") and RX_U_FRA_VOCALI.sub("v", w[1:]) in ita:
        return True
    return len(w) > 6 and w.endswith("si") and (w[:-2] in ita or RX_U_FRA_VOCALI.sub("v", w[:-2]) in ita)


def parola(w):
    """La parola corretta, o la stessa se non c'è niente di sicuro da fare."""
    ita, note = dizionari()
    basso = w.lower()
    if "f" not in basso or basso in note or not ita or (w.isupper() and len(w) <= 5):
        return w
    dove = [i for i, c in enumerate(basso) if c == "f"]
    if len(dove) > MAX_F:
        return w
    # prima le correzioni con meno cambi: «affai» → «assai», non oltre
    for k in range(1, len(dove) + 1):
        trovate = set()
        for scelta in itertools.combinations(dove, k):
            c = list(basso)
            for i in scelta:
                c[i] = "s"
            nuova = "".join(c)
            if _esiste(nuova, ita):
                trovate.add(nuova)
        if len(trovate) == 1:
            return _con_maiuscole(w, trovate.pop())
        if trovate:
            return w        # due letture possibili: meglio lasciarla com'è
    # forme antiche o spezzate che il dizionario non ha («noftre», «ingiufti»):
    # «ft» e «fc» in italiano e in latino quasi non ci sono, «st» e «sc» ovunque
    # (solo parole minuscole, o con la sola iniziale maiuscola, finite in vocale
    # come quelle italiane: le sigle e i nomi stranieri restano come sono)
    if RX_FT.search(basso) and w[1:].islower() and len(w) >= 5 and basso[-1] in "aeiou":
        return _con_maiuscole(w, RX_FT.sub(lambda m: "s" + m.group(0)[1], basso))
    return w


def correggi(testo):
    """Il testo con la ſ fatta s e le parole con la s letta f corrette."""
    testo = testo.replace("ſ", "s")
    if not dizionari()[0]:
        return testo
    return RX_PAROLA.sub(lambda m: parola(m.group(0)), testo)
