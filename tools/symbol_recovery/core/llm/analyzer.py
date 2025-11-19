#!/usr/bin/env python3
"""
使用 Poe API (OpenAI 兼容) 来分析反汇编代码并推断函数功能和函数名
参考: https://creator.poe.com/docs/external-applications/tool-calling
"""

import json
import os
import re
import signal
import time
from pathlib import Path
from typing import Any, Optional

from core.utils import config
from core.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import openai
except ImportError:
    openai = None
    logger.warning('未安装 openai 库，LLM 分析功能将不可用')
    logger.warning('请安装 openai 库: pip install openai')
except Exception as e:
    logger.error('加载 openai 库时出错: %s', e)
    raise

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    logger.warning('未安装 python-dotenv 库，将跳过 .env 文件的加载')
    logger.warning('请安装 python-dotenv 库: pip install python-dotenv')
except Exception as e:
    logger.error('加载 .env 文件时出错: %s', e)
    raise


class LLMFunctionAnalyzer:
    """使用大语言模型分析反汇编代码"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
        base_url: Optional[str] = None,
        enable_cache: bool = True,
    ):
        """
        初始化 LLM 分析器

        Args:
            api_key: API key，如果为 None 则从环境变量或 .env 文件读取
            model: 使用的模型名称，如果为 None 则使用 config.DEFAULT_LLM_MODEL
            base_url: API 基础 URL，如果为 None 则使用 config.LLM_BASE_URL
            enable_cache: 是否启用缓存（避免重复分析相同代码）
        """
        if openai is None:
            raise ImportError('需要安装 openai 库: pip install openai')

        # 从配置获取默认值
        llm_config = config.get_llm_config()
        api_key_env = llm_config['api_key_env']
        default_base_url = llm_config['base_url']
        default_model = llm_config['model']

        # 优先使用参数传入的 key，其次从环境变量读取，最后尝试从 .env 文件读取
        self.api_key = api_key or os.getenv(api_key_env)
        if not self.api_key:
            # 尝试从 .env 文件读取（如果安装了 python-dotenv）
            env_file = Path('.env')
            if env_file.exists():
                try:
                    with open(env_file, encoding='utf-8') as f:
                        for raw_line in f:
                            line = raw_line.strip()
                            # 支持多种环境变量名（向后兼容）
                            key_patterns = [
                                f'{api_key_env}=',
                                'POE_API_KEY=',
                                'OPENAI_API_KEY=',
                                'LLM_API_KEY=',
                            ]
                            for pattern in key_patterns:
                                if line.startswith(pattern) and not line.startswith('#'):
                                    self.api_key = line.split('=', 1)[1].strip()
                                    break
                            if self.api_key:
                                break
                except Exception:
                    pass

        if not self.api_key:
            service_type = llm_config['service_type']
            raise ValueError(
                f'需要提供 {service_type.upper()} API key。\n'
                f'方法1: 通过参数传入 api_key\n'
                f'方法2: 设置环境变量 {api_key_env}\n'
                f'方法3: 在 .env 文件中设置 {api_key_env}=your_key\n'
                f'方法4: 切换服务类型: 设置环境变量 LLM_SERVICE_TYPE=poe|openai|claude|custom'
            )

        self.model = model or default_model
        self.base_url = base_url or default_base_url
        self.enable_cache = enable_cache
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_file = llm_config['cache_file']

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
        logger.info('Token 使用统计')
        logger.info('=' * 80)
        logger.info(f'总请求数: {stats["total_requests"]}')
        logger.info(f'缓存命中: {stats["cached_requests"]}')
        logger.info(f'实际 API 调用: {stats["total_requests"] - stats["cached_requests"]}')
        logger.info(f'\n总 Token 数: {stats["total_tokens"]:,}')
        logger.info(f'  输入 Token: {stats["total_input_tokens"]:,}')
        logger.info(f'  输出 Token: {stats["total_output_tokens"]:,}')
        if stats['total_requests'] - stats['cached_requests'] > 0:
            logger.info('\n平均每次调用:')
            logger.info(f'  输入 Token: {stats["average_input_tokens"]:.0f}')
            logger.info(f'  输出 Token: {stats["average_output_tokens"]:.0f}')
        logger.info('=' * 80)

    def _get_cache_key(
        self,
        instructions: list[str],
        strings: list[str],
        symbol_name: Optional[str] = None,
    ) -> str:
        """生成缓存键"""
        # 使用前20条指令和字符串生成缓存键
        key_parts = [
            '; '.join(instructions[:20]),
            ', '.join(str(s) for s in strings[:10]),  # 确保所有元素都是字符串
            str(symbol_name) if symbol_name else '',
        ]
        return '|'.join(key_parts)

    def analyze_with_llm(
        self,
        instructions: list[str],
        strings: list[str],
        symbol_name: Optional[str] = None,
        called_functions: Optional[list[str]] = None,
        offset: Optional[int] = None,
        context: Optional[str] = None,
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
            cache_key = self._get_cache_key(instructions, strings, symbol_name)
            if cache_key in self.cache:
                self.token_stats['cached_requests'] += 1
                self.token_stats['total_requests'] += 1
                logger.info(f'[DEBUG] 使用缓存结果（总指令数: {len(instructions)}，缓存键基于前20条指令）')
                return self.cache[cache_key]

        # 构建提示词
        logger.info(f'[DEBUG] 构建新的 prompt（总指令数: {len(instructions)}）')
        prompt = self._build_prompt(instructions, strings, symbol_name, called_functions, offset, context)

        try:
            # 调用 LLM（设置超时避免卡住）
            # 从配置获取超时时间
            timeout_seconds = config.LLM_TIMEOUT

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

                    # 保存统计
                    self._save_token_stats()
            finally:
                # 恢复信号处理
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            result_text = response.choices[0].message.content

            # 解析结果
            result = self._parse_llm_response(result_text)

            # 保存到缓存
            if self.enable_cache:
                self.cache[cache_key] = result
                self._save_cache()

            return result

        except Exception as e:
            logger.warning('警告: LLM 分析失败: %s', e)
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
    ) -> str:
        """构建 LLM 提示词"""
        prompt_parts = []

        prompt_parts.append('请分析以下 ARM64 反汇编代码，推断函数的功能和可能的函数名。')
        prompt_parts.append('')

        # 添加背景信息
        if context:
            prompt_parts.append('背景信息:')
            prompt_parts.append(context)
            prompt_parts.append('')

        if offset:
            prompt_parts.append(f'函数偏移量: 0x{offset:x}')

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
        logger.info(f'[DEBUG] 总指令数: {len(instructions)}, 将发送给 LLM: {max_instructions}')
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
        prompt_parts.append('  "functionality": "详细的功能描述（中文，50-200字）",')
        prompt_parts.append('  "function_name": "推断的函数名（英文，遵循常见命名规范）",')
        prompt_parts.append('  "confidence": "高/中/低",')
        prompt_parts.append('  "reasoning": "推理过程（中文，说明为什么这样推断）"')
        prompt_parts.append('}')
        prompt_parts.append('')
        prompt_parts.append('注意:')
        prompt_parts.append('1. 如果符号表中已有函数名，优先使用符号名（如果是 C++ 名称修饰，请还原）')
        prompt_parts.append('2. 函数名应该遵循常见的命名规范（如驼峰命名、下划线命名）')
        prompt_parts.append('3. 功能描述应该具体，不要使用泛泛的描述')
        prompt_parts.append('4. 置信度评估标准：')
        prompt_parts.append(
            "   - '高'：能看到完整的函数逻辑，包括函数序言、主要业务逻辑、函数调用、返回值等，且功能明确"
        )
        prompt_parts.append("   - '中'：能看到部分函数逻辑，能推断出大致功能，但可能缺少一些细节")
        prompt_parts.append("   - '低'：只能看到函数片段（如只有函数结尾），无法确定完整功能")
        prompt_parts.append(
            "5. 如果反汇编代码从函数开始（有 pacibsp 或 stp x29, x30），且能看到主要逻辑，置信度应该设为'高'或'中'"
        )
        prompt_parts.append("6. 如果无法确定，confidence 设为'低'，function_name 可以为 null")

        return '\n'.join(prompt_parts)

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """解析 LLM 返回的结果"""
        # 尝试提取 JSON
        result = {
            'functionality': '未知',
            'function_name': None,
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
                    result['confidence'] = parsed.get('confidence', '低')
                    result['reasoning'] = parsed.get('reasoning', '')

                    # 如果检测到截断，在结果中标记
                    if is_truncated:
                        if result['functionality'].endswith('\\') or len(result['functionality']) < 100:
                            result['functionality'] += ' [响应可能被截断]'
                        if result['reasoning'].endswith('\\') or len(result['reasoning']) < 200:
                            result['reasoning'] += ' [响应可能被截断]'
                except json.JSONDecodeError as je:
                    # JSON 解析失败，尝试从文本中提取
                    logger.warning('警告: JSON 解析失败，尝试文本提取: %s', str(je)[:100])
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
                logger.info(f'  LLM 分析进度: {i + 1}/{total}')

            result = self.analyze_with_llm(
                instructions=task.get('instructions', []),
                strings=task.get('strings', []),
                symbol_name=task.get('symbol_name'),
                called_functions=task.get('called_functions', []),
                offset=task.get('offset'),
            )
            results.append(result)

        return results
