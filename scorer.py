from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
from PIL import Image

# Register HEIC support
import pillow_heif
pillow_heif.register_heif_opener()

DEFAULT_POSITIVE_PROMPTS = [
    "a beautiful vacation photo",
    "a stunning landscape",
    "happy people on holiday",
]
DEFAULT_NEGATIVE_PROMPTS = [
    "a blurry photo",
    "an overexposed image",
    "a dark underexposed photo",
]


@dataclass
class TechScore:
    sharpness: float
    brightness: float
    contrast: float
    resolution: float
    overall: float


@dataclass
class ClipResult:
    score: float
    embedding: np.ndarray


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


# --- CLIP Scoring ---

class ClipModel:
    """Wrapper around open_clip for scoring images against text prompts."""

    def __init__(self):
        import open_clip

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai", device=self.device,
        )
        self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
        self.model.eval()

    @torch.no_grad()
    def encode_text(self, prompts: list[str]) -> torch.Tensor:
        """Encode text prompts into normalized embeddings."""
        tokens = self.tokenizer(prompts).to(self.device)
        text_features = self.model.encode_text(tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        return text_features

    @torch.no_grad()
    def encode_image(self, img: Image.Image) -> np.ndarray:
        """Encode a single PIL image into a normalized embedding."""
        image_input = self.preprocess(img).unsqueeze(0).to(self.device)
        image_features = self.model.encode_image(image_input)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        return image_features.cpu().numpy().squeeze()


def score_clip(
    path: Path,
    clip_model: ClipModel,
    positive_prompts: list[str],
    negative_prompts: list[str],
) -> ClipResult:
    """Score a photo using CLIP similarity to text prompts.

    Returns ClipResult with score (0.0–1.0) and the image embedding.
    """
    img = Image.open(path).convert("RGB")
    embedding = clip_model.encode_image(img)

    pos_features = clip_model.encode_text(positive_prompts)
    neg_features = clip_model.encode_text(negative_prompts)

    emb_tensor = torch.from_numpy(embedding).unsqueeze(0).to(clip_model.device)

    pos_sim = (emb_tensor @ pos_features.T).mean().item()
    neg_sim = (emb_tensor @ neg_features.T).mean().item()

    raw_score = pos_sim - neg_sim
    score = max(0.0, min(1.0, (raw_score + 1.0) / 2.0))

    return ClipResult(score=score, embedding=embedding)
