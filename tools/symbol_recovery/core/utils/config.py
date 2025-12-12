#!/usr/bin/env python3
"""
配置管理模块

提供统一的配置管理接口，支持环境变量、.env 文件和插件配置的优先级读取。
"""

import os
from pathlib import Path
from typing import Any, Optional

# ============================================================================
# 环境变量加载
# ============================================================================

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv 未安装，跳过 .env 文件加载
    pass
except Exception:
    # 加载 .env 文件时出错，忽略
    pass

# ============================================================================
# 默认配置常量
# ============================================================================

DEFAULT_OUTPUT_DIR = Path('output')
DEFAULT_PERF_DATA = 'perf.data'
DEFAULT_PERF_DB = 'perf.db'
DEFAULT_TOP_N = 100
DEFAULT_BATCH_SIZE = 3
DEFAULT_LLM_MODEL = 'GPT-5'
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_CACHE_DIR = 'cache'

# ============================================================================
# 文件模式常量
# ============================================================================

HTML_REPORT_PATTERN = 'hiperf_report.html'
STEP_DIRS: list[str] = ['step4', 'output', '.']
EXCEL_ANALYSIS_PATTERN = 'excel_analysis_{n}_functions.xlsx'
EXCEL_REPORT_PATTERN = 'excel_analysis_{n}_functions_report.html'
EVENT_COUNT_ANALYSIS_PATTERN = 'event_count_top{n}_analysis.xlsx'
EVENT_COUNT_REPORT_PATTERN = 'event_count_top{n}_report.html'
CALL_COUNT_ANALYSIS_PATTERN = 'call_count_top{n}_analysis.xlsx'
CALL_COUNT_REPORT_PATTERN = 'call_count_top{n}_report.html'
TIME_STATS_PATTERN = 'time_stats.json'
TEMP_FILE_PREFIX = 'temp_'

# ============================================================================
# LLM 服务配置常量
# ============================================================================

LLM_CACHE_FILENAME = 'llm_analysis_cache.json'
LLM_TOKEN_STATS_FILENAME = 'llm_token_stats.json'

# 环境变量名
ENV_KEY_LLM_API_KEY = 'LLM_API_KEY'
ENV_KEY_LLM_BASE_URL = 'LLM_BASE_URL'
ENV_KEY_LLM_MODEL = 'LLM_MODEL'
ENV_KEY_LLM_TIMEOUT = 'LLM_TIMEOUT'
ENV_KEY_LLM_CACHE_DIR = 'LLM_CACHE_DIR'


# ============================================================================
# LLM 配置类
# ============================================================================


class LLMConfig:
    """
    LLM 配置管理器

    负责管理 LLM 相关的所有配置，包括 API Key、Base URL、Model 等。
    配置从环境变量读取（.env 文件已通过 load_dotenv() 自动加载，插件配置也已写入环境变量）。
    """

    def __init__(self):
        """初始化 LLM 配置"""
        self._base_url: str = self._determine_base_url()
        self._timeout: int = self._get_timeout()
        self._cache_dir: Path = self._get_cache_dir()
        self._cache_file: Path = self._cache_dir / LLM_CACHE_FILENAME
        self._token_stats_file: Path = self._cache_dir / LLM_TOKEN_STATS_FILENAME

    def _determine_base_url(self) -> str:
        """确定 Base URL"""
        # 从环境变量读取（插件配置和 .env 文件都已加载到环境变量中）
        env_url = os.getenv(ENV_KEY_LLM_BASE_URL)
        if env_url:
            return env_url

        # 默认值（如果没有配置则返回空字符串，由调用方决定）
        return ''

    def _get_timeout(self) -> int:
        """获取超时时间（秒）"""
        timeout_str = os.getenv(ENV_KEY_LLM_TIMEOUT, str(DEFAULT_LLM_TIMEOUT))
        try:
            return int(timeout_str)
        except ValueError:
            return DEFAULT_LLM_TIMEOUT

    def _get_cache_dir(self) -> Path:
        """获取缓存目录"""
        cache_dir = os.getenv(ENV_KEY_LLM_CACHE_DIR, DEFAULT_CACHE_DIR)
        return Path(cache_dir)

    def get_model(self) -> str:
        """
        获取 LLM 模型名称

        Returns:
            str: LLM 模型名称
        """
        # 从环境变量读取（插件配置和 .env 文件都已加载到环境变量中）
        env_model = os.getenv(ENV_KEY_LLM_MODEL)
        if env_model:
            return env_model

        # 默认值
        return DEFAULT_LLM_MODEL

    def load_api_key(self) -> Optional[str]:
        """
        加载 API Key

        从环境变量读取（插件配置和 .env 文件都已加载到环境变量中）

        Returns:
            Optional[str]: API Key，如果未找到则返回 None
        """
        env_key = os.getenv(ENV_KEY_LLM_API_KEY)
        if env_key:
            return env_key

        return None

    def get_config_dict(self) -> dict[str, Any]:
        """
        获取完整的 LLM 配置字典

        Returns:
            Dict[str, Any]: 包含所有 LLM 配置的字典
        """
        return {
            'api_key': self.load_api_key(),
            'base_url': self._base_url,
            'timeout': self._timeout,
            'cache_dir': self._cache_dir,
            'cache_file': self._cache_file,
            'token_stats_file': self._token_stats_file,
            'model': self.get_model(),
            'batch_size': DEFAULT_BATCH_SIZE,
        }

    @property
    def base_url(self) -> str:
        """获取 Base URL"""
        return self._base_url

    @property
    def timeout(self) -> int:
        """获取超时时间"""
        return self._timeout

    @property
    def cache_dir(self) -> Path:
        """获取缓存目录"""
        return self._cache_dir

    @property
    def cache_file(self) -> Path:
        """获取缓存文件路径"""
        return self._cache_file

    @property
    def token_stats_file(self) -> Path:
        """获取 Token 统计文件路径"""
        return self._token_stats_file


# ============================================================================
# 主配置类
# ============================================================================


class Config:
    """
    配置单例类

    提供统一的配置管理接口，采用单例模式确保全局配置一致性。
    """

    _instance: Optional['Config'] = None
    _initialized: bool = False

    def __new__(cls) -> 'Config':
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """初始化配置（仅在首次调用时执行）"""
        if Config._initialized:
            return

        self._llm_config = LLMConfig()
        Config._initialized = True

    def get_llm_config(self) -> dict[str, Any]:
        """
        获取完整的 LLM 配置字典

        Returns:
            Dict[str, Any]: 包含所有 LLM 配置的字典
        """
        return self._llm_config.get_config_dict()

    def get_output_dir(self, custom_dir: Optional[str] = None) -> Path:
        """
        获取输出目录路径

        Args:
            custom_dir: 自定义输出目录，如果提供则使用该目录

        Returns:
            Path: 输出目录路径对象
        """
        if custom_dir:
            return Path(custom_dir)
        return DEFAULT_OUTPUT_DIR

    def ensure_output_dir(self, output_dir: Path) -> Path:
        """
        确保输出目录存在，如果不存在则创建

        Args:
            output_dir: 输出目录路径

        Returns:
            Path: 输出目录路径对象（与输入相同）
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


# ============================================================================
# 单例实例
# ============================================================================

config = Config()
