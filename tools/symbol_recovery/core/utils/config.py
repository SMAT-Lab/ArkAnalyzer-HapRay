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
DEFAULT_LLM_SERVICE_TYPE = 'poe'
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_CACHE_DIR = 'cache'
DEFAULT_ENV_FILE = '.env'
DEFAULT_ENCODING = 'utf-8'

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

# LLM 服务类型
SERVICE_TYPE_POE = 'poe'
SERVICE_TYPE_OPENAI = 'openai'
SERVICE_TYPE_CLAUDE = 'claude'
SERVICE_TYPE_DEEPSEEK = 'deepseek'
SERVICE_TYPE_CUSTOM = 'custom'

# 支持的服务类型列表
SUPPORTED_SERVICE_TYPES = [
    SERVICE_TYPE_POE,
    SERVICE_TYPE_OPENAI,
    SERVICE_TYPE_CLAUDE,
    SERVICE_TYPE_DEEPSEEK,
    SERVICE_TYPE_CUSTOM,
]

# API Key 环境变量名映射
API_KEY_ENV_MAP: dict[str, str] = {
    SERVICE_TYPE_POE: 'POE_API_KEY',
    SERVICE_TYPE_OPENAI: 'OPENAI_API_KEY',
    SERVICE_TYPE_CLAUDE: 'ANTHROPIC_API_KEY',
    SERVICE_TYPE_DEEPSEEK: 'DEEPSEEK_API_KEY',
    SERVICE_TYPE_CUSTOM: os.getenv('LLM_API_KEY_ENV', 'LLM_API_KEY'),
}

# Base URL 映射
BASE_URL_MAP: dict[str, str] = {
    SERVICE_TYPE_POE: 'https://api.poe.com/v1',
    SERVICE_TYPE_OPENAI: 'https://api.openai.com/v1',
    SERVICE_TYPE_CLAUDE: 'https://api.anthropic.com/v1',
    SERVICE_TYPE_DEEPSEEK: 'https://api.deepseek.com/v1',
    SERVICE_TYPE_CUSTOM: os.getenv('LLM_BASE_URL', 'https://api.poe.com/v1'),
}

# 模型环境变量名映射
MODEL_ENV_MAP: dict[str, str] = {
    SERVICE_TYPE_POE: 'POE_MODEL',
    SERVICE_TYPE_OPENAI: 'OPENAI_MODEL',
    SERVICE_TYPE_CLAUDE: 'CLAUDE_MODEL',
    SERVICE_TYPE_DEEPSEEK: 'DEEPSEEK_MODEL',
    SERVICE_TYPE_CUSTOM: 'LLM_MODEL',
}

# 环境变量名（向后兼容支持）
ENV_KEY_POE_API_KEY = 'POE_API_KEY'
ENV_KEY_OPENAI_API_KEY = 'OPENAI_API_KEY'
ENV_KEY_DEEPSEEK_API_KEY = 'DEEPSEEK_API_KEY'
ENV_KEY_LLM_API_KEY = 'LLM_API_KEY'
ENV_KEY_LLM_MODEL = 'LLM_MODEL'
ENV_KEY_LLM_SERVICE_TYPE = 'LLM_SERVICE_TYPE'
ENV_KEY_LLM_BASE_URL = 'LLM_BASE_URL'
ENV_KEY_LLM_TIMEOUT = 'LLM_TIMEOUT'
ENV_KEY_LLM_CACHE_DIR = 'LLM_CACHE_DIR'
ENV_KEY_LLM_API_KEY_ENV = 'LLM_API_KEY_ENV'

# 插件配置前缀
PLUGIN_CONFIG_PREFIX = 'HAPRAY_PLUGIN_CONFIG_'


# ============================================================================
# 辅助函数
# ============================================================================


def _normalize_key(key: str) -> str:
    """
    将配置键转换为环境变量名格式

    Args:
        key: 配置键名（小写，下划线或连字符分隔）

    Returns:
        str: 大写下划线分隔的环境变量名
    """
    return key.upper().replace('-', '_')


def _strip_quotes(value: str) -> str:
    """
    移除字符串两端的引号

    Args:
        value: 可能包含引号的字符串

    Returns:
        str: 移除引号后的字符串
    """
    return value.strip('"').strip("'")


# ============================================================================
# LLM 配置类
# ============================================================================


class LLMConfig:
    """
    LLM 配置管理器

    负责管理 LLM 相关的所有配置，包括服务类型、API Key、Base URL 等。
    支持从多个源读取配置，按优先级顺序：
    1. 插件配置（HAPRAY_PLUGIN_CONFIG_*）
    2. 环境变量
    3. .env 文件
    4. 默认值
    """

    def __init__(self, plugin_config_loader):
        """
        初始化 LLM 配置

        Args:
            plugin_config_loader: 插件配置加载器函数
        """
        self._plugin_config_loader = plugin_config_loader
        self._service_type: str = self._determine_service_type()
        self._api_key_env: str = self._get_api_key_env_name()
        self._base_url: str = self._determine_base_url()
        self._model_env: str = self._get_model_env_name()
        self._timeout: int = self._get_timeout()
        self._cache_dir: Path = self._get_cache_dir()
        self._cache_file: Path = self._cache_dir / LLM_CACHE_FILENAME
        self._token_stats_file: Path = self._cache_dir / LLM_TOKEN_STATS_FILENAME

    def _determine_service_type(self) -> str:
        """
        确定 LLM 服务类型

        注意：此方法主要用于向后兼容，实际配置优先使用 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL
        """
        plugin_value = self._plugin_config_loader('llm_service_type')
        env_value = os.getenv(ENV_KEY_LLM_SERVICE_TYPE)
        # 如果没有配置服务类型，使用默认值（不再强制要求）
        service_type = (plugin_value or env_value or DEFAULT_LLM_SERVICE_TYPE).lower()
        return service_type if service_type in SUPPORTED_SERVICE_TYPES else DEFAULT_LLM_SERVICE_TYPE

    def _get_api_key_env_name(self) -> str:
        """获取 API Key 环境变量名"""
        return API_KEY_ENV_MAP.get(
            self._service_type,
            os.getenv(ENV_KEY_LLM_API_KEY_ENV, ENV_KEY_POE_API_KEY),
        )

    def _determine_base_url(self) -> str:
        """确定 Base URL"""
        # 优先级 1: 插件配置
        plugin_url = self._plugin_config_loader('llm_base_url')
        if plugin_url:
            return plugin_url

        # 优先级 2: LLM_BASE_URL 通用环境变量
        env_url = os.getenv(ENV_KEY_LLM_BASE_URL)
        if env_url:
            return env_url

        # 优先级 3: 默认值（如果设置了服务类型，使用对应的默认 URL）
        return BASE_URL_MAP.get(self._service_type, BASE_URL_MAP[DEFAULT_LLM_SERVICE_TYPE])

    def _get_model_env_name(self) -> str:
        """获取模型环境变量名"""
        return MODEL_ENV_MAP.get(self._service_type, ENV_KEY_LLM_MODEL)

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
        # 优先级 1: 插件配置
        plugin_model = self._plugin_config_loader('llm_model')
        if plugin_model:
            return plugin_model

        # 优先级 2: LLM_MODEL 通用环境变量
        generic_model = os.getenv(ENV_KEY_LLM_MODEL)
        if generic_model:
            return generic_model

        # 优先级 3: 服务特定的环境变量（向后兼容）
        service_model = os.getenv(self._model_env)
        if service_model:
            return service_model

        # 优先级 4: 默认值
        return DEFAULT_LLM_MODEL

    def load_api_key(self) -> Optional[str]:
        """
        加载 API Key

        按优先级顺序从以下源读取：
        1. 插件配置
        2. LLM_API_KEY 环境变量（通用）
        3. 服务特定的环境变量（向后兼容）
        4. .env 文件

        Returns:
            Optional[str]: API Key，如果未找到则返回 None
        """
        # 优先级 1: 插件配置
        plugin_key = self._plugin_config_loader('llm_api_key')
        if plugin_key:
            return plugin_key

        # 优先级 2: LLM_API_KEY 通用环境变量（dotenv 已加载）
        generic_key = os.getenv(ENV_KEY_LLM_API_KEY)
        if generic_key:
            return generic_key

        # 优先级 3: 服务特定的环境变量（向后兼容）
        env_key = os.getenv(self._api_key_env)
        if env_key:
            return env_key

        # 优先级 4: .env 文件手动解析（fallback）
        return self._load_api_key_from_env_file()

    def _load_api_key_from_env_file(self) -> Optional[str]:
        """
        从 .env 文件手动解析 API Key（作为 fallback）

        Returns:
            Optional[str]: API Key，如果未找到则返回 None
        """
        env_file = Path(DEFAULT_ENV_FILE)
        if not env_file.exists():
            return None

        try:
            with open(env_file, encoding=DEFAULT_ENCODING) as file:
                for line in file:
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#'):
                        continue

                    api_key = self._extract_api_key_from_line(stripped_line)
                    if api_key:
                        return api_key
        except OSError:
            # 文件读取失败，静默忽略
            pass

        return None

    def _extract_api_key_from_line(self, line: str) -> Optional[str]:
        """
        从 .env 文件行中提取 API Key

        Args:
            line: .env 文件的一行内容

        Returns:
            Optional[str]: 提取的 API Key，如果不匹配则返回 None
        """
        # 优先支持 LLM_API_KEY，然后支持其他环境变量名（向后兼容）
        key_patterns = [
            f'{ENV_KEY_LLM_API_KEY}=',  # 优先使用通用变量
            f'{self._api_key_env}=',
            f'{ENV_KEY_POE_API_KEY}=',
            f'{ENV_KEY_OPENAI_API_KEY}=',
            f'{ENV_KEY_DEEPSEEK_API_KEY}=',
        ]

        for pattern in key_patterns:
            if line.startswith(pattern):
                value = line.split('=', 1)[1].strip()
                return _strip_quotes(value)

        return None

    def get_config_dict(self) -> dict[str, Any]:
        """
        获取完整的 LLM 配置字典

        Returns:
            Dict[str, Any]: 包含所有 LLM 配置的字典
        """
        return {
            'service_type': self._service_type,
            'api_key_env': self._api_key_env,
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
    def service_type(self) -> str:
        """获取服务类型"""
        return self._service_type

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

        self._llm_config = LLMConfig(self._get_plugin_config)
        Config._initialized = True

    def _get_plugin_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        从插件配置环境变量读取配置值

        插件配置通过 HAPRAY_PLUGIN_CONFIG_ 前缀的环境变量提供，具有最高优先级。

        Args:
            key: 配置键名（小写，下划线或连字符分隔）
            default: 默认值，如果配置不存在时返回

        Returns:
            Optional[str]: 配置值，如果不存在且未提供默认值则返回 None
        """
        env_key = f'{PLUGIN_CONFIG_PREFIX}{_normalize_key(key)}'
        value = os.getenv(env_key)
        if value is not None and value != '':
            return value
        return default

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
