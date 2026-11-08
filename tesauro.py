#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tesauro di dominio: espande una parola nei suoi equivalenti reali.

Un archivio come questo è scritto in italiano, croato, latino, greco, inglese e
tedesco, e la stessa cosa vi compare sotto nomi che non si somigliano: la
Nicopeia è «Nikopeja» in croato, «Νικοποιός» in greco, «imagine di Nostra
Donna» nelle fonti cinquecentesche. Cercare una stringa sola vuol dire trovare
un decimo di quello che c'è.

Ogni voce è un nucleo concettuale con tutte le sue rese. Si corregge a mano:
è un file di testo, non un modello. Chi lo legge capisce perché un risultato
è uscito, che con gli embedding non succede.
"""
import re
import unicodedata

# Ogni forma deve voler dire una cosa sola. Una parola che in latino, in inglese
# o in croato vuol dire anche altro va scritta con il suo contesto: «dux» da solo
# è qualunque condottiero — nella Bibbia latina compare in 93 brani — e solo
# «dux Venetiarum» è il doge; «split» in inglese è «dividere», «corner» un
# angolo, «scuola» qualunque scuola.
NUCLEI = {
    "nicopeia": [
        "nicopeia", "nikopeia", "nicopeja", "nikopeja", "nikopej", "nicopea",
        "nikopoios", "nicopoios", "nikopoia", "νικοποιός", "νικοποιος",
        "bogorodica nikopeja", "madonna nicopeia", "vergine nicopeia",
        "imagine di nostra donna", "imagine della madre di dio",
        "gospa od pobjede", "bogorodica pobjednica", "madonna della vittoria",
    ],
    "icona": [
        "icona", "icone", "ikona", "ikone", "ikon", "icon", "icons", "εικόνα",
        "eikon", "ikonopis", "iconografia", "ikonografija",
        "tavola dipinta", "pala d'altare", "pala d'oro", "tabula picta",
    ],
    "san luca": [
        "san luca", "s. luca", "santo luca", "sancti lucae", "diui lucae",
        "lucana", "acheiropoieta", "acheropita", "αχειροποίητος",
        "dipinta da san luca", "manu beati lucae", "opera di san luca",
    ],
    "tipi mariani": [
        "hodigitria", "odigitria", "hodegetria", "odighitria", "οδηγήτρια",
        "eleusa", "eleousa", "ελεούσα", "umilenie", "glykophilousa",
        "galaktotrofousa", "lactans", "kardiotissa", "skopiotissa", "skopiotis",
        "mesopanditissa", "mesopandit", "pelagonitissa", "vrefokratousa",
        "deesis", "deisis", "platytera", "blachernitissa", "kyriotissa",
    ],
    "bisanzio": [
        "bisanzio", "bizantino", "bizantina", "bizantin", "bizant", "byzant",
        "byzantine", "byzantium", "byzanz", "rhomaioi", "ῥωμαῖοι",
        "impero d'oriente", "impero bizantino", "basileus", "costantinopoli",
        "constantinopoli", "constantinople", "carigrad", "konstantinopol",
        "κωνσταντινούπολις", "bisanzio", "nova roma",
    ],
    "greci": [
        "greci", "greco", "greca", "grk", "grci", "grka", "grcima", "grčki",
        "grčka", "grkinja", "greek", "greeks", "graeci", "graecorum",
        "έλληνες", "ellenico", "nazione greca", "comunità greca",
        "grčka zajednica", "rito greco", "grčki obred", "morae graecorum",
    ],
    "rito orientale": [
        "rito greco", "rito orientale", "greek rite", "eastern rite",
        "ortodosso", "ortodossa", "pravoslavni", "pravoslavna", "pravoslavlje",
        "orthodox", "orthodoxe", "ὀρθόδοξος", "uniate", "unijat", "grkokatolik",
        "greco-cattolico", "liturgia greca", "bizantski obred", "papà greco", "sacerdote greco",
        "caloiero", "hieromonaco", "jeromonah", "iconostasi", "ikonostas",
    ],
    "profughi": [
        "profugo", "profughi", "esule", "esuli", "rifugiato", "refugee",
        "izbjeglica", "izbjeglice", "prognanik", "emigrato", "emigrazione",
        "migrazione", "migracije", "doseljenici", "iseljenici", "diaspora",
        "dijaspora", "colonia greca", "grčka kolonija", "naseljavanje", "stratioti",
        "stradioti", "oltramarini", "prekomorske postrojbe",
    ],
    "levante veneziano": [
        "candia", "kandija", "kandijski", "creta", "kreta", "crete", "cretan",
        "kretski", "cretese", "chandax", "cipro", "cipar", "cyprus", "ciparski",
        "corfù", "corfu", "krf", "kerkyra", "κέρκυρα", "zante", "zakintos",
        "zakynthos", "cefalonia", "kefalonija", "morea", "moreja", "peloponneso",
        "peloponez", "negroponte", "eubea", "nauplia", "monemvasia", "malvasia",
        "corone e modone", "coron", "modone", "stato da mar", "levante",
    ],
    "adriatico orientale": [
        "dalmazia", "dalmacija", "dalmatinski", "dalmatia", "zara", "zadar",
        "iadera", "sebenico", "šibenik", "sibenik", "traù", "trogir", "spalato",
        "splitski", "ragusa", "dubrovnik", "cattaro", "kotor", "bocche di cattaro",
        "boka kotorska", "perasto", "perast", "curzola", "korčula", "korcula",
        "lesina", "hvar", "arbe", "rab", "isola di veglia", "krk", "cherso", "cres",
        "istria", "istra", "pula", "parenzo", "poreč", "peroi", "peroj",
        "capodistria", "koper", "pirano", "piran",
    ],
    "venezia": [
        "venezia", "venetia", "venice", "venedig", "mleci", "mletački",
        "mletačka republika", "serenissima", "san marco", "sv. marka",
        "basilica marciana", "procuratori de supra", "consiglio dei dieci",
        "doge", "dux venetiarum", "dux veneciarum", "dux venetie", "dux venecie",
        "scuola grande", "scuola piccola",
    ],
    "confraternite": [
        "confraternita", "confraternite", "scuola dei greci", "bratovština",
        "bratovstina", "bratovštine", "confraternity", "sodalizio",
        "scuola dalmata", "san giorgio degli schiavoni", "san giorgio dei greci",
        "sv. juraj i tripun", "mariegola", "gastaldo", "guardian grande",
    ],
    "reliquie e culto": [
        "reliquia", "reliquie", "relikvija", "relikvije", "relic", "relics",
        "culto", "kult", "štovanje", "stovanje", "devozione", "devotione",
        "processione", "processione", "procesija", "pellegrinaggio",
        "hodočašće", "ex voto", "zavjetni", "votivo", "miracolo", "čudo",
        "taumaturgo", "miracoloso", "čudotvorna",
    ],
    "pittori": [
        "madonneri", "madonnero", "pittori cretesi", "cretan painters",
        "kretski slikari", "scuola cretese", "italo-bizantino", "italogreco",
        "veneto-cretese", "kretsko-venecijansko", "bathas", "vathas",
        "damaskinos", "klontzas", "ritzos", "tzafouris", "tzafournaris",
        "angelos akotantos", "bizamano", "bitzamanos", "theotokopoulos",
        "el greco", "poulakis",
    ],
    "quarta crociata": [
        "quarta crociata", "fourth crusade", "iv crociata", "četvrti križarski",
        "1204", "bottino", "spoliation", "saccheggio", "sack of constantinople",
        "partitio romaniae", "partitio terrarum", "impero latino", "latin empire",
        "murzuflo", "murtzuphlos", "mourtzouphlos", "alessio v", "alexios v",
        "enrico dandolo", "villehardouin", "niceta coniata", "choniates",
        "robert de clari", "devastatio constantinopolitana",
    ],
    "fonti veneziane": [
        "ramusio", "sanudo", "sanuto", "diarii", "sansovino", "giovanni stringa",
        "tiepolo", "querini", "moravio", "boschini", "flaminio corner", "cornaro",
        "rodolfo gallo", "veludo", "ongania", "emmanuele cicogna", "romanin", "molmenti",
    ],
    "materialità": [
        "restauro", "restauri", "conservazione", "riza", "oklad", "coperta d'argento",
        "rivestimento", "cornice", "smalti", "cloisonné", "gemme", "perle",
        "tempera su tavola", "riflettografia", "radiografia", "infrarosso",
        "analisi dei pigmenti", "dendrocronologia", "imaging", "diagnostica",
    ],
}

# NUCLEI è il tesauro di partenza, «Venezia, Bisanzio, Adriatico». Da quando i
# tesauri stanno nella base dati — uno per ricerca, scelti cartella per
# cartella: vedi tesauri.py — serve solo a riempire il primo la prima volta.
# Le funzioni qui sotto lavorano su qualunque insieme di temi, {nome: forme};
# senza, usano quello che dice FONTE: tutti i tesauri in uso.
FONTE = lambda: NUCLEI


def piatto(s):
    s = unicodedata.normalize("NFKD", s.replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _mappa(nuclei):
    """Da ogni forma, scritta piatta, ai temi che la contengono."""
    fuori = {}
    for nucleo, forme in nuclei.items():
        for f in list(forme) + [nucleo]:
            p = piatto(f)
            if p:
                fuori.setdefault(p, set()).add(nucleo)
    return fuori


def nuclei_di(query, nuclei=None):
    """Quali nuclei concettuali tocca questa interrogazione."""
    nuclei = FONTE() if nuclei is None else nuclei
    q = piatto(query)
    trovati = set()
    for forma, ns in _mappa(nuclei).items():
        if forma in q:
            trovati |= ns
    return sorted(trovati)


def espandi(query, massimo=60, nuclei=None):
    """L'interrogazione più tutte le forme dei nuclei che tocca."""
    nuclei = FONTE() if nuclei is None else nuclei
    forme = {piatto(p) for p in re.findall(r"\w+", query, re.UNICODE) if len(p) > 2}
    for nucleo in nuclei_di(query, nuclei):
        for f in nuclei[nucleo]:
            forme.add(piatto(f))
    return sorted(f for f in forme if f)[:massimo]


def gruppi(query, nuclei=None):
    """Come si combina una ricerca per tesauro: ogni parola deve esserci, ma
    ognuna vale anche con tutte le sue varianti.

    Restituisce una lista di gruppi di forme: dentro un gruppo basta una
    forma (è la stessa cosa detta in modi diversi), e i gruppi devono esserci
    tutti. «icona greci candia» sono tre gruppi — le forme di icona, quelle
    di greci, quelle di Candia — e un documento va bene solo se li ha tutti e
    tre. Prima bastava uno qualsiasi: si trovavano i documenti che parlavano
    di icone, oppure di greci, oppure di Candia, cioè quasi tutti.
    """
    nuclei = FONTE() if nuclei is None else nuclei
    q = piatto(query)
    parole = [piatto(p) for p in re.findall(r"\w+", query, re.UNICODE) if len(p) > 2]
    per_parole = {}                            # parole coperte -> forme del tema
    for nucleo in nuclei_di(query, nuclei):
        forme = {piatto(f) for f in nuclei[nucleo]} | {piatto(nucleo)}
        # le parole della ricerca che fanno parte del modo in cui il tema è stato scritto
        coperte = frozenset(w for f in forme if f and f in q for w in f.split() if w in parole)
        if coperte:
            per_parole.setdefault(coperte, set()).update(forme)
    fuori, coperte_tutte = [], set()
    for coperte, forme in per_parole.items():
        fuori.append(sorted(forme))
        coperte_tutte |= coperte
    for w in parole:
        if w not in coperte_tutte:
            fuori.append([w])
    return fuori or [[piatto(query)]]


def spiega(query, nuclei=None):
    """Perché la ricerca è stata allargata, detto a chi la legge."""
    nuclei = FONTE() if nuclei is None else nuclei
    trovati = nuclei_di(query, nuclei)
    if not nuclei:
        return ("in questa cartella non c'è nessun tesauro in uso: qui tesauro ed esatta "
                "danno gli stessi risultati")
    if not trovati:
        return ("parola che i tesauri in uso non conoscono: qui tesauro ed esatta "
                "danno gli stessi risultati")
    aggiunte = sorted({f for g in gruppi(query, nuclei) if len(g) > 1 for f in g})
    esempio = ", ".join(aggiunte[:8]) + (" …" if len(aggiunte) > 8 else "")
    return (f"il tesauro ha riconosciuto: {', '.join(trovati)} — e ha cercato anche "
            f"{len(aggiunte)} varianti: {esempio}")
