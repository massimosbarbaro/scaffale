#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Il PDF e il suo .md: un documento solo.

Un .md fatto da un PDF è lo stesso testo: non servono due riassunti, né due
righe nell'elenco. Ma bisogna sapere che il .md c'è — e spesso non sta accanto
al PDF: sta in una sottocartella «markdown», con le immagini delle pagine — e
se ci si può fidare. Qui:

- `coppie(docs)`: per ogni PDF di una cartella, il suo .md, cercato accanto, in
  una sottocartella markdown/md/trascrizioni, o altrove nella cartella con lo
  stesso nome (se ce n'è uno solo);
- `qualita(md, …)`: un giudizio — buono, da controllare, da rifare — con i
  motivi scritti: pagine mancanti o vuote rispetto al PDF, testo illeggibile,
  la s lunga letta f («fopra», «quefto»), e se i numeri sono stati letti due
  volte (verifica_numeri.py) o no. Il giudizio si tiene nella base dati e si
  rifà da solo quando il .md cambia.
"""
import json
import os
import re
import unicodedata

import archivio
import estrattori
import verifica_numeri

SOTTOCARTELLE_MD = ("markdown", "md", "trascrizioni", "trascrizione")

SCHEMA = """
CREATE TABLE IF NOT EXISTS qualita_md (
    md TEXT PRIMARY KEY,
    firma TEXT,          -- dimensione e data del .md: se cambiano, il giudizio si rifà
    giudizio TEXT,       -- buono | da controllare | da rifare
    motivi TEXT,         -- JSON: ["…", "…"]
    dati TEXT            -- JSON: i numeri del giudizio
);
"""

# la s lunga delle stampe antiche letta f: parole frequenti che così diventano altre
S_LUNGA = set("""fono fopra fotto effere effendo eflere cofa cofe fua fue fuo fuoi fiano fia ftato
ftata ftati ftate fta ftare quefto quefta quefti quefte queflo cofi cofl fempre fecondo fenza fopra
fignor fignore fignori fignoria fanto fanta fantiffimo pafsato prefente prefenti ftefso fteffo
ftefla fteffa afsai affai mefser meffer mifura parlaffe feguente feguenti fpecie fpefa fpefe
fervitio fervizio fecolo fecoli noftro noftra noftri noftre voftro voftra voftri voftre rifpofta
rifpofte rifpofto giufto giufta giufti giuftitia giuftizia fudetto fudetta fudetti fuddito fudditi
fteffi fteffe ftefsi meffo meffa mefso fiamo fapere faputo fubito ftrada ftimato
fi diffe differo caufa cafa cafe""".split())

# I segni di pagina, in tutte le forme che Scaffale ha usato negli anni. Il
# «## Pagina N» senza «PDF» è quello delle versioni vecchie, con l’intestazione
# in inglese (`title:`, `source_pdf:`): non era nell’elenco, e per 109 .md della
# cartella di Massimo il conto delle pagine veniva zero. Allora il controllo
# «mancano pagine» si saltava in silenzio e il documento passava per «buono»
# senza che nessuno avesse guardato se c’erano tutte. Trovato il 5 novembre 2026.
RX_PAGINA = re.compile(r"^## Pa(?:gina|ge) (?:PDF )?(\d+)|<!-- pagina (\d+) -->|\[\[pagina (\d+)\]\]", re.M)
# Anche il modo di dire «qui non c’era niente da leggere» è cambiato negli anni:
# i .md più vecchi lo scrivono in inglese, e le loro pagine vuote non si
# contavano.
VUOTA = re.compile(r"Nessun testo leggibile|\[OCR non disponibile"
                   r"|\[No extractable text found|\[No text found")


def apri():
    c = archivio.apri()
    c.executescript(SCHEMA)
    return c


def _chiave(nome):
    base = os.path.splitext(os.path.basename(nome))[0]
    base = unicodedata.normalize("NFKD", base)
    base = "".join(ch for ch in base if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", base)


def coppie(docs):
    """{percorso del PDF: percorso del .md} per i documenti di una cartella."""
    md = [d["percorso"] for d in docs if (d.get("estensione") or "").lower() == ".md"]
    per_dove = {(os.path.dirname(p).lower(), _chiave(p)): p for p in md}
    per_nome = {}
    for p in md:
        per_nome.setdefault(_chiave(p), []).append(p)
    fuori = {}
    for d in docs:
        if (d.get("estensione") or "").lower() != ".pdf":
            continue
        pdf = d["percorso"]
        k, cartella = _chiave(pdf), os.path.dirname(pdf)
        trovato = per_dove.get((cartella.lower(), k))
        for sotto in SOTTOCARTELLE_MD:
            trovato = trovato or per_dove.get((os.path.join(cartella, sotto).lower(), k))
        if not trovato and len(per_nome.get(k, [])) == 1:
            trovato = per_nome[k][0]
        if not trovato:
            # un .md appena scritto, non ancora nell'indice
            for c in [cartella] + [os.path.join(cartella, s) for s in SOTTOCARTELLE_MD]:
                p = os.path.join(c, os.path.splitext(os.path.basename(pdf))[0] + ".md")
                if os.path.exists(p):
                    trovato = p
                    break
        if trovato:
            fuori[pdf] = trovato
    return fuori


def md_di(pdf):
    """Il .md di un PDF solo, guardando l'indice della sua cartella."""
    c = archivio.apri()
    r = c.execute("SELECT radice FROM documenti WHERE percorso=?", (pdf,)).fetchone()
    docs = archivio.documenti_di(r["radice"]) if r else [{"percorso": pdf, "estensione": ".pdf"}]
    return coppie(docs).get(pdf)


def _pagine_md(testo):
    """{numero di pagina: testo} secondo i segni di pagina del .md."""
    pezzi = RX_PAGINA.split(testo)
    fuori = {}
    # dopo lo split: [prima, g1, g2, g3, testo, g1, g2, g3, testo, …]
    for i in range(1, len(pezzi) - 3, 4):
        n = next((x for x in pezzi[i:i + 3] if x), None)
        if n:
            fuori[int(n)] = fuori.get(int(n), "") + (pezzi[i + 3] or "")
    return fuori


# Le vocali non sono soltanto quelle latine. Una parola greca o cirillica le
# vocali ce l’ha, ma non queste, e finiva fra le parole strane: il 5 novembre
# 2026 undici documenti in greco, letti benissimo (il 397B scrive
# «ΜΑΡΓΑΡΙΤΑ ΒΟΥΛΓΑΡΟΠΟΥΛΟΥ» giusto), erano giudicati «testo in gran parte
# illeggibile» al 70-82%, e il lavoro se li sarebbe riletti tutti da capo:
# ventisette ore buttate. Peggio: fra quei falsi allarmi spariva il rotto vero,
# il PDF che ha il greco in un font di trent’anni fa e scrive «ȽɏγȽ» dove
# dovrebbe esserci «αρχα».
VOCALI = re.compile(r"[aeiouyαεηιουωаеиоуыэюя]")


def _parola_strana(w):
    """Una «parola» che non è una parola: senza vocali, o con tre lettere uguali
    di fila (i resti di una lettura sporca)."""
    p = unicodedata.normalize("NFKD", w)
    p = "".join(ch for ch in p if not unicodedata.combining(ch)).lower()
    if len(p) < 3:
        return False
    return (not VOCALI.search(p)) or bool(re.search(r"(.)\1\1", p))


def esamina(md, pagine_pdf=None, metodo_pdf=None):
    """Il giudizio su un .md, con i motivi. Non usa la base dati: legge il file."""
    try:
        testo = open(md, encoding="utf-8", errors="replace").read(8_000_000)
    except OSError:
        return {"giudizio": "da rifare", "motivi": ["il file .md non si apre"], "dati": {}}
    pagine = _pagine_md(testo)
    corpo = re.sub(r"\A---\n.*?\n---\n", "", testo, flags=re.S)
    corpo = re.sub(r"!\[[^\]]*\]\([^)]*\)|<!--.*?-->", " ", corpo)
    parole = re.findall(r"[^\W\d_]+", corpo)
    n_par = max(len(parole), 1)
    strane = sum(1 for w in parole if _parola_strana(w))
    lettere = [ch for ch in corpo if ch.isalpha()]
    finte = sum(1 for ch in lettere if 0x180 <= ord(ch) <= 0x2AF)
    s_lunga = sum(1 for w in parole if w.lower() in S_LUNGA)
    vuote = sum(1 for t in pagine.values()
                if VUOTA.search(t) or len(re.findall(r"[^\W_]", re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t))) < 40)
    dati = {"parole": len(parole), "pagine_md": len(pagine), "pagine_pdf": pagine_pdf or 0,
            "pagine_vuote": vuote, "strane_per_cento": round(100 * strane / n_par, 1),
            "lettere_finte_per_cento": round(100 * finte / max(len(lettere), 1), 1),
            "s_lunga_per_mille": round(1000 * s_lunga / n_par, 1)}
    v = verifica_numeri.carica(md)
    rifare, controllare = [], []
    if len(parole) < 50:
        rifare.append("quasi senza testo")
    if pagine_pdf and pagine and len(pagine) < 0.8 * pagine_pdf:
        rifare.append(f"mancano pagine: il .md ne ha {len(pagine)}, il PDF {pagine_pdf}")
    if pagine:
        quota = vuote / len(pagine)
        if quota > 0.3:
            rifare.append(f"{vuote} pagine su {len(pagine)} senza testo leggibile")
        elif quota > 0.1:
            controllare.append(f"{vuote} pagine su {len(pagine)} senza testo leggibile")
    # Un PDF di trent’anni fa il greco lo scrive con un font suo: dentro il file
    # non ci sono lettere greche ma lettere latine strane («ȽɏγȽ» dove si legge
    # «αρχα»), e chi copia il testo del PDF si porta via quelle. Il conto delle
    # parole strane non le vede, perche’ in mezzo qualche lettera greca vera c’e’
    # e la parola sembra normale. Trovato il 5 novembre 2026 su 41583643.pdf, che
    # era scritto nel .md in una lingua che non esiste. Si rilegge dall’immagine.
    if dati["lettere_finte_per_cento"] > 2:
        rifare.append(f"il PDF ha le lettere in un font vecchio "
                      f"({dati['lettere_finte_per_cento']}% di lettere finte): "
                      f"va riletto dall’immagine, non dal testo del PDF")
    if dati["strane_per_cento"] > 12:
        rifare.append(f"testo in gran parte illeggibile ({dati['strane_per_cento']}% di parole strane)")
    elif dati["strane_per_cento"] > 5:
        controllare.append(f"molte parole lette male ({dati['strane_per_cento']}%)")
    if dati["s_lunga_per_mille"] > 8:
        rifare.append(f"la s lunga letta f, di continuo («fopra», «quefto»: "
                      f"{dati['s_lunga_per_mille']} ogni mille parole)")
    elif dati["s_lunga_per_mille"] > 1.5:
        controllare.append(f"la s lunga a volte letta f ({dati['s_lunga_per_mille']} ogni mille parole)")
    if v:
        da = v["conti"].get("da_verificare", 0)
        if da:
            controllare.append(f"numeri letti due volte: {da} righe ancora da verificare")
        dati["numeri"] = "verificati"
    elif metodo_pdf == "pdf" and not re.search(r"(?mi)^metodo:.*(ocr|tesseract)", testo[:2000]):
        dati["numeri"] = "dal testo del PDF"
    else:
        controllare.append("numeri non verificati: date e cifre possono essere sbagliate")
        dati["numeri"] = "non verificati"
    giudizio = "da rifare" if rifare else "da controllare" if controllare else "buono"
    return {"giudizio": giudizio, "motivi": rifare + controllare, "dati": dati}


def qualita(md, pagine_pdf=None, metodo_pdf=None, c=None, pdf=None):
    """Il giudizio, dalla base dati se il .md non è cambiato; se no si rifà.
    Un PDF «con testo» può essere una scansione con l'OCR di qualcun altro: se
    c'è il PDF lo si guarda, e allora i numeri non valgono come del testo
    dell'editore."""
    try:
        st = os.stat(md)
    except OSError:
        return {"giudizio": "da rifare", "motivi": ["il file .md non c'è più"], "dati": {}}
    firma = f"{st.st_size}:{int(st.st_mtime)}:{pagine_pdf or 0}:{metodo_pdf or ''}"
    vj = verifica_numeri.file_verifica(md)
    if os.path.exists(vj):
        firma += f":{int(os.stat(vj).st_mtime)}"
    c = c or apri()
    r = c.execute("SELECT * FROM qualita_md WHERE md=?", (md,)).fetchone()
    if r and r["firma"] == firma:
        return {"giudizio": r["giudizio"], "motivi": json.loads(r["motivi"] or "[]"),
                "dati": json.loads(r["dati"] or "{}")}
    # solo quando il giudizio va rifatto: aprire ogni PDF a ogni pagina costerebbe troppo
    if metodo_pdf == "pdf" and pdf:
        try:
            d = estrattori._apri(pdf)
            if verifica_numeri.tipo_pdf(d) != "nato digitale":
                metodo_pdf = "scansione con testo"
            d.close()
        except Exception:
            metodo_pdf = "sconosciuto"
    q = esamina(md, pagine_pdf, metodo_pdf)
    c.execute("INSERT OR REPLACE INTO qualita_md (md, firma, giudizio, motivi, dati) VALUES (?,?,?,?,?)",
              (md, firma, q["giudizio"], json.dumps(q["motivi"], ensure_ascii=False),
               json.dumps(q["dati"], ensure_ascii=False)))
    c.commit()
    return q


def da_riassumere_della_coppia(pdf_doc, md_percorso):
    """Di una coppia si riassume uno solo: il PDF se ha il testo dell'editore,
    se no il .md, che è il testo che c'è."""
    return pdf_doc["percorso"] if pdf_doc.get("metodo") == "pdf" else md_percorso
