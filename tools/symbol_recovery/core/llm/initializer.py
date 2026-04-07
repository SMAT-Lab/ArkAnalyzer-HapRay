#!/usr/bin/env python3
"""
LLM 初始化工具
集中处理 API key 的获取和初始化
"""

from typing import Optional

from core.llm.analyzer import LLMFunctionAnalyzer
from core.llm.batch_analyzer import BatchLLMFunctionAnalyzer
from core.utils.config import config
from core.utils.logger import get_logger

logger = get_logger(__name__)


def init_llm_analyzer(
    use_llm: bool,
    llm_model: str,
    batch_size: Optional[int],
    save_prompts: bool = False,
    output_dir: Optional[str] = None,
    open_source_lib: Optional[str] = None,
) -> tuple[Optional[LLMFunctionAnalyzer], bool, bool]:
    """初始化 LLM 分析器
    Args:
        use_llm: 是否使用 LLM 分析
        llm_model: LLM 模型名称
        batch_size: 批量分析时每个 prompt 包含的函数数量；
                    传 None 时自动读取服务类型对应的默认值（claude=10, openai=5, deepseek=3 等）
        save_prompts: 是否保存生成的 prompt 到文件
        output_dir: 输出目录，用于保存 prompt 文件
        open_source_lib: 开源库名称（可选，如 "ffmpeg", "openssl" 等）
    Returns:
        (llm_analyzer, use_llm, use_batch_llm) 其中use_llm和use_batch_llm是实际使用的LLM分析器类型
    """

    if not use_llm:
        return None, False, False

    llm_config = config.get_llm_config()
    api_key = llm_config['api_key']
    if not api_key:
        logger.info('LLM API key not found (LLM_API_KEY), will skip LLM analysis')
        return None, False, False

    model_name = llm_model if llm_model is not None else llm_config['model']
    base_url = llm_config['base_url']

    # batch_size=None 时从配置读取服务特定默认值
    resolved_batch_size = batch_size if batch_size is not None else llm_config['batch_size']
    request_delay = llm_config['request_delay']
    max_concurrent = llm_config['max_concurrent']

    try:
        if resolved_batch_size > 1:
            analyzer = BatchLLMFunctionAnalyzer(
                api_key=api_key,
                model=model_name,
                base_url=base_url,
                batch_size=resolved_batch_size,
                request_delay=request_delay,
                max_concurrent=max_concurrent,
                enable_cache=True,
                save_prompts=save_prompts,
                output_dir=output_dir,
                open_source_lib=open_source_lib,
            )
            logger.info(
                f'Using batch LLM analyzer: model={model_name}, '
                f'batch_size={resolved_batch_size}, request_delay={request_delay}s, '
                f'max_concurrent={max_concurrent}'
            )
            if save_prompts:
                logger.info('Prompt saving enabled')
            return analyzer, True, True
        logger.info('Batch LLM analyzer unavailable, will use single function analysis')
        analyzer = LLMFunctionAnalyzer(
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            enable_cache=True,
            save_prompts=save_prompts,
            output_dir=output_dir,
            open_source_lib=open_source_lib,
        )
        logger.info(f'Using single LLM analyzer: model={model_name}')
        if save_prompts:
            logger.info('Prompt saving enabled')
        return analyzer, True, False
    except Exception as e:
        logger.info(f'Failed to initialize LLM analyzer: {e}')
        return None, False, False
