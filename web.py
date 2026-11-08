#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L'app web locale: una casella di ricerca e i risultati, con i link ai file."""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response

import threading

import archivio
import biblioteca
import citazione
import coppie
import domande
import estrattori
import ricercatore
import sistema
import cartelle as navigatore
import semantica
import strumenti
import tesauri
import tesauro
import temi_proposti
import trascrizioni
import varianti
import verifica_numeri

app = FastAPI(title="Scaffale")

# Un lavoro a cui si è chiesto di fermarsi è ancora vivo finché non si chiude
# davvero, al primo punto sicuro: fino ad allora conta come in corso.
IN_CORSO = ("in_corso", "da_fermare")

PAGINA = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<title>Scaffale</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--i:#1a1a1a;--f:#fbfaf7;--b:#d9d4c8;--a:#7a2e2e;--m:#6a6459}
*{box-sizing:border-box}
body{margin:0;background:var(--f);color:var(--i);font:16px/1.55 Georgia,'Iowan Old Style',serif}
header{padding:22px 28px 14px;border-bottom:1px solid var(--b)}
h1{margin:0;font-size:21px;letter-spacing:.02em;font-weight:600}
.sotto{color:var(--m);font-size:13px;margin-top:4px}
main{max-width:980px;margin:0 auto;padding:22px 28px 70px}
form{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
input[type=search]{flex:1;min-width:270px;padding:11px 13px;font:17px Georgia,serif;
 border:1px solid var(--b);border-radius:3px;background:#fff}
button{padding:11px 18px;font:15px Georgia,serif;background:var(--a);color:#fff;
 border:0;border-radius:3px;cursor:pointer}
nav{margin-top:9px;font-size:13px}
nav a{color:var(--m);text-decoration:none;margin-right:15px;border-bottom:1px solid var(--b)}
nav a.indietro{color:var(--a);font-weight:600;border:1px solid var(--a);border-radius:4px;padding:1px 8px}
nav a:hover{color:var(--a)}
.pannello{background:#fff;border:1px solid var(--b);border-radius:3px;padding:18px 20px;margin-bottom:22px}
.pannello h2{margin:0 0 6px;font-size:17px}
.pannello p{margin:0 0 14px;color:var(--m);font-size:14px}
.pannello input[type=text]{width:100%;padding:10px 12px;font:15px Georgia,serif;
 border:1px solid var(--b);border-radius:3px;margin-bottom:9px;background:var(--f)}
.riga2{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
.riga2 input[type=text]{flex:1;min-width:180px;margin:0}
.navig{border:1px solid var(--b);border-radius:3px;margin:10px 0;background:var(--f)}
.scorciatoie{padding:8px 10px;border-bottom:1px solid var(--b);font-size:13px}
.scorciatoie a{color:var(--a);text-decoration:none;margin-right:14px}
.briciole{padding:8px 10px;border-bottom:1px solid var(--b);font-size:13px;color:var(--m)}
.briciole a{color:var(--i);text-decoration:none}
.briciole a:hover{color:var(--a)}
.sceltone{padding:10px;border-bottom:1px solid var(--b);display:flex;gap:11px;align-items:center;flex-wrap:wrap}
.elenco{list-style:none;margin:0;padding:6px 0;max-height:260px;overflow:auto}
.elenco li{padding:4px 12px;font-size:14px}
.elenco li a{color:var(--i);text-decoration:none}
.elenco li:hover{background:var(--b)}
.barra{height:7px;background:var(--b);border-radius:4px;overflow:hidden;margin:12px 0 7px}
.barra i{display:block;height:100%;background:var(--a);width:0;transition:width .4s}
.diario{font:12px ui-monospace,Consolas,monospace;color:var(--m);white-space:pre-wrap;
 max-height:150px;overflow:auto;background:var(--f);padding:8px;border-radius:3px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--b)}
th{font-size:12px;color:var(--m);font-weight:600}
@media(prefers-color-scheme:dark){.pannello{background:#1f1f24}}
.modi{display:flex;gap:16px;font-size:13px;color:var(--m);margin:2px 0 16px}
.modi label{cursor:pointer}
.spiega{font-size:13px;color:var(--m);margin-bottom:18px;font-style:italic}
.ris{border-top:1px solid var(--b);padding:15px 0}
.tit{font-size:16px;font-weight:600}
.tit a{color:var(--i);text-decoration:none;border-bottom:1px solid var(--b)}
.tit a:hover{border-color:var(--a);color:var(--a)}
.meta{font-size:12.5px;color:var(--m);margin:3px 0 8px}
.meta span{margin-right:13px}
.brano{background:#fff;border:1px solid var(--b);border-left:3px solid var(--a);
 padding:10px 13px;border-radius:2px;font-size:14.5px}
.brano b{background:#f6e9c8;font-weight:600;padding:0 1px}
.azioni{font-size:12.5px;margin-top:7px;display:flex;gap:15px;align-items:baseline;flex-wrap:wrap}
.azioni a{color:var(--i);text-decoration:none;border-bottom:1px dotted var(--b)}
.azioni a:hover{color:var(--a);border-color:var(--a)}
.strada{color:var(--m);font:11.5px ui-monospace,Consolas,monospace;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;direction:rtl;text-align:left}
.avviso{background:#fdf6e3;border:1px solid var(--b);border-left:3px solid var(--a);
 padding:11px 14px;border-radius:2px;font-size:13.5px;margin-bottom:18px}
.avviso code{font:12.5px ui-monospace,Consolas,monospace;background:var(--f);padding:1px 5px}
@media(prefers-color-scheme:dark){.avviso{background:#26231c}}
.cartella{border-top:1px solid var(--b);padding:12px 0}
.cartella:first-of-type{border-top:0}
.cartella .nome{font-size:16px;font-weight:600}
.cartella .nome a{color:var(--i);text-decoration:none}
.cartella .nome a:hover{color:var(--a)}
.cartella .meta{margin:2px 0}
.cartella button{padding:7px 13px;font-size:14px}
a.pulsante{display:inline-block;padding:7px 13px;font:14px Georgia,serif;background:var(--i);
 color:var(--f);border-radius:3px;text-decoration:none}
a.pulsante:hover{background:var(--a)}
a.pulsante.secondario{background:transparent;color:var(--i);border:1px solid var(--b)}
a.pulsante.secondario:hover{color:var(--a);border-color:var(--a);background:transparent}
.descr{font-size:13px;margin:3px 0 2px;line-height:1.45}
select.dove{padding:10px 8px;font:15px Georgia,serif;border:1px solid var(--b);border-radius:3px;
 background:#fff;color:var(--i);max-width:260px}
details.aggiungi{margin-bottom:22px}
details.aggiungi summary{cursor:pointer;font-size:14px;color:var(--a);margin-bottom:10px}
.dentro{font-size:13px;color:var(--m);margin:-4px 0 12px}
.dentro b{color:var(--i)}
@media(prefers-color-scheme:dark){select.dove{background:#1f1f24}}
header{position:relative}
button.chiudi{position:absolute;right:28px;top:22px;padding:6px 12px;font-size:13px;
 background:transparent;color:var(--m);border:1px solid var(--b)}
button.chiudi:hover{color:var(--a);border-color:var(--a)}
.anteprima ul{margin:6px 0 12px 18px;padding:0;font-size:14px}
.anteprima li{margin:3px 0}
.scelte{display:flex;flex-direction:column;gap:9px;margin:14px 0 6px;align-items:flex-start}
.scelte span{font-size:12.5px;color:var(--m);margin-left:4px}
.aiuto{font-size:12.5px;color:var(--m);margin:-8px 0 16px;line-height:1.5}
.aiuto b{color:var(--i);font-weight:600}
.foglio{position:relative;border:1px solid var(--b);background:#fff;margin:12px 0}
.foglio img{display:block;width:100%;height:auto}
#qui{position:absolute;left:-7px;width:4px;height:28px;background:var(--a)}
.elenco-file{width:100%;border-collapse:collapse;font-size:13.5px}
.elenco-file td{padding:6px 8px;border-bottom:1px solid var(--b);vertical-align:top}
.elenco-file td.gesti{white-space:nowrap;font-size:12.5px}
.elenco-file td.gesti a{margin-right:9px;color:var(--i)}
.elenco-file .stato{font-size:12px;color:var(--m)}
details.sotto{margin:10px 0}
details.sotto summary{cursor:pointer;font-weight:600;font-size:14.5px;padding:4px 0}
.filtri{margin:8px 0 14px}
.filtri a{margin-right:12px;font-size:13px;color:var(--i)}
.filtri a.scelto{font-weight:600;color:var(--a);text-decoration:none}
.gruppo{border-top:1px solid var(--b);padding:12px 0}
.copia{display:flex;gap:12px;flex-wrap:wrap;align-items:baseline;padding:6px 0 6px 14px;
 border-left:3px solid var(--b);margin:6px 0}
.copia .dati{font-size:12.5px;color:var(--m)}
.uguale,.diverso{font-size:12px;padding:1px 7px;border-radius:9px}
.uguale{background:#e3efe3;color:#245a24}
.diverso{background:#f6e7cf;color:#7a4a00}
.copia a{font-size:12.5px;color:var(--i)}
button.cestino{padding:5px 11px;font-size:13px;background:transparent;color:var(--a);border:1px solid var(--a)}
button.cestino:disabled{color:var(--m);border-color:var(--b);cursor:default}
button.piccolo{padding:4px 10px;font-size:12.5px}
.numeri{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:10px 0 18px}
.numeri > div{border:1px solid var(--b);border-radius:3px;padding:10px 12px;background:var(--f);font-size:13px}
.numeri b.grande{display:block;font-size:22px;font-weight:600;color:var(--i)}
.numeri ul{margin:4px 0 0 16px;padding:0}
.gruppi{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:8px 0 16px}
.gruppi > div{border:1px solid var(--b);border-radius:3px;padding:10px 12px}
.gruppi h4{margin:0 0 6px;font-size:14px}
.gruppi p{font-size:12px;margin:0 0 8px}
.gruppi a.g{display:block;font-size:13.5px;color:var(--i);text-decoration:none;padding:2px 0}
.gruppi a.g:hover{color:var(--a)}
.gruppi a.g.scelto{font-weight:600;color:var(--a)}
.gruppi a.g span{color:var(--m);font-size:12px}
.gruppi .riga-g{display:flex;align-items:baseline;gap:6px}
.gruppi .riga-g a.g{flex:1}
.gruppi{grid-template-columns:minmax(0,2fr) minmax(0,1fr)}
@media(max-width:720px){.gruppi{grid-template-columns:minmax(0,1fr)}}
.gruppi > div{min-width:0}
.temi-unici{max-height:720px;overflow:auto;margin-top:6px}
.temi-unici .tema{border-top:1px solid var(--b);padding:3px 0}
.temi-unici .bollo{margin-right:4px;white-space:nowrap}
.temi-unici summary{cursor:pointer;font-size:13.5px;padding:2px 0}
.temi-unici .anche{margin:0 0 3px 14px;font-size:12px}
.filtro-temi button{margin:0 2px 4px 0;background:var(--m)}
.filtro-temi button.scelto{background:var(--a)}
.gruppi button.tieni{padding:0 6px;font-size:11.5px;line-height:18px;background:transparent;color:var(--a);border:1px solid var(--b)}
.gruppi button.tieni:hover{border-color:var(--a)}
.proposta{border-top:1px solid var(--b);padding:7px 0;font-size:13.5px}
.proposta .parole{font-size:12px;color:var(--m)}
.proposta.generico{opacity:.7}
.risposta p{margin:0 0 10px;line-height:1.55;color:var(--i);font-size:15px}
.cita{text-decoration:none;font-size:12px;vertical-align:super;padding:0 1px}
mark.dubbio{background:none;color:#b3261e;font-weight:600;border-bottom:1px dotted #b3261e}
.giudizio{font-size:11px;padding:0 6px;border-radius:8px;border:1px solid currentColor;font-weight:600}
.giudizio.buono{color:#2e7d32}.giudizio.da-controllare{color:#b26a00}.giudizio.da-rifare{color:#b3261e}
textarea#domanda{width:100%;box-sizing:border-box;font:inherit;padding:8px;border:1px solid var(--b)}
.etichetta{display:inline-block;font-size:11px;padding:0 6px;margin:2px 4px 0 0;border-radius:8px;
 background:var(--f);border:1px solid var(--b);color:var(--m);text-decoration:none}
.etichetta.mio{border-color:var(--a);color:var(--a)}
.barra-scelta{position:sticky;top:0;background:var(--f);border:1px solid var(--b);border-radius:3px;
 padding:8px 10px;margin:8px 0;display:flex;gap:9px;flex-wrap:wrap;align-items:center;font-size:13px;z-index:2}
.barra-scelta select,.riga2 select{padding:5px;font:13px Georgia,serif;max-width:320px}
.parole{font-size:12px;color:var(--m);font-style:italic}
.spiegazione{background:var(--f);border-left:3px solid var(--a);padding:9px 12px;font-size:13px;margin:8px 0 14px}
dl.scheda{display:grid;grid-template-columns:190px 1fr;gap:6px 14px;font-size:14px;margin:8px 0 18px}
dl.scheda dt{color:var(--m)}
dl.scheda dd{margin:0;min-width:0}
.vuoto{color:var(--m);padding:30px 0}
.bollo{display:inline-block;font-size:11px;padding:1px 6px;margin-right:13px;border:1px solid var(--b);
 border-radius:9px;color:var(--m)}
footer{max-width:980px;margin:0 auto;padding:0 28px 40px;color:var(--m);font-size:12.5px}
@media(prefers-color-scheme:dark){:root{--i:#e8e4dc;--f:#17171a;--b:#33323a;--a:#c98b8b;--m:#9a958c}
 input[type=search],.brano{background:#1f1f24}.brano b{background:#4a3f22;color:#f0e6c8}}
</style></head><body>
<header><h1>Scaffale</h1><div class="sotto">__SOTTO__</div>
<nav><a href="/" id="indietro" class="indietro" onclick="return tornaIndietro()">&larr; indietro</a>
<a href="/">ricerca</a> <a href="/domande">domande</a> <a href="/cartelle">cartelle</a> <a href="/doppioni">doppioni</a>
<a href="/tesauri">tesauri</a>
<button type="button" class="chiudi" onclick="chiudiScaffale(false)" title="spegne Scaffale e chiude la finestra nera">Chiudi Scaffale</button></nav>
</header>
<main>
__AVVIO__
<form action="/" method="get">
  <input type="search" name="q" value="__Q__" placeholder="una parola, un nome, una frase…" autofocus>
  __DOVE__
  <input type="hidden" name="modo" value="__MODO__">
  <button type="submit">Cerca</button>
</form>
<div class="modi">
  <label><input type="radio" form="" onclick="vai('tesauro')" __C_T__> tesauro</label>
  <label><input type="radio" onclick="vai('esatta')" __C_E__> esatta</label>
  <label><input type="radio" onclick="vai('semantica')" __C_S__> semantica</label>
  <label><input type="radio" onclick="vai('tutto')" __C_A__> tutte e tre</label>
  <span style="margin-left:auto">__STATOSEM__</span>
</div>
<div class="aiuto"><b>esatta</b>: tutte le parole, così come le scrivi (maiuscole e accenti
non contano). <b>tesauro</b>: tutte le parole, ma ognuna anche nelle sue varianti, grafie e
traduzioni, se è un tema dei <a href="/tesauri">tesauri</a> in uso nella cartella dove cerchi —
«duello» trova anche <i>duellum, dvoboj, Zweikampf</i>; per le altre parole è uguale
all'esatta. In tutti e due i casi le parole devono stare vicine, entro una pagina circa.
<b>semantica</b>: per senso, anche senza le stesse parole.</div>
__AVVISOSEM__
__SPIEGA__
__RISULTATI__
</main>
<footer>__PIEDE__</footer>
<script>
function vai(m){const u=new URL(location);u.searchParams.set('modo',m);vaiA(u)}

async function finestra(ev){
  const b = ev.target;
  b.disabled = true; b.textContent = 'guarda la finestra di sistema…';
  try {
    const d = await (await fetch('/api/finestra')).json();
    if (d.percorso) { imposta(d.percorso, d.percorso.split(/[^\u0000-\uFFFF]/).pop().split(String.fromCharCode(92)).pop()); }
    else if (d.non_disponibile) { alert("La finestra di sistema non è disponibile qui. Usa Scegli dall’elenco."); }
  } catch (e) { alert('Non sono riuscito ad aprire la finestra: ' + e); }
  b.disabled = false; b.textContent = 'Sfoglia…';
}

function imposta(p, nome){
  document.getElementById('cartella').value = p;
  const e = document.getElementById('etichetta');
  if (e && !e.value && nome) { e.value = nome; }
  const n = document.getElementById('navigatore');
  if (n) n.style.display = 'none';
}

function voce(testo, percorso, classe){
  const a = document.createElement('a');
  a.href = '#'; a.textContent = testo; a.dataset.percorso = percorso;
  if (classe) a.className = classe;
  a.addEventListener('click', function(ev){ ev.preventDefault(); naviga(this.dataset.percorso); });
  return a;
}

async function naviga(p){
  const n = document.getElementById('navigatore');
  n.style.display = 'block';
  n.innerHTML = '<div class="navig"><p style="padding:10px;color:var(--m);font-size:13px">carico…</p></div>';
  let d;
  try { d = await (await fetch('/api/sfoglia?percorso=' + encodeURIComponent(p || ''))).json(); }
  catch (e) { n.innerHTML = '<div class="navig"><p style="padding:10px">errore: ' + e + '</p></div>'; return; }
  if (d.errore) { n.innerHTML = '<div class="navig"><p style="padding:10px">' + d.errore + '</p></div>'; return; }

  const box = document.createElement('div'); box.className = 'navig';

  if (d.scorciatoie && d.scorciatoie.length) {
    const s = document.createElement('div'); s.className = 'scorciatoie';
    d.scorciatoie.forEach(x => s.appendChild(voce(x.nome, x.percorso)));
    box.appendChild(s);
  }
  if (d.briciole && d.briciole.length) {
    const b = document.createElement('div'); b.className = 'briciole';
    d.briciole.forEach((x, k) => {
      if (k) b.appendChild(document.createTextNode(' › '));
      b.appendChild(voce(x.nome, x.percorso));
    });
    box.appendChild(b);
  }
  if (d.percorso) {
    const s = document.createElement('div'); s.className = 'sceltone';
    const bt = document.createElement('button');
    bt.type = 'button'; bt.textContent = 'Uso questa cartella';
    bt.addEventListener('click', () => imposta(d.percorso, d.nome_breve));
    s.appendChild(bt);
    if (d.quanti) {
      const q = document.createElement('span');
      q.style.cssText = 'font-size:13px;color:var(--m)';
      q.textContent = d.quanti.documenti + ' documenti' +
        (d.quanti.immagini ? ', ' + d.quanti.immagini + ' immagini' : '');
      s.appendChild(q);
    }
    box.appendChild(s);
  }
  const ul = document.createElement('ul'); ul.className = 'elenco';
  if (d.su) {
    const li = document.createElement('li');
    li.appendChild(voce('↑ cartella superiore', d.su));
    ul.appendChild(li);
  }
  (d.cartelle || []).forEach(c => {
    const li = document.createElement('li');
    li.appendChild(voce(c.nome, c.percorso));
    ul.appendChild(li);
  });
  if (!(d.cartelle || []).length) {
    const li = document.createElement('li');
    li.style.color = 'var(--m)'; li.textContent = 'nessuna sottocartella';
    ul.appendChild(li);
  }
  box.appendChild(ul);
  n.innerHTML = ''; n.appendChild(box);
}

async function trascriviTrovati(b){
  const u = new URL(location);
  const q = u.searchParams.get('q') || '';
  const modo = u.searchParams.get('modo') || 'tesauro';
  const avviso = ["Creo un file .md accanto a ogni PDF trovato.",
                  "Dove un .md esiste gia non viene toccato: viene confrontato,",
                  "e le differenze finiscono nel rapporto.",
                  "Procedo?"].join(String.fromCharCode(10));
  if (!confirm(avviso)) return;
  b.disabled = true; b.textContent = 'lavoro in corso…';
  const e = document.getElementById('esitoMd');
  try {
    const r = await fetch('/trascrivi', {method:'POST', headers:{'Content-Type':'application/json'},
                          body: JSON.stringify({q:q, modo:modo, radice:u.searchParams.get('radice') || ''})});
    const d = await r.json();
    if (d.errore) { e.textContent = d.errore; }
    else { seguiMd(d.lavoro); }
  } catch (err) { e.textContent = 'errore: ' + err; b.disabled = false; }
}

async function creaMd(b){
  const quanti = b.dataset.quanti || '1';
  const cosa = quanti === '1' ? 'il file .md' : quanti + ' file .md';
  const rifai = b.dataset.rifai === '1';
  const avviso = rifai
    ? ['Rifaccio il .md di questo PDF, con la verifica dei numeri: qualche minuto per pagina.',
       'Il .md di adesso non si cancella: resta accanto, con il nome che finisce in .md.vecchio.',
       'Procedo?'].join(String.fromCharCode(10))
    : ['Creo ' + cosa + ' accanto ai PDF' + (b.dataset.tempo ? ': ' + b.dataset.tempo : '') + '.',
       'Dove un .md esiste già non viene toccato: viene confrontato,',
       'e le differenze finiscono nel rapporto.',
       'Procedo?'].join(String.fromCharCode(10));
  if (!confirm(avviso)) return;
  b.disabled = true;
  b.textContent = 'lavoro in corso…';
  const e = b.parentElement.querySelector('.esitoMd') || document.getElementById('esitoMd');
  const corpo = b.dataset.percorso ? {percorsi: [b.dataset.percorso], rifai: rifai}
                                   : {radice: b.dataset.radice, solo_senza_md: true};
  try {
    const d = await (await fetch('/trascrivi', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(corpo)})).json();
    if (d.errore) { e.textContent = d.errore; b.disabled = false; }
    else { seguiMd(d.lavoro, e); }
  } catch (err) { e.textContent = 'errore: ' + err; b.disabled = false; }
}

async function cestina(b){
  const a_capo = String.fromCharCode(10);
  const avverti = b.dataset.diverso ? (a_capo + a_capo + 'ATTENZIONE: questo file non ha copie identiche. ' +
      'Gli altri del gruppo hanno lo stesso testo ma sono file diversi (per esempio una versione ' +
      'compressa, con le immagini peggiori): toglierlo vuol dire perdere questa versione.') : '';
  if (!confirm('Sposto nel Cestino di Windows questo file?' + a_capo + a_capo + b.dataset.percorso +
               avverti + a_capo + a_capo + 'Si recupera dal Cestino quando vuoi. Gli altri file restano dove sono.')) return;
  b.disabled = true;
  let d;
  try {
    d = await (await fetch('/cestina', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({id: Number(b.dataset.id)})})).json();
  } catch (err) { alert('Scaffale non risponde: ' + err); b.disabled = false; return; }
  if (d.errore) { alert(d.errore); b.disabled = false; return; }
  const riga = b.closest('.copia');
  riga.style.opacity = '0.45';
  riga.querySelector('.dati').textContent = 'spostato nel Cestino';
  b.textContent = 'nel Cestino';
  const vivi = b.closest('.gruppo').querySelectorAll('button.cestino:not([disabled])');
  if (vivi.length <= 1) {
    vivi.forEach(function(x){ x.disabled = true; x.title = 'è rimasta una copia sola: questa si tiene'; });
  }
}

async function chiedi(url, corpo){
  const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
                              body: JSON.stringify(corpo)});
  return await r.json();
}

function selezionati(){
  return Array.from(document.querySelectorAll('input.scelta:checked')).map(function(x){ return x.value; });
}

function tuttiOnessuno(c){
  document.querySelectorAll('input.scelta').forEach(function(x){ x.checked = c.checked; });
}

async function seguiEPoi(id, e, poi){
  let d;
  try { d = await (await fetch('/api/lavoro?id=' + id)).json(); }
  catch (err) { setTimeout(function(){ seguiEPoi(id, e, poi); }, 3000); return; }
  e.textContent = (d.messaggio || '') + (d.totale ? '  (' + d.fatti + '/' + d.totale + ')' : '');
  if (d.stato === 'in_corso' || d.stato === 'da_fermare') { setTimeout(function(){ seguiEPoi(id, e, poi); }, 1000); }
  else { poi(d); }
}

async function analizzaCartella(b, da_solo){
  b.disabled = true;
  b.textContent = 'leggo le parole di ogni documento…';
  const e = b.parentElement.querySelector('.esitoMd');
  const d = await chiedi('/analizza', {radice: b.dataset.radice});
  if (d.errore) {
    if (da_solo) { e.textContent = d.errore; } else { alert(d.errore); }
    b.disabled = false;
    b.textContent = 'Analizza la cartella';
    return;
  }
  seguiEPoi(d.lavoro, e, function(){ ricarica(); });
}

async function riassumiTutti(b){
  const a_capo = String.fromCharCode(10);
  if (!confirm('Scrivo i riassunti di ' + b.dataset.quanti + ' documenti, uno dopo l’altro: ' +
               b.dataset.tempo + '.' + a_capo + a_capo +
               'Puoi continuare a usare Scaffale, e fermarlo quando vuoi: quelli fatti restano.')) return;
  b.disabled = true;
  const d = await chiedi('/riassumi_tutti', {radice: b.dataset.radice});
  if (d.errore) { alert(d.errore); b.disabled = false; return; }
  ricarica();
}

async function riassumiSpuntati(b){
  const ps = selezionati();
  if (!ps.length) { alert('Spunta prima i file da riassumere.'); return; }
  const minuti = Math.max(1, Math.round(ps.length * Number(b.dataset.perUno || 130) / 60));
  if (!confirm('Scrivo i riassunti dei ' + ps.length + ' file spuntati: circa ' + minuti +
               ' minuti. Quelli che lo hanno già li salto.')) return;
  const d = await chiedi('/riassumi_tutti', {radice: b.dataset.radice, percorsi: ps});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function riassumiGruppo(b){
  if (!confirm('Scrivo i riassunti dei file di questo gruppo: ' + b.dataset.tempo +
               '. Quelli che lo hanno già li salto.')) return;
  const d = await chiedi('/riassumi_tutti', {radice: b.dataset.radice, gruppo: Number(b.dataset.gruppo)});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function fermaQuesto(b){
  if (!confirm('Fermo? Quello che è già fatto resta.')) return;
  b.disabled = true;
  b.textContent = 'mi fermo…';
  try { await chiedi('/ferma', {lavoro: Number(b.dataset.lavoro)}); }
  catch (e) {
    alert('Il Ferma non è arrivato a Scaffale (' + e + '). Riprova fra qualche secondo.');
    b.disabled = false;
    b.textContent = 'ferma';
  }
}

(function(){
  document.querySelectorAll('[data-segui]').forEach(function(e){
    seguiEPoi(Number(e.dataset.segui), e, function(){ ricarica(); });
  });
  const auto = document.querySelector('button[data-auto="1"]');
  if (auto) analizzaCartella(auto, true);
})();

async function nuovoGruppo(b, con_i_selezionati){
  const nome = prompt('Come si chiama il gruppo nuovo?');
  if (!nome) return;
  const ps = con_i_selezionati ? selezionati() : (b.dataset.percorso ? [b.dataset.percorso] : []);
  const d = await chiedi('/gruppo', {azione: 'nuovo', radice: b.dataset.radice, nome: nome, percorsi: ps});
  if (d.errore) { alert(d.errore); return; }
  if (b.dataset.percorso) { ricarica(); }
  else { vaiA('/cartella?radice=' + encodeURIComponent(b.dataset.radice) + '&gruppo=' + d.id); }
}

function _forme(testo){
  return (testo || '').split(/[,;]/).map(function(x){ return x.trim(); }).filter(function(x){ return x.length > 1; });
}

async function nuovoTema(b){
  const nome = prompt('Come si chiama il tema? (per esempio: AI)');
  if (!nome) return;
  const parole = prompt('Con quali parole lo riconosco? Separale con la virgola, in tutte le lingue che ti servono.' +
                        String.fromCharCode(10) + 'Per esempio: AI, intelligenza artificiale, umetna inteligenca, LLM' +
                        String.fromCharCode(10) + 'Una sigla in maiuscolo, come AI, vale solo in maiuscolo.');
  const forme = _forme(parole);
  if (!forme.length) return;
  const e = b.parentElement.querySelector('.esitoMd');
  b.disabled = true;
  if (e) e.textContent = ' cerco i file… in una cartella grande, e con una sigla, anche mezzo minuto';
  let d;
  try { d = await chiedi('/gruppo', {azione: 'tema', radice: b.dataset.radice, nome: nome, forme: forme}); }
  catch (err) { d = {errore: 'Scaffale non risponde: ' + err}; }
  b.disabled = false;
  if (d.errore) { if (e) e.textContent = ''; alert(d.errore); return; }
  vaiA('/cartella?radice=' + encodeURIComponent(b.dataset.radice) + '&gruppo=' + d.id);
}

async function cambiaForme(b){
  const parole = prompt('Le parole del tema, separate dalla virgola:', b.dataset.forme || '');
  if (parole === null) return;
  const forme = _forme(parole);
  if (!forme.length) { alert('Il tema ha bisogno di almeno una parola.'); return; }
  const e = b.parentElement.querySelector('.esitoMd');
  b.disabled = true;
  if (e) e.textContent = ' cerco i file…';
  let d;
  try { d = await chiedi('/gruppo', {azione: 'forme', gruppo: Number(b.dataset.gruppo), forme: forme}); }
  catch (err) { d = {errore: 'Scaffale non risponde: ' + err}; }
  b.disabled = false;
  if (d.errore) { if (e) e.textContent = ''; alert(d.errore); return; }
  ricarica();
}

async function nuovoTesauro(){
  const nome = prompt('Come si chiama il tesauro? (per esempio: Duello e onore)');
  if (!nome) return;
  const descrizione = prompt('Di che cosa tratta, in una riga? (si può lasciare vuoto)') || '';
  const d = await chiedi('/tesauro', {azione: 'nuovo', nome: nome, descrizione: descrizione});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function rinominaTesauro(b){
  const nome = prompt('Il nome del tesauro:', b.dataset.nome || '');
  if (!nome) return;
  const descrizione = prompt('Di che cosa tratta, in una riga:', b.dataset.descrizione || '');
  const d = await chiedi('/tesauro', {azione: 'rinomina', tesauro: Number(b.dataset.tesauro),
                                      nome: nome, descrizione: descrizione});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function eliminaTesauro(b){
  if (!confirm('Elimino il tesauro «' + b.dataset.nome + '» con tutti i suoi temi? I file non si toccano.')) return;
  const d = await chiedi('/tesauro', {azione: 'elimina', tesauro: Number(b.dataset.tesauro)});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function _salvaTema(b, id_tema, nome_prima, forme_prima){
  const nome = prompt('Il nome del tema:', nome_prima || '');
  if (!nome) return;
  const parole = prompt('Le parole che lo dicono, separate dalla virgola, in tutte le lingue e grafie che ti servono.' +
                        String.fromCharCode(10) + 'Per esempio: duello, duellum, duel, dvoboj, Zweikampf', forme_prima || '');
  if (parole === null) return;
  const e = b.parentElement.querySelector('.esitoMd');
  b.disabled = true;
  if (e) e.textContent = ' salvo e cerco i file nelle cartelle che usano il tesauro…';
  let d;
  try { d = await chiedi('/tesauro', {azione: 'tema', tesauro: Number(b.dataset.tesauro),
                                       id_tema: id_tema, nome: nome, forme: _forme(parole)}); }
  catch (err) { d = {errore: 'Scaffale non risponde: ' + err}; }
  b.disabled = false;
  if (d.errore) { if (e) e.textContent = ''; alert(d.errore); return; }
  alert('Fatto. ' + d.esito);
  ricarica();
}

function nuovoTemaT(b){ apriEditor(b, null, '', ''); }
function modificaTemaT(b){ apriEditor(b, Number(b.dataset.tema), b.dataset.nome, b.dataset.forme); }

function _el(tag, testo, attr){
  const x = document.createElement(tag);
  if (testo) x.textContent = testo;
  for (const k in (attr || {})) x.setAttribute(k, attr[k]);
  return x;
}

function _cartellaScelta(){
  return new URLSearchParams(location.search).get('radice') || '';
}

// Il riquadro per fare o cambiare un tema: nome, parole, e due aiuti — le
// varianti che stanno nei documenti e le altre lingue chieste al modello.
// Niente entra da solo: si spunta, si aggiunge, si salva.
function apriEditor(b, id_tema, nome, forme){
  const pannello = b.closest('.pannello');
  pannello.querySelectorAll('.editor').forEach(function(x){ x.remove(); });
  const ed = _el('div', '', {'class': 'editor spiegazione', 'style': 'margin-top:10px'});
  ed.appendChild(_el('b', id_tema ? 'Cambia il tema' : 'Un tema nuovo'));
  const n = _el('input', '', {'type': 'text', 'placeholder': 'il nome del tema, per esempio: onore',
                              'style': 'display:block;width:100%;margin:6px 0'});
  n.value = nome || '';
  const f = _el('textarea', '', {'rows': '3', 'placeholder': 'le parole che lo dicono, separate dalla virgola: onore, honore, honor, Ehre',
                                 'style': 'display:block;width:100%;margin:0 0 6px'});
  f.value = forme || '';
  const dove = _cartellaScelta();
  const riga = _el('div', '', {'class': 'azioni'});
  const b1 = _el('button', 'Proponi varianti dai tuoi documenti', {'type': 'button', 'class': 'piccolo'});
  const b2 = _el('button', 'Chiedi al modello le altre lingue — circa un minuto', {'type': 'button', 'class': 'piccolo'});
  const stato = _el('span', dove ? ' i conti sono fatti in «' + dove + '»' : ' i conti sono fatti in tutto l’archivio', {'class': 'stato'});
  riga.appendChild(b1); riga.appendChild(b2); riga.appendChild(stato);
  const proposte = _el('div', '', {'class': 'proposte', 'style': 'margin:8px 0'});
  const fondo = _el('div', '', {'class': 'azioni', 'style': 'margin-top:8px'});
  const salva = _el('button', 'Salva il tema', {'type': 'button'});
  const annulla = _el('button', 'Annulla', {'type': 'button', 'class': 'piccolo', 'style': 'background:var(--m)'});
  fondo.appendChild(salva); fondo.appendChild(annulla);
  [n, f, riga, proposte, fondo].forEach(function(x){ ed.appendChild(x); });
  pannello.appendChild(ed);
  ed.scrollIntoView({block: 'center'});
  n.focus();

  function mostra(lista, titolo, assenti){
    proposte.innerHTML = '';
    proposte.appendChild(_el('div', titolo, {'style': 'font-weight:600;margin-bottom:4px'}));
    if (!lista.length) { proposte.appendChild(_el('div', 'Niente da proporre: nei documenti non ho trovato altre forme.', {'class': 'meta'})); }
    lista.forEach(function(p){
      const l = _el('label', '', {'style': 'display:block;font-size:13.5px'});
      const c = _el('input', '', {'type': 'checkbox', 'value': p.forma});
      l.appendChild(c);
      l.appendChild(document.createTextNode(' ' + p.forma + ' — ' + p.file + ' file · ' + p.perche));
      proposte.appendChild(l);
    });
    if (assenti && assenti.length) {
      proposte.appendChild(_el('div', 'Proposte dal modello ma assenti dai tuoi documenti, quindi lasciate fuori: ' + assenti.join(', '),
                               {'class': 'meta', 'style': 'margin-top:4px'}));
    }
    if (lista.length) {
      const agg = _el('button', 'Aggiungi le spuntate alle parole', {'type': 'button', 'class': 'piccolo', 'style': 'margin-top:6px'});
      agg.onclick = function(){
        const scelte = Array.from(proposte.querySelectorAll('input:checked')).map(function(x){ return x.value; });
        if (!scelte.length) { alert('Spunta prima quelle da aggiungere.'); return; }
        const ora = _forme(f.value);
        scelte.forEach(function(s){ if (ora.indexOf(s) < 0) ora.push(s); });
        f.value = ora.join(', ');
        proposte.querySelectorAll('input:checked').forEach(function(x){ x.closest('label').remove(); });
      };
      proposte.appendChild(agg);
    }
  }

  async function chiedi_(via, corpo, bott, attesa){
    const prima = bott.textContent;
    bott.disabled = true; bott.textContent = attesa;
    let d;
    try { d = await chiedi(via, corpo); } catch (err) { d = {errore: 'Scaffale non risponde: ' + err}; }
    bott.disabled = false; bott.textContent = prima;
    return d;
  }

  b1.onclick = async function(){
    if (!_forme(f.value).length) { alert('Scrivi prima almeno una parola del tema.'); return; }
    const d = await chiedi_('/varianti', {parole: _forme(f.value), radice: dove}, b1, 'cerco nei documenti…');
    if (d.errore) { alert(d.errore); return; }
    mostra(d.proposte, 'Varianti che stanno nei tuoi documenti — spunta quelle giuste:');
  };
  b2.onclick = async function(){
    if (!_forme(f.value).length) { alert('Scrivi prima almeno una parola del tema.'); return; }
    const d = await chiedi_('/traduzioni', {nome: n.value, parole: _forme(f.value), radice: dove}, b2,
                            'il modello ci pensa… (circa un minuto)');
    if (d.errore) { alert(d.errore); return; }
    mostra(d.proposte, 'Proposte da ' + d.modello + ' che stanno nei tuoi documenti — controllale, il modello può sbagliare:', d.assenti);
  };
  annulla.onclick = function(){ ed.remove(); };
  salva.onclick = async function(){
    if (!n.value.trim()) { alert('Il tema ha bisogno di un nome.'); return; }
    const d = await chiedi_('/tesauro', {azione: 'tema', tesauro: Number(b.dataset.tesauro), id_tema: id_tema,
                                         nome: n.value, forme: _forme(f.value)}, salva,
                            'salvo e cerco i file nelle cartelle che usano il tesauro…');
    if (d.errore) { alert(d.errore); return; }
    alert('Fatto. ' + d.esito);
    ricarica();
  };
}

// da «fanne un tema»: l'editor del tema appena fatto si apre da solo
(function(){
  const t = new URLSearchParams(location.search).get('tema');
  if (!t) return;
  const b = document.querySelector('button[data-tema="' + t + '"][onclick^="modificaTemaT"]');
  if (b) setTimeout(function(){ modificaTemaT(b); }, 200);
})();

async function tieniGruppo(b){
  b.disabled = true;
  const d = await chiedi('/gruppo', {azione: 'tieni', gruppo: Number(b.dataset.gruppo)});
  if (d.errore) { alert(d.errore); b.disabled = false; return; }
  vaiA('/cartella?radice=' + encodeURIComponent(b.dataset.radice) + '&gruppo=' + d.id);
}

async function proponiTemi(b){
  const e = b.parentElement.querySelector('.esitoMd');
  b.disabled = true;
  const d = await chiedi('/proponi_temi', {radice: b.dataset.radice});
  if (d.errore) { alert(d.errore); b.disabled = false; return; }
  b.textContent = 'il modello sta leggendo la cartella…';
  seguiEPoi(d.lavoro, e, function(){ ricarica(); });
}

async function temaProposto(b){
  const e = b.parentElement.querySelector('.esitoMd');
  b.disabled = true;
  const richiesta = {azione: b.dataset.azione, id: Number(b.dataset.id)};
  if (b.dataset.azione === 'tieni') {
    // le parole lasciate spuntate, più quelle scritte a mano
    const p = b.closest('.proposta');
    const forme = Array.from(p.querySelectorAll('input.forma:checked')).map(function(x){ return x.value; });
    const altre = p.querySelector('input.altre-forme');
    if (altre && altre.value.trim()) altre.value.split(',').forEach(function(x){ if (x.trim()) forme.push(x.trim()); });
    if (!forme.length) { alert('Lascia almeno una parola, o scrivine una tua.'); b.disabled = false; return; }
    richiesta.forme = forme;
    if (e) e.textContent = ' cerco i file del tema…';
  }
  const d = await chiedi('/tema_proposto', richiesta);
  if (d.errore) { alert(d.errore); b.disabled = false; if (e) e.textContent = ''; return; }
  ricarica();
}

// la verifica dei numeri: la riga giusta va nel .md
async function salvaVerifica(b){
  const v = b.closest('.brano');
  const e = v.querySelector('.esitoMd');
  b.disabled = true;
  const d = await chiedi('/verifica', {percorso: b.dataset.percorso, codice: b.dataset.codice,
                                       testo: v.querySelector('input.giusto').value});
  if (d.errore) { alert(d.errore); b.disabled = false; return; }
  v.style.opacity = '.55';
  e.textContent = ' salvato nel .md';
  const r = document.getElementById('restano');
  if (r) r.textContent = d.restano;
}

function usaSeconda(b){
  b.closest('.brano').querySelector('input.giusto').value = b.dataset.seconda;
}

// l'elenco dei temi, filtrato per provenienza: tutti, tuoi, dal tesauro, dal modello, scoperti
function filtraTemi(b){
  const tipo = b.dataset.tipo;
  document.querySelectorAll('.filtro-temi button').forEach(function(x){ x.classList.toggle('scelto', x === b); });
  document.querySelectorAll('.temi-unici > .tema').forEach(function(r){
    r.style.display = (tipo === 'tutti' || r.dataset.tipo === tipo) ? '' : 'none';
  });
}

async function chiediDomanda(b){
  const t = document.getElementById('domanda').value.trim();
  if (t.length < 3) { alert('Scrivi prima la domanda.'); return; }
  const dove = b.parentElement.querySelector('select.dove');
  const prima = b.textContent;
  b.disabled = true; b.textContent = 'cerco i brani…';
  const d = await chiedi('/domanda', {domanda: t, radice: dove ? dove.value : ''});
  if (d.errore) { alert(d.errore); b.disabled = false; b.textContent = prima; return; }
  vaiA('/domande?id=' + d.id);
}

async function sistemaCartella(b){
  const scelte = {};
  let secondi = 0;
  document.querySelectorAll('input.passo-sistema').forEach(function(x){
    scelte[x.value] = x.checked;
    if (x.checked) secondi += Number(x.dataset.secondi || 0);
  });
  if (!Object.values(scelte).some(function(v){ return v; })) { alert('Spunta almeno una cosa da fare.'); return; }
  const ore = secondi / 3600;
  const quanto = ore >= 1 ? 'circa ' + ore.toFixed(1).replace('.', ',') + ' ore' : 'circa ' + Math.max(1, Math.round(secondi / 60)) + ' minuti';
  if (!confirm('Sistemo la cartella: ' + quanto + '. Si può continuare a usare Scaffale, e fermarlo quando vuoi. Procedo?')) return;
  b.disabled = true; b.textContent = 'comincio…';
  const e = b.parentElement.querySelector('.esitoMd');
  const d = await chiedi('/sistema', {radice: b.dataset.radice, scelte: scelte});
  if (d.errore) { alert(d.errore); b.disabled = false; b.textContent = 'Sistema la cartella'; return; }
  seguiEPoi(d.lavoro, e, function(){ ricarica(); });
}

async function chiediRicercatore(b){
  const t = document.getElementById('domanda').value.trim();
  if (t.length < 3) { alert('Scrivi prima la domanda.'); return; }
  const dove = b.parentElement.querySelector('select.dove');
  const prima = b.textContent;
  b.disabled = true; b.textContent = 'il ricercatore comincia…';
  const d = await chiedi('/ricerca_approfondita', {domanda: t, radice: dove ? dove.value : ''});
  if (d.errore) { alert(d.errore); b.disabled = false; b.textContent = prima; return; }
  vaiA('/domande?id=' + d.id);
}

async function togliDomanda(b){
  if (!confirm('Tolgo questa domanda e la sua risposta dall’elenco?')) return;
  const d = await chiedi('/domanda_togli', {id: Number(b.dataset.id)});
  if (d.errore) { alert(d.errore); return; }
  vaiA('/domande');
}

async function inTema(b){
  const scelta = b.parentElement.querySelector('select.in-tesauro').value;
  let tid = Number(scelta);
  if (scelta === 'nuovo') {
    const nome = prompt('Come si chiama il tesauro nuovo? (per esempio: Duello e onore)');
    if (!nome) return;
    const d0 = await chiedi('/tesauro', {azione: 'nuovo', nome: nome, descrizione: ''});
    if (d0.errore) { alert(d0.errore); return; }
    tid = d0.id;
  }
  b.disabled = true;
  b.textContent = 'faccio il tema…';
  const d = await chiedi('/gruppo', {azione: 'in_tema', gruppo: Number(b.dataset.gruppo), tesauro: tid});
  if (d.errore) { alert(d.errore); b.disabled = false; b.textContent = 'fanne un tema'; return; }
  vaiA('/tesauri?radice=' + encodeURIComponent(b.dataset.radice) + '&tema=' + d.tema + '#t' + d.tesauro);
}

async function eliminaTemaT(b){
  if (!confirm('Elimino il tema «' + b.dataset.nome + '»? I file non si toccano.')) return;
  const d = await chiedi('/tesauro', {azione: 'togli_tema', tesauro: Number(b.dataset.tesauro),
                                      id_tema: Number(b.dataset.tema)});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function salvaTesauri(b){
  const ids = Array.from(document.querySelectorAll('input.usa-tesauro:checked')).map(function(x){ return Number(x.value); });
  const e = b.parentElement.querySelector('.esitoMd');
  b.disabled = true;
  const d = await chiedi('/tesauro', {azione: 'attiva', radice: b.dataset.radice, tesauri: ids});
  if (d.errore) { alert(d.errore); b.disabled = false; return; }
  seguiEPoi(d.lavoro, e, function(){
    vaiA('/cartella?radice=' + encodeURIComponent(b.dataset.radice));
  });
}

async function mettiSelezionati(b, sposta){
  const g = document.getElementById('dove_mettere').value;
  const ps = b.dataset.percorso ? [b.dataset.percorso] : selezionati();
  if (!g) { alert('Scegli prima il gruppo.'); return; }
  if (!ps.length) { alert('Spunta prima i file.'); return; }
  const d = await chiedi('/gruppo', {azione: 'metti', gruppo: Number(g), percorsi: ps,
                                     da: sposta && b.dataset.da ? Number(b.dataset.da) : null});
  if (d.errore) { alert(d.errore); return; }
  ricarica();
}

async function gestisciGruppo(b){
  const az = b.dataset.azione;
  const corpo = {azione: az, gruppo: Number(b.dataset.gruppo)};
  if (az === 'rinomina') {
    const n = prompt('Nuovo nome del gruppo:', b.dataset.nome || '');
    if (!n) return;
    corpo.nome = n;
  }
  if (az === 'elimina' && !confirm('Elimino il gruppo? I file non si toccano: restano sul disco dove sono, e negli altri gruppi.')) return;
  if (az === 'togli') corpo.percorsi = b.dataset.percorso ? [b.dataset.percorso] : selezionati();
  const d = await chiedi('/gruppo', corpo);
  if (d.errore) { alert(d.errore); return; }
  if (az === 'elimina' && b.dataset.torna) { vaiA(b.dataset.torna); } else { ricarica(); }
}

async function riassumi(b){
  b.disabled = true;
  b.textContent = 'sto leggendo il documento… ' + (b.dataset.tempo || '');
  try {
    const d = await chiedi('/riassumi', {percorso: b.dataset.percorso});
    if (d.errore) { alert(d.errore); b.disabled = false; b.textContent = 'Riprova'; return; }
    ricarica();
  } catch (err) { alert('Scaffale non risponde: ' + err); b.disabled = false; }
}

async function seguiMd(id, dove){
  const e = dove || document.getElementById('esitoMd');
  const d = await (await fetch('/api/lavoro?id=' + id)).json();
  if (!d) return;
  e.textContent = (d.stato === 'da_fermare' ? 'mi sto fermando… ' : '') + (d.messaggio || '') +
                  (d.totale ? '  (' + d.fatti + '/' + d.totale + ')' : '') + ' ';
  if (d.stato === 'in_corso') {
    const f = riga('a', 'ferma');
    f.href = '#';
    f.addEventListener('click', function(ev){
      ev.preventDefault();
      fetch('/ferma', {method: 'POST', headers: {'Content-Type': 'application/json'},
                       body: JSON.stringify({lavoro: id})});
      f.textContent = 'mi fermo…';
    });
    e.appendChild(f);
  }
  if ((d.stato === 'in_corso' || d.stato === 'da_fermare')) { setTimeout(() => seguiMd(id, e), 1500); }
  else {
    e.innerHTML = (d.messaggio || 'finito') +
      ' — <a href="/rapporto_md" target="_blank">apri il rapporto</a>';
  }
}

async function avvia(){
  const c = document.getElementById('cartella').value.trim();
  if (!c) { alert("Scegli prima una cartella: usa il pulsante Sfoglia oppure Scegli dall’elenco."); return; }
  const n = document.getElementById('etichetta').value.trim();
  mostraAnteprima({cartella: c, nome: n});
}

let attesa = null;
let lavoroInCorso = null;

async function mostraAnteprima(richiesta){
  attesa = richiesta;
  for (const id of ['cartelleTue', 'avvioForm']) {
    const e = document.getElementById(id);
    if (e) e.style.display = 'none';
  }
  const box = document.getElementById('anteprima');
  box.style.display = 'block';
  box.innerHTML = '';
  box.appendChild(riga('h2', 'Conto i file…'));
  box.appendChild(riga('p', 'Guardo che cosa c’è nella cartella e che cosa è cambiato. Su un archivio grande ci vuole qualche decina di secondi.'));
  box.scrollIntoView();
  let d;
  try {
    d = await (await fetch('/anteprima', {method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(richiesta)})).json();
  } catch (e) { alert('Scaffale non risponde: ' + e); ricarica(); return; }
  if (d.errore) { alert(d.errore); ricarica(); return; }
  box.innerHTML = d.html;
  box.scrollIntoView();
}

async function scegli(b){
  if (b.dataset.annulla) { vaiA('/'); return; }
  const r = attesa;
  if (!r) return;
  const ocr = b.dataset.ocr === '1';
  for (const x of document.querySelectorAll('#anteprima button')) x.disabled = true;
  b.textContent = 'avvio…';
  let url = '/indicizza';
  let corpo = {cartella: r.cartella, nome: r.nome || '', ocr: ocr};
  if (r.radice) { url = '/aggiorna'; corpo = {radice: r.radice, ocr: ocr}; }
  let d;
  try {
    d = await (await fetch(url, {method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(corpo)})).json();
  } catch (e) { alert('Scaffale non risponde: ' + e); ricarica(); return; }
  if (d.errore) { alert(d.errore); ricarica(); return; }
  document.getElementById('anteprima').style.display = 'none';
  const p = document.getElementById('avanzamento');
  p.style.display = 'block';
  p.querySelector('h2').textContent = (r.radice ? 'Aggiorno ' : 'Indicizzo ') + (d.nome || '');
  segui(d.lavoro);
}

async function fermaLavoro(b){
  if (!lavoroInCorso) return;
  if (!confirm('Fermo il lavoro? Quello che è già fatto resta, e la prossima volta Aggiorna riprende da lì.')) return;
  b.disabled = true;
  b.textContent = 'mi fermo al primo punto sicuro…';
  try {
    const r = await fetch('/ferma', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                     body: JSON.stringify({lavoro: lavoroInCorso})});
    if (!r.ok) throw new Error('risposta ' + r.status);
  } catch (e) {
    alert('Il Ferma non è arrivato a Scaffale (' + e + '). Riprova fra qualche secondo.');
    b.disabled = false;
    b.textContent = 'Ferma';
  }
}

async function segui(id){
  lavoroInCorso = id;
  let d;
  try { d = await (await fetch('/api/lavoro?id=' + id)).json(); }
  catch (e) { setTimeout(() => segui(id), 4000); return; }
  if (!d) return;
  const pc = d.totale ? Math.round(100 * d.fatti / d.totale) : 0;
  document.getElementById('barra').style.width = pc + '%';
  document.getElementById('messaggio').textContent =
    (d.stato === 'da_fermare' ? 'mi sto fermando al primo punto sicuro… ' : '') +
    (d.messaggio || '') + (d.totale ? '  (' + d.fatti + '/' + d.totale + ')' : '');
  document.getElementById('diario').textContent = d.diario || '';
  if ((d.stato === 'in_corso' || d.stato === 'da_fermare')) { setTimeout(() => segui(id), 1500); }
  else {
    lavoroInCorso = null;
    const f = document.getElementById('bottoneFerma');
    if (f) f.style.display = 'none';
    const detto = d.stato === 'fermato' ? 'Fermato. ' : (d.stato === 'errore' ? 'Errore: ' : 'Finito. ');
    document.getElementById('messaggio').textContent = detto + (d.messaggio || '');
    setTimeout(() => vaiA('/'), 5000);
  }
}

async function aggiornaCartella(b){
  mostraAnteprima({radice: b.dataset.radice});
}

(function(){
  const p = document.getElementById('avanzamento');
  if (p && p.dataset.lavoro) {
    const lista = document.getElementById('cartelleTue');
    if (lista) lista.style.display = 'none';
    p.style.display = 'block';
    segui(p.dataset.lavoro);
  }
})();

async function calcolaVettori(b){
  b.disabled = true; b.textContent = 'avvio…';
  let d;
  try { d = await (await fetch('/vettori', {method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({radice: b.dataset.radice || ''})})).json(); }
  catch (e) { alert('Scaffale non risponde: ' + e); b.disabled = false; return; }
  if (d.errore) { alert(d.errore); ricarica(); return; }
  seguiVettori(d.lavoro);
}

function riga(tag, testo, classe){
  const e = document.createElement(tag);
  if (testo) e.textContent = testo;
  if (classe) e.className = classe;
  return e;
}

async function seguiVettori(id){
  const box = document.getElementById('avvisoSem');
  if (!box) return;
  let d;
  try { d = await (await fetch('/api/lavoro?id=' + id)).json(); }
  catch (e) { setTimeout(function(){ seguiVettori(id); }, 5000); return; }
  if (!d) return;
  box.innerHTML = '';
  if ((d.stato === 'in_corso' || d.stato === 'da_fermare')) {
    box.appendChild(riga('b', 'Sto calcolando i vettori' + (d.nome ? ' di ' + d.nome : '') + '.'));
    box.appendChild(document.createTextNode(
      ' Lascia aperta la finestra nera di Scaffale: se la chiudi il calcolo si ferma, ' +
      'e la volta dopo riprende da dove era. Intanto puoi cercare con il tesauro.'));
    const barra = riga('div', '', 'barra');
    const pieno = document.createElement('i');
    pieno.style.width = (d.totale ? (100 * d.fatti / d.totale).toFixed(1) : 0) + '%';
    barra.appendChild(pieno);
    box.appendChild(barra);
    box.appendChild(riga('span', (d.stato === 'da_fermare' ? 'mi sto fermando… ' : '') + (d.messaggio || 'avvio…')));
    if (d.stato === 'in_corso') {
      lavoroInCorso = id;
      const f = riga('div', '', 'riga2');
      f.style.marginTop = '9px';
      const b = riga('button', 'Ferma');
      b.type = 'button';
      b.style.background = 'var(--m)';
      b.addEventListener('click', function(){ fermaLavoro(this); });
      f.appendChild(b);
      f.appendChild(riga('span', 'i vettori già calcolati restano'));
      box.appendChild(f);
    }
    setTimeout(function(){ seguiVettori(id); }, 4000);
  } else if (d.stato === 'errore') {
    box.appendChild(riga('b', 'Il calcolo si è fermato per un errore. '));
    box.appendChild(document.createTextNode(d.messaggio || ''));
  } else {
    box.appendChild(riga('b', d.stato === 'fermato' ? 'Fermato. ' : 'Fatto. '));
    box.appendChild(document.createTextNode((d.messaggio || '') + '.'));
    setTimeout(function(){ ricarica(); }, 3000);
  }
}

(function(){
  const box = document.getElementById('avvisoSem');
  if (box && box.dataset.lavoro) seguiVettori(box.dataset.lavoro);
})();

let spento = false;

async function chiudiScaffale(forza){
  if (!forza && !confirm('Chiudo Scaffale? Si spegne il programma e si chiude anche la finestra nera.')) return;
  let d;
  try {
    d = await (await fetch('/spegni', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                       body: JSON.stringify({forza: !!forza})})).json();
  } catch (e) { d = {spento: true}; }
  if (d.lavoro_in_corso) {
    if (confirm(d.lavoro_in_corso + ' Lo fermo e chiudo? Quello che è già fatto resta.')) chiudiScaffale(true);
    return;
  }
  spento = true;
  document.body.innerHTML = '';
  const m = riga('main', '');
  m.appendChild(riga('h2', 'Scaffale è chiuso.'));
  m.appendChild(riga('p', 'Puoi chiudere questa scheda. Per riaprirlo, doppio clic sull’icona di Scaffale.'));
  document.body.appendChild(m);
}

// Un segno di vita ogni venti secondi. Quando non arriva più da nessuna scheda,
// Scaffale capisce che il browser è stato chiuso e si spegne da solo — ma non
// se sta lavorando: allora finisce, e si spegne dopo.
const scheda = Math.random().toString(36).slice(2);
let schede_aperte = 1;
function battito(){
  if (spento) return;
  fetch('/battito?scheda=' + scheda, {method: 'POST'})
    .then(function(r){ return r.json(); })
    .then(function(d){ if (d && d.schede) schede_aperte = d.schede; })
    .catch(function(){});
}

// Chiudere la scheda non chiede niente: il browser non dice a una pagina se la
// si sta chiudendo o se si torna indietro con le frecce, e una domanda alla
// chiusura usciva anche con le frecce. Chiusa l'ultima scheda di Scaffale, il
// battito smette e Scaffale si spegne da solo pochi secondi dopo, finestra nera
// compresa. Per chiudere con una domanda c'è il pulsante «Chiudi Scaffale».
function ricarica(){ location.reload(); }
function vaiA(u){ location = u; }

// Il pulsante «indietro»: la pagina di prima, se ce n’è una in questa scheda;
// se la pagina si è aperta in una scheda nuova — un PDF dai risultati — chiude
// la scheda e si torna a quella da cui si era partiti; se no, alla ricerca.
function _daScaffale(){
  return document.referrer && document.referrer.indexOf(location.origin) === 0;
}
function _schedaNuova(){
  // una scheda aperta da un link di Scaffale, con dentro solo questa pagina:
  // il browser permette di chiuderla
  return history.length === 1 && _daScaffale();
}
function tornaIndietro(){
  if (history.length > 1) { history.back(); return false; }
  if (_schedaNuova()) {
    window.close();
    setTimeout(function(){ location = '/'; }, 400);     // se il browser non la chiude
    return false;
  }
  return true;                                             // va alla ricerca
}
(function(){
  const b = document.getElementById('indietro');
  if (!b) return;
  if (_schedaNuova()) {
    b.innerHTML = '&larr; chiudi e torna indietro';
  } else if (history.length === 1 && location.pathname === '/' && !location.search) {
    b.style.display = 'none';                              // la prima pagina: non c’è un indietro
  }
})();
battito();
setInterval(battito, 20000);
// una scheda lasciata dietro le altre il browser la rallenta o la mette a
// dormire, e il battito tace: appena la si guarda di nuovo, si fa sentire subito
document.addEventListener('visibilitychange', function(){ if (!document.hidden) battito(); });
window.addEventListener('pageshow', battito);
window.addEventListener('pagehide', function(){
  if (!spento) navigator.sendBeacon('/addio?scheda=' + scheda);
});

</script></body></html>"""


def _link_file(percorso, pagina=None):
    """Il link che apre davvero il documento.

    Un `file:///` scritto dentro una pagina servita via http il browser lo
    ignora in silenzio, per una regola di sicurezza che non si può aggirare e
    che non dà nessun avviso: si clicca e non succede niente. Il documento passa
    quindi da Scaffale stesso, che lo serve; e per i PDF il numero di pagina
    arriva al lettore del browser, che ci salta sopra.
    """
    u = "/apri?percorso=" + urllib.parse.quote(percorso)
    if pagina and percorso.lower().endswith(".pdf"):
        u += f"#page={pagina}"
    return u


# Un foglio di calcolo non ha pagine, e un database nemmeno: il numero che
# Scaffale conserva indica il foglio, la tabella o la diapositiva. Chiamarlo
# sempre «pagina» lascerebbe il lettore senza sapere dove guardare.
DOVE = {".xls": "foglio", ".xlsx": "foglio", ".xlsm": "foglio", ".ods": "foglio",
        ".mdb": "tabella", ".accdb": "tabella",
        ".pptx": "diapositiva", ".odp": "diapositiva"}


# Questi hanno pagine vere: il numero rimanda a un punto che si ritrova
# nell'originale. Un Word, un testo, un .rtf non ne hanno — per loro il numero
# sarebbe sempre «pagina 1», anche al brano 154 di 206, e manderebbe a
# cercare nel posto sbagliato.
CON_PAGINE = (".pdf", ".immagini")


def _dove(percorso, pagina):
    if not pagina:
        return ""
    e = os.path.splitext(percorso)[1].lower()
    if e in DOVE:
        return f"{DOVE[e]} {pagina}"
    if e in CON_PAGINE or percorso.endswith("[ricomposto].txt"):
        return f"pagina {pagina}"
    return ""


QUANTI = {"foglio": "fogli", "tabella": "tabelle", "diapositiva": "diapositive"}


def _estensione(percorso, pagine):
    """Quanto è lungo il documento, nell'unità che ha: 106 pp., 3 fogli, niente."""
    if not pagine:
        return ""
    e = os.path.splitext(percorso)[1].lower()
    if e in DOVE:
        return f"{pagine} {QUANTI[DOVE[e]] if pagine != 1 else DOVE[e]}"
    if e in CON_PAGINE or percorso.endswith("[ricomposto].txt"):
        return f"{pagine} pp."
    return ""


def _dove_o_brano(percorso, pagina, frammento):
    """La pagina, se il formato ne ha; se no, il posto del brano nel documento."""
    dove = _dove(percorso, pagina)
    if dove or not frammento:
        return dove
    n, di = archivio.posizione(frammento)
    return f"brano {n} di {di}" if n and di and di > 1 else ""


def _evidenzia(testo, query):
    forme = [f for f in tesauro.espandi(query) if len(f) > 3][:40]
    fuori = html.escape(testo)
    for f in sorted(set(forme), key=len, reverse=True):
        fuori = re.sub(f"(?i)({re.escape(f)})", r"<b>\1</b>", fuori)
    return fuori


def _ritaglio(brano):
    """Il ritaglio che SQLite fa attorno alla parola trovata.

    La parola arriva fra due segni di servizio, che qui diventano grassetto.
    È il pezzo giusto da mostrare: un frammento è lungo 2.400 caratteri e la
    parola cercata può stare in fondo, dove mostrando l'inizio non si vedrebbe
    — ed era proprio questo a far sembrare che i risultati venissero da chissà
    dove. I caporali del testo restano quelli dell'autore.
    """
    fuori = html.escape(brano or "")
    return fuori.replace("\x02", "<b>").replace("\x03", "</b>")


AVVIO = r"""
<div class="pannello" id="avvioForm">
  <h2>__TITOLO__</h2>
  <p>__SPIEGAZIONE__</p>
  <div class="riga2" style="margin-bottom:9px">
    <button type="button" onclick="finestra(event)" style="background:var(--i)">Sfoglia…</button>
    <button type="button" onclick="naviga('')" style="background:var(--i)">Scegli dall'elenco</button>
    <span style="font-size:13px;color:var(--m)">oppure incolla il percorso qui sotto</span>
  </div>
  <input type="text" id="cartella" placeholder="C:\Users\...\la mia cartella di archivio" value="__PRECOMPILATO__">
  <div id="navigatore" style="display:none"></div>
  <div class="riga2">
    <input type="text" id="etichetta" placeholder="come chiamarla (facoltativo)">
    <button onclick="avvia()">Indicizza</button>
  </div>
</div>
<div class="pannello" id="avanzamento" style="display:none">
  <h2>Indicizzazione in corso</h2>
  <div class="riga2" style="margin:4px 0 2px">
    <button type="button" id="bottoneFerma" onclick="fermaLavoro(this)" style="background:var(--m);padding:7px 13px;font-size:14px">Ferma</button>
    <span style="font-size:13px;color:var(--m)">quello che è già fatto resta: la prossima volta Aggiorna riprende da lì</span>
  </div>
  <div class="barra"><i id="barra"></i></div>
  <p id="messaggio">avvio…</p>
  <div class="diario" id="diario"></div>
</div>
<div class="pannello anteprima" id="anteprima" style="display:none"></div>
"""


def _forme_di(q, modo):
    """Le forme da cercare in una pagina per evidenziarla."""
    if not q.strip():
        return []
    if modo == "esatta":
        return [archivio.piatto(p) for p in re.findall(r"\w+", q, re.UNICODE)]
    return sorted({f for g in tesauro.gruppi(q) for f in g} | set(tesauro.espandi(q)))


def _pagina_del_punto(v, forme):
    """In quale pagina del PDF sta davvero la parola trovata.

    Un brano comincia a una pagina ma può finire in quella dopo: la pagina
    giusta è quella dell'ultimo segno di pagina prima della parola.
    """
    testo = v.get("testo") or ""
    scritte = (re.findall("\x02([^\x03]+)\x03", v.get("brano") or "")
               or archivio.forme_nel_testo(testo, forme))
    posti = [testo.find(x) for x in scritte if testo.find(x) >= 0]
    if not posti:
        return v.get("pagina") or 1
    segni = re.findall(r"\[\[pagina (\d+)\]\]", testo[:min(posti)])
    return int(segni[-1]) if segni else (v.get("pagina") or 1)


def _link_vedi(percorso, n, q, modo, vicino=True):
    return (f"/vedi?percorso={urllib.parse.quote(percorso)}&amp;n={n}"
            f"&amp;q={urllib.parse.quote(q)}&amp;modo={modo}" + ("&amp;vicino=1" if vicino else ""))


def _riga(v, query, modo="tesauro"):
    dove = _dove_o_brano(v["percorso"], v.get("pagina"), v.get("frammento"))
    pag = f"<span>{dove}</span>" if dove else ""
    copie = f'<span class="bollo">{v["copie"]} copie</span>' if v.get("copie", 1) > 1 else ""
    sem = ""
    if v.get("semantico"):
        come = "solo per senso" if not v.get("brano") else "anche per senso"
        sem = (f'<span class="bollo" title="trovato {come}, non per le parole">'
               f'affinità {v["semantico"]:.2f}</span>')
    # Il ritaglio di SQLite è centrato sulla parola trovata; per un risultato
    # solo semantico non c'è ritaglio, e allora si mostra l'inizio del brano.
    brano = (_ritaglio(v["brano"]) if v.get("brano")
             else _evidenzia((v.get("testo") or "")[:700], query) + "…")
    p = urllib.parse.quote(v["percorso"])
    # un PDF si apre sulla sua pagina, con la parola trovata evidenziata; gli
    # altri formati, che pagine non ne hanno, sul brano
    if v["percorso"].lower().endswith(".pdf"):
        titolo = _link_vedi(v["percorso"], _pagina_del_punto(v, _forme_di(query, modo)),
                            query, modo)
    elif v.get("frammento"):
        titolo = f'/brano?f={v["frammento"]}&amp;q={urllib.parse.quote(query)}'
    else:
        titolo = _link_file(v["percorso"], v.get("pagina"))
    contesto = ""
    if v.get("frammento"):
        contesto = (f'<a href="/brano?f={v["frammento"]}&amp;q={urllib.parse.quote(query)}">'
                    f'dov\'era</a>')
    # da un risultato si cita: la pagina si riapre e si rilegge guardandola, e
    # il brano trovato si confronta con quello che c’è scritto sulla carta
    cita = ""
    if v["percorso"].lower().endswith(".pdf") and v.get("pagina"):
        cita = (f'<a href="/cita?percorso={p}&amp;n={v["pagina"]}'
                f'&amp;brano={urllib.parse.quote((v.get("testo") or "")[:300])}'
                f'&amp;q={urllib.parse.quote(query)}&amp;modo={modo}">cita</a>')
    return f"""<div class="ris">
<div class="tit"><a href="{titolo}"{_scheda(titolo)}>{html.escape(v['nome'][:110])}</a></div>
<div class="meta"><span>{html.escape(v.get('radice') or '')}</span>{pag}
 <span>{_estensione(v['percorso'], v.get('pagine'))}</span><span>{v.get('metodo') or ''}</span>{copie}{sem}</div>
<div class="brano">{brano}</div>
<div class="azioni">{contesto} {cita}
 <a href="/lancia?percorso={p}" target="_blank">apri nel programma</a>
 <a href="/mostra?percorso={p}" target="_blank">mostra nella cartella</a>
 <span class="strada" title="{html.escape(v['percorso'])}">{html.escape(v['percorso'])}</span></div>
</div>"""


def _unisci(query, modo, limite=40, radice=None, gruppo=None):
    voci, indice = [], {}
    if modo in ("tesauro", "esatta", "tutto"):
        m = "esatta" if modo == "esatta" else "tesauro"
        for v in archivio.cerca(query, m, limite, radice=radice, gruppo=gruppo):
            indice[v["percorso"]] = v
            voci.append(v)
    if modo in ("semantica", "tutto"):
        for punteggio, fr, d in semantica.cerca(query, limite, radice=radice, gruppo=gruppo):
            if punteggio < 0.35:
                continue
            p = d["percorso"]
            if p in indice:
                indice[p]["semantico"] = max(indice[p].get("semantico", 0), punteggio)
                continue
            v = {"documento": d["id"], "frammento": fr,
                 "nome": d["nome"], "percorso": p,
                 "radice": d["radice"], "pagina": d["pagina"], "metodo": d["metodo"],
                 "pagine": d["pagine"], "parole": d["parole"], "testo": d["testo"],
                 "copie": 1, "semantico": punteggio}
            indice[p] = v
            voci.append(v)
    voci.sort(key=lambda v: -(v.get("semantico", 0) * 2 + (1 if v.get("brano") else 0)))
    return voci[:limite]


_STATO_SEM = {"quando": 0, "esito": None}


def stato_semantico():
    if _STATO_SEM["esito"] and time.time() - _STATO_SEM["quando"] < 30:
        return _STATO_SEM["esito"]
    _STATO_SEM["esito"] = _stato_semantico()
    _STATO_SEM["quando"] = time.time()
    return _STATO_SEM["esito"]


def _stato_semantico():
    """Se la ricerca semantica può funzionare, e se no perché.

    Una ricerca che non trova niente e non dice come mai è peggio di una che
    non c'è: fa credere che nell'archivio non ci sia nulla. I vettori si
    calcolano uno per frammento, e finché non ci sono tutti la semantica vede
    solo il pezzo di archivio che ne ha.

    L'esito resta buono mezzo minuto: chiedere a Ollama se è vivo costa fino a
    quattro secondi di attesa quando è spento, e sarebbero quattro secondi su
    ogni pagina.
    """
    if not semantica.acceso():
        return False, "semantica spenta: Ollama non risponde", (
            "<b>La ricerca semantica non può funzionare: Ollama non risponde.</b><br>"
            "Ollama è il programma che legge i testi per senso, e gira sul tuo "
            "computer. Chiudi Scaffale e riaprilo dall'icona: prova ad accenderlo "
            "da sé. Se non basta, Ollama non è installato — si prende da "
            "<code>ollama.com</code>. Intanto restano la ricerca esatta e quella "
            "per tesauro, che non hanno bisogno di niente.")
    radici = semantica.mancanti_per_radice()
    tutti = sum(r["tutti"] for r in radici)
    fatti = sum(r["fatti"] for r in radici)
    if not tutti:
        return True, "", ""                # archivio vuoto: non c'è niente da dire
    if fatti >= tutti * 0.98:
        return True, f"semantica pronta: {_numero(fatti)} frammenti", ""
    pronte = [r["radice"] for r in radici if r["tutti"] and r["fatti"] >= r["tutti"] * 0.98]
    quota = 100 * fatti / tutti
    if pronte:
        riga = f"semantica pronta per {', '.join(pronte[:2])} · {_percento(quota)} del totale"
    elif fatti == 0:
        riga = "semantica spenta: nessun vettore"
    else:
        riga = f"semantica parziale: {_percento(quota)} dell'archivio"

    al_secondo = semantica.velocita()
    vel = f"{al_secondo:.2f}".replace(".", ",")
    scelte = []
    for r in sorted(radici, key=lambda r: r["mancano"]):
        if r["mancano"] > 0:
            scelte.append(
                f'<button type="button" data-radice="{html.escape(r["radice"])}" '
                f'onclick="calcolaVettori(this)">Solo «{html.escape(r["radice"])}» — '
                f'{_circa(r["mancano"] / al_secondo)}</button>')
    if len(scelte) > 1:
        scelte.append(
            f'<button type="button" data-radice="" onclick="calcolaVettori(this)" '
            f'style="background:var(--m)">Tutto l\'archivio — '
            f'{_circa((tutti - fatti) / al_secondo)}</button>')
    return False, riga, (
        f"<b>La ricerca semantica vede solo {_numero(fatti)} frammenti su "
        f"{_numero(tutti)}</b> ({_percento(quota)}). "
        "Il resto non uscirà mai per affinità, per quanto sia pertinente.<br>"
        "Per vederlo bisogna calcolare i <i>vettori</i>: Scaffale fa leggere ogni "
        "frammento a Ollama, che ne ricava un'impronta del senso. Si fa una volta "
        "sola, le copie dei doppioni non si contano, e si può cominciare dalla "
        f"cartella che serve. Su questo computer va a {vel} frammenti al secondo "
        "— il computer resta usabile, ma la "
        "finestra nera di Scaffale va lasciata aperta: se la chiudi il calcolo si "
        "ferma, e la volta dopo riprende da dove era."
        f'<div class="riga2" style="margin-top:11px">{"".join(scelte)}</div>')


def _numero(n):
    return f"{n:,}".replace(",", ".")


def _percento(q):
    """0,2% e non 0.2%, né 0%: una cifra decimale finché serve."""
    return (f"{q:.1f}".replace(".", ",") if q < 10 else f"{q:.0f}") + "%"


def _circa(secondi):
    """Il tempo detto come lo direbbe una persona: «pochi secondi», «circa 5 minuti»."""
    if secondi < 20:
        return "pochi secondi"
    if secondi < 60:
        return "meno di un minuto"
    return f"circa {_durata(secondi)}"


def _durata(secondi):
    if secondi < 90:
        return "un minuto"
    if secondi < 150:
        return "un paio di minuti"
    if secondi < 3600:
        return f"{secondi/60:.0f} minuti"
    ore = secondi / 3600
    if ore < 1.25:
        return "un'ora"
    if ore < 1.75:
        return "un'ora e mezza"
    if ore < 36:
        return f"{ore:.0f} ore"
    return f"{ore/24:.1f} giorni".replace(".", ",")


def _quando(t):
    """Una data che si legge: «oggi alle 19:40», «ieri alle 9:05», «21 settembre»."""
    if not t:
        return "mai"
    giorno = time.localtime(t)
    oggi = time.localtime()
    if giorno[:3] == oggi[:3]:
        return time.strftime("oggi alle %H:%M", giorno)
    if time.localtime(time.time() - 86400)[:3] == giorno[:3]:
        return time.strftime("ieri alle %H:%M", giorno)
    mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
            "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    anno = f" {giorno.tm_year}" if giorno.tm_year != oggi.tm_year else ""
    return f"il {giorno.tm_mday} {mesi[giorno.tm_mon - 1]}{anno}"


def _scelta_dove(radice, elenco, gruppo=None):
    """Il menu «dove cercare», accanto alla casella di ricerca.

    Parte da dove ci si trova: dentro una cartella cerca in quella cartella,
    dentro un gruppo in quel gruppo, finché non si sceglie altro. Un gruppo si
    scrive «gruppo:12» nello stesso menu, così basta un comando solo.
    """
    voci = ['<option value="">in tutte le cartelle</option>']
    if gruppo:
        voci.append(f'<option value="gruppo:{gruppo["id"]}" selected>solo nel gruppo '
                    f'«{html.escape(gruppo["nome"][:50])}» di «{html.escape(gruppo["radice"])}»</option>')
    for r in elenco:
        nome = r["radice"] or ""
        scelto = " selected" if nome == radice and not gruppo else ""
        voci.append(f'<option value="{html.escape(nome)}"{scelto}>'
                    f'solo in «{html.escape(nome)}»</option>')
    return f'<select name="radice" class="dove" title="dove cercare">{"".join(voci)}</select>'


def _dove_per(radice="", gruppo=None):
    """Il menu «dove cercare» per una pagina che sta dentro una cartella o un gruppo."""
    elenco = archivio.radici()
    if not elenco:
        return ""
    g = biblioteca.gruppo(int(gruppo)) if gruppo else None
    return _scelta_dove(radice, elenco, g)


def _ultimo_esito(nome):
    """Che cosa ha trovato l'ultimo passaggio su questa cartella."""
    c = archivio.apri()
    r = c.execute("""SELECT stato, messaggio FROM lavori WHERE tipo='indicizza'
                     AND nome=? ORDER BY id DESC LIMIT 1""", (nome,)).fetchone()
    if not r:
        return ""
    if r["stato"] == "fermato":
        return ("l'ultima indicizzazione si è interrotta a metà: "
                "premi Aggiorna per completarla")
    if r["stato"] == "finito" and r["messaggio"] and "nuovi" in r["messaggio"]:
        return f"ultimo aggiornamento: {r['messaggio']}"
    return ""


def _pannello_cartelle(elenco):
    """Le cartelle già indicizzate, ciascuna con i suoi gesti: cercarci dentro e
    aggiornarla. È la prima cosa da vedere aprendo Scaffale: senza, chi ha già
    indicizzato non saprebbe più dove sta il suo lavoro."""
    if not elenco:
        return ""
    righe = []
    for r in elenco:
        nome = r["radice"] or ""
        n = html.escape(nome)
        q_nome = urllib.parse.quote(nome)
        dettagli = [f"{_numero(r['documenti'])} documenti",
                    f"aggiornata {_quando(r['aggiornata_il'])}"]
        if r["da_ocr"]:
            quante = "1 scansione" if r["da_ocr"] == 1 else f"{r['da_ocr']} scansioni"
            dettagli.append(f"<b>{quante} ancora da riconoscere</b>")
        esito = _ultimo_esito(nome)
        if r["esiste"]:
            aggiorna = (f'<button type="button" data-radice="{n}" '
                        f'onclick="aggiornaCartella(this)">Aggiorna</button>')
            apri = (f'<a href="/mostra_cartella?radice={q_nome}" target="_blank">'
                    f'apri in Esplora risorse</a>')
        else:
            aggiorna = ('<button type="button" disabled style="background:var(--m)" '
                        'title="la cartella non si trova">Aggiorna</button>')
            apri = '<span style="color:var(--a)">cartella non trovata sul disco</span>'
        nota = (f'<div class="meta" style="font-style:italic">{html.escape(esito)}</div>'
                if esito else "")
        righe.append(f"""<div class="cartella">
  <div class="nome"><a href="/cartella?radice={q_nome}">{n}</a></div>
  <div class="meta">{" · ".join(dettagli)}</div>
  <div class="strada" title="{html.escape(r['percorso'] or '')}">{html.escape(r['percorso'] or 'percorso sconosciuto')}</div>
  {nota}
  <div class="riga2" style="margin-top:8px">
    <a class="pulsante" href="/cartella?radice={q_nome}">Apri la scheda: file, numeri, gruppi, riassunti</a>
    <a class="pulsante secondario" href="/?radice={q_nome}">Cerca qui dentro</a>
    {aggiorna}
    <span class="azioni" style="margin:0">{apri}</span>
  </div>
</div>""")
    return f"""<div class="pannello" id="cartelleTue">
  <h2>Le tue cartelle</h2>
  <p>Clicca il nome, o <b>Apri la scheda</b>, per vedere che cosa c'è in una cartella:
  quanti file e di che tipo, come sono raggruppati, di che cosa parla ciascuno.
  <b>Cerca qui dentro</b> limita la ricerca a quella cartella. <b>Aggiorna</b>
  la rilegge: aggiunge i file nuovi, rilegge quelli che hai cambiato, toglie
  dall'indice quelli che hai cancellato. Quelli che non hai toccato non li
  rilegge, e le scansioni già riconosciute non le riconosce una seconda volta.</p>
  {"".join(righe)}
</div>"""


def _testata_gruppo(g):
    """In cima alla ricerca dentro un gruppo: quale, di che cartella, e le uscite."""
    q_rad = urllib.parse.quote(g["radice"])
    n = len(biblioteca.membri(g["id"]))
    return f"""<div class="pannello">
<h2>Nel gruppo «{html.escape(g["nome"])}»</h2>
<p style="color:var(--i)"><b>{_numero(n)} documenti</b> della cartella «{html.escape(g["radice"])}».
La ricerca guarda solo dentro questo gruppo, finché nel menu accanto alla casella non scegli altro.</p>
<p style="margin:0"><a class="pulsante" href="/cartella?radice={q_rad}&amp;gruppo={g["id"]}">Apri il gruppo</a>
<a href="/?radice={q_rad}" style="margin-left:12px;font-size:13px">cerca in tutta la cartella</a>
<a href="/" style="margin-left:12px;font-size:13px">cerca in tutte le cartelle</a></p>
</div>"""


def _testata_cartella(radice):
    """In cima alla ricerca dentro una cartella: che cosa c'è, e la porta per la scheda."""
    t = biblioteca.totali(radice)
    gruppi = biblioteca.gruppi_di(radice)
    quanti = {o: sum(1 for g in gruppi if g["origine"] == o) for o in ("tesauro", "scoperto", "mio")}
    tipi = ", ".join(f"{_numero(n)} {html.escape(k)}" for k, n in t["per_tipo"].most_common(4))
    q_rad = urllib.parse.quote(radice)
    return f"""<div class="pannello">
<h2>«{html.escape(radice)}»</h2>
<p style="color:var(--i)"><b>{_numero(t['documenti'])} documenti</b> ({tipi}) ·
{_numero(t['pdf_con_md'])} su {_numero(t['pdf'])} PDF con il .md · {_numero(t['con_copie'])} con copie ·
{quanti['tesauro']} temi, {quanti['scoperto']} gruppi scoperti, {quanti['mio']} gruppi tuoi ·
{_numero(t['riassunti'])} riassunti</p>
<p style="margin:0"><a class="pulsante" href="/cartella?radice={q_rad}">Apri la scheda della cartella</a>
<a href="/" style="margin-left:12px;font-size:13px">cerca in tutte le cartelle</a></p>
<p class="meta" style="margin:8px 0 0">Qui sotto la ricerca guarda solo dentro questa cartella.</p>
</div>"""


def _pagina(sotto, avvio="", spiega="", risultati="", piede="", q="", modo="tesauro",
            statosem="", avvisosem="", dove="", radice="", gruppo=None):
    # ogni pagina che sta dentro una cartella cerca lì, se non si sceglie altro
    if not dove:
        try:
            dove = _dove_per(radice, gruppo)
        except Exception:
            dove = ""
    return (PAGINA.replace("__STATOSEM__", statosem)
            .replace("__DOVE__", dove).replace("__MODO__", html.escape(modo))
            .replace("__AVVISOSEM__", avvisosem)
            .replace("__SOTTO__", sotto).replace("__AVVIO__", avvio)
            .replace("__Q__", html.escape(q)).replace("__SPIEGA__", spiega)
            .replace("__RISULTATI__", risultati).replace("__PIEDE__", piede)
            .replace("__C_T__", "checked" if modo == "tesauro" else "")
            .replace("__C_E__", "checked" if modo == "esatta" else "")
            .replace("__C_S__", "checked" if modo == "semantica" else "")
            .replace("__C_A__", "checked" if modo == "tutto" else ""))


@app.get("/", response_class=HTMLResponse)
def home(q: str = "", modo: str = "tesauro", radice: str = "", limite: int = 40):
    s = archivio.statistiche()
    elenco = archivio.radici()
    # «gruppo:12»: la ricerca dentro un gruppo, che sta in una cartella
    gruppo_g = None
    if radice.startswith("gruppo:"):
        try:
            gruppo_g = biblioteca.gruppo(int(radice.split(":", 1)[1]))
        except ValueError:
            gruppo_g = None
        radice = gruppo_g["radice"] if gruppo_g else ""
    gid = gruppo_g["id"] if gruppo_g else None
    # una cartella che non c'è più nell'archivio non si usa come filtro
    if radice and radice not in {r["radice"] for r in elenco}:
        radice, gruppo_g, gid = "", None, None
    scelta = f"gruppo:{gid}" if gid else radice
    dove = _scelta_dove(radice, elenco, gruppo_g) if elenco else ""
    sotto = (f"{s['documenti']:,} documenti · {s['parole']:,} parole · "
             f"{s['frammenti']:,} frammenti · {s['vettori']:,} vettori").replace(",", ".")
    pronta, riga_sem, avviso_sem = stato_semantico()
    statosem = (f'<a href="/?modo=semantica" title="che cosa serve alla ricerca per senso" '
                f'style="color:inherit">{riga_sem}</a>')
    # L'avviso compare quando la semantica è in ballo e non è in grado di
    # rispondere — è lì che il silenzio verrebbe scambiato per «non c'è nulla» —
    # e sulla pagina iniziale, perché chi non sa che cosa manca lo scopra.
    # Se i vettori si stanno già calcolando, al posto dell'avviso c'è la barra.
    corrente = archivio.lavoro()
    if (corrente and corrente["tipo"] == "vettori" and corrente["stato"] in IN_CORSO
            and not (_LAVORI.get(corrente["id"]) and _LAVORI[corrente["id"]].is_alive())):
        # rimasto «in corso» da una volta in cui Scaffale è stato chiuso a metà:
        # quel calcolo non gira più, e mostrare la barra sarebbe una bugia
        archivio.aggiorna_lavoro(corrente["id"], stato="fermato")
        corrente["stato"] = "fermato"
    if corrente and corrente["tipo"] == "vettori" and corrente["stato"] in IN_CORSO:
        avvisosem = (f'<div class="avviso" id="avvisoSem" data-lavoro="{corrente["id"]}">'
                     f'<b>Sto calcolando i vettori…</b></div>')
    elif avviso_sem and (modo in ("semantica", "tutto") or not q.strip()):
        avvisosem = f'<div class="avviso" id="avvisoSem">{avviso_sem}</div>'
    else:
        avvisosem = ""
    risultati, spiega = "", ""
    if q.strip():
        limite = max(10, min(limite, 500))
        voci = _unisci(q, modo, limite=limite, radice=radice or None, gruppo=gid)
        if voci:
            if gruppo_g:
                dentro = f' del gruppo «{html.escape(gruppo_g["nome"])}»'
            else:
                dentro = f' solo in «{html.escape(radice)}»' if radice else ''
            quanti = ""
            if modo != "semantica":
                totale = archivio.conta(q, "esatta" if modo == "esatta" else "tesauro",
                                        radice or None, gruppo=gid)
                altri = ""
                if totale > len(voci) and limite < 500:
                    base = (f"/?q={urllib.parse.quote(q)}&amp;modo={modo}"
                            f"&amp;radice={urllib.parse.quote(scelta)}")
                    altri = (f' — <a href="{base}&amp;limite={min(limite + 60, 500)}">'
                             f'mostrane altri</a>')
                if totale > len(voci):
                    quanti = (f"<b>{_numero(totale)} documenti</b>{dentro} contengono quello "
                              f"che cerchi: qui ne vedi {len(voci)}{altri}. ")
                else:
                    quanti = (f"<b>{_numero(len(voci))} documenti</b>{dentro} contengono quello "
                              f"che cerchi, e li vedi tutti. ")
            spiega = (f'<div class="spiega">{quanti}{tesauro.spiega(q, tesauri.nuclei_per(radice or None)) if modo != "semantica" else ""}</div>'
                      f'<div class="riga2" style="margin-bottom:16px">'
                      f'<button type="button" onclick="trascriviTrovati(this)">'
                      f'Crea i .md dei PDF trovati</button>'
                      f'<a href="/esporta?q={urllib.parse.quote(q)}&amp;modo={modo}&amp;radice={urllib.parse.quote(radice)}" '
                      f'style="font-size:13px;color:var(--m)">esporta questa ricerca</a>'
                      f'<span id="esitoMd" style="font-size:13px;color:var(--m)"></span></div>')
            risultati = "".join(_riga(v, q, modo) for v in voci)
            quanti_sem = sum(1 for v in voci if v.get("semantico"))
            if modo in ("semantica", "tutto"):
                spiega = spiega.replace(
                    "</div>", f" · {quanti_sem} per affinità</div>", 1)
        else:
            perche = ""
            if modo == "semantica" and not pronta:
                perche = " Ma qui la semantica non è in grado di rispondere: " \
                         "vedi l'avviso qui sopra, e prova intanto col tesauro."
            if gruppo_g:
                perche += (f' Stai cercando solo nel gruppo «{html.escape(gruppo_g["nome"])}»: prova '
                           f'<a href="/?q={urllib.parse.quote(q)}&amp;modo={modo}&amp;radice='
                           f'{urllib.parse.quote(radice)}">in tutta la cartella «{html.escape(radice)}»</a>'
                           f' o <a href="/?q={urllib.parse.quote(q)}&amp;modo={modo}">in tutte le cartelle</a>.')
            elif radice:
                perche += (f' Stai cercando solo in «{html.escape(radice)}»: prova '
                           f'<a href="/?q={urllib.parse.quote(q)}&amp;modo={modo}">in tutte le cartelle</a>.')
            risultati = f'<div class="vuoto">Nessun risultato.{perche}</div>'
    piede = " · ".join(f"{r['radice']}: {r['n']}" for r in s["radici"][:6])
    if s["da_ocr"]:
        piede += f" · <b>{s['da_ocr']} scansioni da riconoscere</b>"
    if s["copie"]:
        piede += f" · {s['copie']} gruppi di copie"
    # Aprendo Scaffale si vedono per prime le cartelle già indicizzate, con i
    # gesti per cercarci dentro e per aggiornarle. Il modulo per aggiungerne
    # una nuova resta sotto, chiuso: è un gesto che si ripete, ma non ogni volta.
    avvio = ""
    if gruppo_g:
        avvio = _testata_gruppo(gruppo_g)
    elif radice:
        avvio = _testata_cartella(radice)
    elif not q.strip():
        if s["documenti"] == 0:
            avvio = (AVVIO.replace("__TITOLO__", "Da dove cominciamo")
                     .replace("__SPIEGAZIONE__",
                              "Indica la cartella con i tuoi file. Scaffale entra in tutte "
                              "le sottocartelle, legge i documenti, riconosce le scansioni e "
                              "ricompone le cartelle di immagini che sono un testo solo.")
                     .replace("__PRECOMPILATO__", ""))
        else:
            modulo = (AVVIO.replace("__TITOLO__", "Indicizza un'altra cartella")
                      .replace("__SPIEGAZIONE__",
                               "Le cartelle si sommano nello stesso archivio. Se scegli una "
                               "cartella che c'è già, Scaffale la aggiorna.")
                      .replace("__PRECOMPILATO__", ""))
            # il pannello di avanzamento resta fuori dalla tendina chiusa:
            # serve anche quando si preme Aggiorna
            taglio = modulo.index('<div class="pannello" id="avanzamento"')
            avvio = (_pannello_cartelle(elenco)
                     + '<details class="aggiungi"><summary>+ Aggiungi un’altra cartella</summary>'
                     + modulo[:taglio] + "</details>" + modulo[taglio:])
        # se un'indicizzazione sta già girando, si vede subito la sua barra
        corrente_i = archivio.lavoro()
        if (corrente_i and corrente_i["tipo"] == "indicizza"
                and corrente_i["stato"] in IN_CORSO
                and _LAVORI.get(corrente_i["id"]) and _LAVORI[corrente_i["id"]].is_alive()):
            avvio = avvio.replace('id="avanzamento" style="display:none"',
                                  f'id="avanzamento" data-lavoro="{corrente_i["id"]}"')
    return _pagina(sotto, avvio, spiega, risultati, piede, q, modo, statosem, avvisosem, dove)


@app.get("/api/cerca")
def api_cerca(q: str, modo: str = "tesauro", limite: int = 40):
    return JSONResponse({"query": q, "modo": modo, "nuclei": tesauro.nuclei_di(q, tesauri.nuclei_per(None)),
                         "risultati": _unisci(q, modo, limite)})


@app.get("/vivo")
def vivo():
    """Risposta istantanea, senza toccare né l'archivio né Ollama: serve
    all'avvio per sapere quando aprire il browser, e se sulla porta c'è già
    Scaffale o un altro programma."""
    return JSONResponse({"scaffale": True})


@app.get("/api/stato")
def api_stato():
    s = archivio.statistiche()
    s["ollama"] = semantica.acceso()
    s["modelli"] = semantica.modelli()
    return JSONResponse(s)


def _noto(percorso):
    """Solo i file che stanno nell'indice: Scaffale non è un accesso al disco."""
    c = archivio.apri()
    return bool(c.execute("SELECT 1 FROM documenti WHERE percorso = ? LIMIT 1",
                          (percorso,)).fetchone())


TIPI = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8",
        ".md": "text/plain; charset=utf-8", ".htm": "text/html",
        ".html": "text/html", ".csv": "text/plain; charset=utf-8"}


@app.get("/apri")
def apri(percorso: str):
    if not _noto(percorso):
        return JSONResponse({"errore": "non è un documento dell'archivio"}, status_code=403)
    if not os.path.exists(percorso):
        return JSONResponse({"errore": "non trovato"}, status_code=404)
    e = os.path.splitext(percorso)[1].lower()
    # «inline» perché un PDF si legga nella scheda, alla pagina giusta, invece
    # di finire nella cartella dei download.
    return FileResponse(percorso, media_type=TIPI.get(e),
                        headers={"Content-Disposition":
                                 f'inline; filename="{urllib.parse.quote(os.path.basename(percorso))}"'}
                        if e in TIPI else None)


def _esito(titolo, dettaglio):
    """Una finestrella che dice che cosa è successo e si chiude da sola."""
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8">
<title>{html.escape(titolo)}</title>
<body style="font:15px/1.6 Georgia,serif;padding:40px;text-align:center;color:#2b2a27">
<p><b>{html.escape(titolo)}</b></p><p style="color:#77736c;font-size:13px">{html.escape(dettaglio)}</p>
<script>setTimeout(function(){{window.close()}},1400)</script></body>""")


@app.get("/lancia")
def lancia(percorso: str):
    """Apre il documento con il programma che gli appartiene: Word, Excel, Access.

    Scaffale gira sul computer di chi lo usa, quindi «aprire sul server» e
    «aprire qui» sono la stessa cosa. È l'unico modo di leggere davvero un .mdb
    o un .docx: nella scheda del browser sarebbero soltanto uno scaricamento.
    """
    if not _noto(percorso):
        return _esito("Non è un documento dell'archivio", percorso)
    if not os.path.exists(percorso):
        return _esito("Il file non c'è più", percorso)
    try:
        if sys.platform == "win32":
            os.startfile(percorso)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", percorso])
    except Exception as exc:
        return _esito("Non sono riuscito ad aprirlo", f"{type(exc).__name__}: {exc}")
    return _esito("Aperto nel suo programma", os.path.basename(percorso))


@app.get("/mostra")
def mostra(percorso: str):
    """Apre la cartella con il file già selezionato."""
    if not _noto(percorso):
        return _esito("Non è un documento dell'archivio", percorso)
    cartella = os.path.dirname(percorso)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(percorso)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", percorso])
        else:
            subprocess.Popen(["xdg-open", cartella])
    except Exception as exc:
        return _esito("Non sono riuscito ad aprire la cartella", str(exc))
    return _esito("Cartella aperta", cartella)


@app.get("/brano", response_class=HTMLResponse)
def brano(f: int, q: str = ""):
    """Da dove viene il brano: il frammento intero, in mezzo ai suoi vicini."""
    d = archivio.frammento(f)
    if not d:
        return _pagina("", risultati='<div class="vuoto">Brano non trovato.</div>')
    v = d["f"]
    dove = _dove(v["percorso"], v["pagina"])
    testa = f"{dove} · " if dove else ""
    vicini = []
    if d["prima"]:
        vicini.append(f'<a href="/brano?f={d["prima"]}&amp;q={urllib.parse.quote(q)}">'
                      f'&larr; il brano precedente</a>')
    if d["dopo"]:
        vicini.append(f'<a href="/brano?f={d["dopo"]}&amp;q={urllib.parse.quote(q)}">'
                      f'il brano seguente &rarr;</a>')
    p = urllib.parse.quote(v["percorso"])
    corpo = f"""<div class="ris" style="border:0">
<div class="tit"><a href="{_link_file(v['percorso'], v['pagina'])}" target="_blank">{html.escape(v['nome'])}</a></div>
<div class="meta"><span>{html.escape(v['radice'] or '')}</span>
 <span>{testa}brano {d['quale']} di {d['quanti']}</span>
 <span>{_estensione(v['percorso'], v['pagine'])}</span><span>{html.escape(v['metodo'] or '')}</span></div>
<div class="avviso">Questo è il testo come Scaffale l'ha letto, per intero e senza tagli.
 <b>Una lettura automatica sbaglia, e sbaglia sui numeri</b>: date, cifre, numeri romani.
 Prima di citarlo, apri l'originale{f' a {dove}' if dove else ''} e controlla.{'' if dove else
 ' Questo formato non ha pagine: per ritrovare il punto, apri il documento nel suo programma e cerca una frase del brano.'}</div>
<div class="brano" style="white-space:pre-wrap">{_evidenzia(v['testo'] or '', q) if q else html.escape(v['testo'] or '')}</div>
<div class="azioni">{' '.join(vicini)}
 <a href="/lancia?percorso={p}" target="_blank">apri nel programma</a>
 <a href="/mostra?percorso={p}" target="_blank">mostra nella cartella</a>
 <a href="/?q={urllib.parse.quote(q)}">torna alla ricerca</a></div>
<div class="azioni"><span class="strada">{html.escape(v['percorso'])}</span></div>
</div>"""
    return _pagina(f"da dove viene il brano · {html.escape(v['nome'][:70])}",
                   risultati=corpo, q=q, radice=v.get("radice") or "")


# ------------------------------------------------ indicizzazione dall'app ---

_LAVORI = {}


def _in_fondo(id_lavoro, cartella, nome, ocr):
    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])
    try:
        archivio.indicizza(cartella, radice=nome or None, ocr=ocr,
                           avviso=riferisci, id_lavoro=id_lavoro)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore",
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200],
                                 finito=__import__("time").time())
    else:
        # letti i file, la cartella si analizza da sola — temi, gruppi, parole
        # caratteristiche — così la sua scheda è pronta senza premere niente
        try:
            radice = archivio._nome_di(archivio.apri(), cartella) or nome
            # se l'aggiornamento non ha trovato niente di nuovo, cambiato o
            # tolto, i temi e i gruppi di prima valgono ancora: non si rifanno
            esito = (archivio.lavoro(id_lavoro) or {}).get("messaggio") or ""
            conti = re.search(r"(\d+) nuovi, (\d+) cambiati, (\d+) tolti", esito)
            gia_fatta = biblioteca.totali(radice).get("analizzata_il")
            if conti and gia_fatta and not any(int(n) for n in conti.groups()):
                return
            id_analisi = archivio.nuovo_lavoro("analizza", "", radice)
            _LAVORI[id_analisi] = threading.current_thread()
            biblioteca.analizza(radice, avviso=lambda riga: None, id_lavoro=id_analisi)
        except Exception as exc:
            archivio.aggiorna_lavoro(id_lavoro, riga=f"analisi non riuscita: {exc}"[:200])
    finally:
        # cartelle e frammenti sono cambiati: l'avviso sulla semantica, che
        # elenca le cartelle con i loro tempi, va ricalcolato subito
        _STATO_SEM["esito"] = None


@app.post("/indicizza")
def avvia_indicizzazione(dati: dict):
    cartella = (dati.get("cartella") or "").strip().strip('"')
    if not cartella or not os.path.isdir(cartella):
        return JSONResponse({"errore": f"Cartella non trovata: {cartella}"})
    # come per Aggiorna: l'analisi della cartella di prima la si aspetta, e se
    # c'è un altro lavoro lo si dice per nome — non sempre è un'indicizzazione
    errore = _occupato()
    if errore:
        corrente = archivio.lavoro()
        return JSONResponse({"errore": errore, "lavoro": corrente["id"] if corrente else None})
    nome = (dati.get("nome") or "").strip() or os.path.basename(cartella.rstrip("\\/"))
    # la stessa cartella scelta una seconda volta è un aggiornamento, e tiene il
    # suo nome: altrimenti i file nuovi finirebbero sotto un'etichetta diversa
    # da quelli vecchi, e la cartella si spezzerebbe in due
    for r in archivio.radici():
        if r["percorso"] and _stesso_percorso(r["percorso"], cartella):
            nome = r["radice"]
            break
    id_lavoro = archivio.nuovo_lavoro("indicizza", cartella, nome)
    t = threading.Thread(target=_in_fondo, daemon=True,
                         args=(id_lavoro, cartella, nome, bool(dati.get("ocr", True))))
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro, "cartella": cartella, "nome": nome})


def _stesso_percorso(a, b):
    norma = lambda p: os.path.normcase(os.path.abspath(p)).rstrip("\\/")
    return norma(a) == norma(b)


def _occupato():
    """Un lavoro sta già girando? Allora non se ne avvia un secondo: due
    scritture insieme sulla stessa base dati si bloccano a vicenda.

    L'analisi di una cartella, che parte da sola dopo averla letta, dura pochi
    secondi: quella la si aspetta, invece di rispondere «riprova».
    """
    corrente = archivio.lavoro()
    if corrente and corrente["tipo"] == "analizza" and corrente["stato"] in IN_CORSO:
        vivo = _LAVORI.get(corrente["id"])
        if vivo and vivo.is_alive() and vivo is not threading.current_thread():
            vivo.join(timeout=120)
        corrente = archivio.lavoro()
    if not corrente or corrente["stato"] not in IN_CORSO:
        return None
    vivo = _LAVORI.get(corrente["id"])
    if vivo and vivo.is_alive():
        if corrente["tipo"] == "vettori":
            return ("Sto calcolando i vettori per la ricerca semantica. Aspetta che "
                    "finisca, oppure fermalo con il suo pulsante: la volta dopo riprende "
                    "da dove era.")
        if corrente["tipo"] == "analizza":
            return (f"Sto analizzando la cartella «{corrente.get('nome') or ''}»: in una "
                    "cartella grande ci vuole qualche minuto. Riprova quando ha finito, oppure "
                    "fermala con il suo pulsante.")
        if corrente["tipo"] == "riassunti":
            return ("Sto scrivendo i riassunti. Aspetta che finisca, oppure fermalo dalla "
                    "scheda della cartella: quelli fatti restano.")
        if corrente["tipo"] == "temi":
            return ("Il modello sta leggendo una cartella per proporne i temi. Aspetta che "
                    "finisca, oppure fermalo dalla scheda di quella cartella.")
        if corrente["tipo"] == "trascrivi":
            return "Sto creando dei file .md: aspetta che finisca, oppure fermalo."
        if corrente["tipo"] == "domanda":
            return ("Il modello sta rispondendo a un'altra domanda: qualche minuto. Riprova "
                    "quando ha finito, oppure fermala dalla pagina delle domande.")
        if corrente["tipo"] == "sistema":
            return (f"Sto sistemando la cartella «{corrente.get('nome') or ''}»: .md, analisi, "
                    "riassunti. Aspetta che finisca, oppure fermalo dalla scheda di quella cartella.")
        return "C'è già un'indicizzazione in corso: aspetta che finisca."
    archivio.aggiorna_lavoro(corrente["id"], stato="fermato")
    return None


def _peso(byte):
    if byte >= 1e9:
        return f"{byte / 1e9:.1f} GB".replace(".", ",")
    return f"{max(byte / 1e6, 0.1):.0f} MB" if byte >= 1e6 else f"{byte / 1e3:.0f} kB"


def _riquadro_anteprima(a, nome, aggiornamento):
    """Il riquadro che si vede prima di cominciare: che cosa c'è, che cosa
    cambia, quanto ci vuole, e le scelte. Scritto qui e non nel browser,
    perché è testo — e il testo, in Python, non rompe niente."""
    e = html.escape
    breve = nome or os.path.basename(a["percorso"].rstrip("\\/"))
    titolo = (f"Aggiornare «{e(breve)}»?" if aggiornamento
              else f"Prima di cominciare: «{e(breve)}»")
    tipi = sorted(a["per_tipo"].items(), key=lambda x: -x[1])
    elenco_tipi = " · ".join(f"{_numero(n)} {e(t)}" for t, n in tipi[:7])
    if len(tipi) > 7:
        elenco_tipi += f" · {_numero(sum(n for _, n in tipi[7:]))} di altri tipi"
    righe = [f"<li>Nella cartella ci sono <b>{_numero(a['totale'])} documenti</b> "
             f"({_peso(a['byte'])}), sottocartelle comprese: {elenco_tipi}.</li>"]
    if a["nome"]:
        cancellati = f"<b>{_numero(a['tolti'])} cancellati</b>, " if a["tolti"] else ""
        righe.append(f"<li>Rispetto all'ultima volta: <b>{_numero(a['nuovi'])} nuovi</b>, "
                     f"<b>{_numero(a['cambiati'])} cambiati</b>, {cancellati}"
                     f"{_numero(a['invariati'])} invariati, che non si rileggono.</li>")
    else:
        righe.append("<li>È una cartella nuova: si leggono tutti.</li>")
    parti_ocr = []
    if a["scansioni_in_attesa"]:
        parti_ocr.append(f"{_numero(a['scansioni_in_attesa'])} già in attesa dall'ultima volta")
    if a["scansioni_nuove"]:
        if a["pdf_aperti"] < a["pdf_da_leggere"]:
            parti_ocr.append(f"circa {_numero(a['scansioni_nuove'])} fra i PDF da leggere "
                             f"(è una stima: ne ho aperti {a['pdf_aperti']} su "
                             f"{_numero(a['pdf_da_leggere'])})")
        else:
            parti_ocr.append(f"{_numero(a['scansioni_nuove'])} fra i PDF da leggere "
                             f"(li ho aperti tutti)")
    if a["immagini"]:
        parti_ocr.append(f"{_numero(a['immagini'])} immagini da ricomporre in documenti")
    if parti_ocr:
        righe.append(f"<li>Scansioni da riconoscere: {'; '.join(parti_ocr)} — in tutto "
                     f"circa <b>{_numero(a['pagine_ocr'])} pagine</b>.</li>")
    else:
        righe.append("<li>Nessuna scansione da riconoscere: tutti i documenti hanno già il testo.</li>")
    if a["illeggibili"]:
        righe.append(f"<li>{len(a['illeggibili'])} sottocartelle non si sono potute aprire: "
                     "quello che contengono resta com'è.</li>")

    t_testo, t_ocr = a["secondi_testo"], a["secondi_ocr"]
    niente_da_leggere = a["da_leggere"] == 0 and a["tolti"] == 0
    def bottone(testo, ocr, nota="", secondario=False):
        stile = ' style="background:var(--i)"' if secondario else ""
        spiega = f"<span>{nota}</span>" if nota else ""
        return (f'<div><button type="button" data-ocr="{1 if ocr else 0}" '
                f'onclick="scegli(this)"{stile}>{testo}</button>{spiega}</div>')
    annulla = ('<div><button type="button" data-annulla="1" onclick="scegli(this)" '
               'style="background:transparent;color:var(--m);border:1px solid var(--b)">'
               'Annulla</button></div>')
    scelte = []
    if niente_da_leggere and not a["pagine_ocr"]:
        domanda = "Non è cambiato niente dall'ultima volta: non c'è niente da fare."
        scelte.append('<div><button type="button" data-annulla="1" onclick="scegli(this)">'
                      'Va bene</button></div>')
    elif niente_da_leggere:
        domanda = ("Non ci sono file nuovi né cambiati. Restano però delle scansioni "
                   "da riconoscere.")
        scelte.append(bottone(f"Riconosci le scansioni — {_circa(t_ocr)}", True,
                              "si può fermare quando vuoi con Ferma"))
        scelte.append(annulla)
    elif a["pagine_ocr"]:
        domanda = "Che cosa faccio?"
        scelte.append(bottone(f"Solo i testi — {_circa(t_testo)}", False,
                              "le scansioni restano in attesa: le riconosci quando vuoi, "
                              "con Aggiorna", secondario=True))
        scelte.append(bottone(f"Tutto, anche le scansioni — {_circa(t_testo + t_ocr)}",
                              True, "si può fermare quando vuoi con Ferma: "
                                    "quello che è fatto resta"))
        scelte.append(annulla)
    else:
        domanda = "Comincio?"
        scelte.append(bottone(f"Sì, indicizza — {_circa(t_testo)}", False))
        scelte.append(annulla)
    v = archivio.velocita()
    cifra = lambda x, d: f"{x:.{d}f}".replace(".", ",")
    nota = (f"Le stime vengono dai tempi misurati su questo computer: {cifra(v['pdf'], 2)} "
            f"secondi per leggere un PDF, {cifra(v['testo'], 3)} per un file di altro tipo, "
            f"{cifra(v['ocr'], 1)} per riconoscere una pagina scansionata. Poi, per la "
            "ricerca semantica, servono i vettori: si calcolano a parte.")
    return (f"<h2>{titolo}</h2><ul>{''.join(righe)}</ul>"
            f"<p style='margin:10px 0 0;color:var(--i)'><b>{domanda}</b></p>"
            f"<div class='scelte'>{''.join(scelte)}</div>"
            f"<p style='font-size:12.5px;margin:10px 0 0'>{nota}</p>")


@app.post("/anteprima")
def anteprima(dati: dict):
    """Conta prima di cominciare, e lascia decidere. Funzione normale e non
    asincrona: l'anteprima apre dei file, e così gira a parte senza fermare
    il resto dell'app mentre lavora."""
    radice = (dati.get("radice") or "").strip()
    nome = (dati.get("nome") or "").strip()
    if radice:
        voce = next((r for r in archivio.radici() if r["radice"] == radice), None)
        if not voce:
            return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
        if not voce["esiste"]:
            return JSONResponse({"errore": "La cartella non si trova più sul disco: "
                                           f"{voce['percorso']}."})
        cartella = voce["percorso"]
    else:
        cartella = (dati.get("cartella") or "").strip().strip('"')
        if not cartella or not os.path.isdir(cartella):
            return JSONResponse({"errore": f"Cartella non trovata: {cartella}"})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    a = archivio.anteprima(cartella)
    nome = radice or a["nome"] or nome
    return JSONResponse({"html": _riquadro_anteprima(a, nome, bool(radice or a["nome"])),
                         "cartella": cartella, "nome": nome})


@app.post("/ferma")
def ferma_lavoro(dati: dict):
    """Il pulsante Ferma: il lavoro si chiude da sé al primo punto sicuro."""
    id_lavoro = int(dati.get("lavoro") or 0)
    if id_lavoro:
        archivio.ferma(id_lavoro)
    return JSONResponse({"ok": True})


# ------------------------------------------------------ spegnere Scaffale ---

_SCHEDE = {}                                   # scheda del browser -> ultimo segno
SILENZIO_SCHEDA = 3 * 3600                     # secondi senza battito: scheda data per chiusa
# ultimo: l'ultima richiesta di qualunque tipo; in_volo: quante se ne stanno servendo
_VITA = {"avvio": time.time(), "ultimo": time.time(), "in_volo": 0,
         "scheda_vista": False, "avvisato": False}


@app.middleware("http")
async def _segni_di_vita(request, call_next):
    """Ogni richiesta è un segno di vita: mentre una pagina si sta preparando —
    la scheda di una cartella grande chiede qualche secondo — Scaffale non si
    spegne sotto i piedi di chi l'ha chiesta."""
    _VITA["in_volo"] += 1
    _VITA["ultimo"] = time.time()
    try:
        return await call_next(request)
    finally:
        _VITA["in_volo"] -= 1
        _VITA["ultimo"] = time.time()


def _che_lavoro(tipo):
    return {"indicizza": "l'indicizzazione", "vettori": "il calcolo dei vettori",
            "trascrivi": "la creazione dei .md", "analizza": "l'analisi della cartella",
            "riassunti": "i riassunti", "sistema": "la sistemazione della cartella"
            }.get(tipo, "il lavoro in corso")


def _lavoro_vivo():
    return any(t.is_alive() for t in _LAVORI.values())


def _spegni(perche):
    print(f"\n  {perche}", flush=True)
    print("  Tutto quello che hai fatto è salvato. Questa finestra si chiude.", flush=True)
    os._exit(0)


@app.post("/battito")
def battito(scheda: str = ""):
    _SCHEDE[scheda or "?"] = time.time()
    _VITA["scheda_vista"] = True
    return JSONResponse({"ok": True, "schede": len(_SCHEDE)})


@app.post("/addio")
def addio(scheda: str = ""):
    """La scheda si chiude, o passa a un'altra pagina: se è un'altra pagina di
    Scaffale, il suo battito arriva subito dopo."""
    _SCHEDE.pop(scheda, None)
    _VITA["ultimo"] = time.time()
    return JSONResponse({"ok": True})


def _guardiano():
    """Spegne Scaffale quando nessuna scheda è più aperta.

    Cinque secondi dopo l'ultima scheda chiusa, se non ne arrivano altre e non
    c'è nessuna richiesta a metà. Una scheda che tace da due minuti e mezzo —
    il browser chiuso senza salutare — conta come chiusa. Se sta girando un
    lavoro, lo si lascia finire e lo si dice nella finestra nera: chiudere il
    browser di sera non deve fermare i riassunti lasciati per la notte.
    """
    prima = time.time()
    while True:
        time.sleep(2)
        ora = time.time()
        if ora - prima > 30:
            # il computer si è addormentato: al risveglio le schede non hanno
            # colpa se tacevano, e hanno tempo di rifarsi vive
            for k in list(_SCHEDE):
                _SCHEDE[k] = ora
            _VITA["ultimo"] = ora
        prima = ora
        # una scheda chiusa lo dice (/addio); una che tace soltanto è quasi sempre
        # una scheda messa a dormire dal browser (Edge e Chrome lo fanno con quelle
        # dietro le altre), non chiusa: la si dà per chiusa solo dopo tre ore
        for k, t in list(_SCHEDE.items()):
            if ora - t > SILENZIO_SCHEDA:
                _SCHEDE.pop(k, None)
        if _SCHEDE or _VITA["in_volo"] > 0:
            _VITA["avvisato"] = False
            continue
        if _lavoro_vivo():
            if _VITA["scheda_vista"] and not _VITA["avvisato"]:
                l = archivio.lavoro() or {}
                print(f"\n  Le pagine di Scaffale nel browser sono state chiuse. Finisco "
                      f"{_che_lavoro(l.get('tipo'))} e poi mi chiudo da solo.\n  Se vuoi fermare "
                      "tutto subito, chiudi questa finestra: quello che è fatto resta.\n  Se invece "
                      "vuoi continuare, riapri Scaffale dall'icona.", flush=True)
                _VITA["avvisato"] = True
            continue
        if _VITA["scheda_vista"]:
            if ora - _VITA["ultimo"] > 5:
                _spegni("Hai chiuso Scaffale nel browser: mi spengo.")
        elif ora - _VITA["avvio"] > 240:
            # il browser non si è mai fatto vivo
            _spegni("Il browser non si è aperto: mi spengo. Riapri Scaffale dall'icona.")


@app.on_event("startup")
def _all_avvio():
    if os.environ.get("SCAFFALE_SPEGNI_DA_SOLO") == "1":
        threading.Thread(target=_guardiano, daemon=True).start()


@app.post("/spegni")
def spegni(dati: dict = None):
    """Il pulsante Chiudi Scaffale: spegne il programma, e con lui la finestra nera."""
    forza = bool((dati or {}).get("forza"))
    vivi = [(i, t) for i, t in _LAVORI.items() if t.is_alive()]
    if vivi and not forza:
        l = archivio.lavoro(vivi[-1][0]) or {}
        return JSONResponse({"lavoro_in_corso": f"È in corso {_che_lavoro(l.get('tipo'))}."})

    def chiudi():
        time.sleep(0.6)                        # il tempo di rispondere alla pagina
        for i, t in vivi:
            archivio.ferma(i)
        for i, t in vivi:
            t.join(timeout=60)                 # si fermano al primo punto sicuro
        _spegni("Scaffale è stato chiuso con il pulsante «Chiudi Scaffale».")

    threading.Thread(target=chiudi, daemon=True).start()
    return JSONResponse({"spento": True})


@app.post("/aggiorna")
def aggiorna_cartella(dati: dict):
    """Rilegge una cartella già indicizzata: file nuovi, cambiati, cancellati."""
    nome = (dati.get("radice") or "").strip()
    voce = next((r for r in archivio.radici() if r["radice"] == nome), None)
    if not voce:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    if not voce["esiste"]:
        return JSONResponse({"errore": "La cartella non si trova più sul disco: "
                                       f"{voce['percorso']}. Se l'hai spostata, "
                                       "indicizzala di nuovo dal suo posto nuovo."})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    id_lavoro = archivio.nuovo_lavoro("indicizza", voce["percorso"], nome)
    t = threading.Thread(target=_in_fondo, daemon=True,
                         args=(id_lavoro, voce["percorso"], nome, bool(dati.get("ocr", True))))
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro, "cartella": voce["percorso"], "nome": nome})


@app.get("/mostra_cartella")
def mostra_cartella(radice: str):
    """Apre in Esplora risorse una cartella indicizzata."""
    voce = next((r for r in archivio.radici() if r["radice"] == radice), None)
    if not voce or not voce["esiste"]:
        return _esito("Cartella non trovata", voce["percorso"] if voce else radice)
    try:
        if sys.platform == "win32":
            os.startfile(voce["percorso"])
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open",
                              voce["percorso"]])
    except Exception as exc:
        return _esito("Non sono riuscito ad aprire la cartella", str(exc))
    return _esito("Cartella aperta", voce["percorso"])


def _vettori_in_fondo(id_lavoro, radice=None):
    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])
    try:
        fatti = semantica.calcola(avviso=riferisci, id_lavoro=id_lavoro, radice=radice)
        quanti = f"{fatti:,}".replace(",", ".")
        if archivio.da_fermare(id_lavoro):
            archivio.aggiorna_lavoro(id_lavoro, stato="fermato", finito=time.time(),
                                     messaggio=f"fermato: {quanti} vettori calcolati, "
                                               "gli altri la prossima volta")
        else:
            archivio.aggiorna_lavoro(id_lavoro, stato="finito", finito=time.time(),
                                     messaggio=f"{quanti} vettori calcolati")
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])
    _STATO_SEM["esito"] = None      # lo stato mostrato va ricalcolato


@app.post("/vettori")
def avvia_vettori(dati: dict = None):
    """Il pulsante che rende possibile la ricerca semantica.

    Calcolare i vettori è la parte lunga, e finora si faceva solo dal terminale:
    per chi non ci lavora è come se non esistesse. Parte da qui, in sottofondo,
    con la sua barra; si interrompe chiudendo Scaffale e riprende da dove era.
    """
    if not semantica.acceso():
        return JSONResponse({"errore": "Ollama non risponde. Avvialo e riprova."})
    corrente = archivio.lavoro()
    if corrente and corrente["stato"] in IN_CORSO:
        vivo = _LAVORI.get(corrente["id"])
        if vivo and vivo.is_alive():
            if corrente["tipo"] == "vettori":
                return JSONResponse({"lavoro": corrente["id"]})     # si riaggancia
            return JSONResponse({"errore": "C'è già un altro lavoro in corso: "
                                           "aspetta che finisca."})
        archivio.aggiorna_lavoro(corrente["id"], stato="fermato")
    radice = ((dati or {}).get("radice") or "").strip() or None
    id_lavoro = archivio.nuovo_lavoro("vettori", "", radice or "tutto l'archivio")
    t = threading.Thread(target=_vettori_in_fondo, args=(id_lavoro, radice), daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro})


@app.get("/api/lavoro")
def api_lavoro(id: int = 0):
    return JSONResponse(archivio.lavoro(id or None))


@app.get("/cartelle", response_class=HTMLResponse)
def pagina_cartelle():
    # è la stessa cosa che si vede aprendo Scaffale: una pagina iniziale con
    # le cartelle, e il modulo per aggiungerne. Due versioni diverse della
    # stessa lista finirebbero per dire cose diverse.
    return home()


def _md_di(percorso):
    """Il .md di un PDF: accanto, in una sottocartella markdown, o con lo stesso
    nome nella sua cartella (coppie.py). Accanto, se non ce n'è nessuno: è lì che
    si scrive quello nuovo."""
    return coppie.md_di(percorso) or os.path.splitext(percorso)[0] + ".md"


def _ha_md(percorso):
    return os.path.exists(_md_di(percorso))


@app.get("/vedi", response_class=HTMLResponse)
def vedi(percorso: str, n: int = 1, q: str = "", modo: str = "tesauro", vicino: int = 0):
    """La pagina del PDF dove sta la parola trovata, con la parola evidenziata.

    Il lettore di PDF del browser apre la pagina giusta, ma non sa che cosa si
    stava cercando: la parola va trovata a occhio. Qui la pagina è disegnata da
    Scaffale, con la parola in giallo e un segno rosso a fianco.
    """
    if not _noto(percorso) or not os.path.exists(percorso):
        return _pagina("", risultati='<div class="vuoto">Questo documento non è '
                                     'nell’archivio, o non si trova più sul disco.</div>')
    forme = _forme_di(q, modo)
    d = estrattori._apri(percorso)
    try:
        tot = d.page_count
        n = max(1, min(n, tot))

        def colpi(i):
            pg = d[i - 1]
            testo = pg.get_text()
            scritte = archivio.forme_nel_testo(testo, forme)
            return testo, scritte, [r for x in scritte for r in pg.search_for(x)], pg.rect.height

        testo, scritte, rett, altezza = colpi(n)
        # dal risultato di una ricerca: se la parola non è su questa pagina ma su
        # quella accanto — un brano può stare a cavallo di due pagine — ci si va
        if vicino and forme and not rett:
            for m in (n + 1, n - 1, n + 2):
                if 1 <= m <= tot:
                    alt = colpi(m)
                    if alt[2]:
                        n, (testo, scritte, rett, altezza) = m, alt
                        break
    finally:
        d.close()
    muta = len(testo.strip()) < 20
    e = html.escape
    nome = os.path.basename(percorso)
    qq = urllib.parse.quote(q)
    if rett:
        volte = "volta" if len(rett) == 1 else "volte"
        nota = (f"Qui la ricerca ha trovato <b>«{e('», «'.join(scritte))}»</b>: "
                f"{len(rett)} {volte} in questa pagina, in giallo. Il segno rosso a "
                "sinistra indica la prima.")
    elif muta:
        c = archivio.apri()
        doc = c.execute("SELECT id FROM documenti WHERE percorso=?", (percorso,)).fetchone()
        fr = c.execute("""SELECT id FROM frammenti WHERE documento=? AND pagina<=?
                          ORDER BY pagina DESC, ordine LIMIT 1""",
                       (doc["id"] if doc else -1, n)).fetchone()
        brano = (f' <a href="/brano?f={fr["id"]}&amp;q={qq}">Leggi il testo riconosciuto '
                 f'di questa parte</a>.' if fr else "")
        nota = ("Questa pagina è una <b>scansione</b>: dentro il PDF c’è solo l’immagine, "
                "senza testo, e Scaffale non può evidenziarci sopra la parola. Il testo "
                "riconosciuto dall’OCR, con la parola in evidenza, è nel brano." + brano)
    elif forme:
        nota = ("In questa pagina la parola non c’è. Guarda quelle vicine, con le "
                "frecce qui sotto.")
    else:
        nota = ""

    def vai(m, testo_link):
        if not 1 <= m <= tot:
            return ""
        return f'<a href="{_link_vedi(percorso, m, q, modo, vicino=False)}">{testo_link}</a>'

    segno = ""
    if rett:
        alto = 100 * min(r.y0 for r in rett) / (altezza or 1)
        segno = f'<div id="qui" style="top:calc({alto:.2f}% - 6px)"></div>'
    al_caricamento = ('var s=document.getElementById("qui");'
                      'if(s){s.scrollIntoView({block:"center"});}')
    avviso = f'<div class="avviso">{nota}</div>' if nota else ""
    p = urllib.parse.quote(percorso)
    corpo = f"""<div class="ris" style="border:0">
<div class="tit">{e(nome)}</div>
<div class="meta"><span>pagina <b>{n}</b> di {tot}</span><span class="strada">{e(percorso)}</span></div>
{avviso}
<div class="azioni">{vai(n - 1, "&larr; pagina prima")} {vai(n + 1, "pagina dopo &rarr;")}
 <form action="/vedi" method="get" style="display:inline;margin:0">
  <input type="hidden" name="percorso" value="{e(percorso)}"><input type="hidden" name="q" value="{e(q)}">
  <input type="hidden" name="modo" value="{e(modo)}">
  vai a pagina <input type="number" name="n" min="1" max="{tot}" value="{n}" style="width:70px"></form>
 <a href="/cita?percorso={p}&amp;n={n}&amp;q={qq}&amp;modo={e(modo)}">cita questo passo</a>
 <a href="{_link_file(percorso, n)}" target="_blank">apri il PDF intero a questa pagina</a>
 <a href="/lancia?percorso={p}" target="_blank">apri nel programma</a>
 <a href="/mostra?percorso={p}" target="_blank">mostra nella cartella</a></div>
<div class="foglio">{segno}<img alt="pagina {n}" onload='{al_caricamento}'
 src="/pagina.png?percorso={p}&amp;n={n}&amp;q={qq}&amp;modo={e(modo)}"></div>
<div class="azioni">{vai(n - 1, "&larr; pagina prima")} {vai(n + 1, "pagina dopo &rarr;")}</div>
</div>"""
    r_ = archivio.apri().execute("SELECT radice FROM documenti WHERE percorso=?", (percorso,)).fetchone()
    return _pagina(f"{e(nome[:70])} · pagina {n} di {tot}", risultati=corpo, q=q, modo=modo,
                   radice=(r_["radice"] if r_ else "") or "")


@app.get("/pagina.png")
def pagina_png(percorso: str, n: int = 1, q: str = "", modo: str = "tesauro"):
    """Una pagina del PDF come immagine, con le parole cercate evidenziate.

    L'evidenziatura si fa su una copia in memoria: il file sul disco non
    viene toccato.
    """
    if not _noto(percorso) or not os.path.exists(percorso):
        return Response(status_code=404)
    forme = _forme_di(q, modo)
    d = estrattori._apri(percorso)
    try:
        pg = d[max(1, min(n, d.page_count)) - 1]
        try:
            for x in archivio.forme_nel_testo(pg.get_text(), forme):
                for r in pg.search_for(x):
                    a = pg.add_highlight_annot(r)
                    a.set_colors(stroke=(1.0, 0.82, 0.25))
                    a.update()
        except Exception:
            pass                     # un PDF protetto: si mostra la pagina, senza giallo
        png = pg.get_pixmap(dpi=130, annots=True).tobytes("png")
    finally:
        d.close()
    return Response(png, media_type="image/png")


@app.get("/ritaglio.png")
def ritaglio_png(percorso: str, n: int = 1, box: str = ""):
    """Il pezzo di pagina di una riga da verificare, con la riga sopra e quella sotto."""
    if not _noto(percorso) or not os.path.exists(percorso):
        return Response(status_code=404)
    import fitz
    try:
        x0, y0, x1, y1 = [float(v) for v in box.split(",")]
    except ValueError:
        return Response(status_code=400)
    s = verifica_numeri.DPI / 72
    d = estrattori._apri(percorso)
    try:
        pg = d[max(1, min(n, d.page_count)) - 1]
        r = fitz.Rect(x0 / s, y0 / s - 14, x1 / s, y1 / s + 14) & pg.rect
        png = pg.get_pixmap(dpi=200, clip=r).tobytes("png")
    finally:
        d.close()
    return Response(png, media_type="image/png")


@app.get("/cita", response_class=HTMLResponse)
def pagina_cita(percorso: str, n: int = 1, brano: str = "", q: str = "", modo: str = "tesauro"):
    """La citazione a pagina n: com’è nel .md e com’è sull’originale, riletto adesso.

    Il .md serve per cercare — su un’immagine non si cerca — ma quando una
    frase finisce fra virgolette in un articolo, un errore di lettura non si
    vede più: una data letta 1296 invece di 1298 non la ritrova nessuno. Qui
    la pagina si riapre e si rilegge guardandola, e le due letture stanno una
    accanto all’altra. Costa circa quattromila gettoni e cinque secondi: in un
    articolo le citazioni sono quaranta, non ventimila."""
    if not _noto(percorso) or not os.path.exists(percorso):
        return _pagina("", risultati='<div class="vuoto">Questo documento non è '
                                     'nell’archivio, o non si trova più sul disco.</div>')
    r = citazione.cita(percorso, n, brano)
    p = urllib.parse.quote(percorso)
    if r["differenze"]:
        voci = "".join(
            f'<tr><td class="meta">{e_(d["come"])}</td>'
            f'<td>{e_(d["nel_md"]) or "<i>niente</i>"}</td>'
            f'<td><b>{e_(d["sull_originale"]) or "<i>niente</i>"}</b></td></tr>'
            for d in r["differenze"])
        tabella = (f'<table style="width:100%;border-collapse:collapse"><tr>'
                   f'<th></th><th style="text-align:left">nel .md</th>'
                   f'<th style="text-align:left">sull’originale</th></tr>{voci}</table>')
    else:
        tabella = ""
    da_copiare = r["sull_originale"] or r["nel_md"]
    corpo = f"""<div class="pannello">
<h3 style="margin:0 0 6px">La citazione, guardata sull’originale</h3>
<p class="meta">{e_(os.path.basename(percorso))} · pagina <b>{n}</b></p>
<p><b>{e_(r["stato"])}</b></p>
<div style="display:flex;gap:14px;flex-wrap:wrap">
 <div style="flex:1 1 380px;min-width:300px">
  <div class="foglio"><img alt="pagina {n}" style="width:100%"
   src="/pagina.png?percorso={p}&amp;n={n}"></div>
  <p class="azioni"><a href="{_link_vedi(percorso, n, q, modo, vicino=False)}">vedi la pagina intera</a>
   <a href="{_link_file(percorso, n)}" target="_blank">apri il PDF qui</a></p>
 </div>
 <div style="flex:1 1 380px;min-width:300px">
  <p class="meta">da copiare — è la lettura fatta adesso sull’immagine:</p>
  <textarea style="width:100%;height:150px;box-sizing:border-box;font:inherit;padding:6px"
   >{e_(da_copiare)}</textarea>
  <p class="meta" style="margin-top:10px">come sta nel .md:</p>
  <p style="background:#f6f6f6;padding:8px;border-radius:4px">{e_(r["nel_md"]) or "<i>questa pagina nel .md non c’è</i>"}</p>
  {tabella}
 </div>
</div></div>"""
    return _pagina(f"citazione · {e_(os.path.basename(percorso)[:50])} p. {n}",
                   risultati=corpo, q=q, modo=modo)


@app.get("/verifica", response_class=HTMLResponse)
def pagina_verifica(percorso: str, tutte: int = 0, sporche: int = 0):
    """Le righe con numeri da verificare di un .md: per ognuna il pezzo
    dell'originale, le due letture e il campo per scrivere quella giusta."""
    md = _md_di(percorso)
    dati = verifica_numeri.carica(md) if _noto(percorso) else None
    if not dati:
        return _pagina("", risultati='<div class="vuoto">Per questo documento non ci sono numeri '
                                     'da verificare.</div>')
    q = urllib.parse.quote(percorso)
    # Le «sporche» sono righe che il voto aveva deciso e che nel .md non hanno
    # nessun avviso: dentro hanno lettere di un altro alfabeto. Nessun altro
    # elenco le mostra, quindi hanno un filtro loro.
    def e_sporca(r):
        return (r["stato"] == "deciso a maggioranza"
                and verifica_numeri.lettura_sporca(r.get("giusto") or ""))
    quante_sporche = sum(1 for r in dati["righe"] if e_sporca(r))
    if sporche:
        righe = [r for r in dati["righe"] if e_sporca(r)]
    else:
        righe = [r for r in dati["righe"] if tutte or r["stato"] == "da verificare"]
    voci = []
    for r in righe:
        img = f'/ritaglio.png?percorso={q}&amp;n={r["pagina"]}&amp;box={",".join(str(int(v)) for v in r["box"])}'
        vedi = _link_vedi(percorso, r["pagina"], "", "tesauro", vicino=False)
        if r["stato"] == "verificato":
            gesti = f'<p class="meta">✓ verificato: {e_(r.get("giusto", ""))}</p>'
        elif r["stato"] == "deciso a maggioranza":
            # Decisa non vuol dire giusta: il terzo giudice da' ragione a una
            # delle due letture, ma puo' sbagliare tutte e tre. Qui nel .md non
            # c'e' nessun avviso, quindi senza questo campo la riga non si
            # poteva piu' toccare da nessuna parte.
            avviso = ('<p class="meta" style="color:var(--m)"><b>lettura sporca</b>: '
                      'ha lettere di un altro alfabeto dove dovrebbero esserci '
                      'latine o cifre</p>' if e_sporca(r) else '')
            gesti = (f'<p class="meta">✓ deciso da tre letture — la terza, «{e_(r.get("terza", ""))}», '
                     f'ha dato ragione alla {e_(r.get("scelta", ""))}: {e_(r.get("giusto", ""))}</p>'
                     + avviso
                     + f'<p><input type="text" class="giusto" value="{e_(r.get("giusto") or r["prima"])}" '
                     f'style="width:100%;box-sizing:border-box;font:inherit;padding:5px"></p>'
                     f'<p><button type="button" data-percorso="{e_(percorso)}" data-codice="{e_(r["codice"])}" '
                     f'onclick="salvaVerifica(this)">salva</button> '
                     f'<button type="button" class="piccolo" data-seconda="{e_(r["seconda"])}" '
                     f'onclick="usaSeconda(this)" style="background:var(--m)">metti la seconda lettura</button>'
                     f'<span class="esitoMd stato"></span></p>')
        else:
            gesti = (f'<p><input type="text" class="giusto" value="{e_(r["prima"])}" '
                     f'style="width:100%;box-sizing:border-box;font:inherit;padding:5px"></p>'
                     f'<p><button type="button" data-percorso="{e_(percorso)}" data-codice="{e_(r["codice"])}" '
                     f'onclick="salvaVerifica(this)">salva</button> '
                     f'<button type="button" class="piccolo" data-seconda="{e_(r["seconda"])}" '
                     f'onclick="usaSeconda(this)" style="background:var(--m)">metti la seconda lettura</button>'
                     f'<span class="esitoMd stato"></span></p>')
        voci.append(f'<div class="brano" id="v{e_(r["codice"])}"><div class="meta">pagina {r["pagina"]} · '
                    f'<a href="{vedi}"{_scheda(vedi)}>apri la pagina intera</a></div>'
                    f'<img src="{img}" alt="la riga sull\'originale" style="max-width:100%;'
                    f'border:1px solid var(--b);margin:4px 0">'
                    f'<p style="margin:4px 0"><span class="meta">prima lettura:</span> {e_(r["prima"])}<br>'
                    f'<span class="meta">seconda lettura:</span> {e_(r["seconda"])}<br>'
                    f'<span class="meta">{e_(r["nota"])}</span></p>{gesti}</div>')
    restano = dati["conti"].get("da_verificare", 0)
    altre = ("" if tutte else f' · <a href="/verifica?percorso={q}&amp;tutte=1">mostra anche quelle già verificate</a>')
    if sporche:
        altre = f' · <a href="/verifica?percorso={q}">torna a quelle da verificare</a>'
    elif quante_sporche:
        altre += (f' · <a href="/verifica?percorso={q}&amp;sporche=1" style="color:var(--m)">'
                  f'<b>{quante_sporche} letture sporche</b> date per buone</a>')
    corpo = f"""<div class="pannello"><h2>Numeri da verificare</h2>
<p><b>{e_(os.path.basename(percorso))}</b> — <span id="restano">{restano if not sporche else len(righe)}</span> righe {"sporche da guardare" if sporche else "da verificare"} su
{dati["conti"].get("righe_con_numeri", 0)} righe con numeri{altre}.</p>
<p style="font-size:13.5px">Ogni riga con numeri è stata letta due volte, da due programmi diversi
({e_(dati["conti"].get("seconda_lettura", ""))} per la seconda). Qui ci sono quelle in cui i numeri
non concordano: guarda il pezzo dell'originale, correggi la riga nel campo — di solito basta un
numero — e premi <b>salva</b>. La correzione va nel .md, al posto della riga e del suo
[⚠ verificare …]. Il PDF non si tocca.</p></div>{"".join(voci) or "<p class='meta'>nessuna</p>"}"""
    return _pagina("", risultati=corpo)


@app.post("/verifica")
def salva_verifica(dati: dict):
    percorso = str(dati.get("percorso") or "")
    if not _noto(percorso):
        return JSONResponse({"errore": "Questo documento non è nell'archivio."})
    try:
        restano = verifica_numeri.correggi(_md_di(percorso),
                                           str(dati.get("codice") or ""), str(dati.get("testo") or ""))
    except ValueError as exc:
        return JSONResponse({"errore": str(exc)})
    return JSONResponse({"ok": True, "restano": restano})


STATI = {"indicizzato": "letto", "da_ocr": "scansione da riconoscere", "vuoto": "senza testo"}
FILTRI = [("tutti", "tutti"), ("pdf", "solo i PDF"), ("senza_md", "PDF senza .md"),
          ("con_copie", "con copie altrove"), ("da_ocr", "scansioni da riconoscere"),
          ("vuoti", "senza testo")]
# L'ordine delle colonne: prima quello che viene dai documenti di questa
# cartella — i gruppi scoperti — e i tuoi; i temi del tesauro, che vengono da
# un vocabolario già pronto, per ultimi e chiusi.
ORIGINE = {"mio": "gruppo tuo", "cartella": "sottocartella", "tesauro": "tema del tesauro",
           "scoperto": "gruppo scoperto"}


def e_(x):
    return html.escape(str(x))


def _scheda(url):
    """Dove si apre un link: le pagine di Scaffale nella stessa scheda — così la
    freccia del browser e «indietro» riportano alla ricerca — e il file vero,
    il PDF intero o il Word, in una scheda sua."""
    return ' target="_blank"' if str(url).startswith("/apri") else ""


def _bottone_forme(g, gid):
    """Per un tema fatto da te: il pulsante per cambiarne le parole."""
    if not g or g.get("origine") != "mio" or not g.get("forme"):
        return ""
    import json
    parole = ", ".join(json.loads(g["forme"]))
    return (f'<button type="button" class="piccolo" data-gruppo="{gid}" '
            f'data-forme="{e_(parole)}" onclick="cambiaForme(this)">cambia le parole</button>'
            f'<span class="esitoMd stato"></span>')


def _elenco_contato(contatore, quanti=8):
    voci = contatore.most_common()
    righe = [f"<li>{e_(k)}: <b>{_numero(n)}</b></li>" for k, n in voci[:quanti]]
    if len(voci) > quanti:
        righe.append(f"<li>altri: {_numero(sum(n for _, n in voci[quanti:]))}</li>")
    return "<ul>" + "".join(righe) + "</ul>"


def _apri_documento(x):
    """Dove porta il nome di un documento: la sua scheda."""
    return f"/documento?percorso={urllib.parse.quote(x['percorso'])}"


@app.get("/cartella", response_class=HTMLResponse)
def pagina_cartella(radice: str, mostra: str = "tutti", gruppo: int = 0):
    """La scheda di una cartella: i numeri, come è raggruppata, i file.

    I numeri dicono che cosa c'è; i raggruppamenti dicono di che cosa parla, e
    ognuno spiega come è stato trovato; i file si guardano tutti o per gruppo,
    e si spostano da un gruppo all'altro.
    """
    voce = next((r for r in archivio.radici() if r["radice"] == radice), None)
    if not voce:
        return _pagina("", risultati='<div class="vuoto">Questa cartella non è nell’archivio.</div>')
    t = biblioteca.totali(radice)
    docs = archivio.documenti_di(radice)
    copie = t["copie"]
    # il PDF e il suo .md, ovunque stia il .md: una coppia, una riga
    coppia = coppie.coppie(docs)
    compagni = set(coppia.values())
    for x in docs:
        x["pdf"] = x["estensione"] == ".pdf"
        x["md"] = coppia.get(x["percorso"]) if x["pdf"] else None
        x["copie"] = copie.get(x["impronta"], 1)
    gruppi = biblioteca.gruppi_di(radice)
    per_file = biblioteca.gruppi_per_file(radice)
    schede = biblioteca.schede_di(radice)
    q_rad = urllib.parse.quote(radice)
    base = voce["percorso"] or ""

    # 1) in numeri
    semantica_pct = 100 * t["con_vettori"] / max(t["brani"], 1)
    numeri = f"""<div class="numeri">
<div><b class="grande">{_numero(t['documenti'])}</b> documenti · {_peso(t['byte'])}<br>
 {_numero(t['parole'])} parole · {_numero(t['brani'])} brani</div>
<div>per tipo{_elenco_contato(t['per_tipo'])}</div>
<div>come ho avuto il testo{_elenco_contato(t['per_metodo'])}</div>
<div><b class="grande">{_numero(t['pdf_con_md'])} su {_numero(t['pdf'])}</b> PDF hanno già il .md
 · <a href="/cartella?radice={q_rad}&amp;mostra=senza_md">quelli senza</a></div>
<div><b class="grande">{_numero(t['con_copie'])}</b> documenti hanno una copia, qui o altrove
 ({_numero(t['gruppi_copie'])} gruppi) · <a href="/doppioni?radice={q_rad}">dove sono</a></div>
<div><b class="grande">{_percento(semantica_pct)}</b> dei brani ha i vettori per la ricerca per senso</div>
</div>"""

    # 2) come sono raggruppati
    corrente = archivio.lavoro()
    vivo = bool(corrente and corrente["stato"] in IN_CORSO and _LAVORI.get(corrente["id"])
                and _LAVORI[corrente["id"]].is_alive())
    if vivo and corrente["tipo"] == "analizza" and corrente["nome"] == radice:
        stato_analisi = (f'<b>Sto analizzando la cartella…</b> <span class="esitoMd stato" '
                         f'data-segui="{corrente["id"]}"></span>')
    elif not t["analizzata_il"] and t["documenti"]:
        # mai analizzata: si comincia da soli, appena si apre la scheda
        stato_analisi = (f'<b>La cartella non era ancora stata analizzata: lo faccio adesso.</b> '
                         f'<button type="button" data-radice="{e_(radice)}" data-auto="1" '
                         f'onclick="analizzaCartella(this, false)">Analizza la cartella</button>'
                         f'<span class="esitoMd stato"></span>')
    elif t["analizzata_il"]:
        stato_analisi = (f"Ultima analisi {_quando(t['analizzata_il'])}. "
                         f'<button type="button" class="piccolo" data-radice="{e_(radice)}" '
                         f'onclick="analizzaCartella(this)">Rifai l’analisi</button>'
                         f'<span class="esitoMd stato"></span>')
    else:
        durata = _circa(5 + 0.02 * t["documenti"])
        stato_analisi = (f'<b>La cartella non è ancora stata analizzata</b>, quindi non ci sono né '
                         f'temi né gruppi scoperti. <button type="button" data-radice="{e_(radice)}" '
                         f'onclick="analizzaCartella(this)">Analizza la cartella — {durata}</button>'
                         f'<span class="esitoMd stato"></span>')
    colonne = _colonne_temi(radice, q_rad, gruppi, gruppo, t, vivo, corrente)
    tre_colonne = "".join(colonne)
    in_analisi = ((vivo and corrente["tipo"] == "analizza" and corrente["nome"] == radice)
                  or (not t["analizzata_il"] and t["documenti"]))
    if in_analisi:
        tre_colonne = ('<div class="spiegazione" style="grid-column:1/-1">Sto analizzando la '
                       'cartella — da pochi secondi a qualche minuto, secondo quanti file ha: qui '
                       'compaiono le sottocartelle, i temi del tesauro, i gruppi scoperti e i tuoi, '
                       'e nell’elenco le parole caratteristiche di ogni file. La pagina si aggiorna '
                       'da sola quando ho finito.</div>')
    raggruppamenti = f"""<p style="margin:14px 0 0"><a href="/domande?radice={q_rad}"><b>Fai una
domanda ai documenti di questa cartella</b></a> — il modello risponde con i brani che ha letto,
e ogni brano si apre alla sua pagina.</p>
<h3 style="margin:18px 0 4px">Come sono raggruppati</h3>
<p style="font-size:13.5px">Per trovarli quando cerchi, Scaffale ha indicizzato ogni documento
<b>per le parole che contiene</b>: nessuna classificazione per argomento. Per raggrupparli per
materia li raccoglie in <b>temi</b>, in un elenco solo — i tuoi, quelli dei tesauri, quelli
proposti dal modello e quelli scoperti nei documenti, ognuno con la sua etichetta — e accanto
ti mostra le tue sottocartelle. Apri un tema, e la ricerca guarda solo lì dentro. {stato_analisi}</p>
<div class="gruppi">{tre_colonne}</div>"""

    # 2bis) di che cosa parlano: i riassunti
    v_r = archivio.velocita()["riassunto"]
    mancano_r = max(t["con_testo"] - t["riassunti"], 0)
    ollama_ok = semantica.acceso()
    if vivo and corrente["tipo"] == "riassunti" and corrente["nome"] == radice:
        gesto_r = (f'<b>Sto scrivendo i riassunti…</b> <span class="esitoMd stato" '
                   f'data-segui="{corrente["id"]}"></span> <button type="button" class="piccolo" '
                   f'data-lavoro="{corrente["id"]}" onclick="fermaQuesto(this)" '
                   f'style="background:var(--m)">Ferma</button>')
    elif not mancano_r:
        gesto_r = "Li hanno tutti." if t["con_testo"] else ""
    elif not ollama_ok:
        gesto_r = ("Ollama non risponde, quindi adesso i riassunti non si possono scrivere: "
                   "chiudi e riapri Scaffale dall’icona, che prova ad accenderlo.")
    else:
        gesto_r = (f'<button type="button" data-radice="{e_(radice)}" data-quanti="{mancano_r}" '
                   f'data-tempo="{_circa(mancano_r * v_r)}" onclick="riassumiTutti(this)">'
                   f'Scrivi i riassunti degli altri {_numero(mancano_r)} — {_circa(mancano_r * v_r)}'
                   f'</button><span class="esitoMd stato"></span>')
    ciascuno = _circa(v_r).replace("circa ", "")
    per_tutti = _circa(mancano_r * v_r).replace("circa ", "")
    riassunti_html = f"""<h3 style="margin:18px 0 4px">Di che cosa parlano</h3>
<p style="font-size:13.5px"><b>{_numero(t['riassunti'])} su {_numero(t['con_testo'])}</b> documenti
hanno il riassunto. <b>I riassunti non si scrivono da soli</b>: li scrive un modello di Ollama che
gira su questo computer — niente esce dal PC — e ci vogliono circa {ciascuno} a documento, cioè
{per_tutti} per tutti quelli che mancano. Puoi farli scrivere a tutti, lasciandolo lavorare anche
di notte, oppure solo a quelli che ti servono: <b>spuntali</b> nell’elenco qui sotto, o <b>apri un
gruppo</b> e fai riassumere i suoi. Si può fermare quando vuoi, e quelli fatti restano. Sono
automatici e possono sbagliare. Sotto ogni file c’è il suo riassunto, o finché manca le sue
prime righe.</p><p style="font-size:13.5px">{gesto_r}</p>"""

    # 3) i file: tutti, per filtro, o di un gruppo
    g_scelto = biblioteca.gruppo(gruppo) if gruppo else None
    membri = biblioteca.membri(gruppo) if g_scelto else {}
    prova = {"tutti": lambda x: True, "pdf": lambda x: x["pdf"],
             "senza_md": lambda x: x["pdf"] and not x["md"],
             "con_copie": lambda x: x["copie"] > 1,
             "da_ocr": lambda x: x["stato"] == "da_ocr",
             "vuoti": lambda x: x["stato"] not in ("indicizzato", "da_ocr")}
    mostra = mostra if mostra in prova else "tutti"
    scelti = [x for x in docs if prova[mostra](x) and (not g_scelto or x["percorso"] in membri)]
    conti = {k: sum(1 for x in docs if f(x)) for k, f in prova.items()}
    filtri = " ".join(
        f'<a href="/cartella?radice={q_rad}&amp;mostra={k}"'
        f'{" class=scelto" if k == mostra and not g_scelto else ""}>{nome} ({_numero(conti[k])})</a>'
        for k, nome in FILTRI)
    quale_gruppo = ""
    if g_scelto:
        torna = f"/cartella?radice={q_rad}"
        senza_r = [p for p in membri if not schede.get(p, {}).get("riassunto")]
        gesto_gruppo = ""
        if senza_r and ollama_ok:
            gesto_gruppo = (f'<button type="button" class="piccolo" data-radice="{e_(radice)}" '
                            f'data-gruppo="{gruppo}" data-tempo="{_circa(len(senza_r) * v_r)}" '
                            f'onclick="riassumiGruppo(this)">riassumi i suoi {len(senza_r)} file senza '
                            f'riassunto — {_circa(len(senza_r) * v_r)}</button>')
        cerca_qui = (f'<form action="/" method="get" style="margin:8px 0 2px;display:flex;gap:8px">'
                     f'<input type="hidden" name="radice" value="gruppo:{gruppo}">'
                     f'<input type="search" name="q" placeholder="cerca solo in questo gruppo…" '
                     f'style="flex:1;max-width:460px">'
                     f'<button type="submit">Cerca nel gruppo</button>'
                     f'<a href="/domande?radice=gruppo:{gruppo}" style="align-self:center">'
                     f'fai una domanda a questo gruppo</a></form>')
        quale_gruppo = (f'<div class="spiegazione"><b>{e_(g_scelto["nome"])}</b> — '
                        f'{_numero(len(scelti))} documenti. {e_(g_scelto["spiegazione"] or "")}'
                        f'{cerca_qui}'
                        f'<div class="azioni" style="margin-top:6px">'
                        f'<a href="{torna}">torna a tutti i file</a>'
                        f'<button type="button" class="piccolo" data-azione="rinomina" '
                        f'data-gruppo="{gruppo}" data-nome="{e_(g_scelto["nome"])}" '
                        f'onclick="gestisciGruppo(this)">rinomina</button>'
                        f'<button type="button" class="piccolo" data-azione="elimina" '
                        f'data-gruppo="{gruppo}" data-torna="{torna}" '
                        f'onclick="gestisciGruppo(this)" style="background:var(--m)">elimina il gruppo</button>'
                        f'{gesto_gruppo}{_bottone_forme(g_scelto, gruppo)}{_in_tema(g_scelto, gruppo)}'
                        f'</div></div>')
    # nelle sottocartelle non si mettono file a mano: rispecchiano il disco
    opzioni = "".join(f'<option value="{g["id"]}">{e_(g["nome"])} ({ORIGINE[g["origine"]]})</option>'
                      for g in gruppi if g["id"] != gruppo and g["origine"] != "cartella")
    sposta = ""
    if g_scelto:
        sposta = (f'<button type="button" class="piccolo" data-da="{gruppo}" '
                  f'onclick="mettiSelezionati(this, true)">spostali lì (escono da '
                  f'«{e_(g_scelto["nome"])}»)</button>'
                  f'<button type="button" class="piccolo" data-azione="togli" data-gruppo="{gruppo}" '
                  f'onclick="gestisciGruppo(this)" style="background:var(--m)">toglili da questo gruppo</button>')
    riassumi_spuntati = ""
    if ollama_ok:
        riassumi_spuntati = (f'<button type="button" class="piccolo" data-radice="{e_(radice)}" '
                             f'data-per-uno="{int(v_r)}" onclick="riassumiSpuntati(this)">'
                             f'riassumi quelli spuntati</button>')
    barra = (f'<div class="barra-scelta"><label><input type="checkbox" onclick="tuttiOnessuno(this)"> '
             f'tutti</label> quelli spuntati: <select id="dove_mettere"><option value="">scegli un '
             f'gruppo…</option>{opzioni}</select>'
             f'<button type="button" class="piccolo" onclick="mettiSelezionati(this, false)">mettili lì</button>'
             f'{sposta}<button type="button" class="piccolo" data-radice="{e_(radice)}" '
             f'onclick="nuovoGruppo(this, true)">mettili in un gruppo nuovo…</button>'
             f'{riassumi_spuntati}</div>')

    per_cartella = {}
    # il .md di un PDF che è già in elenco non fa una riga a sé: sta nella riga del PDF
    pdf_in_elenco = {x["percorso"] for x in scelti if x["pdf"]}
    da_nascondere = {coppia[p] for p in pdf_in_elenco if p in coppia}
    for x in scelti:
        if x["percorso"] in da_nascondere:
            continue
        try:
            rel = os.path.relpath(x["cartella"], base) if base else x["cartella"]
        except ValueError:
            rel = x["cartella"]
        per_cartella.setdefault("la cartella stessa" if rel == "." else rel, []).append(x)
    aperte = len(per_cartella) <= 4 or mostra != "tutti" or bool(g_scelto)
    blocchi = []
    for rel, lista in per_cartella.items():
        righe = []
        for x in lista:
            sch = schede.get(x["percorso"], {})
            parole = ", ".join(w for w, _, _ in sch.get("parole", [])[:6])
            etichette = "".join(
                f'<a class="etichetta{" mio" if o == "mio" else ""}" '
                f'href="/cartella?radice={q_rad}&amp;gruppo={gid}">{e_(nome)}</a>'
                for gid, nome, o in per_file.get(x["percorso"], [])[:6])
            perche = ""
            if g_scelto and x["percorso"] in membri:
                perche = f'<br><span class="stato">qui perché: {e_(membri[x["percorso"]][1] or "")}</span>'
            copia = ""
            if x["copie"] > 1:
                copia = (f' · <a href="/documento?percorso={urllib.parse.quote(x["percorso"])}#copie">'
                         f'{x["copie"]} copie</a>')
            md = " · senza .md" if x["pdf"] and not x["md"] else ""
            motivi_md, bottone_md = "", ""
            if x["md"]:
                q = coppie.qualita(x["md"], x["pagine"], x["metodo"], pdf=x["percorso"])
                apri_md = _link_file(x["md"])
                md = (f' · <a href="{apri_md}"{_scheda(apri_md)}>il .md</a> '
                      f'<b class="giudizio {q["giudizio"].replace(" ", "-")}" '
                      f'title="{e_("; ".join(q["motivi"]) or "nessun problema trovato")}">{e_(q["giudizio"])}</b>')
                if q["motivi"]:
                    motivi_md = f"<br><span class='stato'>il .md: {e_('; '.join(q['motivi']))}</span>"
                v_n = verifica_numeri.carica(x["md"])
                if v_n and v_n["conti"].get("da_verificare"):
                    md += (f' · <a href="/verifica?percorso={urllib.parse.quote(x["percorso"])}">'
                           f'{v_n["conti"]["da_verificare"]} righe con numeri da verificare</a>')
                if q["giudizio"] == "da rifare" or (q["dati"].get("numeri") == "non verificati"
                                                    and verifica_numeri.modello()):
                    bottone_md = (f' <button type="button" class="piccolo" data-percorso="{e_(x["percorso"])}" '
                                  f'data-rifai="1" onclick="creaMd(this)">rifai il .md con la verifica dei '
                                  f'numeri</button><span class="esitoMd stato"></span>')
            elif x["pdf"]:
                bottone_md = (f' <button type="button" class="piccolo" data-percorso="{e_(x["percorso"])}" '
                              f'onclick="creaMd(this)">crea .md</button><span class="esitoMd stato"></span>')
            # un riassunto solo per la coppia: se il PDF non ce l'ha, si mostra quello del .md
            if x["pdf"] and x["md"] and not sch.get("riassunto") and schede.get(x["md"], {}).get("riassunto"):
                sch = dict(sch, riassunto=schede[x["md"]]["riassunto"])
            riga_parole = f"<br><span class='parole'>{e_(parole)}</span>" if parole else ""
            if sch.get("riassunto"):
                descr = f"<div class='descr'>{e_(sch['riassunto'][:480])}</div>"
            elif sch.get("incipit"):
                descr = (f"<div class='descr'><span class='meta'>comincia così:</span> "
                         f"{e_(sch['incipit'][:260])}</div>")
            else:
                descr = ""
            riga_etichette = f"<br>{etichette}" if etichette else ""
            righe.append(
                f'<tr><td style="width:24px"><input type="checkbox" class="scelta" '
                f'value="{e_(x["percorso"])}"></td>'
                f'<td><a href="{_apri_documento(x)}"><b>{e_(x["nome"])}</b></a>{descr}'
                f'<span class="stato">{e_(x["estensione"] or "")} · '
                f'{_estensione(x["percorso"], x["pagine"]) or "—"} · '
                f'{e_(biblioteca.come_letto(x["metodo"], x["stato"]))}{md}{copia}</span>{bottone_md}'
                f'{motivi_md}{riga_parole}{riga_etichette}{perche}</td></tr>')
        aperta = " open" if aperte else ""
        blocchi.append(f'<details class="sotto"{aperta}>'
                       f'<summary>{e_(rel)} — {_numero(len(lista))} file</summary>'
                       f'<table class="elenco-file">{"".join(righe)}</table></details>')

    v = archivio.velocita()
    mancano = [x for x in docs if x["pdf"] and not x["md"]]
    secondi = sum((x["pagine"] or 1) * v["ocr"] if x["stato"] == "da_ocr" else v["pdf"]
                  for x in mancano)
    if verifica_numeri.modello():
        # la seconda lettura dei numeri: tutta per le scansioni; per i PDF con il
        # testo, un terzo circa sono scansioni con l'OCR di altri e si rileggono
        secondi = sum(verifica_numeri.stima(x["pagine"] or 1, True) if x["stato"] == "da_ocr"
                      else v["pdf"] + verifica_numeri.stima(x["pagine"] or 1, False) / 3
                      for x in mancano)
    tutti_md = ""
    if mancano:
        tutti_md = (f'<div class="riga2" style="margin:10px 0 4px">'
                    f'<button type="button" class="piccolo" data-radice="{e_(radice)}" '
                    f'data-quanti="{len(mancano)}" data-tempo="{_circa(secondi)}" onclick="creaMd(this)">'
                    f'Crea i .md dei {_numero(len(mancano))} PDF che non ce l’hanno — {_circa(secondi)}'
                    f'</button><span class="esitoMd stato"></span></div>')
    nessuno = '<div class="vuoto">Nessun file qui.</div>'
    i_file = "".join(blocchi) or nessuno
    corpo = f"""<div class="pannello">
<h2>«{e_(radice)}»</h2>
<p><span class="strada" style="display:block">{e_(base)}</span>
<a href="/?radice={q_rad}">cerca solo in questa cartella</a> ·
<a href="/doppioni?radice={q_rad}">i suoi doppioni</a></p>
<h3 style="margin:14px 0 4px">In numeri</h3>
{numeri}
{_pannello_sistema(radice)}
{raggruppamenti}
{riassunti_html}
<h3 style="margin:18px 0 4px">I file</h3>
<div class="filtri">{filtri}</div>
{quale_gruppo}
{tutti_md}
{barra}
{i_file}
</div>"""
    return _pagina(f"{e_(radice)} · {_numero(len(docs))} documenti", risultati=corpo,
                   radice=radice, gruppo=gruppo if g_scelto else None)


@app.get("/documento", response_class=HTMLResponse)
def pagina_documento(percorso: str):
    """Tutto quello che Scaffale sa di un documento."""
    c = archivio.apri()
    d = c.execute("SELECT * FROM documenti WHERE percorso=?", (percorso,)).fetchone()
    if not d:
        return _pagina("", risultati='<div class="vuoto">Questo documento non è nell’archivio.</div>')
    d = dict(d)
    p = urllib.parse.quote(percorso)
    q_rad = urllib.parse.quote(d["radice"] or "")
    brani = c.execute("SELECT COUNT(*) n, MIN(id) primo FROM frammenti WHERE documento=?",
                      (d["id"],)).fetchone()
    con_vettori = c.execute("""SELECT COUNT(*) n FROM vettori v JOIN frammenti f ON f.id = v.frammento
                               WHERE f.documento=?""", (d["id"],)).fetchone()["n"]
    copie = [dict(r) for r in c.execute(
        "SELECT id, percorso, radice FROM documenti WHERE impronta=? AND impronta<>'' AND id<>?",
        (d["impronta"] or "", d["id"]))]
    sch = biblioteca.scheda(percorso)
    suoi = biblioteca.gruppi_del_file(percorso)
    tutti = biblioteca.gruppi_di(d["radice"])
    pdf = percorso.lower().endswith(".pdf")
    if pdf:
        apri = _link_vedi(percorso, 1, "", "tesauro", vicino=False)
    elif brani["primo"]:
        apri = f"/brano?f={brani['primo']}"
    else:
        apri = _link_file(percorso)
    try:
        st = os.stat(percorso)
        sul_disco = f"{_peso(st.st_size)} · modificato {_quando(st.st_mtime)}"
    except OSError:
        sul_disco = "<b>non c’è più sul disco</b>"

    # com'è stato indicizzato
    righe = [
        ("dove sta", f'<span class="strada" style="display:block">{e_(percorso)}</span>'
                     f'nella cartella «{e_(d["radice"])}»'),
        ("sul disco", sul_disco),
        ("tipo", f'{e_(d["estensione"])} · {_estensione(percorso, d["pagine"]) or "—"}'),
        ("come ho avuto il testo", e_(biblioteca.come_letto(d["metodo"], d["stato"]))),
        ("indicizzato", f'{_quando(d["indicizzato_il"])} · {_numero(d["parole"] or 0)} parole in '
                        f'{_numero(brani["n"])} brani, ognuno col suo numero di pagina'),
        ("ricerca per senso", f'{_numero(con_vettori)} brani su {_numero(brani["n"])} hanno i vettori'),
    ]
    if pdf:
        md = _md_di(percorso)
        if os.path.exists(md):
            q = coppie.qualita(md, d["pagine"], d["metodo"], pdf=percorso)
            motivi = ("<br><span class='meta'>" + e_("; ".join(q["motivi"])) + "</span>") if q["motivi"] else ""
            righe.append(("il .md", f'c’è, <b class="giudizio {q["giudizio"].replace(" ", "-")}">'
                                    f'{e_(q["giudizio"])}</b>{motivi}'
                                    f'<span class="strada" style="display:block">{e_(md)}</span>'))
        else:
            righe.append(("il .md", f'non c’è ancora. <button type="button" class="piccolo" '
                                    f'data-percorso="{e_(percorso)}" onclick="creaMd(this)">crea .md'
                                    f'</button><span class="esitoMd stato"></span>'))
    scheda_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in righe)

    # le copie
    if copie:
        mia_firma = strumenti.firma_file(percorso)
        for x in copie:
            firma = strumenti.firma_file(x["percorso"])
            try:
                peso = _peso(os.path.getsize(x["percorso"])) + " · "
            except OSError:
                peso = ""
            if not firma or not mia_firma:
                x["com_e"] = f'{peso}<span class="diverso">non confrontato</span>'
            elif firma == mia_firma:
                x["com_e"] = f'{peso}<span class="uguale">file identico a questo</span>'
            else:
                x["com_e"] = f'{peso}<span class="diverso">file diverso: stesso testo, ma non è lo stesso file</span>'
        elenco = "".join(
            f'<div class="copia"><span class="dati">{x["com_e"]} · in «{e_(x["radice"] or "")}»</span>'
            f'<span class="strada" style="max-width:560px">{e_(x["percorso"])}</span>'
            f'<a href="/documento?percorso={urllib.parse.quote(x["percorso"])}">scheda</a>'
            f'<a href="/mostra?percorso={urllib.parse.quote(x["percorso"])}" target="_blank">'
            f'mostra nella cartella</a></div>' for x in copie)
        quanti_altri = "altro file" if len(copie) == 1 else "altri file"
        blocco_copie = (f'<p>Lo stesso testo sta anche in <b>{len(copie)} {quanti_altri}</b>. '
                        f'<a href="/doppioni?radice={q_rad}">Vai ai doppioni</a> '
                        f'per sceglierne uno da togliere.</p>{elenco}')
    else:
        blocco_copie = "<p>Nessun altro file dell’archivio ha lo stesso testo.</p>"

    # di che cosa parla
    parole = sch.get("parole") or []
    if parole:
        dette = ", ".join(
            f'<span title="{n} volte in questo documento, in {_numero(r)} brani di tutto l’archivio">'
            f'<b>{e_(w)}</b> ({n})</span>' for w, n, r in parole)
        parole_html = (f"<p>{dette}</p><p class='meta'>Sono le parole frequenti in questo "
                       f"documento e rare nel resto dell’archivio: fra parentesi quante volte "
                       f"compaiono qui.</p>")
    else:
        parole_html = (f"<p class='meta'>Non ancora calcolate: premi «Analizza la cartella» nella "
                       f"<a href='/cartella?radice={q_rad}'>scheda della cartella</a>.</p>")
    inizio = ""
    if sch.get("incipit"):
        inizio = (f"<p class='meta' style='margin:10px 0 4px'>Come comincia</p>"
                  f'<div class="brano">{e_(sch["incipit"])}</div>')
    v = archivio.velocita()
    tempo = _circa(v["riassunto"])
    if sch.get("riassunto"):
        riassunto = (f'<div class="brano" id="riassunto">{e_(sch["riassunto"])}</div>'
                     f'<p class="meta">Scritto da {e_(sch.get("modello") or "")}, che gira su questo '
                     f'computer, {_quando(sch.get("riassunto_il"))}. È automatico: può sbagliare, '
                     f'controlla sul testo prima di fidarti. '
                     f'<button type="button" class="piccolo" data-percorso="{e_(percorso)}" '
                     f'data-tempo="{tempo}" onclick="riassumi(this)">rifallo</button></p>')
    else:
        riassunto = (f'<p><button type="button" data-percorso="{e_(percorso)}" '
                     f'data-tempo="{tempo}" onclick="riassumi(this)">Scrivi il riassunto — {tempo}'
                     f'</button></p><p class="meta">Lo scrive un modello di Ollama che gira su questo '
                     f'computer: niente esce dal PC. È lento e può sbagliare, per questo lo fa solo '
                     f'quando lo chiedi.</p>')

    # l'indice interno del PDF, se ce l'ha
    indice_html = ""
    if pdf:
        voci_indice = biblioteca.indice_pdf(percorso)
        if voci_indice:
            righe_i = "".join(
                f'<li style="margin-left:{(l - 1) * 18}px">'
                f'<a href="{_link_vedi(percorso, pg, "", "tesauro", vicino=False)}">'
                f'{e_(titolo)}</a> <span class="meta">p. {pg}</span></li>'
                for l, titolo, pg in voci_indice[:400])
            indice_html = (f"<h3>L’indice del documento</h3><p class='meta'>È l’indice che il PDF porta "
                           f"con sé: clicca un titolo per aprire quella pagina.</p>"
                           f"<ul style='list-style:none;padding:0;font-size:14px;margin:6px 0 16px'>"
                           f"{righe_i}</ul>")
        else:
            indice_html = ("<h3>L’indice del documento</h3><p class='meta'>Questo PDF non porta con "
                           "sé un indice interno: per orientarti ci sono le parole caratteristiche, "
                           "come comincia e il riassunto.</p>")

    # i gruppi
    miei_id = {x["id"] for x in suoi}
    opzioni = "".join(f'<option value="{g["id"]}">{e_(g["nome"])} ({ORIGINE[g["origine"]]})</option>'
                      for g in tutti if g["id"] not in miei_id)
    righe_g = "".join(
        f'<div class="copia"><span><b>{e_(g["nome"])}</b> '
        f'<span class="dati">— {ORIGINE[g["origine"]]} · {e_(g["prova"] or "")}</span></span>'
        f'<button type="button" class="piccolo" data-da="{g["id"]}" data-percorso="{e_(percorso)}" '
        f'onclick="mettiSelezionati(this, true)">sposta nel gruppo scelto sotto</button>'
        f'<button type="button" class="piccolo" data-azione="togli" data-gruppo="{g["id"]}" '
        f'data-percorso="{e_(percorso)}" onclick="gestisciGruppo(this)" '
        f'style="background:var(--m)">togli</button></div>' for g in suoi)
    if not righe_g:
        righe_g = "<p class='meta'>Per ora non sta in nessun gruppo.</p>"
    gruppi_html = (f'{righe_g}<div class="riga2" style="margin-top:10px"><select id="dove_mettere">'
                   f'<option value="">scegli un gruppo…</option>{opzioni}</select>'
                   f'<button type="button" class="piccolo" data-percorso="{e_(percorso)}" '
                   f'onclick="mettiSelezionati(this, false)">mettilo anche lì</button>'
                   f'<button type="button" class="piccolo" data-radice="{e_(d["radice"])}" '
                   f'data-percorso="{e_(percorso)}" onclick="nuovoGruppo(this, false)">'
                   f'mettilo in un gruppo nuovo…</button></div>')

    corpo = f"""<div class="pannello">
<h2>{e_(d["nome"])}</h2>
<div class="azioni" style="margin-bottom:10px"><a href="{apri}"{_scheda(apri)}>aprilo</a>
 <a href="/lancia?percorso={p}" target="_blank">apri nel programma</a>
 <a href="/mostra?percorso={p}" target="_blank">mostra nella cartella</a>
 <a href="/cartella?radice={q_rad}">torna alla cartella</a></div>
<h3>Com’è stato indicizzato</h3><dl class="scheda">{scheda_html}</dl>
<h3 id="copie">Le copie</h3>{blocco_copie}
<h3>Di che cosa parla</h3>
<p class="meta" style="margin-bottom:4px">Le parole caratteristiche</p>{parole_html}
{inizio}
<p class="meta" style="margin:10px 0 4px">Il riassunto</p>{riassunto}
{indice_html}
<h3>I suoi gruppi</h3>{gruppi_html}
</div>"""
    return _pagina(e_(d["nome"][:80]), risultati=corpo, radice=d["radice"] or "")


@app.post("/gruppo")
def azione_gruppo(dati: dict):
    """Crea, rinomina, elimina un gruppo; ci mette, ne toglie, ne sposta documenti."""
    az = dati.get("azione")
    percorsi = [p for p in (dati.get("percorsi") or []) if _noto(p)]
    if az == "nuovo":
        radice = dati.get("radice") or ""
        nome = (dati.get("nome") or "").strip()
        if not nome:
            return JSONResponse({"errore": "Il gruppo ha bisogno di un nome."})
        if radice not in {r["radice"] for r in archivio.radici()}:
            return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
        gid = biblioteca.nuovo_gruppo(radice, nome)
        if percorsi:
            biblioteca.metti(gid, percorsi)
        return JSONResponse({"id": gid})
    if az == "tema":
        radice = dati.get("radice") or ""
        nome = (dati.get("nome") or "").strip()
        forme = dati.get("forme") or []
        if not nome:
            return JSONResponse({"errore": "Il tema ha bisogno di un nome."})
        if radice not in {r["radice"] for r in archivio.radici()}:
            return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
        try:
            gid, quanti = biblioteca.nuovo_tema(radice, nome, forme)
        except ValueError as exc:
            return JSONResponse({"errore": str(exc)})
        return JSONResponse({"id": gid, "documenti": quanti})
    gid = int(dati.get("gruppo") or 0)
    if not biblioteca.gruppo(gid):
        return JSONResponse({"errore": "Non trovo questo gruppo."})
    if az == "forme":
        try:
            quanti = biblioteca.cambia_forme(gid, dati.get("forme") or [])
        except ValueError as exc:
            return JSONResponse({"errore": str(exc)})
        return JSONResponse({"ok": True, "documenti": quanti})
    if az == "tieni":
        try:
            nuovo = biblioteca.tieni_gruppo(gid)
        except ValueError as exc:
            return JSONResponse({"errore": str(exc)})
        return JSONResponse({"id": nuovo})
    if az == "in_tema":
        # un gruppo scoperto diventa un tema di un tesauro, con le sue parole per cominciare
        import json as _json
        g = biblioteca.gruppo(gid)
        nome = re.sub(r" — in .*$", "", g["nome"]).strip()
        forme = (_json.loads(g["forme"]) if g.get("forme")
                 else [x.strip() for x in nome.split("·") if x.strip()])
        tid = int(dati.get("tesauro") or 0)
        if not tesauri.tesauro_di(tid):
            return JSONResponse({"errore": "Non trovo questo tesauro."})
        try:
            id_tema = tesauri.salva_tema(tid, nome, forme)
        except ValueError as exc:
            return JSONResponse({"errore": str(exc)})
        radice = g["radice"]
        attivi = tesauri.attivi(radice)
        if tid not in attivi:                       # il tema nuovo deve vedersi nella cartella
            tesauri.imposta(radice, attivi + [tid])
        biblioteca.rifai_tema(tid, {nome})
        return JSONResponse({"tesauro": tid, "tema": id_tema})
    if az == "rinomina":
        nome = (dati.get("nome") or "").strip()
        if not nome:
            return JSONResponse({"errore": "Il gruppo ha bisogno di un nome."})
        biblioteca.rinomina(gid, nome)
    elif az == "elimina":
        biblioteca.elimina(gid)
    elif az == "metti":
        if not percorsi:
            return JSONResponse({"errore": "Nessun file da mettere nel gruppo."})
        biblioteca.metti(gid, percorsi, da=int(dati.get("da") or 0) or None)
    elif az == "togli":
        for p in percorsi:
            biblioteca.togli(gid, p)
    else:
        return JSONResponse({"errore": "Non so fare questa cosa."})
    return JSONResponse({"ok": True})


def _temi_in_fondo(id_lavoro, radice):
    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])
    try:
        biblioteca.aggiorna_temi(radice, avviso=riferisci, id_lavoro=id_lavoro)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])


@app.get("/tesauri", response_class=HTMLResponse)
def pagina_tesauri(radice: str = ""):
    """I tesauri: che cosa sono, quali ci sono, i loro temi, dove si usano."""
    e = html.escape
    cartelle = [r["radice"] for r in archivio.radici()]
    if radice not in cartelle:
        radice = ""
    tutti = tesauri.elenco()
    in_uso = set(tesauri.attivi(radice)) if radice else set()
    opzioni = "".join(f'<option value="{e(r)}"{" selected" if r == radice else ""}>{e(r)}</option>'
                      for r in cartelle)
    q_rad = urllib.parse.quote(radice)
    scelta = ""
    if radice:
        scelta = (f'<div class="spiegazione" style="margin-top:10px">Spunta i tesauri da usare in '
                  f'<b>«{e(radice)}»</b>, poi premi il pulsante: Scaffale rifà i temi della '
                  f'cartella — in una cartella grande ci vuole un minuto o due. '
                  f'<button type="button" data-radice="{e(radice)}" onclick="salvaTesauri(this)">'
                  f'Usa i tesauri spuntati in «{e(radice)}»</button>'
                  f'<span class="esitoMd stato"></span> '
                  f'<a href="/cartella?radice={q_rad}">torna alla cartella</a></div>')
    corpo = [f"""<div class="pannello"><h2>I tesauri</h2>
<p>Un <b>tesauro</b> è un elenco di temi, e un <b>tema</b> è un nome con le parole che lo dicono,
in tutte le lingue e le grafie che ti servono — <i>duello: duello, duellum, duel, dvoboj,
Zweikampf</i>. Scaffale li usa in due modi: nella <b>ricerca in modo «tesauro»</b>, dove una
parola trova anche le altre del suo tema, e nella <b>scheda di una cartella</b>, dove dice quali
file toccano ciascun tema, con quali parole e quante volte.</p>
<p>Fanne uno per ogni ricerca — «Progetti europei», «Duello e onore», «Prezzi e inflazione» — e
scegli quali usare in ogni cartella. «{e(tesauri.DI_PARTENZA)}» è quello che Scaffale aveva già;
lo usano le cartelle per cui non hai ancora scelto. Una sigla scritta in maiuscolo, come AI o
EU, nei temi della scheda vale solo in maiuscolo.</p>
<div class="azioni"><button type="button" onclick="nuovoTesauro()">+ nuovo tesauro</button>
<form method="get" action="/tesauri" style="display:inline;margin:0 0 0 14px">
quali tesauri usa la cartella <select name="radice" onchange="this.form.submit()">
<option value="">— scegli —</option>{opzioni}</select></form>
<span class="esitoMd stato"></span></div>{scelta}</div>"""]
    for t in tutti:
        dove = ", ".join(f'<a href="/cartella?radice={urllib.parse.quote(r)}">{e(r)}</a>'
                         for r in t["cartelle"]) or "nessuna cartella"
        spunta = ""
        if radice:
            spunta = (f'<label style="font-weight:600;margin-right:14px"><input type="checkbox" '
                      f'class="usa-tesauro" value="{t["id"]}"{" checked" if t["id"] in in_uso else ""}> '
                      f'usalo in «{e(radice)}»</label>')
        righe = "".join(
            f'<tr><td style="width:190px;vertical-align:top"><b>{e(m["nome"])}</b></td>'
            f'<td class="meta" style="vertical-align:top">{e(", ".join(m["forme"]))}</td>'
            f'<td style="width:170px;vertical-align:top;white-space:nowrap">'
            f'<button type="button" class="piccolo" data-tesauro="{t["id"]}" data-tema="{m["id"]}" '
            f'data-nome="{e(m["nome"])}" data-forme="{e(", ".join(m["forme"]))}" '
            f'onclick="modificaTemaT(this)">modifica</button> '
            f'<button type="button" class="piccolo" data-tesauro="{t["id"]}" data-tema="{m["id"]}" '
            f'data-nome="{e(m["nome"])}" onclick="eliminaTemaT(this)" style="background:var(--m)">'
            f'elimina</button></td></tr>' for m in t["temi"])
        elimina = ("" if t["di_partenza"] else
                   f'<button type="button" class="piccolo" data-tesauro="{t["id"]}" '
                   f'data-nome="{e(t["nome"])}" onclick="eliminaTesauro(this)" '
                   f'style="background:var(--m)">elimina il tesauro</button>')
        nessun_tema = ('<p class="meta">Ancora nessun tema: aggiungine uno, con il nome e le '
                       'parole che lo dicono.</p>')
        tabella = (f'<table style="width:100%;border-collapse:collapse;margin-top:8px">{righe}</table>'
                   if righe else nessun_tema)
        partenza = ' <span class="meta">· di partenza</span>' if t["di_partenza"] else ''
        corpo.append(f"""<div class="pannello" id="t{t["id"]}">
<h3 style="margin:0 0 4px">{e(t["nome"])}{partenza}</h3>
<p class="meta" style="margin:0 0 6px">{e(t["descrizione"] or "")}</p>
<p style="font-size:13.5px;margin:0 0 8px">{len(t["temi"])} temi · lo usano: {dove}</p>
<div class="azioni">{spunta}<button type="button" class="piccolo" data-tesauro="{t["id"]}"
 onclick="nuovoTemaT(this)">+ nuovo tema</button>
<button type="button" class="piccolo" data-tesauro="{t["id"]}" data-nome="{e(t["nome"])}"
 data-descrizione="{e(t["descrizione"] or "")}" onclick="rinominaTesauro(this)">rinomina</button>
{elimina}<span class="esitoMd stato"></span></div>
{tabella}
</div>""")
    sotto = (f"{len(tutti)} {'tesauro' if len(tutti) == 1 else 'tesauri'}"
             + (f" · la cartella «{e(radice)}»" if radice else ""))
    return _pagina(sotto, risultati="".join(corpo), radice=radice)


def _rifatti(tid, solo=None):
    """Rifà i temi toccati nelle cartelle che usano il tesauro, e dice com'è andata."""
    esito = biblioteca.rifai_tema(tid, solo)
    parti = []
    for radice, conti in esito.items():
        for nome, n in conti.items():
            parti.append(f"«{nome}» in «{radice}»: {n} file")
    return "; ".join(parti) or "nessuna cartella usa ancora questo tesauro"


@app.post("/tesauro")
def azione_tesauro(dati: dict):
    """Crea, rinomina, elimina un tesauro e i suoi temi; sceglie i tesauri di una cartella."""
    az = dati.get("azione")
    try:
        if az == "nuovo":
            tid = tesauri.nuovo(dati.get("nome"), dati.get("descrizione") or "")
            return JSONResponse({"id": tid})
        if az == "attiva":
            radice = dati.get("radice") or ""
            if radice not in {r["radice"] for r in archivio.radici()}:
                return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
            errore = _occupato()
            if errore:
                return JSONResponse({"errore": errore})
            tesauri.imposta(radice, [int(x) for x in dati.get("tesauri") or []])
            id_lavoro = archivio.nuovo_lavoro("analizza", "", radice)
            t = threading.Thread(target=_temi_in_fondo, args=(id_lavoro, radice), daemon=True)
            t.start()
            _LAVORI[id_lavoro] = t
            return JSONResponse({"lavoro": id_lavoro})
        tid = int(dati.get("tesauro") or 0)
        ts = tesauri.tesauro_di(tid)
        if not ts:
            return JSONResponse({"errore": "Non trovo questo tesauro."})
        if az == "rinomina":
            tesauri.rinomina(tid, dati.get("nome"), dati.get("descrizione"))
            return JSONResponse({"ok": True})
        if az == "elimina":
            tesauri.elimina(tid)
            biblioteca.togli_gruppi_tesauro(ts)       # i suoi temi escono subito dalle cartelle
            return JSONResponse({"ok": True})
        if az == "tema":
            id_tema = int(dati.get("id_tema") or 0) or None
            vecchio = tesauri.tema(id_tema) if id_tema else None
            id_tema = tesauri.salva_tema(tid, dati.get("nome"), dati.get("forme") or [], id_tema)
            nome = tesauri.tema(id_tema)["nome"]
            toccati = {nome} | ({vecchio["nome"]} if vecchio else set())
            return JSONResponse({"ok": True, "esito": _rifatti(tid, toccati)})
        if az == "togli_tema":
            t_ = tesauri.tema(int(dati.get("id_tema") or 0))
            tesauri.elimina_tema(int(dati.get("id_tema") or 0))
            if t_:
                _rifatti(tid, {t_["nome"]})
            return JSONResponse({"ok": True})
    except ValueError as exc:
        return JSONResponse({"errore": str(exc)})
    return JSONResponse({"errore": "Non so fare questa cosa."})


@app.post("/varianti")
def proponi_varianti(dati: dict):
    """Le varianti delle parole di un tema che stanno davvero nei documenti."""
    parole = tesauri.pulisci_forme(dati.get("parole") or [])
    if not parole:
        return JSONResponse({"errore": "Scrivi prima almeno una parola del tema."})
    radice = dati.get("radice") or None
    if radice and radice not in {r["radice"] for r in archivio.radici()}:
        radice = None
    return JSONResponse({"proposte": varianti.dal_vocabolario(parole, radice), "radice": radice})


@app.post("/traduzioni")
def proponi_traduzioni(dati: dict):
    """Le forme in altre lingue, dal modello locale, tenute solo se stanno nei documenti."""
    parole = tesauri.pulisci_forme(dati.get("parole") or [])
    nome = (dati.get("nome") or "").strip() or (parole[0] if parole else "")
    if not parole:
        return JSONResponse({"errore": "Scrivi prima almeno una parola del tema."})
    if not semantica.acceso():
        return JSONResponse({"errore": "Ollama non risponde: accendilo, e riprova. Le varianti "
                                       "dai tuoi documenti funzionano anche senza."})
    radice = dati.get("radice") or None
    if radice and radice not in {r["radice"] for r in archivio.radici()}:
        radice = None
    try:
        ci_sono, non_ci_sono, modello = varianti.dal_modello(nome, parole, radice)
    except Exception as exc:
        return JSONResponse({"errore": f"Il modello non ha risposto: {exc}"[:300]})
    return JSONResponse({"proposte": ci_sono, "assenti": non_ci_sono, "modello": modello,
                         "radice": radice})


def _in_tema(g, gid):
    """Sotto un gruppo scoperto: tenerlo fra i propri, o farne un tema di un tesauro."""
    if not g or g.get("origine") != "scoperto":
        return ""
    tieni = (f'<button type="button" data-gruppo="{gid}" data-radice="{e_(g["radice"])}" '
             f'onclick="tieniGruppo(this)">Tieni fra i miei gruppi</button>')
    opzioni = "".join(f'<option value="{t["id"]}">{e_(t["nome"])}</option>' for t in tesauri.elenco())
    return (f'{tieni}<span style="margin-left:10px">oppure fanne un tema del tesauro '
            f'<select class="in-tesauro">{opzioni}<option value="nuovo">— un tesauro nuovo… —</option>'
            f'</select> <button type="button" class="piccolo" data-gruppo="{gid}" '
            f'data-radice="{e_(g["radice"])}" onclick="inTema(this)">fanne un tema</button></span>')


# l'elenco unico dei temi: da dove viene ciascuno, e in che ordine si mostra
PROVENIENZA = {"mio": (0, "tuo"), "tesauro": (1, "dal tesauro"),
               "proposto": (2, "proposto dal modello"), "scoperto": (3, "scoperto")}


def _temi_unici(radice, gruppi, proposte, n_doc):
    """I gruppi e i temi della cartella in un elenco solo.

    Prima erano quattro colonne — gruppi scoperti, temi proposti dal modello, i
    tuoi, quelli dei tesauri — e spesso dicevano la stessa cosa: «duello» come
    gruppo scoperto, come tema del tesauro e come proposta del modello. Qui
    ognuno porta l'etichetta della sua provenienza, e due voci con quasi gli
    stessi file diventano una: resta quella che hai deciso tu (tua, poi del
    tesauro, poi proposta, poi scoperta), le altre stanno sotto. La regola è
    quella dei temi del modello: 60% dei file in comune, 80% se uno dei due è
    un tema di fondo, che sta in più di metà della cartella e ha molti file in
    comune con tutti."""
    c = biblioteca.apri()
    ids = [g["id"] for g in gruppi if g["origine"] != "cartella"]
    membri = {}
    if ids:
        for r in c.execute("SELECT gruppo, percorso FROM nei_gruppi WHERE come IN ('automatico','a mano') "
                           f"AND gruppo IN ({','.join('?' * len(ids))})", ids):
            membri.setdefault(r["gruppo"], set()).add(r["percorso"])
    # il tema di un tesauro, per il link «cambia le parole»
    temi_t = {}
    for r in c.execute("""SELECT m.id, m.tesauro, m.nome, t.di_partenza FROM temi_tesauro m
                          JOIN tesauri t ON t.id = m.tesauro"""):
        temi_t[tesauri.chiave_gruppo(r["tesauro"], r["di_partenza"], r["nome"])] = (r["tesauro"], r["id"])
    voci = [{"tipo": g["origine"], "g": g, "membri": membri.get(g["id"], set()), "n": g["documenti"],
             "tema": temi_t.get(g["chiave"])}
            for g in gruppi if g["origine"] in PROVENIENZA]
    voci += [{"tipo": "proposto", "p": p, "membri": p["membri"], "n": p["file"]}
             for p in proposte if p["stato"] == "proposto"]
    voci.sort(key=lambda v: (PROVENIENZA[v["tipo"]][0], -v["n"]))
    di_fondo = lambda v: v["n"] > 0.5 * n_doc
    tenute = []
    for v in voci:
        simile = None
        for t in tenute:
            if not v["membri"] or not t["membri"]:
                continue
            comuni = len(v["membri"] & t["membri"]) / len(v["membri"] | t["membri"])
            if comuni >= (0.8 if di_fondo(v) or di_fondo(t) else 0.6):
                simile = t
                break
        if simile:
            simile.setdefault("anche", []).append(v)
        else:
            tenute.append(v)
    return tenute


def _voce_proposta(p):
    """Il corpo di una proposta del modello: la frase, le parole da scegliere, tieni e scarta."""
    # le parole si scelgono prima di tenere il tema: si tolgono quelle
    # sbagliate, se ne aggiungono di proprie
    parole = " ".join(
        f'<label title="in {n} file"><input type="checkbox" class="forma" checked '
        f'value="{e_(f)}"> {e_(f)} ({n})</label>' for f, n in p["forme"])
    parole += (' <input type="text" class="altre-forme" size="28" '
               'placeholder="aggiungi parole, separate da virgole">')
    gesti = (f'<button type="button" class="piccolo" data-id="{p["id"]}" data-azione="tieni" '
             f'onclick="temaProposto(this)">tieni</button> '
             f'<button type="button" class="piccolo" data-id="{p["id"]}" data-azione="scarta" '
             f'onclick="temaProposto(this)" style="background:var(--m)">scarta</button>'
             f'<span class="esitoMd stato"></span>')
    return (f'<div class="proposta"><b>{e_(p["nome"])}</b> '
            f'<br><span class="meta">{e_(p["descrizione"] or "")}</span>'
            f'<br><span class="parole">{parole}</span><br>{gesti}</div>')


def _gesto_proposte(radice, vivo, corrente, proposte):
    """Il pulsante per far proporre i temi al modello, o il lavoro in corso."""
    if vivo and corrente["tipo"] == "temi" and corrente["nome"] == radice:
        return (f'<p><b>Il modello sta leggendo la cartella…</b> <span class="esitoMd stato" '
                f'data-segui="{corrente["id"]}"></span> <button type="button" class="piccolo" '
                f'data-lavoro="{corrente["id"]}" onclick="fermaQuesto(this)">ferma</button></p>')
    if not semantica.acceso():
        return ('<p class="meta">Per farti proporre dei temi dal modello serve Ollama acceso, con un '
                'modello per scrivere (per esempio qwen3:8b).</p>')
    quanto = _circa(temi_proposti.stima(radice))
    testo = "Fai proporre di nuovo i temi al modello" if proposte else "Fai proporre i temi al modello"
    return (f'<p><button type="button" class="piccolo" data-radice="{e_(radice)}" '
            f'onclick="proponiTemi(this)">{testo} — {quanto}</button><span class="esitoMd stato"></span>'
            f' <span class="meta">si può continuare a usare Scaffale mentre lavora</span></p>')


def _anche(v):
    """Sotto un tema, le voci che hanno quasi gli stessi file."""
    if not v.get("anche"):
        return ""
    pezzi = []
    for a in v["anche"]:
        dice = f'{PROVENIENZA[a["tipo"]][1]}, {_numero(a["n"])} file'
        if a["tipo"] == "proposto":
            p = a["p"]
            pezzi.append(f'<span>«{e_(p["nome"])}» ({dice}) <button type="button" class="piccolo" '
                         f'data-id="{p["id"]}" data-azione="scarta" onclick="temaProposto(this)" '
                         f'style="background:var(--m)" title="è quasi lo stesso tema: toglilo">scarta</button></span>')
        else:
            g = a["g"]
            pezzi.append(f'<a href="/cartella?radice={urllib.parse.quote(g["radice"])}&amp;gruppo={g["id"]}">'
                         f'«{e_(g["nome"])}»</a> ({dice})')
    return (f'<div class="meta anche">con quasi gli stessi file: {" · ".join(pezzi)}</div>')


def _riga_tema(v, q_rad, gruppo, n_doc):
    """Una voce dell'elenco dei temi: il nome, quanti file, da dove viene, i gesti."""
    tipo = v["tipo"]
    bollo = f'<span class="bollo">{PROVENIENZA[tipo][1]}</span>'
    if tipo == "proposto":
        p = v["p"]
        # in una cartella di una ricerca sola, il tema centrale sta quasi dappertutto:
        # non è vago, è il tema di fondo
        fondo = " · <i>tema di fondo</i>" if p["generico"] else ""
        return (f'<div class="tema" data-tipo="proposto"><details><summary><b>{e_(p["nome"])}</b> '
                f'<span class="meta">{_numero(p["file"])} file{fondo}</span> {bollo} '
                f'<span class="meta">— apri per scegliere le parole</span></summary>'
                f'{_voce_proposta(p)}</details>{_anche(v)}</div>')
    g = v["g"]
    fondo = (" · <i>tema di fondo</i>" if tipo in ("tesauro", "scoperto") and g["documenti"] > 0.5 * n_doc
             else "")
    nome_g = e_(g["nome"])
    if tipo == "mio" and g.get("forme"):
        nome_g += ' <i class="meta">tema</i>'
    scelto = " scelto" if g["id"] == gruppo else ""
    voce = (f'<a class="g{scelto}" href="/cartella?radice={q_rad}&amp;gruppo={g["id"]}">'
            f'{nome_g} <span>{_numero(g["documenti"])}{fondo}</span></a>{bollo}')
    if tipo == "scoperto":
        # con un clic fra i propri gruppi, col suo nome e i suoi file
        voce += (f'<button type="button" class="tieni" data-gruppo="{g["id"]}" '
                 f'data-radice="{e_(g["radice"])}" title="tienilo fra i tuoi gruppi, con questo nome e '
                 f'questi file" onclick="tieniGruppo(this)">+ tieni</button>')
    elif tipo == "tesauro" and v.get("tema"):
        tid, id_tema = v["tema"]
        voce += (f'<a class="meta" href="/tesauri?radice={q_rad}&amp;tema={id_tema}#t{tid}" '
                 f'title="le parole con cui Scaffale trova questo tema">cambia le parole</a>')
    return f'<div class="tema" data-tipo="{tipo}"><div class="riga-g">{voce}</div>{_anche(v)}</div>'


def _colonne_temi(radice, q_rad, gruppi, gruppo, t, vivo, corrente):
    """Le due colonne della scheda: i temi della cartella, in un elenco solo, e
    le sottocartelle, che sono l'ordine dato sul disco e non un tema."""
    n_doc = max(t["documenti"], 1)
    proposte = temi_proposti.di(radice)
    voci = _temi_unici(radice, gruppi, proposte, n_doc)
    quanti = {}
    for v in voci:
        quanti[v["tipo"]] = quanti.get(v["tipo"], 0) + 1
    filtro = "".join(
        f'<button type="button" class="piccolo{" scelto" if k == "tutti" else ""}" data-tipo="{k}" '
        f'onclick="filtraTemi(this)">{dice} ({n})</button> '
        for k, dice, n in [("tutti", "tutti", len(voci))]
        + [(k, PROVENIENZA[k][1], quanti[k]) for k in PROVENIENZA if quanti.get(k)])
    usati = [x for x in tesauri.elenco() if x["id"] in tesauri.attivi(radice)]
    nomi_t = ", ".join(f"«{e_(x['nome'])}»" for x in usati) or "<b>nessuno</b>"
    spiega = ("Tutti i temi della cartella in un elenco solo. L'etichetta dice da dove viene "
              "ciascuno: <b>tuo</b>, un gruppo o un tema che hai fatto tu; <b>dal tesauro</b>, un "
              f"tema dei tesauri in uso qui ({nomi_t}), dove un file entra se le sue parole "
              "compaiono in almeno 3 suoi brani; <b>proposto dal modello</b>, da decidere: aprilo, "
              "scegli le parole, tienilo o scartalo; <b>scoperto</b>, parole caratteristiche che i "
              "file hanno in comune, e <b>+ tieni</b> lo fa tuo. Se due hanno quasi gli stessi file "
              "se ne vede uno solo, con l'altro sotto. Apri un tema per vedere i file e cercare solo "
              f"lì dentro. <a href='/tesauri?radice={q_rad}'>Scegli i tesauri, o creane uno</a>.")
    nuovi = (f'<p><button type="button" class="piccolo" data-radice="{e_(radice)}" '
             f'onclick="nuovoGruppo(this, false)">+ nuovo gruppo</button> '
             f'<button type="button" class="piccolo" data-radice="{e_(radice)}" '
             f'onclick="nuovoTema(this)">+ nuovo tema con le tue parole</button>'
             f'<span class="esitoMd stato"></span></p>')
    righe = "".join(_riga_tema(v, q_rad, gruppo, n_doc) for v in voci) or "<p class='meta'>nessuno</p>"
    temi = (f'<div class="temi-col"><h4>temi della cartella ({len(voci)})</h4>'
            f'<p class="meta">{spiega}</p>{nuovi}{_gesto_proposte(radice, vivo, corrente, proposte)}'
            f'<div class="filtro-temi">{filtro}</div>'
            f'<div class="temi-unici">{righe}</div></div>')

    sotto = []
    for g in (x for x in gruppi if x["origine"] == "cartella"):
        nome_g = e_(g["nome"])
        if " › " in g["nome"]:
            # la sottocartella di una sottocartella: rientrata sotto la madre
            nome_g = f'<span style="padding-left:14px">› {e_(g["nome"].split(" › ", 1)[1])}</span>'
        scelto = " scelto" if g["id"] == gruppo else ""
        sotto.append(f'<a class="g{scelto}" href="/cartella?radice={q_rad}&amp;gruppo={g["id"]}">'
                     f'{nome_g} <span>{_numero(g["documenti"])}</span></a>')
    if len(sotto) > 25:
        sotto = [f'<div style="max-height:620px;overflow:auto">{"".join(sotto)}</div>']
    cartelle = (f'<div><h4>le tue sottocartelle ({sum(1 for x in gruppi if x["origine"] == "cartella")})</h4>'
                '<p class="meta">Le sottocartelle, come le hai ordinate tu sul disco, con quelle che '
                'contengono. Non sono temi: sono il tuo ordine, e Scaffale lo prende così com’è.</p>'
                f'{"".join(sotto) or "<p class=meta>nessuna</p>"}</div>')
    return [temi, cartelle]


def _temi_modello_in_fondo(id_lavoro, radice):
    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])
    try:
        temi_proposti.proponi(radice, avviso=riferisci, id_lavoro=id_lavoro)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])


@app.post("/proponi_temi")
def avvia_proposta_temi(dati: dict):
    radice = dati.get("radice") or ""
    if radice not in {r["radice"] for r in archivio.radici()}:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    if not semantica.acceso():
        return JSONResponse({"errore": "Ollama non risponde: accendilo, e riprova."})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    id_lavoro = archivio.nuovo_lavoro("temi", "", radice)
    t = threading.Thread(target=_temi_modello_in_fondo, args=(id_lavoro, radice), daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro})


@app.post("/tema_proposto")
def decidi_tema_proposto(dati: dict):
    """Tenere o scartare un tema proposto dal modello."""
    try:
        if dati.get("azione") == "tieni":
            forme = dati.get("forme")
            tid, id_tema, n = temi_proposti.tieni(int(dati.get("id") or 0),
                                                  forme if isinstance(forme, list) else None)
            return JSONResponse({"ok": True, "tesauro": tid, "file": n})
        if dati.get("azione") == "scarta":
            temi_proposti.scarta(int(dati.get("id") or 0))
            return JSONResponse({"ok": True})
    except ValueError as exc:
        return JSONResponse({"errore": str(exc)})
    return JSONResponse({"errore": "Non so fare questa cosa."})


# ------------------------------------------------------------- domande ---

def _risposta_html(testo, quanti):
    """La risposta del modello: paragrafi, e ogni [n] porta al suo brano, più sotto."""
    def cita(m):
        n = int(m.group(1))
        return f'<a href="#b{n}" class="cita" title="il brano {n}, qui sotto">[{n}]</a>' if 1 <= n <= quanti else ""
    parti = []
    for par in re.split(r"\n\s*\n", (testo or "").strip()):
        h = re.sub(r"\[(\d+)\]", cita, e_(par).replace("\n", "<br>"))
        # i numeri che non stanno nei brani citati (domande.guardia_numeri)
        h = re.sub(r"⚠(\w+)", r'<mark class="dubbio" title="questo numero non sta nel brano citato: '
                              r'controllalo">⚠\1</mark>', h)
        parti.append("<p>" + h + "</p>")
    return "".join(parti)


def _brano_html(b, parole_domanda):
    """Un brano letto dal modello: da dove viene, il testo con le parole in giallo, il link alla pagina."""
    testo = e_(b["testo"])
    for f in sorted(set(b.get("parole") or []), key=len, reverse=True):
        testo = re.sub(f"(?<![\\w])({re.escape(e_(f))})(?![\\w])", r"<b>\1</b>", testo)
    q = " ".join(parole_domanda)
    if b["percorso"].lower().endswith(".pdf"):
        apri = _link_vedi(b["percorso"], b["pagina"] or 1, q, "tesauro")
        dice = "apri la pagina, con le parole in giallo"
    else:
        apri = f"/brano?f={b['frammento']}&amp;q={urllib.parse.quote(q)}"
        dice = "apri il brano nel suo documento"
    dove = _dove_o_brano(b["percorso"], b["pagina"], b["frammento"])
    # nel ricercatore ogni brano ha anche che cosa dice, letto e controllato
    sintesi = (f'<p class="meta" style="margin:2px 0 6px"><b>che cosa dice:</b> {e_(b["sintesi"])}</p>'
               if b.get("sintesi") else "")
    return (f'<div class="brano" id="b{b["n"]}"><div class="meta"><b>[{b["n"]}]</b> '
            f'{e_(b["nome"])}{" · " + dove if dove else ""} · '
            f'<a href="{apri}"{_scheda(apri)}>{dice}</a></div>{sintesi}{testo}</div>')


def _diario_html(d):
    """Come ha lavorato il ricercatore: il piano, le ricerche, ogni brano letto e i controlli."""
    try:
        diario = json.loads(d.get("diario") or "{}")
    except ValueError:
        return ""
    p = diario.get("piano") or {}
    sotto = "".join(f"<li>{e_(x)}</li>" for x in p.get("sottodomande") or [])
    giri = "".join(f'<li>giro {i}: {", ".join(f"«{e_(q)}»" for q in g.get("ricerche") or [])} — '
                   f'{g.get("brani", 0)} brani da leggere</li>' for i, g in enumerate(diario.get("giri") or [], 1))
    rif = diario.get("riflessione") or {}
    manca = (f'<p class="meta">Dopo il primo giro: {"bastava" if rif.get("basta") else "mancava: " + e_(rif.get("manca", ""))}</p>'
             if rif else "")
    letti = []
    for x in diario.get("letti") or []:
        segno = "✓ serve" if x.get("pertinente") else "✗ non serve"
        controlli = []
        if x.get("pertinente"):
            controlli.append("frase copiata: " + ("trovata nel brano" if x.get("citazione_vera")
                                                  else "<b>non trovata nel brano, scartata</b>"))
            if x.get("numeri_assenti"):
                controlli.append("<b>numeri non nel brano: " + e_(", ".join(x["numeri_assenti"])) + "</b>")
        letti.append(f'<li>{e_(x.get("nome", ""))}{" · p. " + str(x["pagina"]) if x.get("pagina") else ""} — '
                     f'{segno}{" · " + " · ".join(controlli) if controlli else ""}'
                     f'{"<br><span class=meta>" + e_(x.get("sintesi", "")) + "</span>" if x.get("pertinente") else ""}</li>')
    return (f'<details style="margin-top:14px"><summary><b>Come ha lavorato</b> — il piano, le ricerche, '
            f'i {len(letti)} brani letti e i controlli</summary>'
            f'<p class="meta" style="margin-top:8px">Le domande in cui ha scomposto la tua:</p><ul>{sotto}</ul>'
            f'<p class="meta">Le ricerche:</p><ul>{giri}</ul>{manca}'
            f'<p class="meta">I brani letti, uno per uno:</p><ul style="font-size:13px">{"".join(letti)}</ul>'
            f'</details>')


@app.get("/domande", response_class=HTMLResponse)
def pagina_domande(radice: str = "", id: int = 0):
    """Le domande ai documenti: la casella, la risposta con i suoi brani, le domande di prima."""
    elenco = archivio.radici()
    d = domande.una(id) if id else None
    gruppo_g = None
    if d:
        radice = d["radice"] or ""
        gruppo_g = biblioteca.gruppo(d["gruppo"]) if d["gruppo"] else None
    elif radice.startswith("gruppo:"):
        try:
            gruppo_g = biblioteca.gruppo(int(radice.split(":", 1)[1]))
        except ValueError:
            gruppo_g = None
        radice = gruppo_g["radice"] if gruppo_g else ""
    if radice and radice not in {r["radice"] for r in elenco}:
        radice, gruppo_g = "", None
    dove = _scelta_dove(radice, elenco, gruppo_g) if elenco else ""
    pronto = semantica.acceso() and biblioteca._modello_per_riassunti()
    quanto = _circa(domande.stima())
    if pronto:
        nota = (f"Il modello risponde in {quanto}: su questo computer, senza scheda grafica, "
                "legge i brani lentamente. Si può continuare a usare Scaffale mentre lavora.")
    else:
        nota = ("<b>Ollama è spento, o non ha un modello per scrivere</b>: Scaffale ti mostra i "
                "brani che rispondono alla domanda, senza la risposta scritta.")
    casella = f"""<div class="pannello"><h2>Fai una domanda ai tuoi documenti</h2>
<p style="font-size:13.5px">Scaffale cerca i brani che rispondono, <b>per parole</b> — con le
varianti dei tesauri — e <b>per senso</b>, dove ci sono i vettori; poi il modello che gira sul
computer li legge e risponde <b>solo con quelli</b>, dicendo da quale brano viene ogni cosa:
[1], [2]. Ogni numero porta al brano, e ogni brano alla sua pagina. Il modello può sbagliare,
i brani no: controlla sempre sui brani prima di citare. Niente esce dal computer.</p>
<textarea id="domanda" rows="3" placeholder="per esempio: come si svolgeva il rito del bacio nelle paci private?"></textarea>
<p style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">{dove}
<button type="button" onclick="chiediDomanda(this)">Chiedi ai documenti</button>
<button type="button" class="piccolo" onclick="chiediRicercatore(this)"
title="il ricercatore: piano, più ricerche, lettura di ogni brano, rapporto verificato">Ricerca approfondita — {_circa(ricercatore.stima())}</button></p>
<p class="meta">{nota} La <b>ricerca approfondita</b> è per le domande difficili: il modello fa un
piano, cerca in più modi — anche con le parole latine o antiche —, legge ogni brano e ne copia la
frase chiave (Scaffale controlla che ci sia davvero), cerca ancora se manca qualcosa, e scrive un
rapporto in cui ogni numero è controllato sulla sua fonte. Da lanciare e lasciar lavorare.</p></div>"""

    corpo = [casella]
    if d:
        parole = domande.parole_di(d["domanda"])
        corrente = archivio.lavoro()
        in_corso = (corrente and corrente["tipo"] == "domanda" and corrente["nome"] == f"domanda {d['id']}"
                    and corrente["stato"] in IN_CORSO and _LAVORI.get(corrente["id"])
                    and _LAVORI[corrente["id"]].is_alive())
        luogo = (f"nel gruppo «{e_(gruppo_g['nome'])}» di «{e_(radice)}»" if gruppo_g
                 else f"in «{e_(radice)}»" if radice else "in tutte le cartelle")
        approfondita = d.get("tipo") == "ricercatore"
        if in_corso and approfondita:
            risposta = (f'<p><b>Il ricercatore sta lavorando…</b> ({_circa(ricercatore.stima())}) '
                        f'<span class="esitoMd stato" data-segui="{corrente["id"]}"></span> '
                        f'<button type="button" class="piccolo" data-lavoro="{corrente["id"]}" '
                        f'onclick="fermaQuesto(this)">ferma</button></p>')
        elif in_corso:
            risposta = (f'<p><b>Il modello sta leggendo i brani…</b> ({quanto}) '
                        f'<span class="esitoMd stato" data-segui="{corrente["id"]}"></span> '
                        f'<button type="button" class="piccolo" data-lavoro="{corrente["id"]}" '
                        f'onclick="fermaQuesto(this)">ferma</button></p>')
        elif d["stato"] == "finito":
            quando = f'{d["modello"]}, {_durata(d["secondi"] or 0)}' if d["modello"] else ""
            risposta = (f'<div class="risposta">{_risposta_html(d["risposta"], len(d["brani"]))}</div>'
                        + (f'<p class="meta">scritta da {e_(quando)}</p>' if quando else ""))
        elif d["stato"] == "fermato":
            risposta = "<p class='meta'>Fermata: nessuna risposta. Ecco i brani trovati.</p>"
        elif d["stato"] == "senza modello":
            risposta = ("<p class='meta'>Senza il modello non c'è la risposta scritta: ecco i brani "
                        "che rispondono alla domanda.</p>")
        else:
            risposta = ("<p class='meta'>La risposta non è arrivata: forse Scaffale è stato chiuso "
                        "mentre il modello scriveva. Fai di nuovo la domanda.</p>")
        brani_h = "".join(_brano_html(b, parole) for b in d["brani"])
        corpo.append(f"""<div class="pannello"><h2>{e_(d["domanda"])}</h2>
<p class="meta">cercato {luogo} · {len(d["brani"])} brani letti ·
<button type="button" class="piccolo" data-id="{d["id"]}" onclick="togliDomanda(this)"
style="background:var(--m)">togli dall’elenco</button></p>
{risposta}
<h3 style="margin:16px 0 6px">I brani da cui viene la risposta</h3>
{brani_h or "<p class='meta'>nessun brano</p>"}{_diario_html(d) if approfondita else ""}</div>""")

    prima = [x for x in domande.ultime() if not d or x["id"] != d["id"]]
    if prima:
        righe = "".join(
            f'<li><a href="/domande?id={x["id"]}">{e_(x["domanda"])}</a> '
            f'<span class="meta">· {e_(x["radice"] or "tutte le cartelle")} · {_quando(x["creato_il"])}</span></li>'
            for x in prima)
        corpo.append(f'<div class="pannello"><h3 style="margin-top:0">Le domande di prima</h3>'
                     f'<ul style="margin:0;padding-left:18px">{righe}</ul></div>')
    return _pagina("", risultati="".join(corpo), radice=radice,
                   gruppo=gruppo_g["id"] if gruppo_g else None)


def _domanda_in_fondo(id_lavoro, id_domanda):
    try:
        domande.rispondi(id_domanda, id_lavoro=id_lavoro)
    except Exception as exc:
        c = domande.apri()
        c.execute("UPDATE domande SET stato='errore' WHERE id=?", (id_domanda,))
        c.commit()
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])


@app.post("/domanda")
def fai_domanda(dati: dict):
    testo = re.sub(r"\s+", " ", str(dati.get("domanda") or "")).strip()[:600]
    if len(testo) < 3:
        return JSONResponse({"errore": "Scrivi prima la domanda."})
    radice, gruppo = str(dati.get("radice") or ""), None
    if radice.startswith("gruppo:"):
        try:
            g = biblioteca.gruppo(int(radice.split(":", 1)[1]))
        except ValueError:
            g = None
        if not g:
            return JSONResponse({"errore": "Non trovo questo gruppo."})
        radice, gruppo = g["radice"], g["id"]
    elif radice and radice not in {r["radice"] for r in archivio.radici()}:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    # prima i brani, che bastano pochi secondi; il modello serve solo se ce ne sono
    id_d, scelti = domande.nuova(testo, radice, gruppo)
    if not scelti:
        domande.rispondi(id_d)          # nessun brano: si dice subito, senza il modello
        return JSONResponse({"id": id_d})
    if not (semantica.acceso() and biblioteca._modello_per_riassunti()):
        domande.senza_modello(id_d)
        return JSONResponse({"id": id_d})
    errore = _occupato()
    if errore:
        domande.dimentica(id_d)
        return JSONResponse({"errore": errore})
    id_lavoro = archivio.nuovo_lavoro("domanda", "", f"domanda {id_d}")
    t = threading.Thread(target=_domanda_in_fondo, args=(id_lavoro, id_d), daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"id": id_d, "lavoro": id_lavoro})


def _ricercatore_in_fondo(id_lavoro, id_domanda):
    try:
        ricercatore.lavora(id_domanda, id_lavoro=id_lavoro)
    except Exception as exc:
        c = domande.apri()
        c.execute("UPDATE domande SET stato='errore' WHERE id=?", (id_domanda,))
        c.commit()
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])


@app.post("/ricerca_approfondita")
def fai_ricerca_approfondita(dati: dict):
    testo = re.sub(r"\s+", " ", str(dati.get("domanda") or "")).strip()[:600]
    if len(testo) < 3:
        return JSONResponse({"errore": "Scrivi prima la domanda."})
    radice, gruppo = str(dati.get("radice") or ""), None
    if radice.startswith("gruppo:"):
        try:
            g = biblioteca.gruppo(int(radice.split(":", 1)[1]))
        except ValueError:
            g = None
        if not g:
            return JSONResponse({"errore": "Non trovo questo gruppo."})
        radice, gruppo = g["radice"], g["id"]
    elif radice and radice not in {r["radice"] for r in archivio.radici()}:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    if not (semantica.acceso() and biblioteca._modello_per_riassunti()):
        return JSONResponse({"errore": "Per la ricerca approfondita serve Ollama acceso, con un modello "
                                       "per scrivere (per esempio qwen3:8b)."})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    c = domande.apri()
    id_d = c.execute("""INSERT INTO domande (radice, gruppo, domanda, brani, stato, creato_il, tipo, diario)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (radice, gruppo, testo, "[]", "in corso", time.time(), "ricercatore", "{}")).lastrowid
    c.commit()
    id_lavoro = archivio.nuovo_lavoro("domanda", "", f"domanda {id_d}")
    t = threading.Thread(target=_ricercatore_in_fondo, args=(id_lavoro, id_d), daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"id": id_d, "lavoro": id_lavoro})


@app.post("/domanda_togli")
def togli_domanda(dati: dict):
    domande.dimentica(int(dati.get("id") or 0))
    return JSONResponse({"ok": True})


def _pannello_sistema(radice):
    """«Sistema tutta la cartella»: che cosa farà, quanto ci vorrà, un pulsante solo."""
    # un lavoro di sistemazione in corso su questa cartella: si segue, con il Ferma
    for r in archivio.apri().execute("SELECT id, stato FROM lavori WHERE tipo='sistema' AND nome=? "
                                     "ORDER BY id DESC LIMIT 1", (radice,)):
        vivo = _LAVORI.get(r["id"])
        if r["stato"] in IN_CORSO and vivo and vivo.is_alive():
            return (f'<div class="spiegazione"><b>Sto sistemando la cartella…</b> '
                    f'<span class="esitoMd stato" data-segui="{r["id"]}"></span> '
                    f'<button type="button" class="piccolo" data-lavoro="{r["id"]}" '
                    f'onclick="fermaQuesto(this)">ferma</button></div>')
    p = sistema.piano(radice)
    voci = [
        ("md_mancanti", True, f'crea i .md che mancano: <b>{len(p["md_mancanti"]["percorsi"])}</b> PDF',
         p["md_mancanti"]),
        ("md_da_rifare", True, f'rifai i .md <b class="giudizio da-rifare">da rifare</b>: '
                               f'<b>{len(p["md_da_rifare"]["percorsi"])}</b>'
                               + (f', di cui <b>{p["md_da_rifare"]["antiche"]}</b> stampe antiche con la s lunga '
                                  f'(«fopra»), da rileggere col dizionario per le stampe antiche'
                                  if p["md_da_rifare"].get("antiche") else ""), p["md_da_rifare"]),
        ("md_non_verificati", False, f'rifai anche i .md con i <b>numeri non verificati</b>: '
                                     f'<b>{len(p["md_non_verificati"]["percorsi"])}</b> — i più lunghi',
         p["md_non_verificati"]),
        ("analisi", True, "aggiorna l’indice con il testo nuovo e rifai l’analisi (temi, gruppi)", p["analisi"]),
        ("riassunti", True, f'scrivi i riassunti che mancano: <b>{p["riassunti"]["quanti"]}</b> documenti '
                            f'(un PDF e il suo .md contano uno)', p["riassunti"]),
    ]
    righe = []
    for chiave, di_solito, testo, dati in voci:
        vuoto = (chiave.startswith("md_") and not dati["percorsi"]) or (chiave == "riassunti" and not dati["quanti"])
        segno = "" if vuoto else (" checked" if di_solito else "")
        spento = " disabled" if vuoto else ""
        quanto = "niente da fare" if vuoto else _circa(dati["secondi"])
        righe.append(f'<label style="display:block;margin:2px 0"><input type="checkbox" class="passo-sistema" '
                     f'value="{chiave}" data-secondi="{int(dati["secondi"])}"{segno}{spento}> {testo} '
                     f'<span class="meta">— {quanto}</span></label>')
    fuori = p.get("messi_da_parte") or {}
    if fuori.get("quanti"):
        # chi guarda deve sapere che un documento c’è ma oggi non si fa: se no
        # cerca nell’elenco un PDF che sa di avere e non lo trova
        righe.append(
            f'<p class="meta" style="margin:8px 0 0">Messi da parte a mano '
            f'(<i>metti_da_parte</i> in scaffale.ini): <b>{_numero(fuori["quanti"])}</b> '
            f'documenti ({_numero(fuori["pagine"])} pagine) non sono negli elenchi qui sopra. '
            f'{e_(", ".join(fuori["nomi"][:4]))}'
            f'{"…" if len(fuori["nomi"]) > 4 else ""}</p>')
    saltate = p.get("copie_saltate") or {}
    if saltate.get("quanti"):
        # perché l'elenco qui sopra è più corto dell'elenco dei PDF della cartella
        righe.append(
            f'<p class="meta" style="margin:8px 0 0">Lo stesso documento tenuto in più copie si fa '
            f'una volta sola: <b>{_numero(saltate["quanti"])}</b> esemplari '
            f'({_numero(saltate["pagine"])} pagine) non sono negli elenchi qui sopra, perché hanno '
            f'lo stesso testo di un altro che c’è già. '
            f'<a href="/doppioni?radice={urllib.parse.quote(radice)}">guardali</a></p>')
    avvisi = []
    if not p["verifica"]:
        avvisi.append("senza il modello GLM-OCR in Ollama i .md si fanno con una lettura sola")
    if not p["modello"]:
        avvisi.append("Ollama non risponde: i riassunti si salteranno")
    nota = f'<p class="meta">{e_("; ".join(avvisi))}.</p>' if avvisi else ""
    return f"""<div class="pannello" style="margin:12px 0"><h3 style="margin:0 0 6px">Sistema tutta la cartella</h3>
<p style="font-size:13.5px">Un pulsante solo, nell’ordine giusto: prima i .md (quelli nuovi e quelli
rifatti hanno i numeri letti tre volte; i .md di prima non si cancellano, restano come
<i>.md.vecchio</i>), poi l’indice e l’analisi sul testo nuovo, e alla fine i riassunti, scritti dal
modello sul computer. Per una cartella grande si lancia la sera: il computer resta sveglio da solo, e
<b>ferma</b> lo interrompe quando vuoi — quello che è fatto resta.</p>
{"".join(righe)}{nota}
<p><button type="button" data-radice="{e_(radice)}" onclick="sistemaCartella(this)">Sistema la cartella</button>
<span class="esitoMd stato"></span></p></div>"""


def _sistema_in_fondo(id_lavoro, radice, scelte):
    def registra(id_passo):
        _LAVORI[id_passo] = threading.current_thread()
    sistema.esegui(id_lavoro, radice, scelte, registra_filo=registra)


@app.post("/sistema")
def avvia_sistema(dati: dict):
    """Sistema tutta una cartella: .md, indice e analisi, riassunti."""
    radice = dati.get("radice") or ""
    if radice not in {r["radice"] for r in archivio.radici()}:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    scelte = {k: bool(v) for k, v in (dati.get("scelte") or {}).items()}
    if not any(scelte.values()):
        return JSONResponse({"errore": "Spunta almeno una cosa da fare."})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    id_lavoro = archivio.nuovo_lavoro("sistema", "", radice)
    t = threading.Thread(target=_sistema_in_fondo, args=(id_lavoro, radice, scelte), daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro})


def _analizza_in_fondo(id_lavoro, radice):
    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])
    try:
        biblioteca.analizza(radice, avviso=riferisci, id_lavoro=id_lavoro)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])


@app.post("/analizza")
def avvia_analisi(dati: dict):
    radice = dati.get("radice") or ""
    if radice not in {r["radice"] for r in archivio.radici()}:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    id_lavoro = archivio.nuovo_lavoro("analizza", "", radice)
    t = threading.Thread(target=_analizza_in_fondo, args=(id_lavoro, radice), daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro})


def _riassunti_in_fondo(id_lavoro, radice, percorsi=None):
    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])
    try:
        biblioteca.riassumi_tutti(radice, avviso=riferisci, id_lavoro=id_lavoro, percorsi=percorsi)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore", finito=time.time(),
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200])


@app.post("/riassumi_tutti")
def avvia_riassunti(dati: dict):
    """I riassunti di tutti i documenti di una cartella, in sottofondo."""
    radice = dati.get("radice") or ""
    if radice not in {r["radice"] for r in archivio.radici()}:
        return JSONResponse({"errore": "Non trovo questa cartella nell'archivio."})
    if not semantica.acceso():
        return JSONResponse({"errore": "Ollama non risponde: senza, i riassunti non si possono fare."})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    percorsi = None
    if dati.get("percorsi"):
        percorsi = [p for p in dati["percorsi"] if _noto(p)]
    elif dati.get("gruppo"):
        percorsi = list(biblioteca.membri(int(dati["gruppo"])).keys())
    if percorsi is not None and not percorsi:
        return JSONResponse({"errore": "Nessun file da riassumere."})
    id_lavoro = archivio.nuovo_lavoro("riassunti", "", radice)
    t = threading.Thread(target=_riassunti_in_fondo, args=(id_lavoro, radice, percorsi),
                         daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro})


@app.post("/riassumi")
def riassumi_documento(dati: dict):
    """Il riassunto di un documento, scritto da un modello di Ollama sul computer."""
    percorso = dati.get("percorso") or ""
    if not _noto(percorso):
        return JSONResponse({"errore": "Questo documento non è nell'archivio."})
    if not semantica.acceso():
        return JSONResponse({"errore": "Ollama non risponde: senza, il riassunto non si può fare."})
    t0 = time.time()
    try:
        testo, modello = biblioteca.riassumi(percorso)
    except Exception as exc:
        return JSONResponse({"errore": f"Non ci sono riuscito: {exc}"})
    archivio._ricorda("riassunto", time.time() - t0, 1, 1)
    return JSONResponse({"riassunto": testo, "modello": modello})


@app.get("/doppioni", response_class=HTMLResponse)
def doppioni(radice: str = ""):
    """I documenti presenti in più copie, con i gesti per controllarli e per
    toglierne una: aprirla, vederla nella sua cartella, spostarla nel Cestino."""
    e = html.escape
    gruppi = strumenti.gruppi_copie()
    if radice:
        gruppi = [g for g in gruppi if any(d["radice"] == radice for d in g["documenti"])]
    sprecato = sum(g["ridondanti"] for g in gruppi)
    misti = sum(1 for g in gruppi if not g["tutti_identici"])
    dove = f" in «{e(radice)}»" if radice else ""
    corpo = [f"""<div class="pannello"><h2>Documenti con lo stesso testo{dove}</h2>
<p>{_numero(len(gruppi))} gruppi. Scaffale li riconosce dal <b>testo</b>, poi confronta i file
uno per uno, e ogni riga dice che cosa ha trovato:</p>
<p><span class="uguale">file identico</span> è proprio lo stesso file salvato in due posti
(stessa dimensione, stesso contenuto): una copia in più, che si può togliere senza perdere
niente. Copie così occupano circa {_peso(sprecato)}.<br>
<span class="diverso">file diverso</span> ha lo stesso testo ma non è lo stesso file: di solito
un PDF e la sua versione compressa — più leggera perché le immagini sono a qualità più
bassa — oppure due scansioni dello stesso libro. Non è una copia da togliere a occhi chiusi:
{_numero(misti)} gruppi contengono file così. <b>Apri</b> e confronta, prima di decidere.</p>
<p><b>Sposta nel Cestino</b> toglie un file: finisce nel Cestino di Windows — o in quello di
OneDrive, se il file sta lì — e si recupera quando vuoi. L’ultimo file di un gruppo non si può
spostare: resta sempre almeno un esemplare.</p>"""]
    for g in gruppi[:150]:
        esistono = [d for d in g["documenti"] if os.path.exists(d["percorso"])]
        righe = []
        for d in g["documenti"]:
            c_e = d in esistono
            try:
                quando = time.strftime("%d/%m/%Y", time.localtime(os.path.getmtime(d["percorso"])))
            except OSError:
                quando = "—"
            apri = (_link_vedi(d["percorso"], 1, "", "tesauro", vicino=False)
                    if d["percorso"].lower().endswith(".pdf") else _link_file(d["percorso"]))
            p = urllib.parse.quote(d["percorso"])
            spento = "" if (c_e and len(esistono) > 1) else " disabled"
            sparito = "" if c_e else " · non c’è più sul disco"
            if not c_e:
                com_e = ""
            elif d["identici"]:
                altre = "un altro file" if d["identici"] == 1 else f"altri {d['identici']} file"
                com_e = f'<span class="uguale">file identico a {altre} del gruppo</span>'
            elif d["firma"] and g["stesso_testo"]:
                com_e = '<span class="diverso">file diverso: stesso testo, ma non è lo stesso file</span>'
            elif d["firma"]:
                com_e = '<span class="diverso">file diverso</span>'
            else:
                com_e = ('<span class="diverso">non confrontato: il file sta solo su OneDrive, '
                         'e per confrontarlo andrebbe scaricato</span>')
            if d["piu_corto"]:
                if d["estensione"] == ".pdf" and (d["pagine"] or 0) < d["pagine_max"]:
                    misura = f'{_numero(d["pagine"] or 0)} pagine contro {_numero(d["pagine_max"])}'
                else:
                    misura = f'{_numero(d["parole"] or 0)} parole contro {_numero(d["parole_max"])}'
                com_e += (f' <span class="diverso">{misura}: comincia con lo stesso testo, ma è '
                          f'più corto — forse solo un capitolo o una parte, o un testo che '
                          f'Scaffale ha letto solo in parte</span>')
            diverso = "" if d["identici"] else ' data-diverso="1"'
            righe.append(
                f'<div class="copia"><span class="dati">{e(d["estensione"] or "")} · '
                f'{_peso(d["byte"] or 0)} · modificato il {quando} · '
                f'in «{e(d["radice"] or "")}»{sparito}</span>{com_e}'
                f'<span class="strada" style="max-width:520px">{e(d["percorso"])}</span>'
                f'<a href="{apri}"{_scheda(apri)}>apri</a>'
                f'<a href="/mostra?percorso={p}" target="_blank">mostra nella cartella</a>'
                f'<button type="button" class="cestino" data-id="{d["id"]}" '
                f'data-percorso="{e(d["percorso"])}"{diverso} onclick="cestina(this)"{spento}>'
                f'Sposta nel Cestino</button></div>')
        if g["tutti_identici"]:
            quanti = f'{g["copie"]} copie identiche'
        elif not g["stesso_testo"]:
            quanti = f'{g["copie"]} file che cominciano con lo stesso testo'
        else:
            quanti = f'{g["copie"]} file con lo stesso testo'
        corpo.append(f'<div class="gruppo"><b>{e(g["documenti"][0]["nome"][:90])}</b> '
                     f'<span class="meta">{quanti} · {_peso(g["byte"])} in tutto</span>'
                     f'{"".join(righe)}</div>')
    if len(gruppi) > 150:
        corpo.append(f'<p class="meta">Mostro i 150 gruppi più pesanti su {_numero(len(gruppi))}.</p>')
    corpo.append("</div>")
    sotto = (f"{_numero(len(gruppi))} gruppi con lo stesso testo · circa {_peso(sprecato)} "
             f"di copie identiche")
    return _pagina(sotto, risultati="".join(corpo), radice=radice)


def _nel_cestino(percorso):
    """Sposta un file nel Cestino di Windows, da cui si recupera.

    Solo su un disco del computer: su un disco di rete o una chiavetta il
    Cestino non c'è, e Windows il file lo cancellerebbe per sempre. Lì ci si
    rifiuta.
    """
    if sys.platform.startswith("linux"):
        # il Cestino di Linux (lo stesso del file manager), con gio: «gio trash» non
        # cancella mai per sempre — dove il Cestino non c'è (un disco di rete, una
        # chiavetta senza cestino) si rifiuta, e qui lo si dice
        import shutil as _sh
        if not _sh.which("gio"):
            raise RuntimeError("manca «gio» (pacchetto libglib2.0-bin): senza, il Cestino non lo uso")
        r = subprocess.run(["gio", "trash", os.path.abspath(percorso)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("non l'ho spostato nel Cestino: " + (r.stderr.strip() or "errore di gio")[:200])
        return
    if sys.platform != "win32":
        raise RuntimeError("lo spostamento nel Cestino è previsto solo su Windows e Linux")
    import ctypes
    from ctypes import wintypes
    assoluto = os.path.abspath(percorso)
    disco = os.path.splitdrive(assoluto)[0] + "\\"
    if ctypes.windll.kernel32.GetDriveTypeW(disco) != 3:            # DRIVE_FIXED
        raise RuntimeError("il file non sta su un disco del computer: lì il Cestino non "
                           "c'è, e non lo cancello per sempre")

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO = 3, 0x4, 0x10, 0x40
    FOF_NOERRORUI, FOF_WANTNUKEWARNING = 0x400, 0x4000
    op = SHFILEOPSTRUCTW(None, FO_DELETE, assoluto + "\0", None,
                         FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT |
                         FOF_NOERRORUI | FOF_WANTNUKEWARNING, False, None, None)
    esito = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if esito != 0 or op.fAnyOperationsAborted:
        raise RuntimeError(f"Windows non l'ha spostato (codice {esito})")


@app.post("/cestina")
def cestina(dati: dict):
    """Una copia di un doppione va nel Cestino, ed esce dall'indice."""
    id_doc = int(dati.get("id") or 0)
    c = archivio.apri()
    r = c.execute("SELECT id, percorso, impronta FROM documenti WHERE id=?", (id_doc,)).fetchone()
    if not r:
        return JSONResponse({"errore": "Non trovo questo documento nell'archivio."})
    if not r["impronta"]:
        return JSONResponse({"errore": "Questo documento non fa parte di un gruppo di copie."})
    altre = [x["percorso"] for x in c.execute(
        "SELECT percorso FROM documenti WHERE impronta=? AND id<>?", (r["impronta"], id_doc))
        if os.path.exists(x["percorso"])]
    if not altre:
        return JSONResponse({"errore": "È l'ultima copia rimasta di questo documento: "
                                       "non la sposto."})
    if os.path.exists(r["percorso"]):
        try:
            _nel_cestino(r["percorso"])
        except Exception as exc:
            return JSONResponse({"errore": f"Non l'ho spostato: {exc}"})
        if os.path.exists(r["percorso"]):
            return JSONResponse({"errore": "Windows non l'ha spostato: il file è ancora lì."})
    archivio.togli_documento(c, id_doc)
    c.commit()
    return JSONResponse({"ok": True, "restano": len(altre)})


@app.get("/esporta")
def esporta(q: str, modo: str = "tesauro", limite: int = 40, nome: str = "", radice: str = ""):
    voci = _unisci(q, modo, limite, radice or None)
    base = strumenti.esporta(voci, nome or None)
    return JSONResponse({"cartella": base, "documenti": len(voci)})


@app.get("/api/sfoglia")
def api_sfoglia(percorso: str = ""):
    return JSONResponse(navigatore.elenca(percorso))


@app.get("/api/finestra")
def api_finestra():
    """Apre la finestra di sistema. Funziona perché server e utente sono lo
    stesso computer: su una macchina remota non avrebbe senso."""
    if not navigatore.disponibile_finestra():
        return JSONResponse({"non_disponibile": True})
    scelto = navigatore.finestra_di_sistema()
    import os as _os
    return JSONResponse({"percorso": scelto or "",
                         "nome_breve": _os.path.basename(scelto.rstrip("\\/")) if scelto else ""})


# ------------------------------------------------- trascrizioni in .md ---

_ULTIMO_RAPPORTO = {"testo": "", "quando": 0}


def _trascrivi_in_fondo(id_lavoro, percorsi, rifai=False):
    import time as _t

    def riferisci(riga):
        archivio.aggiorna_lavoro(id_lavoro, riga=str(riga)[:200])

    def avanza(fatti, totale, nome):
        archivio.aggiorna_lavoro(id_lavoro, fatti=fatti, totale=totale,
                                 messaggio=f"{fatti}/{totale}: {nome}")
    try:
        esiti = trascrizioni.trascrivi_molti(percorsi, avviso=riferisci, progresso=avanza,
                                             smetti=lambda: archivio.da_fermare(id_lavoro), rifai=rifai)
        dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "esportazioni", "rapporto_trascrizioni.md")
        _ULTIMO_RAPPORTO["testo"] = trascrizioni.rapporto(esiti, dest)
        _ULTIMO_RAPPORTO["quando"] = _t.time()
        scritti = sum(1 for e in esiti if e.get("esito") in ("scritto", "riscritto"))
        collaz = sum(1 for e in esiti if e.get("esito") == "collazionato")
        sospetti = sum(1 for e in esiti if e.get("giudizio", "").startswith(("GRAVE", "SOSPETTO")))
        messaggio = f"{scritti} .md scritti, {collaz} gia esistenti collazionati"
        if sospetti:
            messaggio += f", {sospetti} da guardare"
        fermato = archivio.da_fermare(id_lavoro)
        if fermato:
            messaggio = "fermato a metà — " + messaggio
        archivio.aggiorna_lavoro(id_lavoro, stato="fermato" if fermato else "finito",
                                 messaggio=messaggio, finito=_t.time(), riga=messaggio)
    except Exception as exc:
        archivio.aggiorna_lavoro(id_lavoro, stato="errore",
                                 messaggio=f"{type(exc).__name__}: {exc}"[:200],
                                 finito=_t.time())


@app.post("/trascrivi")
def avvia_trascrizione(dati: dict):
    """Crea i .md: dei PDF di una ricerca, di un file solo, o di una cartella."""
    if dati.get("percorsi"):
        percorsi = [p for p in dati["percorsi"] if _noto(p)]
        etichetta = os.path.basename(percorsi[0]) if percorsi else ""
    elif dati.get("radice"):
        docs_r = archivio.documenti_di(dati["radice"])
        con_md = coppie.coppie(docs_r)
        percorsi = [x["percorso"] for x in docs_r
                    if x["estensione"] == ".pdf"
                    and not (dati.get("solo_senza_md") and x["percorso"] in con_md)]
        etichetta = dati["radice"]
    else:
        q = (dati.get("q") or "").strip()
        if not q:
            return JSONResponse({"errore": "nessuna ricerca da cui partire"})
        voci = _unisci(q, dati.get("modo") or "tesauro", 200, dati.get("radice") or None)
        percorsi = [v["percorso"] for v in voci]
        etichetta = q
    if not percorsi:
        return JSONResponse({"errore": "non c'è nessun PDF a cui fare il .md"})
    errore = _occupato()
    if errore:
        return JSONResponse({"errore": errore})
    id_lavoro = archivio.nuovo_lavoro("trascrivi", "", etichetta)
    t = threading.Thread(target=_trascrivi_in_fondo,
                         args=(id_lavoro, percorsi, bool(dati.get("rifai")) and bool(dati.get("percorsi"))),
                         daemon=True)
    t.start()
    _LAVORI[id_lavoro] = t
    return JSONResponse({"lavoro": id_lavoro, "documenti": len(percorsi)})


@app.get("/rapporto_md", response_class=HTMLResponse)
def rapporto_md():
    testo = _ULTIMO_RAPPORTO["testo"] or "Nessuna trascrizione ancora eseguita."
    return _pagina("rapporto delle trascrizioni",
                   '<div class="pannello"><pre style="white-space:pre-wrap;font:13.5px Georgia,serif">'
                   + html.escape(testo) + "</pre></div>")
