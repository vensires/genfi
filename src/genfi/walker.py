"""Recursive directory walker that finds directly-contained video and image files."""

from pathlib import Path

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v",
    ".wmv", ".flv", ".mpg", ".mpeg", ".3gp", ".ogv",
    ".MP4", ".MKV", ".AVI", ".MOV", ".WEBM", ".M4V",
    ".WMV", ".FLV", ".MPG", ".MPEG", ".3GP", ".OGV",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".webp", ".avif", ".ico", ".tga", ".tif", ".tiff",
    ".JPG", ".JPEG", ".PNG", ".GIF", ".BMP",
    ".WEBP", ".AVIF", ".ICO", ".TGA", ".TIF", ".TIFF",
}

MEDIA_TYPES_VIDEO = "video"
MEDIA_TYPES_PHOTO = "photo"
MEDIA_TYPES_BOTH = "both"


def walk_folders(root: Path, follow_symlinks: bool = False, media_types: str = MEDIA_TYPES_BOTH):
    """Yield (folder_path, videos, images) for every directory under root.

    Videos and images are only directly contained in each folder (not recursive).
    The root folder itself is included.

    media_types: 'video', 'photo', or 'both'
    """
    want_videos = media_types in (MEDIA_TYPES_VIDEO, MEDIA_TYPES_BOTH)
    want_images = media_types in (MEDIA_TYPES_PHOTO, MEDIA_TYPES_BOTH)

    for folder in sorted(_iter_dirs(root, follow_symlinks)):
        videos = _collect_by_ext(folder, VIDEO_EXTENSIONS) if want_videos else []
        images = _collect_by_ext(folder, IMAGE_EXTENSIONS) if want_images else []
        if videos or images:
            yield folder, videos, images


def _iter_dirs(root: Path, follow_symlinks: bool):
    """Yield all directories under root, including root itself."""
    root = root.resolve()
    yield root
    if not root.is_dir():
        return
    for item in sorted(root.iterdir()):
        try:
            if not follow_symlinks and item.is_symlink():
                continue
            if item.is_dir():
                yield from _iter_dirs(item, follow_symlinks)
        except (PermissionError, OSError):
            continue


def _collect_by_ext(folder: Path, extensions: set[str]) -> list[Path]:
    """Return list of files with matching extensions directly inside *folder*."""
    result = []
    try:
        for entry in sorted(folder.iterdir()):
            if entry.is_file() and entry.suffix in extensions:
                result.append(entry)
    except (PermissionError, OSError):
        pass
    return result
