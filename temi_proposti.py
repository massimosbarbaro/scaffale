#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I temi di una cartella, proposti dal modello che gira sul computer.

Il modello non legge i documenti interi — su un computer senza scheda grafica
sarebbero giorni — ma un profilo della cartella: per ogni file il titolo e le
sue parole caratteristiche, quelle che l'analisi ha già trovato. Da lì propone
i temi di ricerca che attraversano la cartella, ciascuno con un nome, una frase
e le parole con cui compare nei testi.

Poi Scaffale controlla ogni proposta sull'indice, perché il modello può
inventare e l'indice no: quali parole ci sono davvero, in quanti file, e se il
tema non è così generico da stare in quasi tutta la cartella. Chi fa la ricerca
decide: «tieni» fa del tema un tema vero, nel tesauro della cartella, e i file
ci entrano da soli; «scarta» lo toglie, e non torna la volta dopo.
"""
import json
import os
import re
import time

import archivio
import biblioteca
import tesauri
import tesauro
import varianti

SCHEMA = """
CREATE TABLE IF NOT EXISTS temi_proposti (
    id INTEGER PRIMARY KEY,
    radice TEXT,
    nome TEXT,
    descrizione TEXT,
    forme TEXT,          -- JSON: [[parola, in quanti file della cartella], …], solo quelle che ci sono
    assenti TEXT,        -- JSON: le parole proposte che nella cartella non ci sono
    file INTEGER,        -- quanti file starebbero nel tema
    generico INTEGER,    -- sta in più di metà della cartella: il tema di fondo
    stato TEXT,          -- proposto | tenuto | scartato
    modello TEXT,
    creato_il REAL
);
"""

# secondi per carattere di profilo, misurati con qwen3:8b su un portatile senza
# scheda grafica: 651 secondi per il profilo di Paci Medievali, 70 righe. Conta
# più la risposta, una dozzina di temi, che la lettura. Poi vale la misura di qui.
SECONDI_PER_CARATTERE = 0.09
MASSIMO_RIGHE = 70

# le parole corte che la lettura attacca in fondo o in testa a un'altra:
# «regoleper», «dellachiesa». Solo queste, perché con le altre si sbaglia:
# «perdono» comincia con «per» ed è una parola vera.
ATTACCATE_IN_FONDO = ("per", "del", "dei", "della", "delle", "nel", "con", "the", "and", "und")
ATTACCATE_IN_TESTA = ("della", "delle", "degli", "dello", "dalla", "nella", "sulla", "alla")

# due proposte con quasi tutti i file in comune sono lo stesso tema detto in
# due modi («Paci e mediazione», «Storia delle paci»): si uniscono
UNIRE_SOPRA = 0.6
UNIRE_DI_FONDO = 0.8


def apri():
    c = archivio.apri()
    c.executescript(SCHEMA)
    # i file di ogni proposta, per confrontarla con i gruppi della cartella e non
    # mostrare due volte lo stesso tema; le proposte di prima non li hanno
    if "membri" not in {r["name"] for r in c.execute("PRAGMA table_info(temi_proposti)")}:
        c.execute("ALTER TABLE temi_proposti ADD COLUMN membri TEXT")
        c.commit()
    return c


def _pulito(testo):
    return re.sub(r"\s+", " ", testo or "").strip()


def profilo(radice):
    """Il profilo della cartella che legge il modello: una riga per file, con il
    titolo e le parole caratteristiche. Le trascrizioni .md di un PDF già in
    elenco non si ripetono; in una cartella grande si prende un campione, da
    ogni sottocartella in proporzione. Restituisce (testo, file descritti, file in tutto)."""
    docs = archivio.documenti_di(radice)
    schede = biblioteca.schede_di(radice)
    stem = lambda p: os.path.splitext(p)[0].lower()
    pdf = {stem(d["percorso"]) for d in docs if d["estensione"] == ".pdf"}
    candidati = []
    for d in docs:
        if d["estensione"] == ".md" and stem(d["percorso"]) in pdf:
            continue
        parole = [w[0] for w in (schede.get(d["percorso"], {}).get("parole") or [])][:6]
        if not parole and d["stato"] != "indicizzato":
            continue
        nome = _pulito(re.sub(r"[_]+", " ", os.path.splitext(d["nome"])[0]))[:90]
        candidati.append((d, f"- {nome}" + (f" | {', '.join(parole)}" if parole else "")))
    if len(candidati) > MASSIMO_RIGHE:
        # un campione da ogni sottocartella, in proporzione, almeno uno ciascuna
        _, prima = biblioteca._sottocartelle(radice, [d for d, _ in candidati])
        per_cartella = {}
        for d, riga in candidati:
            per_cartella.setdefault(prima.get(d["id"], ""), []).append(riga)
        scelte = []
        for righe in per_cartella.values():
            quante = max(1, round(MASSIMO_RIGHE * len(righe) / len(candidati)))
            passo = max(1, len(righe) // quante)
            scelte += righe[::passo][:quante]
        righe = scelte[:MASSIMO_RIGHE + 10]
    else:
        righe = [r for _, r in candidati]
    return "\n".join(righe), len(righe), len(docs)


def stima(radice):
    """Quanto ci vorrà, in secondi, secondo le misure fatte su questo computer."""
    testo, _, _ = profilo(radice)
    v = archivio.velocita().get("temi_modello", SECONDI_PER_CARATTERE)
    return 60 + len(testo) * v


def di(radice):
    """Le proposte di una cartella, le ancora da decidere per prime. Quelle
    tenute portano il tesauro e il tema dove sono finite, per poterle cambiare."""
    c = apri()
    ts = c.execute("SELECT id FROM tesauri WHERE nome=?", (f"Temi di «{radice}»",)).fetchone()
    fuori = []
    for r in c.execute("""SELECT * FROM temi_proposti WHERE radice=? AND stato<>'scartato'
                          ORDER BY stato='tenuto', file DESC""", (radice,)):
        x = dict(r)
        x["forme"] = json.loads(x["forme"] or "[]")
        x["assenti"] = json.loads(x["assenti"] or "[]")
        x["membri"] = set(json.loads(x.get("membri") or "[]"))
        x["tesauro"] = x["tema"] = None
        if x["stato"] == "tenuto" and ts:
            t = c.execute("SELECT id FROM temi_tesauro WHERE tesauro=? AND nome=?",
                          (ts["id"], x["nome"])).fetchone()
            if t:
                x["tesauro"], x["tema"] = ts["id"], t["id"]
        fuori.append(x)
    # le proposte di prima non avevano i file: si calcolano una volta e si tengono
    senza = [x for x in fuori if x["stato"] == "proposto" and not x["membri"] and x["forme"]]
    if senza:
        per_id, brani = biblioteca._contesto(c, radice)
        for x in senza:
            x["membri"] = set(biblioteca.membri_del_tema(c, radice, [f for f, _ in x["forme"]],
                                                         per_id, brani))
            c.execute("UPDATE temi_proposti SET membri=? WHERE id=?",
                      (json.dumps(sorted(x["membri"]), ensure_ascii=False), x["id"]))
        c.commit()
    return fuori


def _errore_di_lettura(c, parola, radice, n):
    """Se una parola è un errore di lettura e non una parola vera.
    «cofa» per «cosa», «effere» per «essere»: nelle stampe antiche la s lunga si
    legge f. Si prova con la s al posto delle f dentro la parola — non della
    prima lettera, perché «fede» e «sede» sono due parole vere — e se così la
    parola sta in molti più file della cartella, era un errore.
    «regoleper»: una parola corta attaccata; tolta quella, il resto sta in molti
    più file. `n` è in quanti file della cartella sta la parola com'è.
    Le soglie vengono da Paci Medievali: «cosa» in 57 file, «cofa» in 28; per le
    parole vere la forma con la s non c'è mai («difesa», «dissesa»: 38 e 0)."""
    p = tesauro.piatto(parola)
    if " " in p or len(p) < 4:
        return False
    dentro = [i for i, ch in enumerate(p) if ch == "f" and i > 0]
    con_la_s = {p[:i] + "s" + p[i + 1:] for i in dentro}
    if len(dentro) > 1:
        con_la_s.add(p[0] + p[1:].replace("f", "s"))
    if any(varianti._file(c, q, radice) >= max(1.5 * n, n + 5) for q in con_la_s):
        return True
    # «conf», «tratt», «rappa»: pezzi di parola, abbreviazioni o righe spezzate.
    # Come inizio di parola stanno in molti più file che da sole: «conf» in 14,
    # «conf…» in 80. Per quelle che finiscono per vocale si chiede di più, perché
    # «rito» è una parola vera anche se «ritorno» è più comune (43 e 67 file).
    if len(p) <= 6:
        volte = 4 if p[-1] not in "aeiouy" else 10
        if _come_inizio(c, p, radice) >= max(volte * n, n + 5):
            return True
    if n > 10:
        return False
    staccate = ({p[:-len(k)] for k in ATTACCATE_IN_FONDO if p.endswith(k) and len(p) - len(k) >= 4}
                | {p[len(k):] for k in ATTACCATE_IN_TESTA if p.startswith(k) and len(p) - len(k) >= 4})
    return any(varianti._file(c, q, radice) >= max(4 * n, n + 5) for q in staccate)


def _come_inizio(c, p, radice):
    """In quanti file della cartella c'è una parola che comincia con `p`."""
    try:
        return c.execute("""SELECT COUNT(DISTINCT r.documento) n FROM ricerca r WHERE ricerca MATCH ?
                            AND r.documento IN (SELECT id FROM documenti WHERE radice = ?)""",
                         ('{testo piatto}:"%s"*' % p.replace('"', " "), radice)).fetchone()["n"]
    except Exception:
        return 0


def _unisci(proposte, n_doc):
    """Le proposte con quasi tutti i file in comune diventano una sola: resta il
    nome di quella con più file, le parole si sommano. Ogni proposta è un dict
    con nome, descrizione, parole [[forma, file]] e membri (l'insieme dei file).
    Un tema di fondo, in più di metà della cartella, ha molti file in comune con
    tutti: assorbe un tema preciso mai, un altro tema di fondo solo se hanno
    quasi gli stessi file («Paci medievali» e «Riconciliazione e pace»)."""
    di_fondo = lambda x: len(x["membri"]) > 0.5 * n_doc
    tenute = []
    for p in sorted(proposte, key=lambda x: -len(x["membri"])):
        def vicine(t):
            comuni = len(p["membri"] & t["membri"]) / max(len(p["membri"] | t["membri"]), 1)
            if not di_fondo(t):
                return comuni >= UNIRE_SOPRA
            return di_fondo(p) and comuni >= UNIRE_DI_FONDO
        simile = next((t for t in tenute if vicine(t)), None)
        if not simile:
            tenute.append(p)
            continue
        viste = {tesauro.piatto(f) for f, _ in simile["parole"]}
        simile["parole"] += [x for x in p["parole"] if tesauro.piatto(x[0]) not in viste]
        simile["uniti"] = simile.get("uniti", []) + [p["nome"]]
    return tenute


def _chiedi(nome_cartella, testo, id_lavoro):
    """La domanda al modello. Arriva a pezzi, così il pulsante Ferma funziona anche a metà."""
    if not biblioteca._modello_per_riassunti():
        raise RuntimeError("Non c'è un modello per scrivere: installane uno in Ollama, per "
                           "esempio con «ollama pull qwen3:8b», oppure indica in scaffale.ini "
                           "il modello di un server con «modello_testi».")
    prompt = (f"Sei l'assistente di uno storico. Questa è una cartella di ricerca, «{nome_cartella}». "
              "Per ogni file hai il titolo e le sue parole caratteristiche:\n\n" + testo + "\n\n"
              "Individua da 8 a 14 temi di ricerca precisi che attraversano questi documenti: non temi "
              "generici come «storia», «testi», «documenti», ma quelli su cui si fa ricerca qui. Per ogni "
              "tema dai: un nome breve; una frase che lo descrive; da 6 a 12 parole o brevi espressioni "
              "con cui compare nei testi, nelle lingue dei documenti (italiano, latino, inglese, croato, "
              "sloveno, tedesco…) e nelle loro grafie, anche antiche.\n"
              "Le parole devono dire il tema: concetti, istituzioni, pratiche, luoghi. Non nomi di "
              "autori, non parole comuni come «casa», «corso», «signore», non pezzi di titoli. Fra le "
              "parole caratteristiche ci sono errori di lettura delle stampe antiche («cofa» per «cosa», "
              "«effere» per «essere») e parole attaccate («regoleper»): non usarle.\n"
              'Rispondi solo con JSON: {"temi": [{"nome": "...", "descrizione": "...", "parole": ["..."]}]}')
    testo, modello = biblioteca.scrivi_testo(
        prompt, id_lavoro, lambda n: archivio.aggiorna_lavoro(
            id_lavoro, messaggio=f"il modello sta scrivendo i temi… ({n} parole)"),
        ogni=40, parole=1800, temperatura=0.3, json_puro=True,
        opzioni={"repeat_penalty": 1.15, "num_ctx": 8192})
    try:
        return json.loads(testo).get("temi") or [], modello
    except ValueError:
        return [], modello


def proponi(radice, avviso=print, id_lavoro=None):
    """Il lavoro intero: profilo, domanda al modello, controllo di ogni tema sull'indice."""
    t0 = time.time()
    testo, righe, tutti = profilo(radice)
    archivio.aggiorna_lavoro(id_lavoro, totale=3, fatti=0,
                             riga=f"profilo della cartella: {righe} file su {tutti}")
    archivio.aggiorna_lavoro(id_lavoro, fatti=1, messaggio=f"il modello legge il profilo di {righe} file…")
    try:
        grezzi, modello = _chiedi(radice, testo, id_lavoro)
    except biblioteca.Fermato:
        archivio.aggiorna_lavoro(id_lavoro, stato="fermato", finito=time.time(),
                                 messaggio="fermato: nessun tema proposto")
        return
    # quanto ci ha messo: la prossima stima sarà di qui
    try:
        archivio._ricorda("temi_modello", max(time.time() - t0 - 30, 1), max(len(testo), 1), 1)
    except Exception:
        pass
    archivio.aggiorna_lavoro(id_lavoro, fatti=2, messaggio="controllo i temi sui documenti…")
    c = apri()
    per_id, brani = biblioteca._contesto(c, radice)
    n_doc = max(len(per_id), 1)
    gia = {tesauro.piatto(r["nome"]) for r in c.execute(
        "SELECT nome FROM temi_proposti WHERE radice=? AND stato IN ('tenuto','scartato')", (radice,))}
    c.execute("DELETE FROM temi_proposti WHERE radice=? AND stato='proposto'", (radice,))
    proposte = []
    for t in grezzi:
        if not isinstance(t, dict):
            continue
        nome = _pulito(str(t.get("nome") or ""))[:80]
        if not nome or tesauro.piatto(nome) in gia:
            continue
        gia.add(tesauro.piatto(nome))
        # il nome, se è una parola sola, vale anche come parola del tema
        parole = tesauri.pulisci_forme([str(x) for x in (t.get("parole") or [])]
                                       + ([nome] if " " not in nome else []))
        ci_sono, assenti = [], []
        for p in parole:
            n = varianti._file(c, p, radice)
            # una parola che sta in un file solo, in una cartella, è quasi sempre un
            # pezzo di titolo o un errore di lettura: non basta a fare un tema
            if (n >= 2 and p.lower() not in biblioteca.PAROLE_VUOTE
                    and biblioteca._parola_vera(tesauro.piatto(p))
                    and not _errore_di_lettura(c, p, radice, n)):
                ci_sono.append([p, n])
            else:
                assenti.append(p)
        if not ci_sono:
            continue
        membri = biblioteca.membri_del_tema(c, radice, [p for p, _ in ci_sono], per_id, brani)
        if membri:
            proposte.append({"nome": nome, "descrizione": _pulito(str(t.get("descrizione") or ""))[:300],
                             "parole": ci_sono, "assenti": assenti, "membri": set(membri)})
    unite = _unisci(proposte, n_doc)
    for p in unite:
        if p.get("uniti"):
            # con le parole dell'altra, i file del tema si rifanno
            p["membri"] = set(biblioteca.membri_del_tema(c, radice, [f for f, _ in p["parole"]],
                                                          per_id, brani))
            p["descrizione"] = (p["descrizione"] + " Unito con: "
                                + ", ".join(f"«{u}»" for u in p["uniti"]) + ".")[:400]
        c.execute("""INSERT INTO temi_proposti (radice, nome, descrizione, forme, assenti, file,
                     generico, stato, modello, creato_il, membri) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (radice, p["nome"], p["descrizione"],
                   json.dumps(sorted(p["parole"], key=lambda x: -x[1]), ensure_ascii=False),
                   json.dumps(p["assenti"], ensure_ascii=False), len(p["membri"]),
                   int(len(p["membri"]) > 0.5 * n_doc), "proposto", modello, time.time(),
                   json.dumps(sorted(p["membri"]), ensure_ascii=False)))
    c.commit()
    esito = f"{len(unite)} temi proposti dal modello per «{radice}»"
    if len(proposte) > len(unite):
        esito += f" ({len(proposte) - len(unite)} uniti ad altri molto simili)"
    avviso(esito)
    archivio.aggiorna_lavoro(id_lavoro, stato="finito", fatti=3, finito=time.time(),
                             messaggio=esito, riga=esito)


def tesauro_della_cartella(radice):
    """Il tesauro dove vanno i temi tenuti: «Temi di …», uno per cartella, in uso lì."""
    c = tesauri.apri()
    nome = f"Temi di «{radice}»"
    r = c.execute("SELECT id FROM tesauri WHERE nome=?", (nome,)).fetchone()
    tid = r["id"] if r else tesauri.nuovo(nome, f"I temi proposti dal modello per «{radice}» e "
                                                "tenuti da te.")
    attivi = tesauri.attivi(radice)
    if tid not in attivi:
        tesauri.imposta(radice, attivi + [tid])
    return tid


def tieni(id_proposta, forme=None):
    """Il tema proposto diventa un tema vero, nel tesauro della cartella. Con
    `forme`, le parole scelte da chi fa la ricerca: tolte quelle sbagliate,
    aggiunte le sue; senza, tutte quelle proposte."""
    c = apri()
    p = c.execute("SELECT * FROM temi_proposti WHERE id=?", (id_proposta,)).fetchone()
    if not p:
        raise ValueError("Non trovo questa proposta.")
    if forme is not None:
        forme = tesauri.pulisci_forme(forme)
        if not forme:
            raise ValueError("Lascia almeno una parola, o scrivine una tua.")
    else:
        forme = [f for f, _ in json.loads(p["forme"] or "[]")]
    tid = tesauro_della_cartella(p["radice"])
    nome = p["nome"]
    esiste = c.execute("SELECT id FROM temi_tesauro WHERE tesauro=? AND nome=?", (tid, nome)).fetchone()
    id_tema = tesauri.salva_tema(tid, nome, forme, esiste["id"] if esiste else None)
    c.execute("UPDATE temi_proposti SET stato='tenuto' WHERE id=?", (id_proposta,))
    c.commit()
    conti = biblioteca.rifai_tema(tid, {nome})
    return tid, id_tema, conti.get(p["radice"], {}).get(nome, 0)


def scarta(id_proposta):
    c = apri()
    c.execute("UPDATE temi_proposti SET stato='scartato' WHERE id=?", (id_proposta,))
    c.commit()
