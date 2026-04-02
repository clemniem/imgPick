#!/usr/bin/env python3
"""imgPick — Lokaler KI-Medienpicker für Urlaubsfotos und -videos."""

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path

from scorer import DEFAULT_POSITIVE_PROMPTS, DEFAULT_NEGATIVE_PROMPTS

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tiff", ".tif"}


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


def log(msg: str) -> None:
    print(msg, flush=True)


def scan_files(input_folder: Path, recursive: bool) -> tuple[list[Path], list[Path]]:
    """Scan input folder and categorize files into photos and videos."""
    from video_processor import VIDEO_EXTENSIONS

    pattern = "**/*" if recursive else "*"
    photos = []
    videos = []

    for f in input_folder.glob(pattern):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in PHOTO_EXTENSIONS:
            photos.append(f)
        elif ext in VIDEO_EXTENSIONS:
            videos.append(f)

    return photos, videos


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # --- Step 1: Validate ---
    if not args.no_video:
        from utils import check_ffmpeg
        check_ffmpeg()

    # --- Step 2: Scan files ---
    photo_paths, video_paths = scan_files(args.input_folder, not args.no_recursive)

    if not args.no_video and video_paths:
        from video_processor import categorize_videos
        short_clips, long_videos = categorize_videos(video_paths, args.short_clip_threshold)
    else:
        short_clips, long_videos = [], []

    log(f"STATUS:scan:Gefunden: {len(photo_paths)} Fotos, {len(short_clips)} Kurzclips, {len(long_videos)} lange Videos")

    if not photo_paths and not short_clips and not long_videos:
        log("ERROR:Keine Medien im Eingabeordner gefunden")
        sys.exit(1)

    # --- Step 3: Load CLIP model ---
    clip_model = None
    pos_features = None
    neg_features = None

    if not args.no_clip:
        from scorer import ClipModel
        log("STATUS:model:Lade CLIP-Modell...")
        clip_model = ClipModel()
        pos_features, neg_features = clip_model.prepare_prompts(
            args.positive_prompts, args.negative_prompts
        )
        log("STATUS:model:CLIP-Modell geladen (ViT-B-32)")

    # --- Step 4: Score photos ---
    from exif_reader import read_exif
    from scorer import score_photo

    photo_results = []
    for i, path in enumerate(photo_paths):
        log(f"PROGRESS:photos:{i + 1}:{len(photo_paths)}:{path.name}")
        try:
            result = score_photo(path, clip_model, pos_features, neg_features, args.tech_weight)
            exif = read_exif(path)
            result.date_taken = exif.date_taken
            result.date_source = exif.date_source
            photo_results.append(result)

            if args.verbose:
                clip_s = f", clip={result.clip_result.score:.3f}" if result.clip_result else ""
                log(f"  {path.name}: tech={result.tech_score.overall:.3f}{clip_s}, overall={result.overall_score:.3f}")
        except Exception as e:
            log(f"WARN:Fehler bei {path.name}: {e}")

    # --- Step 5: Deduplicate photos ---
    duplicates_removed = 0
    kept_photo_indices = list(range(len(photo_results)))

    if not args.no_dedup and len(photo_results) > 1:
        # Sort by date for series detection
        sorted_indices = sorted(
            range(len(photo_results)),
            key=lambda i: photo_results[i].date_taken or datetime.max,
        )

        if not args.no_clip and clip_model is not None:
            from deduplicator import deduplicate_clip
            embeddings = [r.clip_result.embedding for r in photo_results]
            scores = [r.overall_score for r in photo_results]
            kept_photo_indices, groups = deduplicate_clip(
                embeddings, scores, sorted_indices, args.dedup_threshold
            )
        else:
            from deduplicator import deduplicate_phash, compute_phash
            log("PROGRESS:dedup:0:0:pHash berechnen...")
            hashes = []
            for i, r in enumerate(photo_results):
                log(f"PROGRESS:dedup:{i + 1}:{len(photo_results)}")
                hashes.append(compute_phash(r.path))
            scores = [r.overall_score for r in photo_results]
            kept_photo_indices, groups = deduplicate_phash(
                hashes, scores, sorted_indices
            )

        duplicates_removed = len(photo_results) - len(kept_photo_indices)
        log(f"STATUS:dedup:Duplikate: {duplicates_removed} Fotos entfernt")

    # --- Step 6: Select top photos ---
    kept_results = [photo_results[i] for i in kept_photo_indices]
    kept_results.sort(key=lambda r: r.overall_score, reverse=True)

    num_keep = max(1, math.ceil(len(kept_results) * args.top_percent / 100))
    selected_photos = kept_results[:num_keep]

    log(f"STATUS:select:Foto-Auswahl: {len(selected_photos)} von {len(photo_results)} Fotos behalten ({args.top_percent}%)")

    # --- Step 7: Score and deduplicate short clips ---
    selected_clips = []
    clip_dedup_removed = 0

    if short_clips:
        from video_processor import score_short_clip, deduplicate_clips

        clip_scores = []
        for i, info in enumerate(short_clips):
            log(f"PROGRESS:clips:{i + 1}:{len(short_clips)}:{info.path.name}")
            try:
                cs = score_short_clip(
                    info.path, clip_model, pos_features, neg_features, args.tech_weight
                )
                if cs:
                    clip_scores.append(cs)
            except Exception as e:
                log(f"WARN:Fehler bei Clip {info.path.name}: {e}")

        # Deduplicate
        if not args.no_dedup and clip_scores:
            kept_clip_indices = deduplicate_clips(clip_scores, args.dedup_threshold)
            clip_dedup_removed = len(clip_scores) - len(kept_clip_indices)
            clip_scores = [clip_scores[i] for i in kept_clip_indices]
            if clip_dedup_removed > 0:
                log(f"STATUS:dedup_clips:Kurzclip-Duplikate: {clip_dedup_removed} entfernt")

        # Select top percent
        clip_scores.sort(key=lambda c: c.overall_score, reverse=True)
        num_keep_clips = max(1, math.ceil(len(clip_scores) * args.top_percent_videos / 100))
        selected_clips = clip_scores[:num_keep_clips]

        log(f"STATUS:select_clips:Kurzclips: {len(selected_clips)} von {len(short_clips)} behalten ({args.top_percent_videos}%)")

    # --- Step 8: Process long videos ---
    all_highlights = []  # list of dicts for export

    if long_videos:
        from video_processor import extract_highlights

        for i, info in enumerate(long_videos):
            log(f"PROGRESS:videos:{i + 1}:{len(long_videos)}:{info.path.name}")
            try:
                scenes = extract_highlights(
                    info.path, args.max_clips, clip_model, pos_features, neg_features
                )
                for j, scene in enumerate(scenes):
                    all_highlights.append({
                        "input_path": info.path,
                        "start_seconds": scene.start_seconds,
                        "end_seconds": scene.end_seconds,
                        "source_name": info.path.name,
                        "scene_index": j + 1,
                        "score": scene.score,
                    })
                dur = f"{info.duration_seconds / 60:.0f}min"
                scene_desc = ", ".join(
                    f"{s.start_seconds:.0f}s–{s.end_seconds:.0f}s"
                    for s in scenes
                )
                log(f"  {info.path.name} ({dur}): {len(scenes)} Highlights ({scene_desc})")
            except Exception as e:
                log(f"WARN:Fehler bei Video {info.path.name}: {e}")

    # --- Step 9: Export ---
    if not args.dry_run:
        from exporter import export_photos, export_short_clips, export_highlights

        # Photos
        photo_dicts = [
            {"path": r.path, "date_taken": r.date_taken, "date_source": r.date_source}
            for r in selected_photos
        ]
        exported_photos, photo_warnings = export_photos(photo_dicts, args.output_folder)
        for w in photo_warnings:
            log(w)
        log(f"PROGRESS:export:{len(exported_photos)}:{len(exported_photos)}:Fotos exportiert")

        # Short clips
        if selected_clips:
            clip_dicts = [
                {
                    "path": c.path,
                    "date_modified": datetime.fromtimestamp(c.path.stat().st_mtime),
                }
                for c in selected_clips
            ]
            export_short_clips(clip_dicts, args.output_folder)

        # Highlights
        if all_highlights:
            export_highlights(all_highlights, args.output_folder)

    # --- Step 10: Report ---
    from exporter import write_report

    # Build file lists for report
    selected_paths = {r.path for r in selected_photos}
    photo_files = [
        {
            "name": r.path.name,
            "score": round(r.overall_score, 4),
            "selected": r.path in selected_paths,
        }
        for r in photo_results
    ]

    clip_files = [
        {
            "name": cs.path.name,
            "score": round(cs.overall_score, 4),
            "selected": cs in selected_clips,
        }
        for cs in clip_scores
    ] if short_clips else []

    video_files = []
    for info in long_videos:
        scenes = [h for h in all_highlights if h["source_name"] == info.path.name]
        video_files.append({
            "name": info.path.name,
            "duration_seconds": round(info.duration_seconds, 1),
            "scenes": [
                {"start": s["start_seconds"], "end": s["end_seconds"], "score": round(s["score"], 4)}
                for s in scenes
            ],
        })

    settings = {
        "top_percent": args.top_percent,
        "top_percent_videos": args.top_percent_videos,
        "max_clips": args.max_clips,
        "short_clip_threshold": args.short_clip_threshold,
        "no_clip": args.no_clip,
        "no_dedup": args.no_dedup,
        "dedup_threshold": args.dedup_threshold,
        "tech_weight": args.tech_weight,
        "positive_prompts": args.positive_prompts,
        "negative_prompts": args.negative_prompts,
        "dry_run": args.dry_run,
    }

    write_report(
        args.json_report,
        settings=settings,
        photos={
            "total": len(photo_results),
            "duplicates_removed": duplicates_removed,
            "selected": len(selected_photos),
            "files": photo_files,
        },
        short_clips={
            "total": len(short_clips),
            "duplicates_removed": clip_dedup_removed,
            "selected": len(selected_clips),
            "files": clip_files,
        },
        long_videos={
            "total": len(long_videos),
            "highlights_created": len(all_highlights),
            "files": video_files,
        },
    )

    # Summary
    log("STATUS:done:Fertig!")
    log(f"  Fotos:      {len(selected_photos)} / {len(photo_results)} behalten ({duplicates_removed} Duplikate entfernt)")
    if short_clips:
        log(f"  Kurzclips:  {len(selected_clips)} / {len(short_clips)} behalten")
    if long_videos:
        log(f"  Highlights: {len(all_highlights)} Clips aus {len(long_videos)} langen Videos")
    log(f"  Report:     {args.json_report}")
    if not args.dry_run:
        log(f"  Ausgabe:    {args.output_folder}")


if __name__ == "__main__":
    main()
