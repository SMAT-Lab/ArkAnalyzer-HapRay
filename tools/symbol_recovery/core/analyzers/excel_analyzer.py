#!/usr/bin/env python3

"""
从 Excel 文件读取偏移量地址进行分析
输入：so文件 + Excel 文件路径（包含函数偏移量地址）
输出：分析结果的excel文件 + HTML报告
"""

from pathlib import Path
from typing import Any, Optional

import pandas as pd
from elftools.elf.elffile import ELFFile

from core.analyzers.r2_analyzer import R2FunctionAnalyzer
from core.llm.initializer import init_llm_analyzer
from core.utils import common as util
from core.utils.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_LLM_MODEL,
    EXCEL_ANALYSIS_PATTERN,
    EXCEL_REPORT_PATTERN,
    config,
)
from core.utils.logger import get_logger
from core.utils.string_extractor import StringExtractor
from core.utils.time_tracker import TimeTracker

logger = get_logger(__name__)


class ExcelOffsetAnalyzer:
    """从 Excel 文件读取偏移量地址进行分析"""

    def __init__(
        self,
        so_file: str,
        excel_file: str,
        use_llm: bool = True,
        llm_model: str = None,
        batch_size: int = None,
        context: str = None,
        save_prompts: bool = False,
        output_dir: str = None,
        skip_decompilation: bool = False,
        open_source_lib: str = None,
    ):
        """
        初始化分析器

        Args:
            so_file: SO 文件路径
            excel_file: Excel 文件路径（包含函数偏移量地址）
            use_llm: 是否使用 LLM 分析
            llm_model: LLM 模型名称
            use_batch_llm: 是否使用批量 LLM 分析
            batch_size: 批量分析时每个 prompt 包含的函数数量
            context: 自定义上下文信息（可选，如果不提供则根据 SO 文件名自动推断）
            save_prompts: 是否保存生成的 prompt 到文件
            output_dir: 输出目录，用于保存 prompt 文件
            skip_decompilation: 是否跳过反编译（默认 False，启用反编译可提高 LLM 分析质量但较慢）
        """
        self.so_file = Path(so_file)
        self.excel_file = Path(excel_file)
        self.use_llm = use_llm
        self.llm_model = llm_model if llm_model is not None else DEFAULT_LLM_MODEL
        self.batch_size = batch_size if batch_size is not None else DEFAULT_BATCH_SIZE
        self.context = context  # 自定义上下文
        self.skip_decompilation = skip_decompilation

        if not self.so_file.exists():
            raise FileNotFoundError(f'SO 文件不存在: {so_file}')
        if not self.excel_file.exists():
            raise FileNotFoundError(f'Excel 文件不存在: {excel_file}')

        # 初始化反汇编器
        self.md = util.create_disassembler()

        # 初始化字符串提取器（稍后设置 disassemble_func）
        self.string_extractor = None

        # 初始化 r2ghidra 反编译器（仅在 LLM 模式且未禁用反编译时使用）
        self.r2_analyzer: Optional[R2FunctionAnalyzer] = None
        if use_llm and not skip_decompilation:
            try:
                self.r2_analyzer = R2FunctionAnalyzer(self.so_file, skip_decompilation=False)
                logger.info(f'✅ r2 反编译器已初始化（r2ghidra）: {self.so_file.name}')
            except Exception as e:
                logger.warning(f'⚠️  r2 初始化失败，将仅使用反汇编: {e}')
                self.r2_analyzer = None

        # 初始化 LLM 分析器
        self.llm_analyzer, self.use_llm, self.use_batch_llm = init_llm_analyzer(
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            batch_size=self.batch_size,
            open_source_lib=open_source_lib,
            save_prompts=save_prompts,
            output_dir=output_dir,
        )

    def parse_offset(self, offset_str: str) -> Optional[int]:
        """解析偏移量字符串（使用统一的 util.parse_offset）"""
        return util.parse_offset(offset_str)

    def load_offsets_from_excel(self, df: pd.DataFrame = None) -> list[dict[str, Any]]:
        """
        从 Excel 文件加载偏移量地址

        Args:
            df: 可选，预加载的 DataFrame（多 SO 模式下传入过滤后的子集）

        Returns:
            偏移量列表，每个元素包含 {'offset': int, 'row_data': dict}
        """
        if df is None:
            logger.info(f'\n📖 读取 Excel 文件: {self.excel_file}')
            try:
                df = pd.read_excel(self.excel_file, engine='openpyxl')
                logger.info(f'✅ 成功读取 Excel 文件，共 {len(df)} 行')
            except Exception as e:
                logger.error('❌ 读取 Excel 文件失败: %s', e)
                return []
        else:
            logger.info(f'📋 使用预加载数据，共 {len(df)} 行')

        # 查找偏移量列（可能的列名）
        offset_column = None
        for col in df.columns:
            col_lower = str(col).lower()
            if 'offset' in col_lower or '偏移' in col_lower or '地址' in col_lower or 'address' in col_lower:
                offset_column = col
                break

        if offset_column is None:
            logger.warning('⚠️  未找到偏移量列，尝试使用第一列')
            offset_column = df.columns[0]

        logger.info(f'📋 使用列: {offset_column}')

        # 解析偏移量
        offsets = []
        for idx, row in df.iterrows():
            offset_str = row.get(offset_column, '')
            offset = self.parse_offset(offset_str)

            if offset is not None:
                offsets.append(
                    {
                        'offset': offset,
                        'offset_str': f'0x{offset:x}',
                        'row_index': idx,
                        'row_data': row.to_dict(),
                    }
                )
            else:
                logger.warning('⚠️  第 %s 行偏移量解析失败: %s', idx + 1, offset_str)

        logger.info(f'✅ 成功解析 {len(offsets)} 个偏移量')
        return offsets

    def find_function_start(self, elf_file: ELFFile, vaddr: int) -> int:
        """查找函数的起始位置（使用统一的 util.find_function_start）"""
        return util.find_function_start(elf_file, vaddr, self.md)

    def disassemble_function(self, elf_file: ELFFile, vaddr: int, size: int = 2000):
        """反汇编指定虚拟地址的函数代码

        Args:
            elf_file: ELF 文件对象
            vaddr: 函数虚拟地址
            size: 最大反汇编大小（默认 2000 字节，增加以支持大型函数）
        """
        try:
            # 获取 .text 段
            text_section = None
            for section in elf_file.iter_sections():
                if section.name == '.text':
                    text_section = section
                    break

            if not text_section:
                return None

            text_vaddr = text_section['sh_addr']
            text_size = text_section['sh_size']

            # 确保地址在 .text 段内
            if vaddr < text_vaddr or vaddr >= text_vaddr + text_size:
                logger.warning('⚠️  地址 0x%s 不在 .text 段内', f'{vaddr:x}')
                return None

            # 查找函数起始位置
            func_start = self.find_function_start(elf_file, vaddr)

            # 尝试从符号表获取函数大小（如果可用）
            func_size = None
            try:
                # 查找 .dynsym 或 .symtab 符号表
                for section_name in ['.dynsym', '.symtab']:
                    symbol_table = elf_file.get_section_by_name(section_name)
                    if symbol_table:
                        for symbol in symbol_table.iter_symbols():
                            if symbol['st_info']['type'] == 'STT_FUNC':
                                sym_addr = symbol['st_value']
                                sym_size = symbol['st_size']
                                # 检查地址是否在这个符号范围内
                                if sym_size > 0 and sym_addr <= vaddr < sym_addr + sym_size:
                                    func_size = sym_size
                                    logger.info(f'从符号表获取函数大小: {func_size} 字节 (符号: {symbol.name})')
                                    break
                    if func_size:
                        break
            except Exception as e:
                logger.debug('符号表查找失败，使用默认大小: %s', e)

            # 计算相对偏移量
            relative_start = func_start - text_vaddr
            if func_size:
                # 使用符号表中的函数大小，但不超过 size 限制
                relative_end = min(relative_start + func_size, relative_start + size, text_size)
            else:
                relative_end = min(relative_start + size, text_size)

            # 读取代码
            code = text_section.data()[relative_start:relative_end]

            if not code:
                return None

            # 反汇编
            instructions = []
            ret_count = 0  # 记录遇到的 ret 指令数量
            consecutive_ret = 0  # 连续 ret 指令计数

            for inst in self.md.disasm(code, func_start):
                instructions.append(inst)

                # 改进的停止条件：
                # 1. 如果遇到 ret 指令，记录但不立即停止
                # 2. 如果连续遇到多个 ret（可能是函数结束标记），且已反汇编足够指令，则停止
                # 3. 如果遇到 ret 且已经反汇编了大部分函数（超过 80%），则停止
                if inst.mnemonic == 'ret':
                    ret_count += 1
                    consecutive_ret += 1
                    # 如果连续遇到 2 个 ret，且已反汇编超过 300 条指令（约 1200 字节），可能是函数结束
                    # 注意：ARM64 指令通常是 4 字节，300 条指令 ≈ 1200 字节
                    # 这个阈值适用于大多数函数，但复杂函数可能超过这个值
                    if consecutive_ret >= 2 and len(instructions) > 300:
                        break
                    # 如果遇到 ret 且已反汇编超过 size 的 80%，可能是函数结束
                    if len(instructions) * 4 > (relative_end - relative_start) * 0.8:
                        break
                else:
                    consecutive_ret = 0  # 重置连续 ret 计数

                # 如果已经反汇编了足够多的指令（超过 size 限制），停止
                if len(instructions) * 4 > (relative_end - relative_start):
                    break

            return instructions
        except Exception:
            logger.exception('反汇编失败 (vaddr=0x%x)', vaddr)
            return None

    def _init_string_extractor(self):
        """延迟初始化字符串提取器（需要先定义 disassemble_function）"""
        if self.string_extractor is None:
            self.string_extractor = StringExtractor(disassemble_func=self.disassemble_function, md=self.md)

    def extract_strings_near_offset(self, elf_file: ELFFile, vaddr: int, instructions: list = None):
        """
        提取虚拟地址附近的字符串常量（使用通用字符串提取器）

        Args:
            elf_file: ELF 文件对象
            vaddr: 函数虚拟地址
            instructions: 反汇编指令列表（如果为 None，将重新反汇编）

        Returns:
            字符串常量列表
        """
        # 初始化字符串提取器（如果还没有初始化）
        self._init_string_extractor()

        # 使用通用的字符串提取器
        return self.string_extractor.extract_strings_near_offset(elf_file, vaddr, instructions)

    def analyze_offset(self, offset: int, rank: int) -> Optional[dict[str, Any]]:
        """
        分析单个偏移量

        Args:
            offset: 偏移量（虚拟地址）
            rank: 排名

        Returns:
            分析结果字典
        """
        logger.info(f'\n{"=" * 80}')
        logger.info(f'分析函数 #{rank}: 偏移量 0x{offset:x}')
        logger.info(f'{"=" * 80}')

        try:
            with open(self.so_file, 'rb') as f:
                elf_file = ELFFile(f)

                # 反汇编函数
                instructions = self.disassemble_function(elf_file, offset)
                if not instructions:
                    logger.warning('⚠️  无法反汇编偏移量 0x%s', f'{offset:x}')
                    return None

                logger.info(f'✅ 反汇编成功，共 {len(instructions)} 条指令')

                # 尝试 r2ghidra 反编译（仅在 LLM 模式且 r2_analyzer 可用时）
                decompiled: Optional[str] = None
                if self.r2_analyzer is not None:
                    try:
                        decompiled = self.r2_analyzer.decompile_function(offset)
                        if decompiled:
                            logger.info(f'✅ r2ghidra 反编译成功 ({len(decompiled.splitlines())} 行)')
                        else:
                            logger.debug('r2ghidra 反编译返回空，将仅使用反汇编')
                    except Exception as e:
                        logger.warning(f'⚠️  r2ghidra 反编译失败: {e}，将仅使用反汇编')

                # 初始化字符串提取器（如果还没有初始化）
                self._init_string_extractor()

                # 提取字符串（传入指令列表以进行精准分析）
                strings = []  # 初始化为空列表，确保始终有值
                try:
                    extracted_strings = self.string_extractor.extract_strings_from_instructions(
                        elf_file, instructions, offset
                    )
                    if extracted_strings:
                        strings = extracted_strings
                        logger.info(
                            f'找到 {len(strings)} 个字符串常量: {", ".join(strings[:3])}{"..." if len(strings) > 3 else ""}'
                        )
                    else:
                        logger.warning('⚠️  未找到字符串常量')
                        # 如果精准提取没有找到，尝试 fallback
                        fallback_strings = self.string_extractor._fallback_extract_strings(elf_file)
                        if fallback_strings:
                            strings = fallback_strings
                            logger.info(
                                f'使用 fallback 方法找到 {len(strings)} 个字符串常量: {", ".join(strings[:3])}{"..." if len(strings) > 3 else ""}'
                            )
                except Exception:
                    logger.exception('⚠️  字符串提取失败')
                strings = []  # 确保 strings 有默认值

                # 确保 strings 是列表类型
                if not isinstance(strings, list):
                    strings = []

                # LLM 分析
                llm_result = None
                if self.use_llm and self.llm_analyzer:
                    logger.info('🤖 开始 LLM 分析...')
                    try:
                        # 构建上下文信息（如果提供了自定义上下文则使用，否则根据 SO 文件自动推断）
                        context = self.context if self.context else self._build_context(offset, strings)

                        llm_result = self.llm_analyzer.analyze_with_llm(
                            instructions=[f'{inst.address:x}: {inst.mnemonic} {inst.op_str}' for inst in instructions],
                            strings=strings,
                            symbol_name=None,
                            called_functions=[],
                            offset=offset,
                            context=context,
                            decompiled=decompiled,
                        )
                        if llm_result:
                            logger.info('✅ LLM 分析完成')
                            if 'function_name' in llm_result:
                                logger.info(f'   推断函数名: {llm_result["function_name"]}')
                    except Exception as e:
                        logger.warning('⚠️  LLM 分析失败: %s', e)

                all_instructions = [
                    f'{inst.address:x}: {inst.mnemonic} {inst.op_str}' for inst in instructions
                ]
                return {
                    'rank': rank,
                    'offset': f'0x{offset:x}',
                    'offset_int': offset,
                    'so_file': str(self.so_file),
                    'instruction_count': len(instructions),
                    'strings': ', '.join(strings) if strings else '',
                    'llm_result': llm_result,
                    'function_name': llm_result.get('function_name', '') if llm_result else '',
                    'function_description': llm_result.get('functionality', '') if llm_result else '',
                    'performance_analysis': llm_result.get('performance_analysis', '') if llm_result else '',
                    'confidence': llm_result.get('confidence', '') if llm_result else '',
                    'instructions': all_instructions[:50],  # Excel 报告只保留前50条
                    # 结构化 JSON 输出所需字段
                    '_all_instructions': all_instructions,
                    '_strings': strings,
                    '_context': context if self.use_llm else '',
                    '_prompt': llm_result.get('_prompt', '') if llm_result else '',
                    '_decompiled': decompiled or '',
                }
        except Exception:
            logger.exception('❌ 分析偏移量 0x%s 失败', f'{offset:x}')
            return None

    def _build_context(self, offset: int, strings: list[str] = None) -> str:
        """
        构建 LLM 分析的上下文信息（与 llm_prompt_simple_example.txt 格式保持一致）

        Args:
            offset: 函数偏移量（用于内部逻辑，不包含在返回的上下文中）
            strings: 函数附近的字符串常量列表（用于内部逻辑，不包含在返回的上下文中）

        Returns:
            上下文字符串（简洁格式，只包含库的类型、名称、平台和主要功能）
        """
        so_name = self.so_file.name.lower()
        so_file_name = self.so_file.name

        # 根据 SO 文件名推断库的类型和用途，格式与示例保持一致
        if 'xwebcore' in so_name or 'xweb' in so_name:
            return (
                f'这是一个基于 Chromium Embedded Framework (CEF) 的 Web 核心库（{so_file_name}），'
                f'运行在 HarmonyOS 平台上。该库负责网页渲染、网络请求、DOM 操作等核心功能。'
            )
        if 'wechat' in so_name or 'wx' in so_name:
            return (
                f'这是一个来自微信（WeChat）应用的 SO 库（{so_file_name}），'
                f'运行在 HarmonyOS 平台上。该库负责即时通讯、社交网络、多媒体处理等功能。'
            )
        if 'taobao' in so_name or 'tb' in so_name:
            return (
                f'这是一个来自淘宝（Taobao）应用的 SO 库（{so_file_name}），'
                f'运行在 HarmonyOS 平台上。该库负责电商购物、商品展示、支付处理等功能。'
            )
        if 'chromium' in so_name or 'blink' in so_name or 'v8' in so_name:
            return (
                f'这是一个基于 Chromium/Blink 引擎的组件库（{so_file_name}），'
                f'通常用于 Web 渲染、JavaScript 执行等 Web 相关功能。'
            )
        if 'flutter' in so_name:
            return (
                f'这是一个 Flutter 框架相关的 SO 库（{so_file_name}），'
                f'Flutter 是 Google 开发的跨平台 UI 框架，用于构建移动应用界面。'
            )
        # 通用格式
        return f'这是一个 SO 库（{so_file_name}），来自 {self.so_file.parent.name} 目录。'

    def analyze_all(self, progress_callback=None, df: pd.DataFrame = None) -> list[dict[str, Any]]:
        """
        分析所有偏移量

        Args:
            progress_callback: 进度回调函数
            df: 可选，预加载的 DataFrame（多 SO 模式下传入过滤后的子集）

        Returns:
            分析结果列表
        """
        # 加载偏移量
        offsets_data = self.load_offsets_from_excel(df=df)
        if not offsets_data:
            logger.error('❌ 没有找到有效的偏移量')
            return []

        # 分析每个偏移量
        results = []
        total_offsets = len(offsets_data)
        logger.info(f'共 {total_offsets} 个偏移量需要分析')

        for idx, offset_data in enumerate(offsets_data, 1):
            if progress_callback:
                progress_callback(idx, f'分析偏移量 {offset_data["offset_str"]}')

            result = self.analyze_offset(offset_data['offset'], idx)
            if result:
                # 添加原始行数据
                result['original_row'] = offset_data['row_data']
                results.append(result)

        # 分析完成后，保存所有缓存和统计
        if self.use_llm and self.llm_analyzer:
            self.llm_analyzer.finalize()

        return results

    def save_results(self, results: list[dict[str, Any]], output_file: Optional[str] = None) -> str:
        """
        保存分析结果到 Excel 文件

        Args:
            results: 分析结果列表
            output_file: 输出文件路径（可选）

        Returns:
            输出文件路径
        """
        if output_file is None:
            output_dir = config.get_output_dir()
            config.ensure_output_dir(output_dir)
            output_file = str(output_dir / EXCEL_ANALYSIS_PATTERN.format(n=len(results)))

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f'\n💾 保存结果到: {output_file}')

        # 准备数据
        data = []
        for result in results:
            so_name = Path(result['so_file']).name
            row = {
                '排名': result['rank'],
                '地址': f"{so_name}+{result['offset']}",
                '偏移量': result['offset'],
                'SO文件': result['so_file'],
                '函数指令数': result['instruction_count'],
                '字符串常量': result['strings'],
            }

            if result.get('llm_result'):
                # 格式化函数名，添加 "Function: " 前缀
                function_name = result.get('function_name', '')
                if (
                    function_name
                    and function_name not in {'nan', 'None'}
                    and not function_name.startswith('Function: ')
                ):
                    function_name = f'Function: {function_name}'
                row['LLM推断函数名'] = function_name
                row['LLM功能描述'] = result.get('function_description', '')
                row['负载问题识别与优化建议'] = result.get('performance_analysis', '')
                row['LLM置信度'] = result.get('confidence', '')
            else:
                row['LLM推断函数名'] = ''
                row['LLM功能描述'] = ''
                row['负载问题识别与优化建议'] = ''
                row['LLM置信度'] = ''

            # 添加原始 Excel 中的其他列
            if 'original_row' in result:
                for key, value in result['original_row'].items():
                    if key not in row:
                        row[f'原始_{key}'] = value

            data.append(row)

        # 创建 DataFrame
        df = pd.DataFrame(data)

        # 保存到 Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='分析结果')

            # 设置列宽
            worksheet = writer.sheets['分析结果']
            for idx, col in enumerate(df.columns, 1):
                max_length = max(df[col].astype(str).map(len).max(), len(str(col)))
                worksheet.column_dimensions[chr(64 + idx)].width = min(max_length + 2, 50)

        logger.info(f'✅ Excel 报告已保存: {output_file}')
        return str(output_file)

    def save_json_outputs(
        self,
        results: list[dict[str, Any]],
        output_dir: str,
    ) -> tuple[str, str]:
        """
        将分析结果保存为两个结构化 JSON 文件：
          - symbol_recovery_results.json : 符号恢复结果（函数名、描述、置信度等）
          - symbol_recovery_prompts.json : 喂给 LLM 的输入（指令、字符串、context、prompt 文本）

        Args:
            results: analyze_all() 返回的结果列表
            output_dir: 输出目录

        Returns:
            (results_json_path, prompts_json_path)
        """
        import json as _json
        from pathlib import Path as _Path

        out = _Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        results_data = []
        prompts_data = []

        for r in results:
            so_name = _Path(r['so_file']).name

            results_data.append({
                'rank': r.get('rank'),
                'address': f"{so_name}+{r['offset']}",
                'offset': r['offset'],
                'so_file': so_name,
                'instruction_count': r.get('instruction_count', 0),
                'inferred_name': r.get('function_name', ''),
                'description': r.get('function_description', ''),
                'performance_analysis': r.get('performance_analysis', ''),
                'confidence': r.get('confidence', ''),
                'strings': r.get('_strings') or [],
            })

            prompts_data.append({
                'rank': r.get('rank'),
                'address': f"{so_name}+{r['offset']}",
                'offset': r['offset'],
                'so_file': so_name,
                'instruction_count': r.get('instruction_count', 0),
                'instructions': r.get('_all_instructions') or r.get('instructions') or [],
                'decompiled': r.get('_decompiled', ''),
                'strings': r.get('_strings') or [],
                'context': r.get('_context', ''),
                'prompt': r.get('_prompt', ''),
            })

        results_path = out / 'symbol_recovery_results.json'
        prompts_path = out / 'symbol_recovery_prompts.json'

        results_path.write_text(
            _json.dumps(results_data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        prompts_path.write_text(
            _json.dumps(prompts_data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        logger.info(f'📄 Results JSON: {results_path}')
        logger.info(f'📄 Prompts JSON: {prompts_path}')
        return str(results_path), str(prompts_path)

    def generate_html_report(
        self,
        results: list[dict[str, Any]],
        html_file: Optional[str] = None,
        time_tracker: Optional[TimeTracker] = None,
    ) -> str:
        """
        生成 HTML 报告

        Args:
            results: 分析结果列表
            html_file: HTML 文件路径（可选）
            time_tracker: 时间跟踪器（可选）

        Returns:
            HTML 文件路径
        """
        if html_file is None:
            output_dir = config.get_output_dir()
            config.ensure_output_dir(output_dir)
            html_file = str(output_dir / EXCEL_REPORT_PATTERN.format(n=len(results)))

        html_file = Path(html_file)
        html_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f'\n📄 生成 HTML 报告: {html_file}')

        # 直接生成 HTML（复用现有代码结构）
        # 转换结果格式
        formatted_results = []
        for result in results:
            formatted_result = {
                'rank': result['rank'],
                'file_path': '',
                'address': f'{Path(result["so_file"]).name}+{result["offset"]}',
                'offset': result['offset'],
                'so_file': result['so_file'],
                'instruction_count': result.get('instruction_count', 0),
                'strings': result.get('strings', ''),
                'call_count': 0,
                'event_count': 0,
                'llm_result': result.get('llm_result'),
                'function_name': result.get('function_name', ''),
                'function_description': result.get('function_description', ''),
                'confidence': result.get('confidence', ''),
            }
            formatted_results.append(formatted_result)

        html_content = util.render_html_report(
            formatted_results,
            llm_analyzer=self.llm_analyzer if self.use_llm else None,
            time_tracker=time_tracker,
            title='Excel 偏移量分析报告',
            show_file_path=False,
            show_instruction_count=False,
        )
        html_path = Path(html_file)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding='utf-8')

        logger.info(f'✅ HTML 报告已保存: {html_path}')
        return str(html_path)
