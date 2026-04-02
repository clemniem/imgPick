# Roadmap — imgPick

Jede Story ist eine abgeschlossene, testbare Einheit. Stories innerhalb eines Epics bauen aufeinander auf. Epics können teilweise parallel bearbeitet werden (siehe Abhängigkeiten).

---

## Epic 1: Projekt-Setup

### Story 1.1: Projekt initialisieren
- `uv init` ausführen, `pyproject.toml` mit allen Dependencies erstellen
- Python 3.11+ als Mindestversion festlegen
- `.gitignore` anlegen (Python, __pycache__, .venv, etc.)
- `uv sync` erfolgreich durchlaufen lassen
- **Akzeptanzkriterium:** `uv run python -c "import cv2, PIL, torch; print('ok')"` funktioniert

### Story 1.2: ffmpeg-Prüfung
- Hilfsfunktion `check_ffmpeg()` die prüft ob ffmpeg installiert ist (`shutil.which`)
- Klare Fehlermeldung mit Installationshinweis je nach Plattform
- **Akzeptanzkriterium:** Funktion gibt Pfad zurück oder wirft Fehler mit Installationsanleitung

---

## Epic 2: EXIF-Reader (`exif_reader.py`)

### Story 2.1: Aufnahmedatum auslesen
- Funktion `read_exif(path) -> ExifData` die EXIF-Daten aus Fotos liest
- Aufnahmedatum extrahieren (EXIF DateTimeOriginal)
- Fallback auf Datei-mtime wenn kein EXIF-Datum
- Warnung wenn weder EXIF noch sinnvolles mtime vorhanden
- Unterstützte Formate: JPG, JPEG, PNG, HEIC, WEBP, TIFF
- **Akzeptanzkriterium:** Gibt korrektes Datum für JPG mit EXIF zurück; gibt Fallback-Datum + Warnung für Datei ohne EXIF

### Story 2.2: GPS-Koordinaten auslesen
- GPS-Daten aus EXIF extrahieren (optional, kann None sein)
- In `ExifData`-Dataclass aufnehmen
- **Akzeptanzkriterium:** Gibt GPS-Koordinaten für Foto mit GPS-Tags zurück, None für Fotos ohne

---

## Epic 3: Foto-Scoring (`scorer.py`)

### Story 3.1: Technischer Score
- Funktion `score_technical(image) -> TechScore`
- Schärfe: Laplacian-Varianz, normalisiert via `min(1.0, variance / 500)`
- Helligkeit: Mittlerer Pixelwert, Score 1.0 im Bereich 80–180, linearer Abzug außerhalb
- Kontrast: Standardabweichung der Luminanz, normalisiert via `min(1.0, std / 80)`
- Auflösung: `min(1.0, megapixels / 12)`
- Gewichteter Durchschnitt als Gesamtwert
- HEIC-Support via pillow-heif
- **Akzeptanzkriterium:** Scharfes helles Foto bekommt Score > 0.7, unscharfes dunkles < 0.4

### Story 3.2: CLIP-Score
- Funktion `score_clip(image, positive_prompts, negative_prompts) -> float`
- CLIP-Modell laden (open_clip, ViT-B-32)
- Bild-Embedding berechnen
- Kosinus-Ähnlichkeit gegen positive und negative Prompts
- Score = Positiv − Negativ, normalisiert via `max(0, min(1, (raw + 1) / 2))`
- Embedding zurückgeben (für Dedup wiederverwendbar)
- **Akzeptanzkriterium:** Schönes Urlaubsfoto scored höher als verwackeltes Foto bei Default-Prompts

### Story 3.3: Batch-CLIP-Inference
- CLIP-Embeddings in Batches berechnen (z.B. 32 Bilder gleichzeitig)
- Performanter als Einzelbild-Inference
- **Akzeptanzkriterium:** 100 Bilder in unter 30s auf CPU

### Story 3.4: Gesamt-Score kombinieren
- Funktion `score_photo(path, clip_model, prompts, tech_weight) -> PhotoResult`
- Kombiniert technischen Score + CLIP-Score mit konfigurierbarem Gewicht
- Falls `--no-clip`: 100% technischer Score
- Gibt `PhotoResult` zurück (Score, Datum, Embedding, Pfad)
- **Akzeptanzkriterium:** Mit `tech_weight=0.4` und CLIP aktiv: Gesamt = 0.4 * tech + 0.6 * clip

---

## Epic 4: Duplikaterkennung (`deduplicator.py`)

**Abhängigkeit:** Epic 3 (braucht Embeddings/Scores aus dem Scorer)

### Story 4.1: Serien-Erkennung (O(n))
- Fotos nach Aufnahmedatum sortieren
- Sequentiell Foto[n] mit Foto[n+1] vergleichen
- Mit CLIP: Kosinus-Ähnlichkeit >= Schwellenwert → selbe Serie
- Ohne CLIP: pHash Hamming-Distanz <= Schwellenwert → selbe Serie
- Pro Serie nur das Foto mit dem höchsten Score behalten
- **Akzeptanzkriterium:** 5 fast identische Strandfotos hintereinander → 1 Serie, bestes wird behalten

### Story 4.2: Serien-Quervergleich (O(s²))
- Repräsentanten (Embedding/Hash des besten Fotos) aller Serien paarweise vergleichen
- Ähnliche Serien zusammenführen
- **Akzeptanzkriterium:** Gleiches Motiv morgens und abends fotografiert → Serien werden zusammengeführt

### Story 4.3: pHash-Fallback
- `imagehash`-Bibliothek für Perceptual Hashing
- Wird verwendet wenn `--no-clip` aktiv
- Hamming-Distanz als Ähnlichkeitsmetrik (Standard-Schwelle: ≤ 8)
- **Akzeptanzkriterium:** Dedup funktioniert auch mit `--no-clip`, erkennt fast identische Fotos

---

## Epic 5: Video-Verarbeitung (`video_processor.py`)

### Story 5.1: Video-Erkennung und Kategorisierung
- Funktion `categorize_videos(paths, threshold_seconds) -> (short_clips, long_videos)`
- Dauer per OpenCV oder ffprobe ermitteln
- Einteilung in Kurzclips (< Schwelle) und lange Videos (>= Schwelle)
- **Akzeptanzkriterium:** 45s-Clip wird als Kurzclip erkannt, 10-Min-Video als lang

### Story 5.2: Kurzclip-Scoring (UC2)
- Funktion `score_short_clip(path, clip_model, prompts) -> ClipResult`
- 10 gleichmäßig verteilte Frames samplen
- Jeden Frame auf Schärfe + Helligkeit bewerten
- Optional: CLIP-Score auf gesampelten Frames
- CLIP-Embedding pro Clip = Durchschnitt der Frame-Embeddings
- Gesamtscore = Durchschnitt aller Frame-Scores
- **Akzeptanzkriterium:** Verwackelter dunkler Clip scored niedriger als stabiler heller Clip

### Story 5.3: Kurzclip-Deduplizierung (UC2)
- Clip-Embeddings paarweise vergleichen (Kosinus-Ähnlichkeit)
- Ähnliche Clips gruppieren, pro Gruppe besten behalten
- Nur wenn CLIP aktiv und Dedup aktiviert
- **Akzeptanzkriterium:** Zwei fast identische Clips → nur der bessere bleibt

### Story 5.4: Highlight-Extraktion (UC3)
- Funktion `extract_highlights(path, max_clips, clip_model) -> list[HighlightScene]`
- Szenenerkennung mit PySceneDetect (AdaptiveDetector)
- Szenen-Mittelpunkt bewerten (Schärfe, Helligkeit, optional CLIP)
- Beste N Szenen auswählen, Start-/End-Timecodes zurückgeben
- **Akzeptanzkriterium:** 30-Min-Video → Liste mit 2 Szenen inkl. Timecodes und Scores

### Story 5.5: Clip-Export via FFmpeg
- Funktion `export_clip(input_path, start, end, output_path)`
- FFmpeg stream copy (kein Re-Encoding)
- `shutil.which('ffmpeg')` für plattformunabhängigen Pfad
- **Akzeptanzkriterium:** Exportierter Clip spielt korrekt ab, hat erwartete Dauer (±1s Keyframe-Genauigkeit)

---

## Epic 6: Export (`exporter.py`)

**Abhängigkeit:** Epic 2 (EXIF-Daten für Sortierung), Epic 3–5 (Ergebnisse)

### Story 6.1: Fotos kopieren und sortieren
- Ausgewählte Fotos in Ausgabeordner kopieren
- Chronologisch nach Aufnahmedatum sortiert
- Prefix-Nummerierung: `001_originalname.jpg`, `002_...`
- Warnung bei fehlendem Datum, Datei ans Ende sortieren
- **Akzeptanzkriterium:** Ausgabeordner enthält nummerierte Fotos in chronologischer Reihenfolge

### Story 6.2: Videos kopieren und Clips exportieren
- Ausgewählte Kurzclips in `videos/` kopieren
- Highlight-Clips via FFmpeg in `videos/` exportieren
- Chronologisch sortiert mit Prefix
- **Akzeptanzkriterium:** `videos/`-Unterordner enthält kopierte Kurzclips + exportierte Highlights

### Story 6.3: JSON-Bericht
- `report.json` mit allen Scores, Einstellungen, Statistiken
- Alle Dateien aufgelistet (ausgewählt und aussortiert)
- Duplikat-Gruppen dokumentiert
- **Akzeptanzkriterium:** JSON ist valide, enthält korrekte Zahlen für total/selected/duplicates

---

## Epic 7: CLI (`main.py`)

**Abhängigkeit:** Epic 1–6

### Story 7.1: Argument-Parsing
- argparse mit allen Flags laut Plan (--top-percent, --no-clip, --dry-run, etc.)
- Sinnvolle Defaults, Validierung der Eingaben
- Fehler wenn `--no-clip` ohne `--no-dedup` und kein pHash-Fallback gewünscht → Hinweis
- **Akzeptanzkriterium:** `python main.py --help` zeigt alle Optionen korrekt an

### Story 7.2: Pipeline verdrahten
- Schritte 1–10 aus dem Plan zusammenstecken
- Fortschrittsprotokoll auf stdout (STATUS/PROGRESS/ERROR/WARN-Format)
- try/except pro Datei — bei Fehler Warnung ausgeben und weitermachen
- **Akzeptanzkriterium:** Kompletter Durchlauf mit echtem Fotoordner, Ausgabeordner korrekt befüllt

### Story 7.3: Dry-Run-Modus
- `--dry-run`: Alles bewerten, Report erstellen, aber keine Dateien kopieren/exportieren
- **Akzeptanzkriterium:** Dry-Run erzeugt `report.json` aber keinen Ausgabeordner mit Medien

---

## Epic 8: GUI (`gui.py`)

**Abhängigkeit:** Epic 7 (CLI muss funktionieren)

### Story 8.1: Grundfenster mit Eingabefeldern
- customtkinter-Fenster mit allen Eingaben laut Plan:
  - Ordner-Auswahl (Input/Output) via Datei-Browser
  - Schieberegler: % Fotos, % Kurzclips, Max Highlights, Clip-Schwelle, Dedup-Schwelle, Tech-Weight
  - Checkboxen: CLIP, Dedup, Videos, Rekursiv, Dry-Run
  - Textfelder: Positive/Negative CLIP-Prompts
- **Akzeptanzkriterium:** Fenster öffnet, alle Eingabefelder sichtbar und bedienbar

### Story 8.2: CLI-Aufruf und Fortschritt
- Start-Button baut CLI-Befehl zusammen aus den Eingabefeldern
- Startet `main.py` als Subprocess
- Parst stdout (PROGRESS/STATUS-Zeilen) für Fortschrittsbalken
- Zeigt Log-Ausgabe live im Fenster
- Start-Button wird deaktiviert während Verarbeitung läuft
- **Akzeptanzkriterium:** Fortschrittsbalken bewegt sich, Log-Fenster zeigt Live-Output

### Story 8.3: Zusammenfassung und Abschluss
- Am Ende: Zusammenfassung anzeigen (Fotos behalten, Duplikate entfernt, Clips)
- Button "Ausgabeordner öffnen" (plattformabhängig: open/startfile/xdg-open)
- **Akzeptanzkriterium:** Zusammenfassung korrekt, Ordner öffnet sich im Dateibrowser

---

## Abhängigkeiten zwischen Epics

```
Epic 1 (Setup)
  ↓
Epic 2 (EXIF) ──────────────────────┐
  ↓                                  │
Epic 3 (Foto-Scoring)               │
  ↓                                  │
Epic 4 (Duplikaterkennung)           │
                                     │
Epic 5 (Video) — unabhängig von 4   │
  ↓                                  ↓
Epic 6 (Export) ← braucht 2, 3, 4, 5
  ↓
Epic 7 (CLI) ← braucht alles
  ↓
Epic 8 (GUI) ← braucht 7
```

**Parallel möglich:**
- Epic 2 + Epic 5 (EXIF und Video sind unabhängig voneinander)
- Story 3.1 (Tech-Score) + Story 4.3 (pHash) — keine Abhängigkeit
- Epic 4 und Epic 5 können parallel, sobald Epic 3 fertig ist

---

## Meilensteine

### M1: Foto-Pipeline funktioniert (Epic 1–4, 6.1, 6.3, 7.1–7.2)
- Fotos bewerten, deduplizieren, auswählen, kopieren — alles via CLI
- Kein Video, keine GUI

### M2: Video-Support (Epic 5, 6.2)
- Kurzclips bewerten + kopieren
- Highlights extrahieren + exportieren

### M3: Fertige App (Epic 7.3, 8)
- Dry-Run, GUI, alles zusammen
