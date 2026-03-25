#!/usr/bin/env bash
set -euo pipefail

NODE_VERSION_DEFAULT=""
PYTHON_VERSION_DEFAULT=""
DRY_RUN=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"

NODE_VERSION=""
PYTHON_VERSION=""

step() { echo ""; echo "==> $*"; }
log_cmd() { echo "\$ $*"; }

run_cmd() {
  log_cmd "$*"
  if [[ "${DRY_RUN}" == "1" ]]; then
    return 0
  fi
  eval "$@"
}

usage() {
  cat <<'EOF'
Usage:
  ./bootstrap_env.sh [options]

Options:
  --dry-run                         Print actions without executing
  -h, --help                        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "${PROJECT_ROOT}" ]]; then
  echo "Project root does not exist: ${PROJECT_ROOT}" >&2
  exit 1
fi

NVMRC_PATH="${PROJECT_ROOT}/.nvmrc"
PYVER_PATH="${PROJECT_ROOT}/.python-version"

if [[ -f "${NVMRC_PATH}" ]]; then
  NODE_VERSION_DEFAULT="$(tr -d '\r' < "${NVMRC_PATH}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
fi
if [[ -f "${PYVER_PATH}" ]]; then
  PYTHON_VERSION_DEFAULT="$(tr -d '\r' < "${PYVER_PATH}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
fi

if [[ -z "${NODE_VERSION}" ]]; then
  NODE_VERSION="${NODE_VERSION_DEFAULT}"
fi
if [[ -z "${PYTHON_VERSION}" ]]; then
  PYTHON_VERSION="${PYTHON_VERSION_DEFAULT}"
fi

if [[ -z "${NODE_VERSION}" || -z "${PYTHON_VERSION}" ]]; then
  echo "Cannot determine Node/Python versions." >&2
  echo "Please ensure .nvmrc and .python-version exist in project root." >&2
  exit 1
fi

echo "Bootstrapping:"
echo "- Project root: ${PROJECT_ROOT}"
echo "- Node.js: ${NODE_VERSION}"
echo "- Python: ${PYTHON_VERSION}"
echo "- Dry run: ${DRY_RUN}"

step "Working directory: ${PROJECT_ROOT}"
cd "${PROJECT_ROOT}"

write_version_file() {
  local path="$1"
  local value="$2"
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[dry-run] Would update ${path} -> ${value}"
    return 0
  fi
  printf '%s\n' "${value}" > "${path}"
  echo "Updated ${path}"
}

if [[ -f "${NVMRC_PATH}" ]]; then
  echo "Using project-managed .nvmrc: ${NODE_VERSION}"
else
  write_version_file "${NVMRC_PATH}" "${NODE_VERSION}"
fi
if [[ -f "${PYVER_PATH}" ]]; then
  echo "Using project-managed .python-version: ${PYTHON_VERSION}"
else
  write_version_file "${PYVER_PATH}" "${PYTHON_VERSION}"
fi

step "Checking uv"
if ! command -v uv >/dev/null 2>&1; then
  step "Installing uv"
  run_cmd "curl -LsSf https://astral.sh/uv/install.sh | sh"
  if [[ "${DRY_RUN}" != "1" ]]; then
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
else
  echo "uv found: $(command -v uv)"
fi

step "Checking nvm"
export NVM_DIR="${HOME}/.nvm"
if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
  step "Installing nvm"
  run_cmd "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash"
fi

step "Installing Node.js ${NODE_VERSION}"
# 在同一 shell 进程中 source nvm 并 nvm use，后续本脚本内的命令会使用对应 Node。
# 若希望「关闭脚本后」当前终端仍保持该版本，请用: source ./bootstrap_env.sh（不要用 ./ 单独执行）
if [[ "${DRY_RUN}" == "1" ]]; then
  log_cmd "nvm install ${NODE_VERSION}"
  log_cmd "nvm alias default ${NODE_VERSION}"
  log_cmd "nvm use ${NODE_VERSION}"
else
  # shellcheck source=/dev/null
  if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
    echo "nvm.sh not found at ${NVM_DIR}/nvm.sh" >&2
    exit 1
  fi
  . "${NVM_DIR}/nvm.sh"
  nvm install "${NODE_VERSION}"
  nvm alias default "${NODE_VERSION}"
  nvm use "${NODE_VERSION}"
fi

step "Installing Python ${PYTHON_VERSION} via uv"
run_cmd "uv python install ${PYTHON_VERSION}"


step "Bootstrap completed"
echo "Next steps:"
echo "- This script already ran nvm use (see above)."
echo "- If you used ./bootstrap_env.sh, your login shell is unchanged; open a new terminal or run: source \"\$HOME/.nvm/nvm.sh\" && nvm use"
echo "- To apply bootstrap in the current shell next time: source ./bootstrap_env.sh"
