#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Il ricercatore: una domanda difficile, lavorata come farebbe uno studioso.

Una domanda semplice (domande.py) cerca una volta e risponde con sei brani. Il
ricercatore invece, sul modello che gira sul computer:

1. fa un piano: scompone la domanda e prepara più ricerche, anche con le parole
   latine o antiche con cui la cosa sta scritta nelle fonti;
2. fa tutte quelle ricerche — per parole, con le varianti dei tesauri, e per
   senso — e tiene i brani migliori;
3. legge i brani uno alla volta: se serve, dice che cosa dice e ne copia la
   frase chiave. Scaffale controlla che la frase stia davvero nel brano, parola
   per parola, e che ogni numero del riassunto stia nel brano: quello che non
   torna si scarta o si segna;
4. guarda che cosa ha trovato e, se manca qualcosa, fa un secondo giro di
   ricerche (uno solo);
5. scrive il rapporto, con [n] dopo ogni affermazione;
6. il rapporto passa per gli stessi controlli di una domanda: numeri di brano
   inesistenti o sbagliati, e ogni numero e data sul brano che la frase cita.

È l'idea di PaperQA2 (github.com/future-house/paper-qa) — prove raccolte e
riassunte una per una prima di scrivere — con i controlli di Scaffale, che non
si fidano del modello sui numeri. Su un computer senza scheda grafica ci vogliono
20–30 minuti: è un lavoro da lanciare e lasciare andare.
"""
import json
import re
import time
import unicodedata

import archivio
import biblioteca
import domande
import verifica_numeri

MASSIMO_BRANI = 14          # quanti brani legge, uno per uno (circa un minuto ciascuno)
PER_RICERCA = 6
SECONDI_DI_BASE = 25 * 60   # la prima stima; poi vale la misura (velocita.json, «ricercatore»)


def _json(testo):
    try:
        return json.loads(testo)
    except ValueError:
        m = re.search(r"\{.*\}", testo or "", re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except ValueError:
            return {}


def _chiedi(prompt, id_lavoro, predici=500, formato_json=True):
    return biblioteca.scrivi_testo(prompt, id_lavoro, parole=predici, temperatura=0.2,
                                   json_puro=formato_json,
                                   opzioni={"num_ctx": 8192, "repeat_penalty": 1.1})


def _piatto(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[«»“”\"'’‘`]", "", s)
    s = re.sub(r"(\w)[-¬]\s+(\w)", r"\1\2", s)      # «Con- siglio», spezzato a fine riga
    return re.sub(r"\s+", " ", s).strip()


def citazione_vera(citazione, testo):
    """Se la frase che il modello dice di aver copiato sta davvero nel brano:
    senza badare a maiuscole, accenti, virgolette e spazi, ma parola per parola.
    Una frase che non c'è è inventata, anche se somiglia."""
    c = _piatto(citazione).strip(" .,;:…")
    return len(c) >= 12 and c in _piatto(testo)


def piano(domanda, id_lavoro):
    prompt = ("Sei l'assistente di uno storico (storia medievale e moderna, Venezia, Adriatico, "
              "Bisanzio, storia economica). Devi cercare nei suoi documenti la risposta a questa "
              f"domanda:\n\n{domanda}\n\n"
              "Scomponila in 2-4 domande più precise, e per ognuna scrivi 1-2 ricerche brevi: poche "
              "parole chiave, come le scriveresti in un indice. Scrivile con le parole che si trovano "
              "nelle fonti e negli studi — in italiano, e dove serve in latino o nell'italiano antico —, "
              "non con il nome della lingua. Per esempio, per il bacio della pace: «bacio pace», "
              "«osculum pacis», «pax et concordia». Niente frasi intere.\n"
              'Rispondi solo con JSON: {"sottodomande": ["..."], "ricerche": ["...", "..."]}')
    testo, _ = _chiedi(prompt, id_lavoro, 350)
    d = _json(testo)
    ricerche = [str(x).strip() for x in (d.get("ricerche") or []) if str(x).strip()][:8]
    return [str(x) for x in (d.get("sottodomande") or [])][:4], ricerche or [domanda]


def raccogli(ricerche, radice, gruppo, gia=()):
    """I brani di tutte le ricerche, fusi per posto (come in domande.brani), senza
    doppioni: né lo stesso brano, né lo stesso testo in un altro file."""
    punti, per_id = {}, {}
    for q in ricerche:
        trovati, _ = domande.brani(q, radice, gruppo, quanti=PER_RICERCA)
        for k, b in enumerate(trovati):
            if b["frammento"] in gia:
                continue
            punti[b["frammento"]] = punti.get(b["frammento"], 0) + 1 / (domande.RRF + k)
            per_id.setdefault(b["frammento"], b)
    scelti, visti, per_famiglia = [], [], {}
    for fr in sorted(punti, key=lambda x: -punti[x]):
        b = per_id[fr]
        parole_b = set(re.findall(r"\w{4,}", _piatto(b["testo"])))
        if any(len(parole_b & v) / max(len(parole_b | v), 1) > 0.5 for v in visti):
            continue
        # al massimo due brani da uno stesso testo, anche fra una ricerca e l'altra:
        # se no le versioni di un articolo riempiono tutte le prove
        chi = domande.famiglia(b["nome"])
        chi = next((k for k in per_famiglia if k.count(" ") >= 1 and chi.count(" ") >= 1
                    and ((chi + " ").startswith(k + " ") or (k + " ").startswith(chi + " "))), chi)
        if per_famiglia.get(chi, 0) >= domande.PER_DOCUMENTO:
            continue
        per_famiglia[chi] = per_famiglia.get(chi, 0) + 1
        visti.append(parole_b)
        scelti.append(b)
    return scelti


def leggi(domanda, b, id_lavoro):
    """Un brano, letto: serve? che cosa dice? la frase chiave, copiata. Con i controlli."""
    prompt = (f"DOMANDA: {domanda}\n\nBRANO («{b['nome']}», pagina {b.get('pagina') or '?'}):\n{b['testo']}\n\n"
              "Il brano serve a rispondere alla domanda, anche solo in parte? Se sì, di' in 1-3 frasi "
              "che cosa dice sulla domanda, senza aggiungere niente che non ci sia, e copia esattamente "
              "la frase del brano più importante. Numeri, date e nomi come sono scritti.\n"
              'Rispondi solo con JSON: {"pertinente": true, "sintesi": "...", "citazione": "..."}')
    testo, _ = _chiedi(prompt, id_lavoro, 300)
    d = _json(testo)
    pert = d.get("pertinente") in (True, "true", "sì", "si", "yes")
    sintesi = str(d.get("sintesi") or "").strip()
    citazione = str(d.get("citazione") or "").strip()
    esito = {"pertinente": bool(pert and sintesi), "sintesi": sintesi, "citazione": citazione,
             "citazione_vera": citazione_vera(citazione, b["testo"]) if citazione else False}
    # i numeri del riassunto devono stare nel brano
    nel_brano = verifica_numeri.numeri(b["testo"])
    esito["numeri_assenti"] = sorted(x for x in verifica_numeri.numeri(sintesi) if x not in nel_brano)
    if not esito["citazione_vera"]:
        esito["citazione"] = ""          # una frase che nel brano non c'è non si mostra come citazione
    return esito


def rifletti(domanda, prove, id_lavoro):
    elenco = "\n".join(f"- {p['sintesi']}" for p in prove) or "(nessuna prova trovata)"
    prompt = (f"DOMANDA: {domanda}\n\nFinora dai documenti è emerso:\n{elenco}\n\n"
              "Basta per rispondere? Se manca qualcosa di importante, scrivi 1-3 nuove ricerche brevi "
              "(parole chiave, anche nelle lingue delle fonti) per trovarlo.\n"
              'Rispondi solo con JSON: {"basta": true, "manca": "...", "nuove_ricerche": ["..."]}')
    testo, _ = _chiedi(prompt, id_lavoro, 250)
    d = _json(testo)
    return (d.get("basta") in (True, "true"), str(d.get("manca") or ""),
            [str(x).strip() for x in (d.get("nuove_ricerche") or []) if str(x).strip()][:3])


def rapporto(domanda, prove, id_lavoro):
    fonti = "\n\n".join(
        f"[{p['n']}] «{p['nome']}», pagina {p.get('pagina') or '?'}\nChe cosa dice: {p['sintesi']}"
        + (f"\nFrase del brano: «{p['citazione']}»" if p.get("citazione") else "")
        + f"\nTesto: {p['testo'][:900]}"
        for p in prove)
    prompt = ("Sei l'assistente di uno storico. Scrivi un breve rapporto che risponde alla DOMANDA "
              "usando soltanto le FONTI qui sotto, prese dai suoi documenti.\n"
              "Regole:\n"
              "- Dopo ogni affermazione metti il numero della fonte tra parentesi quadre: [1], [2][4].\n"
              "- Numeri, date, prezzi, misure e nomi esattamente come sono nelle fonti: non calcolare, "
              "non arrotondare, non convertire.\n"
              "- Se le fonti non bastano, o si contraddicono, dillo.\n"
              "- Non aggiungere niente che non sia nelle fonti.\n"
              "- In italiano, in tre parti: «In breve», «Che cosa dicono le fonti», «Che cosa non si "
              "trova o resta incerto».\n\n"
              f"FONTI:\n\n{fonti}\n\nDOMANDA: {domanda}\n\nRAPPORTO:")
    return _chiedi(prompt, id_lavoro, 1100, formato_json=False)


def stima():
    return archivio.velocita().get("ricercatore", SECONDI_DI_BASE)


def lavora(id_domanda, id_lavoro=None):
    """Tutto il lavoro, dal piano al rapporto verificato. Scrive il diario man mano."""
    t0 = time.time()
    c = domande.apri()
    d = c.execute("SELECT * FROM domande WHERE id=?", (id_domanda,)).fetchone()
    domanda, radice, gruppo = d["domanda"], d["radice"] or "", d["gruppo"]
    diario = {"piano": {}, "giri": [], "letti": []}
    prove = []

    def salva(stato="in corso", risposta="", modello=None):
        c.execute("UPDATE domande SET stato=?, risposta=?, modello=?, secondi=?, diario=?, brani=? WHERE id=?",
                  (stato, risposta, modello, round(time.time() - t0, 1),
                   json.dumps(diario, ensure_ascii=False), json.dumps(prove, ensure_ascii=False), id_domanda))
        c.commit()           # prima di scrivere l'avanzamento con l'altra connessione

    def passo(k, messaggio):
        archivio.aggiorna_lavoro(id_lavoro, totale=6, fatti=k, messaggio=messaggio, riga=messaggio)

    try:
        passo(0, "il ricercatore fa il piano…")
        sotto, ricerche = piano(domanda, id_lavoro)
        diario["piano"] = {"sottodomande": sotto, "ricerche": ricerche}
        salva()
        letti_id = set()
        for giro in (1, 2):
            passo(1 if giro == 1 else 3, f"cerca: {', '.join(ricerche)[:150]}")
            candidati = raccogli(ricerche, radice, gruppo, letti_id)[:MASSIMO_BRANI if giro == 1 else 6]
            diario["giri"].append({"ricerche": ricerche, "brani": len(candidati)})
            for i, b in enumerate(candidati, 1):
                passo(2 if giro == 1 else 4, f"legge il brano {i} di {len(candidati)}: {b['nome'][:60]}")
                esito = leggi(domanda, b, id_lavoro)
                letti_id.add(b["frammento"])
                diario["letti"].append({"nome": b["nome"], "pagina": b.get("pagina"), "giro": giro, **esito})
                if esito["pertinente"]:
                    prove.append(dict(b, n=len(prove) + 1, **esito))
                salva()
            if giro == 2:
                break
            basta, manca, nuove = rifletti(domanda, prove, id_lavoro)
            diario["riflessione"] = {"basta": basta, "manca": manca, "nuove_ricerche": nuove}
            if basta or not nuove:
                break
            ricerche = nuove
        if not prove:
            salva("finito", "Nei documenti dove hai cercato non ho trovato brani che rispondano alla "
                            "domanda. Il diario qui sotto dice che cosa ho cercato e letto.")
            archivio.aggiorna_lavoro(id_lavoro, stato="finito", fatti=6, finito=time.time(),
                                     messaggio="nessuna prova trovata")
            return
        passo(5, f"scrive il rapporto con {len(prove)} prove…")
        testo, modello = rapporto(domanda, prove, id_lavoro)
        testo, avvisi = domande.controlla(testo.strip(), len(prove), prove)
        # le prove con numeri che il modello ha messo nel riassunto e nel brano non ci sono
        storte = [p for p in prove if p.get("numeri_assenti")]
        if storte:
            avvisi.append("Nel leggere, il modello ha scritto numeri che nel brano non ci sono (" +
                          "; ".join(f"[{p['n']}] {', '.join(p['numeri_assenti'])}" for p in storte) +
                          "): quelle prove sono da guardare.")
        if avvisi:
            testo += "\n\n" + "\n".join(f"⚠ {a}" for a in avvisi)
        try:
            archivio._ricorda("ricercatore", time.time() - t0, 1, 1)
        except Exception:
            pass
        salva("finito", testo, modello)
        archivio.aggiorna_lavoro(id_lavoro, stato="finito", fatti=6, finito=time.time(),
                                 messaggio=f"rapporto scritto in {round((time.time() - t0) / 60)} minuti, "
                                           f"con {len(prove)} prove")
    except biblioteca.Fermato:
        salva("fermato")
        archivio.aggiorna_lavoro(id_lavoro, stato="fermato", finito=time.time(),
                                 messaggio="fermato: il diario dice fin dove era arrivato")
