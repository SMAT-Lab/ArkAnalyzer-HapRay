#!/usr/bin/env python3
"""
离线编排第二步：批量调用 LLM 处理 symbol_recovery_llm_tasks.json，产出 llm_results.json。

用法：
    python3 scripts/run_step2.py \
        --tasks output/symbol_recovery_llm_tasks.json \
        --output output/llm_results.json

使用 tools/symbol_recovery/.env 中的 LLM 配置，无需额外参数。
支持 --resume 断点续传（中断后重跑跳过已完成条目）。
"""

import json
import sys
import time
import argparse
from pathlib import Path

# 把 tools/symbol_recovery 加入 sys.path，复用 config 模块
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
from core.utils.logger import get_logger

logger = get_logger('run_step2')


def extract_json(text: str) -> dict:
    """从 LLM 响应文本中提取 JSON 对象。"""
    text = text.strip()
    # 去掉 markdown 代码块
    if '```' in text:
        for part in text.split('```'):
            part = part.strip()
            if part.startswith('json'):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    # 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 找第一个完整的 { ... }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    raise ValueError(f'无法从响应中提取 JSON，原始内容前 300 字符：{text[:300]}')


def main():
    parser = argparse.ArgumentParser(
        description='离线编排第二步：批量调用 LLM 分析 ARM64 反汇编函数',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--tasks', required=True, help='symbol_recovery_llm_tasks.json 路径')
    parser.add_argument('--output', required=True, help='结果 JSON 输出路径（llm_results.json）')
    parser.add_argument('--model', help='覆盖 .env 中的模型名称')
    parser.add_argument('--delay', type=float, default=0.5, help='每次请求后等待秒数（默认 0.5，防限流）')
    parser.add_argument('--resume', action='store_true', help='断点续传：跳过输出文件中已完成的条目')
    args = parser.parse_args()

    tasks_path = Path(args.tasks)
    output_path = Path(args.output)

    if not tasks_path.exists():
        print(f'❌ 找不到任务文件：{tasks_path}')
        sys.exit(1)

    tasks: list[dict] = json.loads(tasks_path.read_text(encoding='utf-8'))
    print(f'📋 任务总数：{len(tasks)} 条')

    # 断点续传：读取已有结果
    results: list[dict] = []
    done_ids: set[str] = set()
    if args.resume and output_path.exists():
        existing = json.loads(output_path.read_text(encoding='utf-8'))
        if isinstance(existing, list):
            results = existing
        elif isinstance(existing, dict):
            results = existing.get('functions') or existing.get('results') or existing.get('tasks') or []
        done_ids = {r['function_id'] for r in results if r.get('function_id')}
        remaining = len(tasks) - len(done_ids)
        print(f'📂 续传模式：已完成 {len(done_ids)} 条，剩余 {remaining} 条')

    # 读取 LLM 配置
    llm_cfg = config.get_llm_config()
    api_key = llm_cfg['api_key']
    base_url = llm_cfg['base_url']
    model = args.model or llm_cfg['model']
    timeout = llm_cfg.get('timeout', 60)

    if not api_key:
        print('❌ 未找到 API Key，请检查 tools/symbol_recovery/.env 配置')
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f'🤖 模型：{model}  base_url：{base_url}')
    print()

    success = 0
    for i, task in enumerate(tasks):
        fid = task.get('function_id', f'func_{i+1}')
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
            results.append({
                'function_id': fid,
                'functionality': '分析失败',
                'function_name': None,
                'confidence': '低',
                'performance_analysis': '',
                'reasoning': str(e),
            })

        # 每条写盘，支持中断续传
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8'
        )

        if args.delay > 0 and i < len(tasks) - 1:
            time.sleep(args.delay)

    print()
    print(f'✅ 完成！成功推断 {success + len(done_ids)}/{len(tasks)} 条 → {output_path}')


if __name__ == '__main__':
    main()
