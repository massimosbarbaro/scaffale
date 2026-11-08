#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estrazione del testo dai formati di un archivio di ricerca disordinato.

Tre casi che un archivio vero presenta sempre e che qui vengono trattati:

  1. documenti con testo         pdf con livello testuale, docx, md, txt, html
  2. scansioni mute              pdf di sole immagini: vanno passati all'OCR
  3. testi sparsi in immagini    una cartella di jpg o png, una per pagina, che
                                 insieme formano un solo documento da ricomporre

Il terzo caso è quello che fa perdere più tempo a mano, ed è riconosciuto qui
dal fatto che una cartella contenga molte immagini con numerazione progressiva.
"""
import os
import re
import subprocess
import tempfile
import threading
import zipfile

import formati
import impostazioni

IMMAGINI = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif")
DOCUMENTI = ((".pdf", ".docx", ".doc", ".md", ".txt", ".htm", ".html", ".epub")
             + formati.ESTENSIONI)

RX_NUMERO = re.compile(r"(\d{1,5})")


def _apri(percorso):
    """Windows tronca oltre 260 caratteri: il prefisso esteso li supera."""
    import fitz
    # i PDF un po' rovinati fanno protestare MuPDF a ogni oggetto storto; il
    # testo si legge lo stesso, e le proteste riempirebbero la finestra nera
    fitz.TOOLS.mupdf_display_errors(False)
    try:
        return fitz.open(percorso)
    except Exception:
        return fitz.open("\\\\?\\" + os.path.abspath(percorso))


def leggi_testo(percorso):
    """(testo, metodo, pagine) — senza OCR: solo quello che il file già dichiara."""
    e = os.path.splitext(percorso)[1].lower()
    try:
        if e in (".md", ".txt"):
            return open(percorso, encoding="utf-8", errors="replace").read(), "testo", 1
        if e in (".htm", ".html"):
            g = open(percorso, encoding="utf-8", errors="replace").read()
            g = re.sub(r"(?is)<(script|style).*?</\1>", " ", g)
            return re.sub(r"<[^>]+>", " ", g), "html", 1
        if e == ".docx":
            parti = []
            with zipfile.ZipFile(percorso) as z:
                for n in z.namelist():
                    if re.match(r"word/(document|footnotes|endnotes)\.xml", n):
                        x = z.read(n).decode("utf-8", "replace")
                        parti.append(re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", x)))
            return "\n".join(parti), "docx", 1
        if e == ".epub":
            parti = []
            with zipfile.ZipFile(percorso) as z:
                for n in z.namelist():
                    if n.lower().endswith((".xhtml", ".html", ".htm")):
                        x = z.read(n).decode("utf-8", "replace")
                        parti.append(re.sub(r"<[^>]+>", " ", x))
            return "\n".join(parti), "epub", 1
        if e == ".doc":
            grezzo = open(percorso, "rb").read().decode("latin-1", "replace")
            ripulito = "".join(c if c.isprintable() or c in "\n\t " else " " for c in grezzo)
            return re.sub(r"\s{3,}", " ", ripulito), "doc grezzo", 1
        if e == ".pdf":
            d = _apri(percorso)
            pagine = [p.get_text() for p in d]
            n = d.page_count
            d.close()
            testo = "".join(pagine)
            utili = len(testo.replace(" ", "").replace("\n", ""))
            if utili < 200 * max(n, 1) // 10:
                return "", "scansione", n
            return "\n".join(f"\n[[pagina {i+1}]]\n" + t for i, t in enumerate(pagine)), "pdf", n
        if e in formati.LETTORI:
            testo, metodo = formati.leggi(percorso)
            return testo, metodo, testo.count("[[pagina ") or 1
    except Exception as exc:
        return "", f"errore {type(exc).__name__}", 0
    return "", "formato ignoto", 0


# Il segno di una pagina che nessuno ha letto. Lo cerca `archivio`, per non
# dare per fatta una scansione muta, e `coppie`, per non confrontare un .md
# vuoto con un altro.
NON_LETTA = "[OCR non disponibile"


def _pagina_col_modello(percorso_immagine):
    """La pagina letta dal modello di `server_ocr`, dove Tesseract manca.

    Costa molto piu di Tesseract — decine di secondi invece di uno — ma e la
    differenza fra indicizzare una scansione e lasciarla muta. Vuoto se il
    modello non e configurato o non risponde, e allora lo dice chi chiama."""
    if not (impostazioni.server_ocr() and impostazioni.modello_ocr()):
        return ""
    try:
        from PIL import Image
        import verifica_numeri          # tardi: verifica_numeri importa estrattori
        with Image.open(percorso_immagine) as im:
            return verifica_numeri.testo_della_pagina(im)
    except Exception:
        return ""


def ocr_immagine(percorso_immagine, lingue=None):
    exe = impostazioni.tesseract()
    if not exe:
        # Dove Tesseract non c'e la pagina la legge il modello che guarda le
        # immagini: senza, l'indice si riempirebbe di scansioni mute.
        testo = _pagina_col_modello(percorso_immagine)
        if testo:
            return testo
        return NON_LETTA + ": manca Tesseract e il modello non ha letto la pagina]"
    lingue = lingue or impostazioni.lingue_ocr() or "eng"
    base = os.path.join(tempfile.gettempdir(),
                        f"scaffale_ocr_{os.getpid()}_{threading.get_ident()}")
    res = subprocess.run([exe, percorso_immagine, base, "-l", lingue, "--psm", "1"],
                         env={**os.environ, "TESSDATA_PREFIX": impostazioni.tessdata()},
                         capture_output=True)
    txt = base + ".txt"
    if os.path.exists(txt):
        t = open(txt, encoding="utf-8", errors="replace").read()
        os.remove(txt)
        return t
    return ""


class Interrotto(Exception):
    """Qualcuno ha premuto «Ferma» a metà di un documento."""


def ocr_pdf(percorso, dpi=None, lingue=None, da=None, a=None, smetti=None):
    """Riconosce un PDF di sole immagini, pagina per pagina.

    `smetti`, se c'è, si interroga prima di ogni pagina: un PDF di trecento
    pagine sono dieci minuti buoni, e chi ha premuto «Ferma» non deve
    aspettare che finisca. Il documento lasciato a metà non viene salvato.
    """
    dpi = dpi or impostazioni.dpi_ocr()
    d = _apri(percorso)
    pezzi = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for i, pagina in enumerate(d):
                if da is not None and i < da:
                    continue
                if a is not None and i >= a:
                    break
                if smetti and smetti():
                    raise Interrotto(percorso)
                img = os.path.join(tmp, f"p{i}.png")
                pagina.get_pixmap(dpi=dpi).save(img)
                pezzi.append(f"\n[[pagina {i+1}]]\n" + ocr_immagine(img, lingue))
                os.remove(img)
        n = d.page_count
    finally:
        d.close()
    return "\n".join(pezzi), n


# Cartelle che non contengono ricerca ma programmi, qualunque cosa ci sia dentro.
SALTATE_PER_NOME = ("site-packages", "node_modules", "tessdata")


def da_saltare(genitore, nome):
    """Una sottocartella da non leggere?

    Si saltano le cartelle nascoste e quelle dei programmi. Un ambiente
    Python si riconosce da ciò che contiene — il file pyvenv.cfg, o la
    cartella conda-meta — e non dal nome: saltare per nome ogni «Lib» e ogni
    «Scripts» avrebbe lasciato fuori anche la cartella di trascrizioni di chi
    l'avesse chiamata così. Dentro un ambiente riconosciuto, Lib e Scripts se
    ne vanno con tutto il resto.
    """
    if nome.startswith((".", "__")) or nome.lower() in SALTATE_PER_NOME:
        return True
    percorso = os.path.join(genitore, nome)
    return (os.path.isfile(os.path.join(percorso, "pyvenv.cfg"))
            or os.path.isdir(os.path.join(percorso, "conda-meta")))


def chiave_ordinamento(nome):
    """Ordina p1, p2, p10 come un umano, non come una macchina."""
    pezzi = RX_NUMERO.split(os.path.splitext(nome)[0])
    return [int(x) if x.isdigit() else x.lower() for x in pezzi]


def gruppi_di_immagini(cartella, minimo=3):
    """Cartelle che contengono molte immagini numerate: un testo da ricomporre.

    Restituisce (percorso_cartella, [immagini in ordine]). La soglia evita di
    scambiare per un libro le due o tre figure sparse in una cartella di lavoro.
    """
    trovati = []
    for radice, sottocartelle, file in os.walk(cartella):
        # le stesse cartelle saltate per i documenti: le icone numerate di un
        # programma non sono un libro da riconoscere
        sottocartelle[:] = [d for d in sottocartelle if not da_saltare(radice, d)]
        immagini = [f for f in file if f.lower().endswith(IMMAGINI)]
        if len(immagini) < minimo:
            continue
        # se ci sono anche documenti veri, le immagini sono probabilmente illustrazioni
        documenti = [f for f in file if f.lower().endswith(DOCUMENTI)]
        if documenti:
            continue
        numerate = sum(1 for f in immagini if RX_NUMERO.search(f))
        if numerate < len(immagini) * 0.6:
            continue
        trovati.append((radice, sorted(immagini, key=chiave_ordinamento)))
    return trovati


def _segnalibro_immagini(cartella, immagini):
    """Dove si segna, foto per foto, quello che si è già letto.

    Un libro fotografato sono centinaia di scatti e ore di modello: senza
    segnalibro, un «Ferma» alla foto 824 di 825 buttava via tutto. I PDF il
    segnalibro ce l’hanno da sempre (`verifica_numeri`), le cartelle di foto
    no, e nessuno se n’era accorto perché finora si erano sempre lette fino
    in fondo. Trovato il 5 novembre 2026, prima di leggere 4.358 fotografie di
    quarantatré libri: settanta ore, da non rifare per un’interruzione."""
    import hashlib
    import archivio          # tardi: archivio importa estrattori
    chiave = (os.path.abspath(cartella) + "|" + "|".join(immagini) + "|"
              + (impostazioni.modello_ocr() or "") + "|" + (impostazioni.tesseract() or ""))
    firma = hashlib.md5(chiave.encode("utf-8")).hexdigest()[:16]
    return os.path.join(archivio.DATI, "letture_parziali", "foto_" + firma + ".json"), firma


def quante_foto_insieme():
    """Quante fotografie si chiedono al modello nello stesso momento.

    Come per le pagine dei PDF (`verifica_numeri.quante_pagine_insieme`): il
    tempo è quasi tutto modello, il server ha otto corsie e se ne usava una.
    Con Tesseract, che sta sul processore, si resta a una."""
    voluto = (impostazioni.valore("foto_insieme") or "").strip()
    if voluto.isdigit() and int(voluto) > 0:
        return int(voluto)
    if impostazioni.tesseract():
        return 1
    return 4 if (impostazioni.server_ocr() and impostazioni.modello_ocr()) else 1


def ricomponi_gruppo(cartella, immagini, lingue=None, smetti=None):
    """OCR di una sequenza di immagini come se fosse un unico documento.

    Le foto già lette si ritrovano nel segnalibro e non si rileggono, e si
    chiedono al modello parecchie insieme: vedi `quante_foto_insieme`."""
    import json
    segna, firma = _segnalibro_immagini(cartella, immagini)
    fatte = {}
    if os.path.exists(segna):
        try:
            d = json.load(open(segna, encoding="utf-8"))
            if d.get("firma") == firma:
                fatte = d.get("foto") or {}
        except Exception:
            fatte = {}

    def scrivi_segnalibro():
        os.makedirs(os.path.dirname(segna), exist_ok=True)
        with open(segna + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"firma": firma, "cartella": cartella, "foto": fatte},
                      f, ensure_ascii=False)
        os.replace(segna + ".tmp", segna)

    def una(nome):
        return ocr_immagine(os.path.join(cartella, nome), lingue)

    insieme = quante_foto_insieme()
    mancano = [nome for nome in immagini if nome not in fatte]
    if insieme > 1 and len(mancano) > 1:
        import concurrent.futures
        for i0 in range(0, len(mancano), insieme):
            gruppo = mancano[i0:i0 + insieme]
            if smetti and smetti():
                scrivi_segnalibro()
                raise Interrotto(cartella)
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(gruppo)) as squadra:
                lavori = {squadra.submit(una, nome): nome for nome in gruppo}
                for finito in concurrent.futures.as_completed(lavori):
                    if finito.cancelled():
                        continue
                    try:
                        fatte[lavori[finito]] = finito.result()
                    except Exception:
                        pass
            scrivi_segnalibro()
    pezzi = []
    for i, nome in enumerate(immagini, 1):
        if nome not in fatte:
            if smetti and smetti():
                scrivi_segnalibro()
                raise Interrotto(cartella)
            fatte[nome] = una(nome)
            scrivi_segnalibro()
        pezzi.append(f"\n[[pagina {i}]]\n[[immagine {nome}]]\n" + fatte[nome])
    # il testo è fatto: il segnalibro non serve più
    try:
        os.remove(segna)
    except OSError:
        pass
    return "\n".join(pezzi), len(immagini)
