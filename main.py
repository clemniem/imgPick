#!/usr/bin/env python3
"""imgPick — Lokaler KI-Medienpicker für Urlaubsfotos und -videos."""

import argparse
import sys
from pathlib import Path

from scorer import DEFAULT_POSITIVE_PROMPTS, DEFAULT_NEGATIVE_PROMPTS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="imgpick",
        description="Wählt die besten Fotos und Videos aus einem Urlaubsordner aus.",
    )

    parser.add_argument("input_folder", type=Path, help="Eingabeordner mit Fotos/Videos")
    parser.add_argument("output_folder", type=Path, help="Ausgabeordner für die Auswahl")

    # Photo selection
    parser.add_argument("--top-percent", type=int, default=30,
                        help="Prozent der besten Fotos behalten (Standard: 30)")
    parser.add_argument("--top-percent-videos", type=int, default=50,
                        help="Prozent der besten Kurzclips behalten (Standard: 50)")

    # Video
    parser.add_argument("--max-clips", type=int, default=2,
                        help="Max. Highlight-Clips pro langem Video (Standard: 2)")
    parser.add_argument("--short-clip-threshold", type=int, default=180,
                        help="Videos kürzer als S Sekunden = Kurzclip (Standard: 180)")
    parser.add_argument("--no-video", action="store_true",
                        help="Videos nicht verarbeiten")

    # CLIP
    parser.add_argument("--no-clip", action="store_true",
                        help="CLIP-Modell nicht verwenden")
    parser.add_argument("--positive-prompts", type=str, default=None,
                        help="Komma-getrennte positive CLIP-Prompts")
    parser.add_argument("--negative-prompts", type=str, default=None,
                        help="Komma-getrennte negative CLIP-Prompts")
    parser.add_argument("--tech-weight", type=float, default=0.4,
                        help="Gewicht technischer Score (0.0–1.0, Standard: 0.4)")

    # Dedup
    parser.add_argument("--no-dedup", action="store_true",
                        help="Duplikat-Check überspringen")
    parser.add_argument("--dedup-threshold", type=float, default=0.95,
                        help="Ähnlichkeitsschwelle für Duplikate (Standard: 0.95)")

    # Scan
    parser.add_argument("--no-recursive", action="store_true",
                        help="Eingabeordner nicht rekursiv durchsuchen")

    # Output
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur bewerten und Report erstellen, keine Dateien kopieren")
    parser.add_argument("--verbose", action="store_true",
                        help="Detaillierte Score-Ausgabe pro Datei")
    parser.add_argument("--json-report", type=Path, default=None,
                        help="Pfad für JSON-Bericht (Standard: <output>/report.json)")

    args = parser.parse_args(argv)

    # Validate
    if not args.input_folder.is_dir():
        parser.error(f"Eingabeordner existiert nicht: {args.input_folder}")

    if not 1 <= args.top_percent <= 100:
        parser.error("--top-percent muss zwischen 1 und 100 liegen")

    if not 1 <= args.top_percent_videos <= 100:
        parser.error("--top-percent-videos muss zwischen 1 und 100 liegen")

    if not 0.0 <= args.tech_weight <= 1.0:
        parser.error("--tech-weight muss zwischen 0.0 und 1.0 liegen")

    if not 0.0 < args.dedup_threshold <= 1.0:
        parser.error("--dedup-threshold muss zwischen 0.0 und 1.0 liegen")

    # Parse prompts
    if args.positive_prompts:
        args.positive_prompts = [p.strip() for p in args.positive_prompts.split(",") if p.strip()]
    else:
        args.positive_prompts = list(DEFAULT_POSITIVE_PROMPTS)

    if args.negative_prompts:
        args.negative_prompts = [p.strip() for p in args.negative_prompts.split(",") if p.strip()]
    else:
        args.negative_prompts = list(DEFAULT_NEGATIVE_PROMPTS)

    # Default report path
    if args.json_report is None:
        args.json_report = args.output_folder / "report.json"

    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    # Pipeline will be wired in Story 7.2
    print(f"Input:  {args.input_folder}")
    print(f"Output: {args.output_folder}")


if __name__ == "__main__":
    main()
