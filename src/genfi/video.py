"""Frame extraction from video files and image processing using ffmpeg and Pillow."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def extract_frame(
    video_path: Path,
    output_path: Path,
    position: float = 0.1,
    size: int = 512,
) -> bool:
    """Extract a single frame from *video_path* and save to *output_path*.

    Returns True on success, False on failure.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.error("ffmpeg not found in PATH")
        return False

    duration = _get_duration(video_path)
    if duration is None or duration <= 0:
        logger.warning("Could not determine duration for %s", video_path)
        return False

    seek_time = max(duration * position, 1.0)

    cmd = [
        ffmpeg,
        "-ss", str(seek_time),
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", f"scale={size}:{size}:force_original_aspect_ratio=increase,crop={size}:{size}",
        "-y",
        "-loglevel", "error",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and output_path.exists():
            return True
        else:
            logger.warning(
                "Failed to extract frame from %s: %s",
                video_path,
                result.stderr.strip(),
            )
            return False
    except subprocess.TimeoutExpired:
        logger.warning("Timeout extracting frame from %s", video_path)
        return False
    except Exception as e:
        logger.warning("Error extracting frame from %s: %s", video_path, e)
        return False


def extract_image_frame(
    image_path: Path,
    output_path: Path,
    size: int = 512,
    crop_mode: str = "center",
) -> bool:
    """Resize/crop an image to a square frame and save to *output_path*.

    Returns True on success.
    """
    try:
        img = Image.open(image_path).convert("RGBA")
        img = _crop_and_resize(img, size, size, crop_mode)
        img.save(output_path, "PNG")
        return True
    except Exception as e:
        logger.warning("Failed to process image %s: %s", image_path, e)
        return False


def extract_media_frames(
    videos: list[Path],
    images: list[Path],
    max_frames: int = 4,
    position: float = 0.1,
    size: int = 512,
    crop_mode: str = "center",
    tmp_dir: Path | None = None,
) -> tuple[list[Path], int, int]:
    """Extract frames from videos and images with video priority.

    Videos are processed first via ffmpeg. Remaining slots are filled from images
    using Pillow. Returns (frame_paths, video_count, image_count).
    """
    work_dir = Path(tempfile.mkdtemp(dir=tmp_dir)) if tmp_dir else Path(tempfile.mkdtemp())
    video_frames = []

    for i, video in enumerate(videos):
        if len(video_frames) >= max_frames:
            break
        frame_path = work_dir / f"vid_{i}_{video.stem}.png"
        if extract_frame(video, frame_path, position, size):
            video_frames.append(frame_path)

    image_frames = []
    remaining = max_frames - len(video_frames)
    for i, image in enumerate(images[:remaining]):
        frame_path = work_dir / f"img_{i}_{image.stem}.png"
        if extract_image_frame(image, frame_path, size, crop_mode):
            image_frames.append(frame_path)

    all_frames = video_frames + image_frames
    return all_frames, len(video_frames), len(image_frames)


def _crop_and_resize(img: Image.Image, target_w: int, target_h: int, mode: str) -> Image.Image:
    """Resize image to fit the target dimensions."""
    img_w, img_h = img.size
    if img_w == 0 or img_h == 0:
        return Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))

    if mode == "fill":
        return img.resize((target_w, target_h), Image.LANCZOS)

    if mode == "fit":
        ratio = min(target_w / img_w, target_h / img_h)
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        new_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        new_img.paste(resized, (paste_x, paste_y))
        return new_img

    ratio = max(target_w / img_w, target_h / img_h)
    new_w = int(img_w * ratio)
    new_h = int(img_h * ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h
    return resized.crop((left, top, right, bottom))


def _get_duration(video_path: Path) -> float | None:
    """Return video duration in seconds, or None on failure."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None

    cmd = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        pass

    return None
