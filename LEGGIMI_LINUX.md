# Scaffale su Linux

## Che cos'è

Scaffale prende le cartelle di un archivio di ricerca — PDF, Word, appunti, fogli,
scansioni, libri fotografati pagina per pagina — e le rende un archivio
interrogabile, **tutto sul computer, senza mandare niente in rete**:

- **un indice** di tutti i file, con i doppioni riconosciuti;
- **la ricerca** per parole (con varianti e tesauri), per senso, e il link che apre
  la pagina giusta del PDF con le parole evidenziate;
- **i temi** di ogni cartella, proposti leggendo i contenuti;
- **un riassunto** di ogni documento, scritto dal modello sul computer;
- **le domande ai documenti**, come NotebookLM: risponde solo con i brani dei tuoi
  file, con le citazioni [1], [2], e segna i numeri che non trova nei brani; e una
  *ricerca approfondita* che fa un piano, cerca più volte e scrive un rapporto;
- **i .md verificati** dei PDF: le scansioni si leggono riga per riga e colonna per
  colonna, e le righe con numeri si rileggono con un secondo programma (e un terzo
  dove i primi due non concordano); quello che resta dubbio è segnato *[⚠
  verificare]* e si corregge guardando il pezzo dell'originale. Le stampe antiche
  (la s lunga, «fopra», «quefto») si leggono col dizionario dell'italiano antico e
  tre letture che votano parola per parola;
- **«Sistema tutta la cartella»**: un pulsante solo che crea i .md che mancano,
  rifà quelli cattivi, rifà l'analisi e scrive i riassunti. Si lancia la sera.

Il programma è lo stesso della versione per Windows: cambia solo come si installa
e come si apre. La spiegazione completa di come funziona è in `GUIDA.md`, l'uso
passo per passo in `LEGGIMI.md` (scritto per Windows: le differenze sono qui sotto).

## Installazione

Su Ubuntu o Debian (anche Linux Mint, Pop!_OS), Fedora, Arch. Servono circa 15 GB
liberi, internet per un'ora, e la password di amministratore.

1. **Scarica Scaffale in una cartella tua, fuori da OneDrive o da altre cartelle
   sincronizzate.** Scaffale tiene la sua base dati dentro la sua cartella: in una
   cartella sincronizzata verrebbe copiata mentre la scrive. I tuoi documenti invece
   possono restare dove sono.

   ```
   cd ~ && git clone https://github.com/massimosbarbaro/scaffale.git Scaffale
   ```

   oppure scarica lo zip della versione da GitHub (*Code → Download ZIP*) ed
   estrailo in `~/Scaffale`.

   Così nasce la cartella `~/Scaffale`.

2. **Installa tutto:**

   ```
   cd ~/Scaffale
   ./installa.sh
   ```

   Installa i programmi di sistema (Python, Tesseract, unixODBC, gio, curl), crea un
   ambiente Python tutto suo in `~/Scaffale/.venv` (il Python del sistema non si
   tocca), installa Ollama con lo script ufficiale di ollama.com se non c'è, scarica
   i tre modelli — **bge-m3** (ricerca per senso, 1,2 GB), **qwen3:8b** (riassunti,
   temi, risposte, 5 GB), **glm-ocr** (la seconda lettura delle scansioni, 2 GB:
   senza, i .md non sono verificati) — poi controlla tutto e mette Scaffale nel menu
   delle applicazioni e sul desktop. Alla fine dice **TUTTO PRONTO**, o che cosa
   manca: in quel caso si rilancia, e rifà solo quello.

## Come si usa

- **Aprire:** l'icona *Scaffale* (menu delle applicazioni o desktop), oppure
  `~/Scaffale/avvia.sh`. Si apre un terminale — è il programma che gira, non va
  chiuso a mano — e poco dopo il browser su `http://127.0.0.1:8000`.
- **La prima volta:** *Sfoglia…*, scegli la cartella dei documenti (anche dentro
  OneDrive), *Indicizza*. Prima di cominciare dice quanti file ci sono e quanto ci
  vorrà; *solo i testi* è questione di minuti, *tutto, anche le scansioni* di ore.
- **Cercare:** la casella in alto; dai risultati si apre la pagina del PDF.
- **La scheda di una cartella** (dall'elenco *cartelle*): temi, doppioni, .md con il
  loro giudizio (*buono*, *da controllare*, *da rifare*), il pannello **Sistema tutta
  la cartella**.
- **Domande:** la pagina *domande*. Circa 4 minuti a risposta.
- **Numeri da verificare:** nella scheda della cartella, accanto a un PDF, «N righe
  con numeri da verificare»: si apre il pezzo dell'originale e si scrive la riga
  giusta.
- **Chiudere:** si chiude la scheda del browser, o *Chiudi Scaffale* in alto a
  destra. Se sta lavorando, finisce prima e poi si chiude da solo.

## Che cosa cambia rispetto a Windows

- **I .md e i loro `.verifica.json`** stanno accanto ai PDF, nelle cartelle dei
  documenti: se i documenti sono in OneDrive, ci sono già anche su Linux, fatti su
  Windows, e Scaffale li riconosce e li usa.
- **L'indice invece si rifà.** La base dati di Windows (`Scaffale\dati\`) ricorda i
  percorsi di Windows (`C:\Users\…`), che su Linux non esistono: su Linux si
  aggiungono le cartelle da capo. La lettura dei testi è veloce; l'OCR delle
  scansioni senza testo è la parte lunga.
- **Non usare la stessa cartella Scaffale da due computer.** Ognuno ha la sua copia,
  con la sua base dati.
- **Il computer resta sveglio** durante i lavori lunghi con `systemd-inhibit`; un
  portatile col coperchio chiuso si può addormentare lo stesso, a seconda delle
  impostazioni: per le notti, attaccato alla corrente e aperto. Se si addormenta non
  si perde niente: la lettura di un PDF riparte dalla pagina dove era arrivata.
- **Il Cestino** è quello del sistema (`gio trash`, lo stesso del file manager): un
  doppione tolto da Scaffale si recupera da lì. Dove il Cestino non c'è (un disco di
  rete), Scaffale non cancella e lo dice.
- **Ollama** su Linux gira come servizio di sistema (`systemctl status ollama`); se è
  spento, `avvia.sh` lo accende.

## Se qualcosa non va

- *«Manca qualcosa: lancia prima ./installa.sh»* — l'ambiente `.venv` non c'è o è
  incompleto: `cd ~/Scaffale && ./installa.sh`.
- *Il browser non si apre* — apri a mano `http://127.0.0.1:8000`.
- *Le scansioni restano senza testo* — manca Tesseract: `tesseract --version`.
- *Niente riassunti, domande o .md verificati* — Ollama spento o senza modelli:
  `ollama list` deve mostrare bge-m3, qwen3:8b e glm-ocr.
- Il controllo completo: `cd ~/Scaffale && .venv/bin/python prepara.py`.
