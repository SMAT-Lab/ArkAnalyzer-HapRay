#!/usr/bin/env python3
"""
通用工具函数模块
提供公共的工具函数，避免代码重复
"""

import json
import re
from pathlib import Path

import pandas as pd
from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Capstone 反汇编器
# ============================================================================


def create_disassembler():
    """创建并配置 ARM64 Capstone 反汇编器"""
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    return md


def parse_offset(offset_str):
    """
    解析偏移量字符串（统一的偏移量解析逻辑）

    Args:
        offset_str: 偏移量字符串，可能是:
            - "0x123456" (十六进制)
            - "123456" (十六进制或十进制)
            - "libxwebcore.so+0x12345678" (文件名+偏移)

    Returns:
        偏移量（整数），如果解析失败返回 None
    """
    if pd.isna(offset_str) or not offset_str:
        return None

    offset_str = str(offset_str).strip()

    # 如果包含 "+"，提取 "+" 后面的部分（如 libxwebcore.so+0x2489250 -> 0x2489250）
    if '+' in offset_str:
        # 匹配格式：文件名+0x十六进制数
        match = re.search(r'\+0x([0-9a-fA-F]+)', offset_str)
        if match:
            try:
                return int(match.group(1), 16)
            except ValueError:
                return None
        # 如果没有匹配到，尝试提取 + 后面的部分
        offset_str = offset_str.split('+')[-1]

    # 移除可能的空格和特殊字符
    offset_str = offset_str.replace(' ', '').replace('-', '')

    # 尝试解析十六进制
    try:
        if offset_str.startswith('0x') or offset_str.startswith('0X'):
            return int(offset_str, 16)
        # 尝试作为十六进制解析（如果全是十六进制字符）
        if all(c in '0123456789abcdefABCDEF' for c in offset_str):
            return int(offset_str, 16)
        # 否则作为十进制解析
        return int(offset_str, 10)
    except ValueError:
        return None


def find_function_start(elf_file, vaddr, disassembler):
    """
    查找函数的起始位置（统一的函数起始查找逻辑）
    优先使用符号表，否则向前查找函数序言

    Args:
        elf_file: ELF 文件对象
        vaddr: 虚拟地址
        disassembler: Capstone 反汇编器实例

    Returns:
        函数起始地址
    """
    func_start = vaddr

    try:
        # 首先尝试从符号表获取函数的真正起始地址
        try:
            for section_name in ['.dynsym', '.symtab']:
                symbol_table = elf_file.get_section_by_name(section_name)
                if symbol_table:
                    for symbol in symbol_table.iter_symbols():
                        if symbol['st_info']['type'] == 'STT_FUNC':
                            sym_addr = symbol['st_value']
                            sym_size = symbol['st_size']
                            # 检查地址是否在这个符号范围内
                            if sym_size > 0 and sym_addr <= vaddr < sym_addr + sym_size:
                                func_start = sym_addr
                                logger.info(f'从符号表获取函数起始地址: 0x{func_start:x} (符号: {symbol.name})')
                                return func_start
        except Exception:
            # 符号表查找失败，继续使用向前查找方法
            pass

        # 如果符号表不可用，使用向前查找函数序言的方法
        # 获取 .text 段
        text_section = None
        for section in elf_file.iter_sections():
            if section.name == '.text':
                text_section = section
                break

        if not text_section:
            return vaddr

        text_vaddr = text_section['sh_addr']
        text_size = text_section['sh_size']

        # 确保地址在 .text 段内
        if vaddr < text_vaddr or vaddr >= text_vaddr + text_size:
            return vaddr

        # 向前查找函数开始（增加查找范围到 2000 字节，以支持大型函数）
        # 注意：vaddr 可能是函数中的某个位置，需要向前查找真正的函数起始
        search_start = max(text_vaddr, vaddr - 2000)
        relative_start = search_start - text_vaddr
        relative_end = vaddr - text_vaddr + 100  # 向后也读取一些

        # 读取代码
        code = text_section.data()[relative_start:relative_end]

        if not code:
            return vaddr

        # 反汇编
        forward_instructions = []
        for inst in disassembler.disasm(code, search_start):
            if inst.address <= vaddr:
                forward_instructions.append(inst)

        # 反向查找函数序言（ARM64 函数序言的常见模式）
        # 1. pacibsp (PAC 保护)
        # 2. stp x29, x30, [sp, #-N]! (保存帧指针和返回地址)
        # 3. sub sp, sp, #N; stp x29, x30, [sp, #M] (分两步的序言)
        # 4. stp x29, x30, [sp, #-N]!; mov x29, sp (完整的序言)

        # 查找最近的函数序言标记
        last_pacibsp = None
        last_stp_fp_lr = None
        last_sub_sp = None

        for inst in reversed(forward_instructions):
            # 查找 pacibsp（通常是最早的指令）
            if inst.mnemonic == 'pacibsp':
                last_pacibsp = inst.address
                func_start = inst.address
                break
            # 查找 stp x29, x30, [sp, ...]! (保存帧指针和返回地址)
            if inst.mnemonic == 'stp' and 'x29' in inst.op_str and 'x30' in inst.op_str:
                if '[sp' in inst.op_str and ']!' in inst.op_str:
                    last_stp_fp_lr = inst.address
                    # 如果这是第一个找到的，先记录，继续查找是否有 pacibsp
                    if func_start == vaddr:
                        func_start = inst.address
            # 查找 sub sp, sp, #N (栈分配，通常在 stp 之前)
            elif inst.mnemonic == 'sub' and 'sp' in inst.op_str and 'sp' in inst.op_str:
                last_sub_sp = inst.address

        # 如果找到了 pacibsp，使用它作为函数起始
        if last_pacibsp:
            func_start = last_pacibsp
        # 否则，如果找到了 stp x29, x30，使用它
        elif last_stp_fp_lr:
            func_start = last_stp_fp_lr
            # 检查前面是否有 sub sp（如果有，使用 sub sp 作为起始）
            if last_sub_sp and last_sub_sp < last_stp_fp_lr:
                func_start = last_sub_sp

        if func_start != vaddr:
            logger.info(f'通过函数序言查找函数起始地址: 0x{func_start:x} (从 0x{vaddr:x} 向前查找)')

        return func_start
    except Exception:
        logger.exception('查找函数起始位置失败')
        return vaddr


# ============================================================================
# HTML 报告渲染
# ============================================================================


def render_html_report(results, llm_analyzer=None, time_tracker=None, title='缺失符号函数分析报告'):
    """渲染 HTML 报告内容"""
    use_event_count = any('event_count' in r and r.get('event_count', 0) > 0 for r in results)

    token_stats = None
    if llm_analyzer:
        try:
            token_stats = llm_analyzer.get_token_stats()
        except Exception:
            token_stats = None
    else:
        token_stats_file = Path('cache/llm_token_stats.json')
        if token_stats_file.exists():
            try:
                with token_stats_file.open('r', encoding='utf-8') as f:
                    saved_stats = json.load(f)
                total_requests = saved_stats.get('total_requests', 0)
                cached_requests = saved_stats.get('cached_requests', 0)
                total_input_tokens = saved_stats.get('total_input_tokens', 0)
                total_output_tokens = saved_stats.get('total_output_tokens', 0)
                total_tokens = saved_stats.get('total_tokens', 0)
                actual_requests = total_requests - cached_requests
                token_stats = {
                    'total_requests': total_requests,
                    'cached_requests': cached_requests,
                    'total_input_tokens': total_input_tokens,
                    'total_output_tokens': total_output_tokens,
                    'total_tokens': total_tokens,
                    'average_input_tokens': total_input_tokens / actual_requests if actual_requests > 0 else 0,
                    'average_output_tokens': total_output_tokens / actual_requests if actual_requests > 0 else 0,
                }
            except Exception:
                token_stats = None

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .rank {{ font-weight: bold; color: #4CAF50; }}
        .address {{ font-family: 'Courier New', monospace; font-size: 0.9em; }}
        .call-count {{ text-align: right; font-weight: bold; }}
        .confidence-high {{ color: #4CAF50; font-weight: bold; }}
        .confidence-medium {{ color: #FF9800; font-weight: bold; }}
        .confidence-low {{ color: #f44336; }}
        .functionality {{ max-width: 400px; word-wrap: break-word; }}
        .strings {{ font-family: 'Courier New', monospace; font-size: 0.85em; max-width: 300px; word-wrap: break-word; }}
        .section {{
            margin-top: 40px;
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }}
        .section h2 {{
            color: #333;
            margin-top: 0;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .token-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .token-stat-item {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }}
        .token-stat-label {{ font-size: 0.9em; color: #666; margin-bottom: 5px; }}
        .token-stat-value {{ font-size: 1.5em; font-weight: bold; color: #4CAF50; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p>共分析了 <strong>{len(results)}</strong> 个函数</p>
"""

    html += """
        <div class="section">
            <h2>📚 技术原理</h2>
            <h3>为什么会出现符号缺失？</h3>
            <p>在性能分析过程中，<code>perf.data</code> 文件中出现符号缺失（显示为 <code>libxwebcore.so+0x...</code>）的主要原因包括：</p>
            <ul>
                <li><strong>符号表剥离</strong>：生产版本的 SO 文件通常会剥离 <code>.symtab</code> 以减小大小，仅保留 <code>.dynsym</code>。</li>
                <li><strong>动态符号表限制</strong>：<code>.dynsym</code> 只包含导出函数，内部函数不会出现。</li>
                <li><strong>编译器优化</strong>：函数内联、死代码消除等可能导致符号丢失。</li>
                <li><strong>地址映射问题</strong>：ASLR 和动态加载导致地址映射不准确。</li>
                <li><strong>JIT 代码</strong>：动态生成的代码没有静态符号。</li>
            </ul>
            <h3>解决方案</h3>
            <ol>
                <li><strong>反汇编分析</strong>：使用 Capstone 对函数反汇编。</li>
                <li><strong>上下文提取</strong>：提取字符串常量、调用信息作为上下文。</li>
                <li><strong>LLM 推断</strong>：利用大模型推断功能和函数名。</li>
                <li><strong>置信度评估</strong>：根据指令数量和上下文评估置信度。</li>
            </ol>
            <p><strong>注意</strong>：推断结果仅供参考。</p>
        </div>
"""

    if time_tracker:
        html += time_tracker.to_html()

    if token_stats:
        html += f"""
        <div class="section">
            <h2>📊 Token 使用统计</h2>
            <div class="token-stats">
                <div class="token-stat-item">
                    <div class="token-stat-label">总请求次数</div>
                    <div class="token-stat-value">{token_stats.get('total_requests', 0):,}</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-label">缓存命中次数</div>
                    <div class="token-stat-value">{token_stats.get('cached_requests', 0):,}</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-label">输入 Token 总数</div>
                    <div class="token-stat-value">{token_stats.get('total_input_tokens', 0):,}</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-label">输出 Token 总数</div>
                    <div class="token-stat-value">{token_stats.get('total_output_tokens', 0):,}</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-label">平均输入 Token</div>
                    <div class="token-stat-value">{token_stats.get('average_input_tokens', 0):,.0f}</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-label">平均输出 Token</div>
                    <div class="token-stat-value">{token_stats.get('average_output_tokens', 0):,.0f}</div>
                </div>
            </div>
        </div>
"""

    html += """
        <table>
            <thead>
                <tr>
                    <th>排名</th>
                    <th>文件路径</th>
                    <th>地址</th>
                    <th>偏移量</th>
"""
    if use_event_count:
        html += '                    <th>指令数 (event_count)</th>\n'
    html += """                    <th>调用次数</th>
                    <th>指令数量</th>
                    <th>字符串常量</th>
                    <th>LLM 推断函数名</th>
                    <th>LLM 功能描述</th>
                    <th>LLM 置信度</th>
                </tr>
            </thead>
            <tbody>
"""

    for result in results:
        llm_result = result.get('llm_result') or {}
        strings_value = result.get('strings', '')
        if isinstance(strings_value, list):
            strings_value = ', '.join(strings_value)
        html += f"""                <tr>
                    <td class="rank">{result.get('rank', '')}</td>
                    <td>{result.get('file_path', '')}</td>
                    <td class="address">{result.get('address', '')}</td>
                    <td class="address">{result.get('offset', '')}</td>
"""
        if use_event_count:
            html += f'                    <td class="call-count">{result.get("event_count", 0):,}</td>\n'
        html += f"""                    <td class="call-count">{result.get('call_count', 0):,}</td>
                    <td class="call-count">{result.get('instruction_count', 0):,}</td>
                    <td class="strings">{strings_value}</td>
                    <td>{llm_result.get('function_name', '')}</td>
                    <td class="functionality">{llm_result.get('functionality', '')}</td>
"""
        confidence = llm_result.get('confidence', '')
        confidence_class = 'confidence-low'
        if confidence == '高':
            confidence_class = 'confidence-high'
        elif confidence == '中':
            confidence_class = 'confidence-medium'
        html += f"""                    <td class="{confidence_class}">{confidence}</td>
                </tr>
"""

    html += """            </tbody>
        </table>
    </div>
</body>
</html>"""

    return html
