import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


def export_photos(
    photos: list[dict],
    output_dir: Path,
) -> list[Path]:
    """Copy selected photos to output directory, sorted chronologically.

    Each photo dict must have: 'path' (Path), 'date_taken' (datetime or None),
    'date_source' (str).

    Returns list of output paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sort by date_taken, None goes to end
    sorted_photos = sorted(
        photos,
        key=lambda p: p["date_taken"] or datetime.max,
    )

    warnings = []
    output_paths = []
    num_digits = len(str(len(sorted_photos)))

    for i, photo in enumerate(sorted_photos, start=1):
        src = photo["path"]
        prefix = str(i).zfill(num_digits)
        dst = output_dir / f"{prefix}_{src.name}"

        if photo["date_source"] == "none":
            warnings.append(f"WARN:Kein Aufnahmedatum für {src.name} — Datei wird ans Ende sortiert")

        shutil.copy2(src, dst)
        output_paths.append(dst)

    return output_paths, warnings


def export_short_clips(
    clips: list[dict],
    output_dir: Path,
) -> list[Path]:
    """Copy selected short clips to output_dir/videos/, sorted chronologically.

    Each clip dict must have: 'path' (Path), 'date_modified' (datetime or None).
    Uses file mtime for sorting since videos typically lack EXIF.

    Returns list of output paths.
    """
    video_dir = output_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    sorted_clips = sorted(
        clips,
        key=lambda c: c.get("date_modified") or datetime.max,
    )

    output_paths = []
    num_digits = len(str(len(sorted_clips))) if sorted_clips else 1

    for i, clip in enumerate(sorted_clips, start=1):
        src = clip["path"]
        prefix = str(i).zfill(num_digits)
        dst = video_dir / f"{prefix}_{src.name}"
        shutil.copy2(src, dst)
        output_paths.append(dst)

    return output_paths


def export_highlights(
    highlights: list[dict],
    output_dir: Path,
) -> list[Path]:
    """Export highlight clips via FFmpeg into output_dir/videos/.

    Each highlight dict must have:
      'input_path' (Path), 'start_seconds' (float), 'end_seconds' (float),
      'source_name' (str), 'scene_index' (int).

    Returns list of output paths (only successful exports).
    """
    from video_processor import export_clip

    video_dir = output_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    output_paths = []

    for h in highlights:
        src_stem = Path(h["source_name"]).stem
        idx = h["scene_index"]
        start = h["start_seconds"]
        end = h["end_seconds"]
        suffix = Path(h["input_path"]).suffix

        dst = video_dir / f"highlight_{src_stem}_{idx:02d}{suffix}"

        success = export_clip(h["input_path"], start, end, dst)
        if success:
            output_paths.append(dst)

    return output_paths
