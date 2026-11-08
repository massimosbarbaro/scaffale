# Scaffale

Prende una cartella piena di file di ricerca — PDF, Word, appunti, scansioni,
cartelle di immagini che sono un libro smontato pagina per pagina — e la rende
un archivio interrogabile. Un indice solo, il link diretto a ogni documento e
alla pagina giusta, tre modi di cercarci dentro.

**Tutto resta sul tuo computer.** Nessun file viene caricato da nessuna parte,
nemmeno per la ricerca semantica.

---

## Installazione automatica (consigliata)

1. Estrai `Scaffale.zip` (tasto destro → *Estrai tutto…*) in una cartella tua,
   per esempio `Documenti\Scaffale`, e lasciala sempre lì.
2. Nella cartella, doppio clic su **`Installa Scaffale.bat`**.

Installa da solo, uno dopo l'altro, Python, i pacchetti di Scaffale, Tesseract,
Ollama e i tre modelli (bge-m3, qwen3:8b, glm-ocr), poi controlla tutto e mette
l'icona di Scaffale sul desktop. Quello che c'è già lo lascia com'è. Ci vogliono
da 30 a 60 minuti, quasi tutti di download (circa 10 GB): serve internet, e il
computer attaccato alla corrente. Due volte Windows chiede il permesso di
installare (Tesseract, Ollama): rispondi **Sì**. La prima volta winget, il
programma di Windows che scarica, può chiedere di accettare le sue condizioni
d'uso: scrivi **Y** e premi Invio.

Alla fine la finestra dice **TUTTO PRONTO**, oppure che cosa manca ancora: in
quel caso basta rilanciare `Installa Scaffale.bat`, che rifà solo quello.

Se qualcosa non va, sotto ci sono gli stessi passi da fare a mano.

---

## Installazione, passo per passo (a mano)

Su Windows 10 o 11. Ci vogliono una ventina di minuti, quasi tutti di download.

**1. La cartella.** Estrai `Scaffale.zip` (tasto destro → *Estrai tutto…*) in
una cartella tua, per esempio `Documenti\Scaffale`. Lasciala sempre lì: la base
dati con l'indice si crea dentro, in `dati\`.

**2. Python.** Da [python.org/downloads](https://www.python.org/downloads/)
scarica Python (3.9 o successivo) e lancia l'installazione. Nella prima
schermata **spunta *Add python.exe to PATH*** — è la casella in basso, facile da
saltare — poi *Install Now*. Se Python c'è già, salta questo passo.

**3. I pacchetti Python.** Nella cartella di Scaffale, doppio clic su
**`prepara.bat`**. Si apre una finestra nera che dice che cosa c'è e che cosa
manca; alla domanda *Installo …? [s/N]* scrivi **s** e premi Invio (due
volte: i pacchetti di base, poi quelli dei formati). Alla fine chiudi la
finestra.

**4. Tesseract, per leggere le scansioni.** Da
[github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
scarica l'installatore per Windows (64 bit) e installalo lasciando tutto com'è.
I dizionari delle lingue non servono: sono già in `tessdata\` dentro Scaffale
(italiano, latino, inglese, croato, sloveno, tedesco, francese, greco antico e
moderno). Senza Tesseract Scaffale funziona, ma le scansioni restano senza testo.

**5. Ollama, per la ricerca semantica e i riassunti.** Da
[ollama.com](https://ollama.com) scarica Ollama per Windows e installalo. Poi
apri il *Prompt dei comandi* (tasto Windows, scrivi `cmd`, Invio) e scrivi, una
riga alla volta:

```
ollama pull bge-m3
ollama pull qwen3:8b
ollama pull glm-ocr
```

Il primo (circa 1,2 GB) serve alla ricerca per senso; il secondo (circa 5 GB)
scrive i riassunti e risponde alle domande; il terzo (circa 2 GB) rilegge i
numeri delle scansioni e le righe delle stampe antiche: **senza, i .md non sono
verificati**. Si scaricano una volta sola e **girano sul computer**:
nessun documento esce dal PC. Senza Ollama restano la ricerca esatta e quella
per tesauro, che per la maggior parte del lavoro bastano.

**6. Controllo.** Doppio clic di nuovo su `prepara.bat`: ora ogni riga deve
dire `[ok]`. Quello che resta `[manca]` ha accanto la spiegazione.

**7. L'icona.** Doppio clic su **`Crea collegamento sul desktop.bat`**: sul
desktop compare l'icona di Scaffale. Da qui in poi basta quella.

---

## Come si comincia

Doppio clic sull'**icona di Scaffale** sul desktop (o su **`Avvia Scaffale.bat`**
nella cartella).

Il file di avvio fa tutto da sé: controlla che ci sia Python, lancia la
preparazione se manca qualcosa, accende Ollama se è installato ma spento, e
apre il browser appena Scaffale è pronto — ci vogliono pochi secondi. Resta una
finestra nera aperta: **è il programma che gira**. Non chiuderla a mano.

Dentro Scaffale ci si muove come in qualunque sito: i link, le frecce avanti e
indietro del browser, e il pulsante **← indietro** in alto a sinistra, su ogni
pagina. Un risultato, un brano, la scheda di un documento si aprono nella
stessa scheda del browser, così indietro riporta sempre alla ricerca; solo il
file vero — il PDF intero, il Word — si apre in una scheda sua.

**Per chiudere Scaffale** basta chiudere il browser, o la scheda di Scaffale:
pochi secondi dopo Scaffale se ne accorge, si spegne e la finestra nera
sparisce da sola. Oppure premi **Chiudi Scaffale**, in alto a destra, che prima
chiede conferma. Con un'eccezione voluta: se sta lavorando — un'indicizzazione,
il calcolo dei vettori, i riassunti — finisce prima il lavoro, e si spegne dopo.
Così si può chiudere il browser la sera e lasciarlo lavorare per la notte.

La prima schermata chiede **qual è la cartella con i tuoi file**: premi
*Sfoglia…* e scegli, dai un nome se vuoi, premi *Indicizza*.

### Prima di cominciare, il conto

Scaffale non parte subito. Prima **conta i file** — sottocartelle comprese — e ti
dice che cosa ha trovato e quanto ci vorrà:

> Nella cartella ci sono **1.313 documenti** (2,1 GB): 870 .pdf · 230 .docx · …
> Scansioni da riconoscere: circa 90 — in tutto circa **3.800 pagine**.

Poi ti chiede che cosa fare:

- **Solo i testi** — pochi minuti: legge i documenti che il testo ce l'hanno già.
  Le scansioni restano in attesa, e le riconosci quando vuoi.
- **Tutto, anche le scansioni** — può essere questione di ore.
- **Annulla**.

Quante siano le scansioni lo sa solo aprendo i PDF: ne apre un campione e stima
il resto, e te lo dice. Le stime vengono dai tempi misurati sul tuo computer, e
diventano più precise a ogni lavoro.

### Fermare un lavoro

Mentre lavora c'è il pulsante **Ferma**. Non interrompe di colpo: si ferma al
primo punto sicuro, tra un file e l'altro o tra una pagina e l'altra, e **tutto
quello che ha già fatto resta**. La volta dopo, *Aggiorna* riprende da lì. Lo
stesso vale per il calcolo dei vettori.

### Le tue cartelle

Dalla seconda volta in poi, aprendo Scaffale trovi per prime **le cartelle che
hai già indicizzato**, ciascuna con il suo percorso, quanti documenti contiene e
quando l'hai aggiornata l'ultima volta. Per ognuna:

- **Cerca qui dentro** — la ricerca guarda solo in quella cartella. Lo stesso si
  sceglie dal menu accanto alla casella di ricerca: *in tutte le cartelle*,
  *solo in «…»*. **La ricerca parte sempre da dove sei**: dalla scheda di una
  cartella, da un documento o da un brano cerca in quella cartella; da un
  gruppo aperto, solo in quel gruppo. Per cercare altrove si cambia il menu.
- **Aggiorna** — se nella cartella hai aggiunto file, ne hai cambiati o ne hai
  cancellati. Prima ti dice quanti sono e quanto ci vuole, come per una cartella
  nuova; poi legge i nuovi, rilegge i cambiati, toglie dall'indice i
  cancellati. Quelli che non hai toccato non li rilegge, e le scansioni già
  riconosciute non le riconosce una seconda volta. Alla fine ti dice quanti
  sono: *3 nuovi, 1 cambiati, 0 tolti, 1.309 invariati*.
- **apri la cartella** — la apre in Esplora risorse.

Se una cartella non si trova più — un disco staccato, OneDrive non ancora
sincronizzato — Scaffale lo dice e non tocca il suo indice: una cartella che
non si vede non è una cartella vuota.

Per aggiungerne una nuova c'è **+ Aggiungi un'altra cartella**, sotto l'elenco.
Se scegli una cartella che c'è già, viene aggiornata e tiene il suo nome.

Dal terminale: `python scaffale.py aggiorna Nicopeia`, oppure
`python scaffale.py aggiorna` per aggiornarle tutte.

---

## Che cosa sa leggere

I documenti veri e propri: `.pdf`, `.docx`, `.doc`, `.md`, `.txt`, `.htm`,
`.html`, `.epub`, `.rtf`, `.odt`, `.pptx`.

E anche quello che in un archivio di ricerca c'è sempre e che nessun programma
si aspetta: i fogli di calcolo `.xls`, `.xlsx`, `.ods`, gli elenchi `.csv` e
`.tsv`, i database di Access `.mdb` e `.accdb`.

Le tabelle diventano testo, con le intestazioni di colonna in testa e una riga
per riga. Il foglio, la tabella o la diapositiva fanno da numero di pagina: così
il risultato di una ricerca resta verificabile sull'originale, come per i PDF.

I database di Access del 1997 il driver di Microsoft si rifiuta di aprirli.
Scaffale li legge lo stesso, per conto suo.

`prepara.bat` installa da sé le librerie che servono. Se ne salti qualcuna, quei
file restano nell'archivio ma senza contenuto cercabile, e Scaffale ti dice
quale libreria gli manca invece di far finta che siano vuoti.

---

## I tre modi di cercare

**esatta** — tutte le parole che scrivi, così come le scrivi (maiuscole e
accenti non contano).

**tesauro** — tutte le parole, ma ognuna anche nelle sue varianti, grafie e
traduzioni, **se è un tema che il tesauro conosce**. Il tesauro incluso è
tarato su storia veneziana, bizantina e adriatica: scrivi «nicopeia» e cerca
anche *Nikopeja*, *Nikopoios*, *Madonna della Vittoria*, *Bogorodica
Pobjednica*. Per una parola che non conosce — un nome come «Cessi» — tesauro ed
esatta danno gli stessi risultati, e l'app lo dice. «icona greci candia» trova i
documenti che hanno tutti e tre i temi, scritti in uno qualsiasi dei loro modi:
nel mio archivio di prova 68 documenti, contro i 3 della ricerca esatta.

In tutti e due i casi le parole devono stare vicine, entro una pagina circa.

Sopra i risultati c'è sempre **quanti documenti contengono davvero quello che
cerchi**, e quanti se ne vedono: con *mostrane altri* si va avanti. Le copie di
uno stesso documento contano una volta sola.

**Aprendo un PDF dai risultati**, Scaffale non lo passa al lettore del browser,
che non saprebbe che cosa stavi cercando: ti mostra lui **la pagina dove sta la
parola**, con la parola in giallo e un segno rosso accanto alla prima, già
scorsa fino a quel punto. Da lì vai alle pagine vicine, o apri il PDF intero a
quella pagina. Se la pagina è una scansione senza testo, te lo dice e ti porta
al testo riconosciuto dall'OCR.

**I tesauri si fanno per ricerca**, dalla pagina **tesauri** (nel menu in alto).
Un tesauro è un elenco di temi, e un tema è un nome con le parole che lo dicono
in tutte le lingue e grafie che servono — *duello: duello, duellum, duel,
dvoboj, Zweikampf*. Se ne fa uno per ogni ricerca — «Progetti europei», «Duello
e onore», «Prezzi e inflazione» — e si sceglie quali usare in ogni cartella: la
ricerca in modo «tesauro» e la colonna dei temi di una cartella usano solo
quelli. Il primo, «Venezia, Bisanzio, Adriatico», è quello di partenza, e lo
usano le cartelle per cui non si è ancora scelto. Cambiato un tema, Scaffale lo
rifà subito nelle cartelle che lo usano e dice quanti file ci sono entrati. Non
serve toccare nessun file.

Una regola sola, ma importante: **ogni forma deve voler dire una cosa sola.**
Una parola che in un'altra lingua vuol dire anche altro va scritta con il suo
contesto. «dux» da solo è qualunque condottiero — nella Bibbia latina compare in
93 brani, e la Bibbia finiva nel tema «Venezia» — mentre «dux Venetiarum» è il
doge. Lo stesso per «scuola» (qualunque scuola: meglio «scuola dei greci»),
«split» (in inglese «dividere»: meglio «splitski»), «corner» (un angolo: meglio
«flaminio corner»).

**semantica** — confronta il senso con gli embedding. Trova accostamenti che il
tesauro non prevede; in cambio non sa dirti perché.

Perché funzioni bisogna prima calcolare i **vettori**: Scaffale fa leggere
ogni frammento a Ollama, che ne ricava un'impronta del senso. Si fa una volta
sola, dopo l'indicizzazione.

Nella pagina iniziale, finché i vettori non ci sono tutti, c'è un riquadro che
lo dice — *«la ricerca semantica vede solo 640 frammenti su 174.932»* — con un
pulsante per ogni cartella e il tempo che ci vuole. Si preme, compare una
barra, e si lascia lavorare. In alto a destra, accanto ai modi di ricerca, c'è
sempre scritto a che punto è la semantica.

**Il tempo dipende molto dal computer.** Con una scheda grafica sono decine di
frammenti al secondo; con il solo processore, meno di uno. Su un portatile senza
scheda grafica un archivio di 175.000 frammenti sono più di due giorni, una
cartella di 25.000 una notte. Per questo si può cominciare dalla cartella su cui
si lavora. Le copie dei doppioni non si calcolano due volte.

La finestra nera di Scaffale va lasciata aperta. Se la chiudi il calcolo si
ferma, e la volta dopo riprende da dove era, senza perdere niente.

Dal terminale è lo stesso:

```
python scaffale.py vettori --cartella Nicopeia
```

---

## Le domande ai documenti

Dalla voce **domande** in alto — o da *Fai una domanda ai documenti di questa
cartella*, nella scheda della cartella, o da un tema aperto — si scrive una
domanda, come in NotebookLM: *come si svolgeva il rito del bacio nelle paci
private?* Scaffale cerca i brani che rispondono, **dove ti trovi** (tutte le
cartelle, una sola, o un tema), per parole e, dove ci sono i vettori, per
senso; ne tiene sei, al massimo due da uno stesso testo, e il modello che gira
sul computer li legge e risponde **solo con quelli**, con il numero del brano
dopo ogni affermazione: [1], [3]. Ogni numero porta al brano, e ogni brano alla
sua pagina con le parole in giallo. Se i brani non bastano, lo dice.

Scaffale controlla la risposta: toglie i numeri di brani che non esistono e
corregge quelli sbagliati, e lo scrive sotto la risposta. **Il modello può
sbagliare, i brani no**: prima di citare, guarda il brano. Una risposta ci mette
circa 4 minuti su un computer senza scheda grafica; il pulsante *ferma* la
interrompe subito. Senza Ollama si vedono solo i brani trovati. Niente esce dal
computer. Le domande restano in elenco, con le loro risposte.

**Ogni numero della risposta è controllato**: se un anno, un prezzo o un numero
romano non sta nel brano che la frase cita, è segnato **⚠** in rosso, e sotto la
risposta c'è scritto dove sta davvero o che non c'è in nessun brano.

**Ricerca approfondita.** Per le domande difficili c'è il pulsante accanto a
*Chiedi ai documenti*: il modello fa un piano, cerca in più modi, legge i brani
uno per uno copiandone la frase chiave (Scaffale controlla che ci sia davvero),
cerca ancora se manca qualcosa, e scrive un rapporto controllato come le
risposte. Ci vogliono 20–30 minuti; sotto il rapporto, *Come ha lavorato* mostra
ogni passo. Mentre Scaffale lavora il computer non va in sospensione.

---

## La scheda di una cartella

Nell'elenco delle tue cartelle, **clicca il nome di una cartella**, o il pulsante
**Apri la scheda**: si apre tutto quello che Scaffale sa di quella cartella.
(*Cerca qui dentro* serve invece a cercare solo lì; anche lì, in cima, trovi i
numeri della cartella e il pulsante per la scheda.)

**In numeri.** Quanti documenti, quanto pesano, di che tipo; come Scaffale ha
avuto il testo di ciascuno — dal PDF, dall'OCR, da Word, da un foglio di calcolo
— e quanti sono scansioni ancora da riconoscere; quanti PDF hanno già il loro
`.md`; quanti documenti hanno una copia, qui o altrove; quanta parte è pronta
per la ricerca semantica.

**Come sono raggruppati.** Per cercarli, Scaffale indicizza ogni documento per
le parole che contiene: **nessuna classificazione per argomento**. Per
raggrupparli per materia Scaffale **analizza la cartella** — da pochi secondi a
qualche minuto, secondo quanti file ha — e li raccoglie in **un elenco solo,
«temi della cartella»**, dove ogni voce porta l'etichetta della sua
provenienza: *tuo*, *dal tesauro*, *proposto dal modello*, *scoperto*. Quando
due voci hanno quasi gli stessi file se ne vede una sola — prima quella decisa
da te, poi quella del tesauro, poi la proposta, poi quella scoperta — e sotto
c'è scritto *con quasi gli stessi file:* con le altre. I pulsanti sopra
l'elenco lo filtrano per provenienza. Accanto, a parte, le tue sottocartelle.
**Aprendo un tema si può cercare solo dentro quello**, con la casella *Cerca
nel gruppo*, o fargli una domanda.
L'analisi si fa da sola la prima volta che apri la scheda, e poi dopo ogni
indicizzazione o *Aggiorna* che ha trovato file nuovi, cambiati o tolti; aprire
la scheda altre volte non la rifà. Si rifà a mano con **Rifai l'analisi**.

- **le tue sottocartelle** — l'ordine che hai già dato tu ai file, sul disco:
  ogni sottocartella è un gruppo, e dentro le sue sottocartelle più grandi
  (*ALDHI*, *ALDHI › Lab HumaDig*…).
- **temi dei tesauri** — i temi dei tesauri che la cartella usa (si scelgono
  dalla pagina *tesauri*, o dal link nella colonna). Un documento entra in un tema se le parole del tema
  compaiono in almeno 3 suoi brani. Accanto a ogni file c'è il perché, con le
  parole trovate: *«venezia» in 35, «doge» in 11 — 42 brani su 115*. Così si
  controlla subito, aprendo il file, se il tema è giusto. Un tema che riguarda
  più di metà della cartella è segnato come *tema di fondo*.
- **gruppi scoperti** — Scaffale trova le *parole caratteristiche* di ogni
  documento, frequenti lì e rare nel resto dell'archivio, e mette insieme i
  documenti che ne hanno una in comune: *mairano*, *translatio*, *genova*,
  *grosso · silver · coins*. Non sa che cosa significhino: sono proposte, da
  tenere, rinominare o eliminare. Una proposta eliminata non torna. Prima
  vengono le più grandi; poi, segnate *— in …*, quelle tipiche di una
  sottocartella, che altrimenti sparirebbero sotto le altre. Accanto a ognuna
  c'è **+ tieni**: con un clic il gruppo passa fra i tuoi, con lo stesso nome e
  gli stessi file, e da lì non cambia più da solo.
- **temi proposti dal modello** — premi *Fai proporre i temi al modello*: il
  modello che gira sul computer legge il profilo della cartella (il titolo e
  le parole caratteristiche di ogni file) e propone i temi di ricerca che la
  attraversano — per Paci medievali *duello e onore*, *mediazione e pace*,
  *riti della pace*… Ci vogliono alcuni minuti, e intanto si lavora. Scaffale
  controlla ogni tema sui documenti e dice in quanti file sta e quali delle
  sue parole ci sono davvero (solo quelle che stanno in almeno due file);
  quelli che stanno in più di metà della cartella sono segnati *tema di
  fondo*: in una cartella di una ricerca sola, è il tema centrale. Gli errori
  di lettura delle stampe antiche («cofa» per «cosa»), i pezzi di parola
  («conf») e le parole attaccate («regoleper») si scartano da soli, e due
  proposte quasi uguali diventano una. **Aprendo la proposta** si tolgono le
  parole sbagliate e se ne aggiungono di proprie, prima di tenerla; dopo, le
  parole si cambiano con *cambia le parole*.
  **Tieni** fa del tema un tema della cartella
  (nel tesauro «Temi di …», che si crea da solo), e i file ci entrano da soli;
  **scarta** lo toglie, e non torna la volta dopo. Non serve la ricerca
  semantica: basta Ollama.
- **i tuoi gruppi e temi** — un *gruppo* lo crei con *+ nuovo gruppo* e ci metti
  i file che vuoi. Un *tema* lo crei con **+ nuovo tema con le tue parole**: gli
  dai un nome e le parole che lo dicono, in tutte le lingue che servono —
  *AI, intelligenza artificiale, artificial intelligence, umetna inteligenca,
  LLM* — e Scaffale ci mette da solo i file in cui compaiono in almeno 2 brani,
  dicendo per ognuno quali parole e quante volte. Le sigle scritte in maiuscolo
  (AI, LLM) valgono solo in maiuscolo, così «AI» non prende la preposizione
  «ai». Il tema si aggiorna da solo a ogni analisi, e le parole si cambiano con
  *cambia le parole*. È il modo per i temi che il tesauro non conosce: il tuo
  laboratorio, un progetto, un argomento di ricerca.

Nell'elenco dei file spunti quelli che ti interessano e li **metti** in un
gruppo, o li **sposti** da quello che stai guardando a un altro. Si rinominano
ed eliminano i gruppi quando vuoi. **I gruppi sono etichette dentro Scaffale:
i file sul disco non si spostano mai.** E quello che fai a mano resta anche
quando rifai l'analisi: un file che hai tolto da un tema non ci rientra.

**Di che cosa parlano.** Quanti file hanno già il riassunto, e il pulsante
**Scrivi i riassunti degli altri**, con il tempo che ci vuole: li scrive uno dopo
l'altro un modello di Ollama che gira sul computer, circa due minuti ciascuno su
un computer senza scheda grafica. Per una cartella grande sono giorni: meglio
cominciare da quelli che servono, spuntandoli nell'elenco e premendo **riassumi
quelli spuntati**, o dai file di un gruppo con **riassumi i file di questo
gruppo**. Si può fermare quando vuoi, e quelli fatti restano; la volta dopo
continua da dove era. Sono automatici e possono sbagliare.

**I file**, divisi per sottocartella, ognuno con sotto il suo riassunto — o,
finché manca, le sue prime righe — le parole caratteristiche e i gruppi in cui
sta. Con i filtri: solo i PDF, i PDF senza `.md`, quelli con copie, le scansioni
da riconoscere, quelli senza testo. Accanto a ogni PDF che non ha il `.md` c'è
il pulsante **crea .md**; in cima quello per crearli tutti.

## La scheda di un documento

Cliccando il nome di un file: dove sta, come Scaffale ha avuto il testo, quando
l'ha indicizzato, se ha il `.md`, **dove sono le sue copie**, le sue parole
caratteristiche, come comincia, e i gruppi in cui sta, con il perché e i
comandi per spostarlo. Per i PDF che lo portano con sé c'è anche **l'indice del
documento** — capitoli e paragrafi — e ogni titolo apre la sua pagina.

C'è anche il **riassunto**: lo scrive su richiesta un modello di Ollama che gira
sul computer — niente esce dal PC. Su un computer senza scheda grafica ci
vogliono un paio di minuti, e può sbagliare: la scheda lo dice, e va
controllato sul testo prima di fidarsi. Scaffale non usa mai i modelli di
Ollama che girano su internet, quelli che finiscono per `:cloud`.

## I doppioni

Scaffale trova i documenti con **lo stesso testo**, poi confronta i file uno
per uno e dice di ciascuno che cosa sono:

- **file identico** — proprio lo stesso file, salvato in due posti: stessa
  dimensione, stesso contenuto. Una copia in più, da togliere senza perdere
  niente.
- **file diverso** — stesso testo, ma non lo stesso file. Di solito un PDF e la
  sua versione compressa (per esempio 77 MB e 33 MB: quella piccola ha le
  immagini a qualità più bassa), o due scansioni dello stesso libro. Non è una
  copia da buttare a occhi chiusi.
- **comincia con lo stesso testo, ma è più corto** — con quante pagine o parole
  contro quante: di solito un capitolo staccato dal libro intero.

Per ogni file: tipo, dimensione, data, cartella, e i comandi **apri**, **mostra
nella cartella** e **Sposta nel Cestino**. Se il file che stai togliendo non ha
copie identiche, Scaffale ti avverte prima. Il file spostato finisce nel Cestino
di Windows — o in quello di OneDrive, se sta lì — e si recupera quando vuoi.
L'ultimo file di un gruppo non si può spostare: ne resta sempre almeno uno. Su
un disco di rete o una chiavetta, dove il Cestino non c'è, Scaffale si rifiuta.

Per molte copie insieme, dal terminale:

```
python scaffale.py copie                l'elenco, con identici e diversi
python scaffale.py deduplica            mostra che cosa farebbe
python scaffale.py deduplica --esegui   lo fa
```

che non cancella niente e tocca **solo le copie identiche**: le sposta in
`quarantena\`, conservando l'albero delle cartelle. I file diversi con lo
stesso testo restano dove sono.

---

## Dai PDF ai file .md

Sotto i risultati di una ricerca c'è **«Crea i .md dei PDF trovati»**: scrive un
file Markdown accanto a ogni PDF, con la provenienza in testa e i cambi di
pagina segnati.

Serve per rileggere, per cercare, per darlo in pasto a un modello linguistico.
Ma in testa a ogni file c'è un'avvertenza da prendere sul serio: **una
trascrizione automatica sbaglia sui numeri** — date, cifre, numeri romani. Per
questo il file porta il rimando alla pagina dell'originale.

**Il PDF e il suo .md sono un documento solo.** Scaffale trova il .md anche
nella sottocartella `markdown`; nella scheda della cartella la coppia è una riga
sola, con un giudizio sul .md — **buono**, **da controllare**, **da rifare** — e i
motivi (pagine mancanti o vuote, testo illeggibile, la s lunga letta f, numeri
non verificati). Dove serve c'è *rifai il .md con la verifica dei numeri*: quello
vecchio resta accanto come `.md.vecchio`. Di una coppia si fa un riassunto solo.

**Sistema tutta la cartella.** Nella scheda di una cartella c'è un pannello con
un pulsante solo: crea i .md che mancano, rifà quelli da rifare, aggiorna
l'indice e l'analisi (temi, gruppi) e alla fine scrive i riassunti che mancano,
con il modello sul computer. Ogni voce dice quanto ci vorrà; per una cartella
grande si lancia la sera, e *ferma* lo interrompe quando vuoi. **La notte il
computer va lasciato attaccato alla corrente e con lo schermo aperto**: Scaffale
lo tiene sveglio da solo, ma se Windows lo addormenta lo stesso (coperchio chiuso,
batteria) il lavoro si ferma. Non si perde niente: ogni pagina letta resta
salvata, e rilanciando si riprende da dove era arrivato. Le stampe antiche
con la s lunga letta f («fopra», «quefto») si rileggono da sole con un dizionario
fatto per le stampe antiche, e le parole rimaste sbagliate si correggono.

**Se in Ollama c'è il modello GLM-OCR** (circa 2 GB), i numeri delle
scansioni si leggono due volte, da due programmi diversi, e valgono solo se le
due letture concordano. Dove non concordano la riga del `.md` porta
*[⚠ verificare …]*, e nella scheda della cartella il PDF dice «N righe con
numeri da verificare»: il link apre una pagina con il pezzo dell'originale, le
due letture e un campo per scrivere quella giusta; *salva* la mette nel `.md`. I
PDF nati digitali, con il testo dell'editore, non si rileggono. Costa circa 4
minuti per una pagina fitta di note: per una cartella grande, si lancia la sera.
Se `prepara.py` ha installato anche PaddleOCR (lo propone, circa 280 MB), dove le
due letture non concordano ne fa una terza: se dà ragione a una delle due, la
riga è decisa e non resta da guardare. Così le righe da verificare a mano sono
molte di meno.

I `.md` che esistono già **non vengono sovrascritti**: vengono confrontati con
il testo estratto ora, e le differenze finiscono in un rapporto che segnala
soprattutto le cifre discordanti.

---

## Dal terminale

```
python scaffale.py indicizza "C:\...\cartella" --nome unNome
python scaffale.py cerca "candia" --semantica
python scaffale.py stato          quanti documenti, parole, vettori
python scaffale.py mute           le scansioni ancora senza testo
python scaffale.py esporta "skopiotissa" --nome una_ricerca
```

L'esportazione fa una cartella con i PDF trovati, l'elenco in Markdown con i
brani, un CSV e un `.bib` per Zotero. Si carica in NotebookLM così com'è.

---

## Se qualcosa non va

**«python non è riconosciuto»** — Python non è nel PATH. Reinstallalo spuntando
*Add Python to PATH*, oppure usa il percorso completo.

**Le scansioni restano vuote** — manca Tesseract, o Scaffale non lo trova.
Apri `scaffale.ini` e scrivi il percorso dell'eseguibile alla voce `tesseract`.

**La ricerca semantica non dà nulla** — o Ollama è spento (`ollama serve`), o i
vettori non sono stati calcolati (`python scaffale.py vettori`).

**Doppio clic sull'icona e non succede niente** — aspetta una decina di
secondi: il browser si apre solo quando Scaffale è pronto. Se Scaffale era già
aperto, riapre quello. Se la porta 8000 è occupata da un altro programma, ne
sceglie da solo un'altra.

**La finestra nera dice «si è fermato per un errore»** — resta aperta apposta:
fanne una foto e mandala a chi ti ha dato Scaffale.

**Ollama non risponde** — di solito parte da solo con Windows (icona del lama
vicino all'orologio). Se non c'è, aprilo dal menu Start.

---

## Com'è fatto, in breve

Una base SQLite con i documenti, i frammenti di testo da circa 2.400 caratteri
— ciascuno con il numero di pagina da cui viene — e un indice FTS5. I vettori
stanno a parte e possono mancare senza che il resto smetta di funzionare.

I frammenti conservano il numero di pagina di proposito: **il brano che leggi
nei risultati deve essere verificabile**. Il link ti porta alla pagina esatta
del PDF, e da lì controlli sull'originale. Una trascrizione automatica sbaglia,
prima o poi, e quando sbaglia lo fa sui numeri: date, cifre, numeri romani.
Per questo l'originale deve restare a un clic di distanza.
