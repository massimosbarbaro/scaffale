#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La biblioteca: che cosa c'è in una cartella, come si raggruppa, di che cosa
parla ogni documento.

Tre modi di mettere insieme i documenti, e per ognuno si dice come:

  temi del tesauro   un documento entra in un tema se le parole di quel tema
                     compaiono in abbastanza suoi brani; si dice in quanti.
  gruppi scoperti    ogni documento ha le sue parole caratteristiche: frequenti
                     lì, rare nel resto dell'archivio. I documenti che ne
                     condividono una stanno insieme, e il gruppo prende il nome
                     da quella parola. Scaffale non sa che cosa significhi: è
                     una proposta, da tenere, rinominare o buttare.
  i tuoi gruppi      li crei tu, e ci metti e sposti i documenti come vuoi.

Nessun gruppo sposta i file sul disco: sono etichette dentro Scaffale. Quello
che si fa a mano — mettere un file in un gruppo, toglierlo da un tema — resta
anche quando si rifà l'analisi.

Il riassunto di un documento lo scrive un modello di Ollama che gira sul
computer, e solo quando lo si chiede: su un computer senza scheda grafica ci
vogliono un paio di minuti, e può sbagliare. Per capire subito di che cosa
parla un file ci sono le parole caratteristiche e l'inizio del testo, che non
inventano niente.
"""
import collections
import json
import math
import os
import re
import time

import archivio
import impostazioni
import tesauro

SCHEMA = """
CREATE TABLE IF NOT EXISTS gruppi (
    id INTEGER PRIMARY KEY,
    radice TEXT,
    chiave TEXT,          -- tesauro:greci | parola:muda | mio:<numero>
    nome TEXT,
    origine TEXT,         -- tesauro | scoperto | mio
    spiegazione TEXT,
    creato_il REAL,
    nascosto INTEGER DEFAULT 0,   -- un gruppo automatico eliminato: non si ripropone
    UNIQUE (radice, chiave)
);
CREATE TABLE IF NOT EXISTS nei_gruppi (
    gruppo INTEGER,
    percorso TEXT,
    come TEXT,            -- automatico | a mano | tolto a mano
    prova TEXT,           -- perché ci sta: «greci» in 45 brani su 206
    punteggio REAL,
    PRIMARY KEY (gruppo, percorso)
);
CREATE INDEX IF NOT EXISTS i_ng_percorso ON nei_gruppi(percorso);
CREATE TABLE IF NOT EXISTS schede (
    percorso TEXT PRIMARY KEY,
    parole TEXT,          -- JSON: [[parola, volte nel documento, brani dell'archivio che la hanno]]
    incipit TEXT,
    riassunto TEXT,
    modello TEXT,
    riassunto_il REAL,
    analizzata_il REAL
);
"""


def apri():
    c = archivio.apri()
    c.executescript(SCHEMA)
    colonne = {r["name"] for r in c.execute("PRAGMA table_info(gruppi)")}
    if "nascosto" not in colonne:
        c.execute("ALTER TABLE gruppi ADD COLUMN nascosto INTEGER DEFAULT 0")
        c.commit()
    if "forme" not in colonne:
        # le parole di un tema fatto da te, in JSON: ["AI", "intelligenza artificiale", …]
        c.execute("ALTER TABLE gruppi ADD COLUMN forme TEXT")
        c.commit()
    return c


def _ha_md(percorso):
    return os.path.exists(os.path.splitext(percorso)[0] + ".md")


# ---------------------------------------------------------------- totali ---

COME_LETTO = {
    "pdf": "testo del PDF", "ocr": "riconosciuto con l'OCR", "docx": "Word",
    "doc grezzo": "Word vecchio, lettura grezza", "testo": "testo semplice",
    "html": "pagina web", "epub": "libro elettronico", "rtf": "RTF",
    "rtf essenziale": "RTF", "immagini ricomposte": "immagini ricomposte e riconosciute",
    "xls": "foglio di calcolo", "xlsx": "foglio di calcolo", "csv": "tabella CSV",
    "mdb": "database Access", "mdb senza driver": "database Access",
    "pptx": "presentazione", "opendocument": "OpenDocument",
}


def come_letto(metodo, stato):
    """Come Scaffale ha avuto il testo di un documento, detto in chiaro."""
    if stato == "da_ocr":
        return "scansione, ancora da riconoscere"
    m = (metodo or "").split(" (")[0]
    if m.startswith("errore"):
        return "errore di lettura"
    if m == "formato ignoto":
        return "formato che non so leggere"
    if stato == "vuoto":
        return f"{COME_LETTO.get(m, m)}, ma senza testo utile"
    return COME_LETTO.get(m, m or "sconosciuto")


def _a_pezzi(lista, n=500):
    lista = list(lista)
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


def copie_di(c, impronte):
    """impronta -> quanti documenti, in tutto l'archivio, hanno lo stesso testo."""
    fuori = {}
    for pezzo in _a_pezzi({x for x in impronte if x}):
        segni = ",".join("?" * len(pezzo))
        for r in c.execute(f"SELECT impronta, COUNT(*) n FROM documenti WHERE impronta IN ({segni}) "
                           "GROUP BY impronta", pezzo):
            fuori[r["impronta"]] = r["n"]
    return fuori


def totali(radice):
    """I numeri di una cartella: quanti, di che tipo, come letti, .md, copie, vettori."""
    c = apri()
    docs = archivio.documenti_di(radice)
    copie = copie_di(c, [d["impronta"] for d in docs])
    con_copie = [d for d in docs if copie.get(d["impronta"], 1) > 1]
    pdf = [d for d in docs if d["estensione"] == ".pdf"]
    brani = c.execute("""SELECT COUNT(*) n FROM frammenti f JOIN documenti d ON d.id = f.documento
                         WHERE d.radice = ?""", (radice,)).fetchone()["n"]
    con_vettori = c.execute("""SELECT COUNT(*) n FROM vettori v JOIN frammenti f ON f.id = v.frammento
                               JOIN documenti d ON d.id = f.documento WHERE d.radice = ?""",
                            (radice,)).fetchone()["n"]
    ultima = c.execute("""SELECT MAX(s.analizzata_il) t FROM schede s JOIN documenti d
                          ON d.percorso = s.percorso WHERE d.radice = ?""", (radice,)).fetchone()["t"]
    con_riassunto = {r["percorso"] for r in c.execute(
        """SELECT s.percorso FROM schede s JOIN documenti d ON d.percorso = s.percorso
           WHERE d.radice = ? AND COALESCE(s.riassunto, '') <> ''""", (radice,))}
    # un PDF e il suo .md sono un documento solo: si conta una volta, e basta
    # il riassunto di uno dei due
    unita, compagno = _unita_da_riassumere(docs)
    riassunti = sum(1 for p in unita if p in con_riassunto or compagno.get(p) in con_riassunto)
    return {
        "documenti": len(docs), "byte": sum(d["byte"] or 0 for d in docs),
        "parole": sum(d["parole"] or 0 for d in docs),
        "per_tipo": collections.Counter(d["estensione"] or "?" for d in docs),
        "per_metodo": collections.Counter(come_letto(d["metodo"], d["stato"]) for d in docs),
        "pdf": len(pdf), "pdf_con_md": len(_coppie(docs)),
        "con_copie": len(con_copie), "gruppi_copie": len({d["impronta"] for d in con_copie}),
        "copie": copie, "brani": brani, "con_vettori": con_vettori, "analizzata_il": ultima,
        "riassunti": riassunti,
        "con_testo": len(unita),
    }


def _coppie(docs):
    import coppie
    return coppie.coppie(docs)


def _unita_da_riassumere(docs):
    """I documenti con testo, contando una volta sola il PDF e il suo .md: di una
    coppia resta quello da riassumere (coppie.da_riassumere_della_coppia).
    Restituisce (percorsi, {percorso: il suo compagno di coppia})."""
    import coppie
    per = {d["percorso"]: d for d in docs}
    fuori, compagno = set(), {}
    for pdf, md in coppie.coppie(docs).items():
        scelto = coppie.da_riassumere_della_coppia(per[pdf], md)
        altro = md if scelto == pdf else pdf
        fuori.add(altro)
        compagno[scelto] = altro
    unita = [d["percorso"] for d in docs if d["stato"] == "indicizzato" and d["percorso"] not in fuori]
    return unita, compagno


# ------------------------------------------------------------- l'analisi ---

RX_PAROLA = re.compile(r"[^\W\d_]{4,24}", re.UNICODE)

# Parole troppo comuni per dire qualcosa, nelle lingue dell'archivio. La rarità
# nell'archivio basterebbe quasi sempre a scartarle; la lista serve per le
# cartelle piccole, dove la statistica è povera.
PAROLE_VUOTE = set("""
della delle degli dello dalla dalle dagli dallo nella nelle negli nello sulla sulle sugli
sono come anche questo questa questi queste quello quella quelli quelle essere stato stata
stati fatto dopo prima ancora molto tutto tutti tutte sempre dove quando quale quali loro
pero perche cosi cioe ogni altri altre altro altra entro verso sotto sopra senza secondo
presso anno anni parte pagina pagine vedi ibid ibidem idem infatti quindi mentre tuttavia
allora poiche fino inoltre essa esso erano aveva avevano viene vengono proprio
that this with from which were have been their there they also into than only other such
these those what when where while would could should about after before between under
over being same very more most some many much will shall page pages vols note notes
koji koja koje kojem koju kojih nije biti bila bilo bili svih takoder prema kako kada
gdje izmedu preko iako samo nakon prije zbog toga tome tako vrlo vise moze mogu nisu
jedan jedna jedno njegov njegova njihov njihova godine godina
und der die das dem den des ein eine einer eines nicht auch sich wird werden wurde sind
mit von fur auf aus nach bei uber unter noch schon oder aber dass
dans pour avec sont mais plus cette comme nous vous leur leurs etre fait sans sous entre
quae quod sunt esse enim etiam autem atque cuius eius eorum quam quem quibus illa ille
illud ipse ipsa ipsum nobis vobis omnes omnia sive tamen item dicti dicta dictus dicto
contro veda vedasi deux siecles siecle history histoire historia storia storie storico storica
corpus racconto racconti documentario testimonianze testimonianza studio studi studies study
capitolo capitoli chapter chapters volume volumi edizione edizioni edition editions rivista
journal saggio saggi articolo articoli autore autori author authors opera opere lavoro lavori
testo testi documento documenti document documents fonte fonti source sources secolo secoli
century centuries university universita press istituto institute nota footnote presente
google digitized digitised chars score scanned copyright reserved download
""".split())


class Fermato(Exception):
    pass


def scrivi_col_modello(corpo, id_lavoro=None, avanza=None, ogni=25, server=None, openai=False):
    """Chiede al modello di Ollama e ne raccoglie la risposta a pezzi, con il
    Ferma che funziona sempre.

    Prima di scrivere la prima parola il modello legge tutto quello che gli si
    dà, e su un computer senza scheda grafica sono minuti in cui non arriva
    niente: chi aspettava la risposta riga per riga non vedeva il Ferma fino
    alla fine della lettura. Qui la risposta si legge in un filo a parte; il
    lavoro guarda il Ferma ogni secondo e, se c'è, chiude la connessione, e
    Ollama smette di lavorare. `avanza(n)` si chiama ogni `ogni` pezzi arrivati.
    Restituisce il testo; con il Ferma, solleva Fermato.

    Con `server` e `openai` la stessa macchina parla a un server compatibile
    OpenAI invece che a Ollama: serve per far rileggere le scansioni a un
    modello gia acceso sul computer, piu grande di quelli che Ollama tiene."""
    import http.client
    import queue
    import socket
    import threading
    import urllib.parse
    u = urllib.parse.urlparse(server or impostazioni.ollama())
    via = "/v1/chat/completions" if openai else "/api/generate"
    # una connessione tenuta in mano: chiuderla sblocca anche il filo che la
    # sta aspettando, cosa che una sessione di requests non fa
    conn = http.client.HTTPConnection(u.hostname or "localhost", u.port or 11434, timeout=3600)
    arrivi = queue.Queue()

    def leggi():
        try:
            conn.request("POST", via, body=json.dumps(dict(corpo, stream=True)),
                         headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            for riga in r:
                riga = riga.strip()
                if not riga:
                    continue
                if openai:
                    # un server compatibile OpenAI manda «data: {...}» a pezzi,
                    # e alla fine «data: [DONE]»
                    if not riga.startswith(b"data:"):
                        continue
                    riga = riga[5:].strip()
                    if riga == b"[DONE]":
                        break
                arrivi.put(("pezzo", json.loads(riga)))
            arrivi.put(("fine", None))
        except Exception as exc:
            arrivi.put(("errore", exc))

    def chiudi():
        try:
            if conn.sock:
                conn.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()

    threading.Thread(target=leggi, daemon=True).start()
    pezzi, arrivati = [], 0
    while True:
        if archivio.da_fermare(id_lavoro):
            chiudi()                     # la connessione chiusa ferma anche Ollama
            raise Fermato
        try:
            tipo, dato = arrivi.get(timeout=1)
        except queue.Empty:
            continue
        if tipo == "errore":
            raise dato
        if tipo == "fine":
            break
        if dato.get("error"):
            conn.close()
            raise RuntimeError(f"Ollama dice: {dato['error']}")
        if openai:
            scelta = (dato.get("choices") or [{}])[0]
            pezzo = scelta.get("delta") or scelta.get("message") or {}
            pezzi.append(pezzo.get("content") or "")
            finito = bool(scelta.get("finish_reason"))
        else:
            pezzi.append(dato.get("response") or "")
            finito = bool(dato.get("done"))
        arrivati += 1
        if avanza and arrivati % ogni == 0:
            avanza(arrivati)
        if finito:
            break
    conn.close()
    return "".join(pezzi)


def _parola_vera(w):
    """Scarta quello che una parola non è: «yyyyyyyy» viene dai vecchi .doc letti
    byte per byte, dove il carattere ÿ si ripete a centinaia; «aaaa» e «abab»
    da tabelle e scansioni sporche."""
    return len(set(w)) >= 3 and not re.search(r"(.)\1\1", w)


def _tronco(parola):
    """Le prime sei lettere di una parola lunga: quanto basta perché «cronache»
    e «cronachistica», «crusade» e «crusaders» contino come una sola."""
    return parola[:6] if len(parola) >= 7 else parola


def incipit(testo, quanto=420):
    """L'inizio del testo, saltando titoli, intestazioni e numeri di pagina."""
    t = re.sub(r"\[\[(pagina|immagine)[^\]]*\]\]", " ", testo or "")
    righe = [r.strip() for r in t.splitlines()]
    buone = [r for r in righe if len(r) >= 60]
    corpo = re.sub(r"\s+", " ", " ".join(buone or righe)).strip()
    if len(corpo) > quanto:
        corpo = corpo[:quanto].rsplit(" ", 1)[0] + "…"
    return corpo


def _rarita(c, parole):
    """In quanti brani di tutto l'archivio compare ciascuna parola."""
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.vocabolario "
              "USING fts5vocab(main, ricerca, 'row')")
    fuori = {}
    for pezzo in _a_pezzi(parole):
        segni = ",".join("?" * len(pezzo))
        fuori.update(c.execute(f"SELECT term, doc FROM temp.vocabolario WHERE term IN ({segni})",
                               pezzo).fetchall())
    return fuori


def _salva_gruppo(c, radice, chiave, nome, origine, spiegazione, membri):
    """Crea o rinfresca un gruppo automatico, senza toccare quello fatto a mano.

    Il nome non si cambia se c'è già: potrebbe averlo cambiato chi usa
    Scaffale. I file messi a mano restano; quelli tolti a mano non rientrano.
    """
    r = c.execute("SELECT id FROM gruppi WHERE radice=? AND chiave=?", (radice, chiave)).fetchone()
    if r:
        gid = r["id"]
        c.execute("UPDATE gruppi SET spiegazione=? WHERE id=?", (spiegazione, gid))
    else:
        gid = c.execute("""INSERT INTO gruppi (radice, chiave, nome, origine, spiegazione, creato_il)
                           VALUES (?,?,?,?,?,?)""",
                        (radice, chiave, nome, origine, spiegazione, time.time())).lastrowid
    c.execute("DELETE FROM nei_gruppi WHERE gruppo=? AND come='automatico'", (gid,))
    a_mano = {x["percorso"] for x in c.execute(
        "SELECT percorso FROM nei_gruppi WHERE gruppo=? AND come IN ('a mano','tolto a mano')", (gid,))}
    for percorso, (prova, punteggio) in membri.items():
        if percorso not in a_mano:
            c.execute("INSERT INTO nei_gruppi (gruppo, percorso, come, prova, punteggio) "
                      "VALUES (?,?,'automatico',?,?)", (gid, percorso, prova, punteggio))
    return gid


def _base_di(radice):
    return next((r["percorso"] for r in archivio.radici() if r["radice"] == radice), "") or ""


def _sottocartelle(radice, documenti):
    """Le sottocartelle di una cartella indicizzata, con i loro file.

    Restituisce (gruppi, prima_cartella): gruppi va da «ALDHI» o «ALDHI/Lab
    HumaDig» ai file che ci stanno — sottocartelle comprese — con la strada di
    ciascuno; prima_cartella dice di ogni documento in quale sottocartella di
    primo livello sta. Il secondo livello si mostra solo dove dice qualcosa in
    più del primo: almeno 3 file, non tutti quelli della cartella madre, e le
    otto più grandi al massimo.
    """
    base = _base_di(radice)
    livelli = collections.defaultdict(dict)
    prima_cartella = {}
    for d in documenti:
        try:
            rel = os.path.relpath(d["cartella"], base) if base else "."
        except ValueError:                  # un altro disco
            continue
        if rel == "." or rel.startswith(".."):
            continue
        parti = rel.split(os.sep)
        prima_cartella[d["id"]] = parti[0]
        livelli[parti[0]][d["percorso"]] = rel
        if len(parti) >= 2:
            livelli[parti[0] + "/" + parti[1]][d["percorso"]] = rel
    gruppi = {k: v for k, v in livelli.items() if "/" not in k and len(v) >= 2}
    for k1, v1 in list(gruppi.items()):
        figli = sorted(((k, v) for k, v in livelli.items()
                        if k.startswith(k1 + "/") and 3 <= len(v) < len(v1)),
                       key=lambda x: -len(x[1]))[:8]
        gruppi.update(figli)
    return gruppi, prima_cartella


def _e_sigla(forma):
    """«AI», «LLM», «OCR»: una sigla corta scritta in maiuscolo. Nell'indice
    diventa «ai», che in italiano è anche una preposizione: la si controlla sul
    testo vero, maiuscole comprese."""
    f = forma.strip()
    return 2 <= len(f) <= 5 and f.isalpha() and f.isupper()


def _brani_per_forma(c, radice, forme):
    """documento -> {forma: i brani in cui compare}, dentro la cartella."""
    fuori = collections.defaultdict(lambda: collections.defaultdict(set))
    for f in forme:
        f = f.strip()
        if not f:
            continue
        espr = '{testo piatto}:"%s"' % tesauro.piatto(f).replace('"', " ")
        try:
            if _e_sigla(f):
                rx = re.compile(r"(?<![^\W\d_])" + re.escape(f) + r"(?![^\W\d_])")
                righe = c.execute("""SELECT documento, frammento, testo FROM ricerca
                                     WHERE ricerca MATCH ? AND documento IN
                                     (SELECT id FROM documenti WHERE radice=?)""", (espr, radice))
                for r in righe:
                    if rx.search(r["testo"] or ""):
                        fuori[r["documento"]][f].add(r["frammento"])
            else:
                righe = c.execute("""SELECT documento, frammento FROM ricerca
                                     WHERE ricerca MATCH ? AND documento IN
                                     (SELECT id FROM documenti WHERE radice=?)""", (espr, radice))
                for r in righe:
                    fuori[r["documento"]][f].add(r["frammento"])
        except Exception:
            pass                            # una forma che l'indice non sa leggere
    return fuori


def _spiega_tema(forme):
    sigle = [f for f in forme if _e_sigla(f)]
    detto = (f"Tema fatto da te, con le parole «{'», «'.join(forme[:12])}». Ci stanno i "
             "documenti in cui compaiono in almeno 2 brani — in 1, per i documenti brevi, "
             "di 5 brani al massimo. Scaffale lo aggiorna da solo a ogni analisi; i file che "
             "metti o togli a mano restano come li hai lasciati.")
    if sigle:
        detto += (f" Le sigle in maiuscolo — {', '.join(sigle)} — valgono solo in maiuscolo: "
                  "«ai» minuscolo, in italiano, è una preposizione.")
    return detto


def _contesto(c, radice):
    docs = [d for d in archivio.documenti_di(radice) if d["primo"]]
    brani = dict(c.execute("""SELECT f.documento, COUNT(*) FROM frammenti f
                              JOIN documenti d ON d.id = f.documento
                              WHERE d.radice = ? GROUP BY f.documento""", (radice,)).fetchall())
    return {d["id"]: d for d in docs}, brani


def riempi_tema(gid, c=None, contesto=None):
    """Mette in un tema fatto da te i documenti che ne hanno le parole."""
    c = c or apri()
    g = c.execute("SELECT * FROM gruppi WHERE id=?", (gid,)).fetchone()
    if not g or not g["forme"]:
        return 0
    forme = json.loads(g["forme"])
    per_id, brani = contesto or _contesto(c, g["radice"])
    membri = {}
    for did, per_f in _brani_per_forma(c, g["radice"], forme).items():
        d = per_id.get(did)
        if not d:
            continue
        n, tot = len(set().union(*per_f.values())), brani.get(did, 1)
        if n >= 2 or (tot <= 5 and n >= 1):
            trovate = sorted(((f, len(s)) for f, s in per_f.items()), key=lambda x: -x[1])[:4]
            dette = ", ".join(f"«{f}» in {k}" for f, k in trovate)
            membri[d["percorso"]] = (f"{dette} — {n} brani su {tot}", n / tot)
    _salva_gruppo(c, g["radice"], g["chiave"], g["nome"], "mio", _spiega_tema(forme), membri)
    c.commit()
    return len(membri)


def _pulisci_forme(forme):
    fuori = []
    for f in forme:
        f = re.sub(r"\s+", " ", str(f)).strip().strip('"«»')
        if len(f) >= 2 and f.lower() not in {x.lower() for x in fuori}:
            fuori.append(f[:80])
    return fuori[:40]


def nuovo_tema(radice, nome, forme):
    """Un tema fatto da te: un nome e le parole che lo dicono. Si riempie subito."""
    forme = _pulisci_forme(forme)
    if not forme:
        raise ValueError("Il tema ha bisogno di almeno una parola.")
    c = apri()
    gid = c.execute("""INSERT INTO gruppi (radice, chiave, nome, origine, spiegazione, creato_il, forme)
                       VALUES (?,?,?,?,?,?,?)""",
                    (radice, f"tema:{time.time_ns()}", nome.strip()[:120], "mio",
                     _spiega_tema(forme), time.time(),
                     json.dumps(forme, ensure_ascii=False))).lastrowid
    c.commit()
    return gid, riempi_tema(gid, c)


def cambia_forme(gid, forme):
    forme = _pulisci_forme(forme)
    if not forme:
        raise ValueError("Il tema ha bisogno di almeno una parola.")
    c = apri()
    c.execute("UPDATE gruppi SET forme=? WHERE id=?", (json.dumps(forme, ensure_ascii=False), gid))
    c.commit()
    return riempi_tema(gid, c)


def membri_del_tema(c, radice, forme, per_id, brani):
    """I documenti che stanno in un tema, con il perché, senza salvare niente:
    le parole del tema in almeno 3 brani e nel 2% dei brani del documento; per
    i documenti brevi, di 5 brani al massimo, ne basta uno.
    Restituisce {percorso: (prova, punteggio)}."""
    membri_t = {}
    for did, per_f in _brani_per_forma(c, radice, forme).items():
        d = per_id.get(did)
        if not d:
            continue
        n, tot = len(set().union(*per_f.values())), brani.get(did, 1)
        if (n >= 3 and n >= 0.02 * tot) or (tot <= 5 and n >= 1):
            trovate = sorted(((f, len(x)) for f, x in per_f.items()), key=lambda x: -x[1])[:4]
            dette = ", ".join(f"«{f}» in {k}" for f, k in trovate) or "le parole del tema"
            membri_t[d["percorso"]] = (f"{dette} — {n} brani su {tot}", n / tot)
    return membri_t


def _un_tema(c, radice, voce, per_id, brani):
    """Il gruppo di un tema di un tesauro, in una cartella: i documenti in cui le
    sue parole compaiono in almeno 3 brani e nel 2% dei brani; per i documenti
    brevi, di 5 brani al massimo, ne basta uno. Ogni documento dice quali parole
    e quante volte: «dux in 93 brani» si capisce subito che non è il doge.
    Restituisce l'id del gruppo, o None se nessun documento ci sta."""
    import tesauri
    tid, tnome, di_partenza, nome, forme = voce
    chiave = tesauri.chiave_gruppo(tid, di_partenza, nome)
    membri_t = membri_del_tema(c, radice, forme, per_id, brani)
    if not membri_t:
        return None
    spiegazione = (f"Tema «{nome}» del tesauro «{tnome}». Ci stanno i documenti in cui le sue "
                   f"parole — {', '.join(forme[:8])}{'…' if len(forme) > 8 else ''} "
                   f"({len(forme)} forme in tutto) — compaiono in almeno 3 brani e in almeno il "
                   "2% dei brani del documento; per i documenti brevi, di 5 brani al massimo, ne "
                   "basta uno.")
    return _salva_gruppo(c, radice, chiave, nome, "tesauro", spiegazione, membri_t)


def _del_tesauro(chiave, ts):
    """Se il gruppo di un tema, dalla sua chiave, viene da questo tesauro."""
    if ts["di_partenza"]:
        return chiave.startswith("tesauro:") and not re.match(r"tesauro:\d+:", chiave)
    return chiave.startswith(f"tesauro:{ts['id']}:")


def rifai_tema(id_tesauro, solo=None):
    """Dopo aver cambiato, aggiunto o tolto un tema: si rifà subito in tutte le
    cartelle che usano il suo tesauro — solo quel tema, se si dice quale, così
    anche in una cartella grande è questione di secondi. Restituisce
    {cartella: {tema: quanti documenti}}."""
    import tesauri
    ts = tesauri.tesauro_di(id_tesauro)
    if not ts:
        return {}
    c = apri()
    tutti_t = [(ts["id"], ts["nome"], bool(ts["di_partenza"]), r["nome"], json.loads(r["forme"] or "[]"))
               for r in c.execute("SELECT nome, forme FROM temi_tesauro WHERE tesauro=? ORDER BY nome",
                                  (ts["id"],)).fetchall()]
    validi = {tesauri.chiave_gruppo(ts["id"], bool(ts["di_partenza"]), v[3]) for v in tutti_t}
    temi_t = [v for v in tutti_t if solo is None or v[3] in solo]
    calcolate = {tesauri.chiave_gruppo(ts["id"], bool(ts["di_partenza"]), v[3]) for v in temi_t}
    fuori = {}
    for r in archivio.radici():
        radice = r["radice"]
        if ts["id"] not in tesauri.attivi(radice, c):
            continue
        per_id, brani = _contesto(c, radice)
        vivi, conti = set(), {}
        for voce in temi_t:
            gid = _un_tema(c, radice, voce, per_id, brani)
            c.commit()                      # membri() legge con un'altra connessione
            conti[voce[3]] = len(membri(gid)) if gid else 0
            if gid:
                vivi.add(gid)
        # i temi tolti o rinominati, e quelli rimasti senza documenti
        for g in c.execute("SELECT id, chiave FROM gruppi WHERE radice=? AND origine='tesauro'",
                           (radice,)).fetchall():
            if _del_tesauro(g["chiave"], ts) and (g["chiave"] not in validi or
                                                  (g["chiave"] in calcolate and g["id"] not in vivi)):
                c.execute("DELETE FROM nei_gruppi WHERE gruppo=?", (g["id"],))
                c.execute("DELETE FROM gruppi WHERE id=?", (g["id"],))
        c.commit()
        fuori[radice] = conti
    return fuori


def togli_gruppi_tesauro(ts):
    """Un tesauro eliminato: i gruppi dei suoi temi escono da tutte le cartelle."""
    c = apri()
    for g in c.execute("SELECT id, chiave FROM gruppi WHERE origine='tesauro'").fetchall():
        if _del_tesauro(g["chiave"], ts):
            c.execute("DELETE FROM nei_gruppi WHERE gruppo=?", (g["id"],))
            c.execute("DELETE FROM gruppi WHERE id=?", (g["id"],))
    c.commit()


def aggiorna_temi(radice, avviso=print, id_lavoro=None):
    """Solo i temi dei tesauri, senza rileggere le parole di ogni documento:
    quello che serve dopo aver scelto altri tesauri per la cartella. In una
    cartella grande è questione di un minuto o due, non dei nove dell'analisi."""
    import tesauri
    c = apri()
    temi = tesauri.temi_per(radice)
    per_id, brani = _contesto(c, radice)
    archivio.aggiorna_lavoro(id_lavoro, totale=len(temi), fatti=0, riga=f"temi da rifare: {len(temi)}")
    rinfrescati = set()
    try:
        for j, voce in enumerate(temi, 1):
            if archivio.da_fermare(id_lavoro, c):
                raise Fermato
            gid = _un_tema(c, radice, voce, per_id, brani)
            if gid:
                rinfrescati.add(gid)
            c.commit()
            archivio.aggiorna_lavoro(id_lavoro, fatti=j, messaggio=f"temi dei tesauri: {voce[3]}")
        for g in c.execute("SELECT id FROM gruppi WHERE radice=? AND origine='tesauro'",
                           (radice,)).fetchall():
            if g["id"] not in rinfrescati:
                c.execute("DELETE FROM nei_gruppi WHERE gruppo=?", (g["id"],))
                c.execute("DELETE FROM gruppi WHERE id=?", (g["id"],))
        c.commit()
    except Fermato:
        c.commit()
        archivio.aggiorna_lavoro(id_lavoro, stato="fermato", finito=time.time(),
                                 messaggio="temi rifatti solo in parte: rifalli quando vuoi")
        return
    esito = f"{len(rinfrescati)} temi dei tesauri in «{radice}»"
    avviso(esito)
    archivio.aggiorna_lavoro(id_lavoro, stato="finito", finito=time.time(), messaggio=esito, riga=esito)


def analizza(radice, avviso=print, id_lavoro=None):
    """Legge le parole di tutti i documenti di una cartella e ne ricava le
    parole caratteristiche, l'inizio del testo, i temi e i gruppi scoperti."""
    c = apri()

    def avanza(**campi):
        # L'avanzamento si scrive con un'altra connessione: se questa tenesse
        # ancora aperta una scrittura, l'altra aspetterebbe per sempre. Si
        # chiude prima la propria.
        c.commit()
        archivio.aggiorna_lavoro(id_lavoro, **campi)

    docs = [d for d in archivio.documenti_di(radice) if d["primo"]]
    brani = dict(c.execute("""SELECT f.documento, COUNT(*) FROM frammenti f
                              JOIN documenti d ON d.id = f.documento
                              WHERE d.radice = ? GROUP BY f.documento""", (radice,)).fetchall())
    tutti_i_brani = c.execute("SELECT COUNT(*) n FROM frammenti").fetchone()["n"] or 1
    import tesauri
    temi = tesauri.temi_per(radice)
    passi = len(docs) + len(temi) + 2
    avanza( totale=passi, fatti=0,
                             riga=f"documenti da leggere: {len(docs)}")
    try:
        # 1) le parole di ogni documento: i primi sessanta brani bastano a dire di che cosa parla
        volte, inizio = {}, {}
        for i, d in enumerate(docs, 1):
            if archivio.da_fermare(id_lavoro, c):
                raise Fermato
            tf = collections.Counter()
            for k, r in enumerate(c.execute("SELECT testo FROM frammenti WHERE documento=? "
                                            "ORDER BY ordine LIMIT 60", (d["id"],)).fetchall()):
                if k == 0:
                    inizio[d["id"]] = r["testo"]
                tf.update(w for w in RX_PAROLA.findall(archivio.piatto(r["testo"]))
                          if w not in PAROLE_VUOTE and _parola_vera(w))
            volte[d["id"]] = tf
            if i % 50 == 0:
                avanza( fatti=i,
                                         messaggio=f"leggo le parole: {i}/{len(docs)}")

        # 2) le parole caratteristiche: frequenti nel documento, rare nell'archivio
        candidate = set()
        for tf in volte.values():
            candidate.update(w for w, n in tf.most_common(150) if n >= 2)
        avviso(f"Parole candidate: {len(candidate)}")
        rare = _rarita(c, candidate)
        caratteristiche = {}
        for d in docs:
            tf = volte[d["id"]]
            punti = [(w, n, rare.get(w, 1)) for w, n in tf.most_common(150) if n >= 2]
            punti.sort(key=lambda x: -x[1] * math.log(tutti_i_brani / (1 + x[2])))
            scelte = [p for p in punti if p[2] < tutti_i_brani * 0.05][:12]
            caratteristiche[d["id"]] = scelte
            c.execute("""INSERT INTO schede (percorso, parole, incipit, analizzata_il) VALUES (?,?,?,?)
                         ON CONFLICT(percorso) DO UPDATE SET parole=excluded.parole,
                         incipit=excluded.incipit, analizzata_il=excluded.analizzata_il""",
                      (d["percorso"], json.dumps(scelte, ensure_ascii=False),
                       incipit(inizio.get(d["id"], "")), time.time()))
        c.commit()
        avanza( fatti=len(docs) + 1,
                                 messaggio="parole caratteristiche fatte")

        rinfrescati = set()
        # 3) i temi dei tesauri in uso in questa cartella
        per_id = {d["id"]: d for d in docs}
        for j, voce in enumerate(temi, 1):
            if archivio.da_fermare(id_lavoro, c):
                raise Fermato
            gid = _un_tema(c, radice, voce, per_id, brani)
            if gid:
                rinfrescati.add(gid)
            avanza(fatti=len(docs) + 1 + j, messaggio=f"temi dei tesauri: {voce[3]}")
        c.commit()

        # 3bis) le tue sottocartelle: il modo in cui hai già ordinato i file tu.
        # Si guardano tutti i documenti, anche quelli senza testo.
        cartelle, prima_cartella = _sottocartelle(radice, archivio.documenti_di(radice))
        for k, dentro in cartelle.items():
            nome = k.replace("/", " › ")
            spieg = (f"La sottocartella «{nome}»: ci stanno tutti i file che hai messo lì, "
                     "sottocartelle comprese. È il modo in cui hai già ordinato i file tu; "
                     "i temi e i gruppi scoperti la attraversano.")
            membri_c = {p: (f"sta in {rel}", 1.0) for p, rel in dentro.items()}
            rinfrescati.add(_salva_gruppo(c, radice, "cartella:" + k, nome, "cartella",
                                          spieg, membri_c))
        c.commit()

        # 3ter) i temi fatti da te, con le loro parole: si rinfrescano anche loro
        for g in c.execute("""SELECT id FROM gruppi WHERE radice=? AND origine='mio'
                              AND COALESCE(forme, '') <> ''""", (radice,)).fetchall():
            riempi_tema(g["id"], c, (per_id, brani))

        # 4) i gruppi scoperti: documenti che condividono una parola caratteristica.
        # Le parole che il tesauro conosce già si lasciano ai suoi temi — altrimenti
        # «venice», «venedig», «venetian» farebbero tre gruppi dello stesso tema —
        # e le varianti di una parola («cronache», «cronachistica») vanno insieme.
        del_tesauro = {_tronco(w) for *_, forme in temi for f in forme
                       for w in tesauro.piatto(f).split() if len(w) >= 4}
        per_tronco = collections.defaultdict(set)
        forme_del_tronco = collections.defaultdict(collections.Counter)
        for did, scelte in caratteristiche.items():
            for w, n, _ in scelte:
                t = _tronco(w)
                if t in del_tesauro or len(w) < 5:
                    continue
                per_tronco[t].add(did)
                forme_del_tronco[t][w] += n
        per_parola = {forme_del_tronco[t].most_common(1)[0][0]: ds for t, ds in per_tronco.items()}
        massimo = max(4, int(0.35 * len(docs)))
        parole_buone = sorted((w for w, ds in per_parola.items() if 3 <= len(ds) <= massimo),
                              key=lambda w: -len(per_parola[w]))
        proposte = []                                  # [parole, documenti]
        for w in parole_buone:
            ds = per_parola[w]
            for p in proposte:
                if len(p[1] & ds) / len(p[1] | ds) >= 0.6:
                    p[0].append(w)
                    p[1] |= ds
                    break
            else:
                proposte.append([[w], set(ds)])
        tutte = sorted((p for p in proposte if len(p[1]) >= 3), key=lambda p: -len(p[1]))
        # i trenta più grandi, da 4 file in su; e poi ogni sottocartella con i suoi
        # tre migliori: un tema di sessanta file sparisce sotto quelli di
        # novemila, se si guardano solo i più grandi
        proposte = [p + [None] for p in tutte if len(p[1]) >= 4][:30]
        gia = {id(p[1]) for p in proposte}
        per_sotto = collections.defaultdict(list)
        for p in tutte:
            if id(p[1]) in gia:
                continue
            conta = collections.Counter(prima_cartella.get(did) for did in p[1])
            cart, k = conta.most_common(1)[0]
            if cart and k >= 3 and k >= 0.6 * len(p[1]) and len(per_sotto[cart]) < 3:
                per_sotto[cart].append(p + [cart])
        for ps in per_sotto.values():
            proposte.extend(ps)
        for parole, ds, cart in proposte:
            membri_gruppo = {}
            for did in ds:
                sue = {_tronco(w): (w, n) for w, n, _ in caratteristiche[did]}
                comuni = [f"{sue[_tronco(p)][0]} ({sue[_tronco(p)][1]} volte)"
                          for p in parole if _tronco(p) in sue][:4]
                membri_gruppo[per_id[did]["percorso"]] = (
                    "fra le sue parole caratteristiche: " + ", ".join(comuni), len(comuni))
            nome = " · ".join(parole[:3]) + (f" — in {cart}" if cart else "")
            spiegazione = (f"Gruppo scoperto da Scaffale. Questi documenti hanno fra le loro parole "
                           f"caratteristiche «{'», «'.join(parole[:6])}»: parole frequenti in un "
                           "documento e rare nel resto dell'archivio. Scaffale non sa che cosa "
                           "significhino: è una proposta, da tenere, rinominare o eliminare.")
            if cart:
                spiegazione += (f" Quasi tutti stanno nella sottocartella «{cart}»: è uno dei "
                                "gruppi più piccoli, proposto perché è tipico di quella cartella.")
            gid_s = _salva_gruppo(c, radice, f"parola:{parole[0]}", nome, "scoperto",
                                  spiegazione, membri_gruppo)
            # le sue parole restano scritte: servono a farne un tema di un tesauro
            c.execute("UPDATE gruppi SET forme=? WHERE id=?",
                      (json.dumps(parole, ensure_ascii=False), gid_s))
            rinfrescati.add(gid_s)
        c.commit()

        # 5) i gruppi automatici che non ci sono più, se nessuno li ha toccati a mano
        for g in list(c.execute("SELECT id FROM gruppi WHERE radice=? AND origine IN "
                                "('tesauro','scoperto','cartella') AND COALESCE(nascosto, 0) = 0",
                                (radice,)).fetchall()):
            if g["id"] in rinfrescati:
                continue
            a_mano = c.execute("SELECT 1 FROM nei_gruppi WHERE gruppo=? AND come='a mano' LIMIT 1",
                               (g["id"],)).fetchone()
            del_tesauro_spento = c.execute("SELECT origine FROM gruppi WHERE id=?",
                                           (g["id"],)).fetchone()["origine"] == "tesauro"
            if not a_mano or del_tesauro_spento:
                c.execute("DELETE FROM nei_gruppi WHERE gruppo=?", (g["id"],))
                c.execute("DELETE FROM gruppi WHERE id=?", (g["id"],))
        c.commit()
    except Fermato:
        c.commit()
        avanza( stato="fermato", finito=time.time(),
                                 messaggio="analisi fermata a metà: rifalla quando vuoi")
        return
    n_temi = c.execute("SELECT COUNT(*) n FROM gruppi WHERE radice=? AND origine='tesauro'",
                       (radice,)).fetchone()["n"]
    scoperti = c.execute("SELECT COUNT(*) n FROM gruppi WHERE radice=? AND origine='scoperto'",
                         (radice,)).fetchone()["n"]
    sotto = c.execute("SELECT COUNT(*) n FROM gruppi WHERE radice=? AND origine='cartella'",
                      (radice,)).fetchone()["n"]
    esito = (f"{len(docs)} documenti letti · {sotto} sottocartelle · {n_temi} temi del tesauro · "
             f"{scoperti} gruppi scoperti")
    avviso(esito)
    avanza( stato="finito", finito=time.time(), messaggio=esito,
                             riga=esito)


# ----------------------------------------------------------------- gruppi ---

def gruppi_di(radice):
    """I gruppi di una cartella, con quanti documenti ciascuno."""
    c = apri()
    return [dict(r) for r in c.execute("""
        SELECT g.*, (SELECT COUNT(*) FROM nei_gruppi n WHERE n.gruppo = g.id
                     AND n.come IN ('automatico','a mano')) documenti
        FROM gruppi g WHERE g.radice = ? AND COALESCE(g.nascosto, 0) = 0
        ORDER BY CASE g.origine WHEN 'mio' THEN 0 WHEN 'cartella' THEN 1
                                WHEN 'tesauro' THEN 2 ELSE 3 END,
                 CASE WHEN g.origine = 'cartella' THEN g.nome ELSE '' END,
                 documenti DESC, g.nome""", (radice,))]


def gruppo(gid):
    r = apri().execute("SELECT * FROM gruppi WHERE id=?", (gid,)).fetchone()
    return dict(r) if r else None


def membri(gid):
    """percorso -> (come, prova) dei documenti di un gruppo."""
    return {r["percorso"]: (r["come"], r["prova"]) for r in apri().execute(
        "SELECT percorso, come, prova FROM nei_gruppi WHERE gruppo=? AND come IN ('automatico','a mano')",
        (gid,))}


def gruppi_per_file(radice):
    """percorso -> [nomi dei gruppi], per mostrarli nell'elenco dei file."""
    fuori = collections.defaultdict(list)
    for r in apri().execute("""SELECT n.percorso, g.id, g.nome, g.origine FROM nei_gruppi n
                               JOIN gruppi g ON g.id = n.gruppo
                               WHERE g.radice = ? AND n.come IN ('automatico','a mano')
                               AND COALESCE(g.nascosto, 0) = 0 AND g.origine <> 'cartella'
                               ORDER BY CASE g.origine WHEN 'mio' THEN 0 WHEN 'tesauro' THEN 1 ELSE 2 END""",
                            (radice,)):
        fuori[r["percorso"]].append((r["id"], r["nome"], r["origine"]))
    return fuori


def gruppi_del_file(percorso):
    return [dict(r) for r in apri().execute("""
        SELECT g.id, g.nome, g.origine, g.radice, n.come, n.prova FROM nei_gruppi n
        JOIN gruppi g ON g.id = n.gruppo
        WHERE n.percorso = ? AND n.come IN ('automatico','a mano') AND COALESCE(g.nascosto, 0) = 0
        ORDER BY CASE g.origine WHEN 'mio' THEN 0 WHEN 'tesauro' THEN 1 ELSE 2 END, g.nome""",
        (percorso,))]


def tieni_gruppo(gid):
    """Un gruppo scoperto diventa un gruppo tuo, con un clic: stesso nome, stessi
    file. Da lì in poi è tuo e non cambia più da solo; quello scoperto si nasconde,
    così non si vede due volte, e non torna alla prossima analisi."""
    c = apri()
    g = c.execute("SELECT * FROM gruppi WHERE id=?", (gid,)).fetchone()
    if not g:
        raise ValueError("Non trovo questo gruppo.")
    nome = re.sub(r" — in .*$", "", g["nome"]).strip()
    nuovo = c.execute("""INSERT INTO gruppi (radice, chiave, nome, origine, spiegazione, creato_il)
                         VALUES (?,?,?,?,?,?)""",
                      (g["radice"], f"mio:{time.time_ns()}", nome[:120], "mio",
                       f"Gruppo tuo, preso dal gruppo scoperto «{g['nome']}»: ci stanno i file che "
                       "Scaffale ci aveva trovato, e quelli che ci metti tu. Non cambia più da solo.",
                       time.time())).lastrowid
    for r in c.execute("""SELECT percorso, prova FROM nei_gruppi WHERE gruppo=?
                          AND come IN ('automatico','a mano')""", (gid,)).fetchall():
        c.execute("""INSERT OR IGNORE INTO nei_gruppi (gruppo, percorso, come, prova, punteggio)
                     VALUES (?,?,'a mano',?,1)""", (nuovo, r["percorso"], r["prova"]))
    if g["origine"] == "scoperto":
        c.execute("UPDATE gruppi SET nascosto=1 WHERE id=?", (gid,))
    c.commit()
    return nuovo


def nuovo_gruppo(radice, nome):
    c = apri()
    gid = c.execute("""INSERT INTO gruppi (radice, chiave, nome, origine, spiegazione, creato_il)
                       VALUES (?,?,?,?,?,?)""",
                    (radice, f"mio:{time.time_ns()}", nome.strip()[:120], "mio",
                     "Gruppo creato da te: ci stanno i documenti che ci hai messo.",
                     time.time())).lastrowid
    c.commit()
    return gid


def rinomina(gid, nome):
    c = apri()
    c.execute("UPDATE gruppi SET nome=? WHERE id=?", (nome.strip()[:120], gid))
    c.commit()


def elimina(gid):
    """Toglie il gruppo, non i documenti: i file restano dove sono.

    Un gruppo automatico non si cancella ma si nasconde: se no la prossima
    analisi lo ritroverebbe, e lo riproporrebbe tale e quale.
    """
    c = apri()
    g = c.execute("SELECT origine FROM gruppi WHERE id=?", (gid,)).fetchone()
    if g and g["origine"] != "mio":
        c.execute("UPDATE gruppi SET nascosto=1 WHERE id=?", (gid,))
    else:
        c.execute("DELETE FROM nei_gruppi WHERE gruppo=?", (gid,))
        c.execute("DELETE FROM gruppi WHERE id=?", (gid,))
    c.commit()


def metti(gid, percorsi, da=None):
    """Mette dei documenti in un gruppo; con `da`, li sposta da un altro."""
    c = apri()
    for p in percorsi:
        c.execute("""INSERT INTO nei_gruppi (gruppo, percorso, come, prova, punteggio)
                     VALUES (?,?,'a mano','messo da te',NULL)
                     ON CONFLICT(gruppo, percorso) DO UPDATE SET come='a mano', prova='messo da te'""",
                  (gid, p))
    c.commit()
    if da and da != gid:
        for p in percorsi:
            togli(da, p)


def togli(gid, percorso):
    """Toglie un documento da un gruppo. Da un gruppo automatico lo si segna
    come tolto, perché l'analisi successiva non lo rimetta dentro."""
    c = apri()
    g = c.execute("SELECT origine FROM gruppi WHERE id=?", (gid,)).fetchone()
    if not g:
        return
    if g["origine"] == "mio":
        c.execute("DELETE FROM nei_gruppi WHERE gruppo=? AND percorso=?", (gid, percorso))
    else:
        c.execute("""INSERT INTO nei_gruppi (gruppo, percorso, come, prova, punteggio)
                     VALUES (?,?,'tolto a mano','tolto da te',NULL)
                     ON CONFLICT(gruppo, percorso) DO UPDATE SET come='tolto a mano'""",
                  (gid, percorso))
    c.commit()


# ------------------------------------------------------------ le schede ---

def scheda(percorso):
    r = apri().execute("SELECT * FROM schede WHERE percorso=?", (percorso,)).fetchone()
    if not r:
        return {}
    d = dict(r)
    d["parole"] = json.loads(d["parole"] or "[]")
    return d


def schede_di(radice):
    c = apri()
    fuori = {}
    for r in c.execute("""SELECT s.percorso, s.parole, s.riassunto, s.incipit FROM schede s
                          JOIN documenti d ON d.percorso = s.percorso WHERE d.radice = ?""", (radice,)):
        fuori[r["percorso"]] = {"parole": json.loads(r["parole"] or "[]"),
                                "riassunto": r["riassunto"], "incipit": r["incipit"]}
    return fuori


def indice_pdf(percorso):
    """L'indice interno di un PDF — capitoli e paragrafi — se il PDF ce l'ha.

    Molti PDF di libri e articoli lo portano con sé, e il lettore del browser
    lo mostra di lato. Scaffale lo legge senza toccare il file: (livello,
    titolo, pagina).
    """
    if not percorso.lower().endswith(".pdf"):
        return []
    import estrattori
    try:
        d = estrattori._apri(percorso)
        try:
            return [(l, t.strip(), p) for l, t, p in d.get_toc(simple=True) if t.strip()]
        finally:
            d.close()
    except Exception:
        return []


def da_riassumere(radice):
    """I documenti di una cartella che hanno testo e non hanno ancora il riassunto."""
    c = apri()
    senza = [r["percorso"] for r in c.execute("""
        SELECT d.percorso FROM documenti d LEFT JOIN schede s ON s.percorso = d.percorso
        WHERE d.radice = ? AND d.stato = 'indicizzato'
          AND (s.riassunto IS NULL OR s.riassunto = '')
          AND EXISTS (SELECT 1 FROM frammenti f WHERE f.documento = d.id)
        ORDER BY d.cartella, d.nome""", (radice,))]
    # di un PDF e del suo .md se ne riassume uno solo, e non se l'altro ce l'ha già
    unita, compagno = _unita_da_riassumere(archivio.documenti_di(radice))
    unita = set(unita)
    con = {r["percorso"] for r in c.execute(
        "SELECT percorso FROM schede WHERE COALESCE(riassunto, '') <> ''")} if compagno else set()
    return [p for p in senza if p in unita and compagno.get(p) not in con]


def riassumi_tutti(radice, avviso=print, id_lavoro=None, percorsi=None):
    """I riassunti dei documenti di una cartella, uno dopo l'altro: tutti, o
    solo quelli indicati — gli spuntati, quelli di un gruppo.

    Quelli già fatti non si rifanno; si può fermare fra un documento e l'altro,
    e la volta dopo riprende da dove era.
    """
    lista = da_riassumere(radice)
    if percorsi is not None:
        voluti = set(percorsi)
        lista = [p for p in lista if p in voluti]
    archivio.aggiorna_lavoro(id_lavoro, totale=len(lista), fatti=0,
                             riga=f"documenti da riassumere: {len(lista)}")
    fatti, errori = 0, 0
    for i, p in enumerate(lista, 1):
        if archivio.da_fermare(id_lavoro):
            archivio.aggiorna_lavoro(id_lavoro, stato="fermato", finito=time.time(),
                                     messaggio=f"fermato: {fatti} riassunti scritti, gli altri "
                                               "la prossima volta")
            return
        archivio.aggiorna_lavoro(id_lavoro, fatti=i - 1,
                                 messaggio=f"riassumo {i}/{len(lista)}: {os.path.basename(p)[:60]}")
        t0 = time.time()
        try:
            riassumi(p)
            fatti += 1
            archivio._ricorda("riassunto", time.time() - t0, 1, 1)
        except Exception as exc:
            errori += 1
            avviso(f"  {os.path.basename(p)[:60]}: {exc}")
    esito = f"{fatti} riassunti scritti" + (f", {errori} non riusciti" if errori else "")
    archivio.aggiorna_lavoro(id_lavoro, stato="finito", finito=time.time(), fatti=len(lista),
                             messaggio=esito, riga=esito)


def _modello_per_riassunti():
    """Il modello che scrive: riassunti, temi, risposte, ricerca approfondita.

    Con `modello_testi` in `scaffale.ini` si sceglie a mano, e se è lo stesso
    nome di `modello_ocr` si parla al server di `server_ocr` invece che a
    Ollama: è il modello grande già acceso sul computer, e per leggere documenti
    di storia e scriverne è un altro mestiere rispetto a un modello da otto
    miliardi di parametri. Vuoto: il migliore che Ollama abbia, come prima.

    Mai uno di quelli che finiscono per «:cloud»: girano su internet, e i
    documenti uscirebbero dal computer. Né quelli che fanno solo vettori o OCR.
    """
    import semantica
    voluto = impostazioni.valore("modello_testi") or impostazioni.valore("modello_riassunti")
    if voluto and voluto.endswith(":cloud"):
        voluto = ""
    # il modello del server: non sta in Ollama, quindi non lo si cerca là
    if voluto and voluto == impostazioni.modello_ocr() and impostazioni.server_ocr():
        return voluto
    ci_sono = [m for m in semantica.modelli() if not m.endswith(":cloud")]
    if voluto and voluto in ci_sono:
        return voluto
    for preferito in ("qwen3:8b", "qwen3.5:latest", "qwen3:4b", "llama3.1:8b", "mistral:latest"):
        if preferito in ci_sono:
            return preferito
    escluse = ("bge", "embed", "ocr", "llava", "-vl", "minilm", "nomic")
    resto = [m for m in ci_sono if not any(x in m.lower() for x in escluse)]
    return resto[0] if resto else None


def server_dei_testi(nome=None):
    """Il server dove gira il modello che scrive, o None se sta in Ollama."""
    nome = nome or _modello_per_riassunti()
    if nome and nome == impostazioni.modello_ocr() and impostazioni.server_ocr():
        return impostazioni.server_ocr()
    return None


def scrivi_testo(prompt, id_lavoro=None, avanza=None, ogni=25, parole=600,
                 temperatura=0.2, json_puro=False, opzioni=None):
    """(testo, nome del modello): quello che il modello scrive, a pezzi.

    Un posto solo per i riassunti, i temi, le risposte e la ricerca
    approfondita, così il modello si sceglie una volta in `scaffale.ini` e vale
    per tutti. Parla a Ollama, o al server di `server_ocr` se è là che sta il
    modello scelto. Il Ferma funziona in tutti e due i casi."""
    nome = _modello_per_riassunti()
    if not nome:
        raise RuntimeError("non c'è un modello adatto a scrivere: in Ollama non ce n'è uno, "
                           "e `modello_testi` in scaffale.ini non indica il modello di un server")
    server = server_dei_testi(nome)
    if server:
        corpo = {"model": nome, "temperature": temperatura, "max_tokens": parole,
                 "chat_template_kwargs": {"enable_thinking": False},
                 "messages": [{"role": "user", "content": prompt}]}
        if json_puro:
            corpo["response_format"] = {"type": "json_object"}
        return scrivi_col_modello(corpo, id_lavoro, avanza, ogni,
                                  server=server, openai=True).strip(), nome
    corpo = {"model": nome, "prompt": prompt, "think": False,
             "options": dict({"temperature": temperatura, "num_predict": parole},
                             **(opzioni or {}))}
    if json_puro:
        corpo["format"] = "json"
    return scrivi_col_modello(corpo, id_lavoro, avanza, ogni).strip(), nome


def riassumi(percorso):
    """Chiede a un modello di Ollama, sul computer, di dire di che cosa tratta un documento."""
    import requests
    c = apri()
    d = c.execute("SELECT id FROM documenti WHERE percorso=?", (percorso,)).fetchone()
    if not d:
        raise RuntimeError("documento non trovato nell'archivio")
    brani = [r["testo"] for r in c.execute(
        "SELECT testo FROM frammenti WHERE documento=? ORDER BY ordine", (d["id"],))]
    if not brani:
        raise RuntimeError("questo documento non ha testo da riassumere")
    # l'inizio, e un brano da metà: l'inizio da solo è spesso indice e premessa
    scelti = brani[:2] + ([brani[len(brani) // 2]] if len(brani) > 4 else [])
    testo = re.sub(r"\[\[(pagina|immagine)[^\]]*\]\]", " ", "\n".join(scelti))[:6000]
    prompt = ("Sei l'assistente di uno storico. Leggi questi passi di un documento e scrivi in "
              "italiano, in 3 frasi al massimo, di che cosa tratta: argomento, periodo, luoghi, "
              "autore se si capisce. Non inventare niente che non sia nel testo; se qualcosa non "
              "si capisce, non dirlo.\n\nTESTO:\n" + testo)
    riassunto, modello = scrivi_testo(prompt, parole=260, temperatura=0.2)
    if not riassunto:
        raise RuntimeError("il modello non ha risposto niente")
    c.execute("""INSERT INTO schede (percorso, riassunto, modello, riassunto_il) VALUES (?,?,?,?)
                 ON CONFLICT(percorso) DO UPDATE SET riassunto=excluded.riassunto,
                 modello=excluded.modello, riassunto_il=excluded.riassunto_il""",
              (percorso, riassunto, modello, time.time()))
    c.commit()
    return riassunto, modello
