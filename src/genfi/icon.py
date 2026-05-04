"""Set, clean, and refresh folder custom icons.

Supports Nautilus, Nemo (both use GIO metadata), Dolphin, and Thunar
(both use the freedesktop .directory file convention).
"""

import configparser
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# File managers that share the GIO metadata mechanism
_GIO_MANAGERS = {"nautilus", "nemo"}

# File managers that use the .directory file mechanism
_DOTDIR_MANAGERS = {"dolphin", "thunar"}

ALL_MANAGERS = _GIO_MANAGERS | _DOTDIR_MANAGERS
DEFAULT_MANAGER = "nautilus"


# ── Public API ────────────────────────────────────────────────────────────────

def set_icon(folder: Path, icon_path: Path) -> bool:
    """Set *icon_path* as the custom icon for *folder* using GIO metadata.

    Used by Nautilus and Nemo. Returns True on success.
    """
    return _gio_set(folder, icon_path)


def set_icon_dotdir(folder: Path, icon_path: Path) -> bool:
    """Set *icon_path* as the custom icon for *folder* via a .directory file.

    Used by Dolphin and Thunar. Returns True on success.
    """
    return _dotdir_set(folder, icon_path)


def clean_icon(folder: Path) -> bool:
    """Remove the custom icon from *folder* using GIO metadata.

    Used by Nautilus and Nemo. Returns True on success.
    """
    return _gio_unset(folder)


def clean_icon_dotdir(folder: Path) -> bool:
    """Remove the custom icon from *folder* by clearing the .directory file.

    Used by Dolphin and Thunar. Returns True on success.
    """
    return _dotdir_unset(folder)


def refresh(
    processed_folders: list[Path],
    file_manager: str = DEFAULT_MANAGER,
    quiet: bool = False,
) -> str:
    """Refresh the file manager so new icons appear without manual restart.

    Returns a short description of what was done.
    """
    fm = _normalise(file_manager)
    if fm == "nautilus":
        return _refresh_nautilus(processed_folders, quiet)
    if fm == "nemo":
        return _refresh_nemo(processed_folders, quiet)
    if fm == "dolphin":
        return _refresh_dolphin(processed_folders, quiet)
    if fm == "thunar":
        return _refresh_thunar(processed_folders, quiet)
    logger.warning("Unknown file manager '%s'; falling back to nautilus refresh", file_manager)
    return _refresh_nautilus(processed_folders, quiet)


# ── GIO (Nautilus / Nemo) ─────────────────────────────────────────────────────

def _gio_set(folder: Path, icon_path: Path) -> bool:
    icon_uri = icon_path.as_uri()
    cmd = ["gio", "set", "-t", "string", str(folder), "metadata::custom-icon", icon_uri]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True
        logger.warning("gio set failed for %s: %s", folder, result.stderr.strip())
        return False
    except Exception as e:
        logger.warning("gio set error for %s: %s", folder, e)
        return False


def _gio_unset(folder: Path) -> bool:
    cmd = ["gio", "set", "-t", "unset", str(folder), "metadata::custom-icon"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True
        logger.warning("gio unset failed for %s: %s", folder, result.stderr.strip())
        return False
    except Exception as e:
        logger.warning("gio unset error for %s: %s", folder, e)
        return False


# ── .directory file (Dolphin / Thunar) ───────────────────────────────────────
#
# The freedesktop Desktop Entry spec allows a .directory file inside a folder
# that sets metadata understood by KDE/Dolphin and XFCE/Thunar.
# The relevant key is Icon= under the [Desktop Entry] section.
# The value must be an absolute path for a custom image file.

_DOTDIR_SECTION = "Desktop Entry"
_DOTDIR_KEY = "Icon"


def _dotdir_set(folder: Path, icon_path: Path) -> bool:
    dot_dir = folder / ".directory"
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str  # preserve key case

    if dot_dir.exists():
        try:
            cfg.read(dot_dir, encoding="utf-8")
        except Exception as e:
            logger.warning("Could not read %s: %s", dot_dir, e)

    if not cfg.has_section(_DOTDIR_SECTION):
        cfg.add_section(_DOTDIR_SECTION)

    cfg.set(_DOTDIR_SECTION, _DOTDIR_KEY, str(icon_path))

    # Ensure a minimal Type= key is present (required by the spec)
    if not cfg.has_option(_DOTDIR_SECTION, "Type"):
        cfg.set(_DOTDIR_SECTION, "Type", "Directory")

    try:
        with dot_dir.open("w", encoding="utf-8") as fh:
            cfg.write(fh, space_around_delimiters=False)
        return True
    except Exception as e:
        logger.warning("Could not write %s: %s", dot_dir, e)
        return False


def _dotdir_unset(folder: Path) -> bool:
    dot_dir = folder / ".directory"
    if not dot_dir.exists():
        return True

    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    try:
        cfg.read(dot_dir, encoding="utf-8")
    except Exception as e:
        logger.warning("Could not read %s: %s", dot_dir, e)
        return False

    changed = False
    if cfg.has_section(_DOTDIR_SECTION) and cfg.has_option(_DOTDIR_SECTION, _DOTDIR_KEY):
        cfg.remove_option(_DOTDIR_SECTION, _DOTDIR_KEY)
        changed = True

    if not changed:
        return True

    # If the section is now empty (or only has Type=), remove the file entirely
    remaining = [k for k in cfg.options(_DOTDIR_SECTION) if k.lower() != "type"]
    if not remaining:
        try:
            dot_dir.unlink()
            return True
        except Exception as e:
            logger.warning("Could not remove %s: %s", dot_dir, e)
            return False

    try:
        with dot_dir.open("w", encoding="utf-8") as fh:
            cfg.write(fh, space_around_delimiters=False)
        return True
    except Exception as e:
        logger.warning("Could not write %s: %s", dot_dir, e)
        return False


# ── Refresh strategies ────────────────────────────────────────────────────────

def _touch_folders(folders: list[Path]) -> None:
    for folder in folders:
        try:
            subprocess.run(["touch", str(folder)], capture_output=True, timeout=5)
        except Exception:
            pass


def _refresh_nautilus(folders: list[Path], quiet: bool) -> str:
    """touch → xdotool F5 on open windows → fallback nautilus -q."""
    _touch_folders(folders)

    xdotool = shutil.which("xdotool")
    if xdotool:
        try:
            search = subprocess.run(
                [xdotool, "search", "--class", "nautilus"],
                capture_output=True, text=True, timeout=5,
            )
            wids = [w.strip() for w in search.stdout.strip().split("\n") if w.strip()]
            if wids:
                for wid in wids:
                    subprocess.run(
                        [xdotool, "key", "--window", wid, "F5"],
                        capture_output=True, timeout=5,
                    )
                msg = f"Sent F5 to {len(wids)} Nautilus window(s) via xdotool"
                if not quiet:
                    print(msg)
                return msg
        except Exception:
            pass

    subprocess.run(["nautilus", "-q"], capture_output=True, timeout=10)
    msg = "Restarted Nautilus (nautilus -q); icons will appear on next folder open"
    if not quiet:
        print(msg)
    return msg


def _refresh_nemo(folders: list[Path], quiet: bool) -> str:
    """touch → xdotool F5 on open windows → fallback nemo -q.

    Nemo uses the same GIO metadata as Nautilus and responds to the same
    refresh signals; only the process name differs.
    """
    _touch_folders(folders)

    xdotool = shutil.which("xdotool")
    if xdotool:
        try:
            search = subprocess.run(
                [xdotool, "search", "--class", "nemo"],
                capture_output=True, text=True, timeout=5,
            )
            wids = [w.strip() for w in search.stdout.strip().split("\n") if w.strip()]
            if wids:
                for wid in wids:
                    subprocess.run(
                        [xdotool, "key", "--window", wid, "F5"],
                        capture_output=True, timeout=5,
                    )
                msg = f"Sent F5 to {len(wids)} Nemo window(s) via xdotool"
                if not quiet:
                    print(msg)
                return msg
        except Exception:
            pass

    subprocess.run(["nemo", "-q"], capture_output=True, timeout=10)
    msg = "Restarted Nemo (nemo -q); icons will appear on next folder open"
    if not quiet:
        print(msg)
    return msg


def _refresh_dolphin(folders: list[Path], quiet: bool) -> str:
    """Notify Dolphin of directory changes via KDirNotify D-Bus signal.

    Dolphin watches KDirNotify for FilesChanged/FilesAdded signals and
    refreshes the affected directories automatically.  Touching the folders
    is also done as a belt-and-braces fallback for systems without dbus-send.
    """
    _touch_folders(folders)

    dbus_send = shutil.which("dbus-send")
    if dbus_send:
        try:
            for folder in folders:
                subprocess.run(
                    [
                        dbus_send,
                        "--session",
                        "--type=signal",
                        "/",
                        "org.kde.KDirNotify.FilesChanged",
                        f"as:1:{folder.as_uri()}",
                    ],
                    capture_output=True,
                    timeout=5,
                )
            msg = f"Sent KDirNotify FilesChanged for {len(folders)} folder(s)"
            if not quiet:
                print(msg)
            return msg
        except Exception:
            pass

    msg = "Touched folders; Dolphin will refresh on next directory visit"
    if not quiet:
        print(msg)
    return msg


def _refresh_thunar(folders: list[Path], quiet: bool) -> str:
    """Touch folders so Thunar's inotify watcher picks up the .directory change.

    Thunar monitors directories via inotify and re-reads .directory files
    automatically when the folder mtime changes — a simple touch is sufficient.
    """
    _touch_folders(folders)
    msg = "Touched folders; Thunar will refresh automatically via inotify"
    if not quiet:
        print(msg)
    return msg


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise(file_manager: str) -> str:
    return file_manager.lower().strip()


# Backward-compatible alias used by older call sites
def refresh_nautilus(processed_folders: list[Path], quiet: bool = False) -> str:
    return _refresh_nautilus(processed_folders, quiet)
