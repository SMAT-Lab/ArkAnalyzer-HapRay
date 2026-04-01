#!/usr/bin/env python3
"""
KMP 模式分析器：针对 stripped KMP .so 文件的符号恢复 + KMP 组件分类。

工作流程:
  1. 从 perf.db 中查询目标 SO 文件的 top-N 指令数地址（symbol_id=-1）
  2. 用 KMPBatchLLMAnalyzer（注入 KMP 背景知识）进行反汇编 + 符号恢复
  3. 将 KMP 组件分类写入 Excel 输出的「KMP分类」列
  4. 构建「[Category] Function: name」格式的地址映射，用于 HTML 符号替换
"""

from pathlib import Path

import pandas as pd

from core.analyzers.event_analyzer import EventCountAnalyzer
from core.llm.kmp_batch_analyzer import KMPBatchLLMAnalyzer
from core.utils.logger import get_logger

logger = get_logger(__name__)


class KMPAnalyzer(EventCountAnalyzer):
    """KMP 感知的事件计数分析器，注入 KMPBatchLLMAnalyzer 实现组件分类。

    新增参数：
        app_name: 目标应用名称（如 "Bilibili"、"快手"），用于在 prompt 中生成
                  对应的业务分类标签（如 "Business (Bilibili)"）。
                  不传时生成通用的 "Business Logic" 描述，适用于任意 KMP 库分析。
                  可配合 --context 进一步注入应用特有的命名空间/占比信息。
    """

    def __init__(self, *args, app_name: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        # KMP 模式使用 inclusive 口径（Total 列），统计调用链中任意位置出现目标 SO 的样本
        self._self_cost_only = False
        # 将默认的 BatchLLMFunctionAnalyzer 替换为 KMP 专用版本
        if self.use_llm and self.use_batch_llm and self.llm_analyzer is not None:
            old = self.llm_analyzer
            so_name = self.so_dir.name if self.so_dir else ''
            try:
                self.llm_analyzer = KMPBatchLLMAnalyzer(
                    api_key=old.api_key,
                    model=old.model,
                    base_url=old.base_url,
                    batch_size=self.batch_size,
                    enable_cache=True,
                    save_prompts=old.save_prompts,
                    output_dir=str(old.output_dir),
                    open_source_lib=old.open_source_lib,
                    so_name=so_name,
                    app_name=app_name,
                )
                logger.info(
                    'KMPBatchLLMAnalyzer injected: so=%s, app=%s',
                    so_name, app_name or '(generic)',
                )
            except Exception as e:
                logger.warning('Failed to create KMPBatchLLMAnalyzer, falling back to default: %s', e)

    # ------------------------------------------------------------------
    # Override analyze_event_count_only to promote kmp_category up
    # from llm_result into the top-level result dict.
    # ------------------------------------------------------------------
    def analyze_event_count_only(self, top_n=None):
        results = super().analyze_event_count_only(top_n=top_n)
        for result in results:
            llm_result = result.get('llm_result') or {}
            kmp_category = llm_result.get('kmp_category', 'Other')
            # ------------------------------------------------------------------
            # Python-level deterministic override（优先级高于 LLM）
            # 防止 LLM 因调用上下文覆盖明确的 KMP Runtime 汇编模式
            # ------------------------------------------------------------------
            kmp_category = _apply_kmp_rule_overrides(result, kmp_category)
            result['kmp_category'] = kmp_category
        return results

    # ------------------------------------------------------------------
    # KMP-specific save: delegates to parent then appends KMP分类 column.
    # ------------------------------------------------------------------
    def save_kmp_results(self, results, time_tracker=None, output_dir=None, top_n=None):
        """保存 KMP 分析结果（含 KMP分类 列）。

        返回最终 Excel 文件路径。
        """
        output_file = self.save_event_count_results(
            results,
            time_tracker=time_tracker,
            output_dir=output_dir,
            top_n=top_n,
        )
        if output_file and Path(output_file).exists():
            _add_kmp_category_column(output_file, results)
            logger.info('KMP分类 column written to: %s', output_file)
        return output_file

    # ------------------------------------------------------------------
    # Build address → "[Category] Function: name" mapping for HTML replacement.
    # ------------------------------------------------------------------
    def build_kmp_function_mapping(self, results):
        """构建地址到「[Category] Function: name」的映射，供 HTML 符号替换使用。"""
        mapping = {}
        for result in results:
            address = result.get('address', '').strip()
            if not address:
                continue
            llm_result = result.get('llm_result') or {}
            func_name = str(llm_result.get('function_name', '')).strip()
            if not func_name or func_name in ('nan', 'None'):
                continue
            category = result.get('kmp_category', 'Other')
            mapping[address] = f'[{category}] Function: {func_name}'
        logger.info('Built KMP function mapping: %d entries', len(mapping))
        return mapping


# ---------------------------------------------------------------------------
# Deterministic rule-based KMP category override
# ---------------------------------------------------------------------------

def _apply_kmp_rule_overrides(result: dict, llm_category: str) -> str:
    """根据汇编特征对 LLM 分类结果做确定性覆盖。

    KMP Runtime 特征优先于调用上下文，LLM 容易因为看到 VSync/ArkUI callers
    而将纯帧管理函数误分类为 androidx.compose.ui:ui。
    """
    instruction_count = result.get('instruction_count', 0) or 0

    # 规则 1: 极短函数（≤4 条指令）且没有外部函数调用 → 必定是 LeaveFrame / 帧出口
    # 3~4 条 ldp/ret 是 ARM64 函数帧恢复的典型 epilog，属于 Kotlin/Native runtime
    if instruction_count <= 4:
        called_funcs = result.get('called_functions') or []
        if not called_funcs:
            if llm_category != 'KMP Runtime':
                logger.info(
                    'Rule override: %s  instruction_count=%d, no external calls → '
                    'KMP Runtime (was: %s)',
                    result.get('address', ''), instruction_count, llm_category,
                )
            return 'KMP Runtime'

    return llm_category


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _add_kmp_category_column(excel_file: str, results: list) -> None:
    """在已存在的 Excel 文件中插入「KMP分类」列。"""
    cat_map = {
        str(r.get('address', '')).strip(): r.get('kmp_category', 'Other')
        for r in results
        if r.get('address')
    }
    try:
        df = pd.read_excel(excel_file, engine='openpyxl')
        df['KMP分类'] = df['地址'].apply(lambda addr: cat_map.get(str(addr).strip(), 'Other'))
        df.to_excel(excel_file, index=False, engine='openpyxl')
    except Exception as e:
        logger.warning('Failed to add KMP分类 column to %s: %s', excel_file, e)
