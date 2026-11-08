# Installa tutto quello che serve a Scaffale, su Windows 10 o 11.
#
# Si lancia con un doppio clic su «Installa Scaffale.bat». Fa, nell'ordine:
#   1. Python (se manca)              — con winget, il programma di Windows per installare
#   2. i pacchetti Python di Scaffale — da requisiti.txt
#   3. Tesseract (se manca)           — per leggere le scansioni
#   4. Ollama (se manca) e i tre modelli: bge-m3, qwen3:8b, glm-ocr
#   5. il controllo finale (prepara.py) e l'icona sul desktop
# Quello che c'è già lo lascia com'è. Si può rilanciare quante volte si vuole:
# riprende da quello che manca.
param([switch]$SenzaCollegamento)

$ErrorActionPreference = "Continue"
$QUI = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $QUI
$problemi = @()

function Titolo($t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan; Write-Host "  $('-' * $t.Length)" }
function Ok($t)     { Write-Host "  [ok]      $t" -ForegroundColor Green }
function Manca($t)  { Write-Host "  [manca]   $t" -ForegroundColor Yellow }
function Dice($t)   { Write-Host "            $t" }

function Aggiorna-Path {
    # dopo un'installazione il PATH nuovo vale solo per le finestre nuove: lo si rilegge
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Trova-Python {
    # «python» può essere il finto Python di Windows che apre lo Store: si prova davvero
    $candidati = @("python", "py",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python313\python.exe")
    foreach ($c in $candidati) {
        try {
            $v = & $c -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 9) { return $c }
        } catch { }
    }
    return $null
}

function Installa-Con-Winget($id, $nome, $extra) {
    Dice "Installo $nome con winget. Se Windows chiede il permesso, rispondi Sì."
    Dice "Se winget chiede di accettare le condizioni d'uso, scrivi Y e premi Invio."
    $argomenti = @("install", "--id", $id, "--exact", "--source", "winget") + $extra
    & winget @argomenti
    Aggiorna-Path
}

Write-Host ""
Write-Host "  SCAFFALE — installazione di tutto quello che serve" -ForegroundColor Cyan
Write-Host "  Ci vogliono da 30 a 60 minuti, quasi tutti di download (circa 10 GB)."
Write-Host "  Serve internet adesso; dopo, Scaffale lavora senza."

# --- spazio libero ---
$disco = Get-PSDrive -Name ($QUI.Substring(0, 1))
$liberi = [math]::Round($disco.Free / 1GB, 1)
if ($liberi -lt 15) {
    Manca "spazio libero sul disco: $liberi GB. Ne servono almeno 15."
    $problemi += "poco spazio sul disco ($liberi GB liberi, ne servono 15)"
}

# --- winget ---
Titolo "0. winget, il programma di Windows per installare"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Manca "winget non c'è su questo computer."
    Dice "Aprilo dal Microsoft Store: cerca «Programma di installazione app» e aggiornalo,"
    Dice "poi rilancia «Installa Scaffale.bat». Apro la pagina dello Store."
    Start-Process "ms-windows-store://pdp/?productid=9NBLGGH4NNS1"
    exit 1
}
Ok "winget c'è"

# --- 1. Python ---
Titolo "1. Python"
$py = Trova-Python
if (-not $py) {
    Installa-Con-Winget "Python.Python.3.13" "Python 3.13" @("--scope", "user",
        "--override", "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0")
    $py = Trova-Python
}
if ($py) { Ok ("Python " + (& $py -c "import sys; print(sys.version.split()[0])")) }
else {
    Manca "Python non si è installato."
    Dice "Scaricalo da https://www.python.org/downloads/ e spunta «Add python.exe to PATH»,"
    Dice "poi rilancia «Installa Scaffale.bat»."
    exit 1
}

# --- 2. i pacchetti Python ---
Titolo "2. I pacchetti Python di Scaffale"
& $py -m pip install -r requisiti.txt --disable-pip-version-check
if ($LASTEXITCODE -eq 0) { Ok "pacchetti installati" }
else {
    Manca "alcuni pacchetti non si sono installati (vedi sopra)."
    $problemi += "pacchetti Python (rilancia l'installazione: spesso è la rete)"
}

# --- 3. Tesseract ---
Titolo "3. Tesseract, per leggere le scansioni"
$tess = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
          "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $tess) {
    Installa-Con-Winget "UB-Mannheim.TesseractOCR" "Tesseract" @()
    $tess = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
              "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($tess) { Ok "Tesseract in $tess (i dizionari delle lingue sono già in Scaffale\tessdata)" }
else { Manca "Tesseract non si è installato."; $problemi += "Tesseract (senza, le scansioni restano senza testo)" }

# --- 4. Ollama e i modelli ---
Titolo "4. Ollama e i tre modelli"
function Trova-Ollama {
    $c = Get-Command ollama -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $p) { return $p }
    return $null
}
function Ollama-Risponde {
    try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 3 | Out-Null; return $true }
    catch { return $false }
}
$ollama = Trova-Ollama
if (-not $ollama) {
    Installa-Con-Winget "Ollama.Ollama" "Ollama" @()
    $ollama = Trova-Ollama
}
if (-not $ollama) {
    Manca "Ollama non si è installato."
    $problemi += "Ollama (senza: niente ricerca per senso, riassunti, domande, .md verificati)"
} else {
    Ok "Ollama in $ollama"
    if (-not (Ollama-Risponde)) {
        $app = Join-Path (Split-Path $ollama) "ollama app.exe"
        if (Test-Path $app) { Start-Process $app -WindowStyle Hidden } else { Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden }
        for ($i = 0; $i -lt 30 -and -not (Ollama-Risponde); $i++) { Start-Sleep -Seconds 2 }
    }
    if (-not (Ollama-Risponde)) {
        Manca "Ollama non si accende."; $problemi += "Ollama installato ma spento: riavvia il computer e rilancia"
    } else {
        $presenti = ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags).Content | ConvertFrom-Json).models.name
        $modelli = @(
            @{ nome = "bge-m3";   cerca = "bge-m3";   a = "la ricerca per senso, circa 1,2 GB" },
            @{ nome = "qwen3:8b"; cerca = "qwen3:8b"; a = "riassunti e risposte, circa 5 GB" },
            @{ nome = "glm-ocr";  cerca = "glm-ocr";  a = "i .md verificati, circa 2 GB" })
        foreach ($m in $modelli) {
            if ($presenti | Where-Object { $_.ToLower().Contains($m.cerca) }) { Ok "$($m.nome) c'è già ($($m.a))"; continue }
            Dice "Scarico $($m.nome): $($m.a)…"
            & $ollama pull $m.nome
            if ($LASTEXITCODE -eq 0) { Ok "$($m.nome) scaricato" }
            else { Manca "$($m.nome) non si è scaricato."; $problemi += "il modello $($m.nome) (rilancia: riprende da dove era)" }
        }
    }
}

# --- 5. controllo finale e icona ---
Titolo "5. Controllo finale"
"" | & $py prepara.py

if (-not $SenzaCollegamento) {
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Scaffale.lnk"))
    $s.TargetPath = (Join-Path $QUI "Avvia Scaffale.bat")
    $s.WorkingDirectory = $QUI
    $s.IconLocation = (Join-Path $QUI "scaffale.ico") + ",0"
    $s.Description = "Scaffale - cerca dentro il tuo archivio"
    $s.Save()
    Ok "icona «Scaffale» sul desktop"
}

Write-Host ""
if ($problemi.Count -eq 0) {
    Write-Host "  TUTTO PRONTO. Per usare Scaffale: doppio clic sull'icona «Scaffale» sul desktop." -ForegroundColor Green
} else {
    Write-Host "  QUASI PRONTO. Manca ancora:" -ForegroundColor Yellow
    foreach ($p in $problemi) { Write-Host "    - $p" -ForegroundColor Yellow }
    Write-Host "  Rilancia «Installa Scaffale.bat»: rifà solo quello che manca."
}
