#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

NODE_VER="$(tr -d ' \r\n' < "${REPO_ROOT}/.nvmrc")"
NODE_DIST_DIR="node-v${NODE_VER}-linux-x64"

set -ex
export DOCKER_BUILDKIT=1
docker pull ubuntu:22.04
docker build \
  --build-arg "NODE_VERSION=${NODE_VER}" \
  --build-arg "NODE_DIST_DIR=${NODE_DIST_DIR}" \
  -t hapray \
  -f "${SCRIPT_DIR}/Dockerfile" \
  "${REPO_ROOT}"
