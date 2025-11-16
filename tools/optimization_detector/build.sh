#!/bin/bash
# Build optimization detector executable

set -e

echo "Building optimization-detector executable..."

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="$PROJECT_DIR/.venv"
POSIX_PYTHON="$VENV_DIR/bin/python"
WINDOWS_PYTHON="$VENV_DIR/Scripts/python.exe"

# Prefer project-local virtual environment (create if missing)
if [ -x "$POSIX_PYTHON" ]; then
    PYTHON_CMD="$POSIX_PYTHON"
elif [ -x "$WINDOWS_PYTHON" ]; then
    PYTHON_CMD="$WINDOWS_PYTHON"
else
    echo "Virtual environment not found at $VENV_DIR, creating..."
    if command -v python3 &> /dev/null; then
        BASE_PYTHON=python3
    elif command -v python &> /dev/null; then
        BASE_PYTHON=python
    else
        echo "Error: system python command not found to create .venv"
        exit 1
    fi
    "$BASE_PYTHON" -m venv "$VENV_DIR"
    if [ -x "$POSIX_PYTHON" ]; then
        PYTHON_CMD="$POSIX_PYTHON"
    elif [ -x "$WINDOWS_PYTHON" ]; then
        PYTHON_CMD="$WINDOWS_PYTHON"
    else
        echo "Error: failed to initialize virtual environment at $VENV_DIR"
        exit 1
    fi
fi

PYTHON_VERSION=$("$PYTHON_CMD" --version)
echo "Using Python: $PYTHON_VERSION"

# Check and install dependencies
echo "Checking project dependencies..."
if ! "$PYTHON_CMD" -c "import pandas, numpy, tensorflow" 2>/dev/null; then
    echo "Installing project dependencies..."
    "$PYTHON_CMD" -m pip install --quiet -e . || "$PYTHON_CMD" -m pip install --quiet numpy pandas tensorflow tqdm pyelftools arpy joblib
fi

# Check and install PyInstaller
echo "Checking PyInstaller..."
if ! "$PYTHON_CMD" -m pip list 2>/dev/null | grep -q "^pyinstaller "; then
    echo "Installing PyInstaller..."
    "$PYTHON_CMD" -m pip install --quiet pyinstaller
fi

# Clean previous build artifacts (keep spec files)
echo "Cleaning previous build artifacts..."
rm -rf build/ dist/ *.egg-info

# Prepare build directory
BUILD_DIR="build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Run PyInstaller
echo "Start packaging executable..."
echo "Note: TensorFlow bundling may take 10-30 minutes..."

# Determine packaging mode (onedir or onefile)
echo "Using onedir mode (faster startup, multiple files)..."
SPEC_FILE="optimization_detector.spec"
EXE_NAME="opt-detector/opt-detector"

"$PYTHON_CMD" -m PyInstaller "$SPEC_FILE" --clean --noconfirm

# Sync artifacts to repo dist/tools
ROOT_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"
ROOT_DIST_DIR="$ROOT_DIR/dist/tools"
TARGET_DIR="$ROOT_DIST_DIR/opt_detector"

echo ""
echo "Syncing artifact to: $TARGET_DIR"
if [ -d "dist/opt-detector" ]; then
    mkdir -p "$ROOT_DIST_DIR"
    rm -rf "$TARGET_DIR"
    cp README.md dist/opt-detector/
    cp -R "dist/opt-detector" "$TARGET_DIR"
    echo "✓ onedir artifact copied to dist/tools"
else
    echo "⚠ dist/opt-detector* not found, skip sync"
fi

echo ""
echo "Build finished."
