from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Register HEIC support
import pillow_heif
pillow_heif.register_heif_opener()


@dataclass
class TechScore:
    sharpness: float
    brightness: float
    contrast: float
    resolution: float
    overall: float


def score_technical(path: Path) -> TechScore:
    """Score a photo on technical quality metrics.

    Each sub-score is normalized to 0.0–1.0.
    Overall is a weighted average.
    """
    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    sharpness = _score_sharpness(gray)
    brightness = _score_brightness(gray)
    contrast = _score_contrast(gray)
    resolution = _score_resolution(arr)

    overall = (
        0.40 * sharpness
        + 0.25 * brightness
        + 0.20 * contrast
        + 0.15 * resolution
    )

    return TechScore(
        sharpness=sharpness,
        brightness=brightness,
        contrast=contrast,
        resolution=resolution,
        overall=overall,
    )


def _score_sharpness(gray: np.ndarray) -> float:
    """Laplacian variance — higher means sharper."""
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return min(1.0, variance / 500.0)


def _score_brightness(gray: np.ndarray) -> float:
    """Mean pixel value — penalize too dark or too bright."""
    mean = float(gray.mean())
    if 80 <= mean <= 180:
        return 1.0
    elif mean < 80:
        return max(0.0, mean / 80.0)
    else:
        return max(0.0, (255.0 - mean) / 75.0)


def _score_contrast(gray: np.ndarray) -> float:
    """Standard deviation of luminance — higher means more contrast."""
    std = float(gray.std())
    return min(1.0, std / 80.0)


def _score_resolution(arr: np.ndarray) -> float:
    """Megapixels — 12 MP as reference maximum."""
    h, w = arr.shape[:2]
    megapixels = (h * w) / 1_000_000
    return min(1.0, megapixels / 12.0)
