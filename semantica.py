#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ricerca semantica con embedding locali, via Ollama.

Il modello è **bge-m3**, già installato sulla macchina: è multilingue, e su un
archivio che mescola italiano, croato, latino, greco e inglese questo conta più
della finezza. Nulla esce dal computer.

La semantica non sostituisce il tesauro: lo completa. Il tesauro dice *perché*
un risultato è uscito ed è correggibile a mano; la semantica trova accostamenti
che nessuno aveva previsto. Nell'app girano insieme e i punteggi si sommano.
"""
import json
import os
import sqlite3
import struct
import time

import numpy as np
import requests

import archivio

import impostazioni

OLLAMA = impostazioni.ollama()
MODELLO = impostazioni.modello()
DIMENSIONE = None      # dedotta al primo uso


# Che cosa ha Ollama, ricordato per mezzo minuto. Una pagina lo chiede molte
# volte — una per ogni file a cui si può rifare il .md — e con Ollama spento
# ogni domanda aspettava 2 secondi di risposta: la scheda di una cartella ci
# metteva 20 secondi invece di uno.
_OLLAMA = {"quando": 0.0, "modelli": None}
RICORDA_SECONDI = 30


def _tags():
    import time
    if time.time() - _OLLAMA["quando"] < RICORDA_SECONDI:
        return _OLLAMA["modelli"]
    try:
        d = requests.get(f"{OLLAMA}/api/tags", timeout=4)
        d.raise_for_status()
        trovati = [m["name"] for m in d.json().get("models", [])]
    except Exception:
        trovati = None                 # Ollama spento, o non risponde
    _OLLAMA.update(quando=time.time(), modelli=trovati)
    return trovati


def acceso():
    return _tags() is not None


def modelli():
    return list(_tags() or [])


LOTTO = 64      # un frammento per volta dà 0,5/s, a lotti di 64 se ne fanno 9


def _normalizza(v):
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def vettori(testi, modello=MODELLO):
    """Un lotto di testi in una sola chiamata: è cinque volte più veloce."""
    r = requests.post(f"{OLLAMA}/api/embed",
                      json={"model": modello, "input": [t[:6000] for t in testi]},
                      timeout=600)
    r.raise_for_status()
    return [_normalizza(v) for v in r.json()["embeddings"]]


def vettore(testo, modello=MODELLO):
    return vettori([testo], modello)[0]


def _impacchetta(v):
    return struct.pack(f"{len(v)}f", *v.tolist())


def _spacchetta(b):
    n = len(b) // 4
    return np.array(struct.unpack(f"{n}f", b), dtype=np.float32)


# Di ogni gruppo di copie basta un esemplare: le copie darebbero vettori
# identici, e su un archivio vecchio sono un quarto dei frammenti.
_UN_ESEMPLARE = """(d.impronta = '' OR d.id = (SELECT MIN(d2.id) FROM documenti d2
                                            WHERE d2.impronta = d.impronta))"""


def mancanti_per_radice():
    """Per ogni cartella indicizzata: quanti frammenti hanno il vettore, quanti no.

    Serve a decidere che cosa calcolare prima. Su un computer senza scheda
    grafica i vettori di un archivio intero sono giorni di lavoro; quelli della
    sola cartella su cui si scrive, una notte.
    """
    c = archivio.apri()
    righe = c.execute(f"""
        SELECT d.radice, COUNT(*) tutti, COUNT(v.frammento) fatti
        FROM frammenti f JOIN documenti d ON d.id = f.documento
        LEFT JOIN vettori v ON v.frammento = f.id
        WHERE {_UN_ESEMPLARE}
        GROUP BY d.radice ORDER BY tutti - fatti DESC""").fetchall()
    return [{"radice": r["radice"], "tutti": r["tutti"], "fatti": r["fatti"],
             "mancano": r["tutti"] - r["fatti"]} for r in righe]


FILE_VELOCITA = os.path.join(archivio.DATI, "velocita_vettori.txt")


def velocita():
    """Frammenti al secondo, come misurati l'ultima volta su questo computer.

    Cambia moltissimo da una macchina all'altra: con una scheda grafica si
    va oltre i dieci al secondo, sul solo processore sotto uno. Una stima
    presa da un altro computer sbaglia di dieci volte — è già successo.
    """
    try:
        return max(float(open(FILE_VELOCITA).read().strip()), 0.05)
    except Exception:
        return 0.85        # misurata su un portatile senza scheda grafica


def calcola(limite=None, modello=MODELLO, avviso=print, id_lavoro=None, radice=None):
    """Calcola i vettori dei frammenti che non ne hanno ancora.

    Si prendono prima i soli numeri dei frammenti, e il testo si va a leggere un
    lotto per volta: su un archivio grande i frammenti sono centinaia di
    migliaia, e tenerli tutti in memoria vorrebbe dire quasi un gigabyte prima
    ancora di cominciare. `radice` limita il calcolo a una cartella.
    """
    if not acceso():
        avviso("Ollama non risponde: avvialo con «ollama serve».")
        return 0
    c = archivio.apri()
    sql = f"""SELECT f.id FROM frammenti f
              JOIN documenti d ON d.id = f.documento
              LEFT JOIN vettori v ON v.frammento = f.id
              WHERE v.frammento IS NULL AND {_UN_ESEMPLARE}"""
    parametri = []
    if radice:
        sql += " AND d.radice = ?"
        parametri.append(radice)
    sql += " ORDER BY f.id"
    if limite:
        sql += f" LIMIT {int(limite)}"
    ids = [r["id"] for r in c.execute(sql, parametri)]
    if radice:
        avviso(f"Cartella: {radice}")
    avviso(f"Frammenti da vettorializzare: {len(ids)}")
    archivio.aggiorna_lavoro(id_lavoro, totale=len(ids), fatti=0)
    fatti, t0 = 0, time.time()
    for inizio in range(0, len(ids), LOTTO):
        if archivio.da_fermare(id_lavoro, c):
            # i lotti già fatti sono salvati: la volta dopo si riparte da qui
            avviso(f"Fermato: {fatti} vettori calcolati, gli altri la prossima volta.")
            break
        lotto = ids[inizio:inizio + LOTTO]
        segni = ",".join("?" * len(lotto))
        righe = list(c.execute(
            f"SELECT id, testo FROM frammenti WHERE id IN ({segni})", lotto))
        try:
            vs = vettori([r["testo"] for r in righe], modello)
        except Exception as exc:
            avviso(f"  errore sul lotto {inizio}: {type(exc).__name__}")
            continue
        for r, v in zip(righe, vs):
            c.execute("INSERT OR REPLACE INTO vettori (frammento,modello,v) VALUES (?,?,?)",
                      (r["id"], modello, _impacchetta(v)))
            fatti += 1
        c.commit()
        if (inizio // LOTTO) % 5 == 0:
            al_secondo = fatti / max(time.time() - t0, 1)
            resta = (len(ids) - fatti) / max(al_secondo, 0.01) / 60
            quanto = f"{resta/60:.1f} ore" if resta > 90 else f"{resta:.0f} minuti"
            avviso(f"  {fatti}/{len(ids)} · {al_secondo:.2f}/s · restano {quanto}")
            archivio.aggiorna_lavoro(id_lavoro, fatti=fatti)
            _ricorda_velocita(fatti, t0)
    c.commit()
    avviso(f"Vettori calcolati: {fatti}")
    archivio.aggiorna_lavoro(id_lavoro, fatti=fatti)
    _ricorda_velocita(fatti, t0)
    return fatti


def _ricorda_velocita(fatti, t0):
    """Dopo qualche lotto la misura è attendibile: la si tiene per le stime."""
    if fatti < LOTTO * 3:
        return
    try:
        with open(FILE_VELOCITA, "w") as f:
            f.write(f"{fatti / max(time.time() - t0, 1):.3f}")
    except OSError:
        pass


def _matrice(c):
    righe = list(c.execute("SELECT frammento, v FROM vettori"))
    if not righe:
        return None, []
    M = np.vstack([_spacchetta(r["v"]) for r in righe])
    return M, [r["frammento"] for r in righe]


_CACHE = {"M": None, "ids": None, "quando": 0}


def cerca(query, limite=40, modello=MODELLO, radice=None, gruppo=None):
    if not acceso():
        return []
    c = archivio.apri()
    if _CACHE["M"] is None or time.time() - _CACHE["quando"] > 300:
        _CACHE["M"], _CACHE["ids"] = _matrice(c)
        _CACHE["quando"] = time.time()
    M, ids = _CACHE["M"], _CACHE["ids"]
    if M is None:
        return []
    q = vettore(query, modello)
    if q.shape[0] != M.shape[1]:
        return []
    punteggi = M @ q
    # dentro una sola cartella si scorrono più candidati, perché i migliori
    # dell'archivio intero possono stare quasi tutti altrove
    migliori = np.argsort(-punteggi)[:limite * (60 if radice or gruppo else 3)]
    dentro = None
    if gruppo:
        dentro = {r["percorso"] for r in c.execute(
            "SELECT percorso FROM nei_gruppi WHERE gruppo=? AND come IN ('automatico','a mano')",
            (int(gruppo),))}
    righe = []
    for k in migliori:
        fr = ids[int(k)]
        d = c.execute("""SELECT d.*, f.pagina, f.testo FROM frammenti f
                         JOIN documenti d ON d.id = f.documento WHERE f.id = ?""",
                      (fr,)).fetchone()
        if d and (not radice or d["radice"] == radice) and (dentro is None or d["percorso"] in dentro):
            righe.append((float(punteggi[int(k)]), fr, d))
            if len(righe) >= limite * 2:
                break
    return righe[:limite * 2]
