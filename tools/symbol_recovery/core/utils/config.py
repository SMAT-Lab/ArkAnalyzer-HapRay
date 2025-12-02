#!/usr/bin/env python3
"""
配置文件
"""

import os
from pathlib import Path
from typing import Optional

# 加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv 未安装，跳过 .env 文件加载
    pass
except Exception:
    # 加载 .env 文件时出错，忽略
    pass

DEFAULT_OUTPUT_DIR = Path('output')
DEFAULT_PERF_DATA = 'perf.data'
DEFAULT_PERF_DB = 'perf.db'
DEFAULT_TOP_N = 100
DEFAULT_BATCH_SIZE = 3
DEFAULT_LLM_MODEL = 'GPT-5'

HTML_REPORT_PATTERN = 'hiperf_report.html'

# Step 4 HTML 文件搜索目录
STEP_DIRS = ['step4', 'output', '.']

EXCEL_ANALYSIS_PATTERN = 'excel_analysis_{n}_functions.xlsx'
EXCEL_REPORT_PATTERN = 'excel_analysis_{n}_functions_report.html'

EVENT_COUNT_ANALYSIS_PATTERN = 'event_count_top{n}_analysis.xlsx'
EVENT_COUNT_REPORT_PATTERN = 'event_count_top{n}_report.html'

CALL_COUNT_ANALYSIS_PATTERN = 'call_count_top{n}_analysis.xlsx'
CALL_COUNT_REPORT_PATTERN = 'call_count_top{n}_report.html'

TIME_STATS_PATTERN = 'time_stats.json'

# 临时文件前缀
TEMP_FILE_PREFIX = 'temp_'

# ============================================================================
# LLM 服务配置
# ============================================================================

# LLM 服务类型：支持 "poe", "openai", "claude", "deepseek", "custom"
# 可以通过环境变量 LLM_SERVICE_TYPE 覆盖
LLM_SERVICE_TYPE = os.getenv('LLM_SERVICE_TYPE', 'poe').lower()

# LLM API Key 环境变量名（根据服务类型自动设置，也可通过环境变量覆盖）
LLM_API_KEY_ENV_MAP = {
    'poe': 'POE_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'claude': 'ANTHROPIC_API_KEY',
    'deepseek': 'DEEPSEEK_API_KEY',
    'custom': os.getenv('LLM_API_KEY_ENV', 'LLM_API_KEY'),
}

# 当前服务类型的 API Key 环境变量名
LLM_API_KEY_ENV = LLM_API_KEY_ENV_MAP.get(LLM_SERVICE_TYPE, os.getenv('LLM_API_KEY_ENV', 'POE_API_KEY'))

# LLM API Base URL（根据服务类型自动设置）
LLM_BASE_URL_MAP = {
    'poe': 'https://api.poe.com/v1',
    'openai': 'https://api.openai.com/v1',
    'claude': 'https://api.anthropic.com/v1',  # Claude 使用不同的 API，这里仅作示例
    'deepseek': 'https://api.deepseek.com/v1',
    'custom': os.getenv('LLM_BASE_URL', 'https://api.poe.com/v1'),
}

# 当前服务类型的 Base URL
LLM_BASE_URL = LLM_BASE_URL_MAP.get(LLM_SERVICE_TYPE, os.getenv('LLM_BASE_URL', 'https://api.poe.com/v1'))

# LLM 模型配置（支持服务特定的模型环境变量）
LLM_MODEL_ENV_MAP = {
    'poe': 'POE_MODEL',
    'openai': 'OPENAI_MODEL',
    'claude': 'CLAUDE_MODEL',
    'deepseek': 'DEEPSEEK_MODEL',
    'custom': 'LLM_MODEL',
}

# 当前服务类型的模型环境变量名
LLM_MODEL_ENV = LLM_MODEL_ENV_MAP.get(LLM_SERVICE_TYPE, 'LLM_MODEL')


# 获取 LLM 模型名称（优先从服务特定的环境变量读取，其次从通用 LLM_MODEL，最后使用默认值）
def get_llm_model() -> str:
    """获取 LLM 模型名称"""
    # 优先从服务特定的环境变量读取
    model = os.getenv(LLM_MODEL_ENV)
    if model:
        return model
    # 其次从通用 LLM_MODEL 环境变量读取
    model = os.getenv('LLM_MODEL')
    if model:
        return model
    # 最后使用默认值
    return DEFAULT_LLM_MODEL


# LLM API 调用超时时间（秒）
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '30'))

# LLM 缓存目录
LLM_CACHE_DIR = Path(os.getenv('LLM_CACHE_DIR', 'cache'))

# LLM 缓存文件路径
LLM_CACHE_FILE = LLM_CACHE_DIR / 'llm_analysis_cache.json'
LLM_TOKEN_STATS_FILE = LLM_CACHE_DIR / 'llm_token_stats.json'


def load_api_key() -> Optional[str]:
    """
    从环境变量或 .env 文件中加载 API key（使用 config 中的配置）

    Returns:
        Optional[str]: API key，如果未找到则返回 None
    """
    # 从环境变量读取（load_dotenv() 已经加载了 .env 文件）
    api_key = os.getenv(LLM_API_KEY_ENV)
    if api_key:
        return api_key

    # 从 .env 文件读取（手动解析，作为 fallback）
    env_file = Path('.env')
    if env_file.exists():
        try:
            with open(env_file, encoding='utf-8') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    # 支持多种环境变量名（向后兼容）
                    key_patterns = [
                        f'{LLM_API_KEY_ENV}=',
                        'POE_API_KEY=',
                        'OPENAI_API_KEY=',
                        'DEEPSEEK_API_KEY=',
                        'LLM_API_KEY=',
                    ]
                    for pattern in key_patterns:
                        if line.startswith(pattern) and not line.startswith('#'):
                            api_key = line.split('=', 1)[1].strip()
                            # 移除引号（如果有）
                            return api_key.strip('"').strip("'")
        except Exception:
            pass
    return None


def get_llm_config():
    """
    获取 LLM 配置字典

    Returns:
        dict: 包含所有 LLM 配置的字典
    """
    return {
        'service_type': LLM_SERVICE_TYPE,
        'api_key_env': LLM_API_KEY_ENV,
        'base_url': LLM_BASE_URL,
        'timeout': LLM_TIMEOUT,
        'cache_dir': LLM_CACHE_DIR,
        'cache_file': LLM_CACHE_FILE,
        'token_stats_file': LLM_TOKEN_STATS_FILE,
        'model': get_llm_model(),
        'batch_size': DEFAULT_BATCH_SIZE,
    }


def get_output_dir(custom_dir=None):
    """获取输出目录"""
    if custom_dir:
        return Path(custom_dir)
    return DEFAULT_OUTPUT_DIR


def ensure_output_dir(output_dir: Path):
    """确保输出目录存在"""
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
