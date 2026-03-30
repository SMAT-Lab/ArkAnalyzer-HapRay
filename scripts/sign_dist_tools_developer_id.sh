#!/usr/bin/env bash
# 在 Tauri 打包前，用 Developer ID 签名 dist/tools 下 PyInstaller 等生成的 Mach-O，
# 否则公证会报：Resources/tools/.../xxx 未用有效 Developer ID 签名。
#
# 依赖环境变量：APPLE_SIGNING_IDENTITY
# 用法：bash sign_dist_tools_developer_id.sh /path/to/dist/tools

set -euo pipefail

TOOLS_DIR="${1:-}"
IDENTITY="${APPLE_SIGNING_IDENTITY:-}"
SKIP_TOOL_DIRS=("opt-detector" "perf-testing" "symbol-recovery")

if [[ -z "$IDENTITY" ]]; then
  echo "[sign_dist_tools_developer_id] 未设置 APPLE_SIGNING_IDENTITY，跳过。"
  exit 0
fi

if [[ -z "$TOOLS_DIR" ]] || [[ ! -d "$TOOLS_DIR" ]]; then
  echo "[sign_dist_tools_developer_id] tools 目录不存在，跳过: ${TOOLS_DIR:-<empty>}"
  exit 0
fi

echo "[sign_dist_tools_developer_id] 使用 Developer ID 签名: $TOOLS_DIR"
echo "[sign_dist_tools_developer_id] 跳过已在 PyInstaller 阶段签名的工具: ${SKIP_TOOL_DIRS[*]}"

# 公证常见要求：timestamp + hardened runtime（与主应用一致）
# 注意：set -u 下空数组 "${extra[@]}" 可能报 unbound variable，故用 shift 后 "$@" 传递 --deep 等额外参数
csign() {
  local target="$1"
  shift
  [[ -e "$target" ]] || return 0
  if [[ -d "$target" ]]; then
    echo "  codesign: $target"
    codesign --sign "$IDENTITY" --force --timestamp --options runtime "$@" "$target" || {
      echo "  警告: 签名失败: $target" >&2
    }
    return 0
  fi
  [[ -f "$target" ]] || return 0
  file "$target" 2>/dev/null | grep -q "Mach-O" || return 0
  echo "  codesign: $target"
  codesign --sign "$IDENTITY" --force --timestamp --options runtime "$@" "$target" || {
    echo "  警告: 签名失败（若因 hardened runtime，可再查 entitlement）: $target" >&2
  }
}

# 判断路径（含符号链接解析后）是否位于某个 .framework 内。
# 例如 _internal/Python 往往是到 Python.framework/Versions/*/Python 的符号链接；
# 若在签完 framework 后再签该软链路径，会改写 framework 内目标文件并破坏密封。
in_framework_path() {
  local p="$1"
  [[ "$p" == *".framework/"* ]] && return 0
  local rp
  rp="$(realpath "$p" 2>/dev/null || true)"
  [[ -n "$rp" && "$rp" == *".framework/"* ]]
}

# 按路径组件判断是否属于「已在 PyInstaller 阶段完成签名」的工具目录。
should_skip_tool() {
  local p="$1"
  local rel="${p#"$TOOLS_DIR"/}"
  local d
  for d in "${SKIP_TOOL_DIRS[@]}"; do
    if [[ "$rel" == "$d" ]] || [[ "$rel" == "$d/"* ]] || [[ "$rel" == */"$d" ]] || [[ "$rel" == */"$d/"* ]]; then
      return 0
    fi
  done
  return 1
}

SKIP_LOGGED_KEYS=$'\n'

log_skip_once() {
  local target="$1"
  local key="${target#"$TOOLS_DIR"/}"
  [[ "$SKIP_LOGGED_KEYS" == *$'\n'"$key"$'\n'* ]] && return 0
  echo "  skip (pyinstaller 已签名): $target"
  SKIP_LOGGED_KEYS+="$key"$'\n'
}

# 1) 先签 .framework（整包 --deep）。路径按「深度」降序，先签内层嵌套 Framework，再签外层。
while IFS= read -r fw; do
  [[ -n "$fw" ]] || continue
  if should_skip_tool "$fw"; then
    log_skip_once "$fw"
    continue
  fi
  csign "$fw" --deep
done < <(find "$TOOLS_DIR" -name "*.framework" -type d 2>/dev/null | awk -F'/' '{ print NF, $0 }' | sort -rn | cut -d' ' -f2-)

# 2) 仅签「不在 .framework 内」的 .dylib / .so。
#    若对 Framework 整包 --deep 后再单独 codesign 其内部的 dylib/so，会破坏密封，公证报 Python 等 invalid signature。
while IFS= read -r -d '' f; do
  if should_skip_tool "$f"; then
    log_skip_once "$f"
    continue
  fi
  in_framework_path "$f" && continue
  csign "$f"
done < <(find "$TOOLS_DIR" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 2>/dev/null)

# 3) 其余 Mach-O（可执行文件、无后缀二进制等；跳过 .framework 内已 deep 签名的内容）
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  if should_skip_tool "$f"; then
    log_skip_once "$f"
    continue
  fi
  # 跳过符号链接：避免对 _internal/Python 这类指向 framework 内目标的路径二次签名
  [[ -L "$f" ]] && continue
  [[ "$f" == *.dylib ]] && continue
  [[ "$f" == *.so ]] && continue
  in_framework_path "$f" && continue
  case "$f" in
  *.py|*.pyc|*.json|*.txt|*.md|*.zip|*.html|*.css|*.js|*.png|*.icns) continue ;;
  esac
  file "$f" 2>/dev/null | grep -q "Mach-O" || continue
  csign "$f"
done < <(find "$TOOLS_DIR" -type f 2>/dev/null)

echo "[sign_dist_tools_developer_id] 完成。"
