"""Configuration loading from TOML files."""

import logging
from pathlib import Path

import tomllib

from .walker import MEDIA_TYPES_BOTH, MEDIA_TYPES_PHOTO, MEDIA_TYPES_VIDEO

logger = logging.getLogger(__name__)

VALID_MEDIA_TYPES = (MEDIA_TYPES_VIDEO, MEDIA_TYPES_PHOTO, MEDIA_TYPES_BOTH)

DEFAULTS = {
    "max_frames": 4,
    "icon_size": 512,
    "frame_position": 0.1,
    "crop_mode": "center",
    "layout": "grid",
    "follow_symlinks": False,
    "media_types": MEDIA_TYPES_BOTH,
    "workers": 4,
    "force": False,
    "dry_run": False,
    "verbose": False,
    "quiet": False,
    "background": None,
    "file_manager": "nautilus",
}

CONFIG_PATHS = [
    Path.home() / ".config" / "genfi" / "genfi.toml",
]


def load_config(cli_args: dict | None = None) -> dict:
    """Load config from file, merged with defaults, overridden by CLI args."""
    config = dict(DEFAULTS)

    for path in CONFIG_PATHS:
        if path.exists():
            try:
                with open(path, "rb") as f:
                    file_config = tomllib.load(f)
                config.update(file_config)
                logger.debug("Loaded config from %s", path)
            except Exception as e:
                logger.warning("Failed to load config from %s: %s", path, e)
            break

    if cli_args:
        config.update(cli_args)

    mt = config.get("media_types", MEDIA_TYPES_BOTH)
    if mt not in VALID_MEDIA_TYPES:
        logger.warning("Invalid media_types '%s', falling back to '%s'", mt, MEDIA_TYPES_BOTH)
        config["media_types"] = MEDIA_TYPES_BOTH

    return config


def ensure_config_dir():
    """Create the user config directory if it doesn't exist."""
    config_dir = Path.home() / ".config" / "genfi"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
