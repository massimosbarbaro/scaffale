#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aiutare a costruire un tema: le varianti che ci sono davvero nei documenti.

Chi fa un tema scrive le parole che conosce — «onore» — e dimentica quelle che
i documenti usano: «honore», «onori», la «pruoua» dei testi a stampa, l'«effere»
che l'OCR legge dove la stampa aveva «eſſere» con la s lunga. Qui Scaffale le
cerca nel vocabolario dell'indice, cioè fra le parole che compaiono davvero
nei documenti, e le propone con il numero di file in cui stanno. Decide chi fa
il tema: niente entra da solo.

Due fonti:

  il vocabolario   stessa radice (onor-), grafie antiche (h iniziale, u/v,
                   doppie, ti/zi, ct/tt), errori tipici dell'OCR (s→f, rn→m,
                   u→n), e parole molto simili.
  il modello       le traduzioni e le forme in altre lingue — čast, Ehre,
                   honor, honos — chieste al modello di Ollama che gira sul
                   computer. Si propone solo quello che poi si trova anche
                   nell'archivio: il modello può inventare, l'indice no.
"""
import json
import re

import archivio
import biblioteca
import impostazioni
import tesauro

PERCHE = {
    "ocr": "forse un errore di lettura dell'OCR (s lunga letta f, rn letto m…)",
    "grafia": "grafia antica o variante (h, u/v, doppie, ti/zi…)",
    "radice": "stessa radice",
    "simile": "parola molto simile",
    "modello": "proposta dal modello, e c'è nei tuoi documenti",
}
ORDINE = ["grafia", "ocr", "radice", "simile", "modello"]


def _vocabolario(c):
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.vocabolario "
              "USING fts5vocab(main, ricerca, 'row')")


def _con_prefisso(c, prefisso, massimo=20000):
    """Le parole dell'indice che cominciano così, con in quanti brani stanno."""
    return c.execute("SELECT term, doc FROM temp.vocabolario WHERE term >= ? AND term < ? "
                     "LIMIT ?", (prefisso, prefisso + "￿", massimo)).fetchall()


def _distanza(a, b, tetto):
    """Quante lettere cambiare per passare da a a b; si ferma oltre il tetto."""
    if abs(len(a) - len(b)) > tetto:
        return tetto + 1
    prima = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        ora = [i]
        for j, cb in enumerate(b, 1):
            ora.append(min(prima[j] + 1, ora[j - 1] + 1, prima[j - 1] + (ca != cb)))
        if min(ora) > tetto:
            return tetto + 1
        prima = ora
    return prima[-1]


def _sostituzioni(w, da, a):
    """Tutte le parole che si ottengono cambiando una sola occorrenza di da in a."""
    fuori, i = set(), w.find(da)
    while i >= 0:
        fuori.add(w[:i] + a + w[i + len(da):])
        i = w.find(da, i + 1)
    return fuori


def _grafie(w):
    """Come la stessa parola può essere scritta in un testo antico."""
    fuori = set()
    fuori.add(w[1:] if w.startswith("h") else "h" + w)
    for da, a in (("u", "v"), ("v", "u"), ("ti", "zi"), ("zi", "ti"), ("ct", "tt"),
                  ("tt", "ct"), ("pt", "tt"), ("ph", "f"), ("f", "ph"), ("y", "i"),
                  ("j", "i"), ("i", "j"), ("x", "ss"), ("k", "c"), ("ae", "e"), ("oe", "e")):
        fuori |= _sostituzioni(w, da, a)
    for i in range(1, len(w)):                       # le doppie: una in più, una in meno
        if w[i] == w[i - 1] and w[i] not in "aeiou":
            fuori.add(w[:i] + w[i + 1:])
        elif w[i] not in "aeiou" and i + 1 < len(w) and w[i + 1] in "aeiou" and w[i - 1] in "aeiou":
            fuori.add(w[:i] + w[i] + w[i:])
    fuori.discard(w)
    return fuori


def _errori_ocr(w):
    """Come l'OCR legge male la stessa parola in una stampa antica."""
    fuori = set()
    for da, a in (("s", "f"), ("f", "s"), ("m", "rn"), ("rn", "m"), ("n", "u"), ("u", "n"),
                  ("e", "c"), ("c", "e"), ("l", "i"), ("i", "l"), ("h", "b"), ("b", "h")):
        fuori |= _sostituzioni(w, da, a)
    if w.count("s") >= 2:                            # «essere» → «effere»: tutte le s insieme
        fuori.add(w.replace("s", "f"))
    fuori.discard(w)
    return fuori


def _file(c, forma, radice=None):
    """In quanti documenti c'è una forma, nella cartella o in tutto l'archivio."""
    espr = '{testo piatto}:"%s"' % tesauro.piatto(forma).replace('"', " ")
    sql = ("SELECT COUNT(DISTINCT r.documento) n FROM ricerca r WHERE ricerca MATCH ?")
    parametri = [espr]
    if radice:
        sql += " AND r.documento IN (SELECT id FROM documenti WHERE radice = ?)"
        parametri.append(radice)
    try:
        return c.execute(sql, parametri).fetchone()["n"]
    except Exception:
        return 0


def dal_vocabolario(parole, radice=None, massimo=40):
    """Le varianti delle parole di un tema che stanno nei documenti.
    Restituisce [{forma, file, perche, da}], le più sicure prima."""
    c = archivio.apri()
    _vocabolario(c)
    gia = {tesauro.piatto(p) for p in parole}
    trovate = {}                                     # forma -> (tipo, da quale parola, brani)

    def proponi(forma, tipo, da, brani):
        if forma in gia or len(forma) < 3 or forma in biblioteca.PAROLE_VUOTE:
            return
        if tesauro.piatto(forma) != forma:           # «paciﬁca» con la legatura è «pacifica»
            return
        if not biblioteca._parola_vera(forma):
            return
        prima = trovate.get(forma)
        if not prima or ORDINE.index(tipo) < ORDINE.index(prima[0]):
            trovate[forma] = (tipo, da, brani)

    singole = [tesauro.piatto(p) for p in parole if " " not in p.strip()][:8]
    for w in singole:
        if len(w) < 3:
            continue
        grafie, ocr = _grafie(w), _errori_ocr(w)
        tipo_di = lambda t: "grafia" if t in grafie else "ocr"
        vicine = {}
        for pref in {w[:3], ("h" + w)[:3] if not w.startswith("h") else w[1:4]}:
            for term, brani in _con_prefisso(c, pref):
                vicine[term] = brani
        for term in grafie | ocr:
            if term in vicine:
                proponi(term, tipo_di(term), w, vicine[term])
            else:                                    # «effere» per «essere»: comincia diversa
                r = c.execute("SELECT doc FROM temp.vocabolario WHERE term = ?", (term,)).fetchone()
                if r:
                    proponi(term, tipo_di(term), w, r["doc"])
        radice_w = w[:-2] if len(w) >= 7 else w[:-1] if len(w) >= 5 else w
        tetto = 2 if len(w) >= 8 else 1
        for term, brani in vicine.items():
            if term.startswith(radice_w) and len(term) <= len(w) + 5:
                proponi(term, "radice", w, brani)
            elif len(w) >= 5 and _distanza(w, term, tetto) <= tetto:
                proponi(term, "simile", w, brani)
    # le più frequenti nell'archivio, poi i file veri, nella cartella se c'è
    candidate = sorted(trovate.items(), key=lambda x: (ORDINE.index(x[1][0]), -x[1][2]))[:massimo * 2]
    fuori = []
    for forma, (tipo, da, _) in candidate:
        n = _file(c, forma, radice)
        if n:
            fuori.append({"forma": forma, "file": n, "perche": PERCHE[tipo], "tipo": tipo, "da": da})
    fuori.sort(key=lambda x: (ORDINE.index(x["tipo"]), -x["file"]))
    return fuori[:massimo]


def dal_modello(nome, parole, radice=None):
    """Le forme in altre lingue, chieste al modello locale e controllate sull'archivio.
    Restituisce (proposte che ci sono, proposte che non ci sono, modello usato)."""
    import requests
    modello = biblioteca._modello_per_riassunti()
    if not modello:
        raise RuntimeError("Non c'è un modello di Ollama per scrivere: installane uno, per "
                           "esempio con «ollama pull qwen3:8b».")
    # Una lista libera, riga per riga, il modello piccolo la trasforma in una
    # cantilena («honor, honor, honor…» per cinquecento righe): diviso per
    # lingua, in JSON e con la penalità sulle ripetizioni risponde in mezzo minuto.
    prompt = (f"Sei l'assistente di uno storico che costruisce un tesauro. Tema: «{nome}» "
              f"(parole già note: {', '.join(parole[:12])}).\n"
              "Per ogni lingua dai da 3 a 6 parole o brevi espressioni diverse che esprimono questo "
              "tema nelle fonti storiche e negli studi: sinonimi, forme singolari e plurali, grafie "
              "antiche, concetti vicini. Nessuna ripetizione.\n"
              "Rispondi solo con un oggetto JSON con queste chiavi: italiano, latino, croato, "
              "sloveno, tedesco, inglese, francese; ogni valore è una lista di stringhe.")
    r = requests.post(f"{impostazioni.ollama()}/api/generate", timeout=300, json={
        "model": modello, "prompt": prompt, "stream": False, "think": False, "format": "json",
        "options": {"temperature": 0.3, "num_predict": 450, "repeat_penalty": 1.3}})
    testo = r.json().get("response") or ""
    try:
        risposta = json.loads(testo)
    except ValueError:
        risposta = {}
    grezze = []
    for valore in (risposta.values() if isinstance(risposta, dict) else []):
        grezze += valore if isinstance(valore, list) else [valore]
    proposte = []
    for pezzo in grezze:
        pezzo = re.sub(r"\(.*?\)", "", str(pezzo)).strip().strip('"«»').strip()
        if 2 < len(pezzo) <= 60 and len(pezzo.split()) <= 4:
            proposte.append(pezzo)
    gia = {tesauro.piatto(p) for p in parole}
    c = archivio.apri()
    ci_sono, non_ci_sono, viste = [], [], set()
    for p in proposte:
        chiave = tesauro.piatto(p)
        if chiave in gia or chiave in viste:
            continue
        viste.add(chiave)
        n = _file(c, p, radice)
        if n:
            ci_sono.append({"forma": p, "file": n, "perche": PERCHE["modello"], "tipo": "modello"})
        else:
            non_ci_sono.append(p)
    ci_sono.sort(key=lambda x: -x["file"])
    return ci_sono, non_ci_sono, modello
