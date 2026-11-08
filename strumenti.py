#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strumenti sull'archivio già indicizzato: doppioni, esportazione, verifica.

Nulla qui cancella niente senza dirlo. Le copie in eccesso si spostano in una
cartella di quarantena dentro Scaffale, non si eliminano: se il criterio ha
sbagliato — e su un archivio vero prima o poi sbaglia — si rimettono a posto.
"""
import csv
import hashlib
import os
import shutil
import time

import archivio

QUI = os.path.dirname(os.path.abspath(__file__))
QUARANTENA = os.path.join(QUI, "quarantena")
ESPORTAZIONI = os.path.join(QUI, "esportazioni")


# ------------------------------------------------------------- doppioni ---

_FIRME = {}          # (percorso, byte, data) -> firma: non si rilegge due volte


def firma_file(percorso):
    """Che cosa c'è dentro il file, byte per byte: dimensione più l'impronta di
    un pezzo all'inizio, uno a metà e uno in fondo. Due file con la stessa firma
    sono lo stesso file; con lo stesso testo e firme diverse sono due file
    diversi — di solito un PDF e la sua versione compressa, con le immagini
    più leggere.

    None se il file non c'è, o se sta solo su OneDrive: leggerlo vorrebbe dire
    scaricarlo, e per una firma non vale la pena.
    """
    try:
        st = os.stat(percorso)
    except OSError:
        return None
    # FILE_ATTRIBUTE_OFFLINE, RECALL_ON_OPEN, RECALL_ON_DATA_ACCESS
    if getattr(st, "st_file_attributes", 0) & (0x1000 | 0x40000 | 0x400000):
        return None
    chiave = (percorso, st.st_size, st.st_mtime_ns)
    if chiave in _FIRME:
        return _FIRME[chiave]
    h, mega = hashlib.md5(), 1 << 16          # tre campioni da 64 KB
    try:
        with open(percorso, "rb") as f:
            for dove in sorted({0, max(0, st.st_size // 2 - mega // 2), max(0, st.st_size - mega)}):
                f.seek(dove)
                h.update(f.read(mega))
    except OSError:
        return None
    _FIRME[chiave] = f"{st.st_size}:{h.hexdigest()}"
    return _FIRME[chiave]


def gruppi_copie():
    """I documenti con lo stesso testo, e dentro ognuno quali sono proprio lo
    stesso file.

    Il testo uguale non basta a dire «copia»: I diarii di Marino Sanuto da
    77 MB e la loro versione compressa da 33 MB hanno le stesse 957 pagine di
    testo, ma non sono lo stesso file, e chi toglie quello grande perde la
    qualità delle immagini. Ogni documento porta con sé:
      firma      — il contenuto byte per byte (None: non l'ho potuto leggere)
      identici   — quanti altri file del gruppo sono proprio questo file
    e ogni gruppo:
      tutti_identici — sono tutti lo stesso file
      ridondanti     — i byte delle copie identiche in più: questi sì sprecati
    """
    c = archivio.apri()
    fuori = []
    for r in c.execute("""SELECT impronta, COUNT(*) n, SUM(byte) b FROM documenti
                          WHERE impronta<>'' GROUP BY impronta HAVING n>1
                          ORDER BY b DESC"""):
        doc = [dict(x) for x in c.execute(
            "SELECT id,percorso,nome,byte,parole,pagine,radice,estensione FROM documenti WHERE impronta=?"
            " ORDER BY LENGTH(nome) DESC, byte DESC", (r["impronta"],))]
        per_firma, misure = {}, {}
        for d in doc:
            try:
                d["misura"] = os.path.getsize(d["percorso"])
            except OSError:
                d["misura"] = None
            misure[d["misura"]] = misure.get(d["misura"], 0) + 1
        for d in doc:
            if d["misura"] is None:
                d["firma"] = None
            elif misure[d["misura"]] == 1:
                # nessun altro ha la sua dimensione: è per forza un file diverso,
                # e non serve leggerlo (né scaricarlo da OneDrive) per saperlo
                d["firma"] = f"{d['misura']}:unica"
            else:
                d["firma"] = firma_file(d["percorso"])
            if d["firma"]:
                per_firma.setdefault(d["firma"], []).append(d)
        for d in doc:
            d["identici"] = len(per_firma[d["firma"]]) - 1 if d["firma"] else 0
        ridondanti = sum(len(uguali[1:]) * (uguali[0]["byte"] or 0) for uguali in per_firma.values())
        # l'impronta guarda l'inizio del testo: un capitolo e il libro intero che
        # comincia con quel capitolo la condividono. Parole e pagine lo tradiscono.
        parole_max = max((d["parole"] or 0) for d in doc)
        pagine_max = max((d["pagine"] or 0) for d in doc if d["estensione"] == ".pdf") \
            if any(d["estensione"] == ".pdf" for d in doc) else 0
        for d in doc:
            d["piu_corto"] = bool(
                (parole_max and (d["parole"] or 0) < 0.98 * parole_max)
                or (d["estensione"] == ".pdf" and pagine_max and (d["pagine"] or 0) < pagine_max))
            d["parole_max"], d["pagine_max"] = parole_max, pagine_max
        fuori.append({"impronta": r["impronta"], "copie": r["n"],
                      "byte": r["b"], "documenti": doc,
                      "tutti_identici": len(per_firma) == 1 and all(d["firma"] for d in doc),
                      "stesso_testo": not any(d["piu_corto"] for d in doc),
                      "ridondanti": ridondanti,
                      "tenere": doc[0]["percorso"] if doc else "",
                      "spostare": [d["percorso"] for d in doc[1:]]})
    return fuori


def _punteggio_da_tenere(d):
    """Meglio il nome più parlante, il formato originale, la cartella meno anonima."""
    p = d["percorso"].lower()
    punti = len(d["nome"])
    if d["estensione"] == ".pdf":
        punti += 40
    for brutta in ("\\pdf_raw\\", "\\pdf_ocr\\", "\\workspace\\", "\\copia", " - copia",
                   "\\backup", "_compressed", "(1)", "(2)"):
        if brutta in p:
            punti -= 60
    return punti


def deduplica(esegui=False, avviso=print):
    """Sposta in quarantena le copie in eccesso. Senza --esegui mostra e basta."""
    gruppi = gruppi_copie()
    spostati, liberati = 0, 0
    for g in gruppi:
        ordinati = sorted(g["documenti"], key=_punteggio_da_tenere, reverse=True)
        tenere, resto = ordinati[0], ordinati[1:]
        avviso(f"\n{tenere['nome'][:70]}  ({g['copie']} file con lo stesso testo)")
        avviso(f"  tengo    {tenere['percorso']}")
        for d in resto:
            if not (d["firma"] and d["firma"] == tenere["firma"]):
                avviso(f"  lascio   {d['percorso']}  — stesso testo, ma è un file diverso")
                continue
            avviso(f"  sposto   {d['percorso']}")
            if esegui and os.path.exists(d["percorso"]):
                rel = os.path.splitdrive(d["percorso"])[1].lstrip("\\/")
                dest = os.path.join(QUARANTENA, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                try:
                    shutil.move(d["percorso"], dest)
                    archivio.apri().execute(
                        "UPDATE documenti SET stato='in_quarantena' WHERE id=?", (d["id"],))
                    spostati += 1
                    liberati += d["byte"]
                except Exception as exc:
                    avviso(f"    non spostato: {type(exc).__name__}")
    if esegui:
        archivio.apri().commit()
        avviso(f"\nSpostati {spostati} file in quarantena, {liberati/1e9:.1f} GB liberati.")
        avviso(f"Sono in {QUARANTENA}: controlla, poi cancella o rimetti a posto.")
    else:
        totale = sum(g["ridondanti"] for g in gruppi)
        avviso(f"\n{len(gruppi)} gruppi · si libererebbero ~{totale/1e9:.1f} GB.")
        avviso("Per farlo davvero: python scaffale.py deduplica --esegui")
    return gruppi


# --------------------------------------------------------- esportazione ---

def esporta(risultati, nome=None, copia_pdf=True, avviso=print):
    """Da una lista di risultati: cartella con i PDF, elenco Markdown e BibTeX."""
    nome = nome or time.strftime("ricerca_%Y%m%d_%H%M")
    base = os.path.join(ESPORTAZIONI, nome)
    os.makedirs(base, exist_ok=True)
    visti = set()
    righe_md, righe_bib = [f"# {nome}\n"], []
    for i, v in enumerate(risultati, 1):
        p = v["percorso"]
        if p in visti:
            continue
        visti.add(p)
        righe_md.append(f"\n## {i}. {v['nome']}")
        righe_md.append(f"*{v.get('radice','')}* · pagina {v.get('pagina','?')} · `{p}`")
        # il ritaglio centrato sulla parola trovata, non l'inizio del frammento:
        # in un elenco da portare altrove conta vedere il punto che è uscito
        if v.get("brano"):
            righe_md.append("\n> " + v["brano"].replace(chr(2), "**").replace(chr(3), "**"))
        elif v.get("testo"):
            righe_md.append(f"\n> …{v['testo'][:700]}…")
        chiave = "".join(ch for ch in os.path.splitext(v["nome"])[0] if ch.isalnum())[:28]
        righe_bib.append("@misc{%s,\n  title = {{%s}},\n  note = {{%s}},\n  file = {{%s}}\n}"
                         % (chiave or f"doc{i}", v["nome"].replace("{", "").replace("}", ""),
                            v.get("radice", ""), p))
        if copia_pdf and p.lower().endswith(".pdf") and os.path.exists(p):
            try:
                shutil.copy2(p, os.path.join(base, os.path.basename(p)))
            except Exception:
                pass
    open(os.path.join(base, "elenco.md"), "w", encoding="utf-8").write("\n".join(righe_md))
    open(os.path.join(base, "riferimenti.bib"), "w", encoding="utf-8").write("\n\n".join(righe_bib))
    with open(os.path.join(base, "elenco.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["nome", "radice", "pagina", "percorso"])
        for v in risultati:
            w.writerow([v["nome"], v.get("radice", ""), v.get("pagina", ""), v["percorso"]])
    avviso(f"Esportati {len(visti)} documenti in {base}")
    return base
