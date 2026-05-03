"""Set, clean, and refresh folder custom icons via gio."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def set_icon(folder: Path, icon_path: Path) -> bool:
    """Set *icon_path* as the custom icon for *folder* using gio.

    Returns True on success.
    """
    icon_uri = icon_path.as_uri()
    cmd = ["gio", "set", "-t", "string", str(folder), "metadata::custom-icon", icon_uri]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True
        logger.warning("Failed to set icon for %s: %s", folder, result.stderr.strip())
        return False
    except Exception as e:
        logger.warning("Error setting icon for %s: %s", folder, e)
        return False


def clean_icon(folder: Path) -> bool:
    """Remove the custom icon from *folder*, reverting to default.

    Returns True on success.
    """
    cmd = ["gio", "set", "-t", "unset", str(folder), "metadata::custom-icon"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True
        logger.warning("Failed to clean icon for %s: %s", folder, result.stderr.strip())
        return False
    except Exception as e:
        logger.warning("Error cleaning icon for %s: %s", folder, e)
        return False


def touch_folder(folder: Path):
    """Best-effort touch of the folder to trigger Nautilus metadata re-read."""
    try:
        subprocess.run(
            ["touch", str(folder)],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def refresh_nautilus(processed_folders: list[Path], quiet: bool = False) -> str:
    """Attempt to refresh Nautilus so new icons appear.

    Strategy:
    1. Touch each processed folder (best-effort)
    2. Try xdotool F5 on open Nautilus windows
    3. If xdotool unavailable or no windows found, run nautilus -q

    Returns a description of what was done.
    """
    for folder in processed_folders:
        touch_folder(folder)

    xdotool = shutil.which("xdotool")
    if xdotool:
        try:
            search = subprocess.run(
                [xdotool, "search", "--class", "nautilus"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            window_ids = [w.strip() for w in search.stdout.strip().split("\n") if w.strip()]

            if window_ids:
                for wid in window_ids:
                    subprocess.run(
                        [xdotool, "key", "--window", wid, "F5"],
                        capture_output=True,
                        timeout=5,
                    )
                method = f"Sent F5 to {len(window_ids)} Nautilus window(s) via xdotool"
                if not quiet:
                    print(method)
                return method
        except Exception:
            pass

    subprocess.run(["nautilus", "-q"], capture_output=True, timeout=10)
    method = "Restarted Nautilus (nautilus -q); icons will appear on next folder open"
    if not quiet:
        print(method)
    return method
