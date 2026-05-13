#!/usr/bin/env python3
"""
兼容入口（不推荐新脚本依赖）：历史上用于 split/merge/openai 子命令。

**正式入口**请使用仓库根 ``main.py``（或打包后的 ``symbol-recovery`` 可执行文件）上的：

- ``--step2-split`` / ``--step2-tasks`` / ``--step2-split-out-dir`` / ``--step2-split-batch-size``
- ``--step2-merge`` / ``--step2-merge-output`` / ``--step2-merge-input``（可重复）
- ``--step2-openai`` / ``--step2-tasks`` / ``--step2-output`` 等

实现均在 ``core.utils.step2_agent``；HapRay 集成路径**不得**再调用本脚本路径。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.utils.step2_agent import cmd_merge, cmd_openai, cmd_split  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] not in ('split', 'merge', 'openai', '-h', '--help'):
        if '--tasks' in sys.argv and '--output' in sys.argv:
            sys.argv.insert(1, 'openai')

    parser = argparse.ArgumentParser(
        description='[兼容] 离线 Step2：请优先使用 main.py --step2-*（见 main --help）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_split = sub.add_parser('split', help='切分为多份 JSON，供 Cursor Agent 逐批推断（推荐）')
    p_split.add_argument('--tasks', required=True, help='symbol_recovery_llm_tasks.json')
    p_split.add_argument('--output-dir', required=True, help='输出 batch JSON 的目录')
    p_split.add_argument('--batch-size', type=int, default=10, help='每批最多条数（默认 10）')
    p_split.set_defaults(func=cmd_split)

    p_merge = sub.add_parser('merge', help='合并 Agent 产出的多份 *_results.json')
    p_merge.add_argument('--output', required=True, help='合并后的 JSON 路径')
    p_merge.add_argument(
        'result_files',
        nargs='+',
        help='结果文件路径或 glob，例如 output/batch_*_results.json',
    )
    p_merge.set_defaults(func=cmd_merge)

    p_api = sub.add_parser('openai', help='[可选] 使用 .env 直连 OpenAI 兼容 API（非 Agent）')
    p_api.add_argument('--tasks', required=True)
    p_api.add_argument('--output', required=True)
    p_api.add_argument('--model', help='覆盖 .env 中的模型')
    p_api.add_argument('--delay', type=float, default=0.5)
    p_api.add_argument('--resume', action='store_true')
    p_api.set_defaults(func=cmd_openai)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
