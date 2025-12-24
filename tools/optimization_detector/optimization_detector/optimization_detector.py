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
from elftools.elf.elffile import ELFFile
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
        """Extract features from file, returns None if no data, empty list if error, list if success"""
        try:
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
        except Exception:
            # 如果提取失败，返回 None（会在 _run_analysis 中捕获异常）
            return None

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

                # 调用LTO检测器（传递file_info以支持缓存）
                lto_result = self.lto_detector.detect(file_info, opt_level)
                lto_results[file_info.file_id] = lto_result

            except Exception as e:
                logging.debug('LTO detection failed for %s: %s', file_info.absolute_path, e)
                lto_results[file_info.file_id] = {'score': None, 'prediction': 'Failed', 'model_used': 'N/A'}

        return lto_results

    def _run_analysis(self, file_info: FileInfo) -> tuple[FileInfo, Optional[list[tuple[int, float]]], Optional[str]]:
        """Run optimization flag detection on a single file with optional timeout
        Returns: (file_info, flags, error_reason)
        - flags: None means skip (too few chunks), [] means no data, list means success
        - error_reason: None means no error, str means failure reason
        """
        try:
            # 检查chunk数量，如果小于10个chunk，跳过预测
            MIN_CHUNKS = 10
            # 先尝试直接打开 ELF 文件，以便捕获更详细的错误信息
            try:
                with open(file_info.absolute_path, 'rb') as f:
                    elf = ELFFile(f)
                    section = elf.get_section_by_name('.text')
                    if not section:
                        error_msg = 'No .text section found in ELF file'
                        return file_info, [], error_msg
            except Exception as e:
                # 捕获 ELF 文件读取异常（如 Magic number does not match）
                error_msg = f'Failed to read ELF file: {str(e)}'
                logging.error('Error reading ELF file %s: %s', file_info.absolute_path, e)
                return file_info, [], error_msg

            # 如果 ELF 文件读取成功，再尝试提取 .text 段数据
            text_data = file_info.extract_dot_text()
            if not text_data:
                # 检查文件类型
                if file_info.file_type.value == 0xFF:  # NOT_SUPPORT
                    error_msg = 'File type not supported (not .so or .a)'
                else:
                    error_msg = 'No .text section data extracted (section exists but data is empty)'
                return file_info, [], error_msg

            # 提取特征
            features_array = self._extract_features(file_info, features=2048)
            # 只有当有数据但chunk数量不足时才跳过预测
            # 如果没有数据（features_array is None），继续执行让_run_inference返回[]，最终标记为failed
            if features_array is not None and len(features_array) < MIN_CHUNKS:
                logging.debug(
                    'Skipping file with too few chunks (%d < %d): %s',
                    len(features_array),
                    MIN_CHUNKS,
                    file_info.absolute_path,
                )
                # 返回特殊标记，表示跳过（使用None表示skip，与"没有数据"区分）
                return file_info, None, None
        except Exception as e:
            error_msg = f'Failed to extract features: {str(e)}'
            logging.error('Error extracting features from %s: %s', file_info.absolute_path, e)
            return file_info, [], error_msg

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

        try:
            if self.timeout is None:
                # No timeout, run normally
                result = self._run_inference(file_info)
                return file_info, result, None
            # Use ThreadPoolExecutor with timeout for cross-platform compatibility
            from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
            from concurrent.futures import TimeoutError as FutureTimeoutError  # noqa: PLC0415

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_inference, file_info)
                try:
                    result = future.result(timeout=self.timeout)
                    return file_info, result, None
                except FutureTimeoutError:
                    error_msg = f'Analysis timeout after {self.timeout} seconds'
                    logging.warning('File analysis timeout after %d seconds: %s', self.timeout, file_info.absolute_path)
                    # Cancel the future if possible
                    future.cancel()
                    return file_info, [], error_msg
        except Exception as e:
            error_msg = f'Analysis error: {str(e)}'
            logging.error('Error analyzing file %s: %s', file_info.absolute_path, e)
            return file_info, [], error_msg

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
            for file_info, flags, error_reason in results:
                flags_path = os.path.join(FileInfo.CACHE_DIR, f'flags_{file_info.file_id}.csv')
                error_path = os.path.join(FileInfo.CACHE_DIR, f'error_{file_info.file_id}.txt')

                if flags is None:
                    # 跳过预测（chunk数量太少），创建skip标记文件
                    with open(flags_path, 'w', encoding='UTF-8') as f:
                        f.write('file,prediction,confidence\n')
                        f.write(f'{file_info.file_id},skip,0.0\n')
                elif flags:
                    # 正常预测结果
                    with open(flags_path, 'w', encoding='UTF-8') as f:
                        f.write('file,prediction,confidence\n')
                        for pred, conf in flags:
                            f.write(f'{file_info.file_id},{pred},{conf}\n')
                # 如果flags是空列表[]，表示没有数据或失败
                if error_reason:
                    # 保存失败原因
                    with open(error_path, 'w', encoding='UTF-8') as f:
                        f.write(error_reason)
                elif not flags and flags is not None and not os.path.exists(error_path):
                    # 没有数据但没有错误信息，这种情况不应该发生（应该在 _run_analysis 中已经捕获）
                    # 但为了安全起见，仍然尝试提取失败原因
                    try:
                        text_data = file_info.extract_dot_text()
                        if not text_data:
                            # 检查文件类型
                            if file_info.file_type.value == 0xFF:  # NOT_SUPPORT
                                fallback_error_reason = 'File type not supported (not .so or .a)'
                            else:
                                fallback_error_reason = 'No .text section found in ELF file'
                        else:
                            fallback_error_reason = 'Unknown error: extracted data is empty'
                        with open(error_path, 'w', encoding='UTF-8') as f:
                            f.write(fallback_error_reason)
                    except Exception as e:
                        fallback_error_reason = f'Failed to extract .text section: {str(e)}'
                        with open(error_path, 'w', encoding='UTF-8') as f:
                            f.write(fallback_error_reason)

        flags_results = {}
        files_with_results = 0
        for file_info in file_infos:
            flags_path = os.path.join(FileInfo.CACHE_DIR, f'flags_{file_info.file_id}.csv')
            error_path = os.path.join(FileInfo.CACHE_DIR, f'error_{file_info.file_id}.txt')

            # 读取失败原因（如果存在）
            error_reason = None
            if os.path.exists(error_path):
                try:
                    with open(error_path, encoding='UTF-8') as f:
                        error_reason = f.read().strip()
                except Exception:
                    pass

            if os.path.exists(flags_path):
                try:
                    flags_df = pd.read_csv(flags_path)
                    if not flags_df.empty:
                        # 检查是否是skip标记
                        if len(flags_df) == 1 and flags_df.iloc[0]['prediction'] == 'skip':
                            # 跳过预测的文件，标记为skip
                            flags_results[file_info.file_id] = {
                                'prediction': 'skip',
                                'confidence': 0.0,
                                'distribution': {},
                                'opt_score': None,
                                'opt_category': None,
                                'total_chunks': 0,
                                'error_reason': None,
                            }
                            files_with_results += 1
                        else:
                            # 正常预测结果
                            file_results = self._merge_chunk_results(flags_df)
                            for _file_id, result in file_results.items():
                                result['error_reason'] = None
                            flags_results.update(file_results)
                            files_with_results += 1
                except Exception as e:
                    logging.error('Error loading results for %s: %s', file_info.absolute_path, e)
                    if not error_reason:
                        error_reason = f'Error loading results: {str(e)}'

            # 如果没有结果但有错误原因，保存错误信息
            if file_info.file_id not in flags_results and error_reason:
                flags_results[file_info.file_id] = {
                    'prediction': None,
                    'confidence': None,
                    'distribution': {},
                    'opt_score': None,
                    'opt_category': None,
                    'total_chunks': 0,
                    'error_reason': error_reason,
                }

        return files_with_results, len(file_infos) - files_with_results, flags_results

    def _collect_results(
        self, flags_results: dict, file_infos: list[FileInfo], lto_results: Optional[dict] = None
    ) -> pd.DataFrame:
        if lto_results is None:
            lto_results = {}

        report_data = []
        for file_info in sorted(file_infos, key=lambda x: x.logical_path):
            result = flags_results.get(file_info.file_id)
            error_reason = None
            if result is None:
                status = FILE_STATUS_MAPPING['failed']
                opt_category = 'N/A'
                opt_score = 'N/A'
                distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
                total_chunks = 0
                size_optimized = 'N/A'
                error_reason = 'No analysis result found'
            elif result.get('prediction') == 'skip':
                # 跳过预测的文件（chunk数量太少）
                status = FILE_STATUS_MAPPING['skipped_few_chunks']
                opt_category = 'N/A'
                opt_score = 'N/A'
                distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
                total_chunks = 0
                size_optimized = 'N/A'
                error_reason = None
            elif result.get('error_reason'):
                # 有错误原因
                status = FILE_STATUS_MAPPING['failed']
                opt_category = 'N/A'
                opt_score = 'N/A'
                distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
                total_chunks = 0
                size_optimized = 'N/A'
                error_reason = result.get('error_reason')
            else:
                status = FILE_STATUS_MAPPING['analyzed']
                opt_category = result['opt_category']
                opt_score = result['opt_score']
                distribution = result['distribution']
                total_chunks = result['total_chunks']
                os_chunks = distribution.get(4, 0)
                os_ratio = os_chunks / total_chunks if total_chunks > 0 else 0
                size_optimized = f'{"Yes" if os_ratio >= 0.5 else "No"} ({os_ratio:.1%})'
                error_reason = None

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
                'Failure Reason': error_reason if error_reason else 'N/A',
            }

            # 添加LTO检测列
            if lto_results and file_info.file_id in lto_results:
                lto_result = lto_results[file_info.file_id]
                row['LTO Score'] = f'{lto_result["score"]:.4f}' if lto_result['score'] is not None else 'N/A'
                row['LTO Prediction'] = lto_result['prediction']
            elif self.enable_lto:
                row['LTO Score'] = 'N/A'
                row['LTO Prediction'] = 'N/A'

            report_data.append(row)
        return pd.DataFrame(report_data)
