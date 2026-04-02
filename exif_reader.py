from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import exifread


@dataclass
class ExifData:
    date_taken: Optional[datetime]
    date_source: str  # "exif", "mtime", or "none"
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None


def read_exif(path: Path) -> ExifData:
    """Read EXIF data from a photo file.

    Returns ExifData with date_taken from EXIF DateTimeOriginal.
    Falls back to file mtime if no EXIF date found.
    """
    exif_date = _read_exif_date(path)
    if exif_date:
        return ExifData(date_taken=exif_date, date_source="exif")

    mtime = _read_mtime(path)
    if mtime:
        return ExifData(date_taken=mtime, date_source="mtime")

    return ExifData(date_taken=None, date_source="none")


def _read_exif_date(path: Path) -> Optional[datetime]:
    """Try to read DateTimeOriginal from EXIF tags."""
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False, stop_tag="DateTimeOriginal")
    except Exception:
        return None

    tag = (
        tags.get("EXIF DateTimeOriginal")
        or tags.get("Image DateTimeOriginal")
        or tags.get("Image DateTime")
    )
    if not tag:
        return None

    try:
        return datetime.strptime(str(tag), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _read_mtime(path: Path) -> Optional[datetime]:
    """Read file modification time as fallback."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None
