#!/usr/bin/env python3
"""
LLM 初始化工具
集中处理 API key 的获取和初始化
"""

from collections.abc import Callable
from typing import Optional

from core.llm.analyzer import LLMFunctionAnalyzer
from core.utils import config
from core.utils.logger import get_logger

module_logger = get_logger(__name__)

try:
    from core.llm.batch_analyzer import BatchLLMFunctionAnalyzer

    BATCH_LLM_AVAILABLE = True
except ImportError:
    BATCH_LLM_AVAILABLE = False
    module_logger.warning('batch_llm_function_analyzer 模块不可用,将使用单个函数分析')


def init_llm_analyzer(
    use_llm: bool,
    llm_model: str,
    use_batch_llm: bool,
    batch_size: int,
    logger: Callable,
) -> tuple[Optional[LLMFunctionAnalyzer], bool, bool]:
    """初始化 LLM 分析器
    Args:
        use_llm: 是否使用 LLM 分析
        llm_model: LLM 模型名称
        use_batch_llm: 是否使用批量 LLM 分析
        batch_size: 批量分析时每个 prompt 包含的函数数量
        logger: 日志打印函数
    Returns:
        (llm_analyzer, use_llm, use_batch_llm) 其中use_llm和use_batch_llm是实际使用的LLM分析器类型
    """
    log = logger or module_logger.info

    if not use_llm:
        return None, False, use_batch_llm

    api_key = config.load_api_key()
    if not api_key:
        llm_config = config.get_llm_config()
        service_type = llm_config['service_type']
        api_key_env = llm_config['api_key_env']
        log(f'未找到 {service_type.upper()} API key ({api_key_env})，将跳过 LLM 分析')
        return None, False, use_batch_llm

    batch_size = batch_size if batch_size is not None else config.DEFAULT_BATCH_SIZE
    model_name = llm_model if llm_model is not None else config.get_llm_model()

    # 从配置获取 base_url
    llm_config = config.get_llm_config()
    base_url = llm_config['base_url']
    service_type = llm_config['service_type']

    try:
        if use_batch_llm and BATCH_LLM_AVAILABLE:
            analyzer = BatchLLMFunctionAnalyzer(
                api_key=api_key,
                model=model_name,
                base_url=base_url,
                batch_size=batch_size,
                enable_cache=True,
            )
            log(f'使用批量 LLM 分析器: 服务={service_type}, 模型={model_name}, 批量大小={batch_size}')
            return analyzer, True, True

        if use_batch_llm and not BATCH_LLM_AVAILABLE:
            log('批量 LLM 分析器不可用,将使用单个函数分析')
            analyzer = LLMFunctionAnalyzer(api_key=api_key, model=model_name, base_url=base_url, enable_cache=True)
            log(f'使用单个 LLM 分析器: 服务={service_type}, 模型={model_name}')
            return analyzer, True, False
    except Exception as e:
        log(f'初始化 LLM 分析器失败: {e}')
        return None, False, use_batch_llm
