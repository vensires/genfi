"""CLI interface and main orchestration logic for genfi."""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from . import __version__
from . import walker
from .cache import IconCache
from .compose import compose_grid
from .config import load_config, ensure_config_dir
from .icon import clean_icon, refresh_nautilus, set_icon
from .video import extract_media_frames

CACHE_DIR = Path.home() / ".cache" / "thumbnails" / "genfi"
ICON_NAME = ".folder-icon.png"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genfi",
        description="Generate folder icons from contained video frames and/or photos.",
        epilog=(
            "Examples:\n"
            "  genfi ~/Videos\n"
            "  genfi . --max-frames 4 --size 256\n"
            "  genfi --types photo ~/Pictures\n"
            "  genfi --dry-run ~/Videos\n"
            "  genfi --clean ~/Videos\n"
            "  genfi --uninstall\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"genfi {__version__}",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove custom icons from all processed folders and delete generated files",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove all cache, config, and generated icons; revert all folders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate icons even if folder hasn't changed",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum media frames per icon (default: 4)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=None,
        help="Output icon resolution in pixels (default: 512)",
    )
    parser.add_argument(
        "--frame-position",
        type=float,
        default=None,
        help="Position in video to grab frame (0.0-1.0, default: 0.1)",
    )
    parser.add_argument(
        "--crop",
        choices=["fill", "fit", "center"],
        default=None,
        help="How to handle non-square frames (default: center)",
    )
    parser.add_argument(
        "--types",
        choices=["both", "video", "photo"],
        default=None,
        help="Media types to use: both (video+photo, video priority), video, photo (default: both)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel frame extraction workers (default: 4)",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Do not refresh Nautilus after generating icons",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )
    parser.add_argument(
        "--nautilus-script",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def setup_logging(verbose: bool = False, quiet: bool = False):
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    cli_overrides = {
        k: v for k, v in {
            "force": args.force,
            "verbose": args.verbose,
            "quiet": args.quiet,
            "dry_run": args.dry_run,
        }.items() if v is not None
    }
    if args.max_frames is not None:
        cli_overrides["max_frames"] = args.max_frames
    if args.size is not None:
        cli_overrides["icon_size"] = args.size
    if args.frame_position is not None:
        cli_overrides["frame_position"] = args.frame_position
    if args.crop is not None:
        cli_overrides["crop_mode"] = args.crop
    if args.types is not None:
        cli_overrides["media_types"] = args.types
    if args.workers is not None:
        cli_overrides["workers"] = args.workers

    config = load_config(cli_overrides)
    setup_logging(config["verbose"], config["quiet"])

    if args.nautilus_script:
        root = _get_nautilus_path()
        if root is None:
            return 1
    else:
        root = Path(args.path).resolve()

    if not root.is_dir():
        logging.error("Path does not exist or is not a directory: %s", root)
        return 1

    if args.uninstall:
        return _do_uninstall(config, quiet=config["quiet"])

    if args.clean:
        return _do_clean(root, config)

    return _do_generate(root, config, dry_run=args.dry_run, no_restart=args.no_restart)


def _get_nautilus_path() -> Path | None:
    """Get the current path from Nautilus script environment variables."""
    import urllib.parse
    uri = Path("/proc/self/environ").read_text(errors="ignore")
    for line in uri.split("\x00"):
        if line.startswith("NAUTILUS_SCRIPT_CURRENT_URI="):
            raw_uri = line.split("=", 1)[1]
            decoded = urllib.parse.unquote(raw_uri)
            if decoded.startswith("file://"):
                decoded = decoded[7:]
            return Path(decoded)
    return None


def _do_generate(root: Path, config: dict, dry_run: bool = False, no_restart: bool = False) -> int:
    """Generate folder icons recursively."""
    cache = IconCache(CACHE_DIR)
    max_frames = config["max_frames"]
    icon_size = config["icon_size"]
    frame_position = config["frame_position"]
    crop_mode = config["crop_mode"]
    media_types = config["media_types"]
    force = config["force"]
    quiet = config["quiet"]

    total = 0
    generated = 0
    skipped = 0
    errors = 0
    processed_folders: list[Path] = []

    for folder, videos, images in walker.walk_folders(
        root, config["follow_symlinks"], media_types
    ):
        total += 1

        limited_videos = videos[:max_frames]
        remaining = max(0, max_frames - len(limited_videos))
        limited_images = images[:remaining]

        if not force and not cache.needs_update(folder, limited_videos, limited_images):
            if not quiet:
                print(f"SKIP  {folder}")
            skipped += 1
            continue

        icon_path = folder / ICON_NAME

        n_vid = len(limited_videos)
        n_img = len(limited_images)
        logging.info(
            "Processing %s (%d videos, %d images)", folder, n_vid, n_img
        )

        if dry_run:
            frame_desc = f"{min(n_vid, max_frames)} video + {min(n_img, max(0, max_frames - n_vid))} photo"
            if not quiet:
                print(f"WOULD {folder} ({frame_desc} frames)")
            generated += 1
            continue

        frames, vid_count, img_count = extract_media_frames(
            limited_videos,
            limited_images,
            max_frames=max_frames,
            position=frame_position,
            size=icon_size,
            crop_mode=crop_mode,
            tmp_dir=CACHE_DIR,
        )

        if not frames:
            logging.warning("No frames extracted for %s", folder)
            errors += 1
            continue

        if not compose_grid(frames, icon_path, icon_size, crop_mode):
            logging.error("Failed to compose icon for %s", folder)
            errors += 1
            continue

        if not set_icon(folder, icon_path):
            logging.error("Failed to set icon for %s", folder)
            errors += 1
            continue

        cache.record(folder, icon_path, limited_videos, limited_images)
        processed_folders.append(folder)
        generated += 1

        desc_parts = []
        if vid_count:
            desc_parts.append(f"{vid_count} video")
        if img_count:
            desc_parts.append(f"{img_count} photo")
        frame_desc = " + ".join(desc_parts)
        if not quiet:
            print(f"OK    {folder} ({frame_desc} frames)")

    if processed_folders and not no_restart and not dry_run:
        refresh_nautilus(processed_folders, quiet=quiet)

    if not quiet:
        print(f"\nDone: {generated} generated, {skipped} skipped, {errors} errors (of {total} folders)")

    return 0


def _do_clean(root: Path, config: dict) -> int:
    """Remove custom icons under *root*."""
    cache = IconCache(CACHE_DIR)
    quiet = config["quiet"]
    cleaned = 0
    errors = 0

    for folder_path, icon_path in cache.get_all():
        folder = Path(folder_path)
        icon = Path(icon_path)
        if not folder.is_relative_to(root):
            continue

        if icon.exists():
            try:
                icon.unlink()
            except OSError as e:
                logging.error("Could not delete %s: %s", icon, e)
                errors += 1

        if clean_icon(folder):
            cleaned += 1
            if not quiet:
                print(f"CLEAN {folder}")
        else:
            errors += 1

        cache.remove(folder)

    if not quiet:
        print(f"\nDone: {cleaned} cleaned, {errors} errors")

    return 0


def _do_uninstall(config: dict, quiet: bool = False) -> int:
    """Full uninstall: remove cache, config, revert all folders, delete icons."""
    logging.info("Uninstalling genfi...")

    cache = IconCache(CACHE_DIR)
    cleaned = 0
    errors = 0

    for folder_path, icon_path in cache.get_all():
        folder = Path(folder_path)
        icon = Path(icon_path)

        if icon.exists():
            try:
                icon.unlink()
            except OSError:
                pass

        if clean_icon(folder):
            cleaned += 1
        else:
            errors += 1

        cache.remove(folder)

    cache.clear()

    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR, ignore_errors=True)

    config_dir = Path.home() / ".config" / "genfi"
    if config_dir.exists():
        shutil.rmtree(config_dir, ignore_errors=True)

    nautilus_script = Path.home() / ".local" / "share" / "nautilus" / "scripts" / "genfi"
    if nautilus_script.exists():
        try:
            nautilus_script.unlink()
        except OSError:
            pass

    if not quiet:
        print(f"Uninstalled genfi: {cleaned} folders reverted, {errors} errors")

    return 0
