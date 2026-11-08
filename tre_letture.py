#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tre letture di una riga, e per ogni parola vince quella su cui due concordano.

Per le stampe antiche nessun motore basta da solo. Tesseract (col dizionario
ita_old) mette gli spazi giusti ma scambia u e n («tramutanano»); GLM-OCR legge
meglio le lettere ma ogni tanto ne aggiunge («a'animici»); l'OCR che il PDF ha
già dentro (Google Books, Adobe) ha quasi sempre le lettere giuste e la ſ, ma
attacca le parole («Romatantopieua»). Sbagliano in posti diversi: così le parole
dove Tesseract e GLM concordano restano; dove no, decide il testo del PDF,
confrontato senza spazi. Se il PDF un testo non ce l'ha, vale GLM.
"""
import difflib
import itertools
import re

RX_TOLTI = re.compile(r"[^\w]", re.U)


def _piatto(s):
    """Per confrontare: minuscole, ſ e f come s (la s lunga è la stessa lettera
    per chi la legge e un errore per chi non la conosce), u e v uguali, senza
    spazi né punteggiatura."""
    s = s.lower().replace("ſ", "s").replace("f", "s").replace("v", "u")
    return RX_TOLTI.sub("", s)


def _presenza(candidato, terza):
    """Quanto del candidato si ritrova, di seguito, nella terza lettura (0-1)."""
    c = _piatto(candidato)
    if not c:
        return 0.0
    if c in terza:
        return 1.0
    m = difflib.SequenceMatcher(None, c, terza, autojunk=False).find_longest_match(0, len(c), 0, len(terza))
    return m.size / len(c)


def _con_f(s):
    """Come _piatto, ma la f resta f: serve a decidere fra f e ſ."""
    s = s.lower().replace("ſ", "s").replace("v", "u")
    return RX_TOLTI.sub("", s)


RX_LETTERE = re.compile(r"[^\W\d_]+", re.U)


def _f_o_s(parola, terza_f, prima="", dopo=""):
    """Le f della parola che nel testo del PDF sono ſ diventano s. Il testo di
    Google o di Adobe la ſ la distingue dalla f; Tesseract e GLM spesso no
    («diffe» per «diſſe»). Si cambia solo se una sola lettura si ritrova lì.
    Una parola corta («fi») si cerca con le vicine: da sola si ritroverebbe
    dentro chissà quale altra («fine»)."""
    def una(m):
        w = m.group(0)
        basso = w.lower()
        dove = [i for i, c in enumerate(basso) if c == "f"]
        if not dove or len(dove) > 4:
            return w
        if len(basso) < 4:
            avanti, dietro = _con_f(prima), _con_f(dopo)
            if not (avanti or dietro):
                return w
        else:
            avanti = dietro = ""
        cerca = lambda x: (avanti + _con_f(x) + dietro) in terza_f
        if cerca(w):
            return w
        trovate = set()
        for k in range(1, len(dove) + 1):
            for scelta in itertools.combinations(dove, k):
                c = list(w)
                for i in scelta:
                    c[i] = "S" if c[i] == "F" else "s"
                if cerca("".join(c)):
                    trovate.add("".join(c))
        return trovate.pop() if len(trovate) == 1 else w
    return RX_LETTERE.sub(una, parola)


def _e_un_numero(pezzo):
    """Il pezzo è un numero scritto bene: una cifra araba o un romano valido.

    Fra «DCCCXIII» e «ncccxin» non c'è da votare: il secondo non è un numero, e
    chi legge meglio le lettere non per questo legge meglio le cifre. Le regole
    sono quelle di verifica_numeri, che le ha già; si chiede tardi perché è
    verifica_numeri a importare questo modulo, non il contrario."""
    import verifica_numeri
    return bool(verifica_numeri.numeri(pezzo))


def vota(prima, seconda, terza=None, prima_migliore=False):
    """La riga votata: `prima` è Tesseract (dà le parole), `seconda` GLM-OCR,
    `terza` il testo del PDF per quella riga (o None).

    Con `prima_migliore` la prima lettura non è Tesseract ma il modello grosso
    che ha guardato la pagina intera, e allora i pareggi li vince lei. Il voto
    a maggioranza presuppone che i tre sbaglino in punti diversi; qui uno legge
    una lettera sbagliata ogni centosettanta e gli altri una ogni venticinque,
    e metterlo in minoranza peggiora la riga invece di migliorarla."""
    if not seconda:
        return prima
    if not prima:
        return seconda
    a, b = prima.split(), seconda.split()
    t = _piatto(terza) if terza else ""
    fuori = []
    sm = difflib.SequenceMatcher(None, [_piatto(x) for x in a], [_piatto(x) for x in b], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        pa, pb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        na, nb = _e_un_numero(pa), _e_un_numero(pb)
        if op == "equal":
            # le stesse parole: si tiene la grafia di GLM, che legge meglio la
            # punteggiatura e le maiuscole, se non toglie niente. Ma un numero
            # lo si lascia come l'ha scritto chi ha letto la pagina intera: il
            # maiuscoletto di una data va reso DCCLXIX, non dcclxix.
            if (na and nb) or prima_migliore:
                fuori.append(pa)
            else:
                fuori.append(pb if len(_piatto(pb)) >= len(_piatto(pa)) else pa)
            continue
        if na != nb:
            # uno dei due è un numero e l'altro no: non è un pareggio da
            # risolvere a maggioranza, è una lettura che il numero non l'ha visto
            fuori.append(pa if na else pb)
            continue
        if not t:
            fuori.append((pa or pb) if prima_migliore else (pb or pa))
            continue
        sa, sb = _presenza(pa, t), _presenza(pb, t)
        if op == "delete":          # solo Tesseract ha queste parole
            if sa >= 0.8:
                fuori.append(pa)
        elif op == "insert":        # solo GLM
            if sb >= 0.8:
                fuori.append(pb)
        else:
            fuori.append(pa if (sa >= sb if prima_migliore else sa > sb) else pb)
    riga = " ".join(x for x in fuori if x)
    if terza:
        tf = _con_f(terza)
        p = riga.split()
        riga = " ".join(_f_o_s(x, tf, p[i - 1] if i else "", p[i + 1] if i + 1 < len(p) else "")
                        for i, x in enumerate(p))
    return riga
