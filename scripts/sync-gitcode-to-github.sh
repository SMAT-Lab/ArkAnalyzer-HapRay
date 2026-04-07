#!/usr/bin/env bash
# 将 gitcode（origin）上的 main、dev 同步到 GitHub（github）同名分支。
# 用法：在仓库根目录执行 ./scripts/sync-gitcode-to-github.sh
#
# origin / github 若不存在会自动添加（本仓库默认 URL）；若已存在则不改 URL。
# 手动配置示例：
#   git remote add origin git@gitcode.com:SMAT/ArkAnalyzer-HapRay.git
#   git remote add github git@github.com:SMAT-Lab/ArkAnalyzer-HapRay.git
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "==> git remote add origin git@gitcode.com:SMAT/ArkAnalyzer-HapRay.git"
  git remote add origin git@gitcode.com:SMAT/ArkAnalyzer-HapRay.git
fi
if ! git remote get-url github >/dev/null 2>&1; then
  echo "==> git remote add github git@github.com:SMAT-Lab/ArkAnalyzer-HapRay.git"
  git remote add github git@github.com:SMAT-Lab/ArkAnalyzer-HapRay.git
fi

echo "==> git fetch origin"
git fetch origin

for branch in main dev; do
  if ! git show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
    echo "错误: origin 上不存在 ${branch} 分支" >&2
    exit 1
  fi
done

echo "==> git push github origin/main -> main"
git push github origin/main:refs/heads/main

echo "==> git push github origin/dev -> dev"
git push github origin/dev:refs/heads/dev

echo "完成: GitHub 已与 gitcode 对齐（main + dev）。"
