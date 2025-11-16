import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd
from tqdm import tqdm

from optimization_detector.file_info import FileInfo


def _find_hapray_sa_cmd() -> Optional[str]:
    """查找 hapray-sa-cmd.js 文件的路径

    Returns:
        hapray-sa-cmd.js 的绝对路径，如果未找到则返回 None
    """
    # 获取当前文件的目录
    current_file = Path(__file__).resolve()
    # 从当前文件向上查找项目根目录
    # optimization_detector/optimization_detector/invoke_symbols.py -> tools/optimization_detector -> tools -> dist/tools 或 tools
    project_root = current_file.parent.parent.parent.parent

    # 尝试多个可能的路径
    candidates = [
        project_root / 'dist' / 'tools' / 'sa-cmd' / 'hapray-sa-cmd.js',
        project_root / 'tools' / 'sa-cmd' / 'hapray-sa-cmd.js',
        project_root.parent / 'dist' / 'tools' / 'sa-cmd' / 'hapray-sa-cmd.js',
        project_root.parent / 'tools' / 'sa-cmd' / 'hapray-sa-cmd.js',
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    logging.warning('hapray-sa-cmd.js not found in expected locations')
    return None


def execute_hapray_cmd(args: list[str], timeout: int = 1800) -> bool:
    """执行 hapray 命令

    Args:
        args: 传递给 hapray 命令的参数列表
        timeout: 命令执行的超时时间（秒），默认30分钟

    Returns:
        如果执行成功返回 True，否则返回 False
    """
    hapray_cmd_path = _find_hapray_sa_cmd()
    if not hapray_cmd_path:
        logging.error('hapray-sa-cmd.js not found, cannot execute command')
        return False

    # 构建完整命令: node hapray-sa-cmd.js hapray <args>
    cmd = ['node', hapray_cmd_path, 'hapray', *args]

    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout
        )

        # 记录输出
        if result.stdout:
            logging.debug('Command output [%s]:\n%s', ' '.join(cmd), result.stdout)
        if result.stderr:
            logging.warning('Command warnings [%s]:\n%s', ' '.join(cmd), result.stderr)

        logging.info('Command executed successfully: %s', ' '.join(cmd))
        return True

    except subprocess.TimeoutExpired as e:
        logging.error(
            'Command timed out after %d seconds: %s\nSTDOUT: %s\nSTDERR: %s',
            timeout,
            ' '.join(cmd),
            e.stdout if e.stdout else '',
            e.stderr if e.stderr else '',
        )
        return False

    except subprocess.CalledProcessError as e:
        logging.error(
            'Command failed with code %d: %s\nSTDOUT: %s\nSTDERR: %s',
            e.returncode,
            ' '.join(cmd),
            e.stdout if e.stdout else '',
            e.stderr if e.stderr else '',
        )
        return False

    except FileNotFoundError:
        logging.error('Command not found: %s (Node.js may not be installed)', ' '.join(cmd))
        return False


class InvokeSymbols:
    def __init__(self):
        pass

    def _process_file(self, file_info: FileInfo, report_dir: str) -> tuple[list, dict]:
        """Process a single file and return symbol data"""
        output_file = os.path.join(FileInfo.CACHE_DIR, f'invoke_{file_info.file_id}.json')
        # Execute the hapray command to analyze the ELF file
        if not execute_hapray_cmd(['elf', '-i', file_info.absolute_path, '-r', report_dir, '-o', output_file]):
            # Command execution failed, return empty data
            logging.warning('Failed to execute hapray command for file: %s', file_info.logical_path)
            summary_data = {'File': file_info.logical_path, 'count': 0, 'invoked': '0.000'}
            return [], summary_data

        symbol_data = []
        invoked = 0
        summary_data = {'File': file_info.logical_path, 'count': 0, 'invoked': ''}
        # Read and parse the generated JSON output
        if not os.path.exists(output_file):
            logging.warning('Output file not found after command execution: %s', output_file)
            summary_data['invoked'] = '0.000'
            return [], summary_data

        try:
            with open(output_file, encoding='utf-8') as f:
                data = json.load(f)
                # Extract relevant symbol information
                for symbol in data:
                    if symbol.get('invoke'):
                        invoked += 1
                    symbol_data.append(
                        {'File': file_info.logical_path, 'Symbol': symbol.get('symbol'), 'Invoke': symbol.get('invoke')}
                    )
            summary_data['count'] = len(symbol_data)
            summary_data['invoked'] = f'{invoked * 100 / len(symbol_data):.3f}' if symbol_data else '0.000'
        except (OSError, json.JSONDecodeError) as e:
            logging.error('Error reading or parsing output file %s: %s', output_file, str(e))
            summary_data['invoked'] = '0.000'
            return [], summary_data

        return symbol_data, summary_data

    def analyze(self, file_infos: list[FileInfo], report_dir: str) -> list[tuple[str, pd.DataFrame]]:
        # Ensure cache directory exists
        os.makedirs(FileInfo.CACHE_DIR, exist_ok=True)
        symbol_detail_data = []
        summary_data = []

        # Create a progress bar with total number of files
        progress_bar = tqdm(total=len(file_infos), desc='Analyzing files symbols', unit='file')

        # Use thread pool for parallel file processing
        with ThreadPoolExecutor() as executor:
            # Submit all file processing tasks to the thread pool
            future_to_file = {
                executor.submit(self._process_file, file_info, report_dir): file_info for file_info in file_infos
            }

            # Process results as they complete with progress tracking
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    # Get the result from completed future
                    file_data, summary = future.result()
                    # Add file results to main report
                    symbol_detail_data.extend(file_data)
                    summary_data.append(summary)

                    # Update progress bar with file name
                    progress_bar.set_postfix(file=file_info.logical_path, refresh=False)
                except Exception as e:
                    # Handle errors for individual files without stopping entire process
                    logging.error('Error processing file %s: %s', file_info.logical_path, str(e))
                finally:
                    # Always update the progress count
                    progress_bar.update(1)

        # Close the progress bar when done
        progress_bar.close()

        # Convert collected data to DataFrame
        return [('symbols', pd.DataFrame(symbol_detail_data)), ('symbols_summary', pd.DataFrame(summary_data))]
