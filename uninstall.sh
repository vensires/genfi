#!/usr/bin/env bash
set -euo pipefail

# genfi uninstaller - removes all files and reverts changes

GENFI_CACHE="$HOME/.cache/thumbnails/genfi"
GENFI_CONFIG="$HOME/.config/genfi"
NAUTILUS_SCRIPT="$HOME/.local/share/nautilus/scripts/genfi"
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "")

CLEAN_ALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all|-a)
            CLEAN_ALL=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --all, -a    Also remove generated .folder-icon.png files and revert all folder icons"
            echo "  -h, --help   Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Uninstalling genfi..."

# Remove system-wide or user install via pip
if command -v pip3 &>/dev/null; then
    if pip3 show genfi &>/dev/null; then
        echo "Removing pip package..."
        pip3 uninstall -y genfi
    fi
fi

# Remove config directory
if [[ -d "$GENFI_CONFIG" ]]; then
    echo "Removing config: $GENFI_CONFIG"
    rm -rf "$GENFI_CONFIG"
fi

# Remove cache directory
if [[ -d "$GENFI_CACHE" ]]; then
    echo "Removing cache: $GENFI_CACHE"
    rm -rf "$GENFI_CACHE"
fi

# Remove Nautilus script
if [[ -f "$NAUTILUS_SCRIPT" ]]; then
    echo "Removing Nautilus script: $NAUTILUS_SCRIPT"
    rm -f "$NAUTILUS_SCRIPT"
fi

# Clean all generated icons and revert folder metadata
if $CLEAN_ALL; then
    echo "Reverting folder icons and removing generated images..."
    if [[ -f "$GENFI_CACHE/genfi_cache.db" ]]; then
        python3 -c "
import sqlite3, subprocess, os
from pathlib import Path

db_path = Path('$GENFI_CACHE/genfi_cache.db')
conn = sqlite3.connect(db_path)
rows = conn.execute('SELECT path, icon_path FROM folders').fetchall()
for folder, icon in rows:
    if os.path.exists(icon):
        os.unlink(icon)
    subprocess.run(['gio', 'set', '-t', 'unset', folder, 'metadata::custom-icon'],
                   capture_output=True)
conn.close()
" 2>/dev/null || echo "  (Note: could not revert all icons; run 'genfi --uninstall' instead)"
    echo "Done reverting folder icons."
fi

echo ""
echo "genfi has been uninstalled."
echo "Restart Nautilus with: nautilus -q"
