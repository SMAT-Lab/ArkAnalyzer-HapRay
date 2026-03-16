#!/usr/bin/env bash
# Setup script for opt-detector skill. Run from skill root.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PKG_DIR="$SKILL_ROOT/optimization_detector"

if [ ! -d "$PKG_DIR" ]; then
    echo "Error: optimization_detector not found at $PKG_DIR"
    echo "Ensure the skill was installed with the full package."
    exit 1
fi

echo "Installing optimization_detector from $PKG_DIR..."
pip install -e "$PKG_DIR"
echo "Done. Run 'opt-detector --help' to verify."
