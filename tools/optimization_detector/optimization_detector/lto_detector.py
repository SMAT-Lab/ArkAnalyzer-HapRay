"""
LTO (Link-Time Optimization) Detector
基于统一SVM模型的LTO检测器，模型文件位于 package 内的 models/lto/ 目录
"""

import json
import logging
import math
import traceback
from pathlib import Path
from typing import Optional

import numpy as np

from optimization_detector.file_info import FileInfo

try:
    import joblib
except ImportError:
    import pickle as joblib  # 降级到pickle（如果joblib不可用）


class LtoDetector:
    """
    LTO检测器

    功能：
    - 检测SO文件是否使用了LTO优化
    - 使用统一的SVM模型（不区分优化级别）
    - 返回LTO分数和判定结果
    """

    def __init__(self, model_dir: Optional[Path] = None):
        """
        初始化LTO检测器

        Args:
            model_dir: 统一模型目录，默认为 package 内的 models/lto/
        """
        if model_dir is None:
            # 默认模型目录（在 package 内）
            try:
                from importlib.resources import files  # noqa: PLC0415

                model_dir = files('optimization_detector').joinpath('models/lto')
            except Exception:  # noqa: S110
                # 备选：相对路径
                model_dir = Path(__file__).parent / 'models' / 'lto'

        self.model_dir = Path(model_dir)
        self.model = None  # 统一模型（延迟加载）
        self.feature_names = None  # 特征名称列表
        self.feature_extractor = None  # 特征提取器（延迟创建）

        # 导入特征提取器
        self._import_feature_extractor()

    def _import_feature_extractor(self):
        """导入AllFeatureExtractor（统一模型使用的特征提取器）"""
        try:
            # 从同一目录下的 lto_feature_pipeline 导入（git 仓库内）
            from .lto_feature_pipeline import AllFeatureExtractor  # noqa: PLC0415

            self.AllFeatureExtractor = AllFeatureExtractor
            logging.debug('Successfully imported AllFeatureExtractor from local lto_feature_pipeline')

        except Exception as e:  # noqa: BLE001
            # 捕获所有异常，包括 ImportError 和其他可能的错误（如依赖缺失）
            error_msg = f'Failed to import AllFeatureExtractor: {e}\n{traceback.format_exc()}'
            logging.error(error_msg)
            self.AllFeatureExtractor = None

    def _load_model(self):
        """
        加载统一的SVM模型（延迟加载）

        Returns:
            True 如果成功加载，False 否则
        """
        if self.model is not None:
            return True  # 已经加载

        model_path = self.model_dir / 'model.pkl'
        feature_path = self.model_dir / 'feature_names.json'

        if not model_path.exists():
            logging.warning('LTO model not found: %s', model_path)
            return False

        if not feature_path.exists():
            logging.warning('Feature names not found: %s', feature_path)
            return False

        try:
            # 加载模型（Pipeline，包含 StandardScaler 和 SVC）
            self.model = joblib.load(model_path)
            logging.info('Loaded unified LTO SVM model from %s', model_path)

            # 加载特征名称
            with open(feature_path, encoding='utf-8') as f:
                self.feature_names = json.load(f).get('feature_names', [])

            if not self.feature_names:
                logging.warning('No feature names found in %s', feature_path)
                return False

            logging.debug('Loaded unified LTO model: %d features', len(self.feature_names))
            return True

        except Exception as e:
            logging.error('Failed to load LTO model: %s', e)
            self.model = None
            self.feature_names = None
            return False

    def _extract_features(self, so_path: str) -> Optional[np.ndarray]:
        """
        提取SO文件的特征（使用AllFeatureExtractor）

        Args:
            so_path: SO文件路径

        Returns:
            特征向量 或 None
        """
        if self.AllFeatureExtractor is None:
            logging.error('AllFeatureExtractor not available')
            return None

        if self.feature_names is None:
            logging.error('Feature names not loaded')
            return None

        try:
            # 创建或获取特征提取器
            if self.feature_extractor is None:
                self.feature_extractor = self.AllFeatureExtractor()

            # 提取特征
            feat, names, _ = self.feature_extractor.extract(so_path)

            # 对齐到训练时的特征名称
            name_to_index = {n: i for i, n in enumerate(self.feature_names)}
            vec = np.zeros(len(self.feature_names), dtype=np.float32)

            matched_count = 0
            for i, n in enumerate(names):
                j = name_to_index.get(n)
                if j is not None:
                    vec[j] = float(feat[i])
                    matched_count += 1

            if matched_count == 0:
                logging.warning(
                    'No features matched for %s. Extracted %d features, expected %d',
                    so_path,
                    len(names),
                    len(self.feature_names),
                )
                return None

            return vec

        except Exception as e:
            logging.debug('Feature extraction failed for %s: %s', so_path, e)
            return None

    def detect(self, file_info: FileInfo, opt_level: Optional[str] = None) -> dict:
        """
        检测单个SO文件是否使用LTO（使用统一模型，opt_level参数已废弃但保留以兼容）

        Args:
            file_info: FileInfo对象，包含文件路径、ID和哈希等信息
            opt_level: 优化级别（已废弃，统一模型不区分优化级别，保留以兼容旧代码）

        Returns:
            {
                'score': float,      # LTO分数 [0-1]
                'prediction': str,   # 'LTO' 或 'No LTO'
                'model_used': str    # 使用的模型名称（统一SVM）
            }
        """
        so_path = file_info.absolute_path

        # 尝试从缓存读取
        cache_result = self._load_from_cache(file_info)
        if cache_result is not None:
            logging.debug('LTO cache hit for %s', so_path)
            return cache_result

        # 延迟加载模型
        if not self._load_model():
            return {'score': None, 'prediction': 'N/A', 'model_used': 'N/A'}

        # 提取特征
        features = self._extract_features(so_path)
        if features is None:
            return {'score': None, 'prediction': 'Failed', 'model_used': 'Unified SVM'}

        try:
            # 预测（模型是 Pipeline，包含 StandardScaler 和 SVC）
            features_2d = features.reshape(1, -1)  # 转为2D数组

            # 注意：SVM Pipeline 在训练时设置了 probability=False，所以没有 predict_proba
            # 使用 decision_function 并转换为概率
            decision = self.model.decision_function(features_2d)
            decision_value = float(decision[0])

            # 将 decision_function 转换为概率 [0, 1]
            # 使用 sigmoid 函数：1 / (1 + exp(-decision))
            # 如果 scipy 可用，使用 expit；否则手动计算
            try:
                from scipy.special import expit  # noqa: PLC0415

                lto_score = float(expit(decision_value))
            except ImportError:
                # 如果没有 scipy，手动计算 sigmoid
                lto_score = 1.0 / (1.0 + math.exp(-decision_value))

            lto_label = 1 if lto_score >= 0.5 else 0

            result = {
                'score': lto_score,
                'prediction': 'LTO' if lto_label == 1 else 'No LTO',
                'model_used': 'Unified SVM',
            }

            # 保存到缓存
            self._save_to_cache(file_info, result)

            return result

        except Exception as e:
            logging.debug('LTO prediction failed for %s: %s', so_path, e)
            return {'score': None, 'prediction': 'Error', 'model_used': 'Unified SVM'}

    def _get_cache_path(self, file_info: FileInfo) -> Path:
        """
        获取缓存文件路径

        Args:
            file_info: FileInfo对象，包含文件ID和哈希等信息

        Returns:
            缓存文件路径
        """
        cache_dir = Path(FileInfo.CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_filename = f'lto_{file_info.file_id}_{file_info.file_hash}.json'
        return cache_dir / cache_filename

    def _load_from_cache(self, file_info: FileInfo) -> Optional[dict]:
        """
        从缓存加载LTO检测结果

        Args:
            file_info: FileInfo对象，包含文件ID和哈希等信息

        Returns:
            检测结果字典，如果缓存不存在则返回 None
        """
        cache_path = self._get_cache_path(file_info)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, encoding='utf-8') as f:
                result = json.load(f)
            # 统一模型：确保 model_used 始终为 "Unified SVM"（兼容旧缓存）
            if result.get('model_used') != 'Unified SVM':
                result['model_used'] = 'Unified SVM'
            logging.debug('Loaded LTO cache from %s', cache_path)
            return result
        except Exception as e:
            logging.warning('Failed to load LTO cache from %s: %s', cache_path, e)
            return None

    def _save_to_cache(self, file_info: FileInfo, result: dict) -> None:
        """
        保存LTO检测结果到缓存

        Args:
            file_info: FileInfo对象，包含文件ID和哈希等信息
            result: 检测结果字典
        """
        cache_path = self._get_cache_path(file_info)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logging.debug('Saved LTO cache to %s', cache_path)
        except Exception as e:
            logging.warning('Failed to save LTO cache to %s: %s', cache_path, e)
