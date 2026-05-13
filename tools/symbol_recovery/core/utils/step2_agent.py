"""Step2 编排：任务切批、合并、以及 OpenAI 兼容 API 直连（供 CLI 与 perf_testing 内联调用）。"""

from __future__ import annotations

import json
import re
import sys
import time
from argparse import Namespace
from glob import glob
from pathlib import Path
from typing import Optional


def func_id_key(fid: str) -> tuple[int, str]:
    m = re.match(r'^func_(\d+)$', str(fid or ''))
    if m:
        return (int(m.group(1)), fid or '')
    return (10**9, fid or '')


def split_symbol_recovery_tasks(tasks_path: Path, output_dir: Path, batch_size: int = 10) -> dict:
    """将 symbol_recovery_llm_tasks.json 切分为多批 JSON。返回 meta 字典。"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[dict] = json.loads(Path(tasks_path).read_text(encoding='utf-8'))
    n = len(tasks)
    bs = max(1, int(batch_size))
    batches: list[list[dict]] = [tasks[i : i + bs] for i in range(0, n, bs)]
    meta = {'total_tasks': n, 'batch_size': bs, 'batch_count': len(batches), 'source_tasks': str(tasks_path)}

    for idx, chunk in enumerate(batches, start=1):
        name = f'batch_{idx:03d}_of_{len(batches):03d}.json'
        (out_dir / name).write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding='utf-8')

    (out_dir / 'agent_batches_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return meta


def merge_symbol_recovery_agent_results(output_path: Path, result_files: list[str]) -> int:
    """合并 Agent 产出的多份结果 JSON。result_files 可为 glob 模式。返回合并后的条数。"""
    paths: list[Path] = []
    for p in result_files:
        paths.extend(glob(p, recursive=False))
    paths = sorted({Path(p).resolve() for p in paths if Path(p).is_file()})
    if not paths:
        return 0

    merged: list[dict] = []
    for p in paths:
        raw = json.loads(Path(p).read_text(encoding='utf-8'))
        if isinstance(raw, list):
            merged.extend(raw)
        elif isinstance(raw, dict):
            merged.extend(raw.get('functions') or raw.get('results') or raw.get('tasks') or [])
        else:
            print(f'⚠️  跳过无法解析的文件：{p}')

    merged.sort(key=lambda r: func_id_key(str(r.get('function_id', ''))))
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    return len(merged)


def _load_dotenv_sr_root(sr_root: Optional[Path]) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if sr_root is not None:
        load_dotenv(sr_root / '.env', override=False)


def _extract_json(text: str) -> dict:
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


def run_openai_symbol_recovery_tasks(
    tasks_path: Path,
    output_path: Path,
    *,
    model: Optional[str] = None,
    delay: float = 0.5,
    resume: bool = False,
    sr_root: Optional[Path] = None,
) -> tuple[int, int]:
    """使用 OpenAI 兼容 API 逐条推断。返回 (成功条数, 任务总数)。"""
    _load_dotenv_sr_root(sr_root)
    if sr_root is not None:
        root_s = str(sr_root.resolve())
        if root_s not in sys.path:
            sys.path.insert(0, root_s)

    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError('未找到 openai 库，请先安装：uv pip install openai') from e

    from core.utils.config import config

    tasks_path = Path(tasks_path)
    output_path = Path(output_path)
    if not tasks_path.exists():
        raise FileNotFoundError(f'找不到任务文件：{tasks_path}')

    tasks: list[dict] = json.loads(tasks_path.read_text(encoding='utf-8'))

    results: list[dict] = []
    done_ids: set[str] = set()
    if resume and output_path.exists():
        existing = json.loads(output_path.read_text(encoding='utf-8'))
        if isinstance(existing, list):
            results = existing
        elif isinstance(existing, dict):
            results = existing.get('functions') or existing.get('results') or existing.get('tasks') or []
        done_ids = {r['function_id'] for r in results if r.get('function_id')}

    llm_cfg = config.get_llm_config()
    api_key = llm_cfg['api_key']
    base_url = llm_cfg['base_url']
    use_model = model or llm_cfg['model']
    timeout = llm_cfg.get('timeout', 60)

    if not api_key:
        raise RuntimeError('未找到 API Key（.env 或环境变量）。若要用对话 Agent 推断，请使用 split/merge 或 HAPRAY_SYMBOL_RECOVERY_AGENT_CMD。')

    client = OpenAI(api_key=api_key, base_url=base_url)
    success = 0
    for i, task in enumerate(tasks):
        fid = task.get('function_id', f'func_{i + 1}')
        if fid in done_ids:
            continue

        try:
            response = client.chat.completions.create(
                model=use_model,
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
            result = _extract_json(text)
            result['function_id'] = fid
            results.append(result)
            success += 1
        except Exception as e:
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

        if delay > 0 and i < len(tasks) - 1:
            time.sleep(delay)

    return success + len(done_ids), len(tasks)


def cmd_split(args: Namespace) -> None:
    meta = split_symbol_recovery_tasks(Path(args.tasks), Path(args.output_dir), int(args.batch_size))
    n = meta['total_tasks']
    bc = meta['batch_count']
    bs = meta['batch_size']
    out_dir = Path(args.output_dir)
    print(f'📋 总任务 {n} 条 → 切成 {bc} 批（每批最多 {bs} 条）')
    print(f'📂 输出目录：{out_dir.resolve()}')
    print()
    print('切分等价命令（推荐，在 symbol_recovery 根目录）：')
    print(
        f'  python main.py --step2-split --step2-tasks {args.tasks} '
        f'--step2-split-out-dir {args.output_dir} --step2-split-batch-size {int(args.batch_size)}'
    )
    print()
    print('下一步（在 Cursor 对话中交给 Agent，使用当前对话模型，而非 .env）：')
    print(f'  - 依次读取 {out_dir}/batch_*_of_*.json（任务切片，勿改 function_id）')
    print('  - 对每条任务按 prompt / expected_schema 推断，收集为 JSON 数组')
    print(f'  - 将对应批的结果写入同目录，例如 batch_001_of_004_results.json（与输入批编号一致）')
    print()
    print('合并命令示例（在 symbol_recovery 根目录，勿使用 scripts/run_step2.py）：')
    print(
        '  python main.py --step2-merge --step2-merge-output symbol_recovery_external_results.json \\\n'
        f'    --step2-merge-input "{out_dir}/batch_*_results.json"'
    )


def cmd_merge(args: Namespace) -> None:
    out = Path(args.output)
    cnt = merge_symbol_recovery_agent_results(out, list(args.result_files))
    if cnt <= 0:
        print('❌ 未找到任何结果文件，请检查 merge 参数中的 glob/路径')
        sys.exit(1)
    merged = json.loads(out.read_text(encoding='utf-8'))
    paths: list[Path] = []
    for p in args.result_files:
        paths.extend(glob(p, recursive=False))
    paths = sorted({Path(p).resolve() for p in paths if Path(p).is_file()})
    ids = {r.get('function_id') for r in merged if isinstance(r, dict) and r.get('function_id')}
    print(f'✅ 合并 {len(paths)} 个文件 → {len(merged)} 条记录（唯一 function_id: {len(ids)}）')
    print(f'📄 {out.resolve()}')


def cmd_openai(args: Namespace) -> None:
    sr_root = Path(__file__).resolve().parent.parent.parent
    try:
        ok, total = run_openai_symbol_recovery_tasks(
            Path(args.tasks),
            Path(args.output),
            model=getattr(args, 'model', None),
            delay=float(getattr(args, 'delay', 0.5)),
            resume=bool(getattr(args, 'resume', False)),
            sr_root=sr_root,
        )
    except Exception as e:
        print(f'❌ {e}')
        sys.exit(1)
    print(f'✅ 完成！成功推断 {ok}/{total} 条 → {Path(args.output).resolve()}')
