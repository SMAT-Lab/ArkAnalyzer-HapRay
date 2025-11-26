#!/usr/bin/env python3
"""
诊断 performance_analysis 字段缺失问题
"""

import json
import sys
from pathlib import Path

def check_cache_file(cache_file: Path):
    """检查缓存文件"""
    print(f'\n检查缓存文件: {cache_file}')
    if not cache_file.exists():
        print('  ✅ 缓存文件不存在，不会影响新分析')
        return
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        
        total_entries = len(cache)
        missing_perf_analysis = 0
        has_perf_analysis = 0
        
        for key, value in cache.items():
            # 检查新格式
            if isinstance(value, dict) and 'analysis' in value:
                analysis = value['analysis']
                if 'performance_analysis' in analysis:
                    if analysis.get('performance_analysis'):
                        has_perf_analysis += 1
                    else:
                        missing_perf_analysis += 1
                else:
                    missing_perf_analysis += 1
            # 检查旧格式
            elif isinstance(value, dict):
                if 'performance_analysis' in value:
                    if value.get('performance_analysis'):
                        has_perf_analysis += 1
                    else:
                        missing_perf_analysis += 1
                else:
                    missing_perf_analysis += 1
        
        print(f'  总缓存条目: {total_entries}')
        print(f'  有 performance_analysis 字段: {has_perf_analysis}')
        print(f'  缺少或为空 performance_analysis 字段: {missing_perf_analysis}')
        
        if missing_perf_analysis > 0:
            print(f'  ⚠️  发现 {missing_perf_analysis} 个缓存条目缺少 performance_analysis 字段')
            print(f'  建议：删除缓存文件重新分析')
            print(f'  命令：rm {cache_file}')
    except Exception as e:
        print(f'  ❌ 读取缓存文件失败: {e}')

def check_prompt_file(prompt_file: Path):
    """检查 prompt 文件"""
    print(f'\n检查 prompt 文件: {prompt_file}')
    if not prompt_file.exists():
        print('  ⚠️  Prompt 文件不存在（可能未启用 --save-prompts）')
        return
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'performance_analysis' in content:
            print('  ✅ Prompt 中包含 performance_analysis 字段要求')
        else:
            print('  ❌ Prompt 中未找到 performance_analysis 字段要求')
            print('  这可能是问题所在！')
        
        if '负载问题识别与优化建议' in content:
            print('  ✅ Prompt 中包含"负载问题识别与优化建议"说明')
        else:
            print('  ⚠️  Prompt 中未找到"负载问题识别与优化建议"说明')
    except Exception as e:
        print(f'  ❌ 读取 prompt 文件失败: {e}')

def check_response_file(response_file: Path):
    """检查 LLM 响应文件"""
    print(f'\n检查 LLM 响应文件: {response_file}')
    if not response_file.exists():
        print('  ⚠️  响应文件不存在（可能未启用 --save-prompts）')
        return
    
    try:
        with open(response_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '"performance_analysis"' in content:
            print('  ✅ 响应中包含 performance_analysis 字段')
            # 尝试提取一些示例
            import re
            matches = re.findall(r'"performance_analysis"\s*:\s*"([^"]+)"', content)
            if matches:
                print(f'  找到 {len(matches)} 个 performance_analysis 值')
                for i, match in enumerate(matches[:3], 1):
                    print(f'    示例 {i}: {match[:50]}...')
        else:
            print('  ❌ 响应中未找到 performance_analysis 字段')
            print('  这可能是问题所在！LLM 可能没有返回该字段')
    except Exception as e:
        print(f'  ❌ 读取响应文件失败: {e}')

def main():
    print('=' * 80)
    print('诊断 performance_analysis 字段缺失问题')
    print('=' * 80)
    
    # 检查缓存文件
    cache_file = Path('.cache/llm_cache.json')
    check_cache_file(cache_file)
    
    # 检查 prompt 文件（查找最新的）
    prompt_dir = Path('prompts')
    if prompt_dir.exists():
        prompt_files = sorted(prompt_dir.glob('prompt_*.txt'), key=lambda p: p.stat().st_mtime, reverse=True)
        if prompt_files:
            check_prompt_file(prompt_files[0])
        else:
            print('\n⚠️  未找到 prompt 文件（可能未启用 --save-prompts）')
    
    # 检查响应文件（查找最新的）
    response_dir = Path('prompts')
    if response_dir.exists():
        response_files = sorted(response_dir.glob('llm_response_*.txt'), key=lambda p: p.stat().st_mtime, reverse=True)
        if response_files:
            check_response_file(response_files[0])
        else:
            print('\n⚠️  未找到响应文件（可能未启用 --save-prompts）')
    
    print('\n' + '=' * 80)
    print('诊断完成')
    print('=' * 80)
    print('\n建议：')
    print('1. 如果缓存文件中有旧数据，删除缓存重新分析：')
    print('   rm .cache/llm_cache.json')
    print('2. 如果 prompt 中缺少 performance_analysis 字段要求，检查代码')
    print('3. 如果响应中缺少 performance_analysis 字段，检查 LLM 是否理解要求')
    print('4. 运行分析时使用 --save-prompts 参数保存 prompt 和响应，便于调试')

if __name__ == '__main__':
    main()

