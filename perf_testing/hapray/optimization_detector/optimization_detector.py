import logging
import multiprocessing
import os
from collections import Counter
from functools import partial
from importlib.resources import files
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd
import tensorflow as tf
from tqdm import tqdm

from hapray.optimization_detector.file_info import FileInfo, FILE_STATUS_MAPPING


class OptimizationDetector:

    def __init__(self, workers: int = 1):
        self.parallel = workers > 1
        self.workers = min(workers, multiprocessing.cpu_count() - 1)
        self.model = None

    @staticmethod
    def _merge_chunk_results(df: pd.DataFrame) -> Dict[str, dict]:
        results = {}
        for file, group in df.groupby('file'):
            predictions = group['prediction'].tolist()
            distribution = dict(Counter(predictions))
            most_common = Counter(predictions).most_common(1)[0][0]
            confidence = predictions.count(most_common) / len(predictions)
            total_chunks = len(predictions)

            if any(x in distribution for x in [0, 1, 2, 3, 4]):
                opt_score = (
                    distribution.get(0, 0) * 0          # O0
                    + distribution.get(1, 0) * 0.33     # O1
                    + distribution.get(2, 0) * 0.67     # O2
                    + distribution.get(3, 0) * 1.0      # O3
                    + distribution.get(4, 0) * 0.67     # Os
                ) / total_chunks

                # Determine optimization category
                if opt_score < 0.2:
                    opt_category = "Unoptimized (O0 dominant)"
                elif opt_score < 0.4:
                    opt_category = "Low Optimization (O1 dominant)"
                elif opt_score < 0.7:
                    opt_category = "Medium Optimization (O2/Os dominant)"
                else:
                    opt_category = "High Optimization (O3 dominant)"
            else:
                opt_score = None
                opt_category = None

            results[file] = {
                'prediction': most_common,
                'confidence': confidence,
                'distribution': distribution,
                'opt_score': opt_score,
                'opt_category': opt_category,
                'total_chunks': total_chunks
            }

        return results

    def detect_optimization(self, file_infos: List[FileInfo]) -> List[Tuple[str, pd.DataFrame]]:
        success, failures, flags = self._analyze_files(file_infos)
        logging.info("Analysis complete: %s files analyzed, %s files failed", success, failures)
        return [('optimization', self._collect_results(flags, file_infos))]

    @staticmethod
    def _extract_features(file_info: FileInfo, features: int = 2048) -> Optional[np.ndarray]:
        data = file_info.extract_dot_text()
        if not data or len(data) == 0:
            return None

        sequences = []
        while data:
            seq = data[:features]
            if len(seq) < features:
                seq = np.pad(seq, (0, features - len(seq)), 'constant')
            sequences.append(seq)
            data = data[features:]
        return np.array(sequences, dtype=np.uint8)

    def _run_inference(self, file_info: FileInfo, model, features: int = 2048) -> List[Tuple[int, float]]:
        features_array = self._extract_features(file_info, features)
        if features_array is None or not features_array.size:
            return []

        y_predict = model.predict(features_array, batch_size=256)
        results = []
        for _predict in y_predict:
            prediction = np.argmax(_predict)
            confidence = _predict[prediction]
            results.append((prediction, confidence))
        return results

    def _run_analysis(self, file_info: FileInfo) -> Tuple[FileInfo, Optional[List[Tuple[int, float]]]]:
        """Run optimization flag detection on a single file"""
        # Lazy load model
        if self.model is None:
            flags_model = files('hapray.optimization_detector').joinpath("models/aarch64-flag-lstm-converted.h5")
            self.model = tf.keras.models.load_model(str(flags_model))

        return file_info, self._run_inference(file_info, self.model)

    def _analyze_files(self, file_infos: List[FileInfo]) -> Tuple[int, int, Dict]:
        # Filter out analyzed files
        remaining_files = []
        for file_info in file_infos:
            flags_path = os.path.join(FileInfo.CACHE_DIR, f"flags_{file_info.file_id}.csv")
            if os.path.exists(flags_path):
                logging.debug("Skipping already analyzed file: %s", file_info.absolute_path)
                continue
            remaining_files.append(file_info)

        logging.info("Files to analyze: %d", len(remaining_files))

        # Create directory for intermediate results
        os.makedirs(FileInfo.CACHE_DIR, exist_ok=True)

        if remaining_files:
            process_func = partial(self._run_analysis)
            if self.parallel and len(remaining_files) > 1:
                logging.info("Using %d parallel workers", self.workers)
                with multiprocessing.Pool(self.workers) as pool:
                    results = list(tqdm(
                        pool.imap(process_func, remaining_files),
                        total=len(remaining_files),
                        desc="Analyzing binaries optimization"
                    ))
            else:
                results = [process_func(fi) for fi in tqdm(remaining_files, desc="Analyzing binaries optimization")]

            # Save intermediate results
            for file_info, flags in results:
                if flags:
                    flags_path = os.path.join(FileInfo.CACHE_DIR, f"flags_{file_info.file_id}.csv")
                    with open(flags_path, "w", encoding='UTF-8') as f:
                        f.write("file,prediction,confidence\n")
                        for pred, conf in flags:
                            f.write(f"{file_info.file_id},{pred},{conf}\n")

        flags_results = {}
        files_with_results = 0
        for file_info in file_infos:
            flags_path = os.path.join(FileInfo.CACHE_DIR, f"flags_{file_info.file_id}.csv")
            if os.path.exists(flags_path):
                try:
                    flags_df = pd.read_csv(flags_path)
                    if not flags_df.empty:
                        file_results = self._merge_chunk_results(flags_df)
                        flags_results.update(file_results)
                        files_with_results += 1
                except Exception as e:
                    logging.error("Error loading results for %s: %s", file_info.absolute_path, e)

        return files_with_results, len(file_infos) - files_with_results, flags_results

    def _collect_results(self, flags_results: dict, file_infos: List[FileInfo]) -> pd.DataFrame:
        report_data = []
        for file_info in sorted(file_infos, key=lambda x: x.logical_path):
            result = flags_results.get(file_info.file_id)
            if result is None:
                status = FILE_STATUS_MAPPING['failed']
                opt_category = 'N/A'
                opt_score = 'N/A'
                distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
                total_chunks = 0
                size_optimized = 'N/A'
            else:
                status = FILE_STATUS_MAPPING['analyzed']
                opt_category = result['opt_category']
                opt_score = result['opt_score']
                distribution = result['distribution']
                total_chunks = result['total_chunks']
                os_chunks = distribution.get(4, 0)
                os_ratio = os_chunks / total_chunks if total_chunks > 0 else 0
                size_optimized = f"{'Yes' if os_ratio >= 0.5 else 'No'} ({os_ratio:.1%})"

            row = {
                "File": file_info.logical_path,
                "Status": status,
                "Optimization Category": opt_category or "N/A",
                "Optimization Score": f"{opt_score:.2%}" if isinstance(opt_score, float) else opt_score,
                "O0 Chunks": distribution.get(0, 0),
                "O1 Chunks": distribution.get(1, 0),
                "O2 Chunks": distribution.get(2, 0),
                "O3 Chunks": distribution.get(3, 0),
                "Os Chunks": distribution.get(4, 0),
                "Total Chunks": total_chunks,
                "File Size (bytes)": file_info.file_size,
                "Size Optimized": size_optimized,
            }
            report_data.append(row)
        return pd.DataFrame(report_data)
