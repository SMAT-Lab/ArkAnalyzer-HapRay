"""
配置管理器 - 管理卡顿帧分析相关的配置

Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0
"""

import contextlib
import logging
import os
from typing import Any, Optional

import yaml


class FrameAnalysisConfig:
    """帧分析配置管理器

    负责加载和管理卡顿帧分析的各种配置参数，支持：
    1. YAML配置文件加载
    2. 环境变量覆盖
    3. 默认值设置
    4. 配置验证
    """

    # 默认配置
    DEFAULT_CONFIG = {
        'frame_analysis': {
            'stuttered_frames': {
                'top_n_analysis': 10,
                'enable_lightweight_mode': True,
                'severity_scoring': {
                    'level_weights': {'level_1': 10, 'level_2': 50, 'level_3': 100},
                    'exceed_frames_weight': 5.0,
                    'exceed_time_weight': 0.1,
                },
            },
            'empty_frames': {'enabled': True, 'timeout': 300},
            'frame_loads': {'fast_mode_enabled': True, 'timeout': 600},
        },
        'performance': {
            'database': {'connection_timeout': 30, 'query_timeout': 120},
            'memory': {'optimize_memory_usage': True, 'large_database_threshold': 500, 'huge_database_threshold': 1000},
        },
        'logging': {'enable_performance_logs': True, 'enable_optimization_logs': True, 'slow_query_threshold': 10.0},
        'cache': {'enable_preload': False, 'expire_time': 3600, 'auto_cleanup': True},
        'compatibility': {'maintain_backward_compatibility': True, 'default_mode': 'optimized'},
    }

    _instance = None
    _config: dict[str, Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置"""
        self._config = self.DEFAULT_CONFIG.copy()

        # 查找配置文件
        config_file = self._find_config_file()
        if config_file:
            try:
                self._load_from_file(config_file)
                logging.info('已加载配置文件: %s', config_file)
            except Exception as e:
                logging.warning('加载配置文件失败，使用默认配置: %s', str(e))
        else:
            logging.info('未找到配置文件，使用默认配置')

        # 应用环境变量覆盖
        self._apply_env_overrides()

        # 验证配置
        self._validate_config()

    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        # 可能的配置文件路径
        possible_paths = [
            # 当前工作目录
            'config/frame_analysis.yaml',
            'frame_analysis.yaml',
            # 项目根目录
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'frame_analysis.yaml'),
            # 用户配置目录
            os.path.expanduser('~/.hapray/frame_analysis.yaml'),
            # 系统配置目录
            '/etc/hapray/frame_analysis.yaml',
        ]

        for path in possible_paths:
            if os.path.isfile(path):
                return path

        return None

    def _load_from_file(self, config_file: str):
        """从文件加载配置"""
        with open(config_file, encoding='utf-8') as f:
            file_config = yaml.safe_load(f)

        if file_config:
            self._deep_update(self._config, file_config)

    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # 支持通过环境变量覆盖关键配置
        env_mappings = {
            'HAPRAY_TOP_N_ANALYSIS': ['frame_analysis', 'stuttered_frames', 'top_n_analysis'],
            'HAPRAY_ENABLE_LIGHTWEIGHT': ['frame_analysis', 'stuttered_frames', 'enable_lightweight_mode'],
            'HAPRAY_DB_TIMEOUT': ['performance', 'database', 'query_timeout'],
            'HAPRAY_MEMORY_OPTIMIZE': ['performance', 'memory', 'optimize_memory_usage'],
        }

        for env_key, config_path in env_mappings.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                try:
                    # 尝试转换类型
                    if env_value.lower() in ('true', 'false'):
                        env_value = env_value.lower() == 'true'
                    elif env_value.isdigit():
                        env_value = int(env_value)
                    elif '.' in env_value:
                        with contextlib.suppress(ValueError):
                            env_value = float(env_value)

                    # 设置配置值
                    self._set_nested_value(self._config, config_path, env_value)
                    logging.info('应用环境变量覆盖: %s = %s', env_key, env_value)
                except Exception as e:
                    logging.warning('环境变量覆盖失败 %s: %s', env_key, str(e))

    def _validate_config(self):
        """验证配置的有效性"""
        # 验证 top_n_analysis
        top_n = self.get_top_n_analysis()
        if not isinstance(top_n, int) or top_n < 0:
            logging.warning('无效的top_n_analysis值: %s，使用默认值10', top_n)
            self._set_nested_value(self._config, ['frame_analysis', 'stuttered_frames', 'top_n_analysis'], 10)

        # 验证权重值
        weights = self.get_severity_weights()
        for level, weight in weights.items():
            if not isinstance(weight, (int, float)) or weight < 0:
                logging.warning('无效的权重值 %s: %s', level, weight)

    def _deep_update(self, base_dict: dict, update_dict: dict):
        """深度更新字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def _set_nested_value(self, config: dict, path: list, value: Any):
        """设置嵌套配置值"""
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _get_nested_value(self, config: dict, path: list, default: Any = None):
        """获取嵌套配置值"""
        current = config
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    # 配置访问方法
    def get_top_n_analysis(self) -> int:
        """获取TOP N分析数量"""
        return self._get_nested_value(self._config, ['frame_analysis', 'stuttered_frames', 'top_n_analysis'], 10)

    def is_lightweight_mode_enabled(self) -> bool:
        """是否启用轻量级模式"""
        return self._get_nested_value(
            self._config, ['frame_analysis', 'stuttered_frames', 'enable_lightweight_mode'], True
        )

    def get_severity_weights(self) -> dict[str, float]:
        """获取严重程度评分权重"""
        level_weights = self._get_nested_value(
            self._config,
            ['frame_analysis', 'stuttered_frames', 'severity_scoring', 'level_weights'],
            {'level_1': 10, 'level_2': 50, 'level_3': 100},
        )

        exceed_frames_weight = self._get_nested_value(
            self._config, ['frame_analysis', 'stuttered_frames', 'severity_scoring', 'exceed_frames_weight'], 5.0
        )

        exceed_time_weight = self._get_nested_value(
            self._config, ['frame_analysis', 'stuttered_frames', 'severity_scoring', 'exceed_time_weight'], 0.1
        )

        return {**level_weights, 'exceed_frames_weight': exceed_frames_weight, 'exceed_time_weight': exceed_time_weight}

    def get_database_timeout(self) -> int:
        """获取数据库查询超时时间"""
        return self._get_nested_value(self._config, ['performance', 'database', 'query_timeout'], 120)

    def is_memory_optimization_enabled(self) -> bool:
        """是否启用内存优化"""
        return self._get_nested_value(self._config, ['performance', 'memory', 'optimize_memory_usage'], True)

    def get_large_database_threshold(self) -> int:
        """获取大数据库文件阈值（MB）"""
        return self._get_nested_value(self._config, ['performance', 'memory', 'large_database_threshold'], 500)

    def is_performance_logs_enabled(self) -> bool:
        """是否启用性能日志"""
        return self._get_nested_value(self._config, ['logging', 'enable_performance_logs'], True)

    def is_optimization_logs_enabled(self) -> bool:
        """是否启用优化策略日志"""
        return self._get_nested_value(self._config, ['logging', 'enable_optimization_logs'], True)

    def get_default_mode(self) -> str:
        """获取默认分析模式"""
        return self._get_nested_value(self._config, ['compatibility', 'default_mode'], 'optimized')

    def get_config(self) -> dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()

    def reload_config(self):
        """重新加载配置"""
        self._load_config()
        logging.info('配置已重新加载')

    def __repr__(self):
        return (
            f'FrameAnalysisConfig(top_n={self.get_top_n_analysis()}, lightweight={self.is_lightweight_mode_enabled()})'
        )


# 全局配置实例
config = FrameAnalysisConfig()
