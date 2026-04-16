"""
knowledge_loader.py

从 knowledge/ 目录检索与当前分析上下文最相关的知识段落，注入 LLM system prompt。

设计要点：
────────────────────────────────────────────────
1. 段落级索引（Section Index）
   - 按 H2 标题（## ...）将每个文档拆分为若干段落
   - 每个段落记录：所属文件、heading、implicit_keywords（从标题提取）
   - 首次加载时建立内存索引，无需持久化

2. 关键词相关性检索（Keyword Retrieval）
   - 调用方传入 context_signals：当前分析推导出的关键词列表
     （来源：checker 类型、问题假设、唤醒线程名、代码 owner 名等）
   - 对每个段落计算相关性得分 = context_signals 命中段落关键词的数量
   - 只注入得分最高的若干段落，控制在 token 预算内

3. 降级策略
   - 若 context_signals 为空，退化为"高 priority 优先，顺序填充"

4. Frontmatter 支持
   - priority : int（默认 5，越大越优先）
   - applicable : ["checker-name"]（过滤不相关 checker 的整个文件）
   - keywords : ["kw1", "kw2"]（文件级额外关键词，补充标题关键词）
────────────────────────────────────────────────
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w+)\s*:\s*(.+)$", re.MULTILINE)
_H2_RE = re.compile(r"^## .+", re.MULTILINE)

# 中文分词近似：按 2-gram 切片 + 标点切割
_ZH_SPLIT_RE = re.compile(r"[\s\-_/（）【】：。，、\[\]()]+")


# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class KnowledgeSection:
    """一个段落（H2 级别）的知识片段。"""
    file_stem: str
    heading: str
    body: str
    priority: int = 5
    keywords: set[str] = field(default_factory=set)  # 标题 + frontmatter 关键词

    @property
    def char_count(self) -> int:
        return len(self.heading) + len(self.body)

    def relevance_score(self, signals: list[str]) -> float:
        """计算与 context_signals 的关键词命中得分。"""
        if not signals:
            return float(self.priority)
        hit = 0
        body_lower = (self.heading + " " + self.body).lower()
        for sig in signals:
            for token in _tokenize(sig):
                if token and len(token) >= 2 and token in body_lower:
                    hit += 1
        # 额外奖励：预设 keywords 命中
        for kw in self.keywords:
            if kw.lower() in body_lower:
                hit += 2
        return hit + self.priority * 0.1  # 优先级作为平局决胜


def _tokenize(text: str) -> list[str]:
    """粗略分词：按分隔符切割 + 小写。"""
    parts = _ZH_SPLIT_RE.split(text.lower())
    tokens: list[str] = []
    for p in parts:
        if not p:
            continue
        # 2-gram 切片（覆盖中文短语）
        if len(p) >= 4:
            for i in range(len(p) - 1):
                tokens.append(p[i:i+2])
        tokens.append(p)
    return tokens


# ── 解析工具 ────────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """提取 YAML frontmatter，返回 (meta, body)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    meta: dict[str, Any] = {}
    for kv in _KV_RE.finditer(m.group(1)):
        key, val = kv.group(1).strip(), kv.group(2).strip()
        if key == "priority":
            try:
                meta[key] = int(val)
            except ValueError:
                meta[key] = 5
        elif key in ("applicable", "keywords"):
            items = re.findall(r'"([^"]+)"', val)
            if not items:
                items = [v.strip().strip('"') for v in val.strip("[]").split(",")]
            meta[key] = [i for i in items if i]
        else:
            meta[key] = val.strip('"')

    body = text[m.end():]
    return meta, body


def _extract_keywords_from_heading(heading: str) -> set[str]:
    """从 H2 标题提取隐式关键词（按分隔符切割）。"""
    clean = re.sub(r"^#+\s*", "", heading)
    parts = _ZH_SPLIT_RE.split(clean.lower())
    return {p for p in parts if len(p) >= 2}


def _split_into_sections(
    body: str,
    file_stem: str,
    priority: int,
    file_keywords: list[str],
) -> list[KnowledgeSection]:
    """将文档 body 按 H2 标题拆分为段落列表。"""
    # 找所有 H2 标题的位置
    splits = [(m.start(), m.group()) for m in _H2_RE.finditer(body)]

    if not splits:
        # 无 H2，整篇作为一个段落
        heading = file_stem
        return [KnowledgeSection(
            file_stem=file_stem,
            heading=heading,
            body=body.strip(),
            priority=priority,
            keywords=set(file_keywords),
        )]

    sections: list[KnowledgeSection] = []
    for idx, (pos, heading) in enumerate(splits):
        # 当前段落的 body 是从本标题到下一标题之间的内容
        end = splits[idx + 1][0] if idx + 1 < len(splits) else len(body)
        section_body = body[pos + len(heading):end].strip()
        kw = _extract_keywords_from_heading(heading) | set(file_keywords)
        sections.append(KnowledgeSection(
            file_stem=file_stem,
            heading=heading.strip(),
            body=section_body,
            priority=priority,
            keywords=kw,
        ))
    return sections


# ── 公共接口 ────────────────────────────────────────────────────────────────

def build_knowledge_index(
    knowledge_dir: str | Path,
    checker: str = "",
) -> list[KnowledgeSection]:
    """
    扫描 knowledge/ 目录，构建段落级内存索引。

    Parameters
    ----------
    knowledge_dir : path
        knowledge/ 目录路径。
    checker : str
        当前 checker 类型（如 "empty-frame"）。用于过滤 applicable 字段。

    Returns
    -------
    list[KnowledgeSection]
        所有符合 checker 过滤条件的段落，按 priority 降序预排列。
    """
    knowledge_dir = Path(knowledge_dir)
    if not knowledge_dir.is_dir():
        return []

    all_sections: list[KnowledgeSection] = []

    for md_path in sorted(knowledge_dir.glob("*.md")):
        if md_path.name == "README.md":
            continue
        try:
            raw = md_path.read_text(encoding="utf-8")
        except OSError:
            continue

        meta, body = _parse_frontmatter(raw)
        priority: int = meta.get("priority", 5)
        applicable: list[str] = meta.get("applicable", [])
        file_keywords: list[str] = meta.get("keywords", [])

        # checker 过滤（applicable 为空表示适用所有）
        if checker and applicable and checker not in applicable:
            continue

        sections = _split_into_sections(
            body=body,
            file_stem=md_path.stem,
            priority=priority,
            file_keywords=file_keywords,
        )
        all_sections.extend(sections)

    # 预排序：priority 降序
    all_sections.sort(key=lambda s: s.priority, reverse=True)
    return all_sections


def retrieve_knowledge(
    sections: list[KnowledgeSection],
    context_signals: list[str],
    max_chars: int = 5000,
    max_sections: int = 8,
) -> str:
    """
    根据 context_signals 从段落索引中检索最相关的段落，
    组合成注入 system prompt 的知识文本。

    Parameters
    ----------
    sections : list[KnowledgeSection]
        由 build_knowledge_index() 返回的段落列表。
    context_signals : list[str]
        当前分析推导出的信号，例如：
        ["ForEach", "setInterval", "aboutToAppear", "com.jd.hm.mall"]
        用于计算段落相关性得分。
    max_chars : int
        注入 system prompt 的最大字符预算（默认 5000）。
    max_sections : int
        最多注入段落数（默认 8）。

    Returns
    -------
    str
        格式化的知识文本；若无匹配则返回空字符串。
    """
    if not sections:
        return ""

    # 计算各段落得分并排序
    scored = sorted(
        sections,
        key=lambda s: s.relevance_score(context_signals),
        reverse=True,
    )

    selected: list[KnowledgeSection] = []
    used_chars = 0
    seen_files: dict[str, int] = {}  # 限制同一文件最多贡献 3 个段落，避免单文件垄断

    for sec in scored:
        if len(selected) >= max_sections:
            break
        # 每个文件最多 3 段
        if seen_files.get(sec.file_stem, 0) >= 3:
            continue
        if used_chars + sec.char_count > max_chars:
            continue
        selected.append(sec)
        used_chars += sec.char_count
        seen_files[sec.file_stem] = seen_files.get(sec.file_stem, 0) + 1

    if not selected:
        return ""

    # 按文件和段落顺序重新排列（保持文档可读性）
    selected.sort(key=lambda s: (s.file_stem, s.heading))

    parts: list[str] = []
    current_file = ""
    for sec in selected:
        if sec.file_stem != current_file:
            current_file = sec.file_stem
            parts.append(f"**[来源: {sec.file_stem}]**\n")
        parts.append(f"{sec.heading}\n\n{sec.body}\n")

    return "\n".join(parts)


def load_knowledge(
    knowledge_dir: str | Path,
    checker: str = "",
    context_signals: list[str] | None = None,
    max_chars: int = 5000,
) -> str:
    """
    便捷函数：建索引 + 检索，一步完成。

    Parameters
    ----------
    context_signals : list[str] | None
        当前分析上下文关键词（如假设类型、线程名、组件名等）。
        None 或空列表时退化为"按 priority 顺序填充"。
    """
    sections = build_knowledge_index(knowledge_dir, checker=checker)
    return retrieve_knowledge(
        sections,
        context_signals=context_signals or [],
        max_chars=max_chars,
    )
