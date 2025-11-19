#!/usr/bin/env python3
"""
支持批量分析的 LLM 分析器：在一个 prompt 中包含多个函数，进行批量分析
"""

import json
import re
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

        # 添加背景信息
        if context:
            prompt_parts.append('背景信息:')
            prompt_parts.append(context)
            prompt_parts.append('')

        # 添加每个函数的信息
        for idx, func_data in enumerate(functions_data, 1):
            prompt_parts.append(f'{"=" * 80}')
            prompt_parts.append(f'函数 {idx} (ID: {func_data.get("function_id", f"func_{idx}")})')
            prompt_parts.append(f'{"=" * 80}')

            offset = func_data.get('offset')
            if offset:
                # offset 可能已经是字符串格式（如 "libxxx.so+0x123456"），直接使用
                if isinstance(offset, str):
                    prompt_parts.append(f'函数偏移量: {offset}')
                else:
                    prompt_parts.append(f'函数偏移量: 0x{offset:x}')

            symbol_name = func_data.get('symbol_name')
            if symbol_name:
                prompt_parts.append(f'符号表中的函数名: {symbol_name}')
                prompt_parts.append('（如果符号名是 C++ 名称修饰，请尝试还原原始函数名）')

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

            prompt_parts.append('')

        # 输出格式说明
        prompt_parts.append('=' * 80)
        prompt_parts.append('请按以下 JSON 格式返回分析结果:')
        prompt_parts.append('{')
        prompt_parts.append('  "functions": [')
        prompt_parts.append('    {')
        prompt_parts.append('      "function_id": "func_1",')
        prompt_parts.append('      "functionality": "详细的功能描述（中文，50-200字）",')
        prompt_parts.append('      "function_name": "推断的函数名（英文，遵循常见命名规范）",')
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
        prompt_parts.append('5. 功能描述应该具体，不要使用泛泛的描述')
        prompt_parts.append('6. 置信度评估标准：')
        prompt_parts.append(
            "   - '高'：能看到完整的函数逻辑，包括函数序言、主要业务逻辑、函数调用、返回值等，且功能明确"
        )
        prompt_parts.append("   - '中'：能看到部分函数逻辑，能推断出大致功能，但可能缺少一些细节")
        prompt_parts.append("   - '低'：只能看到函数片段（如只有函数结尾），无法确定完整功能")
        prompt_parts.append(
            "7. 如果反汇编代码从函数开始（有 pacibsp 或 stp x29, x30），且能看到主要逻辑，置信度应该设为'高'或'中'"
        )
        prompt_parts.append("8. 如果无法确定，confidence 设为'低'，function_name 可以为 null")

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

            logger.info(f'\n批量分析批次 {batch_num}/{total_batches} (包含 {len(batch)} 个函数)...')

            # 检查缓存
            batch_results = []
            uncached_batch = []

            for func_data in batch:
                if self.enable_cache:
                    cache_key = self._get_cache_key(
                        func_data.get('instructions', []),
                        func_data.get('strings', []),
                        func_data.get('symbol_name'),
                    )
                    if cache_key in self.cache:
                        cached_result = self.cache[cache_key].copy()
                        cached_result['function_id'] = func_data['function_id']
                        batch_results.append(cached_result)
                        self.token_stats['cached_requests'] += 1
                        self.token_stats['total_requests'] += 1
                        continue

                uncached_batch.append(func_data)

            # 如果有未缓存的函数，进行批量分析
            if uncached_batch:
                try:
                    # 构建批量 prompt
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
                        max_tokens=8000,  # 批量模式下需要更多 tokens
                        timeout=60,  # 批量模式下增加超时时间
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

                        self._save_token_stats()

                    # 解析批量结果
                    result_text = response.choices[0].message.content
                    batch_parsed_results = self._parse_batch_response(result_text, uncached_batch)

                    # 保存到缓存
                    if self.enable_cache:
                        for func_data, result in zip(uncached_batch, batch_parsed_results):
                            cache_key = self._get_cache_key(
                                func_data.get('instructions', []),
                                func_data.get('strings', []),
                                func_data.get('symbol_name'),
                            )
                            # 保存时移除 function_id（缓存键中不包含它）
                            cache_result = result.copy()
                            cache_result.pop('function_id', None)
                            self.cache[cache_key] = cache_result
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
                                'confidence': '低',
                                'reasoning': f'批量分析失败: {str(e)}',
                            }
                        )

            all_results.extend(batch_results)
            logger.info(f'✅ 批次 {batch_num} 完成，分析了 {len(batch_results)} 个函数')

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
            # 尝试提取 JSON
            json_match = re.search(r'\{[^{}]*"functions"[^{}]*\[.*?\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # 尝试补全 JSON（如果被截断）
                if not json_str.rstrip().endswith('}'):
                    json_str += '}'

                data = json.loads(json_str)
                functions_results = data.get('functions', [])

                # 按 function_id 匹配结果
                for func_result in functions_results:
                    func_id = func_result.get('function_id')
                    if func_id and func_id in function_id_map:
                        results.append(
                            {
                                'function_id': func_id,
                                'functionality': func_result.get('functionality', '未知'),
                                'function_name': func_result.get('function_name'),
                                'confidence': func_result.get('confidence', '低'),
                                'reasoning': func_result.get('reasoning', ''),
                            }
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
                                'confidence': '低',
                                'reasoning': 'LLM 响应中未找到该函数的结果',
                            }
                        )

                return results
        except json.JSONDecodeError as e:
            logger.warning('⚠️  JSON 解析失败: %s', e)
            logger.warning('响应文本前500字符: %s', response_text[:500])

        # 如果解析失败，尝试逐个匹配（fallback）
        logger.warning('⚠️  尝试使用备用解析方法...')
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
                        'confidence': '低',
                        'reasoning': '无法从响应中解析结果',
                    }
                )

        return results
