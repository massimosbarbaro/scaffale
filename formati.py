#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lettori per i formati che un archivio vecchio contiene e che nessuno prevede.

Un archivio di ricerca stratificato negli anni non è fatto di soli PDF. Ci sono
gli `.rtf` degli anni Novanta, i fogli `.xls` degli spogli quantitativi, i
`.csv` esportati da qualche programma, i database `.mdb` di Access con dentro
anni di schedatura, e ogni tanto un `.odt` o un `.pptx`.

Tutti questi si leggono. Le tabelle diventano testo riga per riga, con le
intestazioni di colonna in testa: così cercare «Piran 1387» trova la riga
giusta, e il foglio o la tabella fanno da numero di pagina.

Nessun lettore qui solleva eccezioni verso l'esterno: se un file è illeggibile
lo dice nel metodo, e l'indicizzazione prosegue.
"""
import csv as _csv
import io
import os
import re
import zipfile

LIMITE_RIGHE = 20000        # oltre, un foglio non è più un documento ma un archivio
LIMITE_CELLA = 300


def _cella(v):
    if v is None:
        return ""
    return str(v).strip()[:LIMITE_CELLA]


def _riga(valori):
    return " | ".join(_cella(v) for v in valori).strip(" |")


# ------------------------------------------------------------------- rtf ---

def rtf(percorso):
    """Toglie i comandi di formattazione e restituisce il testo.

    Si prova prima striprtf, che tratta bene le tabelle; se non c'è, resta un
    lettore essenziale, meno fine ma sufficiente per cercare.
    """
    grezzo = open(percorso, encoding="latin-1", errors="replace").read()
    try:
        from striprtf.striprtf import rtf_to_text
        return rtf_to_text(grezzo, errors="ignore"), "rtf"
    except Exception:
        pass
    testo = re.sub(r"\\'([0-9a-fA-F]{2})",
                   lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), grezzo)
    testo = re.sub(r"\\\*\\[a-zA-Z]+[^{}]*", " ", testo)
    testo = re.sub(r"\\[a-zA-Z]+-?\d*[ ]?", " ", testo)
    testo = re.sub(r"[{}]", " ", testo)
    return re.sub(r"[ \t]{2,}", " ", testo), "rtf essenziale"


# ------------------------------------------------------------------- csv ---

def csv_testo(percorso):
    """Intestazioni più righe. Il separatore si indovina, perché non è mai uguale."""
    grezzo = open(percorso, encoding="utf-8", errors="replace").read(400000)
    try:
        dialetto = _csv.Sniffer().sniff(grezzo[:4000], delimiters=";,\t|")
    except Exception:
        class dialetto(_csv.excel):
            delimiter = ";" if grezzo.count(";") > grezzo.count(",") else ","
    righe = list(_csv.reader(io.StringIO(grezzo), dialetto))[:LIMITE_RIGHE]
    if not righe:
        return "", "csv vuoto"
    corpo = [_riga(r) for r in righe[1:] if any(str(x).strip() for x in r)]
    return f"[colonne] {_riga(righe[0])}\n" + "\n".join(corpo), f"csv ({len(corpo)} righe)"


# ----------------------------------------------------------- fogli Excel ---

def xls(percorso):
    """Excel fino al 2003."""
    import xlrd
    # xlrd commenta ad alta voce ogni irregolarità dei file vecchi: qui le sue
    # lamentele finiscono in un secchio, per non sporcare il diario dei lavori.
    libro = xlrd.open_workbook(percorso, on_demand=True, logfile=io.StringIO())
    nomi = libro.sheet_names()
    pezzi, righe_tot = [], 0
    for indice, nome in enumerate(nomi, 1):
        foglio = libro.sheet_by_name(nome)
        pezzi.append(f"\n[[pagina {indice}]]\n[foglio] {nome}")
        for r in range(min(foglio.nrows, LIMITE_RIGHE)):
            riga = _riga(foglio.row_values(r))
            if riga:
                pezzi.append(riga)
                righe_tot += 1
    libro.release_resources()
    return "\n".join(pezzi), f"xls ({len(nomi)} fogli, {righe_tot} righe)"


def xlsx(percorso):
    """Excel moderno, e anche .xlsm."""
    import openpyxl
    libro = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
    nomi = list(libro.sheetnames)
    pezzi, righe_tot = [], 0
    for indice, nome in enumerate(nomi, 1):
        foglio = libro[nome]
        pezzi.append(f"\n[[pagina {indice}]]\n[foglio] {nome}")
        for k, valori in enumerate(foglio.iter_rows(values_only=True)):
            if k >= LIMITE_RIGHE:
                break
            riga = _riga(valori)
            if riga:
                pezzi.append(riga)
                righe_tot += 1
    libro.close()
    return "\n".join(pezzi), f"xlsx ({len(nomi)} fogli, {righe_tot} righe)"


# ------------------------------------------- OpenDocument e presentazioni ---

RX_TAG = re.compile(r"<[^>]+>")
RX_FINE_PARAGRAFO = re.compile(r"</(text:p|text:h|a:p)>", re.I)


def open_document(percorso):
    """.odt, .ods, .odp: dentro sono zip con un content.xml."""
    with zipfile.ZipFile(percorso) as z:
        if "content.xml" not in z.namelist():
            return "", "opendocument senza contenuto"
        x = z.read("content.xml").decode("utf-8", "replace")
    return RX_TAG.sub(" ", RX_FINE_PARAGRAFO.sub("\n", x)), "opendocument"


def pptx(percorso):
    """Una diapositiva per pagina, così il rimando resta verificabile."""
    with zipfile.ZipFile(percorso) as z:
        diapositive = sorted(
            (n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"(\d+)", os.path.basename(n)).group(1)))
        pezzi = []
        for i, n in enumerate(diapositive, 1):
            x = z.read(n).decode("utf-8", "replace")
            pezzi.append(f"\n[[pagina {i}]]\n" + RX_TAG.sub(" ", RX_FINE_PARAGRAFO.sub("\n", x)))
        for n in sorted(x for x in z.namelist() if "notesSlide" in x and x.endswith(".xml")):
            t = z.read(n).decode("utf-8", "replace")
            pezzi.append("\n[note] " + RX_TAG.sub(" ", RX_FINE_PARAGRAFO.sub("\n", t)))
    return "\n".join(pezzi), f"pptx ({len(diapositive)} diapositive)"


# ----------------------------------------------------------- Access .mdb ---

def mdb(percorso):
    """Ogni tabella diventa una pagina: colonne, poi le righe.

    Richiede pyodbc e il driver Access di Microsoft. Dove il driver manca il
    file resta catalogato e il metodo lo dichiara, invece di fingere che sia
    vuoto: un archivio che tace su quello che non ha letto è peggio di uno che
    non l'ha nemmeno guardato.
    """
    try:
        import pyodbc
    except ImportError:
        return mdb_vecchio(percorso, perche="manca pyodbc")
    driver = next((d for d in pyodbc.drivers()
                   if "access" in d.lower() and "mdb" in d.lower()), None)
    if not driver:
        return mdb_vecchio(percorso, perche="manca il driver Access")
    try:
        con = pyodbc.connect(f"DRIVER={{{driver}}};DBQ={os.path.abspath(percorso)};", timeout=20)
    except Exception as exc:
        # I database di Access 97 il driver moderno si rifiuta di aprirli.
        # Sono i piu vecchi, quindi spesso i piu interessanti: si leggono lo stesso.
        return mdb_vecchio(percorso, perche=str(exc)[:80])
    pezzi, righe_tot, tabelle = [], 0, 0
    try:
        nomi = [r.table_name for r in con.cursor().tables(tableType="TABLE")
                if not r.table_name.startswith("MSys")]
        for indice, nome in enumerate(nomi, 1):
            tabelle += 1
            pezzi.append(f"\n[[pagina {indice}]]\n[tabella] {nome}")
            try:
                c2 = con.cursor().execute(f"SELECT * FROM [{nome}]")
            except Exception:
                pezzi.append("(tabella non leggibile)")
                continue
            pezzi.append("[colonne] " + " | ".join(d[0] for d in c2.description))
            for k, r in enumerate(c2):
                if k >= LIMITE_RIGHE:
                    break
                riga = _riga(list(r))
                if riga:
                    pezzi.append(riga)
                    righe_tot += 1
    finally:
        con.close()
    return "\n".join(pezzi), f"mdb ({tabelle} tabelle, {righe_tot} righe)"


def mdb_vecchio(percorso, perche=""):
    """Legge il file di Access direttamente, senza passare da nessun driver.

    Serve in due casi: quando il driver di Microsoft non c'è, e quando c'è ma
    si rifiuta di aprire un database del 1997 — cioè, di regola, il più antico
    e il più interessante dell'archivio.
    """
    try:
        import logging
        from access_parser import AccessParser
    except ImportError:
        return "", f"mdb non apribile ({perche}) e manca access-parser"
    for n in ("access_parser", "access_parser.utils"):
        logging.getLogger(n).setLevel(logging.CRITICAL)
    db = AccessParser(percorso)
    nomi = [t for t in db.catalog if not t.startswith("MSys")]
    pezzi, righe_tot, lette = [], 0, 0
    for indice, nome in enumerate(nomi, 1):
        pezzi.append(f"\n[[pagina {indice}]]\n[tabella] {nome}")
        try:
            tabella = db.parse_table(nome)
        except Exception:
            pezzi.append("(tabella non leggibile)")
            continue
        colonne = list(tabella)
        if not colonne:
            continue
        lette += 1
        pezzi.append("[colonne] " + " | ".join(colonne))
        for k in range(min(len(tabella[colonne[0]]), LIMITE_RIGHE)):
            riga = _riga([tabella[c][k] if k < len(tabella[c]) else "" for c in colonne])
            if riga:
                pezzi.append(riga)
                righe_tot += 1
    return "\n".join(pezzi), f"mdb senza driver ({lette} tabelle, {righe_tot} righe)"


# ------------------------------------------------------------------------ #

LETTORI = {
    ".rtf": rtf,
    ".csv": csv_testo, ".tsv": csv_testo,
    ".xls": xls,
    ".xlsx": xlsx, ".xlsm": xlsx,
    ".odt": open_document, ".ods": open_document, ".odp": open_document,
    ".pptx": pptx,
    ".mdb": mdb, ".accdb": mdb,
}

ESTENSIONI = tuple(LETTORI)


def leggi(percorso):
    """(testo, metodo) — mai un'eccezione verso l'esterno."""
    lettore = LETTORI.get(os.path.splitext(percorso)[1].lower())
    if not lettore:
        return "", "formato ignoto"
    try:
        return lettore(percorso)
    except Exception as exc:
        return "", f"errore {type(exc).__name__}"
