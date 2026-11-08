#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domande ai documenti, come in NotebookLM, ma sul computer.

Si fa una domanda; Scaffale cerca i brani che le rispondono, nella cartella
dove ci si trova, in due modi insieme: per le parole — con le varianti dei
tesauri in uso — e per senso, con i vettori, dove ci sono. Le due classifiche
si fondono (la fusione dei ranghi, «reciprocal rank fusion»: conta il posto
di un brano in ciascuna, non il punteggio, che nelle due ricerche si misura
in modi diversi). I brani migliori, numerati, vanno al modello che gira sul
computer, con l'ordine di rispondere solo con quelli e di dire da quale brano
viene ogni cosa: [1], [3]. Ogni numero, nella pagina, porta alla pagina del
documento con le parole in giallo.

Il modello può sbagliare; i brani no. Per questo i brani si mostrano sempre,
sotto la risposta, e i numeri che non corrispondono a nessun brano si tolgono.
Senza il modello — Ollama spento — si mostrano solo i brani trovati.

L'idea di fondere le due ricerche e di dare comunque i brani senza il modello
viene da OpenNotebookLM (github.com/woodysc8/OpenNotebookLM), che fa la stessa
cosa con SQLite; il resto è di Scaffale.
"""
import json
import re
import time

import archivio
import biblioteca
import semantica
import tesauri
import tesauro

SCHEMA = """
CREATE TABLE IF NOT EXISTS domande (
    id INTEGER PRIMARY KEY,
    radice TEXT,         -- dove si è cercato: una cartella, o '' per tutte
    gruppo INTEGER,      -- un gruppo della cartella, se la domanda è fatta lì
    domanda TEXT,
    risposta TEXT,
    brani TEXT,          -- JSON: [{n, documento, frammento, nome, percorso, pagina, testo, parole}]
    modello TEXT,
    secondi REAL,
    stato TEXT,          -- in corso | finito | senza modello | fermato | errore
    creato_il REAL
);
"""

QUANTI_BRANI = 6
PER_DOCUMENTO = 2        # non più di due brani da uno stesso documento: la risposta ne guarda più d'uno
FINESTRA = 1500          # caratteri di ogni brano che il modello legge, attorno alle parole trovate
RRF = 60                 # la costante della fusione dei ranghi, quella usata di solito

# le parole di una domanda che non dicono che cosa si cerca
DOMANDA_VUOTE = set("""
chi che cosa come quale quali quando dove perche quanto quanta quanti quante cui
del dei delle degli della dello nel nei nelle negli nella sul sui sulle sugli sulla
con per tra fra una uno gli non piu meno era erano sono stato stata viene venivano
parla parlano dice dicono documenti documento testi testo fonti fonte cartella
what who which when where why how does did the and for with from about
""".split())


def apri():
    c = archivio.apri()
    c.executescript(SCHEMA)
    # il ricercatore (ricercatore.py) scrive nella stessa tabella: tipo e diario
    colonne = {r["name"] for r in c.execute("PRAGMA table_info(domande)")}
    for nome in ("tipo", "diario"):
        if nome not in colonne:
            c.execute(f"ALTER TABLE domande ADD COLUMN {nome} TEXT")
    c.commit()
    return c


def parole_di(domanda):
    """Le parole della domanda che servono a cercare."""
    fuori = []
    for p in re.findall(r"\w+", domanda, re.UNICODE):
        w = tesauro.piatto(p)
        if len(w) > 2 and w not in DOMANDA_VUOTE and w not in biblioteca.PAROLE_VUOTE and w not in fuori:
            fuori.append(w)
    return fuori


# singolare e plurale, maschile e femminile: «pene» vale anche «pena», «riti» anche «rito»
ALTRA_DESINENZA = {"e": "a", "a": "e", "i": "o", "o": "i"}


def _forme_per_parola(parole, radice):
    """Per ogni parola della domanda: le forme intere (con le varianti dei
    tesauri e l'altra desinenza) e la radice, per le parole lunghe.
    Restituisce [(parola, forme, radice o None)]."""
    nuclei = tesauri.nuclei_per(radice or None)
    fuori = []
    for w in parole:
        forme = {f for g in tesauro.gruppi(w, nuclei) for f in g} | {w}
        if len(w) >= 4 and w[-1] in ALTRA_DESINENZA:
            forme.add(w[:-1] + ALTRA_DESINENZA[w[-1]])
        # nelle parole lunghe vale anche la radice: «private» trova «privato»,
        # «giurata» anche «giurato» e «giurati». Solo dalle sei lettere in su:
        # «notai» ridotto a «nota» troverebbe tutte le note.
        rad = w[:-1] if len(w) >= 6 and w[-1] in "aeiou" and " " not in w else None
        fuori.append((w, sorted(forme), rad))
    return fuori


def _per_parole(parole, radice, gruppo):
    """I brani con le parole della domanda, o con le loro varianti.

    L'indice ne trova 80 dove ce n'è almeno una; poi passano avanti quelli che
    ne hanno di più, di parole diverse della domanda. Senza questo vince la
    parola più rara: a «quali pene per chi rompeva una pace giurata» rispondeva
    «rompeva il muro della casa», perché in una cartella sulle paci «pace» sta
    dappertutto e pesa poco."""
    if not parole:
        return []
    forma = lambda f: '{testo piatto}:"%s"' % f.replace('"', " ")
    per_parola = _forme_per_parola(parole, radice)
    pezzi = []
    for _, forme, rad in per_parola:
        pezzi += [forma(f) for f in forme]
        if rad:
            pezzi.append('{testo piatto}:"%s"*' % rad)
    righe = archivio._fts(" OR ".join(pezzi), 80, radice or None, gruppo)
    if not righe:
        return []
    c = archivio.apri()
    coperte = {}
    for k, r in enumerate(righe):
        t = c.execute("SELECT testo FROM frammenti WHERE id=?", (r["frammento"],)).fetchone()
        testo = " " + " ".join(re.findall(r"\w+", tesauro.piatto(t["testo"] if t else ""))) + " "
        coperte[r["frammento"]] = sum(
            1 for _, forme, rad in per_parola
            if any(f" {f} " in testo for f in forme) or (rad and f" {rad}" in testo))
    ordine = {r["frammento"]: k for k, r in enumerate(righe)}
    return sorted(ordine, key=lambda fr: (-coperte[fr], ordine[fr]))


def _per_senso(domanda, radice, gruppo):
    try:
        return [fr for _, fr, _ in semantica.cerca(domanda, 20, radice=radice or None, gruppo=gruppo)]
    except Exception:
        return []


def _finestra(testo, parole):
    """Il pezzo del brano attorno alle parole trovate, se il brano è lungo."""
    if len(testo) <= FINESTRA:
        return testo
    scritte = archivio.forme_nel_testo(testo, parole)
    posti = sorted(p for p in (testo.find(x) for x in scritte) if p >= 0)
    inizio = max(0, min(posti[0] - FINESTRA // 3, len(testo) - FINESTRA)) if posti else 0
    pezzo = testo[inizio:inizio + FINESTRA]
    return ("…" if inizio else "") + pezzo + ("…" if inizio + FINESTRA < len(testo) else "")


PAROLE_DI_VERSIONE = set("""aggiornato aggiornata revisione rivisto rivista bozza copia versione
final finale def definitivo definitiva nuovo nuova vecchio vecchia old new draft rev""".split())


def famiglia(nome):
    """Le versioni di uno stesso testo, dal nome del file: «Dalla_luce_al_trattato_aggiornato 6.docx»
    e «… 5.docx», l'articolo e la sua «_revisione», il PDF e il suo .md. Hanno testi
    quasi uguali ma non identici, e riempirebbero da sole la risposta."""
    base = re.sub(r"\.[a-z0-9]{1,5}$", "", tesauro.piatto(nome))
    parole = [w for w in re.findall(r"[a-z]+", base) if w not in PAROLE_DI_VERSIONE and len(w) > 1]
    return " ".join(parole) or base


def brani(domanda, radice="", gruppo=None, quanti=QUANTI_BRANI):
    """I brani che rispondono alla domanda, i migliori prima. Restituisce
    (brani, come) dove `come` dice quali ricerche hanno lavorato."""
    parole = parole_di(domanda)
    per_parole = _per_parole(parole, radice, gruppo)
    per_senso = _per_senso(domanda, radice, gruppo)
    punti = {}
    for elenco in (per_parole, per_senso):
        for k, fr in enumerate(elenco):
            punti[fr] = punti.get(fr, 0) + 1 / (RRF + k)
    # le varianti, per trovarle nel testo e metterle in giallo
    forme = sorted({f for _, ff, _ in _forme_per_parola(parole, radice) for f in ff})
    c = archivio.apri()
    scelti, per_doc, impronte, visti = [], {}, {}, []
    for fr in sorted(punti, key=lambda x: -punti[x]):
        d = c.execute("""SELECT f.id, f.documento, f.pagina, f.testo, d.nome, d.percorso, d.impronta
                         FROM frammenti f JOIN documenti d ON d.id = f.documento
                         WHERE f.id = ?""", (fr,)).fetchone()
        if not d:
            continue
        # le copie identiche contano come un documento solo; le versioni di uno
        # stesso testo, tutte insieme, danno al massimo due brani
        imp = d["impronta"] or f"doc{d['documento']}"
        if impronte.setdefault(imp, d["documento"]) != d["documento"]:
            continue
        chi = famiglia(d["nome"])
        # «glavina sbarbaro brunettin» e «glavina sbarbaro brunettin zc»: se un
        # nome comincia con l'altro, di almeno due parole, è la stessa famiglia
        chi = next((k for k in per_doc if k.count(" ") >= 1 and chi.count(" ") >= 1
                    and ((chi + " ").startswith(k + " ") or (k + " ").startswith(chi + " "))), chi)
        if per_doc.get(chi, 0) >= PER_DOCUMENTO:
            continue
        # lo stesso testo in un altro file — il PDF e il suo .md, due versioni
        # dello stesso articolo — non si legge due volte
        parole_b = set(re.findall(r"\w{4,}", tesauro.piatto(d["testo"] or "")))
        if any(len(parole_b & v) / max(len(parole_b | v), 1) > 0.5 for v in visti):
            continue
        visti.append(parole_b)
        per_doc[chi] = per_doc.get(chi, 0) + 1
        testo = _finestra(d["testo"] or "", forme)
        scelti.append({"n": len(scelti) + 1, "documento": d["documento"], "frammento": d["id"],
                       "nome": d["nome"], "percorso": d["percorso"], "pagina": d["pagina"],
                       "testo": testo, "parole": archivio.forme_nel_testo(testo, forme)[:8]})
        if len(scelti) >= quanti:
            break
    come = []
    if per_parole:
        come.append("per parole")
    if per_senso:
        come.append("per senso")
    return scelti, come


def _prompt(domanda, scelti):
    fonti = "\n\n".join(f"[{b['n']}] «{b['nome']}», pagina {b['pagina'] or '?'}:\n{b['testo']}"
                        for b in scelti)
    return ("Sei l'assistente di uno storico. Rispondi alla DOMANDA usando soltanto i BRANI qui "
            "sotto, presi dai suoi documenti.\n"
            "Regole:\n"
            "- Dopo ogni affermazione metti il numero del brano da cui viene, tra parentesi quadre: "
            "[1], oppure [2][4].\n"
            "- Se i brani non contengono la risposta, o ne contengono solo una parte, dillo "
            "chiaramente («Nei brani trovati non si parla di…»). Non completare con quello che sai.\n"
            "- Le citazioni in latino o in altre lingue riportale esattamente come sono nel brano, "
            "tra virgolette, senza correggerle.\n"
            "- Non inventare nomi, date, citazioni o pagine.\n"
            "- Rispondi in italiano, in modo chiaro, al massimo in quattro paragrafi.\n\n"
            f"BRANI:\n\n{fonti}\n\nDOMANDA: {domanda}\n\nRISPOSTA:")


def stima(quanti=QUANTI_BRANI):
    """Quanto ci vorrà, in secondi, secondo le misure fatte su questo computer."""
    return 40 + quanti * FINESTRA * archivio.velocita()["domanda"]


def _scrivi(prompt, id_lavoro):
    """La risposta del modello, a pezzi, così il pulsante Ferma funziona anche a metà."""
    if not biblioteca._modello_per_riassunti():
        return None, None
    return biblioteca.scrivi_testo(
        prompt, id_lavoro,
        lambda n: archivio.aggiorna_lavoro(
            id_lavoro, messaggio=f"il modello scrive la risposta… ({n} parole)"),
        parole=900, temperatura=0.2,
        opzioni={"repeat_penalty": 1.1, "num_ctx": 8192})


def _parole_piene(testo):
    return {w for w in re.findall(r"\w{5,}", tesauro.piatto(testo))
            if w not in biblioteca.PAROLE_VUOTE and w not in DOMANDA_VUOTE}


def correggi_numeri(risposta, scelti):
    """Il modello a volte dà il numero sbagliato: la frase su Muzio veniva dal
    brano [3], e lui scriveva [5]. Per ogni frase con un numero si guarda quante
    delle sue parole stanno nel brano citato; se stanno quasi tutte in un altro
    e poco in quello, il numero si corregge. Restituisce (risposta, correzioni)."""
    brani_p = {b["n"]: _parole_piene(b["testo"]) for b in scelti}
    correzioni = []

    def frase(m):
        testo = m.group(0)
        parole = _parole_piene(re.sub(r"\[\d+\]", " ", testo))
        if len(parole) < 3:
            return testo
        quota = {n: len(parole & p) / len(parole) for n, p in brani_p.items()}
        migliore = max(quota, key=quota.get)

        def numero(mn):
            n = int(mn.group(1))
            if n in quota and n != migliore and quota[n] < 0.3 and quota[migliore] >= 2 * quota[n] + 0.2:
                correzioni.append((n, migliore))
                return f"[{migliore}]"
            return mn.group(0)
        return re.sub(r"\[(\d+)\]", numero, testo)

    # una frase: fino al punto, compresi i numeri che la seguono
    return re.sub(r"[^.!?\n]+[.!?]?(?:\s*\[\d+\])*", frase, risposta), correzioni


def guardia_numeri(risposta, scelti):
    """Ogni numero della risposta deve stare, uguale, nei brani che la frase cita.

    Per la storia — e per quella economica più che mai — un numero sbagliato è
    l'errore peggiore: il modello può scrivere «1593» dove il brano dice «1539»,
    o un prezzo che nel brano non c'è, e la frase resta credibile. Il controllo è
    meccanico, e il modello non lo aggira: si prendono i numeri di ogni frase
    (cifre arabe e romani, come nella verifica dei .md) e si cercano nei brani che
    la frase cita, o in tutti se non ne cita. Quelli che non ci sono si segnano
    ⚠ nel testo. Restituisce (risposta, [(numero, brani in cui sta davvero)])."""
    import collections
    import verifica_numeri
    nei_brani = {b["n"]: verifica_numeri.numeri(b.get("testo", "")) for b in scelti}
    tutti = collections.Counter()
    for v in nei_brani.values():
        tutti |= v
    dubbi = []

    def frase(m):
        testo = m.group(0)
        citati = [int(x) for x in re.findall(r"\[(\d+)\]", testo)]
        for x in verifica_numeri.numeri(re.sub(r"\[\d+\]", " ", testo)):
            fonti = [nei_brani.get(c, {}) for c in citati] if citati else [tutti]
            if any(x in f for f in fonti):
                continue
            dubbi.append((x, [n for n, v in nei_brani.items() if x in v]))
            romano = not x.isdigit()
            testo = re.sub(rf"(?<![\w⚠]){re.escape(x)}(?!\w)", lambda k: "⚠" + k.group(0), testo, count=1,
                           flags=re.I if romano else 0)
        return testo

    risposta = re.sub(r"[^.!?\n]+[.!?]?(?:\s*\[\d+\])*", frase, risposta)
    return risposta, dubbi


def controlla(risposta, quanti, scelti=None):
    """Toglie i numeri di brano che non esistono: il modello a volte ne inventa;
    e corregge quelli sbagliati. Restituisce (risposta, avvisi)."""
    avvisi = []
    if scelti:
        risposta, corrette = correggi_numeri(risposta, scelti)
        if corrette:
            avvisi.append("Ho corretto il numero di brano di " + ", ".join(
                f"[{a}] in [{b}]" for a, b in corrette) + ": le parole della frase stanno nel "
                "secondo, non nel primo. Controlla quelle frasi.")
    falsi = sorted({int(n) for n in re.findall(r"\[(\d+)\]", risposta) if not 1 <= int(n) <= quanti})
    if falsi:
        risposta = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= quanti else "",
                          risposta)
        avvisi.append("Il modello ha citato brani che non esistono (" + ", ".join(map(str, falsi))
                      + "): li ho tolti. Controlla quelle frasi sui brani qui sotto.")
    if risposta and not re.search(r"\[\d+\]", risposta):
        avvisi.append("Il modello non ha detto da quali brani viene la risposta: controllala sui "
                      "brani qui sotto prima di usarla.")
    if scelti:
        risposta, dubbi = guardia_numeri(risposta, scelti)
        if dubbi:
            dove = lambda b: (f"sta nel brano {', '.join(f'[{n}]' for n in b)}, non in quello citato"
                              if b else "non sta in nessun brano")
            avvisi.append("Numeri da controllare, segnati ⚠ nel testo: " + "; ".join(
                f"«{x}» {dove(b)}" for x, b in dubbi) + ". Prima di usarli, guardali sui brani.")
    return risposta, avvisi


def nuova(domanda, radice="", gruppo=None):
    """Registra la domanda e trova i brani: pochi secondi. Restituisce l'id e i brani."""
    scelti, _ = brani(domanda, radice, gruppo)
    c = apri()
    i = c.execute("""INSERT INTO domande (radice, gruppo, domanda, brani, stato, creato_il)
                     VALUES (?,?,?,?,?,?)""",
                  (radice, gruppo, domanda, json.dumps(scelti, ensure_ascii=False),
                   "in corso", time.time())).lastrowid
    c.commit()
    return i, scelti


def rispondi(id_domanda, id_lavoro=None):
    """Il lavoro lungo: il modello legge i brani e scrive la risposta."""
    t0 = time.time()
    c = apri()
    d = c.execute("SELECT * FROM domande WHERE id=?", (id_domanda,)).fetchone()
    scelti = json.loads(d["brani"] or "[]")

    def chiudi(stato, risposta="", modello=None, messaggio=""):
        c.execute("UPDATE domande SET stato=?, risposta=?, modello=?, secondi=? WHERE id=?",
                  (stato, risposta, modello, round(time.time() - t0, 1), id_domanda))
        c.commit()      # prima di scrivere l'avanzamento con l'altra connessione
        archivio.aggiorna_lavoro(id_lavoro, stato="fermato" if stato == "fermato" else "finito",
                                 fatti=2, finito=time.time(), messaggio=messaggio, riga=messaggio)

    if not scelti:
        return chiudi("finito", "Nei documenti dove hai cercato non ho trovato brani che "
                                "c'entrino con la domanda.", None, "nessun brano trovato")
    archivio.aggiorna_lavoro(id_lavoro, totale=2, fatti=1,
                             messaggio=f"il modello legge {len(scelti)} brani…")
    prompt = _prompt(d["domanda"], scelti)
    try:
        risposta, modello = _scrivi(prompt, id_lavoro)
    except biblioteca.Fermato:
        return chiudi("fermato", "", None, "fermato: nessuna risposta")
    if risposta is None:
        return chiudi("senza modello", "", None, "nessun modello per scrivere: ecco i brani")
    risposta, avvisi = controlla(risposta, len(scelti), scelti)
    if avvisi:
        risposta += "\n\n" + "\n".join(f"⚠ {a}" for a in avvisi)
    try:
        archivio._ricorda("domanda", max(time.time() - t0 - 40, 1), max(len(prompt), 1), 1)
    except Exception:
        pass
    chiudi("finito", risposta, modello, f"risposta scritta in {round(time.time() - t0)} secondi")


def senza_modello(id_domanda):
    c = apri()
    c.execute("UPDATE domande SET stato='senza modello' WHERE id=?", (id_domanda,))
    c.commit()


def una(id_domanda):
    r = apri().execute("SELECT * FROM domande WHERE id=?", (id_domanda,)).fetchone()
    return dict(r, brani=json.loads(r["brani"] or "[]")) if r else None


def ultime(radice=None, quante=20):
    c = apri()
    if radice is None:
        righe = c.execute("SELECT id, radice, domanda, stato, creato_il FROM domande "
                          "ORDER BY id DESC LIMIT ?", (quante,))
    else:
        righe = c.execute("SELECT id, radice, domanda, stato, creato_il FROM domande WHERE radice=? "
                          "ORDER BY id DESC LIMIT ?", (radice, quante))
    return [dict(r) for r in righe]


def dimentica(id_domanda):
    c = apri()
    c.execute("DELETE FROM domande WHERE id=?", (id_domanda,))
    c.commit()
