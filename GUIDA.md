# Scaffale

Prende una cartella di archivio disordinata — PDF, Word, testi, scansioni mute,
cartelle di immagini che sono un libro smontato pagina per pagina — e la rende
un archivio interrogabile: un indice unico, con il link diretto a ogni file e
alla pagina giusta, e tre modi di cercarci dentro.

Tutto resta sul computer. Niente va in rete, nemmeno la ricerca semantica.
Internet serve solo per installare.

---

## Installare

Su Windows 10 o 11, doppio clic su **`Installa Scaffale.bat`** (nel pacchetto,
accanto a `LEGGIMI.md`). Il programma (`installa.ps1`) installa con **winget**, lo
strumento di Windows per i programmi, quello che manca e salta quello che c'è:
Python 3.13 (per l'utente, nel PATH), i pacchetti di `requisiti.txt`, Tesseract
(UB-Mannheim), Ollama e i tre modelli — **bge-m3** (ricerca per senso, 1,2 GB),
**qwen3:8b** (riassunti, temi, risposte, 5 GB), **glm-ocr** (la seconda lettura delle
scansioni, 2 GB: senza, i .md non sono verificati). Poi lancia il controllo
(`prepara.py`, che ora dice anche se GLM-OCR c'è) e mette l'icona sul desktop. Le
condizioni d'uso di winget e il permesso di Windows li dà chi installa: il
programma non li accetta da solo. Rilanciato, rifà solo quello che manca. I passi
a mano sono in `LEGGIMI.md`.

---

## Come si usa

**Si parte aprendo l'app**, anche con l'archivio vuoto:

```
python scaffale.py servi
```

La prima schermata chiede **qual è la cartella con i tuoi file**. Scrivi il
percorso, dai un nome se vuoi, premi *Indicizza*: Scaffale entra in tutte le
sottocartelle e comincia, mostrando una barra di avanzamento e il diario di
quello che sta facendo. Quando finisce, la pagina passa da sola alla ricerca.

Altre cartelle si aggiungono quando vuoi, dalla pagina **cartelle**: si sommano
nello stesso archivio, non lo sostituiscono. Lì vedi anche quanti documenti ha
dato ciascuna e quante scansioni restano da riconoscere.

Se preferisci il terminale, lo stesso lavoro si fa così:

```
python scaffale.py indicizza "C:\...\progetto_iv_crociata" --nome IVcrociata
python scaffale.py indicizza "C:\...\Doktorat\RicercaOld"  --nome RicercaOld
```

Cosa fa, in ordine: legge il testo dei documenti che ce l'hanno; mette da parte
le scansioni mute; riconosce le cartelle di immagini numerate e le ricompone in
un unico documento; passa all'OCR tutto il resto, in nove lingue — italiano,
latino, inglese, croato, sloveno, tedesco, francese, greco antico e moderno.

`--senza-ocr` salta il riconoscimento, che è la parte lenta: comodo per una
prima passata veloce. `--daccapo` rifà tutto ignorando quanto già fatto.

**Dall'app, prima di cominciare Scaffale fa il conto**: quanti documenti ci
sono e di che tipo, che cosa è cambiato dall'ultima volta, quante pagine
scansionate ci sono da riconoscere, e quanto ci vorrà. Poi chiede: *solo i
testi*, *tutto, anche le scansioni*, oppure *annulla*. Le scansioni fra i PDF
nuovi si stimano aprendone un campione di 40; il conto lo dice. I tempi vengono
dalle misure di questo computer, tenute in `dati\velocita.json` e aggiornate a
ogni lavoro: 1,34 secondi per leggere un PDF, 0,024 per un file di altro tipo,
2,4 per riconoscere una pagina in nove lingue.

**Ferma** interrompe un lavoro al primo punto sicuro — tra un file e l'altro, tra
una pagina e l'altra, tra un lotto di vettori e l'altro — e lascia intatto quello
che è fatto. Una scansione lasciata a metà non viene salvata a metà: resta in
attesa, intera.

**Chiudere Scaffale**: il pulsante *Chiudi Scaffale*, in alto a destra, spegne il
programma e chiude la finestra nera. Chiudendo solo il browser, Scaffale si
spegne da solo pochi secondi dopo — ma non mentre lavora: finisce prima.
Chiudere la scheda non chiede conferma, di proposito: il browser non distingue
la chiusura dalle frecce avanti e indietro, e la domanda usciva anche con
quelle. Dal terminale (`python scaffale.py servi --senza-browser`) non si spegne
da solo. Ogni pagina aperta manda un segno di vita ogni 20 secondi; chiusa la
scheda, lo dice al programma, che si spegne pochi secondi dopo. Una scheda che
invece tace soltanto non è chiusa: Edge e Chrome addormentano le schede lasciate
dietro le altre. Per questo una scheda muta si dà per chiusa solo dopo tre ore
(`web.SILENZIO_SCHEDA`), e appena la si riguarda si fa sentire subito.

**I lavori lunghi, di notte.** Scaffale tiene sveglio il computer finché lavora,
ma un portatile con lo schermo chiuso, o a batteria, Windows lo addormenta lo
stesso: va lasciato attaccato alla corrente e aperto (o, nelle impostazioni di
alimentazione, «coperchio chiuso: non fare nulla» quando è in carica). Se si
addormenta non si perde niente: la trascrizione salva ogni pagina letta e riparte
da lì (vedi più avanti).

**La scheda della cartella** (dall'elenco delle cartelle) ha i numeri — tipi,
come è stato letto ogni file, `.md`, copie, vettori — e i raggruppamenti. Il
tuo archivio è indicizzato *per parole*, non per argomento; i raggruppamenti li
fa **Analizza la cartella**, da pochi secondi a un minuto — da sola la prima
volta, e dopo ogni aggiornamento che ha cambiato qualcosa. Sono **un elenco solo,
«temi della cartella»**, e ogni voce porta l'etichetta della sua provenienza:
*tuo* (un gruppo fatto a mano, o un tema con le tue parole: *+ nuovo tema*, un
nome e le parole, anche sigle in maiuscolo come AI, che valgono solo in
maiuscolo), *dal tesauro* (un tema dei tesauri in uso nella cartella: le sue
parole in almeno 3 brani, e accanto al file quali e quante volte, *«venezia» in
35, «doge» in 11*; *cambia le parole* apre il tema nella pagina *tesauri*),
*proposto dal modello* (`temi_proposti.py`: il modello di Ollama legge il
profilo della cartella — titolo e parole caratteristiche di ogni file,
campionato nelle cartelle grandi — e propone temi; ogni parola è controllata
sull'indice, gli errori di lettura come «cofa» e «effere» e i pezzi come «conf»
o «regoleper» si scartano da soli, le proposte quasi uguali si uniscono; si
apre la proposta, si tolgono o si aggiungono parole, e *tieni* la mette nel
tesauro «Temi di …» della cartella) e *scoperto* (documenti con una parola
caratteristica in comune, i più grandi e poi i tipici di ogni sottocartella,
con *+ tieni* per farne un gruppo tuo). Quando due voci hanno quasi gli stessi
file — il 60%, o l'80% se una sta in più di metà della cartella — se ne vede
una sola, quella decisa da te prima di quella proposta, e l'altra sta sotto,
«con quasi gli stessi file». I pulsanti sopra l'elenco lo filtrano per
provenienza. Accanto, a parte, *le tue sottocartelle*: l'ordine che hai dato tu
sul disco, che non è un tema. I file si spuntano e si mettono o spostano da un
gruppo all'altro; i gruppi sono etichette dentro Scaffale, i file sul disco non
si muovono. La logica sta in `biblioteca.py`.

**La scheda del documento**: come è stato indicizzato, dove sono le sue copie,
parole caratteristiche, inizio del testo, gruppi, e il riassunto su richiesta,
scritto da `qwen3:8b` sul computer in circa due minuti (il modello piccolo
`qwen3.5:0.8b` è più veloce ma nella prova ha scritto «Roma» per «Paesi
romeni»; si cambia con la voce `modello_riassunti` in `scaffale.ini`).

**Aggiornare una cartella** dopo averci aggiunto, cambiato o cancellato file:
dalla pagina iniziale, pulsante **Aggiorna** accanto alla cartella, oppure

```
python scaffale.py aggiorna Nicopeia
python scaffale.py aggiorna              tutte le cartelle
```

Un file conta come cambiato se ha un'altra dimensione o un'altra data. I file
cancellati escono dall'indice con i loro brani e i loro vettori; ma solo se la
cartella si trova, e solo se il file sul disco davvero non c'è più. Una
sottocartella che non si è potuta aprire non viene scambiata per vuota.

### Che cosa legge

Oltre a `.pdf`, `.docx`, `.doc`, `.md`, `.txt`, `.htm`, `.html` ed `.epub`:

| formato | come diventa testo | serve |
|---|---|---|
| `.rtf` | il testo, senza i comandi di formattazione | `striprtf` |
| `.csv` `.tsv` | intestazioni di colonna, poi le righe | — |
| `.xls` | un foglio per pagina, riga per riga | `xlrd` |
| `.xlsx` `.xlsm` | un foglio per pagina, riga per riga | `openpyxl` |
| `.odt` `.ods` `.odp` | il contenuto del documento | — |
| `.pptx` | una diapositiva per pagina, note comprese | — |
| `.mdb` `.accdb` | una tabella per pagina, colonne e righe | `pyodbc` o `access-parser` |

Le tabelle diventano testo con le intestazioni in testa, così cercare
«Piran 1387» trova la riga giusta, e il foglio o la tabella fanno da numero di
pagina — come per i PDF, il rimando resta verificabile sull'originale.

I database di Access del 1997 il driver di Microsoft si rifiuta di aprirli
(«creato con una versione precedente»). Sono i più vecchi, quindi spesso i più
interessanti: Scaffale li legge da sé, senza driver, con `access-parser`. Nel
tuo archivio sono 90 su 387.

Quando una libreria manca, quei file restano nell'indice ma senza contenuto
cercabile, e il metodo lo dichiara — «mdb: manca pyodbc» — invece di far finta
che siano vuoti.

**2. Calcolare i vettori**, se si vuole la ricerca semantica. Serve Ollama
acceso e il modello `bge-m3`, che è già installato.

Il modo più semplice è dall'app: nella pagina iniziale c'è un riquadro con un
pulsante per ogni cartella e il tempo che ci vuole. Si preme e si lascia
lavorare, con la finestra nera aperta. Dal terminale:

```
python scaffale.py vettori --cartella Nicopeia
python scaffale.py vettori                        tutto l'archivio
```

**Su questo computer va a 0,85 frammenti al secondo**: non ha una scheda
grafica, e Ollama lavora sul processore. Vuol dire circa 8 ore per la cartella
*Nicopeia* (23.965 frammenti) e circa due giorni e mezzo per tutto l'archivio.
Le copie dei doppioni non si calcolano due volte, e si può interrompere e
riprendere: ricomincia da dove era. La velocità misurata si aggiorna da sé in
`dati\velocita_vettori.txt`, e le stime dell'app la usano.

**3. Aprire l'app.**

```
python scaffale.py servi
```

Si apre su `http://127.0.0.1:8000`. In cima il totale dell'archivio, sotto la
casella di ricerca; ogni risultato porta il nome del documento, la radice, la
pagina, il metodo con cui è stato letto, e se ne esistono copie altrove. Il
titolo è un link che apre il file **alla pagina del brano**; accanto c'è il
link alla cartella che lo contiene.

---

## I tre modi di cercare

**esatta** — quello che scrivi, niente di più. Con gli operatori di FTS5.

**tesauro** — la ricerca viene allargata agli equivalenti reali del tuo campo.
Scrivi «nicopeia» e cerca anche *Nikopeja*, *Nikopoios*, *Νικοποιός*, *Gospa od
Pobjede*, *imagine di Nostra Donna*. Scrivi «stratioti» e cerca anche
*stradioti*, *oltramarini*, *prekomorske postrojbe*, *izbjeglice*. L'app ti dice
sempre quali nuclei ha riconosciuto, così sai perché un risultato è uscito.

Il tesauro è un file di testo, `tesauro.py`, con una quindicina di nuclei
concettuali — Nicopeia, icona, san Luca, tipi mariani, Bisanzio, greci, rito
orientale, profughi, Levante veneziano, Adriatico orientale, Venezia,
confraternite, reliquie e culto, pittori, Quarta crociata, fonti veneziane,
materialità. **Si corregge a mano**: se ti accorgi che manca una forma, la
aggiungi e la ricerca migliora subito.

**semantica** — confronta il senso, non le parole, con gli embedding di bge-m3.
Trova accostamenti che il tesauro non prevede. In cambio è una scatola nera:
non sa dirti perché.

**tutte e tre** insieme: i risultati si fondono e quelli trovati da più vie
salgono in cima.

---

## Le domande ai documenti

Dalla voce **domande** in alto, o da *Fai una domanda ai documenti di questa
cartella* nella scheda, o da un gruppo aperto. Si scrive una domanda, come a
NotebookLM, e Scaffale:

1. cerca i brani che rispondono, **dove ti trovi** (tutte le cartelle, una, o un
   gruppo), in due modi insieme: per parole — con le varianti dei tesauri, il
   singolare e il plurale, la radice delle parole lunghe — e per senso, con i
   vettori, dove ci sono. Le due classifiche si fondono per posto, non per
   punteggio; passano avanti i brani con più parole diverse della domanda;
2. tiene i sei migliori, non più di due da uno stesso testo — le versioni di un
   articolo, il PDF e il suo `.md` contano come uno;
3. li dà al modello che gira sul computer (`qwen3:8b`), con l'ordine di
   rispondere solo con quelli, di dire da quale brano viene ogni cosa — [1],
   [2] — di riportare il latino com'è, e di dire quando i brani non bastano;
4. controlla la risposta: i numeri di brani che non esistono si tolgono, e se
   le parole di una frase stanno in un brano diverso da quello citato, il
   numero si corregge e lo si dice sotto la risposta.

Ogni numero porta al brano, e ogni brano alla sua pagina con le parole in
giallo. **Il modello può sbagliare, i brani no**: si controlla sempre sui brani
prima di citare. Su questo computer, senza scheda grafica, una risposta ci mette
circa 4 minuti; il pulsante *ferma* la interrompe. Senza Ollama si vedono solo i
brani. Le domande restano in elenco, con le loro risposte (`domande.py`, tabella
`domande`). L'idea di fondere le due ricerche e di dare comunque i brani senza il
modello viene da OpenNotebookLM (github.com/woodysc8/OpenNotebookLM); quel
programma, e gli altri simili provati prima di scrivere questa parte, non vanno
dentro le cartelle e non portano alla pagina.

**La guardia sui numeri** (`domande.guardia_numeri`). Ogni numero e ogni data
della risposta — cifre arabe e romani — deve stare, uguale, nei brani che la
frase cita (o in uno qualsiasi, se la frase non ne cita). Quelli che non ci sono
si segnano **⚠** in rosso nel testo, e sotto la risposta si dice dove stanno
davvero («sta nel brano [3], non in quello citato») o che non stanno in nessun
brano. È un controllo meccanico: il modello non lo aggira. Non vede i numeri
scritti in lettere («tre anni»).

**La ricerca approfondita** (`ricercatore.py`, pulsante accanto a *Chiedi ai
documenti*). Per le domande difficili, sull'esempio di PaperQA2
(github.com/future-house/paper-qa) ma con i controlli di Scaffale: il modello fa
un piano (2–4 domande più precise e le ricerche, anche in latino o nell'italiano
antico), Scaffale fa tutte le ricerche e tiene al massimo 14 brani, due per
testo; il modello li legge uno per uno, dice se servono e che cosa dicono, e ne
copia la frase chiave — Scaffale controlla che la frase stia nel brano parola per
parola (se no la scarta) e che i numeri del riassunto stiano nel brano; se manca
qualcosa, un secondo giro di ricerche; poi il rapporto, in tre parti («In
breve», «Che cosa dicono le fonti», «Che cosa non si trova o resta incerto»),
che passa per gli stessi controlli di una domanda. *Come ha lavorato*, sotto il
rapporto, mostra il piano, le ricerche e ogni brano letto con i suoi controlli.
Ci vogliono 20–30 minuti; *ferma* lo interrompe e il diario resta. Sta nella
tabella `domande`, con `tipo` = ricercatore e il `diario` in JSON.

**Il computer resta sveglio** mentre un lavoro va avanti (`archivio._resta_sveglio`):
ogni volta che un lavoro dice a che punto è, si azzera il conto alla rovescia
della sospensione di Windows, come fanno i programmi video. Finiti i lavori, il
computer torna a comportarsi come sempre; nessuna impostazione cambia.

## Doppioni ed esportazione

La pagina **doppioni** elenca i documenti con lo stesso testo, e poi confronta
i file: **identico** (stessa dimensione, stesso contenuto: una copia vera),
**diverso** (stesso testo, file diverso: di solito il PDF e la sua versione
compressa, come i *Diarii* di Sanuto da 77 e da 33 MB), **più corto** (comincia
con lo stesso testo ma ha meno pagine: un capitolo staccato dal libro). Lo
spazio sprecato conta solo le copie identiche. Per intervenire:

```
python scaffale.py deduplica            mostra che cosa farebbe
python scaffale.py deduplica --esegui   lo fa
```

Tiene la copia con il nome più parlante e il formato originale, e penalizza le
cartelle di servizio — `pdf_raw`, `workspace`, `_compressed`, `(1)`, `- Copia`.
Le altre **non le cancella**: le sposta in `Scaffale\quarantena`, conservando
l'albero delle cartelle. Controlli, e poi cancelli tu. Sposta solo le copie
identiche a quella che tiene: un file diverso con lo stesso testo resta al suo
posto.

L'**esportazione** prende i risultati di una ricerca e ne fa una cartella
pronta: i PDF copiati, `elenco.md` con i brani, `elenco.csv` e
`riferimenti.bib` per Zotero. Dall'app: `/esporta?q=skopiotissa`. Dal terminale:

```
python scaffale.py esporta "skopiotissa" --nome icone_zante
```

La cartella che ne esce si carica in NotebookLM così com'è.

## Dai PDF ai file .md

Sotto i risultati di una ricerca c'è **«Crea i .md dei PDF trovati»**. Per ogni
PDF scrive un `.md` accanto all'originale: testata con provenienza, metodo e
numero di pagine, corpo ricucito, e i cambi di pagina segnati come
`<!-- pagina 12 -->`.

In testa a ogni file c'è un'avvertenza, e non è una formalità: **una
trascrizione automatica sbaglia sui numeri**. Date, cifre, numeri romani,
elenchi. Il commento di pagina serve a riaprire l'originale nel punto giusto.

**I numeri letti due volte** (`verifica_numeri.py`). Un PDF nato digitale dà il
testo dell'editore, esatto, e si trascrive com'è. Una scansione — o una
scansione con l'OCR di qualcun altro sopra, come fa Adobe Acrobat — si legge
riga per riga (Tesseract, o il testo che il PDF ha già), e le righe con numeri,
con numeri attesi («sec.», «vol.», «cap.», «filza»…), con parole che sembrano
numeri letti male («IIO», «1x») o con inchiostro accanto che l'OCR non ha letto
(i numeri di pagina di un indice) si rileggono con GLM-OCR, il modello di
Ollama che guarda l'immagine, fermato al primo a capo. Un numero vale solo se le
due letture concordano; se no la riga del `.md` porta **[⚠ verificare 12.3: …]**
con le due letture, e il posto esatto va nel file `.verifica.json` accanto al
`.md`. Nella scheda della cartella il PDF dice «N righe con numeri da
verificare»: il link apre la pagina *Numeri da verificare*, con il pezzo
dell'originale, le due letture e un campo per scrivere la riga giusta; *salva*
la mette nel `.md` al posto della riga e della nota. Le doppie pagine aperte si
leggono in due metà.

**Le colonne dentro la pagina** (`verifica_numeri._colonne`). Un indice a due
colonne, una rivista, un quotidiano: se si legge la pagina per righe intere, la
voce di sinistra e quella di destra diventano una riga sola («Natura piena di
con- a' Cirenei 85»), e le due letture sembrano in disaccordo anche quando hanno
ragione tutte e due. Prima di leggere, Scaffale cerca le strisce bianche verticali
che separano le colonne (nel corpo della pagina, senza testatina e piede: quasi
nessuna riga con inchiostro, colonne larghe almeno il 12% della pagina), e legge
ogni colonna per conto suo, una dopo l'altra. Una pagina a una colonna sola resta
intera: le sue righe attraversano il mezzo. **Le tabelle non si dividono**: se una
delle «colonne» trovate è fatta per più di metà di cifre è la colonna di una
tabella (titolo, capitolo, pagina; voce e importo), e la pagina si legge intera,
perché i numeri devono restare sulla riga della loro voce.

**La seconda lettura legge la riga giusta.** Il ritaglio dato a GLM-OCR va da un
margine all'altro della colonna (così entrano i numeri di pagina di un indice) e,
dove due righe si sovrappongono per più di un quarto (righe fitte, iniziali
corsive), si ferma a metà fra le due: GLM si ferma al primo a capo, e se il
ritaglio prende un pezzo della riga sopra legge quella. Se non legge niente si
riprova col riquadro di Tesseract. Una seconda lettura che somiglia chiaramente di
più alla riga accanto che a quella da rileggere si scarta, e la riga, se ha
numeri, resta *[⚠ verificare …: seconda lettura non riuscita]*: meglio una riga
da guardare che una riga sbagliata data per buona.

**Se il lavoro si interrompe** (il computer si addormenta, si spegne, si preme
ferma), le pagine già lette non si perdono: ognuna si salva appena letta in
`dati\letture_parziali\`, e rilanciando la trascrizione dello stesso PDF riparte
dalla pagina dove si era fermata. Il .md si scrive tutto insieme alla fine; il
salvataggio delle pagine si toglie da solo quando il .md è pronto.

**Il PDF e il suo .md sono un documento solo** (`coppie.py`). Il .md si cerca
accanto al PDF, in una sottocartella `markdown` (o `md`, `trascrizioni`), o con lo
stesso nome altrove nella cartella. Nella scheda la coppia è una riga sola, con
*il .md* che lo apre e un giudizio: **buono**, **da controllare** o **da
rifare**, e i motivi scritti — pagine mancanti rispetto al PDF, pagine senza
testo, parole illeggibili, la s lunga letta f («fopra», «quefto»), numeri non
verificati. I numeri valgono come verificati se il .md è stato fatto con la
verifica, o se viene dal testo di un PDF nato digitale; un PDF «con testo» che è
in realtà una scansione con l'OCR di altri non conta. Il giudizio sta nella
tabella `qualita_md` e si rifà quando il .md cambia. Dove serve c'è **rifai il
.md con la verifica dei numeri**: il .md nuovo va nello stesso posto, e quello di
prima diventa `….md.vecchio`, solo quando il nuovo è pronto. Di una coppia si
fa **un riassunto solo** — del PDF se ha il testo dell'editore, se no del .md —
e i conti della scheda contano la coppia una volta.

**Sistema tutta la cartella** (`sistema.py`, POST `/sistema`): un pannello nella
scheda della cartella, con un pulsante solo e le voci da spuntare, ognuna con il
suo tempo — crea i .md che mancano; rifai quelli *da rifare*; (a scelta) rifai
anche quelli con i numeri non verificati; aggiorna l'indice e rifai l'analisi;
scrivi i riassunti che mancano. Si fanno in quest'ordine, perché i riassunti si
scrivono sul testo nuovo. Un solo *ferma* interrompe il passo in corso e salta
gli altri; quello che è fatto resta. Un .md già rifatto da Scaffale (ha il suo
`.verifica.json`) non si rifà una seconda volta: darebbe lo stesso testo.

**La s lunga** (`s_lunga.py`). Nelle stampe del Cinque-Seicento la ſ, letta f dal
dizionario moderno, dà «fopra», «quefto», «effere». Un .md con più di 1,5 di
queste parole ogni mille (le conta `coppie.esamina`, sull'elenco `S_LUNGA`) si
rifà come **stampa antica**: Tesseract col dizionario `ita_old` (da
`tessdata_best`, addestrato sulle stampe antiche: riconosce la ſ, che poi diventa
s), sempre con l'OCR anche se il PDF ha già il testo di altri, e dopo una
correzione per parole: una parola con la f che non esiste in nessuna delle lingue
dell'archivio, e che con una o più f fatte s è una parola italiana (una sola
possibile), si corregge («poffa» → «possa»); «ft» e «fc» diventano «st» e «sc»
nelle parole minuscole finite in vocale («noftre»). I dizionari sono quelli di
Tesseract, estratti con `dawg2wordlist` in `tessdata/parole_ita.txt.gz`,
`parole_lat.txt.gz`, `parole_altre.txt.gz` (inglese, tedesco, francese, croato,
sloveno: proteggono «fifteenth», «Jahreshefte»). La correzione vale solo per le
stampe antiche: sui testi moderni sbaglierebbe nomi e sigle. Nell'archivio di
prova ne ha trovate 29 su 1159 .md, tutte stampe del '500-'600; sulle pagine del
Manifesto la s lunga è passata da 6,1 a 0 parole ogni mille. Restano gli errori
d'altro tipo (parole attaccate, «fopraildetto»).

Una stampa antica si riconosce anche **prima di leggerla**, dal testo che il PDF
ha già dentro (l'OCR di Google Books o di Adobe, `s_lunga.pdf_antico`): così non
si perdono ore in una prima lettura col dizionario sbagliato. Le lingue, per le
stampe antiche, sono **solo italiano antico e latino** (`ita_old+lat`): con tutte
e nove le lingue Tesseract metteva lettere greche nel testo italiano («{στ»,
«ὁ»). Il correttore conosce anche le grafie dell'epoca: la u per la v fra due
vocali («hauesse», «sapeua»), le forme di avere con la h, il «si» attaccato al
verbo («scriuendosi»). I dizionari di Tesseract, fatti da testi letti con l'OCR,
contengono loro stessi gli errori della s lunga («diffe», «fi», «cafa»): queste
forme stanno nell'elenco `S_LUNGA` e non contano come parole vere.

**Tre letture che votano** (`tre_letture.py`), per le stampe antiche. Nessun
motore basta da solo: Tesseract mette gli spazi giusti ma scambia u e n
(«tramutanano»); GLM-OCR legge meglio le lettere ma ogni tanto ne aggiunge
(«a'animici»); il testo che il PDF ha già (Google Books) ha quasi sempre le
lettere giuste e distingue la ſ dalla f, ma attacca le parole («Romatantopieua»).
Per le stampe antiche GLM rilegge **ogni** riga, non solo quelle con numeri, e per
ogni parola: dove Tesseract e GLM concordano resta; dove no decide il testo del
PDF, confrontato senza spazi; una f che nel testo del PDF è ſ diventa s (le parole
corte, come «fi», si cercano con le vicine, se no «fi» si ritroverebbe dentro
«fine»). Sulla p. 141 della *Relatione* del Botero (1605), confrontata con una
trascrizione a occhio: Tesseract 73 parole giuste su 100, GLM 88, le tre letture
insieme 90; il testo di Google, con le parole attaccate, 29. Costa circa 2–3
minuti a pagina: la *Relatione* intera, 281 pagine, 14 ore. Su 1972 righe con
numeri, 453 le ha decise il terzo giudice e 154 restano da guardare, quasi tutte
nella Tavola (iniziali corsive grandi, cifre all'antica col 5 che sembra una ſ).

**Il terzo giudice.** Dove Tesseract e GLM-OCR non concordano, se è installato
PaddleOCR (PP-OCRv5 per le lingue latine, attraverso `rapidocr` e `onnxruntime`,
circa 280 MB: `prepara.py` lo propone) rilegge lo stesso ritaglio: se dà ragione
a una delle due letture, la riga va nel `.md` così, senza segno, e nel
`.verifica.json` resta «deciso a maggioranza» con le tre letture (la pagina
*Numeri da verificare* le mostra con *mostra anche quelle già verificate*). Solo
dove nemmeno lui concorda resta *[⚠ verificare …]*. Nelle prove, su 36 righe
discordi ne ha decise 29, tutte giuste. PaddleOCR da solo non sostituisce
Tesseract: sulle cifre all'antica sbaglia di più. Alla prima volta scarica i suoi
modelli, pochi MB.

Perché così, e non con un solo motore: misurato su quattro pagine vere, 226
numeri (note d'archivio, cifre all'antica, un indice del Cinquecento, romani in
maiuscoletto), Tesseract ne prende circa 200; GLM-OCR e Unlimited-OCR di Baidu
(provato con franken_ocr, sul solo processore) quasi tutti, ma inventano pezzi
di citazione («Bulletin of Medieval Languages, 1985») e sbagliano i romani
(«IIIII» o «III» per IIII) — in punti diversi da Tesseract. Con le due letture a
confronto nessun numero confermato era sbagliato; restano da guardare 20–35
righe ogni cento con numeri. Costa circa 4 minuti per una pagina fitta di note
(la rilettura di una riga: 3–9 secondi); Unlimited-OCR, 11 minuti a pagina e 22
secondi a riga, è troppo lento per farne la seconda lettura.

**I .md già esistenti non vengono toccati.** Vengono collazionati con il testo
estratto ora, e le differenze finiscono in un rapporto: rapporto fra le
lunghezze, somiglianza, e soprattutto **le cifre presenti in uno e non
nell'altro**. È il controllo che serve quando una trascrizione vecchia ha già
prodotto una nota e non sai se fidartene.

Dal terminale:

```
python scaffale.py trascrivi "skopiotissa"
python scaffale.py trascrivi "candia" --sovrascrivi
```

## Gli altri comandi

```
python scaffale.py stato     quanti documenti, quante parole, quanti vettori
python scaffale.py copie     i doppioni, con lo spazio che sprecano
python scaffale.py mute      le scansioni ancora senza testo
python scaffale.py cerca "candia" --semantica      la stessa ricerca da terminale
```

`copie` è il comando che conviene lanciare per primo su un archivio vecchio:
nel tuo, su 7.064 documenti, 1.039 gruppi avevano lo stesso testo. Il comando
dice per ogni file se è una copia identica o una versione diversa, e lo spazio
che occupano le sole copie identiche. Finché ci sono, ogni ricerca restituisce
più volte la stessa cosa (nel conto dei risultati le copie valgono una volta).

---

## Com'è fatto

`estrattori.py` legge i formati e riconosce le cartelle-libro. `tesauro.py` è il
dizionario di dominio. `archivio.py` tiene la base SQLite: una tavola per i
documenti, una per i frammenti di circa 2.400 caratteri con il numero di pagina,
un indice FTS5 per la ricerca testuale. `semantica.py` parla con Ollama e tiene
i vettori. `domande.py` fa le domande ai documenti e `ricercatore.py` la ricerca
approfondita. `trascrizioni.py` scrive i .md; `verifica_numeri.py` legge le
scansioni riga per riga, colonna per colonna, e rilegge i numeri; `tre_letture.py`
fa votare le tre letture delle stampe antiche; `s_lunga.py` corregge la s lunga;
`coppie.py` tiene insieme un PDF e il suo .md e li giudica; `sistema.py` è
«Sistema tutta la cartella»; `biblioteca.py` fa analisi e riassunti;
`temi_proposti.py` i temi proposti dal modello. `web.py` è l'app. `scaffale.py` è
la riga di comando. Le prove stanno in `prove\` (`tutte_le_prove.sh`, undici
sezioni, ognuna in una copia nella cartella temporanea, mai sulla porta 8000).

I frammenti conservano il numero di pagina perché **il brano che leggi nei
risultati deve essere verificabile**: il link ti porta alla pagina esatta del
PDF, e da lì controlli sull'originale. Dopo l'episodio della *Supplica 1806*,
dove l'originale porta `XVIIII` e la trascrizione diceva `XVIII`, questa è la
parte che conta più di tutte.

## Quanto ci mette

Lettura dei documenti con testo: qualche minuto per migliaia di file. OCR: circa
quindici secondi a pagina, quindi va lanciato e lasciato lavorare. Vettori:
da uno a nove frammenti al secondo secondo la lunghezza — per un archivio come
il tuo, una notte. I .md verificati di una scansione: da 1 a 5 minuti a pagina
(una stampa antica con le tre letture, 2–3 minuti; un libro di 300 pagine, una
notte e mezza). Una risposta alle domande: circa 4 minuti. Tutti questi tempi
crescono se il portatile va a batteria o è caldo: l'OCR di 37 pagine in nove
lingue è andato da 5 a 15 minuti sullo stesso computer.
