# Projekt: Lokaler KI-Medienpicker für Urlaubsfotos und -videos

## Ziel
Lokale Desktop-Applikation (Python), die einen Ordner mit Hunderten von Urlaubsfotos und -videos scannt, die besten Aufnahmen per KI auswählt und in einen neuen Ordner exportiert – bereit zum Hochladen bei Google Photos, Apple Photos oder einem anderen Dienst. Alles läuft lokal, keine Cloud, keine API-Keys.

---

## Use Cases

### UC1: Beste Fotos aus vielen ähnlichen auswählen
**Situation:** Vom Urlaub gibt es 500+ Fotos, oft 5–10 fast identische Aufnahmen vom selben Motiv.
**Was die App tut:** Ähnliche Fotos gruppieren (Duplikaterkennung), pro Gruppe nur das technisch und ästhetisch beste behalten, Rest nach Score sortieren und die Top X% exportieren.
**Ergebnis:** Statt 500 Fotos hat man 150 kuratierte Bilder ohne Duplikate.

### UC2: Beste Kurzclips aus vielen auswählen
**Situation:** Vom Urlaub gibt es viele kurze Clips (15s–3min) — am Strand, beim Essen, in der Stadt. Nicht alle sind sehenswert.
**Was die App tut:** Jeden Clip anhand von Szenenqualität bewerten (Schärfe, Helligkeit der Frames). Die besten Clips als Ganzes in den Ausgabeordner kopieren, den Rest weglassen.
**Ergebnis:** Aus 50 Clips werden die 15 besten ausgewählt und exportiert.

### UC3: Highlights aus einem langen Video extrahieren
**Situation:** Es gibt ein langes Video (z.B. 30 Min Strandspaziergang oder Bootsfahrt), aber nur einzelne Momente sind wirklich sehenswert.
**Was die App tut:** Szenenerkennung im Video, jede Szene bewerten, die N besten Szenen als separate Kurzclips herausschneiden (via FFmpeg stream copy).
**Ergebnis:** Aus einem 30-Min-Video entstehen 2–5 Highlight-Clips von je 10–60 Sekunden.

---

## Architektur

Die App besteht aus zwei Schichten:
- **CLI (Kern)**: Komplette Funktionalität über Kommandozeile nutzbar
- **GUI (Frontend)**: Reines Konfigurationsfenster, das die CLI aufruft — keine eigene Logik

Die GUI baut lediglich den CLI-Befehl zusammen und startet ihn als Subprocess. Dadurch kann man die App auch headless/automatisiert nutzen.

---

## Kernfunktionen

### 1. Foto-Bewertung
- **Technische Qualität**: Schärfe (Laplacian-Varianz), Helligkeit, Kontrast, Auflösung
- **Ästhetische Qualität**: CLIP-Modell (open_clip, ViT-B-32, OpenAI-Gewichte) vergleicht Bilder gegen konfigurierbare Text-Prompts
- Kombinierter Score (0.0–1.0) aus beiden Faktoren
- EXIF-Metadaten auslesen: Aufnahmedatum und GPS wenn vorhanden
- Unterstützte Formate: JPG, JPEG, PNG, HEIC, WEBP, TIFF

### 2. CLIP-Prompt-Konfiguration
- Positive Prompts (Beispiel-Defaults): "a beautiful vacation photo", "a stunning landscape", "happy people on holiday"
- Negative Prompts (Beispiel-Defaults): "a blurry photo", "an overexposed image", "a dark underexposed photo"
- Score = Ähnlichkeit zu positiven Prompts minus Ähnlichkeit zu negativen Prompts
- Prompts sind über CLI-Flags und in der GUI als Textfelder frei editierbar
- So kann man pro Urlaub anpassen (z.B. Strandurlaub vs. Städtetrip vs. Wanderurlaub)

### 3. Duplikaterkennung
Urlaubsfotos entstehen typischerweise in Serien — 5–10 fast identische Aufnahmen direkt hintereinander. Statt alle Bilder gegen alle zu vergleichen (O(n²)), werden Fotos **nach Aufnahmezeit sortiert** und dann **sequentiell n mit n+1 verglichen** (O(n)). Solange aufeinanderfolgende Fotos ähnlich sind, gehören sie zur selben Gruppe. Sobald sich das Bild ändert, beginnt eine neue Gruppe.

**Algorithmus:**
1. Fotos nach Aufnahmedatum sortieren (EXIF, Fallback: Datei-mtime)
2. **Serien erkennen (O(n)):** Sequentiell durchlaufen — Foto[n] mit Foto[n+1] vergleichen. Ähnlich → selbe Serie. Nicht ähnlich → neue Serie beginnt.
3. **Pro Serie:** Bestes Foto behalten, Repräsentant-Embedding/-Hash der Serie speichern (= Embedding/Hash des besten Fotos)
4. **Serien-Quervergleich (O(s²), s = Anzahl Serien):** Repräsentanten aller Serien untereinander vergleichen, um doppelte Serien zu finden (z.B. gleiches Motiv morgens und abends fotografiert). Falls ähnlich → Serien zusammenführen, nur den besten Repräsentanten behalten.
5. Da s << n (typisch: 500 Fotos → ~80 Serien) ist der Quervergleich vernachlässigbar schnell.

**Ähnlichkeitsmetrik — zwei Strategien:**

**Mit CLIP (Standard):**
- CLIP-Embeddings aus der Foto-Bewertung wiederverwenden
- Kosinus-Ähnlichkeit zwischen Nachbarn vergleichen
- Schwellenwert konfigurierbar (Standard 0.95)

**Ohne CLIP (Fallback via Perceptual Hashing):**
- Perceptual Hash (pHash) pro Bild berechnen (`imagehash`-Bibliothek)
- Hamming-Distanz zwischen Nachbarn vergleichen
- Schwellenwert konfigurierbar (Hamming-Distanz ≤ Standard 8)
- Vorteil: deutlich schneller als CLIP, funktioniert auch mit `--no-clip`

### 4. Video-Verarbeitung
Zwei Modi, automatisch unterschieden anhand der Videolänge (Schwelle konfigurierbar, Standard 3 Min):

**Kurzclip-Modus (UC2)** — Videos unter der Schwelle:
- Mehrere Frames gleichmäßig verteilt aus dem Clip samplen
- Jeden Frame auf Schärfe und Helligkeit bewerten → Gesamtscore pro Clip
- Optional: CLIP-Bewertung auf gesampelten Frames
- Clips nach Score ranken, top X% als Ganzes kopieren, Rest weglassen

**Highlight-Modus (UC3)** — Videos über der Schwelle:
- Szenen erkennen mit PySceneDetect (AdaptiveDetector)
- Jeden Szenen-Mittelpunkt per OpenCV auf Schärfe und Helligkeit bewerten
- Die N besten Szenen als separate Kurzclips exportieren via FFmpeg (stream copy, kein Re-Encoding)

**Gemeinsam:**
- Unterstützte Formate: MP4, MOV, AVI, MKV, M4V, MTS (MTS/AVCHD experimentell — abhängig vom OpenCV-Build)

### 5. Auswahl und Export
- Fotos nach Score sortieren, top X% behalten (konfigurierbar)
- Ausgabeordner chronologisch nach Aufnahmedatum sortiert befüllen
- Video-Clips in Unterordner `videos/` exportieren
- JSON-Bericht mit allen Scores, Statistiken und ausgeschlossenen Dateien

### 6. Grafische Oberfläche (GUI)
Reines Konfigurationsfenster für die CLI — keine eigene Verarbeitungslogik.

**Eingaben:**
- Eingabeordner auswählen (Datei-Browser)
- Ausgabeordner auswählen (Datei-Browser)
- Schieberegler: "Wie viel % behalten?" (10–100%, Standard 30%)
- Schieberegler: "% Kurzclips behalten" (10–100%, Standard 50%)
- Schieberegler: "Max. Highlight-Clips pro langem Video" (1–5, Standard 2)
- Schieberegler: "Kurzclip-Schwelle in Sekunden" (60–600, Standard 180)
- Schieberegler: "Duplikat-Schwellenwert" (0.80–1.00, Standard 0.95)
- Schieberegler: "Gewicht technischer Score" (0.0–1.0, Standard 0.4)
- Checkbox: CLIP-Modell verwenden (ja/nein)
- Checkbox: Duplikat-Check (ja/nein)
- Checkbox: Videos verarbeiten (ja/nein)
- Checkbox: Rekursiv scannen (ja/nein, Standard ja)
- Checkbox: Dry-Run — nur bewerten, nicht kopieren (ja/nein)
- **Textfelder für CLIP-Prompts:**
  - Positive Prompts (mehrzeilig, ein Prompt pro Zeile)
  - Negative Prompts (mehrzeilig, ein Prompt pro Zeile)

**Ablauf:**
- Start-Button baut den CLI-Befehl zusammen und startet ihn als Subprocess
- Fortschrittsbalken + Log-Ausgabe (stdout der CLI wird live angezeigt)
- Am Ende: Zusammenfassung (X Fotos behalten, X Duplikate entfernt, X Kurzclips behalten, X Highlight-Clips erstellt)
- Button "Ausgabeordner öffnen"

---

## CLI-Interface

```
python main.py <input_folder> <output_folder> [options]

Optionen:
  --top-percent N             Prozent der besten Fotos behalten (Standard: 30)
  --top-percent-videos N      Prozent der besten Kurzclips behalten (Standard: 50)
  --max-clips N               Max. Highlight-Clips pro langem Video (Standard: 2)
  --short-clip-threshold S    Videos kürzer als S Sekunden = Kurzclip-Modus (Standard: 180)
  --no-clip                   CLIP-Modell nicht verwenden
  --no-dedup                  Duplikat-Check überspringen
  --no-video                  Videos nicht verarbeiten
  --dedup-threshold F         Ähnlichkeitsschwelle für Duplikate (Standard: 0.95)
  --positive-prompts P        Komma-getrennte positive CLIP-Prompts
  --negative-prompts P        Komma-getrennte negative CLIP-Prompts
  --tech-weight F             Gewicht des technischen Scores (0.0–1.0, Standard: 0.4, Rest = CLIP)
  --no-recursive              Eingabeordner nicht rekursiv durchsuchen
  --dry-run                   Nur bewerten und Report erstellen, keine Dateien kopieren
  --verbose                   Detaillierte Score-Ausgabe pro Datei
  --json-report PATH          JSON-Bericht speichern (Standard: <output>/report.json)
```

---

## Technischer Stack
- Python 3.11+ (verwaltet via `uv`)
- `uv` für Projektmanagement, Dependencies und Virtualenv
- `open-clip-torch` für CLIP-Embeddings
- `opencv-python` für Bildqualitätsbewertung und Videoframes
- `scenedetect[opencv]` für Videoszenenerkennung
- `Pillow` + `pillow-heif` für Bildverarbeitung inkl. HEIC-Support
- `imagehash` für Perceptual Hashing (Duplikaterkennung ohne CLIP)
- `exifread` für EXIF-Metadaten
- `tqdm` für Fortschrittsanzeige (CLI)
- `ffmpeg` (externe Abhängigkeit) für Video-Clip-Export (stream copy)
- `customtkinter` für die GUI (moderner Look, basiert auf tkinter)

---

## Projektstruktur
```
imgPick/
├── PLAN.md
├── pyproject.toml       # uv-Projektdefinition + Dependencies
├── main.py              # CLI-Einstiegspunkt (argparse)
├── gui.py               # customtkinter-Oberfläche, ruft main.py als Subprocess auf
├── scorer.py            # Foto-Bewertungslogik (technisch + CLIP)
├── deduplicator.py      # Duplikaterkennung (CLIP + pHash-Fallback)
├── video_processor.py   # Szenenerkennung + Clip-Export
├── exif_reader.py       # Metadaten-Extraktion
├── exporter.py          # Datei-Kopieren, Sortierung und Berichterstellung
├── setup.bat            # Windows-Setup: Doppelklick genügt (startet setup.ps1)
├── setup.ps1            # Windows-Setup (PowerShell): installiert alles + erstellt start.bat
└── README.md            # Installationsanleitung
```

---

## Nicht-funktionale Anforderungen
- Läuft auf macOS, Windows und Linux
- Funktioniert ohne GPU (CPU-Fallback für CLIP)
- Bei Fehlern einzelner Dateien weitermachen (try/except pro Datei)
- Keine Originaldateien verändern oder löschen – nur kopieren
- CLIP-Modell beim ersten Start automatisch herunterladen (~350 MB), danach gecacht
- Verarbeitung von 500 Fotos sollte unter 5 Minuten laufen (auf normaler CPU)
- CLIP-Inference in Batches (z.B. 32 Bilder gleichzeitig) für bessere Performance
- Duplikat-Vergleich in O(n) — Fotos nach Zeit sortiert, sequentieller Nachbar-Vergleich
- CLI gibt Fortschritt auf stdout in maschinenlesbarem Format aus (siehe Fortschrittsprotokoll)

### Windows-Kompatibilität
Während der Implementierung muss durchgehend auf Windows-Kompatibilität geachtet werden:
- **Dateipfade**: Immer `pathlib.Path` verwenden, nie Strings mit `/` konkatenieren
- **Ordner öffnen**: Plattformabhängig — `subprocess.Popen(['open', path])` (macOS), `os.startfile(path)` (Windows), `subprocess.Popen(['xdg-open', path])` (Linux)
- **ffmpeg-Aufruf**: Pfad zu ffmpeg darf keine Unix-Annahmen machen (`which` vs. `where`), am besten `shutil.which('ffmpeg')` nutzen
- **Subprocess-Aufrufe**: Kein `shell=True` wenn vermeidbar, und bei `shell=True` beachten dass Windows `cmd.exe` statt `sh` nutzt
- **Encoding**: Dateinamen können auf Windows nicht-UTF-8 sein — bei Dateioperationen auf Encoding achten

### Fortschrittsprotokoll (stdout)
Die CLI gibt Fortschritt in einem strukturierten Format aus, das die GUI parsen kann:
```
STATUS:scan:Gefunden: 500 Fotos, 15 Kurzclips, 3 lange Videos
STATUS:model:CLIP-Modell geladen (ViT-B-32)
PROGRESS:photos:<current>:<total>:<filename>
PROGRESS:dedup:<current>:<total>
PROGRESS:clips:<current>:<total>:<filename>
PROGRESS:videos:<current>:<total>:<filename>
PROGRESS:export:<current>:<total>:<filename>
STATUS:done:Fertig!
ERROR:<message>
WARN:<message>
```
Alle anderen Zeilen (z.B. bei `--verbose`) werden als Info-Log angezeigt, aber nicht geparst.

---

## Implementierungsreihenfolge

### Phase 1: CLI-Backend
1. `uv init` + Dependencies in `pyproject.toml` definieren
2. `exif_reader.py` — EXIF-Daten (Datum, GPS) aus Fotos lesen
3. `scorer.py` — Technische Bewertung (Schärfe, Helligkeit, Kontrast)
4. `scorer.py` — CLIP-Integration mit konfigurierbaren Prompts
5. `deduplicator.py` — Duplikaterkennung via CLIP-Embeddings oder pHash-Fallback
6. `video_processor.py` — Szenenerkennung + Clip-Export
7. `exporter.py` — Dateien kopieren, chronologisch sortieren, JSON-Bericht
8. `main.py` — CLI zusammenbauen (argparse), alles verdrahten
9. Testen mit echtem Fotoordner

### Phase 2: GUI
10. `gui.py` — Tkinter-Fenster mit allen Eingabefeldern
11. CLI-Befehl zusammenbauen und als Subprocess starten
12. Stdout parsen für Fortschrittsbalken und Log
13. Zusammenfassung + "Ordner öffnen" Button

---

## Detaillierter Programmablauf (Schritt für Schritt)

Wenn der Nutzer die App startet (CLI oder GUI), passiert intern folgendes:

### Schritt 1: Eingabe validieren
- Prüfe ob Eingabeordner existiert und lesbar ist
- Prüfe ob Ausgabeordner erstellt werden kann
- Prüfe ob ffmpeg installiert ist (nur wenn Videos verarbeitet werden sollen)
- Bei Fehlern: Abbruch mit klarer Fehlermeldung

### Schritt 2: Dateien scannen und kategorisieren
- Eingabeordner rekursiv durchsuchen
- Jede Datei anhand der Endung kategorisieren:
  - **Fotos**: .jpg, .jpeg, .png, .heic, .webp, .tiff
  - **Videos**: .mp4, .mov, .avi, .mkv, .m4v, .mts
  - **Sonstiges**: wird ignoriert
- Ausgabe: `Gefunden: 500 Fotos, 15 Kurzclips, 3 lange Videos`
- Videos werden anhand ihrer Dauer (via OpenCV/ffprobe) in Kurzclips (< Schwelle) und lange Videos (>= Schwelle) eingeteilt

### Schritt 3: CLIP-Modell laden (falls aktiviert)
- Modell laden (beim ersten Mal ~350 MB Download, danach aus Cache)
- Text-Embeddings für alle konfigurierten Prompts (positiv + negativ) vorberechnen
- Ausgabe: `CLIP-Modell geladen (ViT-B-32)`
- Falls `--no-clip`: Schritt überspringen, nur technische Scores verwenden

### Schritt 4: Fotos bewerten
Für jedes Foto (mit Fortschrittsbalken `[142/500] beach_001.jpg`):

1. **Bild laden** (Pillow, inkl. HEIC via pillow-heif)
2. **EXIF-Daten lesen**: Aufnahmedatum, GPS-Koordinaten (wenn vorhanden)
3. **Technischer Score berechnen** (jeweils 0.0–1.0, dann gewichtet):
   - Schärfe: Laplacian-Varianz auf Graustufenbild → Normalisierung: `min(1.0, variance / 500)` (empirischer Maximalwert, typische Werte 10–1000)
   - Helligkeit: Mittlerer Pixelwert (0–255) → Score = 1.0 im Idealbereich (80–180), linearer Abzug wenn zu dunkel (<80) oder zu hell (>180), Minimum 0.0
   - Kontrast: Standardabweichung der Luminanz → Normalisierung: `min(1.0, std / 80)` (empirischer Maximalwert)
   - Auflösung: Megapixel → `min(1.0, megapixels / 12)` (12 MP als Referenzwert)
4. **CLIP-Score berechnen** (falls aktiviert):
   - Bild-Embedding mit CLIP berechnen
   - Kosinus-Ähnlichkeit zu jedem positiven Prompt → Durchschnitt = Positiv-Score
   - Kosinus-Ähnlichkeit zu jedem negativen Prompt → Durchschnitt = Negativ-Score
   - CLIP-Score = Positiv-Score − Negativ-Score, normalisiert via Clamp auf [0, 1]: `max(0, min(1, (raw_score + 1) / 2))`
5. **Gesamt-Score**: Gewichteter Durchschnitt aus technischem Score und CLIP-Score
   - Standard-Gewichte: 40% technisch, 60% CLIP (konfigurierbar via `--tech-weight`)
   - Falls `--no-clip`: 100% technischer Score
6. **CLIP-Embedding speichern** (wird in Schritt 5 für Duplikaterkennung wiederverwendet)

Ergebnis: Liste aller Fotos mit Score, Datum und Embedding.

### Schritt 5: Foto-Duplikate erkennen (falls aktiviert)
- Falls CLIP aktiv: CLIP-Embeddings aus Schritt 4 verwenden (Kosinus-Ähnlichkeit)
- Falls `--no-clip`: Fallback auf Perceptual Hashing (pHash, Hamming-Distanz)

**Phase A — Serien erkennen (O(n)):**
1. Fotos nach Aufnahmedatum sortieren (EXIF aus Schritt 4, Fallback: Datei-mtime)
2. Sequentiell durchlaufen: Foto[n] mit Foto[n+1] vergleichen
3. Ähnlichkeit >= Schwellenwert → selbe Serie, sonst neue Serie beginnen
4. Pro Serie: nur das Foto mit dem höchsten Gesamt-Score behalten, Embedding/Hash als Serien-Repräsentant speichern
5. Ausgabe: `Serien: 80 Serien erkannt aus 500 Fotos`

**Phase B — Doppelte Serien finden (O(s²), s = Anzahl Serien):**
6. Repräsentanten aller Serien paarweise vergleichen (gleicher Schwellenwert)
7. Falls Serien-Repräsentanten ähnlich → Serien zusammenführen, nur den besten behalten
8. Ausgabe: `Duplikate: 45 Fotos in 18 Gruppen erkannt, 27 entfernt (davon 3 doppelte Serien zusammengeführt)`

### Schritt 6: Foto-Auswahl
1. Duplikate aus der Liste entfernen
2. Verbleibende Fotos nach Gesamt-Score absteigend sortieren
3. Top X% behalten (z.B. bei 30% und 473 verbleibenden Fotos → 142 behalten)
4. Ausgabe: `Foto-Auswahl: 142 von 500 Fotos behalten (30%)`

### Schritt 7: Kurzclips bewerten und deduplizieren (UC2, falls Videos aktiviert)
Für jeden Kurzclip (< Schwelle, z.B. < 3 Min):

1. **Video öffnen** (OpenCV VideoCapture)
2. **Frames samplen**: z.B. 10 gleichmäßig verteilte Frames aus dem Clip
3. **Jeden Frame bewerten**: Schärfe + Helligkeit (wie bei Fotos)
4. **Optional CLIP-Score**: Durchschnitt über gesampelte Frames
5. **Gesamtscore pro Clip**: Durchschnitt aller Frame-Scores
6. **CLIP-Embedding pro Clip** speichern (Durchschnitt der Frame-Embeddings)

Dann:
7. **Duplikaterkennung** (falls CLIP aktiv und Dedup aktiviert):
   - Clip-Embeddings paarweise vergleichen (Kosinus-Ähnlichkeit)
   - Ähnliche Clips gruppieren (Schwellenwert wie bei Fotos)
   - Pro Gruppe nur den Clip mit dem höchsten Score behalten
   - Ausgabe: `Kurzclip-Duplikate: 12 Clips in 5 Gruppen, 7 entfernt`
8. Verbleibende Clips nach Score sortieren
9. Top X% behalten (z.B. 50%)
10. Ausgabe: `Kurzclips: 8 von 15 Clips behalten (50%)`

### Schritt 8: Lange Videos verarbeiten (UC3, falls Videos aktiviert)
Für jedes lange Video (>= Schwelle):

1. **Szenenerkennung** mit PySceneDetect (AdaptiveDetector)
   - Ergebnis: Liste von Szenen mit Start- und End-Timecodes
2. **Jede Szene bewerten**:
   - Frame aus Szenen-Mitte extrahieren
   - Schärfe + Helligkeit bewerten
   - Optional: CLIP-Score auf dem Frame
3. **Beste N Szenen auswählen** (z.B. Top 2 pro Video)
4. Szenen mit Start-/End-Timecodes und Score merken (noch nicht exportieren)
5. Ausgabe: `Video "bootstrip.mp4" (28:15): 2 Highlight-Szenen ausgewählt (02:30–03:15, 14:00–14:45)`

### Schritt 9: Export
Falls `--dry-run` aktiv: diesen Schritt überspringen, nur den Report erstellen (Schritt 10).

1. **Ausgabeordner erstellen** (falls nicht vorhanden)
2. **Fotos kopieren**:
   - Ausgewählte Fotos in den Ausgabeordner kopieren
   - Dateinamen chronologisch nach Aufnahmedatum sortiert (Prefix: `001_`, `002_`, ...)
   - Falls kein EXIF-Datum vorhanden → Fallback auf Datei-Änderungsdatum (`os.path.getmtime`)
   - Falls auch das nicht sinnvoll → Warnung: `⚠ Kein Aufnahmedatum für beach_001.jpg — Datei wird ans Ende sortiert`
3. **Kurzclips kopieren**:
   - Ausgewählte Kurzclips in Unterordner `videos/` kopieren
   - Ebenfalls chronologisch sortiert
4. **Highlight-Clips exportieren** via FFmpeg:
   - `ffmpeg -ss <start> -to <end> -i <input> -c copy <output>`
   - Stream copy = schnell, kein Qualitätsverlust
   - Zielordner: `videos/`

### Schritt 10: Bericht erstellen
1. **JSON-Bericht** schreiben (`report.json`):
   ```json
   {
     "input_folder": "/pfad/zum/urlaub",
     "settings": { "top_percent": 30, ... },
     "photos": {
       "total": 500,
       "duplicates_removed": 27,
       "selected": 142,
       "files": [
         { "name": "beach_001.jpg", "score": 0.87, "selected": true, "duplicate_of": null },
         ...
       ]
     },
     "short_clips": { "total": 15, "selected": 8, "files": [...] },
     "long_videos": { "total": 3, "highlights_created": 6, "files": [...] }
   }
   ```
2. **Zusammenfassung auf stdout**:
   ```
   ✓ Fertig!
     Fotos:      142 / 500 behalten (27 Duplikate entfernt)
     Kurzclips:    8 / 15 behalten
     Highlights:   6 Clips aus 3 langen Videos erstellt
     Ausgabe:    /pfad/zum/output
   ```

---

## Beispiel-Workflow
1. Nutzer hat 600 Urlaubsfotos + 50 Kurzclips + 3 lange Videos auf dem Computer
2. App starten (GUI oder CLI), Eingabeordner auswählen
3. CLIP-Prompts anpassen: "beautiful beach sunset", "crystal clear water" (Strandurlaub)
4. "Top 30% Fotos, Top 50% Kurzclips behalten" einstellen, Start klicken
5. App scannt Ordner → 600 Fotos, 50 Kurzclips, 3 lange Videos
6. App bewertet alle 600 Fotos (~3 Min), erkennt 80 Duplikate in 30 Gruppen
7. Nach Duplikat-Entfernung: 520 Fotos → Top 30% = 156 Fotos behalten
8. App bewertet 50 Kurzclips → Top 50% = 25 Clips behalten
9. App analysiert 3 lange Videos, erstellt je 2 Highlight-Clips = 6 Clips
10. Ausgabeordner enthält 156 Fotos + 25 Kurzclips + 6 Highlights, chronologisch sortiert
11. Nutzer lädt diesen Ordner direkt bei Google Photos / Apple Photos hoch

---

## Installation & Start

### Voraussetzungen

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **uv** — Paketmanager für Python
  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **ffmpeg** (nur für Video-Verarbeitung) — [ffmpeg.org](https://ffmpeg.org/download.html)
  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu / Debian
  sudo apt install ffmpeg

  # Windows (winget)
  winget install FFmpeg
  ```

### Windows: Schnellstart mit Setup-Script

Für Windows-Nutzer gibt es ein Setup-Script, das alles automatisch erledigt:

```
Doppelklick auf setup.bat
```

Das Script:
1. Prüft ob Python 3.11+ installiert ist — falls nicht, Hinweis mit Download-Link
2. Installiert `uv` automatisch (falls nicht vorhanden)
3. Führt `uv sync` aus (installiert alle Python-Dependencies)
4. Prüft ob ffmpeg installiert ist — falls nicht, installiert es via `winget` (optional)
5. Startet die GUI

Danach reicht ein Doppelklick auf `start.bat` um die GUI zu starten.

### Projekt manuell einrichten (alle Plattformen)

```bash
# Repository klonen
git clone <repo-url>
cd imgPick

# Dependencies installieren (erstellt automatisch ein Virtualenv)
uv sync
```

Beim ersten Start wird das CLIP-Modell automatisch heruntergeladen (~350 MB). Danach wird es aus dem Cache geladen.

### CLI starten

```bash
# Einfachster Aufruf — Top 30% Fotos behalten, alle Defaults
uv run python main.py /pfad/zum/urlaubsordner /pfad/zum/output

# Nur Fotos, kein Video, kein CLIP (schnell, nur technische Bewertung)
uv run python main.py ./fotos ./output --no-clip --no-video

# Strandurlaub mit angepassten Prompts, 40% behalten
uv run python main.py ./urlaub ./auswahl \
  --top-percent 40 \
  --positive-prompts "beautiful beach sunset,crystal clear water,tropical paradise" \
  --negative-prompts "blurry photo,dark image,overexposed"

# Dry-Run — nur bewerten, nichts kopieren
uv run python main.py ./urlaub ./auswahl --dry-run --verbose

# Alles an: Fotos + Videos + Highlights, detaillierte Ausgabe
uv run python main.py ./urlaub ./auswahl \
  --top-percent 30 \
  --top-percent-videos 50 \
  --max-clips 3 \
  --verbose
```

### GUI starten

```bash
uv run python gui.py
```

Das Fenster bietet alle Optionen als Eingabefelder, Schieberegler und Checkboxen. Einfach Eingabe-/Ausgabeordner auswählen, Einstellungen anpassen und "Start" klicken.

### Überprüfen ob alles funktioniert

```bash
# Python-Dependencies prüfen
uv run python -c "import cv2, PIL, open_clip, tqdm; print('Alle Dependencies OK')"

# ffmpeg prüfen (nur für Video nötig)
ffmpeg -version
```
