from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class SeriesGroup:
    """A group of similar photos (a 'series')."""
    best_index: int  # index into the original photo list
    member_indices: list[int] = field(default_factory=list)
    representative: Optional[np.ndarray] = None  # CLIP embedding of best photo


def find_series_clip(
    embeddings: list[np.ndarray],
    scores: list[float],
    sorted_indices: list[int],
    threshold: float = 0.95,
) -> list[SeriesGroup]:
    """Detect series of similar photos using CLIP embeddings.

    Photos must be pre-sorted by date (sorted_indices).
    Compares consecutive photos — O(n).
    """
    if not sorted_indices:
        return []

    groups: list[SeriesGroup] = []
    current_group = SeriesGroup(
        best_index=sorted_indices[0],
        member_indices=[sorted_indices[0]],
    )

    for i in range(1, len(sorted_indices)):
        idx = sorted_indices[i]
        prev_idx = sorted_indices[i - 1]

        similarity = _cosine_similarity(embeddings[prev_idx], embeddings[idx])

        if similarity >= threshold:
            current_group.member_indices.append(idx)
            if scores[idx] > scores[current_group.best_index]:
                current_group.best_index = idx
        else:
            current_group.representative = embeddings[current_group.best_index]
            groups.append(current_group)
            current_group = SeriesGroup(
                best_index=idx,
                member_indices=[idx],
            )

    current_group.representative = embeddings[current_group.best_index]
    groups.append(current_group)

    return groups


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)
