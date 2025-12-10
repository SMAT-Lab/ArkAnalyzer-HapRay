import logging
import multiprocessing
import os
from collections import Counter
from functools import partial
from importlib.resources import files
from typing import Optional

import numpy as np
import pandas as pd
import tensorflow as tf
from tqdm import tqdm

from optimization_detector.file_info import FILE_STATUS_MAPPING, FileInfo


class TimeoutError(Exception):
    """Timeout exception for file analysis"""

    pass


class OptimizationDetector:
    def __init__(
        self, workers: int = 1, timeout: Optional[int] = None, enable_lto: bool = True, enable_opt: bool = True
    ):
        self.parallel = workers > 1
        self.workers = min(workers, multiprocessing.cpu_count() - 1)
        self.timeout = timeout
        self.enable_lto = enable_lto
        self.enable_opt = enable_opt
        self.model = None
        self.flags_model = files('optimization_detector').joinpath('models/aarch64-flag-lstm-converted.h5')

        # 配置 GPU 加速并缓存 GPU 状态
        self.gpus = self._configure_gpu()
        self.use_gpu = len(self.gpus) > 0

        # LTO检测器（延迟加载）
        self.lto_detector = None
        if enable_lto:
            try:
                from optimization_detector.lto_detector import LtoDetector  # noqa: PLC0415

                self.lto_detector = LtoDetector()
                logging.info('LTO detection enabled')
            except ImportError as e:
                logging.warning('Failed to load LTO detector: %s. LTO detection disabled.', e)
                self.enable_lto = False

    @staticmethod
    def _configure_gpu():
        """配置 TensorFlow 使用 GPU 加速，返回 GPU 设备列表"""
        try:
            # 检查 GPU 是否可用
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                try:
                    # 为每个 GPU 设置内存增长，避免一次性占用所有内存
                    for gpu in gpus:
                        tf.config.experimental.set_memory_growth(gpu, True)
                    logging.info('GPU acceleration enabled: %d GPU(s) detected', len(gpus))
                    # 打印 GPU 信息
                    for i, gpu in enumerate(gpus):
                        gpu_details = tf.config.experimental.get_device_details(gpu)
                        logging.info('GPU %d: %s', i, gpu_details.get('device_name', 'Unknown'))
                except RuntimeError as e:
                    # 如果已经在运行时设置，忽略错误
                    logging.debug('GPU memory growth already configured: %s', e)
            else:
                logging.info('No GPU detected, using CPU')
            return gpus
        except Exception as e:
            logging.warning('Failed to configure GPU: %s. Falling back to CPU.', e)
            return []

    @staticmethod
    def _merge_chunk_results(df: pd.DataFrame) -> dict[str, dict]:
        results = {}
        for file, group in df.groupby('file'):
            predictions = group['prediction'].tolist()
            distribution = dict(Counter(predictions))
            most_common = Counter(predictions).most_common(1)[0][0]
            confidence = predictions.count(most_common) / len(predictions)
            total_chunks = len(predictions)

            if any(x in distribution for x in [0, 1, 2, 3, 4]):
                opt_score = (
                    distribution.get(0, 0) * 0  # O0
                    + distribution.get(1, 0) * 0.33  # O1
                    + distribution.get(2, 0) * 0.67  # O2
                    + distribution.get(3, 0) * 1.0  # O3
                    + distribution.get(4, 0) * 0.67  # Os
                ) / total_chunks

                # Determine optimization category
                if opt_score < 0.2:
                    opt_category = 'Unoptimized (O0 dominant)'
                elif opt_score < 0.4:
                    opt_category = 'Low Optimization (O1 dominant)'
                elif opt_score < 0.7:
                    opt_category = 'Medium Optimization (O2/Os dominant)'
                else:
                    opt_category = 'High Optimization (O3 dominant)'
            else:
                opt_score = None
                opt_category = None

            results[file] = {
                'prediction': most_common,
                'confidence': confidence,
                'distribution': distribution,
                'opt_score': opt_score,
                'opt_category': opt_category,
                'total_chunks': total_chunks,
            }

        return results

    def detect_optimization(self, file_infos: list[FileInfo]) -> list[tuple[str, pd.DataFrame]]:
        # 优化级别检测
        flags = {}
        success = 0
        failures = 0
        if self.enable_opt:
            success, failures, flags = self._analyze_files(file_infos)
        else:
            logging.info('Optimization level detection disabled (--no-opt)')

        # LTO检测
        lto_results = {}
        if self.enable_lto and self.lto_detector:
            logging.info('Running LTO detection on %d files', len(file_infos))
            lto_results = self._detect_lto(file_infos, flags)
            logging.info('LTO detection complete')

        if self.enable_opt:
            logging.info('Analysis complete: %s files analyzed, %s files failed', success, failures)
        return [('optimization', self._collect_results(flags, file_infos, lto_results))]

    @staticmethod
    def _extract_features(file_info: FileInfo, features: int = 2048) -> Optional[list[int]]:
        data = file_info.extract_dot_text()
        if not data or len(data) == 0:
            return None

        sequences = []
        for counter in range(0, len(data), features):
            seq = data[counter : counter + features]
            if len(seq) < features:
                seq = np.pad(seq, (0, features - len(seq)), 'constant')
            sequences.append(seq)
        return sequences

    def apply_model(self, data, model):
        if not data.size:
            return None
        # 根据是否有 GPU 调整批处理大小
        batch_size = 512 if self.use_gpu else 256  # GPU 可以使用更大的批处理大小
        return model.predict(data, batch_size=batch_size, verbose=0)

    def _run_inference(self, file_info: FileInfo, features: int = 2048) -> list[tuple[int, float]]:
        features_array = self._extract_features(file_info, features)
        if features_array is None or not len(features_array):
            return []

        def chunkify(lst, n):
            return [lst[i::n] for i in range(n)]

        nped_features_array = list(map(partial(np.array, dtype=np.uint8), chunkify(features_array, self.workers * 10)))

        # For TensorFlow models, avoid multiprocessing (TF models can't be pickled safely)
        # Use simple list comprehension instead
        y_predict_list = [self.apply_model(data, self.model) for data in nped_features_array]

        results = []

        for y_predict in y_predict_list:
            if y_predict is None:
                continue
            for _predict in y_predict:
                prediction = np.argmax(_predict)
                confidence = _predict[prediction]
                results.append((prediction, confidence))
        return results

    def _detect_lto(self, file_infos: list[FileInfo], flags_results: dict) -> dict:
        """对SO文件进行LTO检测"""
        lto_results = {}

        for file_info in tqdm(file_infos, desc='Detecting LTO'):
            try:
                # 获取优化级别（如果已检测）
                opt_level = None
                result = flags_results.get(file_info.file_id)
                if result:
                    prediction = result.get('prediction')
                    opt_level_map = {0: 'O0', 1: 'O1', 2: 'O2', 3: 'O3', 4: 'Os'}
                    opt_level = opt_level_map.get(prediction, 'O2')

                # 调用LTO检测器
                lto_result = self.lto_detector.detect(file_info.absolute_path, opt_level)
                lto_results[file_info.file_id] = lto_result

            except Exception as e:
                logging.debug('LTO detection failed for %s: %s', file_info.absolute_path, e)
                lto_results[file_info.file_id] = {'score': None, 'prediction': 'Failed', 'model_used': 'N/A'}

        return lto_results

    def _run_analysis(self, file_info: FileInfo) -> tuple[FileInfo, Optional[list[tuple[int, float]]]]:
        """Run optimization flag detection on a single file with optional timeout"""
        # Lazy load model
        if self.model is None:
            # 使用 GPU 策略（如果可用）
            if self.use_gpu:
                # 使用 MirroredStrategy 进行多 GPU 推理（如果有多个 GPU）
                if len(self.gpus) > 1:
                    strategy = tf.distribute.MirroredStrategy()
                    with strategy.scope():
                        self.model = tf.keras.models.load_model(str(self.flags_model))
                        self.model.compile(optimizer=self.model.optimizer, loss=self.model.loss, metrics=['accuracy'])
                    logging.info('Model loaded with multi-GPU support (%d GPUs)', len(self.gpus))
                else:
                    # 单 GPU，直接加载
                    self.model = tf.keras.models.load_model(str(self.flags_model))
                    self.model.compile(optimizer=self.model.optimizer, loss=self.model.loss, metrics=['accuracy'])
                    logging.info('Model loaded with GPU acceleration')
            else:
                # CPU 模式
                self.model = tf.keras.models.load_model(str(self.flags_model))
                self.model.compile(optimizer=self.model.optimizer, loss=self.model.loss, metrics=['accuracy'])
                logging.info('Model loaded with CPU')

        if self.timeout is None:
            # No timeout, run normally
            return file_info, self._run_inference(file_info)

        # Use ThreadPoolExecutor with timeout for cross-platform compatibility
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
        from concurrent.futures import TimeoutError as FutureTimeoutError  # noqa: PLC0415

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._run_inference, file_info)
            try:
                result = future.result(timeout=self.timeout)
                return file_info, result
            except FutureTimeoutError:
                logging.warning('File analysis timeout after %d seconds: %s', self.timeout, file_info.absolute_path)
                # Cancel the future if possible
                future.cancel()
                return file_info, None

    def _analyze_files(self, file_infos: list[FileInfo]) -> tuple[int, int, dict]:
        # Filter out analyzed files
        remaining_files = []
        for file_info in file_infos:
            flags_path = os.path.join(FileInfo.CACHE_DIR, f'flags_{file_info.file_id}.csv')
            if os.path.exists(flags_path):
                logging.debug('Skipping already analyzed file: %s', file_info.absolute_path)
                continue
            remaining_files.append(file_info)

        logging.info('Files to analyze: %d', len(remaining_files))

        # Create directory for intermediate results
        os.makedirs(FileInfo.CACHE_DIR, exist_ok=True)

        if remaining_files:
            process_func = partial(self._run_analysis)
            if self.parallel and len(remaining_files) > 1:
                logging.info('Using %d parallel workers', self.workers)
                results = list(
                    tqdm(
                        map(process_func, remaining_files),
                        total=len(remaining_files),
                        desc='Analyzing binaries optimization',
                    )
                )
            else:
                results = [process_func(fi) for fi in tqdm(remaining_files, desc='Analyzing binaries optimization')]

            # Save intermediate results
            for file_info, flags in results:
                if flags:
                    flags_path = os.path.join(FileInfo.CACHE_DIR, f'flags_{file_info.file_id}.csv')
                    with open(flags_path, 'w', encoding='UTF-8') as f:
                        f.write('file,prediction,confidence\n')
                        for pred, conf in flags:
                            f.write(f'{file_info.file_id},{pred},{conf}\n')

        flags_results = {}
        files_with_results = 0
        for file_info in file_infos:
            flags_path = os.path.join(FileInfo.CACHE_DIR, f'flags_{file_info.file_id}.csv')
            if os.path.exists(flags_path):
                try:
                    flags_df = pd.read_csv(flags_path)
                    if not flags_df.empty:
                        file_results = self._merge_chunk_results(flags_df)
                        flags_results.update(file_results)
                        files_with_results += 1
                except Exception as e:
                    logging.error('Error loading results for %s: %s', file_info.absolute_path, e)

        return files_with_results, len(file_infos) - files_with_results, flags_results

    def _collect_results(
        self, flags_results: dict, file_infos: list[FileInfo], lto_results: Optional[dict] = None
    ) -> pd.DataFrame:
        if lto_results is None:
            lto_results = {}

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
                size_optimized = f'{"Yes" if os_ratio >= 0.5 else "No"} ({os_ratio:.1%})'

            row = {
                'File': file_info.logical_path,
                'Status': status,
                'Optimization Category': opt_category or 'N/A',
                'Optimization Score': f'{opt_score:.2%}' if isinstance(opt_score, float) else opt_score,
                'O0 Chunks': distribution.get(0, 0),
                'O1 Chunks': distribution.get(1, 0),
                'O2 Chunks': distribution.get(2, 0),
                'O3 Chunks': distribution.get(3, 0),
                'Os Chunks': distribution.get(4, 0),
                'Total Chunks': total_chunks,
                'File Size (bytes)': file_info.file_size,
                'Size Optimized': size_optimized,
            }

            # 添加LTO检测列
            if lto_results and file_info.file_id in lto_results:
                lto_result = lto_results[file_info.file_id]
                row['LTO Score'] = f'{lto_result["score"]:.4f}' if lto_result['score'] is not None else 'N/A'
                row['LTO Prediction'] = lto_result['prediction']
                row['LTO Model Used'] = lto_result['model_used']
            elif self.enable_lto:
                row['LTO Score'] = 'N/A'
                row['LTO Prediction'] = 'N/A'
                row['LTO Model Used'] = 'N/A'

            report_data.append(row)
        return pd.DataFrame(report_data)
