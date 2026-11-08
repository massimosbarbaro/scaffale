# Scaffale: local indexing, OCR and semantic search of a personal research archive with a local language model

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24057200.svg)](https://doi.org/10.5281/zenodo.24057200)

*Indicizzazione, OCR e ricerca semantica di un archivio di ricerca personale, tutto in locale, con un modello linguistico installato sul computer*

2026 · version 1.0  
Author: **Massimo Sbarbaro** ([ORCID 0009-0006-8965-9013](https://orcid.org/0009-0006-8965-9013))

## Overview

Scaffale takes a disordered research folder — PDFs, Word files, notes, spreadsheets, old databases, mute
scans, folders of images that are a book photographed page by page — and turns it into a searchable
archive: one index, a direct link to every document and to the right page, and three ways of searching it.
Everything stays on the computer. No document is uploaded anywhere: the semantic search, the summaries and
the answers are produced by language models installed locally through [Ollama](https://ollama.com).
The internet is needed only to install.

The program was written for historical research (medieval and early-modern sources, editions and
secondary literature in Italian, Latin, Croatian, Slovene, German, French, English and Greek), where every
statement must be checked against the original: each passage found by the search keeps its page number
and opens the original PDF at that page.

## Research context

I designed and developed Scaffale in 2026 for my own research archive: about 15,000 documents — archival
sources, editions, scans of early printed books, articles and notes — indexed and searchable as one corpus.

- **A research corpus built with Scaffale.** Indexing the whole archive, and turning its scans into
  checked Markdown transcriptions, made it possible to gather and compare every source on the
  **Madonna Nicopeia** — the Byzantine icon of the Virgin Victory-maker taken to Venice after 1204 —
  across languages, centuries and kinds of document, and to write my analysis of the icon on that basis.
- **Local language models for the semantic analysis of archives.** In my doctoral work Scaffale is
  presented as a first case study of a language model running entirely on a local computer, applied to
  the semantic analysis of archives, including historical ones: search by meaning, questions answered
  only from the archive's own passages with their page references, themes and summaries — without
  sending any document outside the institution and without depending on a commercial online service.
- **Verifiable transcriptions.** A historian can quote a transcription only if its numbers and dates are
  right. Scaffale therefore converts PDFs and scans to Markdown with **three independent readings and an
  arbiter**: every line containing numbers or dates (Arabic or Roman numerals) is read by a first reader
  (Tesseract or a large local vision model) and again by a second local OCR model (`glm-ocr`); where the
  two disagree, a **third reader (PaddleOCR) acts as arbiter**. If no reading is confirmed, the line is
  kept as read and flagged `[⚠ verificare]` for a check on the original, never silently "corrected".
  For early-modern printing the three readings also vote word by word, and the long *s* is corrected
  with Tesseract's own dictionaries.

Scaffale is published here as part of the documented record of my research software, with a permanent
DOI on Zenodo.

## Main functions

- **Indexing** of whole folder trees: PDF, DOCX/DOC, RTF, ODT, EPUB, HTML, TXT/MD, CSV, XLS/XLSX, ODS,
  PPTX and old `.mdb`/`.accdb` databases; folders of numbered images are recognised and recomposed as one
  book. Text is split into passages of about 2,400 characters that keep their page number.
- **OCR** of scans in nine languages (Italian, Latin, English, Croatian, Slovene, German, French, ancient
  and modern Greek) with Tesseract, including early-modern Italian printing (long *s*).
- **Three ways of searching**: exact full-text search (SQLite FTS5), search expanded through an editable
  domain thesaurus of equivalent forms in several languages, and semantic search with `bge-m3` embeddings;
  the three can be combined.
- **Questions to the documents**: a question in natural language is answered by a local model
  (`qwen3:8b`) using only the passages found in the archive, each statement with its numbered source;
  a guard checks every number and date of the answer against the passages; an iterative "deep research"
  mode reads more passages before answering.
- **Groups, themes and summaries** of folders and documents produced by the local model, with themes
  proposed by the model and kept or discarded by the user.
- **PDF to Markdown with three readings and an arbiter**: lines containing numbers and dates are read by
  two independent OCR readers and, where they disagree, by a third reader (PaddleOCR) acting as arbiter;
  doubtful lines are flagged for verification instead of being silently "corrected" (see *Research
  context*). Existing `.md` files are collated, not overwritten.
- **Duplicates and copies**: identical files, compressed copies and excerpts of the same text are
  recognised and treated as one document.
- Long jobs can be stopped at a safe point and resumed; the computer is kept awake while working.

## How to install and use

The program and its guides are in Italian.

- **Windows 10/11:** read [`LEGGIMI.md`](LEGGIMI.md). Download `Scaffale.zip` from the latest
  [release](https://github.com/massimosbarbaro/scaffale/releases), extract it and double-click
  `Installa Scaffale.bat`: it installs Python, the Python packages, Tesseract, Ollama and the three
  models (about 10 GB in all) and puts the icon on the desktop.
- **Linux** (Ubuntu/Debian, Fedora, Arch): read [`LEGGIMI_LINUX.md`](LEGGIMI_LINUX.md) and run
  `./installa.sh`.
- **How it works**, module by module: [`GUIDA.md`](GUIDA.md).

Once installed, `python scaffale.py servi` opens the web interface in the browser (on the local machine
only); the first page asks for the folder to index.

## Technology

Python 3 (3.9 or later), FastAPI and uvicorn for the local web interface, SQLite with FTS5 for the index,
PyMuPDF for PDFs, Tesseract for OCR, Ollama with `bge-m3` (embeddings), `qwen3:8b` (summaries, themes,
answers) and `glm-ocr` (second reading of the numbers); optional RapidOCR/ONNX Runtime (PaddleOCR models)
as third reader. Python dependencies are listed in [`requisiti.txt`](requisiti.txt).

## Repository contents

| Path | Content |
|---|---|
| `*.py` | The program: `scaffale.py` (command line), `web.py` (web interface), `archivio.py` (index), `estrattori.py` and `formati.py` (file formats), `semantica.py` (embeddings), `domande.py` and `ricercatore.py` (questions to the documents), `biblioteca.py` and `temi_proposti.py` (groups, themes, summaries), `tesauro.py`, `tesauri.py` and `varianti.py` (thesauri), `trascrizioni.py`, `verifica_numeri.py`, `tre_letture.py`, `s_lunga.py`, `coppie.py` and `sistema.py` (Markdown transcriptions and their checks), other helpers. |
| `installa.ps1`, `*.bat` | Windows installer and launchers. |
| `installa.sh`, `avvia.sh`, `crea_collegamento.sh` | Linux installer and launchers. |
| `prepara.py` | Checks that everything needed is installed. |
| `tessdata/` | Tesseract language data used by the program and word lists extracted from them (Apache License 2.0, see `tessdata/NOTICE`). |
| `GUIDA.md`, `LEGGIMI.md`, `LEGGIMI_LINUX.md` | Guides (Italian). |

Not included: the author's index and documents, the automated tests (they run on copies of the author's
archive) and the development notes.

## How to cite

Use the citation metadata in [`CITATION.cff`](CITATION.cff) (GitHub: *Cite this repository*). The release is archived on Zenodo with the DOI [10.5281/zenodo.24057200](https://doi.org/10.5281/zenodo.24057200).

> Sbarbaro, Massimo. 2026. *Scaffale: local indexing, OCR and semantic search of a personal research archive with a local language model*. Software, version 1.0. Zenodo. https://doi.org/10.5281/zenodo.24057200.

## License

Scaffale is free software, released under the [GNU General Public License v3.0](LICENSE) or (at your
option) any later version. © 2026 Massimo Sbarbaro. The files in `tessdata/` are distributed under the
Apache License 2.0 (see `tessdata/NOTICE`).
