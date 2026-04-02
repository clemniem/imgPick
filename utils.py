import platform
import shutil
import subprocess
from pathlib import Path


def check_ffmpeg() -> Path:
    """Check if ffmpeg is installed and return its path.

    Raises SystemExit with platform-specific install instructions if not found.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return Path(ffmpeg_path)

    system = platform.system()
    if system == "Darwin":
        hint = "brew install ffmpeg"
    elif system == "Windows":
        hint = "winget install ffmpeg  (oder: https://ffmpeg.org/download.html)"
    else:
        hint = "sudo apt install ffmpeg  (oder: https://ffmpeg.org/download.html)"

    raise SystemExit(
        f"ffmpeg nicht gefunden.\n"
        f"Bitte installieren:\n"
        f"  {hint}"
    )


def open_folder(path: Path) -> None:
    """Open a folder in the platform's file browser."""
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", str(path)])
    elif system == "Windows":
        import os
        os.startfile(str(path))
    else:
        subprocess.Popen(["xdg-open", str(path)])
