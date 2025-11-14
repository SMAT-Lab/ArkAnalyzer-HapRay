"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from tqdm import tqdm

from optimization_detector.file_info import FileInfo


class InvokeSymbols:
    def __init__(self, hapray_cmd_executor: Callable[[list[str]], bool] | None = None):
        """
        Initialize InvokeSymbols analyzer.

        Args:
            hapray_cmd_executor: Optional function to execute hapray commands.
                                 If None, will try to find and execute hapray command directly.
                                 Function signature: (args: list[str]) -> bool
        """
        self.hapray_cmd_executor = hapray_cmd_executor

    def _execute_hapray_cmd(self, args: list[str]) -> bool:
        """Execute hapray command using provided executor or by finding hapray command"""
        if self.hapray_cmd_executor:
            return self.hapray_cmd_executor(args)

        # Try to find hapray command
        # First try: look for hapray-sa-cmd relative to optimization_detector_tool
        # optimization_detector_tool is in tools/, so go up to project root
        current_file = os.path.abspath(__file__)
        # __file__ is in tools/optimization_detector_tool/optimization_detector/
        # Go up 3 levels to get project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        hapray_cmd_path = os.path.join(project_root, 'sa-cmd', 'hapray-sa-cmd')

        if not os.path.exists(hapray_cmd_path):
            # Try alternative: use 'hapray' command if available
            try:
                result = subprocess.run(
                    ['hapray', 'elf'] + args[1:],  # Skip 'elf' from args
                    check=False,
                    capture_output=True,
                    timeout=1800,
                )
                return result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logging.error(
                    'hapray command not found. Please provide hapray_cmd_executor or ensure hapray is in PATH'
                )
                return False

        # Execute using node and hapray-sa-cmd
        cmd = ['node', hapray_cmd_path, 'hapray'] + args
        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800
            )
            if result.stdout:
                logging.debug('hapray command output: %s', result.stdout)
            if result.stderr:
                logging.warning('hapray command warnings: %s', result.stderr)
            return True
        except subprocess.CalledProcessError as e:
            logging.error('hapray command failed: %s', e.stderr)
            return False
        except subprocess.TimeoutExpired:
            logging.error('hapray command timed out')
            return False
        except FileNotFoundError:
            logging.error('node command not found. Please ensure Node.js is installed')
            return False

    def _process_file(self, file_info: FileInfo, report_dir: str) -> tuple[list, dict]:
        """Process a single file and return symbol data"""
        output_file = os.path.join(FileInfo.CACHE_DIR, f'invoke_{file_info.file_id}.json')
        # Execute the hapray command to analyze the ELF file
        success = self._execute_hapray_cmd(['elf', '-i', file_info.absolute_path, '-r', report_dir, '-o', output_file])

        if not success:
            logging.warning('Failed to analyze file %s', file_info.logical_path)
            return [], {'File': file_info.logical_path, 'count': 0, 'invoked': '0.000'}

        symbol_data = []
        invoked = 0
        summary_data = {'File': file_info.logical_path, 'count': 0, 'invoked': ''}

        # Read and parse the generated JSON output
        if not os.path.exists(output_file):
            logging.warning('Output file not found: %s', output_file)
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
            logging.error('Failed to read output file %s: %s', output_file, e)
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
