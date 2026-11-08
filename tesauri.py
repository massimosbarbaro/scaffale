#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I tesauri: uno per ricerca, scelti cartella per cartella.

Un tesauro è un elenco di temi; un tema è un nome e le parole che lo dicono,
in tutte le lingue e le grafie che servono — «duello: duello, duellum, duel,
dvoboj, Zweikampf». Scaffale li usa in due posti: nella ricerca in modo
«tesauro», dove una parola trova anche le altre del suo tema, e nella scheda di
una cartella, dove dice quali file toccano ciascun tema.

Ogni cartella usa i tesauri che le si danno: Paci medievali «Duello e onore»,
ZRS «Progetti», Economia «Venezia, Bisanzio, Adriatico» e «Prezzi». Una cartella
per cui non si è mai scelto usa quelli segnati «predefinito»: all'inizio solo
il tesauro di partenza, quello che c'era prima, scritto in tesauro.py.

Tutto sta nella base dati, accanto all'indice, e si cambia dalla pagina
«tesauri»: non serve toccare il codice.
"""
import json
import re
import time

import archivio
import tesauro

SCHEMA = """
CREATE TABLE IF NOT EXISTS tesauri (
    id INTEGER PRIMARY KEY,
    nome TEXT UNIQUE,
    descrizione TEXT,
    predefinito INTEGER DEFAULT 0,   -- lo usano le cartelle per cui non si è scelto
    di_partenza INTEGER DEFAULT 0,   -- quello che veniva da tesauro.py
    creato_il REAL
);
CREATE TABLE IF NOT EXISTS temi_tesauro (
    id INTEGER PRIMARY KEY,
    tesauro INTEGER,
    nome TEXT,
    forme TEXT,                      -- JSON: ["duello", "duellum", "dvoboj", …]
    creato_il REAL,
    UNIQUE (tesauro, nome)
);
CREATE TABLE IF NOT EXISTS tesauri_scelti (
    radice TEXT PRIMARY KEY,         -- la cartella ha scelto i suoi: vale tesauri_attivi
    scelto_il REAL
);
CREATE TABLE IF NOT EXISTS tesauri_attivi (
    radice TEXT,
    tesauro INTEGER,
    PRIMARY KEY (radice, tesauro)
);
"""

DI_PARTENZA = "Venezia, Bisanzio, Adriatico"


def apri():
    c = archivio.apri()
    c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM tesauri LIMIT 1").fetchone():
        # la prima volta: il tesauro che c'era, per non cambiare niente a chi lo usava
        tid = c.execute("""INSERT INTO tesauri (nome, descrizione, predefinito, di_partenza, creato_il)
                           VALUES (?,?,1,1,?)""",
                        (DI_PARTENZA, "Storia veneziana, bizantina e adriatica: icone, "
                         "greci, Levante, confraternite, quarta crociata, fonti veneziane.",
                         time.time())).lastrowid
        for nome, forme in tesauro.NUCLEI.items():
            c.execute("INSERT INTO temi_tesauro (tesauro, nome, forme, creato_il) VALUES (?,?,?,?)",
                      (tid, nome, json.dumps(forme, ensure_ascii=False), time.time()))
        c.commit()
    return c


def pulisci_forme(forme):
    """Le parole di un tema: una per voce, senza doppioni, senza virgolette."""
    if isinstance(forme, str):
        forme = re.split(r"[,;\n]", forme)
    fuori, viste = [], set()
    for f in forme:
        f = re.sub(r"\s+", " ", str(f)).strip().strip('"«»')
        if len(f) >= 2 and tesauro.piatto(f) not in viste:
            viste.add(tesauro.piatto(f))
            fuori.append(f[:80])
    return fuori[:80]


# ------------------------------------------------------------- leggere ---

def elenco():
    """Tutti i tesauri, con i loro temi e le cartelle che li usano."""
    c = apri()
    cartelle = [r["radice"] for r in archivio.radici()]
    fuori = []
    for t in c.execute("SELECT * FROM tesauri ORDER BY di_partenza DESC, nome").fetchall():
        t = dict(t)
        t["temi"] = [dict(r, forme=json.loads(r["forme"] or "[]")) for r in c.execute(
            "SELECT * FROM temi_tesauro WHERE tesauro=? ORDER BY nome", (t["id"],))]
        t["cartelle"] = [r for r in cartelle if t["id"] in attivi(r, c)]
        fuori.append(t)
    return fuori


def tesauro_di(tid):
    r = apri().execute("SELECT * FROM tesauri WHERE id=?", (tid,)).fetchone()
    return dict(r) if r else None


def attivi(radice, c=None):
    """Gli id dei tesauri in uso in una cartella; senza cartella, in tutto l'archivio."""
    c = c or apri()
    if radice is None:
        ids = set()
        for r in archivio.radici():
            ids |= set(attivi(r["radice"], c))
        return sorted(ids) if ids else [r["id"] for r in c.execute(
            "SELECT id FROM tesauri WHERE predefinito=1")]
    if c.execute("SELECT 1 FROM tesauri_scelti WHERE radice=?", (radice,)).fetchone():
        return [r["tesauro"] for r in c.execute(
            "SELECT tesauro FROM tesauri_attivi WHERE radice=? ORDER BY tesauro", (radice,))]
    return [r["id"] for r in c.execute("SELECT id FROM tesauri WHERE predefinito=1 ORDER BY id")]


def temi_per(radice):
    """I temi da usare in una cartella: [(id tesauro, nome tesauro, di partenza, tema, forme)]."""
    c = apri()
    ids = attivi(radice, c)
    if not ids:
        return []
    segni = ",".join("?" * len(ids))
    return [(r["tid"], r["tnome"], bool(r["di_partenza"]), r["nome"], json.loads(r["forme"] or "[]"))
            for r in c.execute(f"""SELECT t.id tid, t.nome tnome, t.di_partenza, m.nome, m.forme
                                   FROM temi_tesauro m JOIN tesauri t ON t.id = m.tesauro
                                   WHERE t.id IN ({segni}) ORDER BY t.di_partenza DESC, t.nome, m.nome""",
                                ids)]


def nuclei_per(radice=None):
    """{tema: forme} dei tesauri in uso: quello che la ricerca per tesauro allarga.
    Due tesauri con un tema dallo stesso nome lo mettono insieme."""
    fuori = {}
    for _, _, _, nome, forme in temi_per(radice):
        fuori.setdefault(nome, [])
        fuori[nome] += [f for f in forme if f not in fuori[nome]]
    return fuori


def chiave_gruppo(tid, di_partenza, tema):
    """Il gruppo di un tema, nella scheda della cartella. Quelli del tesauro di
    partenza tengono la chiave di prima, così restano i ritocchi fatti a mano."""
    return f"tesauro:{tema}" if di_partenza else f"tesauro:{tid}:{tema}"


# ------------------------------------------------------------ cambiare ---

def nuovo(nome, descrizione=""):
    nome = (nome or "").strip()[:120]
    if not nome:
        raise ValueError("Il tesauro ha bisogno di un nome.")
    c = apri()
    if c.execute("SELECT 1 FROM tesauri WHERE nome=?", (nome,)).fetchone():
        raise ValueError(f"C'è già un tesauro che si chiama «{nome}».")
    tid = c.execute("INSERT INTO tesauri (nome, descrizione, creato_il) VALUES (?,?,?)",
                    (nome, (descrizione or "").strip()[:400], time.time())).lastrowid
    c.commit()
    return tid


def rinomina(tid, nome, descrizione=None):
    nome = (nome or "").strip()[:120]
    if not nome:
        raise ValueError("Il tesauro ha bisogno di un nome.")
    c = apri()
    if c.execute("SELECT 1 FROM tesauri WHERE nome=? AND id<>?", (nome, tid)).fetchone():
        raise ValueError(f"C'è già un tesauro che si chiama «{nome}».")
    c.execute("UPDATE tesauri SET nome=? WHERE id=?", (nome, tid))
    if descrizione is not None:
        c.execute("UPDATE tesauri SET descrizione=? WHERE id=?", (descrizione.strip()[:400], tid))
    c.commit()


def elimina(tid):
    """Toglie un tesauro, con i suoi temi. I file non si toccano; nelle cartelle
    che lo usavano, i suoi temi spariscono alla prossima analisi."""
    c = apri()
    t = c.execute("SELECT di_partenza FROM tesauri WHERE id=?", (tid,)).fetchone()
    if not t:
        raise ValueError("Non trovo questo tesauro.")
    if t["di_partenza"]:
        raise ValueError("Il tesauro di partenza non si elimina: se non ti serve, "
                         "toglilo dalle cartelle che lo usano.")
    c.execute("DELETE FROM temi_tesauro WHERE tesauro=?", (tid,))
    c.execute("DELETE FROM tesauri_attivi WHERE tesauro=?", (tid,))
    c.execute("DELETE FROM tesauri WHERE id=?", (tid,))
    c.commit()


def salva_tema(tid, nome, forme, id_tema=None):
    """Crea un tema, o ne cambia nome e parole. Restituisce l'id del tema."""
    nome = (nome or "").strip()[:120]
    forme = pulisci_forme(forme)
    if not nome:
        raise ValueError("Il tema ha bisogno di un nome.")
    if not forme:
        raise ValueError("Il tema ha bisogno di almeno una parola.")
    c = apri()
    if not c.execute("SELECT 1 FROM tesauri WHERE id=?", (tid,)).fetchone():
        raise ValueError("Non trovo questo tesauro.")
    doppio = c.execute("SELECT id FROM temi_tesauro WHERE tesauro=? AND nome=? AND id<>?",
                       (tid, nome, id_tema or 0)).fetchone()
    if doppio:
        raise ValueError(f"In questo tesauro c'è già un tema «{nome}».")
    if id_tema:
        c.execute("UPDATE temi_tesauro SET nome=?, forme=? WHERE id=? AND tesauro=?",
                  (nome, json.dumps(forme, ensure_ascii=False), id_tema, tid))
    else:
        id_tema = c.execute("INSERT INTO temi_tesauro (tesauro, nome, forme, creato_il) VALUES (?,?,?,?)",
                            (tid, nome, json.dumps(forme, ensure_ascii=False), time.time())).lastrowid
    c.commit()
    return id_tema


def tema(id_tema):
    r = apri().execute("SELECT * FROM temi_tesauro WHERE id=?", (id_tema,)).fetchone()
    return dict(r, forme=json.loads(r["forme"] or "[]")) if r else None


def elimina_tema(id_tema):
    c = apri()
    c.execute("DELETE FROM temi_tesauro WHERE id=?", (id_tema,))
    c.commit()


def imposta(radice, ids):
    """I tesauri che una cartella usa, da ora in poi: esattamente questi."""
    c = apri()
    validi = {r["id"] for r in c.execute("SELECT id FROM tesauri")}
    c.execute("DELETE FROM tesauri_attivi WHERE radice=?", (radice,))
    for tid in ids:
        if int(tid) in validi:
            c.execute("INSERT OR IGNORE INTO tesauri_attivi (radice, tesauro) VALUES (?,?)",
                      (radice, int(tid)))
    c.execute("INSERT OR REPLACE INTO tesauri_scelti (radice, scelto_il) VALUES (?,?)",
              (radice, time.time()))
    c.commit()


# la ricerca per tesauro, quando non sa in che cartella si cerca, usa tutti i
# tesauri in uso da qualche parte
tesauro.FONTE = lambda: nuclei_per(None)
