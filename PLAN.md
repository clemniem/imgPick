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
- CLIP-Embeddings aller Fotos berechnen
- Kosinus-Ähnlichkeit zwischen Bildern vergleichen
- Ähnliche Bilder (Schwellenwert konfigurierbar, Standard 0.95) zu Gruppen zusammenfassen
- Pro Gruppe nur das qualitativ beste Bild behalten

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
- Unterstützte Formate: MP4, MOV, AVI, MKV, M4V, MTS

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
- Checkbox: CLIP-Modell verwenden (ja/nein)
- Checkbox: Duplikat-Check (ja/nein)
- Checkbox: Videos verarbeiten (ja/nein)
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
  --verbose                   Detaillierte Score-Ausgabe pro Datei
  --json-report PATH          JSON-Bericht speichern (Standard: <output>/report.json)
```

---

## Technischer Stack
- Python 3.11+
- `open-clip-torch` für CLIP-Embeddings
- `opencv-python` für Bildqualitätsbewertung und Videoframes
- `scenedetect[opencv]` für Videoszenenerkennung
- `Pillow` + `pillow-heif` für Bildverarbeitung inkl. HEIC-Support
- `exifread` für EXIF-Metadaten
- `tqdm` für Fortschrittsanzeige (CLI)
- `ffmpeg` (externe Abhängigkeit) für Video-Clip-Export (stream copy)
- `tkinter` für die GUI
- `torch` / `torchvision` für CLIP

---

## Projektstruktur
```
imgPick/
├── PLAN.md
├── main.py              # CLI-Einstiegspunkt (argparse)
├── gui.py               # Tkinter-Oberfläche, ruft main.py als Subprocess auf
├── scorer.py            # Foto-Bewertungslogik (technisch + CLIP)
├── deduplicator.py      # Duplikaterkennung via CLIP-Embeddings
├── video_processor.py   # Szenenerkennung + Clip-Export
├── exif_reader.py       # Metadaten-Extraktion
├── exporter.py          # Datei-Kopieren, Sortierung und Berichterstellung
├── requirements.txt     # Alle Python-Abhängigkeiten
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
- CLI gibt Fortschritt auf stdout aus (maschinenlesbar genug für GUI-Parsing)

### Windows-Kompatibilität
Während der Implementierung muss durchgehend auf Windows-Kompatibilität geachtet werden:
- **Dateipfade**: Immer `pathlib.Path` verwenden, nie Strings mit `/` konkatenieren
- **Ordner öffnen**: Plattformabhängig — `subprocess.Popen(['open', path])` (macOS), `os.startfile(path)` (Windows), `subprocess.Popen(['xdg-open', path])` (Linux)
- **ffmpeg-Aufruf**: Pfad zu ffmpeg darf keine Unix-Annahmen machen (`which` vs. `where`), am besten `shutil.which('ffmpeg')` nutzen
- **Subprocess-Aufrufe**: Kein `shell=True` wenn vermeidbar, und bei `shell=True` beachten dass Windows `cmd.exe` statt `sh` nutzt
- **Encoding**: Dateinamen können auf Windows nicht-UTF-8 sein — bei Dateioperationen auf Encoding achten

---

## Implementierungsreihenfolge

### Phase 1: CLI-Backend
1. Virtualenv + Dependencies installieren
2. `exif_reader.py` — EXIF-Daten (Datum, GPS) aus Fotos lesen
3. `scorer.py` — Technische Bewertung (Schärfe, Helligkeit, Kontrast)
4. `scorer.py` — CLIP-Integration mit konfigurierbaren Prompts
5. `deduplicator.py` — Duplikaterkennung via CLIP-Embeddings + Kosinus-Ähnlichkeit
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
   - Schärfe: Laplacian-Varianz auf Graustufenbild → höher = schärfer
   - Helligkeit: Mittlerer Pixelwert → Abzug wenn zu dunkel (<50) oder zu hell (>220)
   - Kontrast: Standardabweichung der Luminanz → höher = besser
   - Auflösung: Megapixel → kleiner Bonus für hohe Auflösung
4. **CLIP-Score berechnen** (falls aktiviert):
   - Bild-Embedding mit CLIP berechnen
   - Kosinus-Ähnlichkeit zu jedem positiven Prompt → Durchschnitt = Positiv-Score
   - Kosinus-Ähnlichkeit zu jedem negativen Prompt → Durchschnitt = Negativ-Score
   - CLIP-Score = Positiv-Score − Negativ-Score (normalisiert auf 0.0–1.0)
5. **Gesamt-Score**: Gewichteter Durchschnitt aus technischem Score und CLIP-Score
6. **CLIP-Embedding speichern** (wird in Schritt 5 für Duplikaterkennung wiederverwendet)

Ergebnis: Liste aller Fotos mit Score, Datum und Embedding.

### Schritt 5: Foto-Duplikate erkennen (falls aktiviert)
- Voraussetzung: CLIP muss aktiviert sein. Falls `--no-clip` und Dedup aktiv → Fehlermeldung: "Duplikaterkennung benötigt CLIP. Bitte --no-dedup setzen oder CLIP aktivieren."
1. CLIP-Embeddings aller Fotos aus Schritt 4 nehmen
2. Paarweise Kosinus-Ähnlichkeit berechnen
3. Paare mit Ähnlichkeit >= Schwellenwert (z.B. 0.95) finden
4. Zusammenhängende Gruppen bilden (A ähnlich B, B ähnlich C → Gruppe {A, B, C})
5. Pro Gruppe: nur das Foto mit dem höchsten Gesamt-Score behalten, Rest markieren als "Duplikat"
6. Ausgabe: `Duplikate: 45 Fotos in 18 Gruppen erkannt, 27 entfernt`

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
4. **Clips exportieren** via FFmpeg:
   - `ffmpeg -ss <start> -to <end> -c copy -i <input> <output>`
   - Stream copy = schnell, kein Qualitätsverlust
5. Ausgabe: `Video "bootstrip.mp4" (28:15): 2 Highlight-Clips erstellt (02:30–03:15, 14:00–14:45)`

### Schritt 9: Export
1. **Ausgabeordner erstellen** (falls nicht vorhanden)
2. **Fotos kopieren**:
   - Ausgewählte Fotos in den Ausgabeordner kopieren
   - Dateinamen chronologisch nach Aufnahmedatum sortiert (Prefix: `001_`, `002_`, ...)
   - Falls kein EXIF-Datum vorhanden → Warnung ausgeben: `⚠ Kein Aufnahmedatum für beach_001.jpg — Datei wird ans Ende sortiert`
3. **Kurzclips kopieren**:
   - Ausgewählte Kurzclips in Unterordner `videos/` kopieren
   - Ebenfalls chronologisch sortiert
4. **Highlight-Clips**:
   - Bereits in Schritt 8 via FFmpeg in `videos/` exportiert

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
