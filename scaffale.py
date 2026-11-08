#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scaffale — indicizza un archivio di ricerca disordinato e lo rende interrogabile.

    python scaffale.py indicizza "C:\\...\\una cartella"
    python scaffale.py indicizza "C:\\...\\altra" --nome Nicopeia
    python scaffale.py aggiorna Nicopeia       rilegge file nuovi, cambiati, tolti
    python scaffale.py vettori                 calcola gli embedding (serve Ollama)
    python scaffale.py servi                   apre l'app su http://127.0.0.1:8000
    python scaffale.py cerca "nicopeia"        la stessa ricerca da terminale
    python scaffale.py stato                   che cosa c'è dentro
    python scaffale.py copie                   i doppioni, con lo spazio sprecato
    python scaffale.py mute                    le scansioni ancora senza testo
"""
import argparse
import os
import sys
import webbrowser

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

import archivio        # noqa: E402
import impostazioni    # noqa: E402
import tesauro         # noqa: E402


def c_indicizza(a):
    n = archivio.indicizza(a.cartella, radice=a.nome, ocr=not a.senza_ocr,
                           ricomponi=not a.senza_immagini, riprendi=not a.daccapo)
    print(f"\nFatto: {n} documenti.")
    print("Ora: python scaffale.py vettori   (per la ricerca semantica)")
    print("     python scaffale.py servi     (per aprire l'app)")


def c_aggiorna(a):
    elenco = archivio.radici()
    scelte = [r for r in elenco if not a.nome or r["radice"] == a.nome]
    if not scelte:
        print(f"Non c'è una cartella chiamata «{a.nome}». Quelle indicizzate sono:")
        for r in elenco:
            print(f"  {r['radice']:<30} {r['percorso']}")
        return
    for r in scelte:
        if not r["esiste"]:
            print(f"— {r['radice']}: la cartella non si trova ({r['percorso']}), la salto.")
            continue
        print(f"— aggiorno {r['radice']}  ({r['percorso']})")
        archivio.indicizza(r["percorso"], radice=r["radice"], ocr=not a.senza_ocr)


def c_vettori(a):
    import semantica
    semantica.calcola(limite=a.limite, radice=a.cartella)


def _e_scaffale(url):
    """Sulla porta risponde Scaffale? Si chiede a /vivo, che risponde subito."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(url + "/vivo", timeout=1.5) as r:
            return json.loads(r.read()).get("scaffale") is True
    except Exception:
        return False


def _occupata(porta):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def c_servi(a):
    """Accende Scaffale e apre il browser — ma solo quando è pronto.

    Aprire il browser subito, come si faceva prima, voleva dire arrivare
    sulla porta prima del server: il browser trovava chiuso, mostrava «sito
    non raggiungibile», e sembrava che l'icona non facesse niente. Adesso si
    aspetta che Scaffale risponda. E se Scaffale è già acceso — l'icona premuta
    due volte — non se ne avvia un secondo: si riapre il primo.
    """
    import threading
    import time
    import uvicorn
    porta = a.porta
    url = f"http://127.0.0.1:{porta}"
    if _e_scaffale(url):
        print("  Scaffale è già aperto: te lo riapro nel browser.")
        print("  (Se vuoi chiuderlo, chiudi l'altra finestra nera.)")
        if not a.senza_browser:
            webbrowser.open(url)
        time.sleep(3)
        return
    if _occupata(porta):
        libera = next((p for p in range(porta + 1, porta + 30) if not _occupata(p)), None)
        if libera is None:
            print(f"  Le porte da {porta} a {porta + 29} sono tutte occupate.")
            return
        print(f"  La porta {porta} è occupata da un altro programma: uso la {libera}.")
        porta, url = libera, f"http://127.0.0.1:{libera}"
    print(f"  Sto accendendo Scaffale su {url} …")

    def apri_quando_pronto():
        for _ in range(240):                     # fino a due minuti
            if _e_scaffale(url):
                print("  Pronto. Si apre il browser.")
                print("  Per chiudere Scaffale, chiudi questa finestra.\n")
                if not a.senza_browser:
                    try:
                        webbrowser.open(url)
                    except Exception:
                        print(f"  Non riesco ad aprire il browser: vai tu su {url}")
                return
            time.sleep(0.5)
        print(f"  Scaffale non risponde ancora. Prova ad aprire tu {url}")

    threading.Thread(target=apri_quando_pronto, daemon=True).start()
    # aperto col browser, Scaffale si spegne da solo quando il browser si chiude;
    # lanciato senza, per usarlo da un altro programma, resta acceso
    if not a.senza_browser:
        os.environ["SCAFFALE_SPEGNI_DA_SOLO"] = "1"
    uvicorn.run("web:app", host="127.0.0.1", port=porta, log_level="warning")


def c_cerca(a):
    voci = archivio.cerca(a.query, a.modo, a.limite)
    if a.semantica:
        import semantica as sem
        for punteggio, fr, d in sem.cerca(a.query, a.limite):
            if punteggio >= 0.35:
                voci.append({"nome": d["nome"], "percorso": d["percorso"],
                             "pagina": d["pagina"], "radice": d["radice"],
                             "testo": d["testo"], "semantico": punteggio, "copie": 1})
    print(f"{len(voci)} risultati · {tesauro.spiega(a.query)}\n")
    for v in voci:
        s = f" · affinità {v['semantico']:.2f}" if v.get("semantico") else ""
        print(f"— {v['nome'][:88]}  (p. {v.get('pagina') or '?'}{s})")
        print(f"  {v['percorso']}")
        # il ritaglio è centrato sulla parola trovata: i segni di servizio
        # diventano asterischi, che in un terminale si vedono
        brano = (v.get("brano") or v.get("testo") or "")[:300]
        print(f"  {brano.replace(chr(2), '*').replace(chr(3), '*')}\n")


def c_stato(a):
    s = archivio.statistiche()
    print(f"documenti   {s['documenti']:>7}")
    print(f"  di cui indicizzati {s['indicizzati']}, da riconoscere {s['da_ocr']}")
    print(f"frammenti   {s['frammenti']:>7}")
    print(f"vettori     {s['vettori']:>7}")
    print(f"parole      {s['parole']:>7}")
    print(f"gruppi di copie {s['copie']}")
    print("\nper radice:")
    for r in s["radici"]:
        print(f"  {r['radice'][:40]:<42} {r['n']}")
    try:
        import semantica
        print(f"\nOllama: {'acceso' if semantica.acceso() else 'spento'}")
        if semantica.acceso():
            print("  modelli:", ", ".join(semantica.modelli()[:6]))
    except Exception:
        pass


def c_deduplica(a):
    import strumenti
    strumenti.deduplica(esegui=a.esegui)


def c_esporta(a):
    import strumenti
    voci = archivio.cerca(a.query, "tesauro", a.limite)
    strumenti.esporta(voci, a.nome)


def c_trascrivi(a):
    import trascrizioni, os
    voci = archivio.cerca(a.query, "tesauro", a.limite)
    esiti = trascrizioni.trascrivi_molti([v["percorso"] for v in voci],
                                         sovrascrivi=a.sovrascrivi)
    dest = os.path.join(QUI, "esportazioni", "rapporto_trascrizioni.md")
    print("\n" + trascrizioni.rapporto(esiti, dest))
    print(f"rapporto in {dest}")


def c_azzera(a):
    s = archivio.statistiche()
    if not a.conferma:
        print(f"Nell'archivio ci sono {s['documenti']} documenti.")
        print("Svuotare l'indice NON cancella nessun file sul disco: toglie solo")
        print("quello che Scaffale ha imparato, e si riparte da capo.")
        print("\nPer farlo davvero:  python scaffale.py azzera --conferma")
        return
    quanti = archivio.azzera()
    print(f"Indice svuotato: {quanti} documenti dimenticati. I file sono al loro posto.")


def c_copie(a):
    # stesso testo non vuol dire stesso file: un PDF e la sua versione compressa
    # hanno lo stesso testo, ma non sono una copia da buttare
    import strumenti
    gruppi = strumenti.gruppi_copie()
    sprecato = sum(g["ridondanti"] for g in gruppi)
    print(f"{len(gruppi)} gruppi di file con lo stesso testo · copie identiche "
          f"~{sprecato/1e9:.1f} GB\n")
    for g in gruppi[:a.limite]:
        quanti = ("copie identiche" if g["tutti_identici"] else
                  "file con lo stesso testo" if g["stesso_testo"] else
                  "file che cominciano con lo stesso testo")
        print(f"— {g['documenti'][0]['nome'][:70]}  ({g['copie']} {quanti}, {g['byte']/1e6:.0f} MB)")
        for d in g["documenti"]:
            com_e = ("identico" if d["identici"] else
                     "diverso " if d["firma"] else "non confrontato")
            corto = (f"  — più corto: {d['pagine'] or 0} pagine, {d['parole'] or 0} parole"
                     if d["piu_corto"] else "")
            print(f"    [{com_e}] {(d['byte'] or 0)/1e6:6.0f} MB  {d['percorso']}{corto}")


def c_mute(a):
    c = archivio.apri()
    righe = c.execute("""SELECT nome, pagine, percorso FROM documenti
                         WHERE stato='da_ocr' ORDER BY pagine DESC""").fetchall()
    print(f"{len(righe)} scansioni senza testo, {sum(r['pagine'] or 0 for r in righe)} pagine\n")
    for r in righe[:a.limite]:
        print(f"— {r['nome'][:74]}  ({r['pagine']} pp.)\n    {r['percorso']}")


def main():
    ap = argparse.ArgumentParser(description="Scaffale")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("indicizza"); p.add_argument("cartella")
    p.add_argument("--nome", default=None, help="etichetta della radice")
    p.add_argument("--senza-ocr", action="store_true")
    p.add_argument("--senza-immagini", action="store_true")
    p.add_argument("--daccapo", action="store_true")
    p.set_defaults(f=c_indicizza)

    p = sub.add_parser("aggiorna", help="rilegge le cartelle già indicizzate")
    p.add_argument("nome", nargs="?", default=None,
                   help="il nome della cartella; senza, le aggiorna tutte")
    p.add_argument("--senza-ocr", action="store_true")
    p.set_defaults(f=c_aggiorna)

    p = sub.add_parser("vettori"); p.add_argument("--limite", type=int, default=None)
    p.add_argument("--cartella", default=None,
                   help="solo una cartella indicizzata, col nome che ha nella pagina cartelle")
    p.set_defaults(f=c_vettori)

    p = sub.add_parser("servi"); p.add_argument("--porta", type=int, default=impostazioni.porta())
    p.add_argument("--senza-browser", action="store_true"); p.set_defaults(f=c_servi)

    p = sub.add_parser("cerca"); p.add_argument("query")
    p.add_argument("--modo", default="tesauro", choices=["tesauro", "esatta"])
    p.add_argument("--semantica", action="store_true")
    p.add_argument("--limite", type=int, default=20); p.set_defaults(f=c_cerca)

    p = sub.add_parser("stato"); p.set_defaults(f=c_stato)
    p = sub.add_parser("deduplica")
    p.add_argument("--esegui", action="store_true",
                   help="sposta davvero le copie in quarantena")
    p.set_defaults(f=c_deduplica)
    p = sub.add_parser("esporta"); p.add_argument("query")
    p.add_argument("--nome", default=None); p.add_argument("--limite", type=int, default=40)
    p.set_defaults(f=c_esporta)
    p = sub.add_parser("trascrivi"); p.add_argument("query")
    p.add_argument("--limite", type=int, default=40)
    p.add_argument("--sovrascrivi", action="store_true",
                   help="riscrive anche i .md che esistono gia")
    p.set_defaults(f=c_trascrivi)
    p = sub.add_parser("azzera")
    p.add_argument("--conferma", action="store_true",
                   help="svuota davvero l'indice (i file sul disco restano)")
    p.set_defaults(f=c_azzera)
    p = sub.add_parser("copie"); p.add_argument("--limite", type=int, default=25)
    p.set_defaults(f=c_copie)
    p = sub.add_parser("mute"); p.add_argument("--limite", type=int, default=40)
    p.set_defaults(f=c_mute)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
