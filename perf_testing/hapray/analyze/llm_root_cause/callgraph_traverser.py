"""
callgraph_traverser.py

从反编译生成的 *.callgraph.json 文件中构建调用图，
提供「向上追溯调用链」能力：给定嫌疑函数名，找到顶层生命周期入口。

callgraph.json 结构（由 hap_decompiler 生成）:
{
  "functions": [
    {
      "name":  "短名（点换下划线）",
      "full_name": "完整限定名",
      "call_sites": [{"callee": "被调用者名", "loop_depth": 0, ...}],
      "callers":    ["调用者名", ...],   # 预先计算好的反向边
      "caller_count": N,
      ...
    }
  ],
  "stats": {...}
}

如果 callers 字段为空（部分版本未填充），则从 call_sites 自动构建反向索引。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# 生命周期入口函数名（正则）
_LIFECYCLE_PATTERN = re.compile(
    r"(aboutToAppear|aboutToDisappear|onPageShow|onPageHide|"
    r"initialRender|build|rerender|aboutToBeDeleted|"
    r"func_main_0|onCreate|onDestroy)\b",
    re.IGNORECASE,
)

# 最大追溯深度，防止循环图导致无限递归
_MAX_DEPTH = 6


class CallChain:
    """一条从入口到嫌疑函数的调用链。"""

    def __init__(self, chain: list[str], is_lifecycle_entry: bool):
        self.chain = chain          # [入口函数, ..., 嫌疑函数]
        self.is_lifecycle_entry = is_lifecycle_entry

    @property
    def entry(self) -> str:
        return self.chain[0] if self.chain else ""

    @property
    def suspect(self) -> str:
        return self.chain[-1] if self.chain else ""

    def format(self) -> str:
        return " → ".join(self._shorten(n) for n in self.chain)

    @staticmethod
    def _shorten(name: str) -> str:
        """取最后两段限定名，避免输出过长。"""
        parts = name.replace("_", ".").split(".")
        meaningful = [p for p in parts if p and p not in ("ets", "ts", "js", "src", "main")]
        return ".".join(meaningful[-2:]) if len(meaningful) >= 2 else name


class CallgraphTraverser:
    """
    调用图遍历器。

    Usage:
        traverser = CallgraphTraverser(decompiled_root)
        chains = traverser.find_entry_chains("SilkTNContainer___0__aboutToAppear")
        for chain in chains:
            print(chain.format())
    """

    def __init__(self, decompiled_root: str | Path):
        self.root = Path(decompiled_root)
        # name -> function record
        self._funcs: dict[str, dict[str, Any]] = {}
        # callee_name -> set of caller names（反向索引）
        self._callers_of: dict[str, set[str]] = {}
        self._loaded = False

    # ── 公开接口 ────────────────────────────────────────────────────────

    def find_entry_chains(
        self, symbol_name: str, max_chains: int = 5
    ) -> list[CallChain]:
        """
        从 symbol_name 向上追溯调用链，直到生命周期入口或无更多调用者。
        返回最多 max_chains 条链，优先返回以生命周期入口开头的链。
        """
        self._ensure_loaded()
        candidates = self._find_matching_functions(symbol_name)
        if not candidates:
            return []

        all_chains: list[CallChain] = []
        for func_name in candidates[:3]:  # 最多取 3 个同名变体
            chains = self._bfs_upward(func_name, max_chains)
            all_chains.extend(chains)

        # 优先生命周期入口，其次按链长排序
        all_chains.sort(key=lambda c: (not c.is_lifecycle_entry, len(c.chain)))
        return all_chains[:max_chains]

    def find_callers(self, symbol_name: str, depth: int = 2) -> list[str]:
        """
        返回直接或间接调用 symbol_name 的函数列表（最多 depth 层）。
        """
        self._ensure_loaded()
        candidates = self._find_matching_functions(symbol_name)
        result: list[str] = []
        visited: set[str] = set(candidates)

        current_level = list(candidates)
        for _ in range(depth):
            next_level: list[str] = []
            for name in current_level:
                for caller in self._callers_of.get(name, set()):
                    if caller not in visited:
                        visited.add(caller)
                        next_level.append(caller)
                        result.append(caller)
            current_level = next_level
            if not current_level:
                break
        return result

    def enrich_proc_source_hints(
        self, hints: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        为每个 proc_source_hint 的 decompiled_candidates 补充 call_chains 字段。
        """
        self._ensure_loaded()
        for hint in hints:
            for cand in hint.get("decompiled_candidates") or []:
                symbol_name = cand.get("symbol_name") or ""
                owner_name = cand.get("owner_name") or ""
                query = f"{owner_name}.{symbol_name}" if owner_name else symbol_name
                chains = self.find_entry_chains(query, max_chains=3)
                cand["call_chains"] = [c.format() for c in chains]
                cand["has_lifecycle_entry"] = any(c.is_lifecycle_entry for c in chains)
        return hints

    def format_chains_for_prompt(self, hints: list[dict[str, Any]]) -> str:
        """
        将 proc_source_hints 里的调用链格式化为 LLM prompt 友好的文本段落。
        """
        lines: list[str] = []
        for hint in hints[:5]:
            for cand in (hint.get("decompiled_candidates") or [])[:2]:
                chains = cand.get("call_chains") or []
                if not chains:
                    continue
                label = f"{cand.get('owner_name','')}.{cand.get('symbol_name','')}"
                lines.append(f"  {label}:")
                for chain in chains[:2]:
                    lines.append(f"    {chain}")
        return "\n".join(lines) if lines else "  （调用图未匹配到调用链）"

    # ── 加载与构建 ────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        for cg_path in self.root.glob("*.callgraph.json"):
            try:
                self._load_file(cg_path)
            except Exception:
                pass
        self._loaded = True

    def _load_file(self, path: Path) -> None:
        with open(path, encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)

        funcs: list[dict[str, Any]] = data.get("functions") or []
        for fn in funcs:
            name = fn.get("name") or ""
            full_name = fn.get("full_name") or name
            if not name:
                continue
            # 同时用 name 和 full_name 作为 key
            self._funcs[name] = fn
            if full_name != name:
                self._funcs[full_name] = fn

            # 如果 callers 字段已填充，直接建反向索引
            for caller in fn.get("callers") or []:
                self._callers_of.setdefault(name, set()).add(caller)
                if full_name != name:
                    self._callers_of.setdefault(full_name, set()).add(caller)

        # 如果 callers 字段为空，从 call_sites 构建反向索引
        needs_invert = all(not (fn.get("callers")) for fn in funcs[:20] if fn.get("call_sites"))
        if needs_invert:
            for fn in funcs:
                caller_name = fn.get("name") or ""
                for site in fn.get("call_sites") or []:
                    callee = site.get("callee") or ""
                    if callee:
                        self._callers_of.setdefault(callee, set()).add(caller_name)

    # ── 搜索与遍历 ───────────────────────────────────────────────────

    def _find_matching_functions(self, symbol_name: str) -> list[str]:
        """
        在函数名字典中查找与 symbol_name 匹配的函数（支持部分名匹配）。
        优先精确匹配，其次包含匹配。
        """
        if not symbol_name:
            return []
        # 清洗：把 "OwnerName.symbolName" 拆成多个查询词
        queries = [symbol_name]
        if "." in symbol_name:
            parts = symbol_name.split(".")
            queries.extend([parts[-1], "_".join(p for p in parts if p)])

        exact: list[str] = []
        partial: list[str] = []

        for key in self._funcs:
            for q in queries:
                if not q:
                    continue
                if q == key or q == key.rsplit(".", 1)[-1]:
                    exact.append(key)
                    break
                q_lower = q.lower().replace(".", "").replace("_", "")
                key_lower = key.lower().replace(".", "").replace("_", "")
                if q_lower in key_lower and len(q_lower) >= 6:
                    partial.append(key)
                    break

        seen: set[str] = set()
        result: list[str] = []
        for name in exact + partial:
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result[:8]

    def _bfs_upward(self, start: str, max_chains: int) -> list[CallChain]:
        """
        从 start 向上 BFS，找到所有到达生命周期入口（或图边界）的路径。
        使用 BFS + 路径记录，避免指数级爆炸。
        """
        # 每个节点记录：(当前函数名, 当前路径)
        queue: list[list[str]] = [[start]]
        found: list[CallChain] = []
        visited_paths: set[frozenset[str]] = set()

        while queue and len(found) < max_chains:
            path = queue.pop(0)
            current = path[0]  # BFS 从叶节点往根走，路径是倒序的

            if len(path) > _MAX_DEPTH:
                # 达到深度上限，把当前路径作为一条链保存
                chain = list(reversed(path))
                found.append(CallChain(chain, self._is_lifecycle(chain[0])))
                continue

            callers = self._callers_of.get(current, set())
            if not callers:
                # 无更多调用者：这是一个根节点
                chain = list(reversed(path))
                is_lc = self._is_lifecycle(chain[0])
                found.append(CallChain(chain, is_lc))
                continue

            for caller in list(callers)[:4]:  # 限制扇出，避免爆炸
                if caller in path:  # 避免环
                    continue
                path_key = frozenset(path + [caller])
                if path_key in visited_paths:
                    continue
                visited_paths.add(path_key)

                new_path = [caller] + path
                if self._is_lifecycle(caller):
                    # 命中生命周期入口，立即记录
                    chain = list(reversed(new_path))
                    found.append(CallChain(chain, True))
                    if len(found) >= max_chains:
                        break
                else:
                    queue.append(new_path)

        return found

    @staticmethod
    def _is_lifecycle(func_name: str) -> bool:
        return bool(_LIFECYCLE_PATTERN.search(func_name))
