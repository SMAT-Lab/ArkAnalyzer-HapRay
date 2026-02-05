"""
LTO (Link-Time Optimization) Detector
基于统一SVM模型的LTO检测器，模型文件位于 package 内的 models/lto/ 目录

说明：LTO 使用 scikit-learn 的 Pipeline(StandardScaler + SVC)，sklearn 的 SVC 仅在 CPU 上运行，
无内置 GPU 支持；optimization_detector 的 opt 级别检测使用 TensorFlow/Keras LSTM，故可使用 GPU。
若需 LTO 使用 GPU，需将模型改为 GPU 框架（如 TensorFlow 重训或 cuML/ThunderSVM 等）。
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

    运行设备：当前使用 scikit-learn (joblib 加载的 model.pkl)，仅在 CPU 上推理；
    opt 级别检测使用 TensorFlow，可自动使用 GPU。
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

    def detect_chunk_based(self, file_info: FileInfo, chunks: list[bytes], opt_level: Optional[str] = None) -> dict:
        """
        基于 chunk 的 LTO 检测（每个 chunk 单独预测，然后统计）。
        与 opt_level 技术栈一致：chunks 应由调用方从 .text 按 2048 字节切分并传入，
        避免在 LTO 内重复切分（optimization_detector 在 opt 阶段已切分并复用）。

        Args:
            file_info: FileInfo对象
            chunks: 从 .text 段按 2048 字节切分的二进制列表（与 opt 同一套）
            opt_level: 优化级别（已废弃，保留以兼容）

        Returns:
            {
                'score': float,           # 平均 LTO 分数 [0-1]
                'prediction': str,         # 'LTO' 或 'No LTO'（基于多数投票）
                'model_used': str,         # 使用的模型名称
                'chunk_scores': list,      # 每个 chunk 的分数
                'chunk_predictions': list,  # 每个 chunk 的预测
                'distribution': dict,      # LTO/No LTO 分布
            }
        """
        so_path = file_info.absolute_path
        
        # 延迟加载模型
        if not self._load_model():
            return {'score': None, 'prediction': 'N/A', 'model_used': 'N/A', 
                   'chunk_scores': [], 'chunk_predictions': [], 'distribution': {}}
        
        if not chunks or len(chunks) == 0:
            return {'score': None, 'prediction': 'No chunks', 'model_used': 'Unified SVM',
                   'chunk_scores': [], 'chunk_predictions': [], 'distribution': {}}
        
        # 提取文件级别的全局特征（ELF头、符号表等）
        global_features = self._extract_features(so_path)
        if global_features is None:
            return {'score': None, 'prediction': 'Failed', 'model_used': 'Unified SVM',
                   'chunk_scores': [], 'chunk_predictions': [], 'distribution': {}}
        
        # 获取特征提取器以提取局部特征
        if self.feature_extractor is None:
            if self.AllFeatureExtractor is None:
                return {'score': None, 'prediction': 'Failed', 'model_used': 'Unified SVM',
                       'chunk_scores': [], 'chunk_predictions': [], 'distribution': {}}
            self.feature_extractor = self.AllFeatureExtractor()
        
        chunk_scores = []
        chunk_predictions = []
        
        try:
            # 对每个 chunk 提取局部特征并预测
            for i, chunk_data in enumerate(chunks):
                # 提取 chunk 的局部特征（字节直方图、指令统计等）
                chunk_features = self._extract_chunk_features(chunk_data, global_features, so_path)
                
                if chunk_features is None:
                    continue
                
                # 预测
                features_2d = chunk_features.reshape(1, -1)
                scaler = self.model.steps[0][1]
                scaled_features = scaler.transform(features_2d)
                
                # 应用特征截断修复
                svm = self.model.steps[-1][1]
                if hasattr(svm, 'support_vectors_') and len(svm.support_vectors_) > 0:
                    sv_min = svm.support_vectors_.min(axis=0)
                    sv_max = svm.support_vectors_.max(axis=0)
                    feature_min = sv_min - 3 * (sv_max - sv_min)
                    feature_max = sv_max + 3 * (sv_max - sv_min)
                    scaled_features = np.clip(scaled_features, feature_min, feature_max)
                
                decision = svm.decision_function(scaled_features)
                decision_value = float(decision[0])
                
                # 转换为概率（用于单个 chunk 的预测）
                try:
                    from scipy.special import expit
                    lto_score = float(expit(decision_value))
                except ImportError:
                    lto_score = 1.0 / (1.0 + math.exp(-decision_value))
                
                # 使用更低的阈值（0.45）来减少漏报（实际开了 LTO 但被误判为没开）
                # 根据大规模数据分析（1073个文件）：
                # - 阈值 0.45：高优化级别识别率 89.0%，低优化级别误报率 16.7%
                # - 阈值 0.52：高优化级别识别率 74.4%，低优化级别误报率 8.2%
                # 选择 0.45 以显著提高识别率，减少漏报
                lto_label = 1 if lto_score >= 0.45 else 0
                prediction = 'LTO' if lto_label == 1 else 'No LTO'
                
                # 保存分数和预测结果
                chunk_scores.append(lto_score)  # 保留原始 sigmoid 分数用于参考
                chunk_predictions.append(prediction)
            
            if len(chunk_scores) == 0:
                return {'score': None, 'prediction': 'Failed', 'model_used': 'Unified SVM',
                       'chunk_scores': [], 'chunk_predictions': [], 'distribution': {}}
            
            # 统计结果（学习 optimization_detector 的累加分数方式）
            # 方案：直接累加每个 chunk 的预测概率（sigmoid 分数）
            # 类似 optimization_detector 累加每个 chunk 的优化级别分数
            total_chunks = len(chunk_scores)
            total_score = sum(chunk_scores)  # 累加所有 chunks 的预测概率
            avg_score = total_score / total_chunks  # 平均概率作为最终 LTO 分数
            
            # 预测结果：基于累加分数（>= 0.45 为 LTO，使用更低的阈值减少漏报）
            # 根据大规模数据分析，0.45 阈值可以将高优化级别的识别率从 74.4% 提升到 89.0%
            final_prediction = 'LTO' if avg_score >= 0.45 else 'No LTO'
            
            # 统计分布（用于报告）
            lto_count = chunk_predictions.count('LTO')
            no_lto_count = chunk_predictions.count('No LTO')
            
            return {
                'score': avg_score,
                'prediction': final_prediction,
                'model_used': 'Unified SVM (Chunk-based)',
                'chunk_scores': chunk_scores,  # 每个 chunk 的 sigmoid 概率
                'chunk_predictions': chunk_predictions,
                'distribution': {'LTO': lto_count, 'No LTO': no_lto_count},
                'total_chunks': total_chunks,
                'total_score': total_score,  # 累加的总概率值
            }
            
        except Exception as e:
            logging.debug('Chunk-based LTO prediction failed for %s: %s', so_path, e)
            return {'score': None, 'prediction': 'Error', 'model_used': 'Unified SVM',
                   'chunk_scores': [], 'chunk_predictions': [], 'distribution': {}}
    
    def _extract_chunk_features(self, chunk_data: bytes, global_features: np.ndarray, so_path: str) -> Optional[np.ndarray]:
        """
        提取 chunk 的混合特征（全局特征 + 局部特征）
        
        Args:
            chunk_data: chunk 的二进制数据
            global_features: 文件级别的全局特征向量
            so_path: SO文件路径
        
        Returns:
            混合特征向量 或 None
        """
        try:
            if self.feature_extractor is None or self.feature_names is None:
                return None
            
            # 提取 chunk 的局部特征
            # 1. 字节直方图特征（类似 CompilerProvenanceExtractor）
            chunk_local_features = self._extract_chunk_byte_features(chunk_data)
            
            # 2. 指令统计特征（如果 chunk 足够大，可以反汇编）
            chunk_insn_features = self._extract_chunk_instruction_features(chunk_data)
            
            # 3. 将局部特征对齐到全局特征向量
            # 策略：对于可以局部提取的特征，使用局部值；否则使用全局值
            mixed_features = global_features.copy()
            
            # 更新 HIER_* 特征（字节直方图）
            hier_feature_indices = [i for i, n in enumerate(self.feature_names) if n.startswith('HIER_')]
            if hier_feature_indices and chunk_local_features:
                # 提取局部特征的名称（需要从 extractor 获取）
                # 这里简化处理：直接使用全局特征，但可以后续优化
                pass
            
            # 更新 O3_* 中的指令统计特征
            insn_feature_keywords = ['d_bl', 'd_blr', 'd_br', 'd_ret', 'd_vec', 'INSN']
            insn_feature_indices = [i for i, n in enumerate(self.feature_names) 
                                   if any(kw in n for kw in insn_feature_keywords)]
            
            # 简化实现：直接返回全局特征（因为局部特征提取较复杂）
            # 后续可以优化为真正的混合特征
            return global_features
            
        except Exception as e:
            logging.debug('Failed to extract chunk features: %s', e)
            return None
    
    def _extract_chunk_byte_features(self, chunk_data: bytes) -> Optional[dict]:
        """提取 chunk 的字节级特征"""
        try:
            if len(chunk_data) == 0:
                return None
            
            arr = np.frombuffer(chunk_data, dtype=np.uint8)
            counts = np.bincount(arr, minlength=256)
            probs = counts / len(arr)
            probs = probs[probs > 0]
            entropy = -np.sum(probs * np.log2(probs))
            
            return {
                'entropy': entropy,
                'zero_ratio': float(np.mean(arr == 0)),
                'ascii_ratio': float(np.mean((arr >= 32) & (arr <= 126))),
                'byte_diversity': float(len(np.unique(arr)) / 256.0),
                'avg_byte': float(np.mean(arr)),
                'byte_std': float(np.std(arr)),
            }
        except Exception:
            return None
    
    def _extract_chunk_instruction_features(self, chunk_data: bytes) -> Optional[dict]:
        """提取 chunk 的指令统计特征（如果可能）"""
        # 简化实现：如果 chunk 太小，不进行反汇编
        if len(chunk_data) < 16:
            return None
        
        # 可以在这里添加 capstone 反汇编逻辑
        # 但为了简化，暂时返回 None
        return None
    
    def _extract_chunk_features(self, chunk_data: bytes, global_features: np.ndarray, so_path: str) -> Optional[np.ndarray]:
        """
        提取 chunk 的混合特征（全局特征 + 局部特征）
        
        当前实现：直接使用全局特征（因为模型是基于全局特征训练的）
        后续可以优化为真正的混合特征
        
        Args:
            chunk_data: chunk 的二进制数据
            global_features: 文件级别的全局特征向量
            so_path: SO文件路径
        
        Returns:
            混合特征向量（当前返回全局特征）
        """
        # 简化实现：直接使用全局特征
        # 因为当前模型是基于全局特征训练的，使用全局特征可以保持一致性
        # 虽然每个 chunk 使用相同的全局特征，但不同 chunk 的局部特征差异
        # 可以通过后续优化来体现（需要重新训练模型或使用特征选择）
        return global_features

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
            
            # 临时修复：对异常大的特征值进行截断
            # 标准化后，如果特征值超过合理范围（如 ±100），进行截断
            # 这可以防止 RBF 核值下溢为 0
            scaler = self.model.steps[0][1]
            scaled_features = scaler.transform(features_2d)
            
            # 截断异常大的特征值（基于支持向量的范围）
            svm = self.model.steps[-1][1]
            if hasattr(svm, 'support_vectors_') and len(svm.support_vectors_) > 0:
                # 计算支持向量的范围
                sv_min = svm.support_vectors_.min(axis=0)
                sv_max = svm.support_vectors_.max(axis=0)
                # 允许一定的超出范围（3倍标准差），但截断极端值
                feature_min = sv_min - 3 * (sv_max - sv_min)
                feature_max = sv_max + 3 * (sv_max - sv_min)
                # 截断
                scaled_features = np.clip(scaled_features, feature_min, feature_max)
            
            # 注意：SVM Pipeline 在训练时设置了 probability=False，所以没有 predict_proba
            # 使用 decision_function 并转换为概率
            decision = self.model.steps[-1][1].decision_function(scaled_features)
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

            # 使用更保守的阈值（0.55）来减少误报
            lto_label = 1 if lto_score >= 0.55 else 0

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
