"""
LTO (Link-Time Optimization) Detector
基于SVM的LTO检测器，封装lto_demo的功能供opt指令使用
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import joblib
except ImportError:
    import pickle as joblib  # 降级到pickle（如果joblib不可用）


class LtoDetector:
    """
    LTO检测器

    功能：
    - 检测SO文件是否使用了LTO优化
    - 根据优化级别自动选择合适的模型
    - 返回LTO分数和判定结果
    """

    # 模型映射：优化级别 -> 使用的模型
    MODEL_MAPPING = {
        'O0': 'O2',  # O0使用O2模型
        'O1': 'O2',  # O1使用O2模型
        'O2': 'O2',  # O2使用专用模型
        'O3': 'O3',  # O3使用专用模型
        'Os': 'Os',  # Os使用专用模型
        'Mixed': 'O2',  # Mixed使用O2模型
        None: 'O2',  # 未知级别使用O2模型
    }

    def __init__(self, model_base_dir: Optional[Path] = None):
        """
        初始化LTO检测器

        Args:
            model_base_dir: 模型目录，默认为package内的models/lto/
        """
        if model_base_dir is None:
            # 默认模型目录
            try:
                from importlib.resources import files  # noqa: PLC0415

                model_base_dir = files('hapray.optimization_detector').joinpath('models/lto')
            except Exception:  # noqa: S110
                # 备选：相对路径
                model_base_dir = Path(__file__).parent / 'models' / 'lto'

        self.model_base_dir = Path(model_base_dir)
        self.models = {}  # 缓存已加载的模型
        self.feature_extractors = {}  # 缓存特征提取器

        # 导入特征提取器
        self._import_feature_extractor()

    def _import_feature_extractor(self):
        """导入特征提取器和SVM类（pickle反序列化需要）"""
        try:
            # 直接导入同一目录下的lto_feature_pipeline模块
            from .lto_feature_pipeline import (  # noqa: PLC0415
                CompilerProvenanceRF,  # 新的RF模型
                CompilerProvenanceSVM,  # 旧的SVM模型
                HybridFeatureExtractor,  # 混合特征提取（RF用）
                LegacyFeatureExtractor,  # Legacy特征提取（SVM用）
            )

            self.LegacyFeatureExtractor = LegacyFeatureExtractor
            self.HybridFeatureExtractor = HybridFeatureExtractor
            self.CompilerProvenanceSVM = CompilerProvenanceSVM
            self.CompilerProvenanceRF = CompilerProvenanceRF
            logging.debug('Successfully imported from lto_feature_pipeline')

        except ImportError as e:
            logging.error('Failed to import lto_feature_pipeline: %s', e)
            self.LegacyFeatureExtractor = None
            self.HybridFeatureExtractor = None
            self.CompilerProvenanceSVM = None
            self.CompilerProvenanceRF = None

    def _load_model(self, model_name: str) -> tuple[Optional[object], Optional[list], Optional[str]]:
        """
        加载指定的模型（SVM或RF）

        Args:
            model_name: 模型名称 (O2/O3/Os)

        Returns:
            (model, feature_names, model_type) 或 (None, None, None)
        """
        if model_name in self.models:
            return self.models[model_name]

        model_dir = self.model_base_dir / model_name

        # 优先使用RF模型（最新），回退到SVM模型
        rf_path = model_dir / 'rf_model.joblib'
        svm_path = model_dir / 'svm_model.joblib'
        feature_path = model_dir / 'feature_names.json'

        # 确定使用哪个模型
        if rf_path.exists():
            model_path = rf_path
            model_type = 'RF'
            model_class = self.CompilerProvenanceRF
        elif svm_path.exists():
            model_path = svm_path
            model_type = 'SVM'
            model_class = self.CompilerProvenanceSVM
        else:
            logging.warning('LTO model not found: %s', model_dir)
            return None, None

        if not feature_path.exists():
            logging.warning('Feature names not found: %s', feature_path)
            return None, None, None

        try:
            # 确保模型类已导入（pickle反序列化需要）
            if model_class is None:
                logging.error('%s model class not imported, cannot load model', model_type)
                return None, None, None

            # 将模型类添加到全局命名空间（pickle需要）
            import builtins  # noqa: PLC0415

            if model_type == 'RF':
                if not hasattr(builtins, 'CompilerProvenanceRF'):
                    builtins.CompilerProvenanceRF = self.CompilerProvenanceRF
                # 同时添加到主模块，因为pickle可能从那里查找
                if hasattr(sys.modules.get('__main__'), '__dict__'):
                    sys.modules['__main__'].CompilerProvenanceRF = self.CompilerProvenanceRF
                if hasattr(sys.modules.get('scripts.main'), '__dict__'):
                    sys.modules['scripts.main'].CompilerProvenanceRF = self.CompilerProvenanceRF
            elif model_type == 'SVM':
                if not hasattr(builtins, 'CompilerProvenanceSVM'):
                    builtins.CompilerProvenanceSVM = self.CompilerProvenanceSVM
                if hasattr(sys.modules.get('__main__'), '__dict__'):
                    sys.modules['__main__'].CompilerProvenanceSVM = self.CompilerProvenanceSVM
                if hasattr(sys.modules.get('scripts.main'), '__dict__'):
                    sys.modules['scripts.main'].CompilerProvenanceSVM = self.CompilerProvenanceSVM

            # 加载模型
            model = joblib.load(model_path)
            logging.info('Loaded %s model for %s', model_type, model_name)

            # 加载特征名称
            with open(feature_path, encoding='utf-8') as f:
                feature_names = json.load(f).get('feature_names', [])

            # 缓存模型（包含类型信息）
            self.models[model_name] = (model, feature_names, model_type)
            logging.debug('Loaded %s model %s: %d features', model_type, model_name, len(feature_names))

            return model, feature_names, model_type

        except Exception as e:
            logging.error('Failed to load LTO model %s: %s', model_name, e)
            return None, None, None

    def _extract_features(self, so_path: str, feature_names: list, use_hybrid: bool = False) -> Optional[np.ndarray]:
        """
        提取SO文件的特征

        Args:
            so_path: SO文件路径
            feature_names: 训练时的特征名称列表
            use_hybrid: 是否使用混合特征提取器（RF模型需要）

        Returns:
            特征向量 或 None
        """
        # 根据模型类型选择特征提取器
        if use_hybrid:
            if self.HybridFeatureExtractor is None:
                logging.error('HybridFeatureExtractor not available')
                return None
            extractor_key = 'hybrid'
            ExtractorClass = self.HybridFeatureExtractor
        else:
            if self.LegacyFeatureExtractor is None:
                logging.error('LegacyFeatureExtractor not available')
                return None
            extractor_key = 'legacy'
            ExtractorClass = self.LegacyFeatureExtractor

        try:
            # 创建或获取特征提取器
            if extractor_key not in self.feature_extractors:
                self.feature_extractors[extractor_key] = ExtractorClass()

            extractor = self.feature_extractors[extractor_key]

            # 提取特征
            feat, names, _ = extractor.extract(so_path)

            # 对齐到训练时的特征名称
            name_to_index = {n: i for i, n in enumerate(feature_names)}
            vec = np.zeros(len(feature_names), dtype=np.float32)

            for i, n in enumerate(names):
                j = name_to_index.get(n)
                if j is not None:
                    vec[j] = float(feat[i])

            return vec

        except Exception as e:
            logging.debug('Feature extraction failed for %s: %s', so_path, e)
            return None

    def detect(self, so_path: str, opt_level: Optional[str] = None) -> dict:
        """
        检测单个SO文件是否使用LTO

        Args:
            so_path: SO文件路径
            opt_level: 优化级别 (O0/O1/O2/O3/Os/Mixed/None)
                      如果为None，将使用集成预测（所有模型）

        Returns:
            {
                'score': float,      # LTO分数 [0-1]
                'prediction': str,   # 'LTO' 或 'No LTO'
                'model_used': str    # 使用的模型名称
            }
        """
        # 如果优化级别未知，使用集成预测
        if opt_level is None or opt_level not in self.MODEL_MAPPING:
            return self._detect_with_ensemble(so_path)

        # 选择模型
        model_name = self.MODEL_MAPPING.get(opt_level, 'O2')
        model, feature_names, model_type = self._load_model(model_name)

        if model is None or feature_names is None:
            return {'score': None, 'prediction': 'N/A', 'model_used': 'N/A'}

        # 根据模型类型选择特征提取器
        use_hybrid = model_type == 'RF'

        # 提取特征
        features = self._extract_features(so_path, feature_names, use_hybrid=use_hybrid)

        if features is None:
            return {'score': None, 'prediction': 'Failed', 'model_used': model_name}

        try:
            # 预测
            features_2d = features.reshape(1, -1)  # 转为2D数组
            proba = model.predict_proba(features_2d)
            lto_score = float(proba[0, 1])  # 第二列是LTO的概率
            lto_label = 1 if lto_score >= 0.5 else 0

            return {'score': lto_score, 'prediction': 'LTO' if lto_label == 1 else 'No LTO', 'model_used': model_name}

        except Exception as e:
            logging.debug('LTO prediction failed for %s: %s', so_path, e)
            return {'score': None, 'prediction': 'Error', 'model_used': model_name}

    def _detect_with_ensemble(self, so_path: str) -> dict:
        """
        使用集成预测（当优化级别未知时）

        策略：用O2/O3/Os三个模型都预测，取加权平均
        权重：O2=0.5, O3=0.3, Os=0.2（基于实际使用频率）

        Args:
            so_path: SO文件路径

        Returns:
            集成预测结果
        """
        logging.debug('Using ensemble prediction for %s', so_path)

        models_to_use = ['O2', 'O3', 'Os']
        weights = {'O2': 0.5, 'O3': 0.3, 'Os': 0.2}  # 根据实际使用频率

        scores = []
        valid_models = []

        for model_name in models_to_use:
            model, feature_names, model_type = self._load_model(model_name)
            if model is None or feature_names is None:
                continue

            # 根据模型类型选择特征提取器
            use_hybrid = model_type == 'RF'
            features = self._extract_features(so_path, feature_names, use_hybrid=use_hybrid)
            if features is None:
                continue

            try:
                features_2d = features.reshape(1, -1)
                proba = model.predict_proba(features_2d)
                score = float(proba[0, 1])
                scores.append((model_name, score))
                valid_models.append(model_name)
            except Exception as e:
                logging.debug('Ensemble prediction failed for model %s: %s', model_name, e)
                continue

        if not scores:
            return {'score': None, 'prediction': 'Failed', 'model_used': 'Ensemble(failed)'}

        # 计算加权平均
        weighted_score = sum(weights[m] * s for m, s in scores) / sum(weights[m] for m in valid_models)

        # 取最高分（作为参考）
        max_score = max(s for _, s in scores)
        max_model = [m for m, s in scores if s == max_score][0]

        # 使用加权平均作为最终分数
        final_score = weighted_score
        lto_label = 1 if final_score >= 0.5 else 0

        model_str = f'Ensemble({"+".join(valid_models)})'

        logging.debug('Ensemble scores: %s, weighted=%.4f, max=%.4f(%s)', scores, weighted_score, max_score, max_model)

        return {'score': final_score, 'prediction': 'LTO' if lto_label == 1 else 'No LTO', 'model_used': model_str}
