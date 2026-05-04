# genfi

Generate folder icons from contained video frames and photos.

## Features

- Recursively scans directories for folders containing videos and/or photos
- Extracts frames from videos (ffmpeg) and uses photos directly (Pillow)
- Composes frames into a folder-shaped icon with previews inside (up to 4 frames)
- **Video priority**: videos are used first; remaining slots filled by photos
- Sets the icon as the folder's custom icon via the file manager's native mechanism
- Supports **Nautilus, Nemo, Dolphin, and Thunar**
- Caches results (mtime-based) to skip unchanged folders
- Optional custom folder body background image (`--background`)
- Full CLI with `--dry-run`, `--clean`, `--force`, `--verbose`, `--types`
- Nautilus/Nemo right-click script integration
- Complete uninstaller

## Installation

### Via pip

```bash
pip install genfi
```

### From source

```bash
git clone https://github.com/vensires/genfi.git
cd genfi
pip install .
```

### Nautilus / Nemo script (optional)

```bash
mkdir -p ~/.local/share/nautilus/scripts/
cp nautilus-scripts/genfi ~/.local/share/nautilus/scripts/
chmod +x ~/.local/share/nautilus/scripts/genfi
```

## Requirements

- Python >= 3.11
- ffmpeg (for video frame extraction)
- Pillow (installed automatically via pip)
- `cairosvg` (optional — only needed for SVG `--background` images)

## Usage

```bash
# Generate icons for current directory tree (videos + photos, video priority)
genfi

# Generate icons for a specific path
genfi ~/Videos

# Photos only
genfi --types photo ~/Pictures

# Videos only
genfi --types video ~/Videos

# Dry run — see what would happen
genfi --dry-run ~/Videos

# Limit to 2 frames, 256px icons
genfi --max-frames 2 --size 256 ~/Videos

# Force regeneration of all icons
genfi --force ~/Videos

# Use a custom folder body background image
genfi --background ~/Pictures/texture.jpg ~/Videos

# Use Dolphin instead of Nautilus
genfi --file-manager dolphin ~/Videos

# Remove icons and generated files
genfi --clean ~/Videos

# Skip file manager refresh
genfi --no-restart ~/Videos

# Full uninstall — revert everything, remove cache/config
genfi --uninstall
```

### Options

| Flag | Description |
|------|-------------|
| `path` | Root directory to scan (default: current dir) |
| `--file-manager FM` | `nautilus` (default), `nemo`, `dolphin`, or `thunar` |
| `--types TYPE` | `both` (default), `video`, or `photo` |
| `--max-frames N` | Max media frames per icon (default: 4) |
| `--size N` | Output icon resolution (default: 512) |
| `--frame-position F` | Position in video for frame (0.0–1.0, default: 0.1) |
| `--crop MODE` | Crop mode: `fill`, `fit`, `center` (default: center) |
| `--background IMAGE` | JPEG, PNG, or SVG to use as folder body background |
| `--workers N` | Parallel extraction workers (default: 4) |
| `--force` | Regenerate even if unchanged |
| `--no-restart` | Skip file manager refresh at the end |
| `--dry-run` | Preview without changes |
| `--clean` | Remove icons under path |
| `--uninstall` | Full uninstall, revert all folders |
| `-v`, `--verbose` | Detailed output |
| `-q`, `--quiet` | Suppress output except errors |

## Configuration

Create `~/.config/genfi/genfi.toml` for persistent defaults:

```toml
max_frames = 4
icon_size = 256
frame_position = 0.15
crop_mode = "center"
media_types = "both"
workers = 2
file_manager = "nautilus"
# background = "/path/to/texture.jpg"
```

CLI flags always override config file values.

## File Manager Support

genfi supports four file managers. The `--file-manager` flag (or `file_manager` in the config file) selects which one to use.

### Nautilus (GNOME) — default

Icons are set via GIO metadata (`metadata::custom-icon`). After generating icons, genfi refreshes Nautilus automatically:

1. Touches each processed folder (best-effort)
2. If `xdotool` is available, sends F5 to all open Nautilus windows
3. Otherwise runs `nautilus -q` (Nautilus restarts on next open)

### Nemo (Linux Mint / Cinnamon)

Nemo uses the same GIO metadata mechanism as Nautilus — `gio set metadata::custom-icon` works identically on both. The refresh strategy is the same, using the `nemo` process name instead of `nautilus`.

### Dolphin (KDE Plasma)

Icons are set via a `.directory` file placed inside each folder, using the `Icon=` key under `[Desktop Entry]` — the standard freedesktop mechanism for per-folder icons. After generating icons, genfi sends a `org.kde.KDirNotify.FilesChanged` D-Bus signal (requires `dbus-send`) so Dolphin refreshes without a restart. If `dbus-send` is unavailable, a touch of the folder is used as fallback.

### Thunar (XFCE)

Thunar also reads the `Icon=` key from `.directory` files, identical to Dolphin. Thunar monitors folders via inotify, so touching the folder after writing `.directory` is sufficient to trigger an automatic refresh — no restart or D-Bus call needed.

### Similarity note

Dolphin and Thunar both rely on the same `.directory` file standard, so the icon-setting mechanism is shared. The only difference is the refresh strategy (D-Bus for Dolphin, inotify touch for Thunar). Nautilus and Nemo share the GIO metadata mechanism and differ only in the process name used during refresh.

## File Manager Refresh

Use `--no-restart` to skip the refresh step entirely (useful in scripts or when running headlessly).

## Uninstall

```bash
# Via pip
pip uninstall genfi

# Via script
./uninstall.sh        # Remove genfi files
./uninstall.sh --all  # Also revert all folder icons and delete generated images

# Or use the CLI
genfi --uninstall
```

## License

MIT

