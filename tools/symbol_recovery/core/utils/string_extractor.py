#!/usr/bin/env python3
"""
通用字符串提取模块
通过分析反汇编代码中的字符串引用来精准提取相关的字符串常量
"""

import re
from typing import Optional

from elftools.elf.elffile import ELFFile

from core.utils import common as util
from core.utils.logger import get_logger

logger = get_logger(__name__)

# 需要过滤的字符串模式（错误消息、调试信息等）
FILTERED_STRING_PATTERNS = [
    r'^WeakRef:',
    r'^Error:',
    r'^Warning:',
    r'^Exception:',
    r'^Assertion failed',
    r'^Debug:',
    r'^Traceback',
    r'must be an object',
    r'must be a',
    r'cannot be',
    r'is not',
    r'has no attribute',
    r'TypeError',
    r'ValueError',
    r'AttributeError',
]


def should_filter_string(s: str) -> bool:
    """
    判断字符串是否应该被过滤掉

    Args:
        s: 待检查的字符串

    Returns:
        True 如果应该过滤，False 如果应该保留
    """
    if not s or len(s) < 4:
        return True

    s_lower = s.lower()

    # 检查是否匹配过滤模式
    for pattern in FILTERED_STRING_PATTERNS:
        if re.search(pattern, s_lower):
            return True

    # 过滤掉看起来像错误消息的字符串（包含常见错误关键词）
    error_keywords = ['error', 'warning', 'exception', 'failed', 'invalid', 'null', 'undefined']
    # 如果字符串很短且包含错误关键词，可能是错误消息
    return any(keyword in s_lower for keyword in error_keywords) and len(s) < 50


class StringExtractor:
    """字符串提取器 - 通过分析反汇编代码精准提取字符串常量"""

    def __init__(self, disassemble_func=None, md=None):
        """
        初始化字符串提取器

        Args:
            disassemble_func: 反汇编函数，签名: (elf_file, vaddr, size) -> List[Instruction]
            md: Capstone 反汇编器实例（如果为 None，将创建新的）
        """
        self.disassemble_func = disassemble_func
        self.md = md if md is not None else util.create_disassembler()

    def extract_strings_from_instructions(
        self, elf_file: ELFFile, instructions: list, vaddr: Optional[int] = None
    ) -> list[str]:
        """
        通过分析反汇编指令来提取字符串常量

        Args:
            elf_file: ELF 文件对象
            instructions: 反汇编指令列表
            vaddr: 函数虚拟地址（可选，用于调试）

        Returns:
            字符串常量列表
        """
        strings = []
        string_addresses = set()

        try:
            # 查找 .rodata 和 .data 段
            rodata_section = None
            data_section = None
            for section in elf_file.iter_sections():
                if section.name == '.rodata':
                    rodata_section = section
                elif section.name == '.data':
                    data_section = section

            # 优先使用 .rodata，如果没有则使用 .data
            target_section = rodata_section or data_section
            if not target_section:
                return strings

            section_vaddr = target_section['sh_addr']
            section_size = target_section['sh_size']
            section_data = target_section.data()

            # 分析指令，查找字符串引用
            # ARM64 中字符串引用通常通过以下方式：
            # 1. adrp + add 指令对
            # 2. adr 指令
            # 3. ldr 指令中的立即数地址

            adrp_registers = {}  # 存储 adrp 指令设置的寄存器值

            for inst in instructions:
                mnemonic = inst.mnemonic.lower()
                op_str = inst.op_str

                # 1. 处理 adrp 指令：adrp x0, #0x1234000
                if mnemonic == 'adrp':
                    page_base = self._parse_adrp(inst, op_str)
                    if page_base is not None:
                        parts = op_str.split(',')
                        if len(parts) == 2:
                            reg = parts[0].strip()
                            adrp_registers[reg] = page_base

                # 2. 处理 add 指令：add x0, x0, #0x567
                elif mnemonic == 'add':
                    full_addr = self._parse_add(op_str, adrp_registers)
                    if full_addr is not None and section_vaddr <= full_addr < section_vaddr + section_size:
                        string_addresses.add(full_addr)

                # 3. 处理 adr 指令：adr x0, #0x1234
                elif mnemonic == 'adr':
                    target_addr = self._parse_adr(inst, op_str)
                    if target_addr is not None and section_vaddr <= target_addr < section_vaddr + section_size:
                        string_addresses.add(target_addr)

                # 4. 处理 ldr 指令中的立即数地址：ldr x0, [x1, #0x1234]
                elif mnemonic == 'ldr' and '[' in op_str and ']' in op_str:
                    addr = self._parse_ldr_immediate(op_str, section_vaddr, section_size)
                    if addr is not None:
                        string_addresses.add(addr)

            # 从找到的地址中提取字符串
            for str_addr in string_addresses:
                string = self._extract_string_at_address(section_data, section_vaddr, str_addr)
                if string and string not in strings:  # 去重
                    # 过滤掉错误消息和调试字符串
                    if not should_filter_string(string):
                        strings.append(string)
                    else:
                        logger.debug(f'Filtered out string: {string[:50]}...')

            # 如果通过指令分析没有找到字符串，记录调试信息
            if not strings:
                logger.debug(
                    f'Instruction analysis found no strings (function address: 0x{(vaddr if vaddr is not None else 0):x})'
                )
                logger.debug('  Possible reasons:')
                logger.debug('    1. Function does not reference string constants (normal)')
                logger.debug('    2. Strings referenced in unsupported ways (need to improve extraction logic)')
                logger.debug('    3. Strings optimized or inlined by compiler (cannot extract)')

        except Exception:
            logger.exception('⚠️  Failed to extract string constants')

        return strings[:10]  # 最多返回10个字符串

    def extract_strings_near_offset(
        self, elf_file: ELFFile, vaddr: int, instructions: Optional[list] = None
    ) -> list[str]:
        """
        提取函数附近的字符串常量（主入口函数）

        Args:
            elf_file: ELF 文件对象
            vaddr: 函数虚拟地址
            instructions: 反汇编指令列表（如果为 None，将调用 disassemble_func）

        Returns:
            字符串常量列表
        """
        # 如果没有提供指令，需要先反汇编
        if instructions is None:
            if self.disassemble_func:
                instructions = self.disassemble_func(elf_file, vaddr)
            else:
                return []

            if not instructions:
                return []

        # 使用精准提取
        strings = self.extract_strings_from_instructions(elf_file, instructions, vaddr)

        # 如果通过指令分析没有找到字符串，使用 fallback
        if not strings:
            logger.debug('Instruction analysis found no strings, trying fallback method...')
            strings = self._fallback_extract_strings(elf_file)
            if strings:
                logger.debug(f'Fallback method found {len(strings)} strings')
            else:
                logger.debug(
                    'Fallback method also found no strings, this may be normal (function may not reference string constants)'
                )

        return strings

    def _parse_adrp(self, inst, op_str: str) -> Optional[int]:
        """解析 adrp 指令，返回页基址"""
        try:
            parts = op_str.split(',')
            if len(parts) != 2:
                return None

            imm_str = parts[1].strip()
            if imm_str.startswith('#'):
                imm_str = imm_str[1:]
            imm_value = int(imm_str, 16) if imm_str.startswith('0x') or imm_str.startswith('0X') else int(imm_str, 10)

            # adrp 加载的是页地址（4KB 对齐）
            return (inst.address & ~0xFFF) + (imm_value << 12)
        except (ValueError, IndexError):
            return None

    def _parse_add(self, op_str: str, adrp_registers: dict) -> Optional[int]:
        """解析 add 指令，如果源寄存器在 adrp_registers 中，返回完整地址"""
        try:
            parts = op_str.split(',')
            if len(parts) < 3:
                return None

            src_reg = parts[1].strip()
            if src_reg not in adrp_registers:
                return None

            imm_str = parts[2].strip()
            if imm_str.startswith('#'):
                imm_str = imm_str[1:]
            imm_value = int(imm_str, 16) if imm_str.startswith('0x') or imm_str.startswith('0X') else int(imm_str, 10)

            # 计算完整地址
            return adrp_registers[src_reg] + imm_value
        except (ValueError, IndexError):
            return None

    def _parse_adr(self, inst, op_str: str) -> Optional[int]:
        """解析 adr 指令，返回目标地址"""
        try:
            parts = op_str.split(',')
            if len(parts) != 2:
                return None

            imm_str = parts[1].strip()
            if imm_str.startswith('#'):
                imm_str = imm_str[1:]
            imm_value = int(imm_str, 16) if imm_str.startswith('0x') or imm_str.startswith('0X') else int(imm_str, 10)

            # adr 是相对地址
            return inst.address + imm_value
        except (ValueError, IndexError):
            return None

    def _parse_ldr_immediate(self, op_str: str, section_vaddr: int, section_size: int) -> Optional[int]:
        """解析 ldr 指令中的立即数地址"""
        try:
            # 匹配 [reg, #0x...] 或 [reg, #...] 格式
            match = re.search(r'\[.*?,\s*#(0x[0-9a-fA-F]+|[0-9]+)\]', op_str)
            if match:
                imm_str = match.group(1)
                if imm_str.startswith('0x') or imm_str.startswith('0X'):
                    imm_value = int(imm_str, 16)
                else:
                    imm_value = int(imm_str, 10)

                # 这里需要知道基址寄存器，简化处理：假设是绝对地址
                # 实际应该跟踪寄存器值
                if imm_value > 0x1000 and section_vaddr <= imm_value < section_vaddr + section_size:
                    return imm_value
        except (ValueError, IndexError):
            pass
        return None

    def _extract_string_at_address(self, section_data: bytes, section_vaddr: int, str_addr: int) -> Optional[str]:
        """从指定地址提取字符串"""
        try:
            # 计算在段内的偏移
            offset_in_section = str_addr - section_vaddr
            if not (0 <= offset_in_section < len(section_data)):
                return None

            # 从该地址开始提取字符串（直到遇到 null 或非可打印字符）
            current_string = b''
            for i in range(offset_in_section, min(offset_in_section + 256, len(section_data))):
                byte_val = section_data[i]
                if byte_val == 0:  # null 终止符
                    break
                if 32 <= byte_val < 127:  # 可打印 ASCII
                    current_string += bytes([byte_val])
                else:
                    break

            if len(current_string) >= 4:  # 至少4个字符
                return current_string.decode('utf-8', errors='ignore')
        except Exception:
            pass
        return None

    def _fallback_extract_strings(self, elf_file: ELFFile) -> list[str]:
        """Fallback: 在整个 .rodata 段中提取字符串（限制数量）"""
        strings = []
        try:
            # 查找 .rodata 段
            rodata_section = None
            for section in elf_file.iter_sections():
                if section.name == '.rodata':
                    rodata_section = section
                    break

            if not rodata_section:
                return strings

            section_data = rodata_section.data()

            # 在 .rodata 段中查找所有字符串，但限制数量
            current_string = b''
            for byte in section_data[: min(10000, len(section_data))]:  # 只搜索前10KB
                if 32 <= byte < 127:
                    current_string += bytes([byte])
                else:
                    if len(current_string) >= 4:
                        try:
                            decoded = current_string.decode('utf-8', errors='ignore')
                            # 过滤掉错误消息和调试字符串
                            if decoded not in strings and not should_filter_string(decoded):
                                strings.append(decoded)
                                if len(strings) >= 5:  # 最多5个作为fallback
                                    break
                        except Exception:
                            pass
                    current_string = b''
        except Exception:
            pass

        return strings
