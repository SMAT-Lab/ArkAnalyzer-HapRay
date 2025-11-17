#!/bin/bash
# Package given files/directories into a zip file

set -e

# Validate arguments
if [ "$#" -lt 2 ]; then
    echo "Usage: ./pack.sh <zip-name> <file-or-directory> [more files/dirs]"
    exit 1
fi

# First argument is the base name of the output file
ZIP_BASE="$1"
shift

# Read version from package.json
VERSION=$(node -p "require('./package.json').version" 2>/dev/null || grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' package.json | grep -o '[0-9.]\+' | head -1)

if [ -z "${VERSION}" ]; then
    echo "Warning: failed to read version from package.json, fallback to 1.0.0"
    VERSION="1.0.0"
fi

# Strip trailing .zip if provided
ZIP_BASE="${ZIP_BASE%.zip}"
ZIP_NAME="${ZIP_BASE}-${VERSION}.zip"
ZIP_PATH="${ZIP_NAME}"
ZIP_ABS_PATH="$(pwd)/${ZIP_PATH}"
TARGETS=("$@")

if ! command -v zip &> /dev/null; then
    echo "Error: zip command not found"
    echo "macOS: zip should be preinstalled"
    echo "Linux: sudo apt-get install zip or sudo yum install zip"
    exit 1
fi

# Ensure targets exist
for target in "${TARGETS[@]}"; do
    if [ ! -e "${target}" ]; then
        echo "Error: target ${target} not found"
        exit 1
    fi
done

mkdir -p dist
rm -f "${ZIP_PATH}"

TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t pack-tmp)"
cleanup() {
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

for target in "${TARGETS[@]}"; do
    if [ -d "${target}" ]; then
        cp -a "${target}/." "${TMP_DIR}/"
    else
        cp -a "${target}" "${TMP_DIR}/"
    fi
done

echo "Creating ${ZIP_PATH} with targets: ${TARGETS[*]}"
(
    cd "${TMP_DIR}"
    zip -r -q -9 "${ZIP_ABS_PATH}" .
)

echo ""
echo "Packaging complete!"
ls -lh "${ZIP_PATH}"
echo ""
echo "File size:"
du -sh "${ZIP_PATH}"
