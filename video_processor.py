from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

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
