#!/usr/bin/env python3

"""
使用 radare2 进行函数分析
"""

import contextlib
import json
from pathlib import Path
from typing import Any, Optional

import r2pipe

from core.utils.logger import get_logger
from core.utils.string_extractor import should_filter_string

logger = get_logger(__name__)


class R2FunctionAnalyzer:
    """使用 radare2 进行函数分析"""

    def __init__(self, so_file: Path, skip_decompilation: bool = False):
        """
        初始化分析器

        Args:
            so_file: SO 文件路径
            skip_decompilation: 是否跳过反编译（默认 False，启用反编译）
        """
        self.so_file = Path(so_file)
        if not self.so_file.exists():
            raise FileNotFoundError(f'SO 文件不存在: {so_file}')

        self.r2 = None
        self._functions_cache = None
        self.skip_decompilation = skip_decompilation

    def _open_r2(self, analyze_all=False):
        """
        打开 radare2 实例（延迟初始化，优化：按需分析）

        Args:
            analyze_all: 是否运行完整的 aaa 分析（默认 False，使用更轻量级的方法）
        """
        if self.r2 is None:
            try:
                self.r2 = r2pipe.open(str(self.so_file), flags=['-2'])
                if analyze_all:
                    # 完整分析（耗时，仅在必要时使用）
                    logger.info('正在使用 radare2 完整分析函数（aaa）...')
                    self.r2.cmd('aaa')  # 自动分析所有函数
                else:
                    # 轻量级分析：只分析基本信息和符号表（更快）
                    logger.info('正在使用 radare2 快速分析（aa）...')
                    self.r2.cmd('aa')  # 只分析基本块和函数（比 aaa 快得多）
            except Exception as e:
                logger.error('❌ 打开 radare2 失败: %s', e)
                raise

    def _close_r2(self):
        """关闭 radare2 实例"""
        if self.r2 is not None:
            with contextlib.suppress(Exception):
                self.r2.quit()
            self.r2 = None

    def find_function_by_offset(self, offset: int) -> Optional[dict[str, Any]]:
        """
        根据偏移量查找所在的函数（优化版本，充分利用 radare2 功能）

        Args:
            offset: 函数偏移量（虚拟地址）

        Returns:
            函数信息字典，如果未找到返回 None
        """
        # 优化：先尝试轻量级打开（不运行完整分析）
        self._open_r2(analyze_all=False)

        try:
            # 方法1: 使用 aflj 获取所有函数（从符号表或已分析的结果），然后查找包含该偏移量的函数
            # 这比运行 aaa 快得多，因为只是读取已有信息
            if self._functions_cache is None:
                functions_json = self.r2.cmd('aflj')
                if functions_json:
                    self._functions_cache = json.loads(functions_json)

            # 查找最匹配的函数（偏移量在函数范围内，且函数大小合理）
            # 使用 minbound 和 maxbound 来判断函数范围（更准确）
            best_match = None
            if self._functions_cache:
                for func in self._functions_cache:
                    # 优先使用 minbound/minaddr 和 maxbound/maxaddr（如果存在）
                    # 支持 radare2 不同版本的字段名差异（aflj 使用 minbound/maxbound，afij 使用 minaddr/maxaddr）
                    minbound = func.get('minbound', func.get('minaddr', func.get('offset', 0)))
                    maxbound = func.get('maxbound', func.get('maxaddr', func.get('offset', 0) + func.get('size', 0)))
                    func_offset = func.get('offset', minbound)
                    func_size = func.get('size', maxbound - minbound)

                    # 检查偏移量是否在函数范围内（使用 minbound 和 maxbound）
                    if (
                        minbound <= offset < maxbound
                        and func_size < 100 * 1024
                        and (best_match is None or func_size < best_match.get('size', float('inf')))
                    ):
                        best_match = {
                            'name': func.get('name', ''),
                            'offset': func_offset,
                            'size': func_size,
                            'minbound': minbound,
                            'maxbound': maxbound,
                            'calltype': func.get('calltype', ''),
                            'nargs': func.get('nargs', 0),
                            'nlocals': func.get('nlocals', 0),
                            'nbbs': func.get('nbbs', 0),
                            'edges': func.get('edges', 0),
                            'cc': func.get('cc', ''),
                            'frame': func.get('frame', 0),
                        }

            if best_match:
                return best_match

            # 方法2: 如果 aflj 没找到，使用 af @offset 只分析该地址的函数（比 aaa 快得多）
            # 这只会分析这一个函数，而不是整个文件的所有函数
            logger.info(f'在偏移量 0x{offset:x} 处未找到已知函数，尝试分析该地址...')

            # 使用 af @offset 只分析该地址的函数（不分析整个文件，比 aaa 快得多）
            self.r2.cmd(f'af @{offset}')  # 只分析该地址的函数，不分析整个文件

            # 重新获取函数列表（可能新增了刚分析的函数）
            functions_json = self.r2.cmd('aflj')
            if functions_json:
                self._functions_cache = json.loads(functions_json)
                # 重新查找
                for func in self._functions_cache:
                    # 支持 minbound/minaddr 和 maxbound/maxaddr
                    minbound = func.get('minbound', func.get('minaddr', func.get('offset', 0)))
                    maxbound = func.get('maxbound', func.get('maxaddr', func.get('offset', 0) + func.get('size', 0)))
                    func_size = func.get('size', maxbound - minbound)
                    if minbound <= offset < maxbound and 0 < func_size < 100 * 1024:
                        return {
                            'name': func.get('name', f'fcn.{offset:x}'),
                            'offset': func.get('offset', offset),
                            'size': func_size,
                            'minbound': minbound,
                            'maxbound': maxbound,
                            'calltype': func.get('calltype', ''),
                            'nargs': func.get('nargs', 0),
                            'nlocals': func.get('nlocals', 0),
                            'nbbs': func.get('nbbs', 0),
                            'edges': func.get('edges', 0),
                            'cc': func.get('cc', ''),
                            'frame': func.get('frame', 0),
                        }

            # 如果还是没找到，尝试获取当前函数信息
            func_info_json = self.r2.cmd('afij')
            if func_info_json:
                try:
                    func_info = json.loads(func_info_json)
                    if func_info and len(func_info) > 0:
                        func = func_info[0]
                        func_size = func.get('size', 0)
                        # 支持 minbound/minaddr 和 maxbound/maxaddr（radare2 不同版本可能使用不同字段名）
                        minbound = func.get('minbound', func.get('minaddr', func.get('offset', offset)))
                        maxbound = func.get('maxbound', func.get('maxaddr', minbound + func_size))
                        # 如果函数大小合理，使用它
                        if 0 < func_size < 100 * 1024:
                            return {
                                'name': func.get('name', f'fcn.{offset:x}'),
                                'offset': func.get('offset', offset),
                                'size': func_size,
                                'minbound': minbound,
                                'maxbound': maxbound,
                                'calltype': func.get('calltype', ''),
                                'nargs': func.get('nargs', 0),
                                'nlocals': func.get('nlocals', 0),
                                'nbbs': func.get('nbbs', 0),
                                'edges': func.get('edges', 0),
                                'cc': func.get('cc', ''),
                                'frame': func.get('frame', 0),
                            }
                except Exception:
                    pass

            # 如果自动分析失败，返回一个默认的函数信息（使用合理的默认大小）
            logger.warning('⚠️  无法自动识别函数边界，使用默认大小')
            return {
                'name': f'fcn.{offset:x}',
                'offset': offset,
                'size': 2000,  # 默认 2000 字节
                'calltype': 'arm64',
                'nargs': 0,
                'nlocals': 0,
                'nbbs': 0,
                'edges': 0,
                'cc': '',
                'frame': 0,
            }

        except Exception:
            logger.exception('⚠️  查找函数失败')
            # 返回默认函数信息
            return {
                'name': f'fcn.{offset:x}',
                'offset': offset,
                'size': 2000,
                'calltype': 'arm64',
                'nargs': 0,
                'nlocals': 0,
                'nbbs': 0,
                'edges': 0,
                'cc': '',
                'frame': 0,
            }

    def disassemble_function(self, offset: int, func_info: Optional[dict[str, Any]] = None) -> list[str]:
        """
        反汇编函数（优化版本，充分利用 radare2 的 pdf 命令）

        Args:
            offset: 函数偏移量
            func_info: 函数信息（可选，如果提供则使用，否则自动查找）

        Returns:
            指令列表，格式: ["0x1234: add x0, x1, x2", ...]
        """
        self._open_r2()

        try:
            # 如果提供了函数信息，使用函数起始地址
            func_offset = func_info['offset'] if func_info else offset

            # 验证偏移量是否超出文件大小
            try:
                file_size = self.so_file.stat().st_size
                if func_offset >= file_size:
                    logger.warning(f'⚠️  偏移量 0x{func_offset:x} 超出文件大小 ({file_size:,} 字节)，无法反汇编')
                    logger.warning(f'   这可能是 HAP 文件内的偏移量，而不是 SO 文件内的偏移量')
                    return []
            except Exception:
                pass  # 如果无法获取文件大小，继续尝试反汇编

            # 优化：直接使用 pdfj @offset 反汇编函数，不需要先跳转
            # pdfj: 以 JSON 格式反汇编函数（更高效）
            disasm_json = self.r2.cmd(f'pdfj @{func_offset}')

            if not disasm_json:
                return []

            disasm_data = json.loads(disasm_json)
            if not disasm_data:
                return []

            instructions = []

            # 处理不同的 JSON 格式
            # pdfj 可能返回单个对象（包含 ops 数组）或对象数组（基本块）
            if isinstance(disasm_data, list):
                # 如果是列表，遍历所有基本块
                for block in disasm_data:
                    if isinstance(block, dict) and 'ops' in block:
                        for op in block['ops']:
                            addr = op.get('offset', 0)
                            opcode = op.get('opcode', '')
                            if opcode:
                                instructions.append(f'0x{addr:x}: {opcode}')
            elif isinstance(disasm_data, dict) and 'ops' in disasm_data:
                # 如果是单个对象，直接获取 ops
                for op in disasm_data['ops']:
                    addr = op.get('offset', 0)
                    opcode = op.get('opcode', '')
                    if opcode:
                        instructions.append(f'0x{addr:x}: {opcode}')

            return instructions

        except Exception:
            logger.exception('⚠️  反汇编失败')
            return []

    def extract_strings_from_function(self, offset: int, func_info: Optional[dict[str, Any]] = None) -> list[str]:
        """
        从函数中提取字符串常量（优化版本，充分利用 radare2 的交叉引用功能）

        Args:
            offset: 函数偏移量
            func_info: 函数信息（可选）

        Returns:
            字符串列表
        """
        self._open_r2()

        try:
            if func_info:
                func_offset = func_info['offset']
                func_size = func_info.get('size', 0)
                func_end = func_offset + func_size
            else:
                func_offset = offset
                func_size = 0
                func_end = 0

            strings = []

            # 优化方法1: 使用 axtj 直接查找函数内所有字符串引用（更高效）
            # axtj @offset 查找从该地址出发的所有交叉引用
            try:
                # 先获取函数内所有字符串的地址
                # 使用 izj 获取所有字符串，然后检查哪些在函数中被引用
                strings_json = self.r2.cmd('izj')
                if strings_json:
                    strings_data = json.loads(strings_json)
                    if strings_data:
                        # 对每个字符串，检查函数中是否有引用
                        for s in strings_data:
                            str_addr = s.get('vaddr', 0)
                            str_value = s.get('string', '')

                            if not str_value or len(str_value) == 0:
                                continue

                            # 限制字符串长度（避免提取过长的字符串）
                            if len(str_value) > 200:
                                continue

                            # 过滤掉错误消息和调试字符串
                            if should_filter_string(str_value):
                                continue

                            # 使用 axtj 查找对该字符串地址的引用
                            try:
                                refs_json = self.r2.cmd(f'axtj @{str_addr}')
                                if refs_json:
                                    refs = json.loads(refs_json)
                                    if isinstance(refs, list):
                                        for ref in refs:
                                            ref_addr = ref.get('from', 0)
                                            # 检查引用是否在函数范围内
                                            if func_size > 0:
                                                if func_offset <= ref_addr < func_end:
                                                    if str_value not in strings:
                                                        strings.append(str_value)
                                                        # 限制字符串数量（最多 20 个）
                                                        if len(strings) >= 20:
                                                            return strings
                                                    break
                                            # 如果不知道函数大小，只要引用地址接近函数起始地址就接受
                                            elif abs(ref_addr - func_offset) < 10000:  # 10KB 范围内
                                                if str_value not in strings:
                                                    strings.append(str_value)
                                                    if len(strings) >= 20:
                                                        return strings
                                                break
                            except Exception:
                                pass
            except Exception:
                pass

            # 优化方法2: 使用 afxj 获取函数内的交叉引用（更直接）
            # 如果函数已分析，可以直接获取函数内的所有交叉引用
            if func_info:
                try:
                    # afxj: 获取函数内的交叉引用（JSON 格式）
                    xrefs_json = self.r2.cmd(f'afxj @{func_offset}')
                    if xrefs_json:
                        xrefs = json.loads(xrefs_json)
                        if isinstance(xrefs, list):
                            for _xref in xrefs:
                                # 检查是否是字符串引用
                                # 这里可以进一步优化，检查引用的目标是否是字符串
                                pass
                except Exception:
                    pass

            return strings

        except Exception as e:
            logger.warning('⚠️  提取字符串失败: %s', e)
            return []

    def decompile_function(self, offset: int, func_info: Optional[dict[str, Any]] = None) -> Optional[str]:
        """
        反编译函数为伪 C 代码

        Args:
            offset: 函数偏移量
            func_info: 函数信息（可选）

        Returns:
            反编译的伪 C 代码，如果反编译失败则返回 None
        """
        self._open_r2()

        try:
            func_offset = func_info['offset'] if func_info else offset

            # 确保函数已分析（如果未分析则自动分析）
            self.r2.cmd(f'af @{func_offset}')
            
            # 保存当前位置，以便后续恢复
            current_addr = self.r2.cmd('s')
            
            # 跳转到函数位置（反编译命令需要先跳转到函数位置）
            self.r2.cmd(f's @{func_offset}')

            # 尝试使用不同的反编译插件（按优先级）
            decompilers = [
                ('pdd', 'r2dec'),  # r2dec 反编译器
                ('pdg', 'r2ghidra'),  # Ghidra 反编译器
                ('pdq', 'pdq'),  # 快速反编译器
            ]

            for cmd, name in decompilers:
                try:
                    # 注意：pdg/pdd/pdq 命令需要在函数位置执行，不能使用 @offset 语法
                    decompiled = self.r2.cmd(cmd)
                    if decompiled and decompiled.strip() and not decompiled.startswith('Cannot'):
                        decompiled = decompiled.strip()
                        
                        # 验证反编译代码是否对应正确的函数
                        if len(decompiled) > 100:  # 确保不是空函数或错误的反编译
                            # 限制反编译代码长度，避免包含函数边界外的代码
                            # 根据函数大小估算合理的反编译代码长度
                            func_size = func_info.get('size', 0) if func_info else 0
                            
                            # 估算：每字节代码大约对应 2-5 行反编译代码
                            # 对于很小的函数（< 200 字节），限制在 500 行以内
                            # 对于小函数（< 500 字节），限制在 1500 行以内
                            # 对于大函数，限制在 5000 行以内
                            if func_size < 200:
                                max_lines = 500
                            elif func_size < 500:
                                max_lines = 1500
                            else:
                                max_lines = 5000
                            
                            lines = decompiled.split('\n')
                            if len(lines) > max_lines:
                                logger.warning(
                                    f'⚠️  反编译代码过长 ({len(lines)} 行)，函数大小仅 {func_size} 字节，'
                                    f'可能包含函数边界外的代码。限制为前 {max_lines} 行。'
                                )
                                # 只取前 max_lines 行，并尝试找到函数的结束位置
                                decompiled = '\n'.join(lines[:max_lines])
                                # 尝试找到最后一个完整的大括号块
                                brace_count = 0
                                last_valid_line = max_lines
                                for i in range(max_lines - 1, -1, -1):
                                    line = lines[i]
                                    brace_count += line.count('}') - line.count('{')
                                    if brace_count <= 0 and '}' in line:
                                        last_valid_line = i + 1
                                        break
                                if last_valid_line < max_lines:
                                    decompiled = '\n'.join(lines[:last_valid_line])
                                    logger.info(f'  截取到第 {last_valid_line} 行（找到函数结束）')
                            
                            # 过滤掉 warning 行
                            filtered_lines = []
                            for line in decompiled.split('\n'):
                                # 跳过 warning 行（以 //WARNING 开头或包含 WARNING 的注释行）
                                if not (line.strip().startswith('//WARNING') or 
                                        ('WARNING' in line.upper() and line.strip().startswith('//'))):
                                    filtered_lines.append(line)
                            decompiled = '\n'.join(filtered_lines)
                            
                            logger.info(f'✅ 使用 {name} 反编译成功 ({len(decompiled.split(chr(10)))} 行，已过滤 warning)')
                            # 恢复原位置
                            if current_addr:
                                try:
                                    self.r2.cmd(f's @{current_addr}')
                                except:
                                    pass
                            return decompiled
                except Exception as e:
                    logger.debug(f'反编译插件 {name} 失败: {e}')
                    continue
            
            # 恢复原位置
            if current_addr:
                try:
                    self.r2.cmd(f's @{current_addr}')
                except:
                    pass

            logger.warning('⚠️  所有反编译插件均不可用，将使用反汇编代码')
            return None

        except Exception as e:
            logger.warning('⚠️  反编译失败: %s', e)
            return None

    def get_called_functions(self, offset: int, func_info: Optional[dict[str, Any]] = None) -> list[str]:
        """
        获取函数调用的其他函数列表（优化：使用 radare2 的交叉引用功能）

        Args:
            offset: 函数偏移量
            func_info: 函数信息（可选）

        Returns:
            被调用函数名列表
        """
        self._open_r2()

        try:
            func_offset = func_info['offset'] if func_info else offset

            called_functions = []

            # 使用 axtj 查找函数内的所有交叉引用（函数调用）
            try:
                # 获取函数内的所有交叉引用
                xrefs_json = self.r2.cmd(f'axtj @{func_offset}')
                if xrefs_json:
                    xrefs = json.loads(xrefs_json)
                    if isinstance(xrefs, list):
                        for xref in xrefs:
                            # 检查是否是函数调用
                            xref_type = xref.get('type', '')
                            if 'CALL' in xref_type or 'JMP' in xref_type:
                                # 获取被调用函数的名称
                                target_addr = xref.get('to', 0)
                                if target_addr:
                                    # 查找该地址对应的函数名
                                    func_name_json = self.r2.cmd(f'fdj @{target_addr}')
                                    if func_name_json:
                                        try:
                                            func_data = json.loads(func_name_json)
                                            if isinstance(func_data, list) and len(func_data) > 0:
                                                func_name = func_data[0].get('name', '')
                                                if func_name and func_name not in called_functions:
                                                    called_functions.append(func_name)
                                        except Exception:
                                            pass
            except Exception:
                pass

            return called_functions

        except Exception as e:
            logger.warning('⚠️  获取调用函数列表失败: %s', e)
            return []

    def analyze_function_at_offset(self, offset: int) -> Optional[dict[str, Any]]:
        """
        分析指定偏移量的函数（完整流程，优化版本）

        Args:
            offset: 函数偏移量（从 perf 数据中获取）

        Returns:
            分析结果字典，包含：
            - func_info: 函数信息
            - instructions: 反汇编指令列表
            - strings: 字符串常量列表
            - called_functions: 被调用的函数列表（新增）
            - decompiled: 反编译代码（如果可用）
        """
        logger.info(f'\n{"=" * 80}')
        logger.info(f'使用 radare2 分析函数 (offset=0x{offset:x})')
        logger.info(f'{"=" * 80}')

        try:
            # 0. 验证偏移量是否超出文件大小
            try:
                file_size = self.so_file.stat().st_size
                if offset >= file_size:
                    logger.warning(f'⚠️  偏移量 0x{offset:x} ({offset:,} 字节) 超出文件大小 ({file_size:,} 字节)')
                    logger.warning(f'   这可能是 HAP 文件内的偏移量，而不是 SO 文件内的偏移量')
                    logger.warning(f'   无法进行反汇编分析')
                    return None
            except Exception:
                pass  # 如果无法获取文件大小，继续尝试分析

            # 1. 查找函数（优化：使用 af @offset 直接分析）
            logger.info('正在查找函数...')
            func_info = self.find_function_by_offset(offset)
            if not func_info:
                logger.warning('⚠️  未找到包含偏移量 0x%s 的函数', f'{offset:x}')
                return None

            logger.info(f'✅ 找到函数: {func_info["name"]}')
            logger.info(f'   起始地址: 0x{func_info["offset"]:x}')
            logger.info(f'   函数大小: {func_info["size"]} 字节')

            # 2. 反汇编函数（优化：使用 pdfj @offset 直接反汇编）
            # 注意：disassemble_function 内部会检查 func_info，如果提供了会使用函数起始地址
            logger.info('正在反汇编函数...')
            instructions = self.disassemble_function(offset, func_info)
            if not instructions:
                logger.warning('⚠️  反汇编失败')
                return None

            logger.info(f'✅ 反汇编成功，共 {len(instructions)} 条指令')

            # 3. 提取字符串（优化：使用 axtj 查找字符串引用）
            # extract_strings_from_function 内部会检查 func_info，如果提供了会使用函数起始地址
            logger.info('正在提取字符串常量...')
            strings = self.extract_strings_from_function(offset, func_info)
            if strings:
                logger.info(
                    f'✅ 找到 {len(strings)} 个字符串常量: {", ".join(strings[:3])}{"..." if len(strings) > 3 else ""}'
                )
            else:
                logger.warning('⚠️  未找到字符串常量')

            # 4. 获取被调用的函数列表（新增功能）
            # get_called_functions 内部会检查 func_info，如果提供了会使用函数起始地址
            logger.info('正在分析函数调用关系...')
            called_functions = self.get_called_functions(offset, func_info)
            if called_functions:
                logger.info(
                    f'✅ 找到 {len(called_functions)} 个被调用函数: {", ".join(called_functions[:5])}{"..." if len(called_functions) > 5 else ""}'
                )

            # 5. 尝试反编译（可选，如果插件可用且未跳过）
            # decompile_function 内部会检查 func_info，如果提供了会使用函数起始地址
            decompiled = None
            if not self.skip_decompilation:
                logger.info('正在尝试反编译...')
                decompiled = self.decompile_function(offset, func_info)
            else:
                logger.info('⏭️  跳过反编译（使用 --skip-decompilation 选项）')

            result = {
                'func_info': func_info,
                'instructions': instructions,
                'strings': strings,
                'called_functions': called_functions,  # 新增
                'offset': offset,
            }

            if decompiled:
                result['decompiled'] = decompiled

            return result

        except Exception:
            logger.exception('❌ 分析失败')
            return None

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self._close_r2()
        return False
