from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import imagehash
import numpy as np
from PIL import Image

# Register HEIC support
import pillow_heif
pillow_heif.register_heif_opener()


@dataclass
class SeriesGroup:
    """A group of similar photos (a 'series')."""
    best_index: int  # index into the original photo list
    member_indices: list[int] = field(default_factory=list)
    representative: Union[np.ndarray, imagehash.ImageHash, None] = None


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


def merge_similar_series(
    groups: list[SeriesGroup],
    scores: list[float],
    threshold: float = 0.95,
) -> list[SeriesGroup]:
    """Merge series whose representatives are similar (O(s²), s = number of series).

    This catches duplicate series — e.g. same motif photographed at different times.
    """
    if len(groups) <= 1:
        return groups

    # Build similarity matrix between representatives
    n = len(groups)
    merged_into: list[int] = list(range(n))  # union-find parent

    for i in range(n):
        for j in range(i + 1, n):
            if groups[i].representative is None or groups[j].representative is None:
                continue
            sim = _cosine_similarity(groups[i].representative, groups[j].representative)
            if sim >= threshold:
                # Merge j into i (find root of i)
                root_i = _find_root(merged_into, i)
                root_j = _find_root(merged_into, j)
                if root_i != root_j:
                    merged_into[root_j] = root_i

    # Collect merged groups
    root_to_group: dict[int, SeriesGroup] = {}
    for i in range(n):
        root = _find_root(merged_into, i)
        if root not in root_to_group:
            root_to_group[root] = SeriesGroup(
                best_index=groups[root].best_index,
                member_indices=list(groups[root].member_indices),
                representative=groups[root].representative,
            )
        else:
            merged = root_to_group[root]
            merged.member_indices.extend(groups[i].member_indices)
            if scores[groups[i].best_index] > scores[merged.best_index]:
                merged.best_index = groups[i].best_index
                merged.representative = groups[i].representative

    return list(root_to_group.values())


def _find_root(parents: list[int], i: int) -> int:
    """Find root in union-find with path compression."""
    while parents[i] != i:
        parents[i] = parents[parents[i]]
        i = parents[i]
    return i


def compute_phash(path: Path) -> imagehash.ImageHash:
    """Compute perceptual hash for an image."""
    img = Image.open(path).convert("RGB")
    return imagehash.phash(img)


def find_series_phash(
    hashes: list[imagehash.ImageHash],
    scores: list[float],
    sorted_indices: list[int],
    max_distance: int = 8,
) -> list[SeriesGroup]:
    """Detect series of similar photos using perceptual hashing.

    Photos must be pre-sorted by date (sorted_indices).
    Compares consecutive photos via Hamming distance — O(n).
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

        distance = hashes[prev_idx] - hashes[idx]

        if distance <= max_distance:
            current_group.member_indices.append(idx)
            if scores[idx] > scores[current_group.best_index]:
                current_group.best_index = idx
        else:
            current_group.representative = hashes[current_group.best_index]
            groups.append(current_group)
            current_group = SeriesGroup(
                best_index=idx,
                member_indices=[idx],
            )

    current_group.representative = hashes[current_group.best_index]
    groups.append(current_group)

    return groups


def merge_similar_series_phash(
    groups: list[SeriesGroup],
    scores: list[float],
    max_distance: int = 8,
) -> list[SeriesGroup]:
    """Merge series whose pHash representatives are similar (O(s²))."""
    if len(groups) <= 1:
        return groups

    n = len(groups)
    merged_into: list[int] = list(range(n))

    for i in range(n):
        for j in range(i + 1, n):
            if groups[i].representative is None or groups[j].representative is None:
                continue
            distance = groups[i].representative - groups[j].representative
            if distance <= max_distance:
                root_i = _find_root(merged_into, i)
                root_j = _find_root(merged_into, j)
                if root_i != root_j:
                    merged_into[root_j] = root_i

    root_to_group: dict[int, SeriesGroup] = {}
    for i in range(n):
        root = _find_root(merged_into, i)
        if root not in root_to_group:
            root_to_group[root] = SeriesGroup(
                best_index=groups[root].best_index,
                member_indices=list(groups[root].member_indices),
                representative=groups[root].representative,
            )
        else:
            merged = root_to_group[root]
            merged.member_indices.extend(groups[i].member_indices)
            if scores[groups[i].best_index] > scores[merged.best_index]:
                merged.best_index = groups[i].best_index
                merged.representative = groups[i].representative

    return list(root_to_group.values())


def deduplicate_clip(
    embeddings: list[np.ndarray],
    scores: list[float],
    sorted_indices: list[int],
    threshold: float = 0.95,
) -> tuple[list[int], list[SeriesGroup]]:
    """Full dedup pipeline using CLIP embeddings.

    Returns (kept_indices, groups).
    """
    groups = find_series_clip(embeddings, scores, sorted_indices, threshold)
    groups = merge_similar_series(groups, scores, threshold)
    kept = [g.best_index for g in groups]
    return kept, groups


def deduplicate_phash(
    hashes: list[imagehash.ImageHash],
    scores: list[float],
    sorted_indices: list[int],
    max_distance: int = 8,
) -> tuple[list[int], list[SeriesGroup]]:
    """Full dedup pipeline using perceptual hashing (no CLIP needed).

    Returns (kept_indices, groups).
    """
    groups = find_series_phash(hashes, scores, sorted_indices, max_distance)
    groups = merge_similar_series_phash(groups, scores, max_distance)
    kept = [g.best_index for g in groups]
    return kept, groups


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)
