#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I numeri dei .md, letti due volte.

Un OCR sbaglia poco sulla prosa e molto sui numeri: i romani in maiuscoletto
(«sec. viii» diventa «vin»), le cifre all'antica delle stampe («1ſ» per 15),
i numeri di pagina di un indice, che spariscono in silenzio. Misurato su
quattro pagine vere, 226 numeri: Tesseract ne prende 199–206. GLM-OCR, il
modello di Ollama che «guarda» la pagina, letto riga per riga li prende
tutti — ma ogni tanto inventa («Bulletin of Medieval Languages, 1985», su una
riga che finisce con «Bulletin of») o aggiunge un'asta («IIIII» per IIII).
I due sbagliano in posti diversi. Per questo qui nessuno dei due decide da
solo: la pagina la legge Tesseract (o, se c'è, il testo che il PDF ha già),
le righe con numeri le rilegge GLM-OCR, e un numero è confermato solo se le
due letture concordano. Dove non concordano, la riga del .md porta
[⚠ verificare: …] con le due letture, e il posto esatto — pagina e riquadro —
va nel file .verifica.json accanto al .md, per guardarlo sull'originale.
Nelle prove, nessun numero confermato così era sbagliato.

I PDF nati digitali, con il testo dell'editore, non passano di qui: quel
testo è esatto e non si rilegge.
"""
import base64
import collections
import concurrent.futures
import difflib
import io
import json
import urllib.request
import os
import re
import subprocess
import threading

import archivio
import biblioteca
import estrattori
import tre_letture
import impostazioni
import semantica

DPI = 300
SECONDI_PER_RIGA = 4.0          # GLM-OCR su una riga, senza scheda grafica: 3–9 s; poi vale la misura
# righe da rileggere in una pagina di un libro con note: 30–35 nelle prove
# (Trebbi, Tognetti, Stein, il Pigna); meno nella prosa senza note
RIGHE_CON_NUMERI_PER_PAGINA = 30

RX_ARABO = re.compile(r"\d+")
# Le stampe antiche scrivono gli anni in maiuscoletto, e chi legge la pagina li
# rende minuscoli: «dcclxix» è lo stesso numero di «DCCLXIX». Ignorarli voleva
# dire dare per «non confermata» ogni data del libro. Alle minuscole con l, c,
# d, m si chiedono tre lettere: se no «cc.» (carte) e «cm» diventerebbero numeri.
RX_ROMANO = re.compile(r"(?<![A-Za-z])[IVXLCDM]{2,}(?![A-Za-z])"
                       r"|(?<![A-Za-z])[ivx]{2,}(?![A-Za-z])"
                       r"|(?<![A-Za-z])[ivxlcdm]{3,}(?![A-Za-z])")
VALIDO = re.compile(r"^M{0,4}(CM|CD|D?C{0,4})(XC|XL|L?X{0,4})(IX|IV|V?I{0,4})$")
PAROLE_NON_ROMANE = {"vi", "li", "di", "ci", "mi", "dix", "mix", "vic", "civ", "lid", "mid", "did",
                     # minuscole che diventerebbero numeri validi ma sono parole:
                     # «dii» (gli dèi) e «div.» per divino. Su due milioni e mezzo di
                     # parole erano le uniche otto da escludere.
                     "dii", "div"}


def numeri(testo):
    """I numeri di un testo: cifre arabe e romani di almeno due lettere (IIII
    compreso, come nelle stampe antiche). «vi», «di», «li» sono parole."""
    fuori = RX_ARABO.findall(testo or "")
    for m in RX_ROMANO.findall(testo or ""):
        if m.islower() and m in PAROLE_NON_ROMANE:
            continue
        u = m.upper()
        if VALIDO.match(u) or re.fullmatch(r"[XVI]*IIII", u):
            fuori.append(u)
    return collections.Counter(fuori)


def modello():
    """Il modello della seconda lettura, quella delle righe coi numeri.

    Con `modello_verifica` in `scaffale.ini` si sceglie a mano, ed e quello che
    conviene fare dove c'e un modello grande gia acceso. Misurato sulle dodici
    pagine peggiori del Molin del 1821: con GLM-OCR restavano **62 righe** da
    guardare a mano, col 397B **25**, e il 397B ci mette pure meno (363 secondi
    contro 476), perche GLM-OCR contraddiceva cosi spesso che il terzo giudice
    doveva intervenire settantadue volte invece di ventisette. Su una stampa in
    maiuscoletto GLM-OCR non legge: scrive «ncccxin» per «DCCCXIII», e il suo
    mestiere e contraddire — se contraddice perche non sa leggere, le
    segnalazioni diventano rumore e gli errori veri ci si perdono dentro.

    Vuoto: GLM-OCR dentro Ollama, che su una stampa moderna e svelto e preciso,
    e dove non c'e nemmeno quello, il modello di `server_ocr`."""
    voluto = impostazioni.valore("modello_verifica")
    # niente modelli «:cloud»: tutto deve girare su questo computer
    if voluto and not voluto.endswith(":cloud"):
        return voluto
    return _glm_in_ollama() or impostazioni.modello_ocr() or None


def _glm_in_ollama():
    """Il nome di GLM-OCR dentro Ollama, se c'e. Niente modelli `:cloud`:
    tutto deve girare su questo computer."""
    try:
        return next((m for m in semantica.modelli()
                     if "glm-ocr" in m.lower() and not m.endswith(":cloud")), None)
    except Exception:
        return None


def tipo_pdf(d):
    """nato digitale | scansione con testo | scansione, guardando tre pagine:
    se sono coperte da un'immagine, il PDF è una scansione; se sopra c'è anche
    testo, è l'OCR di qualcun altro (spesso Adobe «Paper Capture»)."""
    immagine = testo = 0
    pagine = sorted({0, d.page_count // 2, d.page_count - 1}) if d.page_count else []
    for i in pagine:
        pg = d[i]
        area = pg.rect.width * pg.rect.height or 1
        coperta = sum((b[2] - b[0]) * (b[3] - b[1]) for b in (x["bbox"] for x in pg.get_image_info()))
        immagine += coperta / area > 0.7
        testo += len(pg.get_text().strip()) > 50
    if immagine * 2 < len(pagine) or not pagine:
        return "nato digitale"
    return "scansione con testo" if testo * 2 >= len(pagine) else "scansione"


def legge_le_pagine():
    """Questo computer ha un modello che guarda le pagine intere?

    Dove c'è, l'OCR che una scansione si porta dentro — quello di Google Books,
    di Adobe «Paper Capture» — non è più la lettura migliore disponibile, ed è
    giusto rileggere la pagina invece di fidarsi. Sulle dodici pagine peggiori
    del Molin del 1821 il testo di Google rendeva 101 numeri romani leggibili,
    il modello 127, e le date che sbagliava le sbagliava in silenzio.

    Prima si rileggeva solo se il PDF sembrava una stampa antica (la s lunga
    letta f): una stampa dell'Ottocento senza s lunga non veniva mai riletta, e
    su una macchina con un modello da 397 miliardi di parametri si teneva l'OCR
    di Google. Costa: una pagina riletta sono decine di secondi invece di uno.
    Chi non vuole spenderli lascia vuoto `server_ocr` in `scaffale.ini`."""
    return bool(impostazioni.server_ocr() and impostazioni.modello_ocr())


# ------------------------------------------------------------- le righe ---

def _righe_tesseract(img, lingue):
    """Le righe di Tesseract, con il riquadro in pixel e il blocco."""
    r = subprocess.run([impostazioni.tesseract(), img, "stdout", "-l", lingue, "--psm", "1", "tsv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "TESSDATA_PREFIX": impostazioni.tessdata()})
    righe = {}
    for l in r.stdout.splitlines()[1:]:
        c = l.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        x, y, w, h = map(int, c[6:10])
        g = righe.setdefault((int(c[2]), int(c[3]), int(c[4])),
                             {"parole": [], "box": [x, y, x + w, y + h], "blocco": int(c[2])})
        g["parole"].append(c[11])
        b = g["box"]
        g["box"] = [min(b[0], x), min(b[1], y), max(b[2], x + w), max(b[3], y + h)]
    return [dict(testo=" ".join(g["parole"]), box=g["box"], blocco=g["blocco"])
            for _, g in sorted(righe.items())]


# ----------------------------------------------- senza Tesseract ---
# Dove Tesseract non c'è (su Linux lo installa l'amministratore, e non sempre
# c'è modo), i riquadri delle righe li dà PaddleOCR, che è già qui come terzo
# giudice e non chiede niente al sistema. Il testo invece, se sul computer c'è
# un modello che guarda le pagine (`server_ocr` in scaffale.ini), lo scrive
# lui: sulla pagina intera legge molto meglio di un ritaglio per volta.
# I riquadri restano quelli di PaddleOCR, perché un modello che guarda la
# pagina dà il testo e non le coordinate, e senza coordinate il
# .verifica.json non può riportare al punto esatto dell'originale.

# Gli esempi dentro l'istruzione non sono un di piu: senza, sulla stessa pagina
# il modello legge benissimo e scrive «Ariftone», e il punteggio contro la
# trascrizione a mano crolla dal 99,8% al 25,5%. Con gli esempi, obbedisce.
ISTRUZIONE_PAGINA = (
    "Trascrivi fedelmente tutto il testo di questa pagina, riga per riga, come e "
    "stampato: una riga di testo per ogni riga della pagina, nello stesso ordine. "
    "ATTENZIONE: se la stampa e antica, la lettera che sembra una f senza traversa e "
    "una s lunga, e va trascritta come s normale: saviezza e non faviezza, Aristone e "
    "non Ariftone, fosse e non foffe, rispose e non rifpofe. La f vera, con la "
    "traversa, resta f. Conserva u e v come sono stampate. "
    "Le cifre e i numeri romani devono essere esatti. "
    "Non aggiungere niente, non spiegare, non correggere, non numerare le righe.")


def _righe_paddle(im):
    """Le righe di PaddleOCR col riquadro, nell'ordine in cui stanno sulla pagina."""
    motore = terzo_giudice()
    if motore is None:
        return []
    try:
        with _SERRATURA_PADDLE:
            esito = motore(im.convert("RGB"))
    except Exception:
        return []
    fuori = []
    for punti, testo in zip(list(esito.boxes if esito.boxes is not None else []), esito.txts or []):
        if not (testo or "").strip():
            continue
        xs = [float(p[0]) for p in punti]
        ys = [float(p[1]) for p in punti]
        fuori.append(dict(testo=testo.strip(), box=[min(xs), min(ys), max(xs), max(ys)], blocco=0))
    return sorted(fuori, key=lambda r: (r["box"][1], r["box"][0]))


# l'ultimo guasto del modello sulla pagina intera, per dirlo a chi si ferma
_ultimo_guasto = [""]


def _pagina_letta_dal_modello(im):
    """La pagina intera, letta dal modello di `server_ocr`. Lista di righe.

    Un modello solo, quello scelto a mano in `scaffale.ini`, perche e il
    migliore che quel computer abbia: su una pagina del Botero, contro la
    verita scritta a mano, il 397B di ALDHI sbaglia una lettera su 170, il
    voto delle tre letture una su 26. Se e spento la pagina resta non letta, e
    chi chiama lo dice: meglio riprovare quando torna che riempire l'archivio
    di letture di due qualita diverse senza che si veda quale."""
    server = impostazioni.server_ocr()
    modello = impostazioni.modello_ocr()
    if not (server and modello):
        return []
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    try:
        testo = biblioteca.scrivi_col_modello({
            "model": modello, "temperature": 0, "max_tokens": 4000,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": ISTRUZIONE_PAGINA},
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}}]}]},
            server=server, openai=True)
    except Exception as guasto:
        # Perche la pagina non si e letta. Prima l'errore spariva qui dentro e
        # chi guardava leggeva soltanto «il modello non risponde», senza sapere
        # se era spento, se la pagina era troppo grande o se era caduta la rete.
        # Trovato il 4 novembre 2026 su D_RamusioRamusio.pdf, che saltava sempre
        # mentre le sue pagine, provate a mano, si leggevano benissimo.
        _ultimo_guasto[0] = f"{type(guasto).__name__}: {guasto}"
        return []
    _ultimo_guasto[0] = ""
    return [r.strip() for r in senza_formule(senza_recinzione(testo)).splitlines()
            if r.strip()]


def testo_della_pagina(im):
    """Il testo di una pagina scansionata, per l'indice.

    La usa l'indicizzazione dove Tesseract non c'e: li servono le parole, non
    i riquadri delle righe, e si risparmia la lettura di PaddleOCR. Stringa
    vuota se il modello non c'e o non risponde."""
    return "\n".join(_pagina_letta_dal_modello(im))


def _sposa(righe, lette):
    """Il testo e quello del modello, i riquadri sono quelli di PaddleOCR.

    Il modello che guarda la pagina scrive bene ma non dice dove: PaddleOCR
    dice dove ma legge peggio. Si scorrono le due letture dall'alto in basso,
    senza mai tornare indietro, e a ogni riga del modello si da il riquadro
    della riga di PaddleOCR che le somiglia di piu. Una riga del modello che
    non trova riscontro tiene il riquadro della vicina: nel .md c'e lo stesso,
    e la verifica dei numeri manda a guardare li intorno invece che altrove."""
    if not lette:
        return righe
    fuori, j = [], 0
    for testo in lette:
        suo = tre_letture._piatto(testo)
        scelta, punteggio = None, 0.0
        for k in range(j, min(j + 4, len(righe))):
            p = difflib.SequenceMatcher(None, suo, tre_letture._piatto(righe[k]["testo"])).ratio()
            if p > punteggio:
                scelta, punteggio = k, p
        if scelta is not None and punteggio >= 0.5:
            fuori.append(dict(righe[scelta], testo=testo))
            j = scelta + 1
        else:
            vicina = righe[min(j, len(righe) - 1)]
            fuori.append(dict(testo=testo, box=list(vicina["box"]), blocco=0))
    return fuori


def _righe_senza_tesseract(im):
    """I riquadri delle righe da PaddleOCR, il testo dal modello.

    PaddleOCR spezza una riga in piu riquadri («Percio» da una parte, il resto
    dall'altra), mentre un modello che guarda la pagina la scrive intera: i
    pezzi si ricuciono prima, se no le due letture non si possono sposare.

    Se il modello e scritto in `scaffale.ini` ma non risponde, la pagina non
    si legge e basta: meglio riprovare quando torna che scrivere un .md col
    solo PaddleOCR, che su una stampa antica prende un terzo delle lettere e
    che poi nessuno distinguerebbe da uno buono."""
    righe = _unisci_fasce(_righe_paddle(im), im.width)
    if not righe:
        return righe
    lette = _pagina_letta_dal_modello(im)
    if not lette and impostazioni.server_ocr() and impostazioni.modello_ocr():
        # Due cose diverse, e qui erano la stessa: il modello spento, e una
        # striscia che non ha niente da leggere. La pagina non si manda intera:
        # `_colonne` la taglia, e l'ultima colonna è spesso il margine. Li
        # PaddleOCR trova un segno o due e il modello, giustamente, non legge
        # niente: Scaffale concludeva «il modello non risponde» e buttava via
        # il documento intero. Trovato il 5 novembre 2026 sul Ramusio, dove
        # ogni pagina ha un margine largo 476 pixel con una riga sola, e il
        # .md non si è mai scritto mentre le stesse pagine, mandate intere a
        # mano, si leggevano benissimo in ventitré secondi.
        # Si grida solo se il modello è caduto davvero (`_ultimo_guasto`), o se
        # la striscia aveva abbastanza righe perche una risposta vuota non si
        # possa spiegare: su tre righe o meno il margine è la spiegazione buona.
        if _ultimo_guasto[0] or len(righe) > 3:
            raise estrattori.Interrotto(
                impostazioni.modello_ocr() + " non risponde"
                + (f" ({_ultimo_guasto[0]})" if _ultimo_guasto[0] else ""))
        return []
    return _sposa(righe, lette)


def _righe_pdf(pg, scala):
    """Le righe del testo che il PDF ha già, con il riquadro portato in pixel."""
    fuori = []
    for bi, b in enumerate(pg.get_text("dict").get("blocks", [])):
        for l in b.get("lines", []):
            t = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
            if t:
                x0, y0, x1, y1 = l["bbox"]
                fuori.append(dict(testo=t, box=[x0 * scala, y0 * scala, x1 * scala, y1 * scala], blocco=bi))
    return fuori


def _unisci_fasce(righe, larghezza):
    """In una tabella l'OCR spezza una riga in pezzi («Del Forte», «cap. III.»,
    «23»): quelli alla stessa altezza diventano una riga sola, letta da sinistra.
    Due colonne di testo invece restano separate: sono larghe tutte e due."""
    fuori = []
    for r in righe:
        x0, y0, x1, y1 = r["box"]
        simile = None
        for f in fuori:
            fx0, fy0, fx1, fy1 = f["box"]
            sovrapposte = min(y1, fy1) - max(y0, fy0) > 0.5 * min(y1 - y0, fy1 - fy0)
            # pezzi di una riga di tabella: almeno uno corto, e poco spazio in mezzo;
            # due colonne di testo hanno righe lunghe, e restano separate
            colonne = (x1 - x0) > 0.3 * larghezza and (fx1 - fx0) > 0.3 * larghezza
            distanza = max(x0 - fx1, fx0 - x1, 0)
            if sovrapposte and not colonne and distanza < 0.12 * larghezza:
                simile = f
                break
        if simile:
            pezzi = sorted(simile["pezzi"] + [(x0, r["testo"])])
            simile["pezzi"] = pezzi
            simile["testo"] = " ".join(t for _, t in pezzi)
            b = simile["box"]
            simile["box"] = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
        else:
            fuori.append(dict(r, pezzi=[(x0, r["testo"])], box=list(r["box"])))
    return fuori


def _ritaglio(riga, righe, margini, altezza):
    """Il riquadro da rileggere: la riga, allargata a destra e a sinistra fino al
    margine (della pagina, o della metà di una doppia pagina) o alla riga più
    vicina alla stessa altezza — così entrano i numeri di pagina di un indice,
    che l'OCR non ha visto, ma non la colonna accanto."""
    x0, y0, x1, y1 = riga["box"]
    sx, dx = margini
    su, giu = max(0, y0 - 4), min(altezza, y1 + 4)
    for r in righe:
        if r is riga:
            continue
        rx0, ry0, rx1, ry1 = r["box"]
        if min(y1, ry1) - max(y0, ry0) > 0.5 * min(y1 - y0, ry1 - ry0):
            if rx0 >= x1:
                dx = min(dx, rx0 - 8)
            elif rx1 <= x0:
                sx = max(sx, rx1 + 8)
        elif min(x1, rx1) > max(x0, rx0):
            # la riga sopra o sotto, nella stessa colonna: nelle righe fitte (un indice,
            # le maiuscole corsive) il riquadro di Tesseract ci entra, e la seconda
            # lettura, che si ferma al primo a capo, leggeva quella. Il ritaglio si
            # ferma a metà strada fra le due righe.
            # solo se si sovrappongono davvero (più di un quarto della riga): nel testo
            # corrente le aste che sfiorano la riga accanto non vanno tagliate
            quarto = 0.25 * (y1 - y0)
            if ry1 <= y1 and ry0 < y0 and ry1 - y0 > quarto:
                su = max(su, (y0 + ry1) // 2)
            elif ry0 >= y0 and ry1 > y1 and y1 - ry0 > quarto:
                giu = min(giu, (y1 + ry0) // 2)
    return (int(sx), int(su), int(dx), int(giu))


def _vicine(riga, righe):
    """Il testo delle righe subito sopra e subito sotto, nella stessa colonna."""
    x0, y0, x1, y1 = riga["box"]
    cy = (y0 + y1) / 2
    stessa = [r for r in righe if r is not riga and r["metà"] == riga["metà"]
              and min(x1, r["box"][2]) > max(x0, r["box"][0])]
    sopra = [r for r in stessa if (r["box"][1] + r["box"][3]) / 2 < cy]
    sotto = [r for r in stessa if (r["box"][1] + r["box"][3]) / 2 > cy]
    vicine = []
    if sopra:
        vicine.append(max(sopra, key=lambda r: r["box"][3])["testo"])
    if sotto:
        vicine.append(min(sotto, key=lambda r: r["box"][1])["testo"])
    return vicine


def _altra_riga(prima, seconda, vicine):
    """La seconda lettura è di un'altra riga? Somiglia poco a quella che doveva
    leggere, e più a una delle vicine."""
    import difflib
    p = tre_letture._piatto
    a, b = p(prima), p(seconda)
    if not a or not b:
        return False
    qui = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    li = max((difflib.SequenceMatcher(None, p(v), b, autojunk=False).ratio() for v in vicine), default=0)
    # «Consiglieri di Prencipi» e «Consiglio de' Dicci» si somigliano a metà: conta
    # che la lettura somigli chiaramente di più alla riga accanto
    return qui < 0.7 and li >= qui + 0.15


# parole che sembrano numeri letti male: «IIO» per 110, «1x» per ix, «τς» per 75
# in una riga latina, lettere e cifre mescolate
RX_SOSPETTO = re.compile(r"(?<!\w)(?:[IlO|]{2,}[.,]?|\d+[a-zA-Z]+|[a-zA-Z]+\d+\w*)(?!\w)|[Ͱ-Ͽ]")
RX_ROMANO_CORTO = re.compile(r"(?<![A-Za-z])[IVXLC](?![A-Za-z])")
# le parole dopo le quali viene un numero: «secolo xi» letto «secolo xr» non
# ha niente che sembri un numero, ma lì un numero ci deve essere
RX_NUMERO_ATTESO = re.compile(
    r"(?i)(?<!\w)(?:sec|secc|secolo|secoli|saec|vol|voll|tomo|cap|capp|lib|libro|reg|filza|busta|"
    r"fasc|doc|ser|serie|anno|t|s|n|nn|p|pp|c|cc|f|ff|fol|ms)\.?\s+\S")


def _inchiostro_non_letto(im, riga, box):
    """Se accanto al testo letto, dentro il riquadro da rileggere, c'è inchiostro
    che l'OCR non ha trascritto: è così che spariscono i numeri di pagina di un
    indice («Dell'Honore cap. I. … 6»), che nessuna parola della riga annuncia."""
    x0, y0, x1, y1 = riga["box"]
    for a, b in ((box[0], x0 - 6), (x1 + 6, box[2])):
        if b - a < 20:
            continue
        pezzo = im.crop((a, y0, b, y1)).convert("L")
        scuri = sum(pezzo.histogram()[:110])
        if scuri > 0.01 * pezzo.width * pezzo.height:
            return True
    return False


def da_rileggere(im, riga, box):
    """Una riga si rilegge se ha numeri, parole che sembrano numeri letti male,
    un romano di una lettera («cap. I»), o inchiostro accanto che l'OCR non ha letto."""
    t = riga["testo"]
    return bool(re.search(r"\d", t) or numeri(t) or RX_SOSPETTO.search(t) or RX_ROMANO_CORTO.search(t)
                or RX_NUMERO_ATTESO.search(t) or _inchiostro_non_letto(im, riga, box))


# Che cosa si chiede a un modello generico, che non sa di essere un OCR.
# GLM-OCR invece ha il suo «Text Recognition:» e non vuole altro. L’avvertenza
# sulla s lunga non e un vezzo: senza, un modello grande legge benissimo e
# scrive «Ariftone» per «Aristone», e il confronto con Tesseract salta.
ISTRUZIONE_RIGA = (
    "Trascrivi questa riga esattamente come e stampata, su una riga sola. "
    "ATTENZIONE: se la stampa e antica, la lettera che sembra una f senza traversa e "
    "una s lunga, e va trascritta come s normale: saviezza e non faviezza, Aristone e "
    "non Ariftone, fosse e non foffe, rispose e non rifpofe. La f vera, con la "
    "traversa, resta f. Conserva u e v come sono stampate. "
    "Le cifre e i numeri romani devono essere esatti. "
    "Non aggiungere niente, non spiegare, non correggere.")


def rileggi(immagine, nome_modello):
    """La seconda lettura di un ritaglio. Si ferma al primo a capo: dopo la riga
    vera il modello tende a ricopiarla o a inventarne il seguito."""
    buf = io.BytesIO()
    immagine.save(buf, format="PNG")
    dato = base64.b64encode(buf.getvalue()).decode()
    # il server di `server_ocr` conosce un modello solo, quello di `modello_ocr`:
    # GLM-OCR invece sta in Ollama, e li va chiesto
    server = impostazioni.server_ocr() if nome_modello == impostazioni.modello_ocr() else ""
    if server:
        testo = biblioteca.scrivi_col_modello({
            "model": nome_modello, "temperature": 0, "max_tokens": 200, "stop": ["\n"],
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": ISTRUZIONE_RIGA},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + dato}}]}]},
            server=server, openai=True)
    else:
        testo = biblioteca.scrivi_col_modello({
            "model": nome_modello, "prompt": "Text Recognition:", "think": False,
            "images": [dato],
            "options": {"temperature": 0, "num_predict": 200, "num_ctx": 4096, "stop": ["\n"]}})
    return senza_formule(senza_recinzione(testo))


RX_APICE = re.compile(r"(?:\$|\\\()\s*\^\s*\{([^}]*)\}\s*(?:\$|\\\))")


RX_RECINZIONE = re.compile(r"^\s*```[A-Za-z0-9_+-]*\s*$")


def senza_recinzione(testo):
    """Toglie la recinzione del codice da una risposta del modello.

    Ogni tanto il modello risponde «```markdown» e poi il testo, o solo la
    recinzione e basta. Trovato il 6 novembre 2026: una riga di CondivisioneMD
    era finita nel .verifica.json come «```markdown», e veniva confrontata con
    le altre due letture come se fosse quello che c'era scritto sulla pagina."""
    righe = (testo or "").splitlines()
    while righe and RX_RECINZIONE.match(righe[0]):
        righe.pop(0)
    while righe and RX_RECINZIONE.match(righe[-1]):
        righe.pop()
    return "\n".join(righe).strip()


def senza_formule(testo):
    """GLM-OCR scrive i richiami di nota come formule, «$ ^{1 4 5} $»: tornano
    un numero solo, «145», se no un richiamo conta come tre numeri."""
    return RX_APICE.sub(lambda m: " " + re.sub(r"\s+", "", m.group(1)), testo)


# Il terzo giudice: PaddleOCR (PP-OCRv5, modello per le lingue latine, attraverso
# RapidOCR). Da solo legge i numeri come Tesseract, e sbaglia in altri posti; ma
# sulle righe dove Tesseract e GLM-OCR non concordano ha dato ragione all'uno o
# all'altro in 29 casi su 36, e tutte e 29 le volte a quello giusto. Non inventa:
# è un OCR classico. Circa 4 secondi a riga. Se non è installato, restano le due letture.
_TERZO = {"motore": None, "provato": False}
# PaddleOCR è un motore solo, condiviso: due filoni che glielo chiedono
# insieme leggono righe mescolate, o lo fanno cadere. Le pagine si leggono
# parecchie insieme (`pagine_insieme`), ma qui si passa uno per volta: sono
# tre secondi su una pagina da sessanta, e non vale il rischio.
_SERRATURA_PADDLE = threading.Lock()


def terzo_giudice():
    if not _TERZO["provato"]:
        _TERZO["provato"] = True
        try:
            import logging
            from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
            _TERZO["motore"] = RapidOCR(params={
                "Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.MOBILE,
                "Rec.lang_type": LangRec.LATIN, "Rec.ocr_version": OCRVersion.PPOCRV5,
                "Rec.model_type": ModelType.MOBILE})
            logging.getLogger("RapidOCR").setLevel(logging.WARNING)
        except Exception:
            _TERZO["motore"] = None
    return _TERZO["motore"]


def _terzo_fuori(immagine):
    """Il terzo giudice che sta dietro una porta, invece che dentro Scaffale.

    `server_terzo` in `scaffale.ini`: un servizio che riceve il PNG di una riga
    e restituisce il testo letto. Serve per usare come arbitro un motore che
    non si puo mettere nell'ambiente di Scaffale — Surya si porta dietro
    PyTorch, transformers e una Pillow diversa, e installarli qui vorrebbe dire
    rischiare di rompere tutto il resto.

    Misurato il 4 novembre 2026 su quindici righe del Molin del 1821 di cui si
    conosce la verita, letta a mano dall'immagine della pagina: Surya legge
    giusti 26 numeri su 39 e scrive otto righe su quindici senza un errore,
    dove PaddleOCR sta a 18 e a una. Sulla riga dove il 397B sbaglia la data
    («MDCCLII» per «MDCCLI») Surya legge giusto."""
    buf = io.BytesIO()
    immagine.convert("RGB").save(buf, format="PNG")
    richiesta = urllib.request.Request(
        impostazioni.valore("server_terzo").rstrip("/") + "/riga",
        data=buf.getvalue(), method="POST", headers={"Content-Type": "image/png"})
    with urllib.request.urlopen(richiesta, timeout=180) as r:
        return r.read().decode("utf-8", "replace").strip()


def terza_lettura(immagine):
    """Il testo di una riga secondo il terzo giudice, o None se non si pronuncia.

    None non vuol dire «la riga e vuota»: vuol dire che l'arbitro non c'e o non
    ha risposto, e allora chi chiama non decide niente e la riga resta da
    verificare."""
    if impostazioni.valore("server_terzo"):
        try:
            return _terzo_fuori(immagine) or None
        except Exception:
            return None
    motore = terzo_giudice()
    if motore is None:
        return None
    try:
        return " ".join(motore(immagine.convert("RGB")).txts or [])
    except Exception:
        return None


def nome_del_terzo():
    """Chi fa da arbitro, per scriverlo nel .md: deve dire il vero."""
    if impostazioni.valore("server_terzo"):
        return impostazioni.valore("nome_terzo") or "il giudice su " + impostazioni.valore("server_terzo")
    return "PaddleOCR (PP-OCRv5 latino)" if terzo_giudice() else ""


RX_UNI = re.compile(r"^(?:I+|1+)$")


# Le lettere di un altro alfabeto. Greco, greco antico e cirillico: sono quelle
# che l'OCR tira fuori quando una lettera latina consumata non la riconosce.
RX_ALTRO_ALFABETO = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff\u0400-\u04ff]")
RX_LATINE = re.compile(r"[A-Za-z\u00c0-\u024f]")


def lettura_sporca(testo):
    """Se una lettura ha lettere di un altro alfabeto appiccicate dove non vanno.

    «3τ Tl Regno di Napoli» non e' greco: e' l'OCR che ha letto «31 Il» su una
    stampa antica e c'e' scivolato dentro una tau. Una lettura cosi' non puo'
    vincere il voto, perche' quello che vince finisce nel .md e li' dentro non
    si vede piu'. Trovato il 6 novembre 2026 guardando le 553 righe decise a
    maggioranza nei primi 51 documenti di CondivisioneMD: due erano cosi'.

    Una riga scritta davvero in greco o in russo si lascia stare: in un libro di
    storia ci sta, ed e' casa sua. Ma dentro una riga latina qualunque lettera
    greca o cirillica e' sporcizia, anche quando sembra una parola.

    Questa seconda meta' della regola e' nata da una verifica andata male. La
    prima stesura segnalava solo la lettera isolata o incollata a lettere
    latine, e lasciava passare i gruppi di due o piu' lettere greche, pensando
    che fossero citazioni. Guardando le 58 righe che lasciava passare in
    CondivisioneMD, non ce n'era una buona: «AA.VV.» letto «ΑΛ.ΝΝ.», «COSIMO
    III» letto «COSIMO πι», «secolo XIII» letto «secolo ΧΙΠΙ». Le maiuscole
    greche sono gemelle delle latine, e una stampa antica consumata le fa
    scambiare a gruppi. Una citazione greca vera, se capita, viene segnata da
    guardare: costa un'occhiata, e l'altro errore costa un .md sbagliato."""
    t = testo or ""
    altre = RX_ALTRO_ALFABETO.findall(t)
    if not altre:
        return False
    # piu' lettere di quell'alfabeto che latine: la riga e' scritta cosi'
    return len(altre) <= len(RX_LATINE.findall(t))


def chi_vince(prima, seconda, terza):
    """(chi ha ragione, perche' no). Il terzo giudice decide fra le prime due.

    Da' ragione a una delle due quando legge i suoi stessi numeri. Ma se la
    lettura che vincerebbe e' sporca non decide nessuno: meglio una riga
    segnata da guardare che una riga sbagliata data per buona."""
    if terza is None:
        return None, "il terzo non ha letto la riga"
    visti = numeri(terza)
    if not visti:
        # due insiemi vuoti si somigliano, ma vuol dire che la riga non l'ha letta
        return None, "il terzo non ha visto numeri"
    if visti == numeri(prima):
        scelta, vincente = "prima", prima
    elif visti == numeri(seconda):
        scelta, vincente = "seconda", seconda
    else:
        return None, "il terzo non da' ragione a nessuno"
    if lettura_sporca(vincente):
        return None, "la lettura che vincerebbe ha lettere di un altro alfabeto"
    return scelta, ""


def solo_i_contro_uno(a, b):
    """Le due letture differiscono soltanto per la I romana letta come 1?

    Nel maiuscoletto delle stampe antiche «n. ɪɪ.» e «n. 11.» sono la stessa
    forma sulla carta. Chi legge il ritaglio di una riga sola non puo
    distinguerli; chi legge la pagina intera si, perche vede come sono scritte
    le altre citazioni intorno — «cap. IV.», «lib. II.» — e capisce che li va un
    numero romano. Quando il disaccordo e tutto qui non si vota: vale la
    lettura della pagina.

    Misurato il 4 novembre 2026 sulle dodici pagine del Molin: senza questa
    regola il voto sceglieva «n. 11.» dove la stampa dice «n. ɪɪ.», ed era
    l'unica delle undici decisioni nuove che risultasse sbagliata."""
    diversi = list((a - b).elements()) + list((b - a).elements())
    return bool(diversi) and all(RX_UNI.match(x) for x in diversi)


def avviso_di(prima, seconda):
    """La nota [⚠ verificare: …] per una riga dove le due letture dei numeri
    non concordano; vuota se concordano."""
    a, b = numeri(prima), numeri(seconda)
    if a == b:
        return ""
    solo_a = sorted((a - b).elements(), key=str)
    solo_b = sorted((b - a).elements(), key=str)
    elenca = lambda xs: ", ".join(f"«{x}»" for x in xs)
    if solo_a and solo_b:
        return f"[⚠ verificare: qui {elenca(solo_a)}, l'altra lettura {elenca(solo_b)}]"
    if solo_b:
        return f"[⚠ verificare: forse manca {elenca(solo_b)}]"
    return f"[⚠ verificare: {elenca(solo_a)} non confermato]"


COLONNA_MINIMA = 0.12      # una colonna è larga almeno il 12% della pagina (un quotidiano ne ha 6-8)
INCHIOSTRO_GOLA = 0.02     # fra due colonne quasi nessuna riga ha inchiostro (2%)


def _colonne(im, a, b):
    """Le colonne di testo fra a e b: le strisce verticali bianche che le separano
    (la «gola»), lunghe quasi quanto la pagina. Una pagina a una colonna sola
    resta intera: le sue righe attraversano il mezzo, e una striscia bianca dall'alto
    in basso non c'è. Si guarda solo il corpo della pagina, senza testatina e piede
    («TAVOLA», «Digitized by Google»), che stanno a cavallo delle colonne."""
    import numpy as np
    g = np.asarray(im.convert("L").crop((a, 0, b, im.height)))
    h, w = g.shape
    if w < 200:
        return [(a, b)]
    corpo = g[int(0.10 * h):int(0.90 * h)] < 140                      # inchiostro
    righe_con_inchiostro = corpo.any(axis=1)
    corpo = corpo[righe_con_inchiostro]
    if len(corpo) < 50:
        return [(a, b)]
    # quante righe di pixel hanno inchiostro in ogni colonna di pixel, un po' sfumato
    densita = np.convolve(corpo.mean(axis=0), np.ones(5) / 5, mode="same")
    vuoto = densita < INCHIOSTRO_GOLA
    gole, x = [], 0
    while x < w:
        if vuoto[x]:
            y = x
            while y < w and vuoto[y]:
                y += 1
            if y - x >= max(6, 0.006 * w):
                gole.append((x, y))
            x = y
        else:
            x += 1
    # i margini bianchi a destra e a sinistra non sono gole: c'è testo da tutte e due le parti
    testo = np.nonzero(~vuoto)[0]
    if not len(testo):
        return [(a, b)]
    sx, dx = testo[0], testo[-1]
    tagli = [(g0 + g1) // 2 for g0, g1 in gole if g0 > sx and g1 < dx]
    strisce, inizio = [], 0
    for t in tagli:
        if t - inizio >= COLONNA_MINIMA * w and dx - t >= COLONNA_MINIMA * w:
            strisce.append((a + inizio, a + t))
            inizio = t
    strisce.append((a + inizio, b))
    return strisce


def _quasi_cifre(righe):
    """Il testo di una colonna è fatto quasi solo di numeri?"""
    t = "".join(r["testo"] for r in righe)
    segni = [c for c in t if not c.isspace()]
    return len(segni) >= 10 and sum(c.isdigit() for c in segni) > 0.5 * len(segni)


def quante_insieme():
    """Quante righe si chiedono al modello nello stesso momento.

    Una per volta il computer sta fermo ad aspettare: misurato il 4 novembre 2026,
    una richiesta al secondo, le schede grafiche a metà e sedici processori che
    non facevano niente. Il server dei modelli le mette in un lotto solo e risponde
    a parecchie nel tempo in cui ne faceva una. Si cambia con `righe_insieme` in
    scaffale.ini; oltre le corsie del server (`--parallel` di llama-server) le
    richieste in più si mettono in coda e non si guadagna più niente.
    Con Ollama, che una per volta ci va comunque, si resta a una."""
    voluto = (impostazioni.valore("righe_insieme") or "").strip()
    if voluto.isdigit() and int(voluto) > 0:
        return int(voluto)
    return 6 if impostazioni.server_ocr() else 1


def _seconde_letture(im, righe, nome_modello, tutte, smetti, n):
    """(riquadri, quali hanno numeri, seconde letture, secondi spesi).

    Prima si prepara il riquadro di ogni riga, poi si chiedono al modello tutte
    le riletture che servono — parecchie in volo insieme, vedi `quante_insieme`.
    Chi si ferma a metà lascia quello che ha già letto: la pagina viene rifatta
    da capo la prossima volta, non c'è niente da salvare a metà."""
    riquadri, coi_numeri = [], []
    for r in righe:
        box = _ritaglio(r, [x for x in righe if x["metà"] == r["metà"]], r["metà"], im.height)
        riquadri.append(box)
        coi_numeri.append(bool(nome_modello) and da_rileggere(im, r, box))

    da_fare = [i for i in range(len(righe))
               if nome_modello and (coi_numeri[i] or tutte)]
    seconde = {}
    if not da_fare:
        return riquadri, coi_numeri, seconde, 0.0

    def una(i):
        r, box = righe[i], riquadri[i]
        try:
            testo = rileggi(im.crop(box), nome_modello)
            if not (testo or "").strip():
                # il ritaglio fermato a metà fra due righe a volte taglia le lettere
                # alte (le iniziali corsive): si riprova col riquadro intero di Tesseract
                x0, y0, x1, y1 = r["box"]
                testo = rileggi(im.crop((box[0], max(0, y0 - 4), box[2], min(im.height, y1 + 4))),
                                nome_modello)
            return testo
        except Exception:
            return None

    import time
    t0 = time.time()
    insieme = min(quante_insieme(), len(da_fare))
    if insieme <= 1:
        for i in da_fare:
            if smetti and smetti():
                raise estrattori.Interrotto(str(n))
            seconde[i] = una(i)
        return riquadri, coi_numeri, seconde, time.time() - t0

    # l'immagine si apre una volta sola qui: i ritagli che seguono stanno su più
    # filoni, e una PIL che si carica da sola mentre la leggono in due dà guai
    im.load()
    fermato = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=insieme) as squadra:
        lavori = {squadra.submit(una, i): i for i in da_fare}
        for finito in concurrent.futures.as_completed(lavori):
            # Una riga annullata torna lo stesso da `as_completed`, e chiederle
            # il risultato alza CancelledError. Prima usciva di qui com’era, e
            # chi l’ha presa l’ha letta come un guasto del documento: il
            # 5 novembre 2026 un «Ferma» ha fatto scrivere «1 non riuscito —
            # errore CancelledError» sui Regesta di Innocenzo III, che invece
            # erano stati soltanto fermati. Si saltano: chi ferma lo sa già.
            if finito.cancelled():
                continue
            seconde[lavori[finito]] = finito.result()
            if not fermato and smetti and smetti():
                fermato = True
                for altro in lavori:
                    altro.cancel()
    if fermato:
        raise estrattori.Interrotto(str(n))
    return riquadri, coi_numeri, seconde, time.time() - t0


def pagina(pg, n, tipo, nome_modello, lingue, smetti=None, tutte=False):
    """Il testo di una pagina, con le righe dai numeri non concordi segnate.
    Restituisce (testo, segnalazioni, righe con numeri, secondi della seconda lettura).

    Con `tutte` (le stampe antiche) GLM-OCR rilegge ogni riga, non solo quelle con
    numeri, e le parole si votano fra le sue letture, quella di Tesseract e il
    testo che il PDF ha già (tre_letture.py)."""
    import tempfile
    import time
    from PIL import Image
    scala = DPI / 72
    pix = pg.get_pixmap(dpi=DPI)
    with tempfile.TemporaryDirectory() as tmp:
        img = os.path.join(tmp, f"p{n}.png")
        pix.save(img)
        im = Image.open(img)
        im.load()
        # una doppia pagina aperta (più larga che alta) si legge in due metà,
        # una dopo l'altra: se no le righe delle due pagine si mescolano
        metà = ([(0, im.width // 2), (im.width // 2, im.width)] if im.width > 1.2 * im.height
                else [(0, im.width)])

        def leggi(a, b, k):
            if tipo == "scansione con testo":
                return [r for r in _righe_pdf(pg, scala) if a <= (r["box"][0] + r["box"][2]) / 2 < b]
            ritaglio = im.crop((a, 0, b, im.height))
            if impostazioni.tesseract():
                parte = os.path.join(tmp, f"p{n}_{k}.png")
                ritaglio.save(parte)
                grezze = _righe_tesseract(parte, lingue)
            else:
                grezze = _righe_senza_tesseract(ritaglio)
            for r in grezze:
                r["box"] = [r["box"][0] + a, r["box"][1], r["box"][2] + a, r["box"][3]]
            return grezze

        # dentro ogni pagina, le colonne (un indice, un quotidiano): si leggono una per
        # volta, se no la riga di sinistra e quella di destra diventano una riga sola
        righe, k = [], 0
        for a, b in metà:
            strisce = _colonne(im, a, b)
            letture = []
            for c0, c1 in strisce:
                letture.append(((c0, c1), leggi(c0, c1, k)))
                k += 1
            # una «colonna» quasi tutta di cifre è la colonna di una tabella: i numeri
            # devono restare sulla riga della loro voce, e la pagina si legge intera
            if len(strisce) > 1 and any(_quasi_cifre(g) for _, g in letture):
                letture = [((a, b), leggi(a, b, k))]
                k += 1
            for (c0, c1), grezze in letture:
                fasce = _unisci_fasce(grezze, c1 - c0)
                for r in fasce:
                    r["metà"] = (c0, c1)
                righe += fasce
    # chi ha letto le righe: il modello che guarda la pagina intera, o Tesseract
    # e il testo che il PDF ha già. Cambia chi vince i pareggi del voto.
    grossa = (tipo != "scansione con testo" and not impostazioni.tesseract()
              and bool(impostazioni.server_ocr() and impostazioni.modello_ocr()))
    fuori, segnalate, con_numeri = [], [], 0
    # il testo che il PDF ha già, riga per riga, per il voto delle stampe antiche
    del_pdf = _righe_pdf(pg, scala) if tutte else []
    # le seconde letture tutte insieme, non una per volta: vedi `quante_insieme`
    riquadri, coi_numeri_di, seconde, secondi = _seconde_letture(
        im, righe, nome_modello, tutte, smetti, n)
    for i, r in enumerate(righe):
        riga = r["testo"]
        box = riquadri[i]
        coi_numeri = coi_numeri_di[i]
        seconda = seconde.get(i)
        if nome_modello and (coi_numeri or tutte):
            # oltre la riga vera il modello inventa: il pezzo in più non conta
            if seconda is not None and len(seconda) > 1.25 * len(riga) + 8:
                seconda = seconda[:len(riga) + 4]
            # ha letto la riga sopra o sotto: quella lettura non vale per questa
            if seconda and _altra_riga(r["testo"], seconda, _vicine(r, righe)):
                seconda = None
                if coi_numeri:
                    codice = f"{n}.{len(segnalate) + 1}"
                    nota = f"[⚠ verificare {codice}: seconda lettura non riuscita]"
                    segnalate.append({"codice": codice, "pagina": n, "box": list(box), "dpi": DPI,
                                      "prima": r["testo"], "seconda": "", "nota": nota,
                                      "stato": "da verificare"})
                    con_numeri += 1
                    fuori.append(f"{riga} {nota}")
                    continue
        if tutte and seconda:
            x0, y0, x1, y1 = r["box"]
            terza = " ".join(q["testo"] for q in del_pdf
                             if y0 <= (q["box"][1] + q["box"][3]) / 2 <= y1
                             and q["box"][0] < x1 and q["box"][2] > x0)
            riga = tre_letture.vota(r["testo"], seconda, terza or None,
                                    prima_migliore=grossa)
        if coi_numeri:
            con_numeri += 1
            if seconda is not None:
                nota = avviso_di(r["testo"], seconda)
                # anche qui la lettura sporca non vince: questa scorciatoia da'
                # ragione a chi ha letto la pagina senza passare dal terzo
                if (nota and solo_i_contro_uno(numeri(r["testo"]), numeri(seconda))
                        and not lettura_sporca(r["testo"])):
                    # la I romana contro la cifra 1: decide chi ha letto la pagina
                    if numeri(riga) != numeri(r["testo"]):
                        riga = r["testo"]
                    segnalate.append({"codice": f"{n}.{len(segnalate) + 1}", "pagina": n,
                                      "box": list(box), "dpi": DPI, "prima": r["testo"],
                                      "seconda": seconda, "stato": "deciso a maggioranza",
                                      "scelta": "prima", "giusto": riga, "nota": "",
                                      "perche": "I romana contro cifra 1: vale la lettura della pagina"})
                    nota = ""
                if nota:
                    # il codice pagina.numero ritrova la riga nel .md, per correggerla
                    codice = f"{n}.{len(segnalate) + 1}"
                    voce = {"codice": codice, "pagina": n, "box": list(box), "dpi": DPI,
                            "prima": r["testo"], "seconda": seconda}
                    # Il terzo giudice: se dà ragione a una delle due, decide lui.
                    # Solo qui, dove le prime due non concordano. Chiamarlo anche
                    # dove concordano — per coprire il caso delle due letture che
                    # vengono dallo stesso modello e sbagliano insieme — è stato
                    # provato il 4 novembre 2026 e fa danni: sulle dodici pagine
                    # del Molin aggiungeva 47 segnalazioni, e guardandole una per
                    # una erano tutte di PaddleOCR che sbaglia (legge la i romana
                    # come 1: «l. c.» diventa «1. c.», «secolo ix» diventa
                    # «secolo 1x»). Su una stampa in maiuscoletto non è un
                    # arbitro abbastanza buono per contraddire chi concorda.
                    terza = terza_lettura(im.crop(box))
                    if terza is not None:
                        voce["terza"] = terza
                    # chi vince lo dice `chi_vince`: da' ragione a una delle due
                    # solo se ne legge i numeri, e mai a una lettura sporca
                    scelta, non_decide = chi_vince(r["testo"], seconda, terza)
                    if scelta:
                        scelta_riga = r["testo"] if scelta == "prima" else seconda
                        # la riga votata parola per parola resta, se ha i numeri decisi
                        if numeri(riga) != numeri(scelta_riga):
                            riga = scelta_riga
                        segnalate.append(dict(voce, stato="deciso a maggioranza", scelta=scelta,
                                              giusto=riga, nota=""))
                    else:
                        voce["perche"] = non_decide
                        nota = nota.replace("[⚠ verificare", f"[⚠ verificare {codice}", 1)
                        riga = f"{riga} {nota}"
                        segnalate.append(dict(voce, nota=nota, stato="da verificare"))
        fuori.append(riga)
    return "\n".join(fuori), segnalate, con_numeri, secondi


def _firma(percorso, antico, lingue, nome_modello):
    """Lo stesso PDF, letto allo stesso modo: se il file cambia, si ricomincia."""
    import hashlib
    st = os.stat(percorso)
    chiave = f"{os.path.abspath(percorso)}|{st.st_size}|{int(st.st_mtime)}|{antico}|{lingue}|{nome_modello}"
    return hashlib.sha1(chiave.encode("utf-8")).hexdigest()[:16]


def quante_pagine_insieme():
    """Quante pagine si leggono nello stesso momento.

    Il tempo di una pagina è quasi tutto il modello che la guarda: misurato il
    5 novembre 2026 su una pagina dello Zorzi, 48 secondi su 62 (il 77%), e il
    processore appena il 6%. Il server però ha otto corsie e ne usava una
    sola, perché le pagine si chiedevano in fila.

    Misurato davvero il 6 novembre 2026 su pagine fitte (il Cozzi, 962 parole a
    pagina), trentadue pagine mai lette prima: una per volta 72,2 s a pagina;
    due 62,4 (1,16 volte); quattro 56,6 (1,28); **otto 35,7 (2,02)**. I
    caratteri letti restano gli stessi (5.900-6.600 a pagina): non legge di
    meno per andare più veloce.

    Qui cade il ragionamento che avevo fatto prima della misura, e vale la pena
    scriverlo: pensavo che otto pagine, facendo ognuna anche le riletture delle
    righe (`righe_insieme`), volessero dire 64 richieste su 8 corsie e si
    accavallassero. Si accavallano, ma è proprio quello che conviene: la coda
    piena tiene il server sempre al lavoro invece di fermo ad aspettare.

    **Sopra otto no.** A sedici le pagine tornano vuote: 376 caratteri a pagina
    invece di 3.878, e 3,8 secondi invece di 23,5 perché non legge niente
    (provato due volte, anche su pagine mai toccate). È lo stesso guaio delle
    pagine vuote del Ramusio: troppe richieste insieme e il server mescola i
    pezzi delle immagini. Otto è il punto in cui va il doppio senza rompersi.

    Si cambia con `pagine_insieme` in scaffale.ini. Senza un modello che guarda
    le pagine si resta a una: lì il tempo è tutto processore, e i filoni si
    darebbero solo fastidio."""
    voluto = (impostazioni.valore("pagine_insieme") or "").strip()
    if voluto.isdigit() and int(voluto) > 0:
        return min(int(voluto), 8)
    return 8 if (impostazioni.server_ocr() and impostazioni.modello_ocr()) else 1


def _gruppo_di_pagine(percorso, numeri, tipo, nome_modello, lingue, smetti, antico):
    """Legge insieme le pagine `numeri` (contate da 1). ({n: esito}, guasto).

    Ogni filone apre il PDF per conto suo: PyMuPDF non si lascia leggere da
    piu` filoni sullo stesso documento aperto, e due che ci frugano insieme
    danno pagine mescolate o cadono.

    Le pagine riuscite si restituiscono anche quando una fallisce: sono minuti
    di modello, e buttarle perché la vicina è andata storta vorrebbe dire
    rileggerle da capo al prossimo giro."""
    fuori, guasto = {}, None
    def una(n):
        d = estrattori._apri(percorso)
        try:
            return pagina(d[n - 1], n, tipo, nome_modello, lingue, smetti, tutte=antico)
        finally:
            d.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(numeri)) as squadra:
        lavori = {squadra.submit(una, n): n for n in numeri}
        for finito in concurrent.futures.as_completed(lavori):
            n = lavori[finito]
            try:
                fuori[n] = finito.result()
            except Exception as g:
                guasto = guasto or g
    return fuori, guasto


def trascrivi(percorso, avviso=print, smetti=None, antico=False):
    """(testo con i segni [[pagina N]], metodo, pagine, segnalazioni, conti)
    di un PDF scansionato o con l'OCR di altri. None se il PDF è nato digitale:
    allora vale il suo testo, e non si rilegge niente.

    Con `antico` — una stampa con la s lunga — si rilegge tutto con Tesseract e
    il dizionario ita_old, anche se il PDF ha già l'OCR di altri (che è proprio
    quello che leggeva «fopra»), e le parole con la s letta f si correggono."""
    import s_lunga
    d = estrattori._apri(percorso)
    try:
        tipo = tipo_pdf(d)
        if tipo == "nato digitale":
            return None
        if antico or (tipo == "scansione con testo" and legge_le_pagine()):
            # «scansione» vuol dire: la pagina la leggiamo noi. Per una stampa
            # antica perché l'OCR di dentro è quello che legge «fopra»; dove
            # c'è un modello che guarda le pagine, perché legge meglio di
            # chiunque abbia fatto l'OCR del PDF anni fa. Il testo di dentro
            # non si butta: con `antico` resta la terza voce del voto.
            tipo = "scansione"
        nome_modello = modello()
        lingue = impostazioni.lingue_ocr() or "eng"
        if antico:
            lingue = s_lunga.lingue_antiche(lingue)
        pezzi, segnalate = [], []
        conti = {"tipo": tipo, "righe_con_numeri": 0, "da_verificare": 0, "secondi_seconda": 0.0,
                 "seconda_lettura": nome_modello or ""}
        # ogni pagina letta si salva subito: un libro di trecento pagine sono ore,
        # e se il computer si spegne a metà si riprende da lì, non da capo
        firma = _firma(percorso, antico, lingue, nome_modello)
        parziale = os.path.join(archivio.DATI, "letture_parziali", firma + ".json")
        fatte = {}
        if os.path.exists(parziale):
            try:
                fatte = json.load(open(parziale, encoding="utf-8"))["pagine"]
                avviso(f"    riprendo da dove ero arrivato: {len(fatte)} pagine già lette")
            except Exception:
                fatte = {}
        # Le pagine si leggono parecchie insieme, non in fila: vedi
        # `quante_pagine_insieme`. Il giro qui sotto resta com’era e trova già
        # pronto quello che il gruppo ha letto, così l’ordine delle pagine nel
        # .md e il segnalibro restano quelli di prima — che è la parte da non
        # rompere: un segnalibro sbagliato fa saltare pagine senza dirlo.
        def _segna():
            os.makedirs(os.path.dirname(parziale), exist_ok=True)
            with open(parziale + ".tmp", "w", encoding="utf-8") as f:
                json.dump({"firma": firma, "pdf": percorso, "pagine": fatte},
                          f, ensure_ascii=False)
            os.replace(parziale + ".tmp", parziale)

        insieme = quante_pagine_insieme()
        mancano = [k + 1 for k in range(d.page_count) if str(k + 1) not in fatte]
        if insieme > 1 and len(mancano) > 1:
            for p0 in range(0, len(mancano), insieme):
                gruppo = mancano[p0:p0 + insieme]
                if smetti and smetti():
                    raise estrattori.Interrotto(percorso)
                avviso(f"    pagine {gruppo[0]}-{gruppo[-1]} di {d.page_count}…")
                letti, guasto = _gruppo_di_pagine(percorso, gruppo, tipo, nome_modello,
                                                  lingue, smetti, antico)
                for n_, esito in letti.items():
                    fatte[str(n_)] = list(esito)
                if letti:
                    _segna()
                if guasto is not None:
                    raise guasto
        for i, pg in enumerate(d):
            if smetti and smetti():
                raise estrattori.Interrotto(percorso)
            if str(i + 1) in fatte:
                testo, s, k, sec = fatte[str(i + 1)]
            else:
                avviso(f"    pagina {i + 1}/{d.page_count}…")
                testo, s, k, sec = pagina(pg, i + 1, tipo, nome_modello, lingue, smetti, tutte=antico)
                fatte[str(i + 1)] = [testo, s, k, sec]
                os.makedirs(os.path.dirname(parziale), exist_ok=True)
                with open(parziale + ".tmp", "w", encoding="utf-8") as f:
                    json.dump({"firma": firma, "pdf": percorso, "pagine": fatte}, f, ensure_ascii=False)
                os.replace(parziale + ".tmp", parziale)
            if antico:
                testo = s_lunga.correggi(testo)
            pezzi.append(f"\n[[pagina {i + 1}]]\n" + testo)
            segnalate += s
            conti["righe_con_numeri"] += k
            conti["secondi_seconda"] += sec
        conti["da_verificare"] = sum(1 for s in segnalate if s["stato"] == "da verificare")
        conti["decise_a_maggioranza"] = sum(1 for s in segnalate if s["stato"] == "deciso a maggioranza")
        conti["terzo_giudice"] = nome_del_terzo()
        if conti["righe_con_numeri"]:
            try:
                archivio._ricorda("verifica_riga", conti["secondi_seconda"], conti["righe_con_numeri"], 5)
            except Exception:
                pass
        # Il .md dichiara come e stato fatto, e deve dire il vero: dove Tesseract
        # manca la pagina l'ha letta qualcun altro, e chi rilegge il file fra un
        # anno deve saperlo senza andare a cercare com'era configurato il computer.
        if tipo != "scansione":
            prima = "testo OCR già nel PDF"
        elif impostazioni.tesseract():
            prima = "Tesseract"
            if antico:
                prima += " col dizionario per le stampe antiche (ita_old)"
        elif impostazioni.server_ocr() and impostazioni.modello_ocr():
            prima = (f"{impostazioni.modello_ocr()} sulla pagina intera, "
                     "riquadri delle righe da PaddleOCR")
        else:
            prima = "PaddleOCR da solo: né Tesseract né un modello che legga le pagine"
        if antico:
            prima += ", s lunga corretta"
            conti["stampa_antica"] = lingue
        metodo = f"{prima} + seconda lettura dei numeri con {nome_modello}" if nome_modello else prima
        conti["_parziale"] = parziale   # si toglie quando il .md è scritto (trascrizioni.trascrivi)
        return "\n".join(pezzi), metodo, d.page_count, segnalate, conti
    finally:
        d.close()


def salva_segnalazioni(dest_md, originale, segnalate, conti):
    """Il file .verifica.json accanto al .md: dove guardare, e che cosa."""
    f = os.path.splitext(dest_md)[0] + ".verifica.json"
    json.dump({"originale": originale, "conti": conti, "righe": segnalate},
              open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return f


def file_verifica(md):
    return os.path.splitext(md)[0] + ".verifica.json"


def carica(md):
    """Le segnalazioni di un .md, o None se non ce ne sono."""
    f = file_verifica(md)
    if not os.path.exists(f):
        return None
    return json.load(open(f, encoding="utf-8"))


def _pezzo_della_pagina(testo, pagina):
    """Da dove a dove, dentro il .md, sta la pagina `pagina`.

    Una riga decisa a maggioranza non ha un `[⚠ verificare …]` da cercare: sta
    nel testo come tutte le altre. Per non correggere la riga sbagliata quando
    le stesse parole tornano altrove nel libro, si guarda solo dentro la pagina
    da cui la riga viene.
    """
    import coppie          # tardi: coppie importa verifica_numeri
    for m in coppie.RX_PAGINA.finditer(testo):
        n = next((g for g in m.groups() if g), None)
        if n and int(n) == pagina:
            dopo = coppie.RX_PAGINA.search(testo, m.end())
            return m.end(), (dopo.start() if dopo else len(testo))
    return 0, len(testo)


def _sostituisci_riga(testo, voce, giusto):
    r"""Rimpiazza nel .md una riga che non ha nota, cercandola per com'e' scritta.

    Nel .md le righe sono ricucite in capoversi, quindi fra una parola e l'altra
    ci puo' essere un ritorno a capo invece di uno spazio: si cerca con `\s+`
    fra le parole. Se non si trova, o se si trova piu' volte nella stessa
    pagina, non si tocca niente e si dice perche'.
    """
    vecchio = " ".join((voce.get("giusto") or voce.get("prima") or "").split())
    if not vecchio:
        raise ValueError("Di questa riga non so che testo cercare nel .md.")
    a, b = _pezzo_della_pagina(testo, voce.get("pagina") or 0)
    rx = re.compile(r"\s+".join(re.escape(x) for x in vecchio.split()))
    trovate = list(rx.finditer(testo, a, b))
    if not trovate:
        raise ValueError("Nel .md questa riga non c'e' piu' com'era: "
                         "forse l'hai gia' corretta a mano.")
    if len(trovate) > 1:
        raise ValueError("Nella pagina %s questa riga compare %d volte uguali: "
                         "correggila a mano, se no non so quale intendi."
                         % (voce.get("pagina"), len(trovate)))
    m = trovate[0]
    return testo[:m.start()] + giusto + testo[m.end():]


def correggi(md, codice, testo_giusto):
    """Mette nel .md la riga come l'hai verificata sull'originale, al posto
    della riga letta e della sua nota [⚠ verificare …], e la segna fatta.

    Nel .md le righe sono state ricucite in capoversi, quindi si cerca la nota
    per il suo codice e, subito prima, il testo della riga: se c'è si
    sostituiscono tutti e due; se no — capita, quando la riga era spezzata da un
    trattino — si sostituisce la sola nota, e il testo giusto va fra parentesi."""
    dati = carica(md)
    voce = next((r for r in (dati or {}).get("righe", []) if r.get("codice") == codice), None)
    if not voce:
        raise ValueError("Non trovo questa riga fra quelle da verificare.")
    testo = open(md, encoding="utf-8").read()
    prima = " ".join(voce["prima"].split())
    giusto = " ".join((testo_giusto or "").split()) or prima
    if not voce.get("nota"):
        # Riga decisa a maggioranza: nel .md non c'e' nessun avviso da cercare.
        # `testo.find("")` tornerebbe 0 e scriverebbe in cima al file.
        testo = _sostituisci_riga(testo, voce, giusto)
    else:
        i = testo.find(voce["nota"])
        if i < 0:
            raise ValueError("Nel .md la nota di questa riga non c'è più: forse l'hai già corretta a mano.")
        inizio = i - len(prima) - 1
        if inizio >= 0 and " ".join(testo[inizio:i].split()) == prima:
            testo = testo[:inizio] + giusto + testo[i + len(voce["nota"]):]
        else:
            testo = testo[:i] + f"[verificato sull'originale: {giusto}]" + testo[i + len(voce["nota"]):]
    open(md, "w", encoding="utf-8").write(testo)
    voce["stato"] = "verificato"
    voce["giusto"] = giusto
    dati["conti"]["da_verificare"] = sum(1 for r in dati["righe"] if r["stato"] == "da verificare")
    json.dump(dati, open(file_verifica(md), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return dati["conti"]["da_verificare"]


def stima(pagine, tipo_scansione=True):
    """Secondi per trascrivere e verificare un PDF di tante pagine."""
    v = archivio.velocita()
    per_riga = v.get("verifica_riga", SECONDI_PER_RIGA)
    ocr = v["ocr"] if tipo_scansione else 0
    return pagine * (ocr + RIGHE_CON_NUMERI_PER_PAGINA * per_riga)
