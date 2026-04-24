#!/usr/bin/env python3
"""
离线编排第二步（与 Cursor / GUI Agent 对齐）：

默认：把 symbol_recovery_llm_tasks.json 切成多份，交给 **对话里的 Agent 模型** 逐批推断，
     再合并为一份结果 JSON 供 --import-llm-results 使用。**不读取 .env、不直连 LLM API。**

可选：--openai 保留旧行为，使用 tools/symbol_recovery/.env 中的 API 配置（仅在你刻意脱离 Agent 时用）。

用法（推荐，走 Agent）：
    # 1) 切批（每批 10 条，可调）
    python3 scripts/run_step2.py split \\
        --tasks output/symbol_recovery_llm_tasks.json \\
        --output-dir output/agent_batches \\
        --batch-size 10

    # 2) 在 Cursor 里让 Agent 读取各 batch JSON，按 expected_schema 写出
    #    output/agent_batches/batch_001_results.json …

    # 3) 合并
    python3 scripts/run_step2.py merge \\
        --output output/symbol_recovery_external_results.json \\
        output/agent_batches/batch_*_results.json

旧用法（直连 OpenAI 兼容 API，需 .env）：
    python3 scripts/run_step2.py openai \\
        --tasks output/symbol_recovery_llm_tasks.json \\
        --output output/llm_results.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from glob import glob
from pathlib import Path


def _func_id_key(fid: str) -> tuple[int, str]:
    m = re.match(r'^func_(\d+)$', str(fid or ''))
    if m:
        return (int(m.group(1)), fid or '')
    return (10**9, fid or '')


def cmd_split(args: argparse.Namespace) -> None:
    tasks_path = Path(args.tasks)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[dict] = json.loads(tasks_path.read_text(encoding='utf-8'))
    n = len(tasks)
    bs = max(1, int(args.batch_size))
    batches: list[list[dict]] = [tasks[i : i + bs] for i in range(0, n, bs)]
    meta = {'total_tasks': n, 'batch_size': bs, 'batch_count': len(batches), 'source_tasks': str(tasks_path)}

    for idx, chunk in enumerate(batches, start=1):
        name = f'batch_{idx:03d}_of_{len(batches):03d}.json'
        (out_dir / name).write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding='utf-8')

    (out_dir / 'agent_batches_meta.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(f'📋 总任务 {n} 条 → 切成 {len(batches)} 批（每批最多 {bs} 条）')
    print(f'📂 输出目录：{out_dir.resolve()}')
    print()
    print('下一步（在 Cursor 对话中交给 Agent，使用当前对话模型，而非 .env）：')
    print(f'  - 依次读取 {out_dir}/batch_*_of_*.json（任务切片，勿改 function_id）')
    print('  - 对每条任务按 prompt / expected_schema 推断，收集为 JSON 数组')
    print(
        f'  - 将对应批的结果写入同目录，例如 batch_001_of_004_results.json（与输入批编号一致）'
    )
    print()
    print('合并命令示例：')
    print(
        f'  python3 scripts/run_step2.py merge --output symbol_recovery_external_results.json '
        f'"{out_dir}/batch_*_results.json"'
    )


def cmd_merge(args: argparse.Namespace) -> None:
    paths = []
    for p in args.result_files:
        paths.extend(glob(p, recursive=False))
    paths = sorted({Path(p).resolve() for p in paths if Path(p).is_file()})
    if not paths:
        print('❌ 未找到任何结果文件，请检查 merge 参数中的 glob/路径')
        sys.exit(1)

    merged: list[dict] = []
    for p in paths:
        raw = json.loads(Path(p).read_text(encoding='utf-8'))
        if isinstance(raw, list):
            merged.extend(raw)
        elif isinstance(raw, dict):
            merged.extend(raw.get('functions') or raw.get('results') or raw.get('tasks') or [])
        else:
            print(f'⚠️  跳过无法解析的文件：{p}')

    merged.sort(key=lambda r: _func_id_key(r.get('function_id', '')))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    ids = {r.get('function_id') for r in merged if r.get('function_id')}
    print(f'✅ 合并 {len(paths)} 个文件 → {len(merged)} 条记录（唯一 function_id: {len(ids)}）')
    print(f'📄 {out.resolve()}')


def cmd_openai(args: argparse.Namespace) -> None:
    """旧路径：直连 OpenAI 兼容 API（需 .env）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    except ImportError:
        pass

    try:
        from openai import OpenAI
    except ImportError:
        print('❌ 未找到 openai 库，请先安装：uv pip install openai')
        sys.exit(1)

    from core.utils.config import config

    tasks_path = Path(args.tasks)
    output_path = Path(args.output)

    if not tasks_path.exists():
        print(f'❌ 找不到任务文件：{tasks_path}')
        sys.exit(1)

    tasks: list[dict] = json.loads(tasks_path.read_text(encoding='utf-8'))
    print(f'📋 任务总数：{len(tasks)} 条（--openai 直连 API，使用 .env）')

    results: list[dict] = []
    done_ids: set[str] = set()
    if args.resume and output_path.exists():
        existing = json.loads(output_path.read_text(encoding='utf-8'))
        if isinstance(existing, list):
            results = existing
        elif isinstance(existing, dict):
            results = existing.get('functions') or existing.get('results') or existing.get('tasks') or []
        done_ids = {r['function_id'] for r in results if r.get('function_id')}
        print(f'📂 续传模式：已完成 {len(done_ids)} 条')

    llm_cfg = config.get_llm_config()
    api_key = llm_cfg['api_key']
    base_url = llm_cfg['base_url']
    model = args.model or llm_cfg['model']
    timeout = llm_cfg.get('timeout', 60)

    if not api_key:
        print('❌ 未找到 API Key。若要用 Agent 模型，请改用：python3 scripts/run_step2.py split ...')
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f'🤖 模型：{model}  base_url：{base_url}')
    print()

    def extract_json(text: str) -> dict:
        text = text.strip()
        if '```' in text:
            for part in text.split('```'):
                part = part.strip()
                if part.startswith('json'):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue
        try:
            return json.loads(text)
        except Exception:
            pass
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        raise ValueError(f'无法从响应中提取 JSON，原始内容前 300 字符：{text[:300]}')

    success = 0
    for i, task in enumerate(tasks):
        fid = task.get('function_id', f'func_{i + 1}')
        if fid in done_ids:
            continue

        addr = task.get('address', fid)
        rank = task.get('rank', i + 1)
        print(f'[{rank}/{len(tasks)}] {addr} ... ', end='', flush=True)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            '你是一个专业的逆向工程专家，擅长分析 ARM64 汇编代码并推断函数功能和函数名。'
                            '请严格按 JSON 格式返回结果，不要有其他内容。'
                        ),
                    },
                    {'role': 'user', 'content': task['prompt']},
                ],
                temperature=0.0,
                max_tokens=1500,
                timeout=timeout,
            )
            text = response.choices[0].message.content or ''
            result = extract_json(text)
            result['function_id'] = fid
            results.append(result)

            name = result.get('function_name') or result.get('inferred_name') or '(无推断名)'
            conf = result.get('confidence', '?')
            print(f'✅ [{conf}] {name}')
            success += 1

        except Exception as e:
            print(f'⚠️  失败：{e}')
            results.append(
                {
                    'function_id': fid,
                    'functionality': '分析失败',
                    'function_name': None,
                    'confidence': '低',
                    'performance_analysis': '',
                    'reasoning': str(e),
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

        if args.delay > 0 and i < len(tasks) - 1:
            time.sleep(args.delay)

    print()
    print(f'✅ 完成！成功推断 {success + len(done_ids)}/{len(tasks)} 条 → {output_path}')


def main() -> None:
    # 兼容旧用法：python3 run_step2.py --tasks T --output O  →  openai 子命令
    if len(sys.argv) > 1 and sys.argv[1] not in ('split', 'merge', 'openai', '-h', '--help'):
        if '--tasks' in sys.argv and '--output' in sys.argv:
            sys.argv.insert(1, 'openai')

    parser = argparse.ArgumentParser(
        description='离线 Step2：默认切批/合并给 Agent；可选 openai 子命令直连 API。',
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
