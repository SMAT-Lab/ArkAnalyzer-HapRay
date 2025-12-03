#!/usr/bin/env python3
"""
支持批量分析的 LLM 分析器：在一个 prompt 中包含多个函数，进行批量分析
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from core.llm.analyzer import LLMFunctionAnalyzer
from core.utils.logger import get_logger

logger = get_logger(__name__)


class BatchLLMFunctionAnalyzer(LLMFunctionAnalyzer):
    """支持批量分析的 LLM 分析器"""

    def __init__(self, *args, batch_size: int = 3, **kwargs):
        """
        初始化批量分析器

        Args:
            batch_size: 每个 prompt 中包含的函数数量（默认: 3）
            其他参数同 LLMFunctionAnalyzer
        """
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size

    def _build_batch_prompt(self, functions_data: list[dict[str, Any]], context: Optional[str] = None) -> str:
        """
        构建包含多个函数的批量 prompt

        Args:
            functions_data: 函数数据列表，每个元素包含:
                {
                    'offset': 0x50338a0,
                    'instructions': [...],
                    'strings': [...],
                    'symbol_name': ...,
                    'called_functions': [...],
                    'function_id': 'func_1'  # 用于标识函数
                }
            context: 背景信息

        Returns:
            批量 prompt 字符串
        """
        prompt_parts = []

        prompt_parts.append('请分析以下多个 ARM64 反汇编函数，推断每个函数的功能和可能的函数名。')
        prompt_parts.append('')
        
        # 添加开源库相关的 prompt（如果指定了开源库）
        self._add_open_source_lib_prompt(prompt_parts, self.open_source_lib)
        
        prompt_parts.append('⚠️ 重要提示：这是一个性能分析场景，这些函数被识别为高指令数负载的热点函数。')
        prompt_parts.append('请重点关注可能导致性能问题的因素，包括但不限于：')
        prompt_parts.append('  - 循环和迭代（特别是嵌套循环、大循环次数）')
        prompt_parts.append('  - 内存操作（大量内存拷贝、频繁的内存分配/释放）')
        prompt_parts.append('  - 字符串处理（字符串拼接、解析、格式化）')
        prompt_parts.append('  - 算法复杂度（O(n²)、O(n³) 等高复杂度算法）')
        prompt_parts.append('  - 系统调用和 I/O 操作（文件读写、网络操作）')
        prompt_parts.append('  - 递归调用（深度递归可能导致栈溢出或高指令数）')
        prompt_parts.append('  - 异常处理（频繁的异常捕获和处理）')
        prompt_parts.append('  - 锁和同步操作（频繁的加锁/解锁、条件等待）')
        prompt_parts.append('  - 数据结构和算法选择不当（低效的数据结构使用）')
        prompt_parts.append('')
        prompt_parts.append('请分别提供以下信息：')
        prompt_parts.append('  1. 功能描述：函数的主要功能是什么（不要包含性能分析）')
        prompt_parts.append('  2. 负载问题识别与优化建议：')
        prompt_parts.append('     - 是否存在明显的性能瓶颈（如上述因素）')
        prompt_parts.append('     - 为什么这个函数可能导致高指令数负载')
        prompt_parts.append('     - 可能的优化建议（如果有）')
        prompt_parts.append('')

        # 添加背景信息（全局上下文）
        if context:
            prompt_parts.append('背景信息:')
            prompt_parts.append(context)
            prompt_parts.append('')

        # 添加每个函数的信息
        for idx, func_data in enumerate(functions_data, 1):
            prompt_parts.append(f'{"=" * 80}')
            prompt_parts.append(f'函数 {idx} (ID: {func_data.get("function_id", f"func_{idx}")})')
            prompt_parts.append(f'{"=" * 80}')
            
            # 调试：记录函数数据的内容
            logger.debug(f'Building prompt for function {idx}: strings={len(func_data.get("strings", []))}, called_functions={len(func_data.get("called_functions", []))}, call_stack_info={func_data.get("call_stack_info") is not None}')

            offset = func_data.get('offset')
            if offset:
                # offset 可能已经是字符串格式（如 "libxxx.so+0x123456"），直接使用
                if isinstance(offset, str):
                    prompt_parts.append(f'函数偏移量: {offset}')
                else:
                    prompt_parts.append(f'函数偏移量: 0x{offset:x}')

            # 函数元信息
            func_info = func_data.get('func_info')
            if func_info:
                func_start = func_info.get('minbound', func_info.get('offset', offset))
                func_end = func_info.get('maxbound', func_start + func_info.get('size', 0))
                func_size = func_info.get('size', 0)
                if func_size > 0:
                    prompt_parts.append(f'函数范围: 0x{func_start:x} - 0x{func_end:x} (大小: {func_size} 字节)')

                nbbs = func_info.get('nbbs', 0)
                edges = func_info.get('edges', 0)
                nargs = func_info.get('nargs', 0)
                if nbbs > 0:
                    prompt_parts.append(f'基本块数量: {nbbs}')
                if edges > 0:
                    prompt_parts.append(f'控制流边数量: {edges}')
                if nargs > 0:
                    prompt_parts.append(f'参数数量: {nargs}')

            # 指令数量
            instructions = func_data.get('instructions', [])
            if instructions:
                prompt_parts.append(f'指令数量: {len(instructions)} 条')

            # 注意：调用次数（call_count）和指令执行次数（event_count）仅用于排序和筛选，
            # 不需要传递给 LLM，因此不添加到 prompt 中

            # SO 文件信息
            so_file = func_data.get('so_file')
            if so_file:
                so_name = so_file.split('/')[-1] if '/' in so_file else so_file
                prompt_parts.append(f'所在文件: {so_name}')

            symbol_name = func_data.get('symbol_name')
            if symbol_name:
                prompt_parts.append(f'符号表中的函数名: {symbol_name}')
                prompt_parts.append('（如果符号名是 C++ 名称修饰，请尝试还原原始函数名）')

            decompiled = func_data.get('decompiled')

            # 如果有反编译代码，优先使用反编译代码，不显示反汇编代码
            if decompiled:
                prompt_parts.append('')
                prompt_parts.append('反编译代码（伪 C 代码）:')
                # 过滤掉 warning 行
                decompiled_lines = decompiled.split('\n')
                filtered_lines = []
                for line in decompiled_lines:
                    # 跳过 warning 行（以 //WARNING 开头或包含 WARNING）
                    if not (
                        line.strip().startswith('//WARNING')
                        or 'WARNING' in line.upper()
                        and line.strip().startswith('//')
                    ):
                        filtered_lines.append(line)

                # 批量模式下，限制反编译代码长度，避免 prompt 过长导致 LLM 响应截断
                # 注意：如果 prompt 过长，LLM 可能无法返回完整的 JSON，导致某些函数的结果丢失
                max_decompiled_lines = 300  # 从 1000 行减少到 300 行，避免 prompt 过长
                for line in filtered_lines[:max_decompiled_lines]:
                    prompt_parts.append(f'  {line}')
                if len(filtered_lines) > max_decompiled_lines:
                    prompt_parts.append(f'  ... (共 {len(filtered_lines)} 行，此处显示前 {max_decompiled_lines} 行)')
            else:
                # 如果没有反编译代码，则显示反汇编代码
                instructions = func_data.get('instructions', [])
                if instructions:
                    prompt_parts.append('')
                    prompt_parts.append('反汇编代码:')
                    # 批量模式下，每个函数发送前200条指令（比单函数模式稍少，因为一次分析多个函数）
                    # 注意：由于函数切分逻辑已改进，现在能获取更多指令，因此增加发送给 LLM 的指令数量
                    max_instructions = 200 if len(instructions) > 100 else len(instructions)
                    for i, inst in enumerate(instructions[:max_instructions], 1):
                        prompt_parts.append(f'  {i:3d}. {inst}')
                    if len(instructions) > max_instructions:
                        prompt_parts.append(f'  ... (共 {len(instructions)} 条指令，此处显示前 {max_instructions} 条)')

            strings = func_data.get('strings', [])
            logger.info(f'Function {idx} strings: {strings}, type: {type(strings)}, len: {len(strings) if isinstance(strings, list) else "N/A"}, bool: {bool(strings)}')
            if strings:
                prompt_parts.append('')
                prompt_parts.append('附近的字符串常量:')
                for s in strings[:5]:  # 批量模式下减少字符串数量
                    prompt_parts.append(f'  - {s}')

            called_functions = func_data.get('called_functions', [])
            if called_functions:
                prompt_parts.append('')
                prompt_parts.append('调用的函数:')
                for func in called_functions[:5]:  # 批量模式下减少调用函数数量
                    prompt_parts.append(f'  - {func}')

            # 添加调用堆栈信息（如果存在）
            call_stack_info = func_data.get('call_stack_info')
            logger.info(f'Function {idx} call_stack_info: {call_stack_info is not None}, type: {type(call_stack_info)}, bool: {bool(call_stack_info) if call_stack_info is not None else "None"}')
            if call_stack_info:
                logger.info(f'Function {idx} call_stack_info content: callers={len(call_stack_info.get("callers", []))}, callees={len(call_stack_info.get("callees", []))}')
                callers = call_stack_info.get('callers', [])
                if callers:
                    prompt_parts.append('')
                    prompt_parts.append('调用堆栈信息（谁调用了这个函数）:')
                    for i, caller in enumerate(callers[:3], 1):  # 只显示前3个
                        caller_info = f'  {i}. '
                        if caller.get('symbol_name'):
                            caller_info += f'{caller["symbol_name"]} '
                        caller_info += f'({caller.get("file_path", "")} {caller.get("address", "")})'
                        prompt_parts.append(caller_info)
                
                callees = call_stack_info.get('callees', [])
                if callees:
                    prompt_parts.append('')
                    prompt_parts.append('被调用的函数（这个函数调用了哪些有符号的函数）:')
                    for i, callee in enumerate(callees[:3], 1):  # 只显示前3个
                        callee_info = f'  {i}. '
                        if callee.get('symbol_name'):
                            callee_info += f'{callee["symbol_name"]} '
                        callee_info += f'({callee.get("file_path", "")} {callee.get("address", "")})'
                        prompt_parts.append(callee_info)

            prompt_parts.append('')

        # 输出格式说明
        prompt_parts.append('=' * 80)
        prompt_parts.append('请按以下 JSON 格式返回分析结果:')
        prompt_parts.append('{')
        prompt_parts.append('  "functions": [')
        prompt_parts.append('    {')
        prompt_parts.append('      "function_id": "func_1",')
        prompt_parts.append('      "functionality": "详细的功能描述（中文，50-200字，仅描述功能，不包含性能分析）",')
        prompt_parts.append('      "function_name": "推断的函数名（英文，遵循常见命名规范）",')
        prompt_parts.append(
            '      "performance_analysis": "负载问题识别与优化建议（中文，100-300字）：是否存在性能瓶颈、为什么导致高指令数负载、可能的优化建议",'
        )
        prompt_parts.append('      "confidence": "高/中/低",')
        prompt_parts.append('      "reasoning": "推理过程（中文，说明为什么这样推断）"')
        prompt_parts.append('    },')
        prompt_parts.append('    ...')
        prompt_parts.append('  ]')
        prompt_parts.append('}')
        prompt_parts.append('')
        prompt_parts.append('注意:')
        prompt_parts.append("1. 返回一个 JSON 对象，包含 'functions' 数组")
        prompt_parts.append("2. 每个函数的结果必须包含 'function_id' 字段，对应输入中的函数 ID")
        prompt_parts.append('3. 如果符号表中已有函数名，优先使用符号名（如果是 C++ 名称修饰，请还原）')
        prompt_parts.append('4. 函数名应该遵循常见的命名规范（如驼峰命名、下划线命名）')
        prompt_parts.append(
            '5. 功能描述应该具体，但请控制在 150 字以内，避免过长导致 JSON 格式问题，且不要包含性能分析内容'
        )
        prompt_parts.append('6. 负载问题识别与优化建议（performance_analysis）必须详细说明：')
        prompt_parts.append('   - 是否存在明显的性能瓶颈（是/否，并说明原因）')
        prompt_parts.append('   - 为什么这个函数可能导致高指令数负载（具体分析）')
        prompt_parts.append('   - 可能的优化建议（如果有）')
        prompt_parts.append('   请控制在 300 字以内，避免过长导致 JSON 格式问题')
        prompt_parts.append('   示例："存在性能瓶颈。该函数包含三层嵌套循环，时间复杂度为O(n³)，')
        prompt_parts.append(
            '   在处理大量数据时会导致高指令数负载。建议：1) 优化算法降低复杂度；2) 使用缓存减少重复计算"'
        )
        prompt_parts.append('7. 推理过程请控制在 200 字以内，简洁明了即可')
        prompt_parts.append('8. 置信度评估标准：')
        prompt_parts.append(
            "   - '高'：能看到完整的函数逻辑，包括函数序言、主要业务逻辑、函数调用、返回值等，且功能明确"
        )
        prompt_parts.append("   - '中'：能看到部分函数逻辑，能推断出大致功能，但可能缺少一些细节")
        prompt_parts.append("   - '低'：只能看到函数片段（如只有函数结尾），无法确定完整功能")
        prompt_parts.append(
            "8. 如果反汇编代码从函数开始（有 pacibsp 或 stp x29, x30），且能看到主要逻辑，置信度应该设为'高'或'中'"
        )
        prompt_parts.append("9. 如果无法确定，confidence 设为'低'，function_name 可以为 null")
        prompt_parts.append('10. 重要：确保 JSON 格式完整，所有字符串字段必须正确闭合引号，不要截断')

        return '\n'.join(prompt_parts)

    def batch_analyze_functions(
        self, functions_data: list[dict[str, Any]], context: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        批量分析多个函数（一个 prompt 包含多个函数）

        Args:
            functions_data: 函数数据列表，每个元素包含:
                {
                    'offset': 0x50338a0,
                    'instructions': [...],
                    'strings': [...],
                    'symbol_name': ...,
                    'called_functions': [...],
                    'function_id': 'func_1'  # 可选，如果不提供会自动生成
                }
            context: 背景信息

        Returns:
            分析结果列表，每个元素对应一个函数
        """
        # 为每个函数分配 ID（如果没有提供）
        for idx, func_data in enumerate(functions_data, 1):
            if 'function_id' not in func_data:
                func_data['function_id'] = f'func_{idx}'

        # 分批处理
        all_results = []
        total_batches = (len(functions_data) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(0, len(functions_data), self.batch_size):
            batch = functions_data[batch_idx : batch_idx + self.batch_size]
            batch_num = batch_idx // self.batch_size + 1

            logger.info(f'\nBatch analysis batch {batch_num}/{total_batches} (contains {len(batch)} functions)...')

            # 检查缓存
            batch_results = []
            uncached_batch = []
            cached_batch = []  # 记录缓存的函数，用于 prompt 保存

            for func_data in batch:
                if self.enable_cache:
                    cache_key = self._get_cache_key(
                        func_data.get('instructions', []),
                        func_data.get('strings', []),
                        func_data.get('symbol_name'),
                        func_data.get('called_functions', []),
                        func_data.get('decompiled'),
                    )
                    if cache_key in self.cache:
                        cache_entry = self.cache[cache_key]
                        # 缓存结构: {'analysis': {...}, 'metadata': {...}}
                        # 需要从 'analysis' 字段中获取实际的分析结果
                        if isinstance(cache_entry, dict) and 'analysis' in cache_entry:
                            cached_result = cache_entry['analysis'].copy()
                        else:
                            # 兼容旧格式（直接存储分析结果）
                            cached_result = cache_entry.copy() if isinstance(cache_entry, dict) else {}

                        # 确保旧缓存格式也有 performance_analysis 字段
                        if 'performance_analysis' not in cached_result:
                            cached_result['performance_analysis'] = ''
                            logger.debug(
                                f'⚠️  函数 {func_data.get("function_id", "unknown")} 的缓存结果缺少 performance_analysis 字段，已添加空值（建议清除缓存重新分析）'
                            )

                        cached_result['function_id'] = func_data['function_id']
                        batch_results.append(cached_result)
                        cached_batch.append(func_data)  # 记录缓存的函数
                        self.token_stats['cached_requests'] += 1
                        self.token_stats['total_requests'] += 1
                        continue

                uncached_batch.append(func_data)

            # 保存 prompt（如果启用）
            # 注意：为了调试方便，prompt 中包含所有函数（包括缓存的），这样可以看到完整的批量分析内容
            if self.save_prompts and batch:  # 只要有函数就保存 prompt
                # 构建包含所有函数的 prompt（包括缓存的）
                all_functions_for_prompt = cached_batch + uncached_batch
                if all_functions_for_prompt:  # 确保有函数才保存
                    batch_prompt = self._build_batch_prompt(all_functions_for_prompt, context)
                    self._save_batch_prompt(batch_prompt, all_functions_for_prompt, batch_num, total_batches)
                    logger.debug(
                        f'✅ 已保存 prompt (批次 {batch_num}/{total_batches})，包含 {len(all_functions_for_prompt)} 个函数（缓存: {len(cached_batch)}, 未缓存: {len(uncached_batch)}）'
                    )

            # 如果有未缓存的函数，进行批量分析
            if uncached_batch:
                try:
                    # 构建批量 prompt（只包含未缓存的函数，用于 LLM 分析）
                    batch_prompt = self._build_batch_prompt(uncached_batch, context)

                    # 调用 LLM
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                'role': 'system',
                                'content': '你是一个专业的逆向工程专家，擅长分析 ARM64 汇编代码并推断函数功能和函数名。',
                            },
                            {'role': 'user', 'content': batch_prompt},
                        ],
                        temperature=0.0,  # 最低随机性，最高一致性和稳定性
                        max_tokens=20000,  # 批量模式下需要更多 tokens（增加缓冲，避免 JSON 截断，特别是当反编译代码较长时）
                        timeout=120,  # 批量模式下增加超时时间
                    )

                    # 统计 token
                    usage = response.usage
                    if usage:
                        input_tokens = usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0
                        output_tokens = usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0
                        total_tokens = (
                            usage.total_tokens if hasattr(usage, 'total_tokens') else (input_tokens + output_tokens)
                        )

                        self.token_stats['total_requests'] += 1
                        self.token_stats['total_input_tokens'] += input_tokens
                        self.token_stats['total_output_tokens'] += output_tokens
                        self.token_stats['total_tokens'] += total_tokens

                        # 延迟保存统计（每10次请求保存一次，减少 I/O）
                        if self.token_stats['total_requests'] % 10 == 0:
                            self._save_token_stats()

                    # 解析批量结果
                    result_text = response.choices[0].message.content

                    # 调试：记录响应信息（仅在 debug 级别）
                    logger.debug('LLM response length: %d characters', len(result_text))
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            'LLM response ending: %s', result_text[-200:] if len(result_text) > 200 else result_text
                        )

                    # 保存完整的 LLM 响应到文件（用于调试）
                    if self.save_prompts:
                        try:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                            response_file = (
                                self.prompt_output_dir / f'llm_response_batch_{batch_num:03d}_{timestamp}.txt'
                            )
                            with open(response_file, 'w', encoding='utf-8') as f:
                                f.write('=' * 80 + '\n')
                                f.write(f'LLM 响应 (批次 {batch_num}/{total_batches})\n')
                                f.write('=' * 80 + '\n')
                                f.write(f'生成时间: {datetime.now().isoformat()}\n')
                                f.write(f'函数数量: {len(uncached_batch)}\n')
                                f.write(f'响应长度: {len(result_text):,} 字符\n')
                                f.write('=' * 80 + '\n\n')
                                f.write(result_text)
                                f.write('\n\n' + '=' * 80 + '\n')
                            logger.debug(f'LLM response saved: {response_file.name}')
                        except Exception as e:
                            logger.warning(f'⚠️  Failed to save LLM response: {e}')

                    batch_parsed_results = self._parse_batch_response(result_text, uncached_batch)

                    # 保存到缓存（包含元信息）
                    if self.enable_cache:
                        for func_data, result in zip(uncached_batch, batch_parsed_results):  # noqa: B905
                            cache_key = self._get_cache_key(
                                func_data.get('instructions', []),
                                func_data.get('strings', []),
                                func_data.get('symbol_name'),
                                func_data.get('called_functions', []),
                                func_data.get('decompiled'),
                            )
                            # 保存时移除 function_id（缓存键中不包含它）
                            cache_result = result.copy()
                            cache_result.pop('function_id', None)

                            # 存储分析结果和元信息
                            cache_entry = {
                                'analysis': cache_result,  # LLM 分析结果
                                'metadata': {
                                    'instruction_count': len(func_data.get('instructions', [])),
                                    'string_count': len(func_data.get('strings', [])),
                                    'has_decompiled': bool(func_data.get('decompiled')),
                                    'called_functions_count': len(func_data.get('called_functions', [])),
                                    'offset': func_data.get('offset', ''),
                                    'function_size': None,  # 可以从 func_info 获取，但暂不存储
                                },
                            }
                            self.cache[cache_key] = cache_entry
                        # 延迟保存缓存（每批次保存一次，减少 I/O）
                        self._save_cache()

                    batch_results.extend(batch_parsed_results)

                except Exception as e:
                    logger.exception('⚠️  批量分析失败')
                    # 为失败的函数返回默认结果
                    for func_data in uncached_batch:
                        batch_results.append(
                            {
                                'function_id': func_data['function_id'],
                                'functionality': '未知',
                                'function_name': None,
                                'performance_analysis': '',
                                'confidence': '低',
                                'reasoning': f'批量分析失败: {str(e)}',
                            }
                        )

            all_results.extend(batch_results)
            logger.info(f'✅ Batch {batch_num} completed, analyzed {len(batch_results)} functions')
            logger.debug(f'Batch {batch_num} returned function_id: {[r.get("function_id") for r in batch_results]}')

        return all_results

    def _parse_batch_response(self, response_text: str, functions_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        解析批量 LLM 响应

        Args:
            response_text: LLM 返回的文本
            functions_data: 原始函数数据列表（用于匹配 function_id）

        Returns:
            解析后的结果列表
        """
        results = []
        function_id_map = {func['function_id']: func for func in functions_data}

        try:
            # 尝试提取 JSON（改进正则，匹配更完整的 JSON 结构）
            # 先尝试匹配完整的 JSON 对象（使用更宽松的匹配，允许嵌套的大括号）
            # 注意：需要处理字符串中的双引号，所以不能简单地用 [^{}] 来匹配
            json_match = re.search(r'\{\s*"functions"\s*:\s*\[.*?\]\s*\}', response_text, re.DOTALL)
            if not json_match:
                # 如果没找到完整结构，尝试匹配到 functions 数组结束
                json_match = re.search(r'\{[^{}]*"functions"[^{}]*\[.*?\]', response_text, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)

                # 修复字符串中的未转义双引号
                # 在 JSON 字符串值中，未转义的双引号会导致解析失败
                # 我们需要将字符串值中的双引号转义为 \"
                def fix_unescaped_quotes_in_strings(text):
                    """修复 JSON 字符串值中的未转义双引号"""
                    result = []
                    i = 0
                    in_string = False
                    escape_next = False

                    while i < len(text):
                        char = text[i]

                        if escape_next:
                            result.append(char)
                            escape_next = False
                            i += 1
                            continue

                        if char == '\\':
                            escape_next = True
                            result.append(char)
                            i += 1
                            continue

                        if char == '"':
                            if not in_string:
                                # 字符串开始
                                in_string = True
                                result.append(char)
                            else:
                                # 检查后续字符，判断是否是字符串结束
                                # 跳过空白字符，找到第一个非空白字符
                                j = i + 1
                                while j < len(text) and text[j] in [' ', '\t', '\n', '\r']:
                                    j += 1

                                # 如果下一个非空白字符是 : 或 , 或 } 或 ]，则是字符串结束
                                if j >= len(text) or text[j] in [':', ',', '}', ']']:
                                    # 字符串结束
                                    in_string = False
                                    result.append(char)
                                else:
                                    # 这是字符串值中的双引号，需要转义
                                    result.append('\\"')
                            i += 1
                            continue

                        result.append(char)
                        i += 1

                    return ''.join(result)

                # 先修复未转义的双引号（保存函数引用以便后续使用）
                fixed_json_str = fix_unescaped_quotes_in_strings(json_str)
                json_str = fixed_json_str

                # 记录修复后的 JSON 用于调试
                logger.debug(f'Fixed JSON length: {len(json_str)} characters')

                # 尝试修复常见的截断问题
                # 1. 如果 JSON 字符串未闭合，尝试补全
                if not json_str.rstrip().endswith('}'):
                    # 检查是否有未闭合的字符串
                    open_braces = json_str.count('{') - json_str.count('}')
                    open_brackets = json_str.count('[') - json_str.count(']')

                    # 尝试补全未闭合的字符串（如果最后一个字符串字段未闭合）
                    if json_str.rstrip().endswith('"') or json_str.rstrip().endswith('\\"'):
                        # 字符串已闭合，只需要补全括号
                        json_str += '}' * open_braces + ']' * open_brackets + '}'
                    else:
                        # 字符串未闭合，尝试找到最后一个引号位置并补全
                        last_quote_pos = json_str.rfind('"')
                        if last_quote_pos > 0:
                            # 在最后一个引号后补全
                            json_str = json_str[: last_quote_pos + 1] + '}' * open_braces + ']' * open_brackets + '}'
                        else:
                            json_str += '}' * open_braces + ']' * open_brackets + '}'

                # 尝试解析
                try:
                    data = json.loads(json_str)
                    logger.debug(f'✅ JSON parsing successful, contains {len(data.get("functions", []))} functions')
                except json.JSONDecodeError as je:
                    logger.warning(f'⚠️  JSON parsing failed: {je}')
                    logger.warning(f'Error position: {je.pos}, line: {je.lineno}, column: {je.colno}')
                    # 显示错误附近的文本用于调试
                    start = max(0, je.pos - 200)
                    end = min(len(json_str), je.pos + 200)
                    logger.debug(f'Text near error:\n{json_str[start:end]}')
                    # 如果仍然失败，尝试更激进的修复
                    logger.warning('⚠️  First JSON parsing failed, attempting to fix truncated strings...')
                    # 移除最后一个可能不完整的对象
                    if '"functions"' in json_str:
                        # 尝试找到最后一个完整的函数对象
                        functions_match = re.search(r'"functions"\s*:\s*\[(.*)\]', json_str, re.DOTALL)
                        if functions_match:
                            functions_content = functions_match.group(1)
                            # 尝试提取所有完整的函数对象
                            func_objects = []
                            brace_count = 0
                            current_obj = ''
                            in_string = False
                            escape_next = False

                            for char in functions_content:
                                if escape_next:
                                    current_obj += char
                                    escape_next = False
                                    continue

                                if char == '\\':
                                    escape_next = True
                                    current_obj += char
                                    continue

                                if char == '"' and not escape_next:
                                    in_string = not in_string

                                if not in_string:
                                    if char == '{':
                                        brace_count += 1
                                    elif char == '}':
                                        brace_count -= 1

                                current_obj += char

                                if not in_string and brace_count == 0 and current_obj.strip():
                                    # 找到一个完整的对象
                                    obj_str = current_obj.strip().rstrip(',').strip()
                                    if obj_str.startswith('{') and obj_str.endswith('}'):
                                        try:
                                            func_obj = json.loads(obj_str)
                                            func_objects.append(func_obj)
                                            logger.debug(
                                                f'✅ 成功解析函数对象: {func_obj.get("function_id", "unknown")}'
                                            )
                                        except json.JSONDecodeError as je:
                                            logger.debug(
                                                f'⚠️  解析函数对象失败: {str(je)[:100]}, function_id: {obj_str[:100]}'
                                            )
                                            # 尝试修复未转义的双引号后重新解析
                                            try:
                                                # 使用相同的修复函数
                                                fixed_obj_str = fix_unescaped_quotes_in_strings(obj_str)
                                                func_obj = json.loads(fixed_obj_str)
                                                func_objects.append(func_obj)
                                                logger.debug(
                                                    f'✅ 修复后成功解析函数对象: {func_obj.get("function_id", "unknown")}'
                                                )
                                            except Exception as e2:
                                                logger.debug(f'⚠️  Still failed to parse after fix: {str(e2)[:100]}')
                                                pass
                                    current_obj = ''

                            # 如果找到了完整的对象，构建新的 JSON
                            if func_objects:
                                data = {'functions': func_objects}
                                logger.info(
                                    f'✅ Successfully fixed, extracted {len(func_objects)} complete function objects'
                                )
                            else:
                                raise je
                        else:
                            raise je
                    else:
                        raise je

                # data 已经在 try-except 中定义，直接使用
                functions_results = data.get('functions', [])

                # 按 function_id 匹配结果
                for func_result in functions_results:
                    func_id = func_result.get('function_id')
                    if func_id and func_id in function_id_map:
                        performance_analysis = func_result.get('performance_analysis', '')
                        if not performance_analysis:
                            logger.warning(
                                f'⚠️  Function {func_id} LLM response missing or empty performance_analysis field'
                            )

                        result_item = {
                            'function_id': func_id,
                            'functionality': func_result.get('functionality', '未知'),
                            'function_name': func_result.get('function_name'),
                            'performance_analysis': performance_analysis,
                            'confidence': func_result.get('confidence', '低'),
                            'reasoning': func_result.get('reasoning', ''),
                        }
                        results.append(result_item)
                        logger.debug(
                            f'✅ 从 LLM 响应中提取了 {func_id}: function_name={result_item["function_name"]}, functionality={result_item["functionality"][:50]}..., performance_analysis={"有" if performance_analysis else "无"}'
                        )

                # 检查是否有遗漏的函数
                processed_ids = {r['function_id'] for r in results}
                for func_data in functions_data:
                    if func_data['function_id'] not in processed_ids:
                        logger.warning(
                            '⚠️  函数 %s 未在 LLM 响应中找到，使用默认结果',
                            func_data['function_id'],
                        )
                        results.append(
                            {
                                'function_id': func_data['function_id'],
                                'functionality': '未知',
                                'function_name': None,
                                'performance_analysis': '',
                                'confidence': '低',
                                'reasoning': 'LLM 响应中未找到该函数的结果',
                            }
                        )

                return results
        except json.JSONDecodeError as e:
            logger.warning('⚠️  JSON parsing failed: %s', e)
            logger.warning('Response text length: %d characters', len(response_text))
            logger.warning('Response text first 500 characters: %s', response_text[:500])
            logger.warning(
                'Response text last 500 characters: %s',
                response_text[-500:] if len(response_text) > 500 else response_text,
            )

            # JSON 解析失败时，为所有函数返回默认结果
            logger.warning('⚠️  Using default results for all functions due to JSON parsing failure')
            results = []
            for func_data in functions_data:
                results.append(
                    {
                        'function_id': func_data['function_id'],
                        'functionality': '未知',
                        'function_name': None,
                        'performance_analysis': '',
                        'confidence': '低',
                        'reasoning': f'LLM 响应 JSON 解析失败: {str(e)}',
                    }
                )
            return results

        # 如果解析失败，尝试逐个匹配（fallback）
        logger.warning('⚠️  Attempting to use fallback parsing method...')
        for func_data in functions_data:
            # 尝试在响应文本中查找该函数的结果
            func_id = func_data['function_id']
            # 修复 f-string 中的括号匹配问题：使用双大括号转义
            pattern = rf'"{func_id}"[^{{]*?\{{[^}}]*?"functionality"[^"]*?"([^"]+)"[^}}]*?"function_name"[^"]*?"([^"]*)"[^}}]*?"confidence"[^"]*?"([^"]+)"'
            match = re.search(pattern, response_text, re.DOTALL)

            if match:
                results.append(
                    {
                        'function_id': func_id,
                        'functionality': match.group(1),
                        'function_name': match.group(2) if match.group(2) else None,
                        'performance_analysis': '',  # 文本提取模式无法提取 performance_analysis
                        'confidence': match.group(3),
                        'reasoning': '从响应文本中提取',
                    }
                )
            else:
                results.append(
                    {
                        'function_id': func_id,
                        'functionality': '未知',
                        'function_name': None,
                        'performance_analysis': '',
                        'confidence': '低',
                        'reasoning': '无法从响应中解析结果',
                    }
                )

        return results

    def _save_batch_prompt(self, prompt: str, functions_data: list[dict[str, Any]], batch_num: int, total_batches: int):
        """保存批量 prompt 到文件"""
        if not self.save_prompts:
            return

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒

            # 生成文件名
            prompt_file = self.prompt_output_dir / f'prompt_batch_{batch_num:03d}_{total_batches:03d}_{timestamp}.txt'

            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write('=' * 80 + '\n')
                f.write(f'生成的 LLM Prompt (批次 {batch_num}/{total_batches})\n')
                f.write('=' * 80 + '\n')
                f.write(f'生成时间: {datetime.now().isoformat()}\n')
                f.write(f'函数数量: {len(functions_data)}\n')
                f.write(f'总长度: {len(prompt):,} 字符\n')
                f.write(f'估计 Token 数: ≈{len(prompt) // 4:,}\n')
                f.write('=' * 80 + '\n\n')

                # 添加函数列表信息
                f.write('函数列表:\n')
                for idx, func_data in enumerate(functions_data, 1):
                    offset = func_data.get('offset')
                    offset_str = f'0x{offset:x}' if isinstance(offset, int) else str(offset) if offset else 'unknown'
                    symbol_name = func_data.get('symbol_name', 'unknown')
                    func_id = func_data.get('function_id', f'func_{idx}')
                    f.write(f'  {idx}. {func_id}: {offset_str} ({symbol_name})\n')
                f.write('\n' + '=' * 80 + '\n\n')

                f.write(prompt)
                f.write('\n\n' + '=' * 80 + '\n')

            logger.info(f'✅ Prompt saved: {prompt_file.name}')
            logger.info(
                f'   Prompt statistics: total length={len(prompt):,} characters, estimated tokens≈{len(prompt) // 4:,}'
            )
        except Exception as e:
            logger.warning(f'Failed to save prompt: {e}')
