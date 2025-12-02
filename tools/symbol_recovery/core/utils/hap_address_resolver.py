#!/usr/bin/env python3
"""
HAP 地址解析模块

从 perf.db 查询 HAP 地址对应的 SO 文件信息
通过调用链信息找到相关的 SO 文件
"""

import re
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Tuple
from core.utils.logger import get_logger

logger = get_logger(__name__)


def is_hap_address(address: str) -> bool:
    """判断是否是 HAP 地址"""
    if not address:
        return False
    return 'entry.hap' in address.lower() or 'entry.zip' in address.lower()


def parse_hap_address(address: str) -> Optional[Tuple[str, int]]:
    """
    解析 HAP 地址字符串
    
    Args:
        address: 地址字符串（如 entry.hap+0x4bc171c 或 entry.hap@0x4bc171c）
    
    Returns:
        (hap_name, offset) 或 None
    """
    if not address:
        return None
    
    # 支持 + 和 @ 两种格式
    if '@' in address:
        parts = address.split('@')
    elif '+' in address:
        parts = address.split('+')
    else:
        return None
    
    if len(parts) != 2:
        return None
    
    offset_str = parts[1].strip()
    try:
        if offset_str.startswith('0x') or offset_str.startswith('0X'):
            offset = int(offset_str, 16)
        else:
            offset = int(offset_str, 16) if all(c in '0123456789abcdefABCDEF' for c in offset_str) else int(offset_str)
        return (parts[0].strip(), offset)
    except ValueError:
        return None


def resolve_hap_address_from_perfdb(perf_db: Path, address: str, quick_mode: bool = True, so_dir: Optional[Path] = None) -> Optional[Dict]:
    """
    从 perf.db 解析 HAP 地址，找到对应的 SO 文件
    
    Args:
        perf_db: perf.db 文件路径
        address: HAP 地址字符串（如 entry.hap+0x4bc171c）
        quick_mode: 快速模式（跳过调用链上下文）
    
    Returns:
        解析结果字典，包含：
        - so_name: SO 文件名
        - so_offset: SO 文件内偏移量
        - original_address: 原始地址
        - file_path: 原始文件路径（用于后续查找）
    """
    if not is_hap_address(address):
        return None
    
    parsed = parse_hap_address(address)
    if not parsed:
        logger.warning(f'⚠️  无法解析 HAP 地址: {address}')
        return None
    
    hap_name, hap_offset = parsed
    
    logger.info(f'🔍 解析 HAP 地址: {address} (偏移量: 0x{hap_offset:x})')
    
    try:
        conn = sqlite3.connect(str(perf_db))
        # 优化：设置 SQLite 性能参数
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA cache_size=10000')
        cursor = conn.cursor()
        
        try:
            # 1. 查找 entry.hap 的 file_id
            cursor.execute("""
                SELECT DISTINCT file_id, path 
                FROM perf_files 
                WHERE path LIKE '%entry.hap%' OR path LIKE '%entry.zip%'
                LIMIT 1
            """)
            hap_files = cursor.fetchall()
            
            if not hap_files:
                logger.warning(f'⚠️  未在 perf.db 中找到 entry.hap 文件')
                return None
            
            file_id, hap_file_path = hap_files[0]
            
            # 2. 查找 data_dict 中的地址
            offset_str = f'0x{hap_offset:x}'
            cursor.execute("""
                SELECT id, data 
                FROM data_dict 
                WHERE data = ? OR data LIKE ?
            """, (f'entry.hap+{offset_str}', f'entry.hap@{offset_str}'))
            data_dict_matches = cursor.fetchall()
            
            if not data_dict_matches:
                logger.warning(f'⚠️  未在 perf.db 中找到地址 {address}')
                return None
            
            data_dict_id = data_dict_matches[0][0]
            
            # 3. 查找调用链中相关的 SO 文件（通过调用链找到）
            # 优化：只查询包含该地址的调用链，然后查找同一调用链中的 SO 文件
            cursor.execute("""
                SELECT DISTINCT pc2.file_id, pf.path
                FROM perf_callchain pc1
                JOIN perf_callchain pc2 ON pc1.callchain_id = pc2.callchain_id
                JOIN perf_files pf ON pc2.file_id = pf.file_id
                WHERE pc1.file_id = ? AND pc1.name = ?
                AND pc2.file_id != ?
                AND pf.path LIKE '%.so'
                AND pf.path NOT LIKE '/system/%'
                AND pf.path NOT LIKE '/vendor/%'
                AND pf.path NOT LIKE '/lib/%'
                LIMIT 5
            """, (file_id, data_dict_id, file_id))
            
            so_files = cursor.fetchall()
            
            if so_files:
                # 选择第一个应用内的 SO 文件
                so_file_id, so_file_path = so_files[0]
                so_name = Path(so_file_path).name
                
                logger.info(f'✅ 从调用链找到相关 SO 文件: {so_name} (路径: {so_file_path})')
                
                # 检查偏移量是否超出文件大小
                so_file_path_local = so_dir / so_name if so_dir else Path(so_file_path)
                if so_file_path_local.exists():
                    so_size = so_file_path_local.stat().st_size
                    if hap_offset >= so_size:
                        logger.warning(f'⚠️  偏移量 0x{hap_offset:x} 超出 SO 文件大小 ({so_size:,} 字节)')
                        logger.warning(f'   HAP 偏移量无法直接映射到 SO 文件，跳过该地址')
                        return {
                            'so_name': so_name,
                            'so_file_path': str(so_file_path_local.resolve()),
                            'so_offset': hap_offset,
                            'original_address': address,
                            'original_file_path': hap_file_path,
                            'resolved': False,  # 偏移量无效，无法解析
                        }
                
                return {
                    'so_name': so_name,
                    'so_file_path': str(so_file_path_local.resolve()) if so_dir else so_file_path,
                    'so_offset': hap_offset,
                    'original_address': address,
                    'original_file_path': hap_file_path,
                    'resolved': True,
                }
            else:
                logger.warning(f'⚠️  调用链中未找到应用内的 SO 文件')
                
                # 如果提供了 so_dir，尝试从 so_dir 中递归查找所有 SO 文件
                if so_dir and so_dir.exists():
                    logger.info(f'尝试从 so_dir 中递归查找 SO 文件: {so_dir}')
                    so_files = list(so_dir.rglob('*.so'))
                    if so_files:
                        # 检查 HAP 偏移量是否合理（不能超过 SO 文件大小）
                        for so_file in so_files:
                            so_size = so_file.stat().st_size
                            # 如果 HAP 偏移量小于 SO 文件大小，可能是有效的偏移量
                            if hap_offset < so_size:
                                so_name = so_file.name
                                logger.info(f'✅ 从 so_dir 找到 SO 文件: {so_name} (偏移量 0x{hap_offset:x} 在文件大小范围内)')
                                return {
                                    'so_name': so_name,
                                    'so_file_path': str(so_file.resolve()),
                                    'so_offset': hap_offset,
                                    'original_address': address,
                                    'original_file_path': hap_file_path,
                                    'resolved': True,
                                }
                        
                        # 如果所有 SO 文件的偏移量都超出范围，无法解析
                        logger.warning(f'⚠️  HAP 偏移量 0x{hap_offset:x} 超出所有 SO 文件大小，无法解析')
                        return {
                            'so_name': None,
                            'so_file_path': None,
                            'so_offset': hap_offset,
                            'original_address': address,
                            'original_file_path': hap_file_path,
                            'resolved': False,
                        }
                
                # 仍然返回解析结果，但标记为未完全解析
                return {
                    'so_name': None,
                    'so_file_path': None,
                    'so_offset': hap_offset,
                    'original_address': address,
                    'original_file_path': hap_file_path,
                    'resolved': False,
                }
        
        finally:
            conn.close()
    
    except Exception as e:
        logger.error(f'❌ 解析 HAP 地址失败: {e}')
        import traceback
        logger.debug(traceback.format_exc())
        return None


def resolve_hap_addresses_batch(perf_db: Path, addresses: list, quick_mode: bool = True, so_dir: Optional[Path] = None) -> Dict[str, Dict]:
    """
    批量解析 HAP 地址
    
    Args:
        perf_db: perf.db 文件路径
        addresses: 地址列表
        quick_mode: 快速模式
    
    Returns:
        地址到解析结果的映射
    """
    results = {}
    hap_addresses = [addr for addr in addresses if is_hap_address(addr)]
    
    if not hap_addresses:
        return results
    
    logger.info(f'🔍 批量解析 {len(hap_addresses)} 个 HAP 地址...')
    
    # 打开一次数据库连接，批量查询
    try:
        conn = sqlite3.connect(str(perf_db))
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA cache_size=10000')
        cursor = conn.cursor()
        
        try:
            # 1. 查找 entry.hap 的 file_id
            cursor.execute("""
                SELECT DISTINCT file_id, path 
                FROM perf_files 
                WHERE path LIKE '%entry.hap%' OR path LIKE '%entry.zip%'
                LIMIT 1
            """)
            hap_files = cursor.fetchall()
            
            if not hap_files:
                logger.warning('⚠️  未在 perf.db 中找到 entry.hap 文件')
                return results
            
            file_id, hap_file_path = hap_files[0]
            
            # 2. 批量查找所有地址的 data_dict ID
            address_to_data_id = {}
            for address in hap_addresses:
                parsed = parse_hap_address(address)
                if not parsed:
                    continue
                
                hap_name, hap_offset = parsed
                offset_str = f'0x{hap_offset:x}'
                
                cursor.execute("""
                    SELECT id, data 
                    FROM data_dict 
                    WHERE data = ? OR data LIKE ?
                    LIMIT 1
                """, (f'entry.hap+{offset_str}', f'entry.hap@{offset_str}'))
                
                match = cursor.fetchone()
                if match:
                    address_to_data_id[address] = (match[0], hap_offset)
            
            logger.info(f'✅ 找到 {len(address_to_data_id)} 个地址的 data_dict 映射')
            
            # 3. 批量查找相关的 SO 文件
            for address, (data_id, hap_offset) in address_to_data_id.items():
                cursor.execute("""
                    SELECT DISTINCT pc2.file_id, pf.path
                    FROM perf_callchain pc1
                    JOIN perf_callchain pc2 ON pc1.callchain_id = pc2.callchain_id
                    JOIN perf_files pf ON pc2.file_id = pf.file_id
                    WHERE pc1.file_id = ? AND pc1.name = ?
                    AND pc2.file_id != ?
                    AND pf.path LIKE '%.so'
                    AND pf.path NOT LIKE '/system/%'
                    AND pf.path NOT LIKE '/vendor/%'
                    AND pf.path NOT LIKE '/lib/%'
                    LIMIT 1
                """, (file_id, data_id, file_id))
                
                so_file = cursor.fetchone()
                if so_file:
                    so_file_id, so_file_path = so_file
                    so_name = Path(so_file_path).name
                    results[address] = {
                        'so_name': so_name,
                        'so_file_path': so_file_path,
                        'so_offset': hap_offset,
                        'original_address': address,
                        'original_file_path': hap_file_path,
                        'resolved': True,
                    }
                else:
                    # 如果调用链中找不到，尝试从 so_dir 中递归查找
                    if so_dir and so_dir.exists():
                        so_files = list(so_dir.rglob('*.so'))
                        if so_files:
                            # 检查偏移量是否合理
                            resolved = False
                            selected_so = None
                            for so_file in so_files:
                                so_size = so_file.stat().st_size
                                if hap_offset < so_size:
                                    selected_so = so_file
                                    resolved = True
                                    break
                            
                            if selected_so:
                                so_name = selected_so.name
                                results[address] = {
                                    'so_name': so_name,
                                    'so_file_path': str(selected_so.resolve()),
                                    'so_offset': hap_offset,
                                    'original_address': address,
                                    'original_file_path': hap_file_path,
                                    'resolved': resolved,
                                }
                            else:
                                # 如果所有 SO 文件的偏移量都超出范围，无法解析
                                results[address] = {
                                    'so_name': None,
                                    'so_file_path': None,
                                    'so_offset': hap_offset,
                                    'original_address': address,
                                    'original_file_path': hap_file_path,
                                    'resolved': False,
                                }
                        else:
                            results[address] = {
                                'so_name': None,
                                'so_file_path': None,
                                'so_offset': hap_offset,
                                'original_address': address,
                                'original_file_path': hap_file_path,
                                'resolved': False,
                            }
                    else:
                        results[address] = {
                            'so_name': None,
                            'so_file_path': None,
                            'so_offset': hap_offset,
                            'original_address': address,
                            'original_file_path': hap_file_path,
                            'resolved': False,
                        }
        
        finally:
            conn.close()
    
    except Exception as e:
        logger.error(f'❌ 批量解析 HAP 地址失败: {e}')
        import traceback
        logger.debug(traceback.format_exc())
    
    logger.info(f'✅ 批量解析完成，成功解析 {sum(1 for r in results.values() if r.get("resolved"))}/{len(results)} 个地址')
    return results

