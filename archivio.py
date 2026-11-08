#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'archivio: indicizzazione e ricerca.

Una base SQLite con tre tavole utili:

  documenti   una riga per documento logico, con percorso, formato, pagine,
              impronta del contenuto (per riconoscere le copie) e stato
  frammenti   il testo spezzato in brani di circa mille caratteri, ciascuno
              con il numero di pagina da cui viene: serve a citare
  ricerca     indice FTS5 sui frammenti

I vettori per la ricerca semantica stanno in una tavola a parte, perché si
calcolano dopo e possono mancare senza che il resto smetta di funzionare.
"""
import hashlib
import json
import os
import re
import sqlite3
import time
import unicodedata

import estrattori
import tesauro

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "dati")
DB = os.path.join(DATI, "archivio.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documenti (
    id INTEGER PRIMARY KEY,
    percorso TEXT UNIQUE,
    nome TEXT,
    cartella TEXT,
    radice TEXT,
    estensione TEXT,
    byte INTEGER,
    modificato REAL,
    pagine INTEGER,
    parole INTEGER,
    metodo TEXT,          -- pdf, docx, ocr, immagini ricomposte…
    impronta TEXT,        -- md5 del testo: raggruppa le copie
    stato TEXT,           -- indicizzato | da_ocr | vuoto | errore
    indicizzato_il REAL
);
CREATE INDEX IF NOT EXISTS i_doc_impronta ON documenti(impronta);
CREATE INDEX IF NOT EXISTS i_doc_stato ON documenti(stato);

CREATE TABLE IF NOT EXISTS frammenti (
    id INTEGER PRIMARY KEY,
    documento INTEGER REFERENCES documenti(id) ON DELETE CASCADE,
    pagina INTEGER,
    ordine INTEGER,
    testo TEXT
);
CREATE INDEX IF NOT EXISTS i_fr_doc ON frammenti(documento);

CREATE VIRTUAL TABLE IF NOT EXISTS ricerca USING fts5(
    testo, piatto, documento UNINDEXED, frammento UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS lavori (
    id INTEGER PRIMARY KEY,
    tipo TEXT,            -- indicizza | vettori | ocr
    cartella TEXT,
    nome TEXT,
    stato TEXT,           -- in_corso | finito | errore | fermato
    totale INTEGER DEFAULT 0,
    fatti INTEGER DEFAULT 0,
    messaggio TEXT,
    diario TEXT,
    iniziato REAL,
    finito REAL
);

CREATE TABLE IF NOT EXISTS vettori (
    frammento INTEGER PRIMARY KEY REFERENCES frammenti(id) ON DELETE CASCADE,
    modello TEXT,
    v BLOB
);

-- Le cartelle indicizzate, con il loro percorso: senza, non si saprebbe più
-- dove andare a guardare per aggiornarle.
CREATE TABLE IF NOT EXISTS radici (
    nome TEXT PRIMARY KEY,
    percorso TEXT,
    aggiunta_il REAL,
    aggiornata_il REAL
);
CREATE INDEX IF NOT EXISTS i_doc_radice ON documenti(radice);
"""

MISURA_FRAMMENTO = 2400
SOVRAPPOSIZIONE = 200
RX_PAGINA = re.compile(r"\[\[pagina (\d+)\]\]")


def piatto(s):
    s = unicodedata.normalize("NFKD", s.replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def apri():
    os.makedirs(DATI, exist_ok=True)
    # mezzo minuto di pazienza, non i cinque secondi di serie: mentre un lavoro
    # salva un libro intero, chi vuole scrivere deve aspettare il suo turno
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def spezza(testo):
    """(pagina, testo) per ogni frammento, conservando il numero di pagina."""
    pezzi, pagina = [], 1
    posizione = 0
    while posizione < len(testo):
        fine = min(len(testo), posizione + MISURA_FRAMMENTO)
        if fine < len(testo):
            taglio = testo.rfind(" ", posizione + MISURA_FRAMMENTO // 2, fine)
            if taglio > 0:
                fine = taglio
        pezzo = testo[posizione:fine]
        for m in RX_PAGINA.finditer(pezzo):
            pagina = int(m.group(1))
        pulito = RX_PAGINA.sub(" ", pezzo)
        pulito = re.sub(r"\[\[immagine [^\]]+\]\]", " ", pulito)
        pulito = re.sub(r"\s+", " ", pulito).strip()
        if len(pulito) > 40:
            pezzi.append((pagina, pulito))
        posizione = max(fine - SOVRAPPOSIZIONE, fine)
    return pezzi


def togli_documento(c, doc):
    """Toglie un documento con tutto quello che ne deriva: frammenti, indice, vettori.

    SQLite non cancella a cascata se non glielo si chiede, e l'indice di
    ricerca non ha legami con nessuno: togliere la sola riga del documento
    lascerebbe i suoi brani a galleggiare nell'indice, trovati e senza padre.
    """
    c.execute("DELETE FROM vettori WHERE frammento IN "
              "(SELECT id FROM frammenti WHERE documento=?)", (doc,))
    c.execute("DELETE FROM ricerca WHERE documento=?", (doc,))
    c.execute("DELETE FROM frammenti WHERE documento=?", (doc,))
    c.execute("DELETE FROM documenti WHERE id=?", (doc,))


def _salva(c, dati, testo):
    cur = c.cursor()
    vecchio = cur.execute("SELECT id FROM documenti WHERE percorso = ?",
                          (dati["percorso"],)).fetchone()
    if vecchio:
        togli_documento(c, vecchio["id"])
    cur.execute("""INSERT INTO documenti
        (percorso, nome, cartella, radice, estensione, byte, modificato, pagine,
         parole, metodo, impronta, stato, indicizzato_il)
        VALUES (:percorso,:nome,:cartella,:radice,:estensione,:byte,:modificato,
                :pagine,:parole,:metodo,:impronta,:stato,:indicizzato_il)""", dati)
    doc = cur.lastrowid
    for ordine, (pagina, pezzo) in enumerate(spezza(testo)):
        cur.execute("INSERT INTO frammenti (documento,pagina,ordine,testo) VALUES (?,?,?,?)",
                    (doc, pagina, ordine, pezzo))
        fr = cur.lastrowid
        cur.execute("INSERT INTO ricerca (testo,piatto,documento,frammento) VALUES (?,?,?,?)",
                    (pezzo, piatto(pezzo), doc, fr))
    c.commit()
    return doc


def _primo_pezzo(percorso, quanti=2 << 20):
    """md5 del primo pezzo di file: basta a distinguere due PDF diversi."""
    try:
        with open(percorso, "rb") as f:
            return hashlib.md5(f.read(quanti)).hexdigest()
    except OSError:
        return ""


def _gemello_gia_letto(c, percorso, byte, pagine):
    """Lo stesso PDF in due cartelle non si riconosce due volte.

    Le copie Scaffale le scopre dall'impronta, che pero' si calcola sul testo:
    finche' la scansione e' muta l'impronta non c'e', e la coda dell'OCR se le
    porta dietro tutte e due. Due copie di «La giustizia ai confini» sono 472
    pagine lette per niente, tre ore e mezza (trovato il 6 novembre 2026 su
    CondivisioneMD). Qui il gemello si riconosce prima di leggere: stesso nome,
    stesso peso, stesse pagine e stesso primo pezzo di file.
    """
    simili = c.execute(
        """SELECT id, percorso, parole, impronta FROM documenti
           WHERE nome=? AND byte=? AND pagine=? AND stato='indicizzato'
             AND metodo='ocr' AND percorso<>?""",
        (os.path.basename(percorso), byte, pagine, percorso)).fetchall()
    if not simili:
        return None
    mio = _primo_pezzo(percorso)
    if not mio:
        return None
    for s in simili:
        if mio == _primo_pezzo(s["percorso"]):
            return s
    return None


def _copia_dal_gemello(c, percorso, gemello):
    """Ricopia testo e frammenti del gemello invece di rileggere la scansione."""
    r = c.execute("SELECT id FROM documenti WHERE percorso=?", (percorso,)).fetchone()
    if not r:
        return False
    doc = r["id"]
    pezzi = c.execute("""SELECT pagina, ordine, testo FROM frammenti
                         WHERE documento=? ORDER BY ordine""",
                      (gemello["id"],)).fetchall()
    if not pezzi:
        return False
    c.execute("DELETE FROM vettori WHERE frammento IN "
              "(SELECT id FROM frammenti WHERE documento=?)", (doc,))
    c.execute("DELETE FROM frammenti WHERE documento=?", (doc,))
    c.execute("DELETE FROM ricerca WHERE documento=?", (doc,))
    for f in pezzi:
        cur = c.execute("INSERT INTO frammenti (documento,pagina,ordine,testo) "
                        "VALUES (?,?,?,?)", (doc, f["pagina"], f["ordine"], f["testo"]))
        c.execute("INSERT INTO ricerca (testo,piatto,documento,frammento) "
                  "VALUES (?,?,?,?)",
                  (f["testo"], piatto(f["testo"]), doc, cur.lastrowid))
    c.execute("""UPDATE documenti SET metodo='ocr', parole=?, impronta=?,
                 stato='indicizzato', indicizzato_il=? WHERE id=?""",
              (gemello["parole"], gemello["impronta"], time.time(), doc))
    c.commit()
    return True


def nuovo_lavoro(tipo, cartella="", nome=""):
    c = apri()
    cur = c.execute("""INSERT INTO lavori (tipo,cartella,nome,stato,messaggio,diario,iniziato)
                       VALUES (?,?,?,'in_corso','avvio…','',?)""",
                    (tipo, cartella, nome, time.time()))
    c.commit()
    return cur.lastrowid


def _resta_sveglio():
    """Finché un lavoro va avanti, Windows non mette il computer in sospensione.

    Una notte di vettori o di .md si fermava a metà: il computer dormiva, e il
    lavoro con lui. Ogni volta che un lavoro dice a che punto è, qui si azzera
    il conto alla rovescia della sospensione (come fanno i programmi video);
    quando i lavori finiscono, nessuno lo azzera più, e il computer torna a
    comportarsi come sempre. Non cambia nessuna impostazione di Windows."""
    if os.name != "nt":
        _resta_sveglio_linux()
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x00000001)   # ES_SYSTEM_REQUIRED
    except Exception:
        pass


_SVEGLIO = {"processo": None}


def _resta_sveglio_linux():
    """Su Linux lo stesso, con systemd-inhibit: un «blocco» della sospensione che
    dura cinque minuti e si rinnova finché il lavoro dice a che punto è. Finiti i
    lavori nessuno lo rinnova, e il computer torna come sempre. Senza systemd
    (o su macOS) non fa niente."""
    import shutil
    import subprocess
    p = _SVEGLIO["processo"]
    if p is not None and p.poll() is None:
        return
    if not shutil.which("systemd-inhibit"):
        return
    try:
        _SVEGLIO["processo"] = subprocess.Popen(
            ["systemd-inhibit", "--what=sleep:idle", "--who=Scaffale", "--why=un lavoro in corso",
             "--mode=block", "sleep", "300"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def aggiorna_lavoro(id_lavoro, **campi):
    if not id_lavoro:
        return
    _resta_sveglio()
    c = apri()
    if "riga" in campi:
        riga = campi.pop("riga")
        vecchio = c.execute("SELECT diario FROM lavori WHERE id=?", (id_lavoro,)).fetchone()
        diario = ((vecchio["diario"] or "") + riga + "\n")[-4000:]
        campi["diario"] = diario
        campi.setdefault("messaggio", riga[:160])
    if not campi:
        return
    sql = ", ".join(f"{k}=?" for k in campi)
    c.execute(f"UPDATE lavori SET {sql} WHERE id=?", (*campi.values(), id_lavoro))
    c.commit()


def lavoro(id_lavoro=None):
    c = apri()
    if id_lavoro:
        r = c.execute("SELECT * FROM lavori WHERE id=?", (id_lavoro,)).fetchone()
    else:
        r = c.execute("SELECT * FROM lavori ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return None
    d = dict(r)
    if d["stato"] == "in_corso" and d["id"] in _DA_FERMARE:
        d["stato"] = "da_fermare"        # il Ferma è arrivato, anche se non ancora scritto
    return d


def dimentica(radice):
    """Toglie dall'archivio una cartella indicizzata. I file sul disco non si toccano."""
    c = apri()
    docs = [r["id"] for r in c.execute("SELECT id FROM documenti WHERE radice=?", (radice,))]
    for d in docs:
        togli_documento(c, d)
    c.execute("DELETE FROM radici WHERE nome=?", (radice,))
    c.commit()
    return len(docs)


def registra_radice(nome, percorso):
    c = apri()
    adesso = time.time()
    c.execute("""INSERT INTO radici (nome, percorso, aggiunta_il, aggiornata_il)
                 VALUES (?,?,?,?)
                 ON CONFLICT(nome) DO UPDATE SET percorso=excluded.percorso,
                                                 aggiornata_il=excluded.aggiornata_il""",
              (nome, os.path.abspath(percorso), adesso, adesso))
    c.commit()


def radici():
    """Le cartelle indicizzate, con dove stanno e com'è messo il loro indice.

    Per quelle indicizzate prima che Scaffale tenesse nota del percorso, lo si
    ricostruisce: dall'ultimo lavoro di indicizzazione con quel nome, se c'è,
    altrimenti dalla parte di percorso che tutti i loro documenti hanno in
    comune. Una volta ricostruito, resta scritto.
    """
    c = apri()
    noti = {r["nome"]: dict(r) for r in c.execute("SELECT * FROM radici")}
    fuori = []
    for r in c.execute("""
            SELECT d.radice, COUNT(*) documenti, COALESCE(SUM(d.parole),0) parole,
                   SUM(CASE WHEN d.stato='da_ocr' THEN 1 ELSE 0 END) da_ocr,
                   MAX(d.indicizzato_il) ultimo
            FROM documenti d GROUP BY d.radice ORDER BY d.radice"""):
        voce = dict(r)
        nota = noti.get(r["radice"])
        if not nota:
            lavoro = c.execute("""SELECT cartella FROM lavori WHERE tipo='indicizza'
                                  AND nome=? AND cartella<>'' ORDER BY id DESC LIMIT 1""",
                               (r["radice"],)).fetchone()
            percorso = lavoro["cartella"] if lavoro else ""
            if not percorso:
                cartelle = [x["cartella"] for x in c.execute(
                    "SELECT DISTINCT cartella FROM documenti WHERE radice=?", (r["radice"],))]
                try:
                    percorso = os.path.commonpath(cartelle) if cartelle else ""
                except ValueError:
                    percorso = ""
            if percorso:
                c.execute("""INSERT OR IGNORE INTO radici (nome, percorso, aggiunta_il,
                             aggiornata_il) VALUES (?,?,?,?)""",
                          (r["radice"], percorso, r["ultimo"], r["ultimo"]))
                c.commit()
            nota = {"percorso": percorso, "aggiornata_il": r["ultimo"]}
        voce["percorso"] = nota["percorso"]
        voce["aggiornata_il"] = nota["aggiornata_il"] or r["ultimo"]
        voce["esiste"] = bool(nota["percorso"]) and os.path.isdir(nota["percorso"])
        fuori.append(voce)
    return fuori


def azzera():
    """Svuota l'indice e riparte da zero. Non cancella nessun documento sul disco."""
    c = apri()
    quanti = c.execute("SELECT COUNT(*) n FROM documenti").fetchone()["n"]
    for tavola in ("vettori", "ricerca", "frammenti", "documenti", "lavori"):
        c.execute(f"DELETE FROM {tavola}")
    c.commit()
    return quanti


def cartelle_indicizzate():
    c = apri()
    return [dict(r) for r in c.execute("""
        SELECT radice, COUNT(*) documenti, SUM(parole) parole,
               SUM(CASE WHEN stato='da_ocr' THEN 1 ELSE 0 END) da_ocr,
               MIN(cartella) esempio
        FROM documenti GROUP BY radice ORDER BY documenti DESC""")]


# le regole su che cosa saltare stanno in estrattori, perché valgono anche
# per le cartelle di immagini
da_saltare = estrattori.da_saltare


# ------------------------------------------------ fermare, misurare, stimare ---

class Fermato(Exception):
    """Qualcuno ha premuto «Ferma»: il lavoro si chiude al primo punto sicuro."""


def ferma(id_lavoro):
    """Chiede a un lavoro in corso di fermarsi.

    Non lo interrompe di colpo: il lavoro se ne accorge da sé al primo punto
    sicuro — tra un file e l'altro, tra una pagina e l'altra — e si chiude
    lasciando intatto tutto quello che ha già fatto. La volta dopo, Aggiorna
    riprende da lì.
    """
    # Prima il segnale in memoria: i lavori girano in questo stesso programma,
    # e lo vedono subito. Scriverlo nella base dati può dover aspettare —
    # mentre si salva un libro di mille pagine la base dati è occupata — e se
    # l'attesa scade il Ferma andava perso, mentre la pagina diceva «mi fermo».
    _DA_FERMARE.add(int(id_lavoro))
    try:
        c = apri()
        c.execute("UPDATE lavori SET stato='da_fermare' WHERE id=? AND stato='in_corso'",
                  (id_lavoro,))
        c.commit()
    except sqlite3.OperationalError:
        pass                     # lo scrive il lavoro stesso, quando si ferma


_DA_FERMARE = set()


def da_fermare(id_lavoro, c=None):
    if not id_lavoro:
        return False
    if int(id_lavoro) in _DA_FERMARE:
        return True
    r = (c or apri()).execute("SELECT stato FROM lavori WHERE id=?", (id_lavoro,)).fetchone()
    return bool(r) and r["stato"] == "da_fermare"


FILE_VELOCITA = os.path.join(DATI, "velocita.json")
# secondi per leggere un PDF che ha già il testo, un file di altro formato, e
# per riconoscere una pagina scansionata in nove lingue: misurati su un
# portatile senza scheda grafica. Un PDF, che spesso è un libro intero, costa
# cinquanta volte un file di testo: una media sola sbaglierebbe sempre, in un
# senso o nell'altro. Dopo il primo lavoro valgono le misure di questo computer.
VELOCITA_DI_BASE = {"pdf": 1.34, "testo": 0.024, "ocr": 2.4,
                    "riassunto": 133,      # secondi per un riassunto con qwen3:8b, senza scheda grafica
                    "temi_modello": 0.044,  # secondi per carattere del profilo che il modello legge
                    # secondi per carattere dei brani di una domanda: stimati dal riassunto
                    # (6000 caratteri in 133 s) più una risposta più lunga; poi vale la misura
                    "domanda": 0.03,
                    # secondi per rileggere con GLM-OCR una riga con numeri (misurati: 3–9)
                    "verifica_riga": 4.0,
                    # secondi per una domanda del ricercatore (piano, 14 brani letti, rapporto)
                    "ricercatore": 1500.0}


def velocita():
    try:
        with open(FILE_VELOCITA, encoding="utf-8") as f:
            misurate = json.load(f)
    except (OSError, ValueError):
        misurate = {}
    return {k: float(misurate.get(k) or v) for k, v in VELOCITA_DI_BASE.items()}


def _ricorda(chiave, secondi, quanti, minimo):
    """Tiene la velocità misurata, se la misura è abbastanza ampia da valere."""
    if quanti < minimo:
        return
    d = velocita()
    d[chiave] = round(secondi / quanti, 3)
    try:
        with open(FILE_VELOCITA, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except OSError:
        pass


def _elenca(cartella):
    """Tutti i documenti sotto la cartella, sottocartelle comprese; e le
    sottocartelle che non si sono potute aprire."""
    elenco, illeggibili = [], []
    for root, sotto, file in os.walk(cartella, onerror=lambda e: illeggibili.append(
            os.path.normcase(os.path.abspath(getattr(e, "filename", "") or "")))):
        sotto[:] = [d for d in sotto if not da_saltare(root, d)]
        for f in sorted(file):
            if f.lower().endswith(estrattori.DOCUMENTI):
                elenco.append(os.path.join(root, f))
    return elenco, illeggibili


def _noti(c):
    """Quello che l'indice sa già di ogni file: dimensione, data, com'è andata."""
    return {r["percorso"]: (r["byte"], r["modificato"], r["stato"]) for r in c.execute(
        "SELECT percorso, byte, modificato, stato FROM documenti")}


def _confronto(prima, st):
    """Che cosa fare di un file: nuovo, cambiato, invariato, o ancora in attesa
    di essere riconosciuto. Due secondi di tolleranza sulla data, perché certi
    dischi e OneDrive la arrotondano."""
    if not prima:
        return "nuovo"
    byte, modificato, stato = prima
    uguale = (byte == st.st_size and modificato is not None
              and abs(modificato - st.st_mtime) < 2)
    if not uguale:
        return "cambiato"
    if stato == "indicizzato":
        return "invariato"
    if stato == "da_ocr":
        return "in_attesa"
    # un file rimasto vuoto si rilegge: nel frattempo può essere arrivato il
    # lettore del suo formato
    return "da_rileggere"


def _sparite(c, cartella, illeggibili):
    """I documenti dell'indice, sotto questa cartella, che sul disco non ci sono
    più. Non basta non averli incontrati: una sottocartella chiusa o non ancora
    sincronizzata non va scambiata per un file cancellato."""
    base = os.path.normcase(os.path.abspath(cartella)).rstrip("\\/") + os.sep
    fuori = []
    for r in c.execute("SELECT id, percorso FROM documenti"):
        p = os.path.normcase(os.path.abspath(r["percorso"]))
        if not p.startswith(base):
            continue
        if any(p.startswith(x.rstrip("\\/") + os.sep) for x in illeggibili if x):
            continue
        if r["percorso"].endswith("[ricomposto].txt"):
            sparito = not os.path.isdir(os.path.dirname(r["percorso"]))
        else:
            sparito = not os.path.exists(r["percorso"])
        if sparito:
            fuori.append((r["id"], r["percorso"]))
    return fuori


def _nome_di(c, cartella):
    """Il nome che una cartella già indicizzata ha nell'archivio, se ce l'ha."""
    norma = lambda p: os.path.normcase(os.path.abspath(p)).rstrip("\\/")
    for r in c.execute("SELECT nome, percorso FROM radici"):
        if r["percorso"] and norma(r["percorso"]) == norma(cartella):
            return r["nome"]
    return None


def anteprima(cartella, campione=40):
    """Prima di cominciare: quanti file, di che tipo, che cosa cambia, quanto ci vuole.

    Serve a decidere prima, non a scoprirlo dopo tre ore. Si contano i file
    e si confrontano con l'indice, che è rapido. Quante siano le scansioni da
    riconoscere, invece, si sa solo aprendo i PDF: se ne apre un campione e
    si stima il resto, dicendolo.
    """
    import collections
    import random
    if not os.path.isdir(cartella):
        return {"esiste": False, "percorso": cartella}
    c = apri()
    noti = _noti(c)
    elenco, illeggibili = _elenca(cartella)
    per_tipo, conti = collections.Counter(), collections.Counter()
    byte, da_leggere, pdf_da_leggere, in_attesa = 0, [], [], []
    for p in elenco:
        try:
            st = os.stat(p)
        except OSError:
            continue
        e = os.path.splitext(p)[1].lower()
        per_tipo[e] += 1
        byte += st.st_size
        esito = _confronto(noti.get(p), st)
        conti[esito] += 1
        if esito in ("nuovo", "cambiato", "da_rileggere"):
            da_leggere.append(p)
            if e == ".pdf":
                pdf_da_leggere.append(p)
        elif esito == "in_attesa":
            in_attesa.append(p)

    # le scansioni fra i PDF da leggere: se ne apre un campione
    aperti, scansioni, pagine_scansioni = 0, 0, []
    for p in random.Random(7).sample(pdf_da_leggere, min(campione, len(pdf_da_leggere))):
        try:
            d = estrattori._apri(p)
            n = d.page_count
            testo = "".join(d[i].get_text() for i in range(min(3, n)))
            d.close()
        except Exception:
            continue
        aperti += 1
        # la stessa regola di leggi_testo: meno di venti caratteri a pagina
        if len(testo.replace(" ", "").replace("\n", "")) < 20 * max(min(3, n), 1):
            scansioni += 1
            pagine_scansioni.append(n)
    scansioni_nuove = round(scansioni / aperti * len(pdf_da_leggere)) if aperti else 0
    media = sum(pagine_scansioni) / len(pagine_scansioni) if pagine_scansioni else 0
    pagine_nuove = round(scansioni_nuove * media)

    pagine_attesa = 0
    for p in in_attesa:
        r = c.execute("SELECT pagine FROM documenti WHERE percorso=?", (p,)).fetchone()
        pagine_attesa += (r["pagine"] or 0) if r else 0
    immagini = sum(len(imm) for cart, imm in estrattori.gruppi_di_immagini(cartella)
                   if os.path.join(cart, "[ricomposto].txt") not in noti)
    tolti = len(_sparite(c, cartella, illeggibili))

    v = velocita()
    pagine_ocr = pagine_nuove + pagine_attesa + immagini
    return {
        "esiste": True, "percorso": cartella, "nome": _nome_di(c, cartella),
        "totale": sum(per_tipo.values()), "byte": byte, "per_tipo": dict(per_tipo),
        "nuovi": conti["nuovo"], "cambiati": conti["cambiato"], "tolti": tolti,
        "invariati": conti["invariato"] + conti["in_attesa"] + conti["da_rileggere"],
        "da_leggere": len(da_leggere),
        "pdf_aperti": aperti, "pdf_da_leggere": len(pdf_da_leggere),
        "scansioni_nuove": scansioni_nuove, "scansioni_in_attesa": len(in_attesa),
        "immagini": immagini, "pagine_ocr": pagine_ocr,
        "secondi_testo": (len(pdf_da_leggere) * v["pdf"]
                          + (len(da_leggere) - len(pdf_da_leggere)) * v["testo"]),
        "secondi_ocr": pagine_ocr * v["ocr"],
        "illeggibili": [x for x in illeggibili if x],
    }


# ------------------------------------------------------------ indicizzare ---

def indicizza(cartella, radice=None, ocr=True, ricomponi=True, riprendi=True,
              avviso=print, id_lavoro=None):
    """Percorre una cartella e indicizza tutto quello che contiene.

    Rifatta sulla stessa cartella è un aggiornamento: i file nuovi si leggono,
    quelli cambiati — altra dimensione o altra data — si rileggono, quelli che
    non ci sono più escono dall'indice. Gli altri si lasciano come sono, OCR
    compreso: è il riconoscimento delle scansioni la parte lunga, e non va
    rifatta su un file che nessuno ha toccato.

    Si può fermare a metà (vedi `ferma`): quello che è fatto resta, e la volta
    dopo si riparte da lì.
    """
    c = apri()
    radice = (radice or _nome_di(c, cartella)
              or os.path.basename(cartella.rstrip("\\/")) or cartella)
    if not os.path.isdir(cartella):
        # una cartella che non si trova — un disco staccato, OneDrive non
        # sincronizzato — non è una cartella vuota: non si toglie niente
        avviso(f"Cartella non trovata: {cartella}. Non tocco l'indice.")
        aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                        messaggio=f"cartella non trovata: {cartella}"[:200])
        return 0
    registra_radice(radice, cartella)
    noti = _noti(c) if riprendi else {}
    smetti = lambda: da_fermare(id_lavoro, c)
    conti = {"nuovi": 0, "cambiati": 0, "invariati": 0, "tolti": 0}
    fatti = 0
    esito = lambda: (f"{conti['nuovi']} nuovi, {conti['cambiati']} cambiati, "
                     f"{conti['tolti']} tolti, {conti['invariati']} invariati")
    try:
        # 1) i documenti
        elenco, illeggibili = _elenca(cartella)
        avviso(f"Documenti trovati: {len(elenco)}")
        aggiorna_lavoro(id_lavoro, totale=len(elenco),
                        riga=f"documenti trovati: {len(elenco)}")
        da_ocr = []
        tempi = {"pdf": [0.0, 0], "testo": [0.0, 0]}
        for i, p in enumerate(elenco, 1):
            if smetti():
                raise Fermato
            if i % 25 == 0:
                avviso(f"  {i}/{len(elenco)}")
                aggiorna_lavoro(id_lavoro, fatti=i, messaggio=f"lettura {i}/{len(elenco)}")
            try:
                st = os.stat(p)
            except OSError:
                continue
            cosa = _confronto(noti.get(p), st) if riprendi else "nuovo"
            if cosa == "invariato":
                conti["invariati"] += 1
                continue
            if cosa == "in_attesa":
                da_ocr.append(p)          # ancora da riconoscere, com'era
                conti["invariati"] += 1
                continue
            conti[{"nuovo": "nuovi", "cambiato": "cambiati"}.get(cosa, "invariati")] += 1
            t0 = time.time()
            testo, metodo, pagine = estrattori.leggi_testo(p)
            tipo = "pdf" if p.lower().endswith(".pdf") else "testo"
            tempi[tipo][0] += time.time() - t0
            tempi[tipo][1] += 1
            stato = "indicizzato"
            if metodo == "scansione":
                stato = "da_ocr"
                da_ocr.append(p)
            elif len(testo.strip()) < (200 if tipo == "pdf" else 20):
                # un PDF con meno di così è una copertina o un numero di pagina;
                # un appunto di una riga invece è un appunto, e si deve trovare
                stato = "vuoto"
            dati = dict(percorso=p, nome=os.path.basename(p), cartella=os.path.dirname(p),
                        radice=radice, estensione=os.path.splitext(p)[1].lower(),
                        byte=st.st_size, modificato=st.st_mtime, pagine=pagine,
                        parole=len(testo.split()), metodo=metodo,
                        impronta=hashlib.md5(piatto(testo)[:30000].encode()).hexdigest()
                        if len(testo) > 200 else "",
                        stato=stato, indicizzato_il=time.time())
            _salva(c, dati, testo if stato == "indicizzato" else "")
            fatti += 1
        for tipo, (secondi, quanti) in tempi.items():
            _ricorda(tipo, secondi, quanti, 20)

        # 2) le cartelle di immagini che formano un testo unico
        gruppi = estrattori.gruppi_di_immagini(cartella) if ricomponi else []
        if gruppi:
            avviso(f"Cartelle di immagini da ricomporre: {len(gruppi)}")
        for cart, immagini in gruppi:
            finto = os.path.join(cart, "[ricomposto].txt")
            if finto in noti or not ocr:
                continue
            if smetti():
                raise Fermato
            avviso(f"  ricompongo {os.path.basename(cart)} ({len(immagini)} immagini)")
            try:
                testo, n = estrattori.ricomponi_gruppo(cart, immagini, smetti=smetti)
            except estrattori.Interrotto:
                raise Fermato
            dati = dict(percorso=finto, nome=f"[ricomposto] {os.path.basename(cart)}",
                        cartella=cart, radice=radice, estensione=".immagini",
                        byte=sum(os.path.getsize(os.path.join(cart, x)) for x in immagini),
                        modificato=time.time(), pagine=n, parole=len(testo.split()),
                        metodo="immagini ricomposte",
                        impronta=hashlib.md5(piatto(testo)[:30000].encode()).hexdigest(),
                        stato="indicizzato", indicizzato_il=time.time())
            _salva(c, dati, testo)
            fatti += 1

        # 2bis) quello che dalla cartella è sparito esce dall'indice
        if riprendi:
            for doc, _ in _sparite(c, cartella, illeggibili):
                togli_documento(c, doc)
                conti["tolti"] += 1
            c.commit()
            if conti["tolti"]:
                avviso(f"Tolti dall'indice {conti['tolti']} file che non ci sono più.")

        # 3) l'OCR delle scansioni mute
        if ocr and da_ocr:
            avviso(f"Scansioni da riconoscere: {len(da_ocr)}")
            aggiorna_lavoro(id_lavoro, totale=len(da_ocr), fatti=0,
                            riga=f"scansioni da riconoscere: {len(da_ocr)}")
            t_ocr, pagine_ocr = 0.0, 0
            for j, p in enumerate(da_ocr, 1):
                if smetti():
                    raise Fermato
                avviso(f"  OCR {j}/{len(da_ocr)}: {os.path.basename(p)[:60]}")
                # la barra conta i documenti finiti, non quello appena cominciato:
                # un libro scansionato di trecento pagine sono dieci minuti
                aggiorna_lavoro(id_lavoro, fatti=j - 1,
                                messaggio=f"OCR {j}/{len(da_ocr)}: {os.path.basename(p)[:60]}")
                suo = c.execute("SELECT byte, pagine FROM documenti WHERE percorso=?",
                                (p,)).fetchone()
                gemello = (_gemello_gia_letto(c, p, suo["byte"], suo["pagine"])
                           if suo else None)
                if gemello and _copia_dal_gemello(c, p, gemello):
                    dove = os.path.basename(os.path.dirname(gemello["percorso"]))
                    avviso(f"    e' la stessa scansione che sta in «{dove}»: "
                           "ricopiato il testo invece di rileggerlo")
                    continue
                t0 = time.time()
                try:
                    testo, n = estrattori.ocr_pdf(p, smetti=smetti)
                except estrattori.Interrotto:
                    raise Fermato      # il documento a metà resta in attesa, intero
                except Exception as exc:
                    avviso(f"    errore {type(exc).__name__}")
                    continue
                if testo.count(estrattori.NON_LETTA) >= n > 0:
                    # nessuna pagina letta: Tesseract non c'e e il modello non
                    # ha risposto. Il documento resta «da_ocr», cosi la
                    # prossima indicizzazione ci riprova, invece di lasciare
                    # nell'indice una scansione muta data per fatta.
                    avviso("    nessuno ha letto le pagine: resta da riconoscere")
                    continue
                t_ocr += time.time() - t0
                pagine_ocr += n
                _ricorda("ocr", t_ocr, pagine_ocr, 3)
                c.execute("""UPDATE documenti SET metodo='ocr', parole=?, impronta=?,
                             stato='indicizzato', indicizzato_il=? WHERE percorso=?""",
                          (len(testo.split()),
                           hashlib.md5(piatto(testo)[:30000].encode()).hexdigest(),
                           time.time(), p))
                r = c.execute("SELECT id FROM documenti WHERE percorso=?", (p,)).fetchone()
                if r:
                    doc = r["id"]
                    c.execute("DELETE FROM vettori WHERE frammento IN "
                              "(SELECT id FROM frammenti WHERE documento=?)", (doc,))
                    c.execute("DELETE FROM frammenti WHERE documento=?", (doc,))
                    c.execute("DELETE FROM ricerca WHERE documento=?", (doc,))
                    for ordine, (pagina, pezzo) in enumerate(spezza(testo)):
                        cur = c.execute(
                            "INSERT INTO frammenti (documento,pagina,ordine,testo) VALUES (?,?,?,?)",
                            (doc, pagina, ordine, pezzo))
                        c.execute(
                            "INSERT INTO ricerca (testo,piatto,documento,frammento) VALUES (?,?,?,?)",
                            (pezzo, piatto(pezzo), doc, cur.lastrowid))
                    c.commit()
    except Fermato:
        c.commit()
        registra_radice(radice, cartella)
        detto = f"fermato a metà — fin qui: {esito()}"
        avviso(f"Fermato. Quello che è fatto resta; Aggiorna riprende da qui. ({esito()})")
        aggiorna_lavoro(id_lavoro, stato="fermato", finito=time.time(),
                        riga=detto, messaggio=detto)
        return fatti

    registra_radice(radice, cartella)
    avviso(f"Fatto: {esito()}.")
    aggiorna_lavoro(id_lavoro, stato="finito", finito=time.time(),
                    riga=f"finito: {esito()}", messaggio=esito())
    return fatti


# ---------------------------------------------------------------- ricerca ---

_NEL_GRUPPO = """ AND r.documento IN (SELECT d2.id FROM documenti d2 JOIN nei_gruppi n
                   ON n.percorso = d2.percorso WHERE n.gruppo = ?
                   AND n.come IN ('automatico', 'a mano'))"""


def _fts(espressione, limite, radice=None, gruppo=None):
    c = apri()
    solo = ""
    parametri = [espressione]
    if radice:
        solo = " AND r.documento IN (SELECT id FROM documenti WHERE radice = ?)"
        parametri.append(radice)
    if gruppo:
        # un gruppo della scheda di una cartella: un tema, un gruppo scoperto, una sottocartella
        solo += _NEL_GRUPPO
        parametri.append(int(gruppo))
    parametri.append(limite)
    # I segni che marcano la parola trovata devono essere segni che nel testo
    # non compaiono mai: i caporali no, perché le fonti li usano per conto loro
    # — «Nicopeia» sta scritto così nei libri — e non si distinguerebbe più il
    # richiamo di Scaffale dalla citazione dell'autore.
    sql = """SELECT r.frammento, r.documento,
                    snippet(ricerca, 0, char(2), char(3), '…', 24) AS brano,
                    bm25(ricerca) AS punteggio
             FROM ricerca r WHERE ricerca MATCH ?""" + solo + """
             ORDER BY punteggio LIMIT ?"""
    try:
        return list(c.execute(sql, parametri))
    except sqlite3.OperationalError:
        return []


def espressione(query, modo="tesauro", radice=None):
    """La ricerca tradotta per l'indice.

    esatta: tutte le parole, come sono scritte (senza badare a maiuscole e accenti).
    tesauro: tutte le parole, ma ognuna anche con le sue varianti — «nicopeia»
    vale anche Nikopeja, Nikopoios, Madonna della Vittoria…
    In tutti e due i casi le parole devono stare nello stesso brano, cioè a una
    pagina circa l'una dall'altra.

    Si cerca in tutte e due le colonne. La colonna «piatto» serve alle grafie
    con i segni diacritici — Čoralić, Đurđica — ma è tutta minuscola e senza
    accenti: cercare anche nel testo originale fa sì che il ritaglio mostrato
    nei risultati sia quello vero, con la parola trovata al suo posto.
    """
    forma = lambda f: '{testo piatto}:"%s"' % f.replace('"', " ")
    if modo == "tesauro":
        # i tesauri in uso nella cartella dove si cerca; in tutte, quelli in uso da qualche parte
        import tesauri
        nuclei = tesauri.nuclei_per(radice or None)
        return " AND ".join("(" + " OR ".join(forma(f) for f in g) + ")"
                            for g in tesauro.gruppi(query, nuclei))
    parole = re.findall(r"\w+", query, re.UNICODE)
    return " AND ".join(forma(p) for p in parole) or forma(query)


def cerca(query, modo="tesauro", limite=60, radice=None, gruppo=None):
    """modo: esatta | tesauro. `radice` limita la ricerca a una cartella indicizzata,
    `gruppo` a uno dei suoi gruppi."""
    righe = _fts(espressione(query, modo, radice), limite * 4, radice, gruppo)
    return _componi(righe, limite)


def conta(query, modo="tesauro", radice=None, gruppo=None):
    """In quanti documenti c'è davvero, non quanti se ne mostrano.

    Le copie di uno stesso documento contano una volta sola, come nell'elenco
    dei risultati: altrimenti il totale prometterebbe documenti che poi, a
    chiedere di vederli, non ci sono.
    """
    c = apri()
    sql = """SELECT COUNT(DISTINCT CASE WHEN d.impronta <> '' THEN d.impronta
                                        ELSE 'doc' || d.id END) n
             FROM ricerca r JOIN documenti d ON d.id = r.documento
             WHERE ricerca MATCH ?"""
    parametri = [espressione(query, modo, radice)]
    if radice:
        sql += " AND d.radice = ?"
        parametri.append(radice)
    if gruppo:
        sql += _NEL_GRUPPO
        parametri.append(int(gruppo))
    try:
        return c.execute(sql, parametri).fetchone()["n"]
    except sqlite3.OperationalError:
        return 0


def documenti_di(radice):
    """Tutti i documenti di una cartella indicizzata, col loro primo brano."""
    c = apri()
    return [dict(r) for r in c.execute("""
        SELECT d.id, d.percorso, d.nome, d.cartella, d.estensione, d.pagine, d.parole,
               d.metodo, d.stato, d.byte, d.modificato, d.impronta,
               (SELECT MIN(f.id) FROM frammenti f WHERE f.documento = d.id) primo
        FROM documenti d WHERE d.radice = ? ORDER BY d.cartella, d.nome""", (radice,))]


def forme_nel_testo(testo, forme):
    """Come le forme cercate sono scritte davvero in un testo: «CESSI», «Cessi».

    La ricerca lavora su parole senza maiuscole e senza accenti; per ritrovarle
    in una pagina bisogna sapere com'erano scritte lì.
    """
    parole = [(m.group(0), piatto(m.group(0))) for m in re.finditer(r"\w+", testo, re.UNICODE)]
    trovate = []
    for f in {x for x in forme if x}:
        pezzi = f.split()
        n = len(pezzi)
        for i in range(len(parole) - n + 1):
            if [p for _, p in parole[i:i + n]] == pezzi:
                trovate.append(" ".join(o for o, _ in parole[i:i + n]))
    return sorted(set(trovate), key=len, reverse=True)


def _componi(righe, limite):
    """Un documento compare una volta sola, con il suo brano migliore.

    Le copie si contano sui documenti che condividono l'impronta, non sui
    frammenti: uno stesso libro ha centinaia di frammenti e ne uscirebbe
    «300 copie» invece di «3».
    """
    c = apri()
    visti_impronta, visti_doc = set(), set()
    risultati = []
    for r in righe:
        if r["documento"] in visti_doc:
            continue
        d = c.execute("""SELECT d.*, f.pagina, f.testo FROM documenti d
                         JOIN frammenti f ON f.id = ?
                         WHERE d.id = ?""", (r["frammento"], r["documento"])).fetchone()
        if not d:
            continue
        visti_doc.add(r["documento"])
        imp = d["impronta"]
        if imp and imp in visti_impronta:
            continue
        copie = 1
        if imp:
            visti_impronta.add(imp)
            copie = c.execute("SELECT COUNT(*) n FROM documenti WHERE impronta=?",
                              (imp,)).fetchone()["n"]
        voce = {
            "documento": d["id"], "frammento": r["frammento"],
            "nome": d["nome"], "percorso": d["percorso"],
            "radice": d["radice"], "pagina": d["pagina"], "metodo": d["metodo"],
            "pagine": d["pagine"], "parole": d["parole"],
            "brano": r["brano"] if "brano" in r.keys() else d["testo"][:400],
            "testo": d["testo"], "punteggio": r["punteggio"] if "punteggio" in r.keys() else 0,
            "copie": copie,
        }
        risultati.append(voce)
        if len(risultati) >= limite:
            break
    return risultati


def posizione(id_frammento):
    """(n, di_quanti): il posto del brano nel suo documento, contando da 1."""
    r = apri().execute("""SELECT f.ordine,
                                 (SELECT COUNT(*) FROM frammenti g WHERE g.documento = f.documento) n
                          FROM frammenti f WHERE f.id = ?""", (id_frammento,)).fetchone()
    return (r["ordine"] + 1, r["n"]) if r and r["ordine"] is not None else (None, None)


def frammento(id_frammento):
    """Un frammento con il suo documento e i due vicini.

    Serve a rispondere alla domanda che un risultato di ricerca lascia sempre
    aperta: da dove viene esattamente questo brano. Restituisce il testo intero
    del frammento — non il ritaglio — con quello che lo precede e lo segue, e
    la sua posizione fra tutti i frammenti dello stesso documento.
    """
    c = apri()
    f = c.execute("""SELECT f.*, d.nome, d.percorso, d.radice, d.estensione,
                            d.metodo, d.pagine, d.parole
                     FROM frammenti f JOIN documenti d ON d.id = f.documento
                     WHERE f.id = ?""", (id_frammento,)).fetchone()
    if not f:
        return None
    fratelli = [r["id"] for r in c.execute(
        "SELECT id FROM frammenti WHERE documento = ? ORDER BY id", (f["documento"],))]
    k = fratelli.index(f["id"]) if f["id"] in fratelli else 0
    vicino = lambda i: fratelli[i] if 0 <= i < len(fratelli) else None
    return {"f": dict(f), "quale": k + 1, "quanti": len(fratelli),
            "prima": vicino(k - 1), "dopo": vicino(k + 1)}


def statistiche():
    c = apri()
    s = {}
    s["documenti"] = c.execute("SELECT COUNT(*) n FROM documenti").fetchone()["n"]
    s["indicizzati"] = c.execute(
        "SELECT COUNT(*) n FROM documenti WHERE stato='indicizzato'").fetchone()["n"]
    s["da_ocr"] = c.execute(
        "SELECT COUNT(*) n FROM documenti WHERE stato='da_ocr'").fetchone()["n"]
    s["frammenti"] = c.execute("SELECT COUNT(*) n FROM frammenti").fetchone()["n"]
    s["vettori"] = c.execute("SELECT COUNT(*) n FROM vettori").fetchone()["n"]
    s["parole"] = c.execute("SELECT COALESCE(SUM(parole),0) n FROM documenti").fetchone()["n"]
    s["radici"] = [dict(r) for r in c.execute(
        "SELECT radice, COUNT(*) n FROM documenti GROUP BY radice ORDER BY n DESC")]
    s["copie"] = c.execute("""SELECT COUNT(*) n FROM (
        SELECT impronta FROM documenti WHERE impronta<>'' GROUP BY impronta
        HAVING COUNT(*)>1)""").fetchone()["n"]
    return s
