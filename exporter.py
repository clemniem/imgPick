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
