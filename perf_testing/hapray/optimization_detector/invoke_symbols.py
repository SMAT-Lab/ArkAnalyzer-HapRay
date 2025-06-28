import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import pandas as pd
from tqdm import tqdm

from hapray.core.common.exe_utils import ExeUtils
from hapray.optimization_detector.file_info import FileInfo


class InvokeSymbols:
    def __init__(self):
        pass

    def _process_file(self, file_info: FileInfo, report_dir: str) -> Tuple[list, dict]:
        """Process a single file and return symbol data"""
        output_file = os.path.join(FileInfo.CACHE_DIR, f"invoke_{file_info.file_id}.json")
        # Execute the hapray command to analyze the ELF file
        ExeUtils.execute_hapray_cmd(['elf', '-i', file_info.absolute_path, '-r', report_dir, '-o', output_file])

        symbol_data = []
        invoked = 0
        summary_data = {'File': file_info.logical_path, 'count': 0, 'invoked': ''}
        # Read and parse the generated JSON output
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Extract relevant symbol information
            for symbol in data:
                if symbol.get('invoke'):
                    invoked += 1
                symbol_data.append({
                    'File': file_info.logical_path,
                    'Symbol': symbol.get('symbol'),
                    'Invoke': symbol.get('invoke')
                })
        summary_data['count'] = len(symbol_data)
        summary_data['invoked'] = f'{invoked * 100 / len(symbol_data):.3f}'
        return symbol_data, summary_data

    def analyze(self, file_infos: List[FileInfo], report_dir: str) -> List[Tuple[str, pd.DataFrame]]:
        # Ensure cache directory exists
        os.makedirs(FileInfo.CACHE_DIR, exist_ok=True)
        symbol_detail_data = []
        summary_data = []

        # Create a progress bar with total number of files
        progress_bar = tqdm(total=len(file_infos), desc="Analyzing files symbols", unit="file")

        # Use thread pool for parallel file processing
        with ThreadPoolExecutor() as executor:
            # Submit all file processing tasks to the thread pool
            future_to_file = {
                executor.submit(self._process_file, file_info, report_dir): file_info
                for file_info in file_infos
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
                    logging.error("Error processing file %s: %s", file_info.logical_path, str(e))
                finally:
                    # Always update the progress count
                    progress_bar.update(1)

        # Close the progress bar when done
        progress_bar.close()

        # Convert collected data to DataFrame
        return [('symbols', pd.DataFrame(symbol_detail_data)), ('symbols_summary', pd.DataFrame(summary_data))]
