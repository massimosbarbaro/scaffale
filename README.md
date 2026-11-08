# Scaffale: local indexing, OCR and semantic search of a personal research archive with a local language model

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24057200.svg)](https://doi.org/10.5281/zenodo.24057200)

*Indicizzazione, OCR e ricerca semantica di un archivio di ricerca personale, tutto in locale, con un modello linguistico installato sul computer*

2026 · version 1.1  
Author: **Massimo Sbarbaro** ([ORCID 0009-0006-8965-9013](https://orcid.org/0009-0006-8965-9013))

## In short

Scaffale is a first attempt to bring **large language models into a historian's everyday work without
leaving the computer**. It runs on an ordinary Windows laptop with no dedicated graphics card, works
offline, and sends no document to any online service. On that machine it does five things:

1. **Indexes** a whole research archive (about 15,000 documents in the author's case), whatever the format.
2. **Searches it by meaning** as well as by exact words, and answers questions only from the archive's own
   passages, each with its page.
3. **Turns PDFs and scans into checked Markdown transcriptions.** Every number and date is read by
   independent readers, and every doubt is flagged instead of being silently "corrected".
4. **Writes summaries** of documents and folders and proposes themes, with a model running on the same
   computer.
5. **Keeps the archive in order.** It shows duplicates and copies, and lists what is still missing: scans
   not yet read, transcriptions that lack pages or need redoing, summaries not yet written.

The language models (`bge-m3`, `qwen3:8b`, `glm-ocr`) are installed locally through
[Ollama](https://ollama.com). The internet is needed only to install them.

The same program exists in two configurations (see [*Two versions*](#two-versions-a-light-judge-and-a-heavy-one)).
On a Windows laptop it uses light models. On a more powerful Linux workstation it uses a much heavier
and more precise reader, **Qwen3.5-397B** (397 billion parameters). That model, too, runs on the
machine itself.

## Why

Commercial AI tools for documents (NotebookLM, ChatGPT and the like) need the documents to be uploaded.
They cannot hold an archive of thousands of files, and they give answers that cannot always be traced to
a page. For an archive of sources that are unpublished, under copyright or belong to an institution,
uploading is often not an option. For a historian, an answer that cannot be checked on the original is
of no use.

Scaffale tests the opposite route. Small open models run on the researcher's own computer, over the
whole archive. Every statement leads back to the page of the original PDF where it can be checked.
In the author's doctoral work it is presented as **a first example of a language model installed and
running entirely on an ordinary Windows PC, applied to the semantic analysis of archives, including
historical ones** (see [*Doctoral research*](#doctoral-research)).

## How it works: the pipeline

```
 research folder          1. INDEX             2. READ               3. TRANSCRIBE
 (PDF, Word, scans,  ──►  every format,   ──►  OCR of mute scans ──►  PDF → checked Markdown,
  images, databases)      passages with        in nine languages      three readings + arbiter
                          page numbers
                               │
                               ▼
  6. CITE              ◄── 5. ORGANISE         ◄── 4. SEARCH AND ASK
  quotation checked        themes, summaries,      exact, thesaurus, semantic;
  on the original page     duplicates, what        questions answered from the
                           is missing              archive with numbered sources
```

### 1. Index a whole archive

Scaffale reads whole folder trees: PDF, DOCX/DOC, RTF, ODT, EPUB, HTML, TXT/MD, CSV, XLS/XLSX, ODS, PPTX
and old `.mdb`/`.accdb` databases. A folder of numbered images is a book photographed page by page; it is
recognised and put back together as one document. The text is split into passages of about 2,400
characters, and each passage keeps the number of its page.

Before starting, Scaffale counts the work: how many files, of what kind, what has changed since the last
time, how many scanned pages are still to be read, and how long it will take on this computer. Updating
a folder later reads only what is new or changed and removes what was deleted.

### 2. Read the scans

Scans without text are read by Tesseract in nine languages: Italian, Latin, English, Croatian, Slovene,
German, French, and ancient and modern Greek. Early-modern Italian printing has its own reading model,
which handles the long *s*.

### 3. From PDF to checked Markdown

This is the part on which the rest depends. A transcription can be quoted only if its numbers and dates
are right: a date read 1296 instead of 1298 enters an article and nobody finds it again. Every PDF
becomes a `.md` file next to the original. The file has a header (source, method, number of pages), the
page breaks marked, and a separate report of what was checked. The checks work as follows.

- **Three readings and an arbiter.** Every line with numbers or dates, Arabic or Roman, is read by a
  first reader and again by a second reader. Where the two readings disagree, a third reader acts as
  arbiter. On the laptop the readers are Tesseract, `glm-ocr` and PaddleOCR. On the Linux workstation
  Qwen3.5-397B reads the whole page and then each line, and Surya OCR 2.5 is the arbiter (see *Two
  versions*).
- **Doubts are flagged, not hidden.** A line that no reading confirms is kept as read and marked
  `[⚠ verificare]`, with the page, for a check on the original.
- **Columns.** Pages in two or more columns, such as newspapers and editions with facing texts, are cut
  along the white gutters and read column by column, so that two columns are not merged into one line.
  Tables are left whole.
- **Early-modern printing.** For old prints the three readings (Tesseract, `glm-ocr` and the PDF's own
  text layer) also vote word by word. The long *s* read as *f* (*quefto*, *fopra*) is corrected only when
  Tesseract's own Italian and Latin dictionaries allow exactly one reading. On a test page of a 1605
  print checked against a manual transcription, 90% of the words came out right, against 73% for
  Tesseract alone.
- **A grade for every transcription.** Each pair of a PDF and its `.md` is treated as one document and
  graded *good*, *to check* or *to redo*, with written reasons: pages missing compared with the PDF,
  empty pages, illegible words, the long *s* misread, numbers not verified.
- **Nothing is lost.** An existing `.md` is never overwritten blindly: the old one becomes `.md.vecchio`
  only when the new one is complete. A long transcription saves every page as soon as it is read and
  resumes from there after an interruption.

**«Sistema tutta la cartella»** (*fix the whole folder*) runs everything in the right order with one
button. It creates the missing `.md` files, redoes those graded *to redo*, updates the index, and
writes the summaries that are missing.

### 4. Search and ask

- **Three ways of searching**, which can be combined:
  - exact full-text search (SQLite FTS5);
  - search expanded through an editable thesaurus of equivalent forms in several languages (*Nicopeia*,
    *Nikopoios*, *Victory-maker*…);
  - semantic search with `bge-m3` embeddings, which finds passages on the same subject even when they
    share no word with the question.
- **Every result opens the original PDF at the right page.**
- **Questions to the documents.** A question in natural language is answered by `qwen3:8b` using only
  the passages found in the archive, each statement with its numbered source. A guard checks every
  number and date of the answer against the passages. A *deep research* mode reads more passages, in
  several rounds, before answering.
- **Export.** The results of a search become a folder with the PDFs, a list of the passages, a CSV
  file and a `.bib` file for Zotero. The folder can be loaded as it is into NotebookLM.

### 5. Organise: themes, summaries, duplicates, what is missing

- **Summaries** of single documents, written on the computer by `qwen3:8b` in about two minutes each,
  and of whole folders. A PDF and its `.md` get one summary, not two.
- **Themes.** For each folder Scaffale proposes groups: those made by the user, those from the
  thesauri, those proposed by the language model, and those discovered from shared characteristic
  words. Every word proposed by the model is checked against the index. The user keeps or discards
  each theme; the files on disk are never moved.
- **Duplicates and copies.** Scaffale recognises three cases and treats each group as one document:
  identical files; the same text in a different file (a PDF and its compressed copy); and an excerpt of
  a longer text (a chapter cut out of a book). It can move the identical copies to a quarantine folder
  for the user to check. It never deletes them.
- **What is missing.** The folder page shows how many scans are still to be read, which PDFs have no
  `.md`, which `.md` files are incomplete or need redoing and why, and which documents have no summary
  yet.

### 6. Cite from the original

When a passage is about to be quoted, Scaffale reopens the original page, reads it again and shows the
two readings side by side, word by word, so that a reading error inside a quotation does not go
unseen.

## On an ordinary computer

Scaffale was developed and used on a Windows 11 laptop: Intel Core Ultra 7 155U, 32 GB of RAM,
integrated Intel graphics, no dedicated graphics card. The models are chosen to fit such a machine.
Measured times on that laptop:

| Task | Time |
|---|---|
| Reading documents that already have text | a few minutes for thousands of files |
| OCR of a scanned page | about 15 seconds |
| Embeddings for semantic search | one night for an archive of about 15,000 documents |
| Checked `.md` of a scanned page | 1 to 5 minutes (a 300-page book: about a night and a half) |
| Summary of one document | about 2 minutes |
| Answer to a question | about 4 minutes |

The long jobs are meant to run at night. They can be stopped at a safe point and resumed, and the
computer is kept awake while they run. Online models (Ollama's `:cloud` models) are refused by
design.

## Two versions: a light judge and a heavy one

Scaffale has been built and used in two configurations. The program and the steps are the same; what
changes is the model that reads the pages, and so the precision of the transcriptions.

| | Windows: ordinary local PC | Linux: research workstation |
|---|---|---|
| Machine | Windows 11 laptop, Intel Core Ultra 7 155U, 32 GB RAM, integrated graphics, no dedicated graphics card | Ubuntu 26.04 LTS, AMD Ryzen Threadripper PRO 7995WX (96 cores), 246 GiB RAM, 2 × NVIDIA RTX PRO 6000 Blackwell Max-Q (96 GB each, 192 GB in all) |
| Line boxes on the page | — | RapidOCR/PaddleOCR |
| First reading | Tesseract | **Qwen3.5-397B-A17B** reads the whole page: a multimodal model, quantised (UD-Q3_K_S), served on the same machine by llama.cpp with CUDA on both cards (about 166 GB of video memory) |
| Second reading | `glm-ocr` (Ollama), on the lines with numbers | Qwen3.5-397B again, line by line, eight line boxes per request |
| Third reading (arbiter) | PaddleOCR (RapidOCR) | **Surya OCR 2.5**, a separate local service on one card |
| Embeddings | `bge-m3` | `bge-m3` |
| Summaries, themes, answers | `qwen3:8b` | `qwen3.5:35b` and `qwen3.5:4b` (Ollama) |
| Python | 3.9 or later | 3.12, in Scaffale's own virtual environment |
| Character | light, slower on scans, more lines left to check by hand | heavy, much more precise, fewer doubts |

**How a scan becomes a `.md` on the workstation.** The page is rendered at 300 dpi; a page in two
columns is split; RapidOCR/PaddleOCR finds the boxes of the lines; Qwen3.5-397B reads the whole page,
then reads it again line by line, eight boxes at a time; Surya 2.5 gives the third reading. The three
readings vote word by word. Where they agree, the word passes; where they do not, the `.md` gets
`[⚠ verificare]` and the line goes into a `.verifica.json` file next to it. For each line that file keeps
the page, the box, the three readings, a note and a status — *to check*, *decided by majority* or
*verified* — and a page of the interface shows those lines with a crop of the real page and a field to
correct them, including the lines that the vote had accepted.

The difference was measured on the author's own sources:

- **A 17th-century printed page** (Botero, p. 141, compared with a manual transcription). Qwen3.5-397B
  read 98.7% of the letters right, against 83.9% for `glm-ocr`.
- **The twelve most difficult pages of an 1821 printed volume.** The lines left for a check by hand
  went from 96 with the laptop configuration to 25 with Qwen3.5-397B as reader. Roman numerals read
  whole and legible rose from 104 to 140.
- **Fifteen lines with numbers, checked by hand.** Qwen3.5-397B read 85% of the numbers right, against
  56% for `glm-ocr`.

The large model is not infallible. On one line it read «MDCCLII» for «MDCCLI», and there an arbiter
read it right. For this reason it also stays one reader among three. In both versions nothing leaves
the machine.

The choice is made in `scaffale.ini`:
- `server_ocr` and `modello_ocr` give the address and name of the large reader;
- `server_terzo` gives an external arbiter.

Left empty, Scaffale uses the light configuration of the laptop.

## Limits

This is a first attempt, built for one researcher's archive and tested on it. The interface and the
guides are in Italian. OCR and checked transcriptions are slow on a laptop. The answers of an 8-billion
parameter model are shorter and less fluent than those of commercial services: they are meant to point
to the passages, which remain the evidence. Every statement must still be checked on the original
page, and Scaffale is designed to make that check quick, not to replace it.

## How to install and use

The program and its guides are in Italian.

- **Windows 10/11:** read [`LEGGIMI.md`](LEGGIMI.md). Download `Scaffale.zip` from the latest
  [release](https://github.com/massimosbarbaro/scaffale/releases), extract it and double-click
  `Installa Scaffale.bat`. It installs Python, the Python packages, Tesseract, Ollama and the three
  models (about 10 GB in all), and puts the icon on the desktop.
- **Linux** (Ubuntu/Debian, Fedora, Arch): read [`LEGGIMI_LINUX.md`](LEGGIMI_LINUX.md) and run
  `./installa.sh`.
- **How it works**, function by function and module by module: [`GUIDA.md`](GUIDA.md).

Once installed, `python scaffale.py servi` opens the web interface in the browser. The interface is
served only to the local machine. The first page asks for the folder to index.

## Technology

- **Language and web interface:** Python 3 (3.9 or later); FastAPI and uvicorn for the local web
  interface.
- **Index and documents:** SQLite with FTS5 for the index; PyMuPDF for PDFs.
- **OCR:** Tesseract.
- **Local models, through Ollama:** `bge-m3` for embeddings; `qwen3:8b` for summaries, themes and
  answers; `glm-ocr` for the second reading.
- **Third reader:** RapidOCR/ONNX Runtime with PaddleOCR models (optional).
- **Linux workstation (optional):** Qwen3.5-397B-A17B through llama.cpp (CUDA) as reader of the pages;
  Surya OCR 2.5 as arbiter through a separate local service; `qwen3.5:35b` and `qwen3.5:4b` through
  Ollama for summaries and themes; Tesseract 5.5 installed without administrator rights with micromamba.

The Python dependencies are listed in [`requisiti.txt`](requisiti.txt).

## Repository contents

| Path | Content |
|---|---|
| `scaffale.py`, `web.py` | Command line and local web interface. |
| `archivio.py`, `estrattori.py`, `formati.py`, `cartelle.py` | Index, file formats, folders. |
| `semantica.py`, `tesauro.py`, `tesauri.py`, `varianti.py` | Semantic search and thesauri. |
| `domande.py`, `ricercatore.py` | Questions to the documents and deep research. |
| `biblioteca.py`, `temi_proposti.py` | Folder analysis, themes, summaries. |
| `trascrizioni.py`, `verifica_numeri.py`, `tre_letture.py`, `s_lunga.py`, `coppie.py`, `sistema.py` | PDF to Markdown, the three readings, the long *s*, grading of transcriptions, «Sistema tutta la cartella». |
| `citazione.py` | Quotation checked on the original page. |
| `installa.ps1`, `*.bat` | Windows installer and launchers. |
| `installa.sh`, `avvia.sh`, `crea_collegamento.sh` | Linux installer and launchers. |
| `prepara.py` | Checks that everything needed is installed. |
| `tessdata/` | Tesseract language data used by the program, and word lists extracted from them (Apache License 2.0, see `tessdata/NOTICE`). |
| `GUIDA.md`, `LEGGIMI.md`, `LEGGIMI_LINUX.md` | Guides (Italian). |

Not included: the author's index and documents, the automated tests (they run on copies of the author's
archive) and the development notes.

## Research context

Scaffale was designed and developed in 2026 for the author's own research archive. The archive holds
about 15,000 documents: archival sources, editions, scans of early printed books, articles and notes.
It covers medieval and early-modern sources and secondary literature in Italian, Latin, Croatian,
Slovene, German, French, English and Greek.

Indexing the whole archive and turning its scans into checked transcriptions made it possible to gather
and compare every source on the **Madonna Nicopeia**, the Byzantine icon of the Virgin Victory-maker
taken to Venice after 1204. These sources span several languages, centuries and kinds of document, and
the author's analysis of the icon was written on that basis.

### Doctoral research

Scaffale is part of the author's doctoral research. There it is presented as **a first working example
of a large language model installed and run locally on an ordinary Windows PC** — a laptop with no
dedicated graphics card — and applied to the **semantic analysis of archives, including historical
ones**. The thesis uses it to show that a single researcher can index, read, transcribe, search by
meaning and question a whole archive of sources with open models on his own computer, without uploading
any document and with every statement traceable to the page of the original. The Linux configuration
with Qwen3.5-397B (see *Two versions*) shows how the same method scales to a more powerful machine.

Scaffale is published here as part of the documented record of the author's research software, with a
permanent DOI on Zenodo.

## How to cite

Use the citation metadata in [`CITATION.cff`](CITATION.cff) (GitHub: *Cite this repository*). The release
is archived on Zenodo with the DOI [10.5281/zenodo.24057200](https://doi.org/10.5281/zenodo.24057200).

> Sbarbaro, Massimo. 2026. *Scaffale: local indexing, OCR and semantic search of a personal research archive with a local language model*. Software, version 1.1. Zenodo. https://doi.org/10.5281/zenodo.24057200.

## License

Scaffale is free software, released under the [GNU General Public License v3.0](LICENSE) or (at your
option) any later version. © 2026 Massimo Sbarbaro. The files in `tessdata/` are distributed under the
Apache License 2.0 (see `tessdata/NOTICE`).
