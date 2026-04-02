# imgPick — Windows Setup Script
# Am einfachsten: Doppelklick auf setup.bat
# Alternativ: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"

trap {
    Write-Host "`n[X] Unerwarteter Fehler: $_" -ForegroundColor Red
    Read-Host "Enter druecken zum Beenden"
    exit 1
}

function Write-Step($msg) {
    Write-Host "`n[$([char]0x2192)] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    [!] $msg" -ForegroundColor Yellow
}

function Write-Fail($msg) {
    Write-Host "    [X] $msg" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  imgPick — Setup fuer Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- Git pruefen / installieren ---
Write-Step "Git pruefen..."
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Warn "Git nicht gefunden."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        $answer = Read-Host "    Git jetzt via winget installieren? (j/n)"
        if ($answer -eq "j" -or $answer -eq "J" -or $answer -eq "y") {
            try {
                & winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + $env:Path
                Write-Ok "Git installiert (ggf. Terminal neu starten fuer PATH-Update)"
            }
            catch {
                Write-Fail "Git-Installation fehlgeschlagen."
                Write-Host "    Manuell installieren: https://git-scm.com/download/win"
                Read-Host "    Enter druecken zum Beenden"
                exit 1
            }
        }
        else {
            Write-Fail "Git wird benoetigt. Bitte manuell installieren: https://git-scm.com/download/win"
            Read-Host "    Enter druecken zum Beenden"
            exit 1
        }
    }
    else {
        Write-Fail "Git nicht gefunden und winget nicht verfuegbar."
        Write-Host "    Bitte Git manuell installieren: https://git-scm.com/download/win"
        Read-Host "    Enter druecken zum Beenden"
        exit 1
    }
}
else {
    Write-Ok "Git gefunden"
}

# --- Python pruefen ---
Write-Step "Python pruefen..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Fail "Python nicht gefunden."
    Write-Host "    Bitte Python 3.11+ installieren: https://www.python.org/downloads/"
    Write-Host "    Wichtig: Bei der Installation 'Add Python to PATH' ankreuzen!"
    Read-Host "    Enter druecken zum Beenden"
    exit 1
}

$pyVersion = & python --version 2>&1
$versionMatch = [regex]::Match($pyVersion, "(\d+)\.(\d+)")
$major = [int]$versionMatch.Groups[1].Value
$minor = [int]$versionMatch.Groups[2].Value

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
    Write-Fail "Python $major.$minor gefunden, aber 3.11+ wird benoetigt."
    Write-Host "    Bitte aktualisieren: https://www.python.org/downloads/"
    Read-Host "    Enter druecken zum Beenden"
    exit 1
}
Write-Ok "Python $major.$minor"

# --- uv pruefen / installieren ---
Write-Step "uv (Paketmanager) pruefen..."
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Warn "uv nicht gefunden — wird jetzt installiert..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        if (-not $uv) {
            throw "uv nach Installation nicht im PATH gefunden"
        }
        Write-Ok "uv installiert"
    }
    catch {
        Write-Fail "uv konnte nicht installiert werden: $_"
        Write-Host "    Manuell installieren: https://docs.astral.sh/uv/getting-started/installation/"
        Read-Host "    Enter druecken zum Beenden"
        exit 1
    }
}
else {
    Write-Ok "uv gefunden"
}

# --- Dependencies installieren ---
Write-Step "Python-Dependencies installieren (kann beim ersten Mal etwas dauern)..."
try {
    & uv sync
    Write-Ok "Dependencies installiert"
}
catch {
    Write-Fail "uv sync fehlgeschlagen: $_"
    Read-Host "    Enter druecken zum Beenden"
    exit 1
}

# --- ffmpeg pruefen / installieren ---
Write-Step "ffmpeg pruefen (fuer Video-Verarbeitung)..."
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Warn "ffmpeg nicht gefunden — wird fuer Video-Verarbeitung benoetigt."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        $answer = Read-Host "    ffmpeg jetzt via winget installieren? (j/n)"
        if ($answer -eq "j" -or $answer -eq "J" -or $answer -eq "y") {
            try {
                & winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
                Write-Ok "ffmpeg installiert (ggf. Terminal neu starten fuer PATH-Update)"
            }
            catch {
                Write-Warn "ffmpeg-Installation fehlgeschlagen. Manuell installieren: https://ffmpeg.org/download.html"
            }
        }
        else {
            Write-Warn "Uebersprungen — Video-Verarbeitung ist ohne ffmpeg nicht verfuegbar."
        }
    }
    else {
        Write-Warn "winget nicht verfuegbar. ffmpeg manuell installieren: https://ffmpeg.org/download.html"
    }
}
else {
    Write-Ok "ffmpeg gefunden"
}

# --- start.bat erstellen ---
Write-Step "start.bat erstellen..."
$batContent = @"
@echo off
cd /d "%~dp0"
uv run python gui.py
pause
"@
Set-Content -Path "start.bat" -Value $batContent -Encoding ASCII
Write-Ok "start.bat erstellt — Doppelklick zum Starten der GUI"

# --- Fertig ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup abgeschlossen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  GUI starten:  Doppelklick auf start.bat" -ForegroundColor White
Write-Host "  CLI starten:  uv run python main.py <input> <output>" -ForegroundColor White
Write-Host ""

$startNow = Read-Host "GUI jetzt starten? (j/n)"
if ($startNow -eq "j" -or $startNow -eq "J" -or $startNow -eq "y") {
    & uv run python gui.py
}
