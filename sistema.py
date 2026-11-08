#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema tutta la cartella, con un pulsante solo.

L'ordine conta: prima i .md (crearli dove mancano, rifare quelli da rifare con
la verifica dei numeri), poi l'indice si aggiorna col testo nuovo, poi l'analisi
— temi, gruppi, parole caratteristiche — su quel testo, e solo alla fine i
riassunti, uno per ogni documento (un PDF e il suo .md contano uno), scritti dal
modello che gira sul computer. Fatti nell'ordine sbagliato, i riassunti si
scriverebbero su testi che poi cambiano.

Ogni passo usa le stesse funzioni dei pulsanti che fanno una cosa sola, con
gli stessi controlli. Un solo Ferma: ferma il passo in corso e salta gli altri.
"""
import os
import re
import threading
import time

import archivio
import biblioteca
import coppie
import impostazioni
import s_lunga
import semantica
import trascrizioni
import verifica_numeri

SECONDI_ANALISI = 90
SECONDI_AGGIORNA = 60

# I nomi che un file prende quando è la copia di un altro: Windows ci mette
# «- Copia», i browser «(1)», e «_compressed» lo scrive chi ha rimpicciolito un
# PDF. Fra due esemplari dello stesso testo si tiene l'altro.
RX_SA_DI_COPIA = re.compile(r"(?i)[-–]\s*copia|\bcopy\b|\(\d+\)|_compress")


def _secondi_md(d, antica=False):
    """Quanto costa un .md: con la verifica, una scansione è lunga; un PDF nato
    digitale, che dà il testo dell'editore, è un attimo. Una stampa antica si
    rilegge tutta con l'OCR, anche se il PDF ha già un testo."""
    v = archivio.velocita()
    pagine = d.get("pagine") or 1
    if antica or d.get("stato") == "da_ocr" or d.get("metodo") == "scansione":
        return verifica_numeri.stima(pagine, True) if verifica_numeri.modello() else pagine * v["ocr"]
    # un PDF con il testo: un terzo circa sono scansioni con l'OCR di altri, da rileggere
    return v["pdf"] + (verifica_numeri.stima(pagine, False) / 3 if verifica_numeri.modello() else 0)


def una_copia_sola(pdf, coppia):
    """(quelli da fare, quelli saltati): dei documenti con lo stesso testo se ne
    tiene uno solo.

    Lo stesso libro in archivio sta spesso in due o tre esemplari — l'originale
    e la sua versione compressa, la stessa scansione salvata in due cartelle —
    e fare il .md di ognuno vuol dire leggere due volte le stesse pagine col
    modello. Nella cartella del progetto IV crociata sono 6378 pagine su 28665:
    un quinto del lavoro, e col modello che legge le pagine un quinto di giorni.

    `impronta` è l'md5 del testo, non del file: riconosce anche il PDF
    compresso, che ha lo stesso testo e byte diversi. Chi non ce l'ha — una
    scansione che nessuno ha ancora letto — fa gruppo per conto suo, perché non
    si sa che cosa contenga.

    Si tiene, in quest'ordine: chi ha già un .md verificato (il lavoro fatto
    non si butta), chi ha un .md, chi ha più pagine (una copia troncata non è
    l'esemplare giusto), chi non ha l'aria di essere la copia («- Copia»,
    «(1)», «_compressed»), e infine chi ha il nome più lungo — perché
    «Davis_2006_ByzantineReliefIconsin Venice.pdf» dice autore, anno e titolo
    mentre «855465-1217878.pdf» è quello che ha deciso un sito di scaricamento.
    A parità vince il primo in ordine alfabetico, così la scelta non cambia da
    una volta all'altra."""
    gruppi, soli = {}, []
    for d in pdf:
        if d.get("impronta"):
            gruppi.setdefault(d["impronta"], []).append(d)
        else:
            soli.append(d)

    def peso(d):
        md = coppia.get(d["percorso"])
        verificato = bool(md and os.path.exists(verifica_numeri.file_verifica(md)))
        nome = os.path.basename(d["percorso"])
        return (verificato, bool(md), d.get("pagine") or 0,
                not RX_SA_DI_COPIA.search(nome), len(nome), [-ord(ch) for ch in d["percorso"]])

    tenuti, saltati = list(soli), []
    for g in gruppi.values():
        if len(g) == 1:
            tenuti.append(g[0])
            continue
        ordinati = sorted(g, key=peso, reverse=True)
        tenuti.append(ordinati[0])
        saltati += ordinati[1:]
    tenuti.sort(key=lambda d: d["percorso"])
    return tenuti, saltati


def messi_da_parte():
    """I documenti che non si devono fare, scritti in `scaffale.ini`.

    `metti_da_parte` è un elenco di nomi di file separati da virgola. Serve
    quando un documento c’è, si potrebbe fare, ma oggi non interessa e la sua
    lettura porterebbe via la macchina per ore: il Ramusio delle
    «Navigationi et viaggi» sono 558 pagine, quasi dieci ore, e intanto non si
    farebbe nient’altro. Messo da parte, non sparisce e non si cancella: resta
    nella cartella e nell’indice, e il pannello dice che c’è e che è fuori."""
    voluto = (impostazioni.valore("metti_da_parte") or "").strip()
    return {n.strip().lower() for n in voluto.split(",") if n.strip()}


def _coi_modelli_di_prima(v):
    """Vero se i numeri li ha controllati roba che adesso non c’è più.

    Un .md controllato con un modello più debole, o senza il terzo giudice, il
    .verifica.json ce l’ha: passava per «verificato» e nessuno lo rifaceva mai
    più. Ma le sue righe segnalate sono molte di più, e non perché le righe
    siano difficili: senza un terzo che voti, due letture che non vanno
    d’accordo restano lì e le deve guardare una persona. Sulle dodici pagine
    peggiori del Molin, GLM-OCR lasciava 62 righe da guardare e il 397B 25
    (vedi `verifica_numeri.modello`). Trovato il 5 novembre 2026: cinque
    documenti letti con GLM-OCR e senza giudice tenevano 1127 righe da guardare
    a mano, più di metà di tutta la cartella.
    """
    if not v:
        return False
    conti = v.get("conti") or {}
    atteso = verifica_numeri.modello()
    if conti.get("seconda_lettura") and atteso and conti["seconda_lettura"] != atteso:
        return True
    # il giudice c’è adesso, ma quando si è letto quel documento non c’era
    return bool(verifica_numeri.nome_del_terzo()) and not conti.get("terzo_giudice")


def piano(radice):
    """Che cosa c'è da fare in una cartella, e quanto ci vorrà, voce per voce."""
    docs = archivio.documenti_di(radice)
    coppia = coppie.coppie(docs)
    per = {d["percorso"]: d for d in docs}
    mancanti, da_rifare, non_verificati = [], [], []
    antiche = set()
    c = coppie.apri()
    # le copie dello stesso testo si contano una volta sola: il .md lo si fa
    # per il documento, non per ogni esemplare che se ne possiede
    soli, saltati = una_copia_sola([d for d in docs if d["estensione"] == ".pdf"], coppia)
    fuori_nomi = messi_da_parte()
    da_parte = [d for d in soli if os.path.basename(d["percorso"]).lower() in fuori_nomi]
    soli = [d for d in soli if d not in da_parte]
    for d in soli:
        md = coppia.get(d["percorso"])
        if not md:
            mancanti.append(d["percorso"])
            continue
        q = coppie.qualita(md, d["pagine"], d["metodo"], c, pdf=d["percorso"])
        if q["giudizio"] == "da rifare":
            # già rifatto da Scaffale (ha il .verifica.json): rifarlo di nuovo
            # darebbe lo stesso testo — e un lavoro fermato a metà, ripreso, non
            # ricomincia da capo. Salvo una stampa antica letta prima che ci
            # fosse il dizionario ita_old: quella si rilegge col dizionario nuovo.
            s = q["dati"].get("s_lunga_per_mille", 0)
            v = verifica_numeri.carica(md)
            if v is not None and (v.get("conti", {}).get("stampa_antica") or s <= s_lunga.SOGLIA_PER_MILLE):
                continue
            if s > s_lunga.SOGLIA_PER_MILLE:
                antiche.add(d["percorso"])
            da_rifare.append(d["percorso"])
        elif q["dati"].get("numeri") == "non verificati":
            non_verificati.append(d["percorso"])
        elif _coi_modelli_di_prima(verifica_numeri.carica(md)):
            # controllato sì, ma con modelli che adesso non ci sono più: si rifà
            non_verificati.append(d["percorso"])
    # davanti quelli già controllati con modelli di prima: il loro .md c’è e si
    # legge, ma le righe segnate sono molte e quasi tutte per niente, e finché
    # non si rifanno chi guarda non sa quali siano i dubbi veri. Gli altri non
    # hanno nessun controllo e possono aspettare il loro turno.
    non_verificati.sort(key=lambda x: verifica_numeri.carica(coppia.get(x)) is None)
    riassunti = biblioteca.da_riassumere(radice)
    v_r = archivio.velocita()["riassunto"]
    return {
        "md_mancanti": {"percorsi": mancanti, "secondi": sum(_secondi_md(per[p]) for p in mancanti)},
        "md_da_rifare": {"percorsi": da_rifare, "antiche": len(antiche),
                         "secondi": sum(_secondi_md(per[p], p in antiche) for p in da_rifare)},
        "md_non_verificati": {"percorsi": non_verificati,
                              "secondi": sum(_secondi_md(per[p]) for p in non_verificati)},
        "messi_da_parte": {"quanti": len(da_parte),
                           "pagine": sum(d.get("pagine") or 0 for d in da_parte),
                           "nomi": [os.path.basename(d["percorso"]) for d in da_parte]},
        "copie_saltate": {"quanti": len(saltati),
                          "pagine": sum(d.get("pagine") or 0 for d in saltati),
                          "percorsi": [d["percorso"] for d in saltati]},
        "analisi": {"secondi": SECONDI_AGGIORNA + SECONDI_ANALISI},
        # dopo i .md nuovi i documenti da riassumere possono cambiare: è una stima
        "riassunti": {"quanti": len(riassunti), "secondi": len(riassunti) * v_r},
        "modello": bool(semantica.acceso() and biblioteca._modello_per_riassunti()),
        "verifica": bool(verifica_numeri.modello()),
    }


def esegui(id_lavoro, radice, scelte, registra_filo=None):
    """Tutti i passi scelti, in ordine. `scelte`: md_mancanti, md_da_rifare,
    md_non_verificati, analisi, riassunti (vero o falso).
    `registra_filo(id)`: per far sapere a chi guarda che il passo è vivo."""
    t0 = time.time()
    voce = next((r for r in archivio.radici() if r["radice"] == radice), None)
    p = piano(radice)
    passi = [k for k in ("md_mancanti", "md_da_rifare", "md_non_verificati", "analisi", "riassunti")
             if scelte.get(k)]
    fatto = []
    corrente = {"id": None, "vivo": True}

    def fermato():
        return archivio.da_fermare(id_lavoro)

    # il Ferma del lavoro grande arriva anche al lavoro del passo in corso
    def guardiano():
        while corrente["vivo"]:
            if corrente["id"] and fermato():
                archivio.ferma(corrente["id"])
            time.sleep(2)
    threading.Thread(target=guardiano, daemon=True).start()

    def scrivi(k, messaggio):
        archivio.aggiorna_lavoro(id_lavoro, totale=len(passi), fatti=k, messaggio=messaggio, riga=messaggio)

    def nuovo_passo(tipo, cartella=""):
        corrente["id"] = archivio.nuovo_lavoro(tipo, cartella, radice)
        if registra_filo:
            registra_filo(corrente["id"])
        return corrente["id"]

    try:
        for i, passo in enumerate(passi):
            if fermato():
                break
            if passo in ("md_mancanti", "md_da_rifare", "md_non_verificati"):
                percorsi = p[passo]["percorsi"]
                if not percorsi:
                    continue
                nome = {"md_mancanti": "i .md che mancano", "md_da_rifare": "i .md da rifare",
                        "md_non_verificati": "i .md con i numeri non verificati"}[passo]
                scrivi(i, f"{nome}: {len(percorsi)} PDF")

                def avanza(n, tot, file, nome=nome, i=i):
                    scrivi(i, f"{nome}: {n} di {tot} — {file}")
                # gli avvisi si buttavano via tutti, e i guasti sparivano con loro:
                # il 4 novembre 2026 un documento saltava ogni volta e nel registro
                # non c'era una riga che dicesse perche. Quelli che contano si scrivono.
                def dillo(r):
                    if any(k in r for k in ("non riuscito", "non risponde", "riprovo", "Fermato")):
                        print(r, flush=True)
                esiti = trascrizioni.trascrivi_molti(percorsi, avviso=dillo, progresso=avanza,
                                                     smetti=fermato, rifai=passo != "md_mancanti")
                scritti = sum(1 for e in esiti if e.get("esito") in ("scritto", "riscritto"))
                # i non riusciti si dicono: chi guarda deve sapere cosa e rimasto indietro,
                # non leggere «0 su 6» e credere che non ci fosse niente da fare
                mancati = [e for e in esiti
                           if str(e.get("esito", "")).startswith(("non riuscito", "errore"))]
                perche = "; ".join(f"{os.path.basename(e['percorso'])}: {e['esito']}"
                                   for e in mancati[:3])
                fatto.append(f"{nome}: {scritti} su {len(percorsi)}"
                             + (f" ({len(mancati)} non riusciti — {perche})" if mancati else ""))
            elif passo == "analisi":
                if voce and voce["esiste"]:
                    scrivi(i, "aggiorno l'indice con il testo dei .md nuovi…")
                    archivio.indicizza(voce["percorso"], radice=radice, ocr=False, avviso=lambda r: None,
                                       id_lavoro=nuovo_passo("indicizza", voce["percorso"]))
                if fermato():
                    break
                scrivi(i, "rifaccio l'analisi: temi, gruppi, parole caratteristiche…")
                biblioteca.analizza(radice, avviso=lambda r: None, id_lavoro=nuovo_passo("analizza"))
                fatto.append("analisi rifatta")
            elif passo == "riassunti":
                if not (semantica.acceso() and biblioteca._modello_per_riassunti()):
                    fatto.append("riassunti saltati: Ollama non risponde")
                    continue
                scrivi(i, f"scrivo i riassunti: {len(biblioteca.da_riassumere(radice))} documenti…")
                id_r = nuovo_passo("riassunti")
                biblioteca.riassumi_tutti(radice, avviso=lambda r: None, id_lavoro=id_r)
                fatto.append(f"riassunti: {(archivio.lavoro(id_r) or {}).get('messaggio', '')}")
            corrente["id"] = None
        if p["copie_saltate"]["quanti"] and any(x.startswith("i .md") for x in fatto):
            fatto.append(f"copie saltate: {p['copie_saltate']['quanti']} documenti "
                         f"({p['copie_saltate']['pagine']} pagine) che hanno lo stesso "
                         f"testo di un altro")
        esito = "; ".join(fatto) or "niente da fare"
        stato = "fermato" if fermato() else "finito"
        if stato == "fermato":
            esito = "fermato — " + esito
        archivio.aggiorna_lavoro(id_lavoro, stato=stato, fatti=len(passi), finito=time.time(),
                                 messaggio=f"{esito} ({round((time.time() - t0) / 60)} minuti)", riga=esito)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])
    finally:
        corrente["vivo"] = False
