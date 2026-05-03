# genfi

Generate folder icons from contained video frames and photos for Nautilus (GNOME Files).

## Features

- Recursively scans directories for folders containing videos and/or photos
- Extracts frames from videos (ffmpeg) and uses photos directly (Pillow)
- Composes frames into a folder-shaped icon with previews inside (up to 4 frames)
- **Video priority**: videos are used first; remaining slots filled by photos
- Sets the icon as the folder's custom Nautilus icon via `gio`
- Caches results (mtime-based) to skip unchanged folders
- Hybrid Nautilus refresh: touch folders → xdotool F5 → fallback to `nautilus -q`
- Full CLI with `--dry-run`, `--clean`, `--force`, `--verbose`, `--types`
- Nautilus right-click script integration
- Complete uninstaller

## Installation

### Via pip

```bash
pip install .
```

### From source

```bash
git clone https://github.com/pmoutsop/genfi.git
cd genfi
pip install .
```

### Nautilus script (optional)

```bash
mkdir -p ~/.local/share/nautilus/scripts/
cp nautilus-scripts/genfi ~/.local/share/nautilus/scripts/
chmod +x ~/.local/share/nautilus/scripts/genfi
```

## Requirements

- Python >= 3.11
- ffmpeg (for video frame extraction)
- Pillow (installed automatically via pip)

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

# Remove icons and generated files
genfi --clean ~/Videos

# Skip Nautilus refresh
genfi --no-restart ~/Videos

# Full uninstall — revert everything, remove cache/config
genfi --uninstall
```

### Options

| Flag | Description |
|------|-------------|
| `path` | Root directory to scan (default: current dir) |
| `--types TYPE` | `both` (default), `video`, or `photo` |
| `--max-frames N` | Max media frames per icon (default: 4) |
| `--size N` | Output icon resolution (default: 512) |
| `--frame-position F` | Position in video for frame (0.0-1.0, default: 0.1) |
| `--crop MODE` | Crop mode: `fill`, `fit`, `center` (default: center) |
| `--workers N` | Parallel extraction workers (default: 4) |
| `--force` | Regenerate even if unchanged |
| `--no-restart` | Skip Nautilus refresh at the end |
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
```

CLI flags always override config file values.

## Nautilus Refresh

After setting icons, genfi automatically refreshes Nautilus:

1. Touches each processed folder (best-effort)
2. If `xdotool` is available, sends F5 to open Nautilus windows
3. Otherwise, runs `nautilus -q` (Nautilus auto-restarts on next open)

Use `--no-restart` to skip this step entirely.

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
