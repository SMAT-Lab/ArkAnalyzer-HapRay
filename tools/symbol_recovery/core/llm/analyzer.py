#!/usr/bin/env python3
"""
使用 Poe API (OpenAI 兼容) 来分析反汇编代码并推断函数功能和函数名
参考: https://creator.poe.com/docs/external-applications/tool-calling
"""

import hashlib
import json
import re
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.utils.config import config
from core.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import openai
except ImportError:
    openai = None
    logger.warning('openai library not installed, LLM analysis will be unavailable')
    logger.warning('Please install openai library: pip install openai')
except Exception as e:
    logger.error('Error loading openai library: %s', e)
    raise


class LLMFunctionAnalyzer:
    """使用大语言模型分析反汇编代码"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
        base_url: Optional[str] = None,
        enable_cache: bool = True,
        save_prompts: bool = False,
        output_dir: Optional[str] = None,
        open_source_lib: Optional[str] = None,
    ):
        """
        初始化 LLM 分析器

        Args:
            api_key: API key，如果为 None 则从环境变量或 .env 文件读取
            model: 使用的模型名称，如果为 None 则从 config.get_llm_config() 获取
            base_url: API 基础 URL，如果为 None 则从 config.get_llm_config() 获取
            enable_cache: 是否启用缓存（避免重复分析相同代码）
            save_prompts: 是否保存生成的 prompt 到文件
            output_dir: 输出目录，用于保存 prompt 文件
            open_source_lib: 开源库名称（可选，如 "ffmpeg", "openssl" 等）。如果指定，会告诉大模型这是基于该开源库的定制版本
        """
        if openai is None:
            raise ImportError('需要安装 openai 库: pip install openai')

        # 从配置获取默认值
        llm_config = config.get_llm_config()
        default_base_url = llm_config['base_url']
        default_model = llm_config['model']

        self.api_key = api_key or llm_config['api_key']
        self.model = model or default_model
        self.base_url = base_url or default_base_url
        self.enable_cache = enable_cache
        self.save_prompts = save_prompts
        self.open_source_lib = open_source_lib  # 开源库名称

        self.output_dir = Path(output_dir) if output_dir else config.get_output_dir()
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_file = llm_config['cache_file']

        # 设置 prompt 保存目录
        if self.save_prompts:
            self.prompt_output_dir = self.output_dir / 'prompts'
            self.prompt_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f'Prompt output directory: {self.prompt_output_dir.absolute()}')

        # 确保缓存目录存在
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Token 统计
        self.token_stats = {
            'total_requests': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_tokens': 0,
            'cached_requests': 0,
            'requests': [],  # 每次请求的详细信息
        }
        self.token_stats_file = llm_config['token_stats_file']

        # 初始化 OpenAI 客户端
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # 加载缓存
        if self.enable_cache and self.cache_file.exists():
            try:
                with open(self.cache_file, encoding='utf-8') as f:
                    self.cache = json.load(f)
            except Exception:
                # 静默处理缓存加载失败，避免在导入时打印
                pass

        # 加载 token 统计
        if self.token_stats_file.exists():
            try:
                with open(self.token_stats_file, encoding='utf-8') as f:
                    saved_stats = json.load(f)
                    # 合并统计（保留历史数据）
                    self.token_stats['total_requests'] = saved_stats.get('total_requests', 0)
                    self.token_stats['total_input_tokens'] = saved_stats.get('total_input_tokens', 0)
                    self.token_stats['total_output_tokens'] = saved_stats.get('total_output_tokens', 0)
                    self.token_stats['total_tokens'] = saved_stats.get('total_tokens', 0)
                    self.token_stats['cached_requests'] = saved_stats.get('cached_requests', 0)
                    # 保留最近的请求记录（最多1000条）
                    self.token_stats['requests'] = saved_stats.get('requests', [])[-1000:]
            except Exception:
                # 静默处理统计加载失败，避免在导入时打印
                pass

    def _save_cache(self):
        """保存缓存到文件"""
        if self.enable_cache:
            try:
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
            except Exception:
                # 静默处理缓存保存失败
                pass

    def _save_token_stats(self):
        """保存 token 统计到文件"""
        try:
            with open(self.token_stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.token_stats, f, ensure_ascii=False, indent=2)
        except Exception:
            # 静默处理统计保存失败
            pass

    def get_token_stats(self) -> dict[str, Any]:
        """获取 token 统计信息"""
        return {
            'total_requests': self.token_stats['total_requests'],
            'total_input_tokens': self.token_stats['total_input_tokens'],
            'total_output_tokens': self.token_stats['total_output_tokens'],
            'total_tokens': self.token_stats['total_tokens'],
            'cached_requests': self.token_stats['cached_requests'],
            'average_input_tokens': (
                self.token_stats['total_input_tokens']
                / (self.token_stats['total_requests'] - self.token_stats['cached_requests'])
                if (self.token_stats['total_requests'] - self.token_stats['cached_requests']) > 0
                else 0
            ),
            'average_output_tokens': (
                self.token_stats['total_output_tokens']
                / (self.token_stats['total_requests'] - self.token_stats['cached_requests'])
                if (self.token_stats['total_requests'] - self.token_stats['cached_requests']) > 0
                else 0
            ),
            'recent_requests': self.token_stats['requests'][-10:],  # 最近10次请求
        }

    def print_token_stats(self):
        """打印 token 统计信息"""
        stats = self.get_token_stats()
        logger.info('\n' + '=' * 80)
        logger.info('Token Usage Statistics')
        logger.info('=' * 80)
        logger.info(f'Total requests: {stats["total_requests"]}')
        logger.info(f'Cache hits: {stats["cached_requests"]}')
        logger.info(f'Actual API calls: {stats["total_requests"] - stats["cached_requests"]}')
        logger.info(f'\nTotal tokens: {stats["total_tokens"]:,}')
        logger.info(f'  Input tokens: {stats["total_input_tokens"]:,}')
        logger.info(f'  Output tokens: {stats["total_output_tokens"]:,}')
        if stats['total_requests'] - stats['cached_requests'] > 0:
            logger.info('\nAverage per call:')
            logger.info(f'  Input tokens: {stats["average_input_tokens"]:.0f}')
            logger.info(f'  Output tokens: {stats["average_output_tokens"]:.0f}')
        logger.info('=' * 80)

    def _get_cache_key(
        self,
        instructions: list[str],
        strings: list[str],
        symbol_name: Optional[str] = None,
        called_functions: Optional[list[str]] = None,
        decompiled: Optional[str] = None,
    ) -> str:
        """生成缓存键（使用 hash 提高效率和准确性）"""
        # 构建用于 hash 的内容
        # 1. 指令：使用前50条指令（增加数量以提高唯一性）+ 指令总数
        inst_content = '; '.join(instructions[:50]) if instructions else ''
        inst_count = str(len(instructions))

        # 2. 字符串：所有字符串（排序以确保一致性）
        strings_sorted = sorted(set(str(s) for s in strings)) if strings else []
        strings_content = ', '.join(strings_sorted)

        # 3. 调用的函数：排序后的函数列表
        called_sorted = sorted(set(str(f) for f in called_functions)) if called_functions else []
        called_content = ', '.join(called_sorted)

        # 4. 反编译代码：如果有，使用前500字符的 hash（避免过长）
        decompiled_hash = ''
        if decompiled:
            decompiled_preview = decompiled[:500]  # 前500字符
            decompiled_hash = hashlib.md5(decompiled_preview.encode('utf-8')).hexdigest()[:16]

        # 5. 符号名
        symbol_str = str(symbol_name) if symbol_name else ''

        # 组合所有内容并生成 hash
        key_content = '|'.join(
            [
                inst_content,
                inst_count,
                strings_content,
                called_content,
                decompiled_hash,
                symbol_str,
            ]
        )

        # 使用 MD5 hash 生成固定长度的 key（避免 key 过长）
        return hashlib.md5(key_content.encode('utf-8')).hexdigest()

    def analyze_with_llm(
        self,
        instructions: list[str],
        strings: list[str],
        symbol_name: Optional[str] = None,
        called_functions: Optional[list[str]] = None,
        offset: Optional[int] = None,
        context: Optional[str] = None,
        func_info: Optional[dict] = None,
        call_count: Optional[int] = None,
        event_count: Optional[int] = None,
        so_file: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        使用 LLM 分析反汇编代码并推断函数功能和函数名

        Args:
            instructions: 反汇编指令列表，格式: ["0x3291b84: bti c", ...]
            strings: 附近的字符串常量列表
            symbol_name: 符号表中的函数名（如果有）
            called_functions: 调用的函数列表
            offset: 函数偏移量（用于上下文）

        Returns:
            {
                'functionality': '功能描述',
                'function_name': '推断的函数名',
                'confidence': '高/中/低',
                'reasoning': '推理过程'
            }
        """
        # 检查缓存
        if self.enable_cache:
            cache_key = self._get_cache_key(instructions, strings, symbol_name, called_functions, None)
            if cache_key in self.cache:
                cached_entry = self.cache[cache_key]
                # 处理新格式（包含元信息）和旧格式（直接是分析结果）
                if isinstance(cached_entry, dict) and 'analysis' in cached_entry:
                    cached_result = cached_entry['analysis']
                else:
                    cached_result = cached_entry

                # 确保旧缓存格式也有 performance_analysis 字段
                if 'performance_analysis' not in cached_result:
                    cached_result['performance_analysis'] = ''
                    logger.debug(
                        '⚠️  Cached result missing performance_analysis field, added empty value (recommend clearing cache and re-analyzing)'
                    )

                self.token_stats['cached_requests'] += 1
                self.token_stats['total_requests'] += 1
                logger.debug(f'Using cached result (total instructions: {len(instructions)})')
                return cached_result

        # 构建提示词
        logger.debug(f'Building new prompt (total instructions: {len(instructions)})')
        prompt = self._build_prompt(
            instructions,
            strings,
            symbol_name,
            called_functions,
            offset,
            context,
            func_info=func_info,
            call_count=call_count,
            event_count=event_count,
            so_file=so_file,
            open_source_lib=self.open_source_lib,
        )

        # 保存 prompt（如果启用）
        if self.save_prompts:
            self._save_single_prompt(prompt, offset, symbol_name)

        try:
            # 调用 LLM（设置超时避免卡住）
            # 从配置获取超时时间
            llm_config = config.get_llm_config()
            timeout_seconds = llm_config['timeout']

            def timeout_handler(signum, frame):
                raise TimeoutError(f'LLM API 调用超时（超过 {timeout_seconds} 秒）')

            # 使用信号设置超时（仅限 Unix 系统）
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)

            try:
                # 调用 LLM
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            'role': 'system',
                            'content': '你是一个专业的逆向工程专家，擅长分析 ARM64 汇编代码并推断函数功能和函数名。',
                        },
                        {'role': 'user', 'content': prompt},
                    ],
                    temperature=0.0,  # 最低随机性，最高一致性和稳定性
                    max_tokens=2000,  # 增加 token 限制，确保功能描述和推理过程完整
                    timeout=timeout_seconds,  # 设置超时
                )

                # 统计 token 使用量
                usage = response.usage
                if usage:
                    input_tokens = usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0
                    output_tokens = usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0
                    total_tokens = (
                        usage.total_tokens if hasattr(usage, 'total_tokens') else (input_tokens + output_tokens)
                    )

                    # 更新统计
                    self.token_stats['total_requests'] += 1
                    self.token_stats['total_input_tokens'] += input_tokens
                    self.token_stats['total_output_tokens'] += output_tokens
                    self.token_stats['total_tokens'] += total_tokens

                    # 记录本次请求详情
                    request_info = {
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'offset': f'0x{offset:x}' if offset else None,
                        'symbol_name': symbol_name,
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': total_tokens,
                        'instruction_count': len(instructions),
                    }
                    self.token_stats['requests'].append(request_info)

                    # 只保留最近1000条记录
                    if len(self.token_stats['requests']) > 1000:
                        self.token_stats['requests'] = self.token_stats['requests'][-1000:]

                    # 延迟保存统计（每10次请求保存一次，减少 I/O）
                    if self.token_stats['total_requests'] % 10 == 0:
                        self._save_token_stats()
            finally:
                # 恢复信号处理
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            result_text = response.choices[0].message.content
            logger.debug(f'LLM response: {result_text}')

            # 解析结果
            result = self._parse_llm_response(result_text)

            # 保存到缓存（包含元信息）
            if self.enable_cache:
                # 存储分析结果和元信息
                cache_entry = {
                    'analysis': result,  # LLM 分析结果
                    'metadata': {
                        'instruction_count': len(instructions),
                        'string_count': len(strings),
                        'has_decompiled': False,  # 单函数模式暂不支持反编译
                        'called_functions_count': len(called_functions) if called_functions else 0,
                        'offset': f'0x{offset:x}' if offset else None,
                    },
                }
                self.cache[cache_key] = cache_entry
                # 延迟保存缓存（每10次保存一次，减少 I/O）
                if len(self.cache) % 10 == 0:
                    self._save_cache()

            return result

        except Exception as e:
            logger.warning('Warning: LLM analysis failed: %s', e)
            # 返回默认结果
            return {
                'functionality': '未知',
                'function_name': None,
                'confidence': '低',
                'reasoning': f'LLM 分析失败: {str(e)}',
            }

    def _build_prompt(
        self,
        instructions: list[str],
        strings: list[str],
        symbol_name: Optional[str],
        called_functions: Optional[list[str]],
        offset: Optional[int],
        context: Optional[str] = None,
        func_info: Optional[dict] = None,
        call_count: Optional[int] = None,
        event_count: Optional[int] = None,
        so_file: Optional[str] = None,
        open_source_lib: Optional[str] = None,
    ) -> str:
        """构建 LLM 提示词"""
        prompt_parts = []

        prompt_parts.append('请分析以下 ARM64 反汇编代码，推断函数的功能和可能的函数名。')
        prompt_parts.append('')

        # 添加开源库相关的 prompt（如果指定了开源库）
        self._add_open_source_lib_prompt(prompt_parts, open_source_lib)

        prompt_parts.append('⚠️ 重要提示：这是一个性能分析场景，该函数被识别为高指令数负载的热点函数。')
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

        # 添加背景信息
        if context:
            prompt_parts.append('背景信息:')
            prompt_parts.append(context)
            prompt_parts.append('')

        # 函数基本信息
        if offset:
            prompt_parts.append(f'函数偏移量: 0x{offset:x}')

        # 函数边界信息
        if func_info:
            func_start = func_info.get('minbound', func_info.get('offset', offset))
            func_end = func_info.get('maxbound', func_start + func_info.get('size', 0))
            func_size = func_info.get('size', 0)
            if func_size > 0:
                prompt_parts.append(f'函数范围: 0x{func_start:x} - 0x{func_end:x} (大小: {func_size} 字节)')

        # 指令数量
        if instructions:
            prompt_parts.append(f'指令数量: {len(instructions)} 条')

        # 函数复杂度指标
        if func_info:
            nbbs = func_info.get('nbbs', 0)
            edges = func_info.get('edges', 0)
            nargs = func_info.get('nargs', 0)
            nlocals = func_info.get('nlocals', 0)
            if nbbs > 0:
                prompt_parts.append(f'基本块数量: {nbbs}')
            if edges > 0:
                prompt_parts.append(f'控制流边数量: {edges}')
            if nargs > 0:
                prompt_parts.append(f'参数数量: {nargs}')
            if nlocals > 0:
                prompt_parts.append(f'局部变量数量: {nlocals}')

        # 注意：调用次数（call_count）和指令执行次数（event_count）仅用于排序和筛选，
        # 不需要传递给 LLM，因此不添加到 prompt 中

        # SO 文件信息
        if so_file:
            so_name = so_file.split('/')[-1] if '/' in so_file else so_file
            prompt_parts.append(f'所在文件: {so_name}')

        if symbol_name:
            prompt_parts.append(f'符号表中的函数名: {symbol_name}')
            prompt_parts.append('（如果符号名是 C++ 名称修饰，请尝试还原原始函数名）')

        prompt_parts.append('')
        prompt_parts.append('反汇编代码:')
        # 根据指令数量自适应调整：短函数发送全部，长函数发送前300条
        # 注意：由于函数切分逻辑已改进，现在能获取更多指令（最多约500条），
        # 因此增加发送给 LLM 的指令数量，以提供更完整的上下文
        max_instructions = 300 if len(instructions) > 100 else len(instructions)
        # 调试信息：记录实际发送的指令数
        logger.debug(f'Total instructions: {len(instructions)}, will send to LLM: {max_instructions}')
        for i, inst in enumerate(instructions[:max_instructions], 1):
            prompt_parts.append(f'  {i:3d}. {inst}')

        # 如果函数很长，提示 LLM
        if len(instructions) > max_instructions:
            prompt_parts.append(f'  ... (共 {len(instructions)} 条指令，此处显示前 {max_instructions} 条)')

        if strings:
            prompt_parts.append('')
            prompt_parts.append('附近的字符串常量:')
            for s in strings[:10]:
                prompt_parts.append(f'  - {s}')

        if called_functions:
            prompt_parts.append('')
            prompt_parts.append('调用的函数:')
            for func in called_functions[:10]:
                prompt_parts.append(f'  - {func}')

        prompt_parts.append('')
        prompt_parts.append('请按以下 JSON 格式返回分析结果:')
        prompt_parts.append('{')
        prompt_parts.append('  "functionality": "详细的功能描述（中文，50-200字，仅描述功能，不包含性能分析）",')
        prompt_parts.append('  "function_name": "推断的函数名（英文，遵循常见命名规范）",')
        prompt_parts.append(
            '  "performance_analysis": "负载问题识别与优化建议（中文，100-300字）：是否存在性能瓶颈、为什么导致高指令数负载、可能的优化建议",'
        )
        prompt_parts.append('  "confidence": "高/中/低",')
        prompt_parts.append('  "reasoning": "推理过程（中文，说明为什么这样推断）"')
        prompt_parts.append('}')
        prompt_parts.append('')
        prompt_parts.append('注意:')
        prompt_parts.append('1. 如果符号表中已有函数名，优先使用符号名（如果是 C++ 名称修饰，请还原）')
        prompt_parts.append('2. 函数名应该遵循常见的命名规范（如驼峰命名、下划线命名）')
        prompt_parts.append('3. 功能描述应该具体，不要使用泛泛的描述，且不要包含性能分析内容')
        prompt_parts.append('4. 负载问题识别与优化建议（performance_analysis）必须详细说明：')
        prompt_parts.append('   - 是否存在明显的性能瓶颈（是/否，并说明原因）')
        prompt_parts.append('   - 为什么这个函数可能导致高指令数负载（具体分析）')
        prompt_parts.append('   - 可能的优化建议（如果有）')
        prompt_parts.append('   示例："存在性能瓶颈。该函数包含三层嵌套循环，时间复杂度为O(n³)，')
        prompt_parts.append(
            '   在处理大量数据时会导致高指令数负载。建议：1) 优化算法降低复杂度；2) 使用缓存减少重复计算"'
        )
        prompt_parts.append('5. 置信度评估标准：')
        prompt_parts.append(
            "   - '高'：能看到完整的函数逻辑，包括函数序言、主要业务逻辑、函数调用、返回值等，且功能明确"
        )
        prompt_parts.append("   - '中'：能看到部分函数逻辑，能推断出大致功能，但可能缺少一些细节")
        prompt_parts.append("   - '低'：只能看到函数片段（如只有函数结尾），无法确定完整功能")
        prompt_parts.append(
            "6. 如果反汇编代码从函数开始（有 pacibsp 或 stp x29, x30），且能看到主要逻辑，置信度应该设为'高'或'中'"
        )
        prompt_parts.append("7. 如果无法确定，confidence 设为'低'，function_name 可以为 null")

        return '\n'.join(prompt_parts)

    def _add_open_source_lib_prompt(self, prompt_parts: list[str], open_source_lib: Optional[str] = None):
        """
        添加开源库和 SIMD 相关的 prompt 内容（共享方法，避免重复代码）

        Args:
            prompt_parts: prompt 内容列表
            open_source_lib: 开源库名称（可选）
        """
        if not open_source_lib:
            return

        prompt_parts.append(f'🔍 重要提示：这是一个基于开源库 {open_source_lib} 的定制版本（三方库）。')
        prompt_parts.append(
            f'   该 SO 文件是基于 {open_source_lib} 开源项目进行定制开发的，函数实现可能与标准 {open_source_lib} 库相似。'
        )
        prompt_parts.append(f'   请利用您对 {open_source_lib} 开源库的知识，结合反编译代码的特征，')
        prompt_parts.append(f'   直接根据 {open_source_lib} 库中常见的函数名和功能模式来推断函数名和功能。')
        prompt_parts.append(f'   如果反编译代码的特征与 {open_source_lib} 库中的某个函数匹配，请优先使用该函数名。')
        prompt_parts.append('')
        prompt_parts.append('   📌 SIMD 向量化指令识别（重要：区分标量与向量）：')
        prompt_parts.append('   请仔细检查反汇编代码中是否使用了 SIMD（单指令多数据）向量化指令。')
        prompt_parts.append('')
        prompt_parts.append('   ✅ 向量 NEON 指令的判断标准（必须同时满足）：')
        prompt_parts.append('   1. 使用向量寄存器 v0-v31（不是标量寄存器 s0-s31）')
        prompt_parts.append('   2. 有向量后缀标识，如：')
        prompt_parts.append('      - .4s, .2s (4个/2个32位浮点数)')
        prompt_parts.append('      - .8h, .4h (8个/4个16位整数)')
        prompt_parts.append('      - .16b, .8b (16个/8个8位整数)')
        prompt_parts.append('      - .2d (2个64位浮点数)')
        prompt_parts.append('   3. 常见的向量 NEON 指令示例：')
        prompt_parts.append('      - fadd v0.4s, v1.4s, v2.4s  (向量加法，4个浮点数)')
        prompt_parts.append('      - fmla v0.4s, v1.4s, v2.4s  (向量融合乘加)')
        prompt_parts.append('      - ld1 {v0.4s}, [x0]         (向量加载)')
        prompt_parts.append('      - st1 {v0.4s}, [x0]         (向量存储)')
        prompt_parts.append('      - addv s0, v1.4s            (向量缩减)')
        prompt_parts.append('      - dup v0.4s, v1.s[0]        (向量复制)')
        prompt_parts.append('')
        prompt_parts.append('   ❌ 不是向量 NEON 的情况：')
        prompt_parts.append('   1. 只使用标量寄存器 s0-s31（32位浮点）或 d0-d31（64位浮点），没有向量后缀')
        prompt_parts.append('      - 例如：fmadd s0, s1, s2, s3  (标量融合乘加，不是向量)')
        prompt_parts.append('      - 例如：fadd s0, s1, s2       (标量浮点加法，不是向量)')
        prompt_parts.append('      - 例如：ldp s0, s1, [x0]     (加载两个标量，不是向量)')
        prompt_parts.append('   2. 虽然 fmadd/fnmsub 是性能优化指令，但如果只操作标量寄存器，')
        prompt_parts.append('      它们不是 SIMD 向量化指令，只是标量浮点优化指令。')
        prompt_parts.append('')
        prompt_parts.append('   🔍 判断步骤：')
        prompt_parts.append('   1. 首先检查是否使用 v0-v31 向量寄存器')
        prompt_parts.append('   2. 然后检查是否有向量后缀（.4s, .2s, .8h 等）')
        prompt_parts.append('   3. 只有同时满足以上两点，才是向量 NEON 指令')
        prompt_parts.append('   4. 如果只使用 s/d 寄存器且无向量后缀，则是标量指令，不是向量 NEON')
        prompt_parts.append('')
        prompt_parts.append('   如果识别到向量 NEON 指令的使用，请在功能描述中明确说明该函数使用了向量化优化，')
        prompt_parts.append('   并描述向量化的具体用途（如批量数据处理、并行计算、矩阵运算等）。')
        prompt_parts.append('')
        prompt_parts.append('   📌 开源库功能相关性：')
        prompt_parts.append(f'   在功能描述中，请结合 {open_source_lib} 开源库的典型功能和特性，')
        prompt_parts.append(
            f'   说明该函数在 {open_source_lib} 库中的作用和定位，以及与其他 {open_source_lib} 函数的关联性。'
        )
        prompt_parts.append(f'   例如：该函数是 {open_source_lib} 中哪个模块/组件的核心功能，')
        prompt_parts.append(f'   在 {open_source_lib} 的典型使用场景中扮演什么角色，')
        prompt_parts.append(f'   与 {open_source_lib} 库中哪些常见函数或功能相关。')
        prompt_parts.append('')

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """解析 LLM 返回的结果"""
        # 尝试提取 JSON
        result = {
            'functionality': '未知',
            'function_name': None,
            'performance_analysis': '',
            'confidence': '低',
            'reasoning': '解析失败',
        }

        # 检查响应是否可能被截断
        is_truncated = False
        if response_text.endswith('\\') or response_text.endswith('...') or not response_text.rstrip().endswith('}'):
            is_truncated = True

        # 尝试找到 JSON 块
        try:
            # 查找 JSON 块
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]

                # 如果响应可能被截断，尝试修复 JSON
                if (
                    is_truncated
                    and not json_str.rstrip().endswith('}')
                    and '"functionality"' in json_str
                    and '"reasoning"' in json_str
                ):
                    # 查找 reasoning 字段的开始
                    reasoning_start = json_str.rfind('"reasoning"')
                    if reasoning_start > 0:
                        # 尝试补全 JSON（添加缺失的引号和括号）
                        if not json_str.rstrip().endswith('"'):
                            # 找到最后一个未闭合的字符串
                            last_quote = json_str.rfind('"')
                            if last_quote > reasoning_start:
                                # 在最后一个引号后补全
                                json_str = json_str[: last_quote + 1] + '}'
                            else:
                                # 如果找不到引号，尝试在末尾补全
                                json_str = json_str.rstrip().rstrip(',') + '}'
                        else:
                            json_str = json_str.rstrip().rstrip(',') + '}'

                try:
                    parsed = json.loads(json_str)

                    result['functionality'] = parsed.get('functionality', '未知')
                    result['function_name'] = parsed.get('function_name')
                    result['performance_analysis'] = parsed.get('performance_analysis', '')
                    result['confidence'] = parsed.get('confidence', '低')
                    result['reasoning'] = parsed.get('reasoning', '')

                    # 调试：检查 performance_analysis 是否存在
                    if not result['performance_analysis']:
                        logger.warning(
                            '⚠️  LLM 响应中未包含 performance_analysis 字段或为空，请检查 prompt 是否包含该字段要求'
                        )
                        # 尝试从 reasoning 或其他字段中提取性能相关信息（fallback）
                        if result.get('reasoning') and (
                            '性能' in result['reasoning']
                            or '瓶颈' in result['reasoning']
                            or '负载' in result['reasoning']
                        ):
                            logger.debug(
                                'Detected performance-related information in reasoning field, but performance_analysis is empty'
                            )

                    # 如果检测到截断，在结果中标记
                    if is_truncated:
                        if result['functionality'].endswith('\\') or len(result['functionality']) < 100:
                            result['functionality'] += ' [响应可能被截断]'
                        if result['reasoning'].endswith('\\') or len(result['reasoning']) < 200:
                            result['reasoning'] += ' [响应可能被截断]'
                except json.JSONDecodeError as je:
                    # JSON 解析失败，尝试从文本中提取
                    logger.warning('Warning: JSON parsing failed, attempting text extraction: %s', str(je)[:100])
                    result['reasoning'] = f'JSON解析失败: {str(je)[:100]}\n原始响应: {response_text[:500]}'

                    # 尝试从文本中提取字段
                    name_match = re.search(
                        r'["\']?function_name["\']?\s*:\s*["\']([^"\']+)["\']',
                        response_text,
                    )
                    if name_match:
                        result['function_name'] = name_match.group(1).strip()

                    func_match = re.search(
                        r'["\']?functionality["\']?\s*:\s*["\']([^"\']+)["\']',
                        response_text,
                    )
                    if func_match:
                        result['functionality'] = func_match.group(1).strip()
            else:
                # 如果没有 JSON，尝试从文本中提取
                result['reasoning'] = response_text
                # 尝试提取函数名（查找类似 "function_name": "xxx" 的模式）
                name_match = re.search(
                    r'["\']?function_name["\']?\s*:\s*["\']?([^"\',\n}]+)',
                    response_text,
                )
                if name_match:
                    result['function_name'] = name_match.group(1).strip()

                func_match = re.search(
                    r'["\']?functionality["\']?\s*:\s*["\']?([^"\',\n}]+)',
                    response_text,
                )
                if func_match:
                    result['functionality'] = func_match.group(1).strip()
        except Exception as e:
            result['reasoning'] = f'解析失败: {str(e)}\n原始响应: {response_text[:500]}'

        return result

    def batch_analyze(self, analysis_tasks: list[dict[str, Any]], delay: float = 0.5) -> list[dict[str, Any]]:
        """
        批量分析多个函数（带延迟以避免 API 限流）

        Args:
            analysis_tasks: 分析任务列表，每个任务包含:
                {
                    'instructions': [...],
                    'strings': [...],
                    'symbol_name': ...,
                    'called_functions': [...],
                    'offset': ...
                }
            delay: 每次 API 调用之间的延迟（秒）

        Returns:
            分析结果列表
        """
        results = []
        total = len(analysis_tasks)

        for i, task in enumerate(analysis_tasks):
            if i > 0:
                time.sleep(delay)  # 避免 API 限流

            if (i + 1) % 10 == 0:
                logger.info(f'  LLM analysis progress: {i + 1}/{total}')

            result = self.analyze_with_llm(
                instructions=task.get('instructions', []),
                strings=task.get('strings', []),
                symbol_name=task.get('symbol_name'),
                called_functions=task.get('called_functions', []),
                offset=task.get('offset'),
            )
            results.append(result)

        return results

    def finalize(self):
        """完成分析后调用，保存所有缓存和统计信息"""
        if self.enable_cache:
            self._save_cache()
        self._save_token_stats()

    def _save_single_prompt(self, prompt: str, offset: Optional[int], symbol_name: Optional[str]):
        """保存单个函数的 prompt 到文件"""
        if not self.save_prompts:
            return

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒

            # 生成文件名
            offset_str = f'0x{offset:x}' if offset else 'unknown'
            symbol_str = symbol_name.replace('/', '_').replace('\\', '_') if symbol_name else 'unknown'
            # 限制文件名长度
            if len(symbol_str) > 50:
                symbol_str = symbol_str[:50]

            prompt_file = self.prompt_output_dir / f'prompt_{offset_str}_{symbol_str}_{timestamp}.txt'

            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write('=' * 80 + '\n')
                f.write('生成的 LLM Prompt (单个函数)\n')
                f.write('=' * 80 + '\n')
                f.write(f'生成时间: {datetime.now().isoformat()}\n')
                f.write(f'函数偏移量: {offset_str}\n')
                if symbol_name:
                    f.write(f'符号名: {symbol_name}\n')
                f.write(f'总长度: {len(prompt):,} 字符\n')
                f.write(f'估计 Token 数: ≈{len(prompt) // 4:,}\n')
                f.write('=' * 80 + '\n\n')
                f.write(prompt)
                f.write('\n\n' + '=' * 80 + '\n')

            logger.debug(f'Prompt saved: {prompt_file.name}')
        except Exception as e:
            logger.warning(f'Failed to save prompt: {e}')
