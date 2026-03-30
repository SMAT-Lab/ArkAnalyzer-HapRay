#!/usr/bin/env python3
"""
KMP-specific batch LLM analyzer.

Extends BatchLLMFunctionAnalyzer to add:
  1. KMP / Kotlin-Native context in the prompt
  2. kmp_category field in the JSON schema (LLM classifies into one of the KMP component categories)
  3. Extraction of kmp_category from the LLM response

泛化说明：
  - 通过 so_name / app_name 构造参数动态生成背景块和分类列表，无需改代码即可分析任意 app 的 KMP 库。
  - 不传 app_name 时生成通用版本；用户可通过 --context 进一步注入 app 特有的命名空间/占比信息。
"""

import json
import re
from typing import Any, Optional

from core.llm.batch_analyzer import BatchLLMFunctionAnalyzer
from core.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 固定分类列表（不含业务分类，业务分类由 app_name 动态生成）
# ---------------------------------------------------------------------------

_KMP_CATEGORIES_FIXED = [
    'KMP Runtime',
    'androidx.compose.ui:ui',
    'androidx.compose.foundation:foundation-layout',
    'androidx.compose.ui:ui-unit',
    'androidx.compose.runtime:runtime',
    # business category is inserted here dynamically
    'Skia/Skiko',
    'Other (3rd-party)',
    'Other',
]


def _make_kmp_categories(app_name: str = '') -> list[str]:
    """构造包含业务分类的完整分类列表。"""
    biz_cat = f'Business ({app_name})' if app_name else 'Business Logic'
    cats = list(_KMP_CATEGORIES_FIXED)
    cats.insert(5, biz_cat)
    return cats


# 向后兼容：模块级默认列表（不含 app_name，使用通用名称）
KMP_CATEGORIES: list[str] = _make_kmp_categories()


# ---------------------------------------------------------------------------
# 动态构建 KMP 背景块
# ---------------------------------------------------------------------------

def _build_kmp_context_block(so_name: str, app_name: str, categories: list[str]) -> str:
    """根据 so_name 和 app_name 动态生成 KMP 分析背景块。

    Args:
        so_name:    目标 .so 文件名，如 "libkntr.so"；传空字符串时使用通用描述。
        app_name:   应用名称，如 "Bilibili"；传空字符串时生成通用业务类描述。
        categories: 完整分类列表，用于在规则说明中展示。
    """
    so_display = so_name if so_name else '目标 KMP .so'
    biz_cat = f'Business ({app_name})' if app_name else 'Business Logic'

    # 【库的组成】段落：有 app_name 时稍微具体，无时保持通用
    if app_name:
        composition_section = f"""\
{so_display} 是 {app_name} 的 KMP（Kotlin Multiplatform）核心库，静态链接了多个组件，可能包含：
  - {biz_cat} 代码：{app_name} 特有的业务逻辑、Protobuf 消息序列化、网络请求、媒体处理等
  - Skia/Skiko 图形引擎：FreeType、HarfBuzz、绘制原语
  - KMP Runtime：GC、内存分配、帧管理、协程、CInterop 等
  - Compose UI（kfun:androidx.compose.ui.*）：UI 渲染框架
  - Compose 生态（foundation、runtime、ui-unit 等）
  - 其他三方库（Ktor、jsoncpp 等）

如果「背景信息」部分提供了该库的具体命名空间信息，可用于辅助判断命名空间归属；
⚠️ 但组成比例（百分比）仅是整体统计，不能作为推断单个函数类别的主要依据——
   请以函数本身的代码特征（指令序列、调用链、字符串）为主要分类依据。"""
    else:
        composition_section = f"""\
{so_display} 是一个 KMP（Kotlin Multiplatform）核心库，静态链接了多个组件，通常包含：
  - {biz_cat} 代码：应用特有的业务逻辑、Protobuf 消息序列化、网络请求、媒体处理等
  - Skia/Skiko 图形引擎：FreeType、HarfBuzz、绘制原语
  - KMP Runtime：GC、内存分配、帧管理、协程、CInterop 等
  - Compose UI（kfun:androidx.compose.ui.*）：UI 渲染框架
  - Compose 生态（foundation、runtime、ui-unit 等）
  - 其他三方库（Ktor、jsoncpp 等）

如果「背景信息」部分提供了该库的具体命名空间信息，可用于辅助判断命名空间归属；
⚠️ 但组成比例（百分比）仅是整体统计，不能作为推断单个函数类别的主要依据——
   请以函数本身的代码特征（指令序列、调用链、字符串）为主要分类依据。"""

    # 业务类别描述：有 app_name 时更具体
    if app_name:
        biz_description = f"""\
  → {biz_cat}：
     函数实现 {app_name} 特定业务逻辑。判断依据（满足其一即可）：
     · 字符串常量或调用链中出现 {app_name} 专属的 kfun: 命名空间
       （如 kfun:kntr.*、kfun:bilibili.*、kfun:yylx.* 等，可从「背景信息」获取完整列表）；
       注意：kfun:kotlin.*、kfun:kotlinx.*、kfun:androidx.* 是通用框架，不属于此类
     · 实现 {app_name} 自定义 Protobuf 消息的序列化/反序列化（非 KMP Runtime 框架层基础设施）
     · {app_name} 核心功能模块（业务逻辑、网络、媒体、IM 等）的代码
     · 含有明确业务语义的 NAPI/CInterop 桥接函数（含错误处理、类型转换、集合遍历等实质逻辑，
       且该逻辑服务于 {app_name} 业务而非 KMP 运行时本身）"""
    else:
        biz_description = f"""\
  → {biz_cat}：
     函数实现应用特定业务逻辑（非 KMP 框架层通用代码）。判断依据（满足其一即可）：
     · 字符串常量或调用链中出现应用专属的 kfun: 命名空间
       （可从「背景信息」获取；注意：kfun:kotlin.*、kfun:kotlinx.*、kfun:androidx.* 是通用框架）
     · 实现应用自定义 Protobuf 消息的序列化/反序列化（非框架层基础设施）
     · 应用核心功能模块（业务逻辑、网络、媒体等）的代码
     · 含有明确业务语义的 NAPI/CInterop 桥接函数（含实质业务逻辑，非仅做运行时调用转发）"""

    return f"""
========== KMP 库分析背景 ==========
分析对象：Kotlin Multiplatform (KMP) 库 {so_display}，已 strip（剥离符号表），编译目标为 HarmonyOS ARM64。
分析目的：对 CPU 采样调用栈热点函数进行 KMP 成分分类。

【库的组成】
{composition_section}

因此你分析的函数可能来自上述任何一类，请根据反编译代码和调用链综合判断。

━━━ 第一步：确定性规则（优先判断，命中即停止） ━━━

以下模式具有唯一确定性，命中则直接归 KMP Runtime，无需进一步推断：

  R1. LeaveFrame：函数体只有 ldp + ret 组合，无任何 bl/blr/b 外部调用
      → 典型 ARM64 KMP 栈帧恢复 epilog

  R2. EnterFrame：含 mrs tpidr_el0（读线程本地存储），操作固定 offset 0xc0 链表
      → KMP 栈帧入口，管理 Kotlin 调用栈链表

  R3. AllocInstance / 对象分配：含以下原子序列
      stlr（store-release）+ ldar xzr（load-acquire 屏障）+ dmb ish，
      配合 add/lsr 做 8 字节大小对齐
      → Kotlin/Native 对象堆分配

  R4. GC Sweep/Mark：含大循环 + ldxr/stxr 原子操作 + tst/bic/orr 位操作处理标记位
      → Kotlin/Native GC 扫描

━━━ 第二步：LLM 语义推断（不命中规则时，基于全部证据自由判断） ━━━

当上述规则均不命中时，综合以下信息对函数进行语义分析，选择最匹配的分类：

  可用证据：
  · 反编译/反汇编代码：函数的逻辑结构、数据访问模式、控制流
  · 字符串常量：包含业务标识或框架标识的常量
    ⚠️ 关于 kfun: 前缀：kfun: 是 Kotlin/Native 对【所有】Kotlin 函数的统一 name mangling 前缀，
       kfun: 本身不代表任何具体分类，关键是 kfun: 后面的【包名/命名空间】：
         kfun:kotlin.*  / kfun:kotlinx.*                  → KMP Runtime（标准库）
         kfun:androidx.compose.*                          → Compose UI / foundation / runtime
         kfun:io.ktor.* / kfun:com.squareup.wire.*        → Other (3rd-party)
         kfun:<app专属命名空间>（如 kntr.*/bilibili.*/yylx.*）→ Business（可从「背景信息」获取）
  · 调用关系（callers/callees）：该函数被谁调用、调用了谁
  · 函数大小/复杂度：指令数、分支数

  分类决策依据（以实际语义为准，不强制任何默认值）：

  → KMP Runtime：
     函数实现 KMP 运行时的通用机制：线程状态管理（ldar/stlr 原子）、
     协程调度（resume/dispatch）、字符串处理（UTF-8、ByteArray）、
     FFI/CInterop 内存拷贝、Protobuf 框架层（编解码基础设施，非应用自定义消息体）、
     通用集合操作（ArrayList、HashMap 等）；
     ⚠️ 以下函数体特征，无论调用者是谁，都应归 KMP Runtime：
       - 原子 CAS / 自旋锁（ldxr/stxr 循环，无业务逻辑）
       - 通用范围检查 / 简单算术运算（仅读字段做比较或计算）
       - 对象内存分配 + 内存屏障（alloc + dmb 模式）
       - 通用帧指针/线程状态操作
       - KMP 对象 Handle/Scope 管理：建立临时作用域（Scope/Arena）、获取/封装 ObjHeader 句柄、
         管理对象引用生命周期（pin/unpin、addRef/releaseRef），这些都是 CInterop 运行时基础设施，
         即使被业务代码调用，其本质仍是通用运行时机制，应归 KMP Runtime
       - 纯 thunk/stub（极薄包装器）：函数体只有"转发参数给下级 + 帧/作用域清理"，
         总指令数极少（通常 ≤ 20 条），不含循环、类型转换、集合遍历、错误消息构造，
         不含业务字符串或业务命名空间，应归 KMP Runtime；
         ⚠️ 含有错误处理、类型转换、集合遍历、多分支逻辑的 NAPI/CInterop 桥接函数，
            即使结构上是"包装器"，也不是纯 thunk，应按实际语义分类（可能是 Business）

  → androidx.compose.ui:ui：
     函数体自身实现 Compose UI 渲染管线的核心逻辑：
       - 直接封装了 VSync 回调的完整流程（读取时间戳、调用 OnFrame/FlushVsync、
         管理 Compose 帧状态、触发重组），属于 Kotlin 编译后的 onComposeVsync/
         onFrameInner 等函数实现体
       - Compose 节点树遍历/重组调度
       - Layout 测量放置
     ⚠️ "调用者含 UIDisplaySync::OnFrame" ≠ 该函数是 compose.ui！
        一个通用原子函数、范围检查函数、简单计算函数，即使被 VSync 路径调用，
        它的本质仍是通用工具，应归 KMP Runtime。

{biz_description}

  → Skia/Skiko：
     函数涉及 2D 图形渲染：路径绘制、字体光栅化（FreeType、HarfBuzz）、
     图像解码/编码、Canvas 操作、GPU 纹理上传

  → androidx.compose.foundation:foundation-layout：
     Row/Column/Box 等布局容器的测量/放置逻辑

  → androidx.compose.runtime:runtime：
     Compose 重组机制：SnapshotState、RecomposeScope、Applier

  → Other (3rd-party)：
     明确的第三方库逻辑：Ktor 网络、jsoncpp 解析、XmlUtil 等

  → Other：
     证据不足、语义不明确时使用；
     ⚠️ 不要把"调用函数指针 + 做帧/状态清理"的 KMP 通用包装器归到 Other，
        此类函数若不含业务标识则应归 KMP Runtime，只在真正无法判断时才使用 Other

  ⚠️ 重要：请直接根据你对函数行为的理解做出最佳判断，
     不要因为"大多数函数是 KMP Runtime"就默认归入此类。
     每个函数都可能属于上述任意一类。
====================================
"""


class KMPBatchLLMAnalyzer(BatchLLMFunctionAnalyzer):
    """KMP-aware batch LLM analyzer that adds component classification.

    新增参数：
        so_name:  目标 .so 文件名（如 "libkntr.so"），用于在背景块中标注分析对象。
        app_name: 应用名称（如 "Bilibili"、"快手" 等），用于动态生成业务分类标签和描述。
                  不传时生成通用版本，可配合 --context 注入 app 特有的命名空间信息。
    """

    def __init__(self, *args, so_name: str = '', app_name: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        self._kmp_categories = _make_kmp_categories(app_name)
        cat_str = '/'.join(self._kmp_categories)
        self._category_schema_field = (
            f'      "kmp_category": "KMP组件分类，从以下选项中选一个：{cat_str}",'
        )
        self._kmp_context_block = _build_kmp_context_block(so_name, app_name, self._kmp_categories)
        logger.debug(
            'KMPBatchLLMAnalyzer initialized: so_name=%r, app_name=%r, categories=%s',
            so_name, app_name, self._kmp_categories,
        )

    def _build_batch_prompt(self, functions_data: list[dict[str, Any]], context: Optional[str] = None) -> str:
        base = super()._build_batch_prompt(functions_data, context)

        # 1. Inject KMP context block right before the JSON format section
        json_format_marker = '请按以下 JSON 格式返回分析结果:'
        if json_format_marker in base:
            base = base.replace(json_format_marker, self._kmp_context_block + json_format_marker)
        else:
            base = self._kmp_context_block + base

        # 2. Add kmp_category field to the JSON schema after "confidence"
        confidence_line = '      "confidence": "高/中/低",'
        if confidence_line in base:
            base = base.replace(
                confidence_line,
                confidence_line + '\n' + self._category_schema_field,
            )

        # 3. Add kmp_category to the notes section
        note_marker = '10. 重要：确保 JSON 格式完整'
        if note_marker in base:
            base = base.replace(
                note_marker,
                '11. kmp_category：先检查 R1-R4 确定性规则；不命中时，根据函数的实际语义'
                '（反编译逻辑 + 调用链 + 字符串）自由选择最匹配的分类，可以是任意分类\n'
                + note_marker,
            )

        return base

    def _parse_batch_response(
        self, response_text: str, functions_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        results = super()._parse_batch_response(response_text, functions_data)

        # Try to extract kmp_category from the raw JSON in the response
        kmp_cat_map: dict[str, str] = {}
        try:
            # Use the same extraction patterns as the parent class
            for pattern in [
                r'\{\s*"functions"\s*:\s*\[.*?\]\s*\}',
                r'\{[^{}]*"functions"[^{}]*\[.*?\]',
            ]:
                m = re.search(pattern, response_text, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(0))
                        for f in data.get('functions', []):
                            fid = f.get('function_id')
                            cat = f.get('kmp_category', 'Other')
                            if fid:
                                kmp_cat_map[fid] = self._normalize_category(cat)
                        break
                    except json.JSONDecodeError:
                        pass

            if not kmp_cat_map:
                # Fallback: try to extract kmp_category field by regex
                for fid, cat in re.findall(
                    r'"function_id"\s*:\s*"([^"]+)"[^}]*?"kmp_category"\s*:\s*"([^"]+)"',
                    response_text,
                    re.DOTALL,
                ):
                    kmp_cat_map[fid] = self._normalize_category(cat)
        except Exception as e:
            logger.warning('Failed to extract kmp_category from LLM response: %s', e)

        for result in results:
            fid = result.get('function_id')
            result['kmp_category'] = kmp_cat_map.get(fid, 'Other') if fid else 'Other'

        return results

    def _normalize_category(self, raw: str) -> str:
        """将 LLM 原始输出映射到当前实例的 KMP 分类列表中。"""
        if not raw:
            return 'Other'
        raw = raw.strip()
        if raw in self._kmp_categories:
            return raw
        # Fuzzy match
        raw_lower = raw.lower()
        for cat in self._kmp_categories:
            if cat.lower() in raw_lower or raw_lower in cat.lower():
                return cat
        return 'Other'
