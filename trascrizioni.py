#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dai PDF ai file .md, con l'avvertenza che meritano.

Una trascrizione automatica è utilissima e sbaglia. Sbaglia poco sulla prosa e
molto sui numeri, perché è lì che i caratteri si somigliano: XVIII e XVIIII
differiscono per un'asta, 23 e 28 per una curva, 4 e 44 per una ripetizione.
Su un documento d'archivio quegli errori diventano date sbagliate in nota.

Perciò ogni file scritto qui porta in testa da dove viene, con che metodo, e
l'avvertenza di verificare cifre e date sull'originale — che resta a un clic,
perché i marcatori di pagina sono conservati.

E se un .md esiste già non viene sovrascritto: viene **collazionato**, e le
divergenze finiscono in un rapporto. È il controllo che serve quando una
trascrizione vecchia ha già prodotto una nota, e non sai se fidartene.
"""
import difflib
import os
import re
import time
import unicodedata

import estrattori
import impostazioni

RX_PAGINA = re.compile(r"\[\[pagina (\d+)\]\]")
RX_IMMAGINE = re.compile(r"\[\[immagine ([^\]]+)\]\]")
RX_SILLABA = re.compile(r"(\w)[-¬]\s*\n\s*(\w)")
RX_NUMERO_SOLO = re.compile(r"^\s*\d{1,4}\s*$")
RX_CIFRA = re.compile(r"\d[\d.,:/]*")


def piatto(s):
    s = unicodedata.normalize("NFKD", s.replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def pulisci(testo):
    """Ricuce le righe spezzate dall'impaginazione, senza perdere i capoversi."""
    testo = testo.replace("\r", "")
    testo = RX_SILLABA.sub(r"\1\2", testo)
    fuori, buffer = [], []

    def scarica():
        if buffer:
            fuori.append(" ".join(buffer))
            buffer.clear()

    for riga in testo.split("\n"):
        r = re.sub(r"[ \t]{2,}", " ", riga.strip())
        m = RX_PAGINA.match(r)
        if m:
            scarica()
            fuori.append(f"\n<!-- pagina {m.group(1)} -->\n")
            continue
        mi = RX_IMMAGINE.match(r)
        if mi:
            scarica()
            fuori.append(f"\n<!-- immagine: {mi.group(1)} -->\n")
            continue
        if not r or RX_NUMERO_SOLO.match(r):
            scarica()
            continue
        buffer.append(r)
        if r.endswith((".", "!", "?", ":", "»", '"', "”")) and len(r) > 40:
            scarica()
    scarica()
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(fuori)).strip()


def testata(percorso, metodo, pagine, caratteri, titolo=None):
    oggi = time.strftime("%Y-%m-%d")
    nome = titolo or os.path.splitext(os.path.basename(percorso))[0]
    avviso = ("trascrizione automatica: prima di citare date, cifre, numeri romani "
              "o elenchi, riaprire l'originale alla pagina indicata")
    return (f"---\n"
            f'titolo: "{nome[:180]}"\n'
            f'originale: "{percorso}"\n'
            f"pagine: {pagine}\n"
            f'metodo: "{metodo}"\n'
            f"caratteri: {caratteri}\n"
            f'trascritto_il: "{oggi}"\n'
            f'avvertenza: "{avviso}"\n'
            f"---\n\n"
            f"# {nome}\n\n"
            f"> **{avviso.capitalize()}.** I commenti `<!-- pagina N -->` segnano "
            f"i cambi di pagina dell'originale.\n\n")


def estrai(percorso, forza_ocr=False, avviso=print, smetti=None, verifica=True, antico=False):
    """(testo grezzo, metodo, pagine, verifica). Fa l'OCR solo se il testo non c'è.

    Con `verifica`, un PDF che non è nato digitale — una scansione, o una
    scansione con l'OCR di qualcun altro sopra — si legge riga per riga e le
    righe con numeri si rileggono con un secondo motore (verifica_numeri.py):
    `verifica` è allora (segnalazioni, conti), se no None."""
    if verifica and percorso.lower().endswith(".pdf"):
        import verifica_numeri
        if verifica_numeri.modello():
            avviso(f"    lettura con la verifica dei numeri di {os.path.basename(percorso)[:50]}…")
            r = verifica_numeri.trascrivi(percorso, avviso=avviso, smetti=smetti, antico=antico)
            if r is not None:
                testo, metodo, pagine, segnalate, conti = r
                return testo, metodo, pagine, (segnalate, conti)
    testo, metodo, pagine = estrattori.leggi_testo(percorso)
    if antico and percorso.lower().endswith(".pdf"):
        # una stampa con la s lunga si rilegge sempre, col dizionario per le stampe antiche
        import s_lunga
        avviso(f"    riconoscimento OCR (stampa antica) di {os.path.basename(percorso)[:50]}…")
        testo, pagine = estrattori.ocr_pdf(percorso, smetti=smetti,
                                           lingue=s_lunga.lingue_antiche(impostazioni.lingue_ocr() or "eng"))
        return s_lunga.correggi(testo), "OCR col dizionario per le stampe antiche, s lunga corretta", pagine, None
    if forza_ocr or metodo == "scansione":
        avviso(f"    riconoscimento OCR di {os.path.basename(percorso)[:50]}…")
        testo, pagine = estrattori.ocr_pdf(percorso, smetti=smetti)
        metodo = "OCR"
    return testo, metodo, pagine, None


def collaziona(md_esistente, testo_nuovo):
    """Che cosa cambia fra una trascrizione già in casa e il testo estratto ora."""
    vecchio = re.sub(r"\A---\n.*?\n---\n", "", md_esistente, flags=re.S)
    a = piatto(re.sub(r"<!--.*?-->", " ", vecchio))
    b = piatto(re.sub(r"\[\[[^\]]+\]\]", " ", testo_nuovo))
    pa, pb = a.split(), b.split()
    somiglianza = difflib.SequenceMatcher(None, a[:60000], b[:60000]).quick_ratio()
    cifre_vecchie = set(RX_CIFRA.findall(vecchio))
    cifre_nuove = set(RX_CIFRA.findall(testo_nuovo))
    return {
        "parole_md": len(pa), "parole_estratte": len(pb),
        "rapporto": round(len(pa) / max(len(pb), 1), 3),
        "somiglianza": round(somiglianza, 3),
        "cifre_solo_nel_md": sorted(cifre_vecchie - cifre_nuove)[:40],
        "cifre_solo_nell_originale": sorted(cifre_nuove - cifre_vecchie)[:40],
    }


def giudizio(c):
    if c["rapporto"] < 0.6 or c["rapporto"] > 1.7:
        return "GRAVE: lunghezze molto diverse"
    if c["somiglianza"] < 0.7:
        return "GRAVE: testi divergenti"
    if len(c["cifre_solo_nel_md"]) > 12:
        return "SOSPETTO: cifre nel .md che nell'originale non ci sono"
    return "coerente"


def _lettere_finte(percorso, pagine=8):
    """Quanta parte delle lettere del testo che il PDF ha dentro non è di
    nessuna lingua: il segno di un font vecchio.

    Un PDF di trent’anni fa il greco lo scrive con un carattere suo. Dentro il
    file non ci sono lettere greche: ci sono lettere latine strane, e chi copia
    il testo si porta via quelle. Nel .md esce «ȽɏγȽɏɜɒȽ» dove sulla carta si
    legge «αρχαιρεσια». Trovato il 5 novembre 2026 su 41583643.pdf, scritto nel
    .md in una lingua che non esiste. Le pagine si prendono sparse per tutto il
    libro, non le prime: in un volume di atti il greco comincia a metà, e
    guardando solo l’inizio il Transcending_Borders sembrava sano."""
    try:
        import fitz
        d = fitz.open(percorso)
    except Exception:
        return False
    try:
        lettere = finte = 0
        tot = d.page_count
        quali = range(tot) if tot <= pagine else [
            i * (tot - 1) // (pagine - 1) for i in range(pagine)]
        for n in quali:
            for ch in d[n].get_text():
                if not ch.isalpha():
                    continue
                lettere += 1
                if 0x180 <= ord(ch) <= 0x2AF:
                    finte += 1
        return lettere > 200 and 100 * finte / lettere > 2
    except Exception:
        return False
    finally:
        d.close()


def trascrivi(percorso, sovrascrivi=False, forza_ocr=False, avviso=print, smetti=None, rifai=False):
    """Scrive il .md accanto al PDF. Se esiste, collaziona invece di sovrascrivere.

    Con `rifai` il .md che c'è — accanto o nella sottocartella markdown — si rifà
    con la verifica dei numeri, nello stesso posto; quello di prima non si
    cancella: diventa «….md.vecchio», e solo quando il nuovo è pronto."""
    if not os.path.exists(percorso):
        return {"percorso": percorso, "esito": "file non trovato"}
    import coppie
    dest = coppie.md_di(percorso) or os.path.splitext(percorso)[0] + ".md"
    esisteva = os.path.exists(dest)
    antico = False
    if rifai:
        sovrascrivi = True
        # il .md di prima aveva la s lunga letta f: si rilegge da stampa antica
        import s_lunga
        antico = esisteva and s_lunga.antica(dest)
    if (sovrascrivi or not esisteva) and not antico:
        # lo dice già il testo che il PDF ha dentro (l'OCR di Google, di Adobe…):
        # meglio saperlo prima che dopo una lettura intera, che sono ore
        import s_lunga
        antico = s_lunga.pdf_antico(percorso)
    # il testo che il PDF ha dentro non sempre si può copiare: se è scritto con
    # un font vecchio sono lettere finte, e allora si guarda l’immagine
    if not forza_ocr and percorso.lower().endswith(".pdf") and _lettere_finte(percorso):
        avviso("    il PDF ha le lettere in un font vecchio: lo leggo dall’immagine…")
        forza_ocr = True

    # un .md che c'è già si collaziona e non si tocca: la verifica dei numeri,
    # che è lenta, lì non serve
    testo, metodo, pagine, verifica = estrai(percorso, forza_ocr, avviso, smetti,
                                             verifica=sovrascrivi or not esisteva, antico=antico)
    # il .md di prima non c'era, o era troppo rovinato per dirlo: se il testo letto
    # ora ha la s lunga letta f, è una stampa antica, e si rilegge come tale
    if (sovrascrivi or not esisteva) and not antico and percorso.lower().endswith(".pdf"):
        import s_lunga
        if s_lunga.per_mille(testo) > s_lunga.SOGLIA_PER_MILLE:
            avviso("    è una stampa antica (la s lunga letta f): la rileggo col dizionario per le stampe antiche…")
            antico = True
            testo, metodo, pagine, verifica = estrai(percorso, forza_ocr, avviso, smetti,
                                                     verifica=True, antico=True)
    if len(testo.strip()) < 100:
        return {"percorso": percorso, "esito": "nessun testo estraibile", "md": None}

    if esisteva and not sovrascrivi:
        try:
            vecchio = open(dest, encoding="utf-8", errors="replace").read()
        except Exception:
            vecchio = ""
        c = collaziona(vecchio, testo)
        return {"percorso": percorso, "md": dest, "esito": "collazionato",
                "giudizio": giudizio(c), **c}

    corpo = pulisci(testo)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    vecchio_md = None
    if rifai and esisteva:
        vecchio_md = dest + ".vecchio"
        k = 2
        while os.path.exists(vecchio_md):
            vecchio_md, k = f"{dest}.vecchio{k}", k + 1
        os.replace(dest, vecchio_md)
    testa = testata(percorso, metodo, pagine, len(corpo))
    esito_v = {}
    parziale = None
    if verifica:
        import verifica_numeri
        segnalate, conti = verifica
        parziale = conti.pop("_parziale", None)
        verifica_numeri.salva_segnalazioni(dest, percorso, segnalate, conti)
        decise = conti.get("decise_a_maggioranza", 0)
        terzo = (f" {decise} dove non concordavano le ha decise una terza lettura "
                 f"({conti['terzo_giudice']}), dando ragione a una delle due;" if decise else "")
        testa += (f"> **Numeri letti due volte.** {conti['righe_con_numeri']} righe con numeri "
                  f"rilette con un secondo motore;{terzo} {conti['da_verificare']} non concordano e sono "
                  f"segnate *[⚠ verificare: …]*: guardale sull'originale.\n\n")
        esito_v = {"righe_con_numeri": conti["righe_con_numeri"], "da_verificare": conti["da_verificare"]}
    open(dest, "w", encoding="utf-8").write(testa + corpo + "\n")
    # il .md è scritto: le pagine salvate una per una non servono più
    if parziale and os.path.exists(parziale):
        os.remove(parziale)
    if vecchio_md:
        esito_v["vecchio"] = vecchio_md
    if antico:
        esito_v["stampa_antica"] = True
    return {"percorso": percorso, "md": dest, "esito": "scritto" if not esisteva else "riscritto",
            "metodo": metodo, "pagine": pagine, "caratteri": len(corpo), **esito_v}


def trascrivi_molti(percorsi, sovrascrivi=False, forza_ocr=False,
                    avviso=print, progresso=None, smetti=None, rifai=False):
    """Un .md per ogni PDF. `smetti`, se c'è, si interroga prima di ogni
    documento: chi ha premuto «ferma» non aspetta la fine dell'elenco."""
    esiti = []
    soli_pdf = [p for p in dict.fromkeys(percorsi)
                if p.lower().endswith((".pdf", ".djvu")) or p.endswith(".immagini")]
    avviso(f"Da trascrivere: {len(soli_pdf)} documenti")
    for i, p in enumerate(soli_pdf, 1):
        if smetti and smetti():
            avviso(f"Fermato: {i - 1} documenti fatti, gli altri la prossima volta.")
            break
        avviso(f"  [{i}/{len(soli_pdf)}] {os.path.basename(p)[:60]}")
        if progresso:
            progresso(i, len(soli_pdf), os.path.basename(p)[:60])
        # Chi legge le pagine con un modello ogni tanto trova il modello muto: un
        # riavvio del server, un momento di troppo carico. Si riprova, con pause
        # che crescono; la pagina da cui ricominciare è segnata, quindi un secondo
        # tentativo riparte da lì e non ricomincia il documento da capo.
        for tentativo, pausa in enumerate((30, 120, 300, 0), 1):
            try:
                esiti.append(trascrivi(p, sovrascrivi, forza_ocr, avviso, smetti, rifai=rifai))
                break
            except estrattori.Interrotto as motivo:
                # Qui dentro finivano due cose diverse: il «Ferma» dell'utente, che
                # deve fermare tutto, e il modello che non risponde su una pagina,
                # che deve far saltare al massimo quel documento. Prima erano la
                # stessa cosa, e un singhiozzo del modello lasciava indietro tutti
                # i documenti che venivano dopo: il lavoro diceva «0 su 6» e
                # passava al passo seguente senza spiegare niente. Trovato il
                # 4 novembre 2026 su sei PDF che non venivano mai trascritti.
                if smetti and smetti():
                    avviso(f"Fermato: {i - 1} documenti fatti, gli altri la prossima volta.")
                    return esiti
                if not pausa:
                    avviso(f"    non riuscito: {motivo} — lo lascio e vado avanti")
                    esiti.append({"percorso": p, "esito": f"non riuscito: {motivo}"})
                    break
                avviso(f"    {motivo} — aspetto {pausa} secondi e riprovo "
                       f"(tentativo {tentativo + 1})")
                for _ in range(pausa):
                    if smetti and smetti():
                        avviso(f"Fermato: {i - 1} documenti fatti, gli altri la prossima volta.")
                        return esiti
                    time.sleep(1)
            except Exception as exc:
                # un guasto di questo documento soltanto: si annota e si va avanti
                esiti.append({"percorso": p, "esito": f"errore {type(exc).__name__}"})
                break
    return esiti


def rapporto(esiti, destinazione=None):
    """Un Markdown con l'esito di tutte le trascrizioni e le collazioni."""
    scritti = [e for e in esiti if e.get("esito") in ("scritto", "riscritto")]
    collaz = [e for e in esiti if e.get("esito") == "collazionato"]
    altri = [e for e in esiti if e not in scritti and e not in collaz]
    fuori = [f"# Trascrizioni — {time.strftime('%d/%m/%Y %H:%M')}\n",
             f"Scritti {len(scritti)} · collazionati {len(collaz)} · "
             f"non riusciti {len(altri)}\n"]
    if scritti:
        fuori.append("\n## Nuovi file .md\n")
        for e in scritti:
            verifica = (f" · {e['da_verificare']} righe con numeri da verificare su "
                        f"{e['righe_con_numeri']}" if "da_verificare" in e else "")
            fuori.append(f"- `{e['md']}` — {e.get('metodo','')}, "
                         f"{e.get('pagine','?')} pagine, {e.get('caratteri',0)} caratteri{verifica}")
    if collaz:
        fuori.append("\n## Già esistenti: collazionati, non toccati\n")
        fuori.append("Il `.md` era già lì. Qui il confronto con il testo estratto ora.\n")
        for e in sorted(collaz, key=lambda x: x.get("somiglianza", 1)):
            fuori.append(f"\n**{os.path.basename(e['md'])}** — {e['giudizio']}")
            fuori.append(f"  \n  md {e['parole_md']} parole · originale {e['parole_estratte']} "
                         f"· rapporto {e['rapporto']} · somiglianza {e['somiglianza']}")
            if e["cifre_solo_nel_md"]:
                fuori.append(f"  \n  cifre nel .md e non nell'originale: "
                             f"{' '.join(e['cifre_solo_nel_md'][:18])}")
            if e["cifre_solo_nell_originale"]:
                fuori.append(f"  \n  cifre nell'originale e non nel .md: "
                             f"{' '.join(e['cifre_solo_nell_originale'][:18])}")
    if altri:
        fuori.append("\n## Non riusciti\n")
        for e in altri:
            fuori.append(f"- `{e['percorso']}` — {e.get('esito')}")
    testo = "\n".join(fuori) + "\n"
    if destinazione:
        os.makedirs(os.path.dirname(destinazione), exist_ok=True)
        open(destinazione, "w", encoding="utf-8").write(testo)
    return testo
