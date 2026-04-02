from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mts"}


@dataclass
class VideoInfo:
    path: Path
    duration_seconds: float
    fps: float
    width: int
    height: int


def get_video_info(path: Path) -> Optional[VideoInfo]:
    """Get basic video metadata via OpenCV."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if fps <= 0 or frame_count <= 0:
            return None

        duration = frame_count / fps

        return VideoInfo(
            path=path,
            duration_seconds=duration,
            fps=fps,
            width=width,
            height=height,
        )
    finally:
        cap.release()


def categorize_videos(
    paths: list[Path],
    threshold_seconds: float = 180.0,
) -> tuple[list[VideoInfo], list[VideoInfo]]:
    """Split videos into short clips and long videos based on duration.

    Returns (short_clips, long_videos).
    """
    short_clips: list[VideoInfo] = []
    long_videos: list[VideoInfo] = []

    for path in paths:
        info = get_video_info(path)
        if info is None:
            continue

        if info.duration_seconds < threshold_seconds:
            short_clips.append(info)
        else:
            long_videos.append(info)

    return short_clips, long_videos


@dataclass
class ClipScore:
    path: Path
    tech_score: float
    clip_score: Optional[float]
    overall_score: float
    embedding: Optional[np.ndarray]  # average CLIP embedding across sampled frames


def _sample_frames(path: Path, num_frames: int = 10) -> list[np.ndarray]:
    """Sample evenly distributed frames from a video as BGR arrays."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return []

        indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
        frames = []

        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if ret:
                frames.append(frame)

        return frames
    finally:
        cap.release()


def _score_frame_technical(frame_bgr: np.ndarray) -> float:
    """Score a single video frame on sharpness + brightness (0.0–1.0)."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    # Sharpness
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness = min(1.0, variance / 500.0)

    # Brightness
    mean = float(gray.mean())
    if 80 <= mean <= 180:
        brightness = 1.0
    elif mean < 80:
        brightness = max(0.0, mean / 80.0)
    else:
        brightness = max(0.0, (255.0 - mean) / 75.0)

    return 0.6 * sharpness + 0.4 * brightness


def score_short_clip(
    path: Path,
    clip_model=None,
    pos_features=None,
    neg_features=None,
    tech_weight: float = 0.4,
    num_frames: int = 10,
) -> Optional[ClipScore]:
    """Score a short video clip by sampling frames.

    Returns None if the video can't be read.
    """
    frames = _sample_frames(path, num_frames)
    if not frames:
        return None

    # Technical score: average across frames
    tech_scores = [_score_frame_technical(f) for f in frames]
    avg_tech = sum(tech_scores) / len(tech_scores)

    # CLIP score: average across frames (if model provided)
    avg_clip_score = None
    avg_embedding = None

    if clip_model is not None and pos_features is not None and neg_features is not None:
        from scorer import _compute_clip_score

        embeddings = []
        clip_scores = []

        for frame_bgr in frames:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            emb = clip_model.encode_image(pil_img)
            embeddings.append(emb)
            cs = _compute_clip_score(emb, pos_features, neg_features, clip_model.device)
            clip_scores.append(cs)

        avg_clip_score = sum(clip_scores) / len(clip_scores)
        avg_embedding = np.mean(embeddings, axis=0)
        avg_embedding /= np.linalg.norm(avg_embedding)

        overall = tech_weight * avg_tech + (1.0 - tech_weight) * avg_clip_score
    else:
        overall = avg_tech

    return ClipScore(
        path=path,
        tech_score=avg_tech,
        clip_score=avg_clip_score,
        overall_score=overall,
        embedding=avg_embedding,
    )


def deduplicate_clips(
    clip_scores: list[ClipScore],
    threshold: float = 0.95,
) -> list[int]:
    """Deduplicate short clips by CLIP embedding similarity.

    Pairwise comparison (O(n²), fine for typical clip counts).
    Returns indices into clip_scores to keep.
    Only works when embeddings are available (CLIP mode).
    """
    if not clip_scores:
        return []

    n = len(clip_scores)
    # Skip if no embeddings
    if clip_scores[0].embedding is None:
        return list(range(n))

    from deduplicator import _cosine_similarity

    removed: set[int] = set()

    for i in range(n):
        if i in removed:
            continue
        for j in range(i + 1, n):
            if j in removed:
                continue
            sim = _cosine_similarity(clip_scores[i].embedding, clip_scores[j].embedding)
            if sim >= threshold:
                # Remove the one with the lower score
                if clip_scores[i].overall_score >= clip_scores[j].overall_score:
                    removed.add(j)
                else:
                    removed.add(i)
                    break  # i is removed, move on

    return [i for i in range(n) if i not in removed]


@dataclass
class HighlightScene:
    start_seconds: float
    end_seconds: float
    score: float
    clip_score: Optional[float] = None


def extract_highlights(
    path: Path,
    max_clips: int = 2,
    clip_model=None,
    pos_features=None,
    neg_features=None,
) -> list[HighlightScene]:
    """Detect scenes in a long video and return the best ones.

    Uses PySceneDetect for scene detection, then scores each scene's
    midpoint frame on sharpness + brightness (+ optional CLIP).
    """
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import AdaptiveDetector

    video = open_video(str(path))
    scene_manager = SceneManager()
    scene_manager.add_detector(AdaptiveDetector())
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    if not scene_list:
        return []

    # Score each scene by its midpoint frame
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []

    scenes: list[HighlightScene] = []

    try:
        for start_time, end_time in scene_list:
            start_s = start_time.get_seconds()
            end_s = end_time.get_seconds()
            mid_s = (start_s + end_s) / 2.0

            # Seek to midpoint
            cap.set(cv2.CAP_PROP_POS_MSEC, mid_s * 1000)
            ret, frame = cap.read()
            if not ret:
                continue

            tech_score = _score_frame_technical(frame)

            scene_clip_score = None
            if clip_model is not None and pos_features is not None and neg_features is not None:
                from scorer import _compute_clip_score
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                emb = clip_model.encode_image(pil_img)
                scene_clip_score = _compute_clip_score(emb, pos_features, neg_features, clip_model.device)
                overall = 0.4 * tech_score + 0.6 * scene_clip_score
            else:
                overall = tech_score

            scenes.append(HighlightScene(
                start_seconds=start_s,
                end_seconds=end_s,
                score=overall,
                clip_score=scene_clip_score,
            ))
    finally:
        cap.release()

    # Return top N scenes sorted by score
    scenes.sort(key=lambda s: s.score, reverse=True)
    best = scenes[:max_clips]
    # Sort by time for chronological output
    best.sort(key=lambda s: s.start_seconds)
    return best
