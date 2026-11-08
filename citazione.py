"""La citazione guardata sull'originale.

Un .md è il PDF già letto, una volta per tutte: è quello che permette di
cercare, perché su un'immagine non si cerca. Ma quando si cita non basta, e
non perché il .md sia meno affidabile del PDF — perché un errore di lettura,
dentro una virgolettatura, non si vede più. Una data letta 1296 invece di
1298 entra nell'articolo e nessuno la ritrova.

Qui la pagina si riapre e si rilegge adesso, guardandola, e le due letture si
mettono una accanto all'altra parola per parola. Costa poco: una pagina a 300
dpi sono circa quattromila gettoni e cinque secondi, e in un articolo le
citazioni sono quaranta, non ventimila. Tutta la cartella guardata così
sarebbero novantanove milioni di gettoni e venti giorni di scheda grafica:
per questo si guarda la pagina che si cita, non la biblioteca.
"""
import difflib
import io
import os
import re

import coppie
import impostazioni
import verifica_numeri

RX_PAROLE = re.compile(r"\S+")


def _parole(testo):
    return RX_PAROLE.findall(testo or "")


def _piatto(p):
    """La parola senza punteggiatura e senza maiuscole, per confrontarla.

    La citazione si copia com'è scritta; il confronto invece deve dire se la
    parola è un'altra parola, non se finisce con la virgola."""
    return re.sub(r"[^\w]", "", p, flags=re.U).lower()


def testo_nel_md(percorso, n):
    """Il testo della pagina n come sta nel .md, o "" se quella pagina non c'è.

    Il .md può non avere quella pagina: succede quando la lettura si era
    fermata, o quando la pagina era senza testo. Chi cita deve saperlo subito,
    perché una pagina che manca in silenzio è il guasto peggiore: il .md dice
    «pagina 500» e sotto non c'è niente, e chi legge crede che la pagina fosse
    bianca. Il 5 novembre 2026 i Regesta di Innocenzo III erano così dalla
    pagina 400 in poi, 598 pagine su 802."""
    md = coppie.md_di(percorso)
    if not md or not os.path.exists(md):
        return ""
    testo = open(md, encoding="utf-8", errors="replace").read()
    return (coppie._pagine_md(testo) or {}).get(n, "").strip()


def _antica(percorso):
    """Il .md di questo PDF viene da una stampa antica, con la s lunga corretta?"""
    import s_lunga
    md = coppie.md_di(percorso)
    if not md or not os.path.exists(md):
        return False
    v = verifica_numeri.carica(md)
    if v is not None and (v.get("conti") or {}).get("stampa_antica"):
        return True
    return s_lunga.antica(md)


def letta_adesso(percorso, n):
    """La pagina n del PDF riletta ora dal modello, guardandola. "" se non si può.

    Su una stampa antica la rilettura si corregge come si corregge quella che
    è finita nel .md: se no il confronto segnala «defcriuere» contro
    «descriuere» a ogni riga, e le differenze vere — una data, un nome —
    si perdono in mezzo alla s lunga."""
    try:
        import fitz
        from PIL import Image
    except Exception:
        return ""
    try:
        d = fitz.open(percorso)
        pix = d[n - 1].get_pixmap(dpi=verifica_numeri.DPI)
        im = Image.open(io.BytesIO(pix.tobytes("png")))
        im.load()
        d.close()
    except Exception:
        return ""
    testo = "\n".join(verifica_numeri._pagina_letta_dal_modello(im))
    if testo and _antica(percorso):
        import s_lunga
        testo = s_lunga.correggi(testo)
    return testo


def _differenze(a, b):
    """Dove le due letture non vanno d'accordo: (quello del .md, quello visto).

    Si confrontano le parole appiattite, ma si restituiscono quelle vere, con
    la punteggiatura: chi guarda deve vedere la parola come la copierebbe."""
    pa, pb = _parole(a), _parole(b)
    m = difflib.SequenceMatcher(None, [_piatto(x) for x in pa], [_piatto(x) for x in pb])
    fuori = []
    for azione, i1, i2, j1, j2 in m.get_opcodes():
        if azione == "equal":
            continue
        fuori.append({"come": azione,
                      "nel_md": " ".join(pa[i1:i2]),
                      "sull_originale": " ".join(pb[j1:j2])})
    return fuori


def _il_brano(testo, brano):
    """Il pezzo di `testo` che corrisponde a `brano`, allargato alle parole intere.

    Chi cita arriva da una ricerca e ha in mano un ritaglio, non la pagina:
    il confronto si fa su quel pezzo, se no ottanta righe di differenze
    nascondono la riga che interessa."""
    if not brano or not testo:
        return testo
    pa, pb = _parole(testo), _parole(brano)
    if not pb:
        return testo
    m = difflib.SequenceMatcher(None, [_piatto(x) for x in pa], [_piatto(x) for x in pb])
    blocchi = [b for b in m.get_matching_blocks() if b.size]
    if not blocchi:
        return testo
    a = min(b.a for b in blocchi)
    z = max(b.a + b.size for b in blocchi)
    return " ".join(pa[max(0, a - 5):z + 5])


def cita(percorso, n, brano=""):
    """La citazione a pagina n, com'è nel .md e com'è sull'originale.

    `brano` è il pezzo che interessa (quello trovato dalla ricerca): se c'è,
    si confronta solo quello. Senza modello si restituisce il solo .md, detto
    chiaramente: meglio una citazione non verificata che si sa tale, che una
    verificata per finta."""
    nel_md = testo_nel_md(percorso, n)
    fuori = {"percorso": percorso, "pagina": n, "nel_md": nel_md,
             "sull_originale": "", "differenze": [], "stato": ""}
    if not (impostazioni.server_ocr() and impostazioni.modello_ocr()):
        fuori["stato"] = "senza modello: la pagina non si è riguardata"
        return fuori
    visto = letta_adesso(percorso, n)
    if not visto:
        fuori["stato"] = "la pagina non si è potuta rileggere"
        return fuori
    if brano:
        nel_md, visto = _il_brano(nel_md, brano), _il_brano(visto, brano)
    fuori["nel_md"], fuori["sull_originale"] = nel_md, visto
    if not nel_md:
        fuori["stato"] = ("questa pagina nel .md non c'è: la citazione viene "
                          "dall'originale, riletto adesso")
        return fuori
    fuori["differenze"] = _differenze(nel_md, visto)
    fuori["stato"] = ("il .md e l'originale dicono la stessa cosa"
                      if not fuori["differenze"]
                      else f"{len(fuori['differenze'])} punti non concordano: "
                           "guarda la pagina qui accanto")
    return fuori
