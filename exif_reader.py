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

    Returns ExifData with date_taken and optional GPS coordinates.
    Falls back to file mtime if no EXIF date found.
    """
    tags = _read_tags(path)

    exif_date = _extract_date(tags)
    gps_lat, gps_lon = _extract_gps(tags)

    if exif_date:
        return ExifData(
            date_taken=exif_date, date_source="exif",
            gps_lat=gps_lat, gps_lon=gps_lon,
        )

    mtime = _read_mtime(path)
    if mtime:
        return ExifData(
            date_taken=mtime, date_source="mtime",
            gps_lat=gps_lat, gps_lon=gps_lon,
        )

    return ExifData(
        date_taken=None, date_source="none",
        gps_lat=gps_lat, gps_lon=gps_lon,
    )


def _read_tags(path: Path) -> dict:
    """Read all EXIF tags from a file."""
    try:
        with open(path, "rb") as f:
            return exifread.process_file(f, details=False)
    except Exception:
        return {}


def _extract_date(tags: dict) -> Optional[datetime]:
    """Extract DateTimeOriginal from EXIF tags."""
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


def _extract_gps(tags: dict) -> tuple[Optional[float], Optional[float]]:
    """Extract GPS latitude and longitude from EXIF tags.

    Returns (lat, lon) or (None, None) if GPS data is missing.
    """
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref = tags.get("GPS GPSLatitudeRef")
    lon_tag = tags.get("GPS GPSLongitude")
    lon_ref = tags.get("GPS GPSLongitudeRef")

    if not all([lat_tag, lat_ref, lon_tag, lon_ref]):
        return None, None

    try:
        lat = _dms_to_decimal(lat_tag.values)
        if str(lat_ref) == "S":
            lat = -lat

        lon = _dms_to_decimal(lon_tag.values)
        if str(lon_ref) == "W":
            lon = -lon

        return lat, lon
    except (ValueError, ZeroDivisionError, AttributeError):
        return None, None


def _dms_to_decimal(dms_values: list) -> float:
    """Convert EXIF GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    d = float(dms_values[0].num) / float(dms_values[0].den)
    m = float(dms_values[1].num) / float(dms_values[1].den)
    s = float(dms_values[2].num) / float(dms_values[2].den)
    return d + m / 60.0 + s / 3600.0


def _read_mtime(path: Path) -> Optional[datetime]:
    """Read file modification time as fallback."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None
