from __future__ import annotations

from pathlib import Path
from typing import Any


class EmptyFrameReportRenderer:
    def render(self, evidence: dict[str, Any], hypotheses: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        overview = evidence.get("overview", {})
        dominant_threads = evidence.get("dominant_threads", [])
        representative_frames = evidence.get("representative_frames", [])
        proc_source_hints = evidence.get("proc_source_hints", [])
        ui_snapshot_hints = evidence.get("ui_snapshot_hints", [])
        caveats = evidence.get("caveats", [])
        top_hypothesis = hypotheses[0] if hypotheses else None

        lines.append("# Empty-Frame Suspect Report")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(self._render_summary_sentence(overview, dominant_threads, top_hypothesis, proc_source_hints, ui_snapshot_hints))
        lines.append("")

        lines.append("## 现象")
        lines.extend(self._render_phenomenon(overview, dominant_threads, representative_frames, top_hypothesis))
        lines.append("")

        if ui_snapshot_hints:
            lines.append("## 场景")
            lines.extend(self._render_scene(ui_snapshot_hints, proc_source_hints))
            lines.append("")

        lines.append("## 根因源代码")
        lines.extend(self._render_top_suspects(proc_source_hints, top_hypothesis, ui_snapshot_hints))
        lines.append("")

        lines.append("## 修复方向")
        checklist_items = self._collect_fix_items(hypotheses)
        if not checklist_items:
            checklist_items = ["补充更多空刷代表帧、页面快照或代码索引信息后再继续定位。"]
        for item in checklist_items[:6]:
            lines.append(f"- [ ] {item}")
        lines.append("")

        lines.append("## Caveats")
        for item in caveats or ["候选代码范围表示优先排查区域，不代表已确认唯一根因。"]:
            lines.append(f"- {item}")
        lines.append("")

        lines.append("## Appendix: Top Evidence")
        lines.extend(self._render_appendix(representative_frames))
        return "\n".join(lines).strip() + "\n"

    def _render_summary_sentence(
        self,
        overview: dict[str, Any],
        dominant_threads: list[dict[str, Any]],
        top_hypothesis: dict[str, Any] | None,
        proc_source_hints: list[dict[str, Any]],
        ui_snapshot_hints: list[dict[str, Any]],
    ) -> str:
        total = overview.get("total_empty_frames", 0)
        rate = overview.get("empty_frame_percentage", 0)
        severity = overview.get("severity_level", "unknown")
        main_pct = overview.get("main_thread_percentage_in_empty_frame", 0)
        thread_names = ", ".join(item.get("thread_name", "unknown") for item in dominant_threads[:3])
        top_title = top_hypothesis.get("title") if top_hypothesis else "尚未形成明确候选根因"
        runtime_ui = self._summarize_runtime_ui(ui_snapshot_hints)
        if proc_source_hints:
            top_source = proc_source_hints[0]
            reason = self._short_reason(top_source)
            ui_clause = f"运行场景更接近 {runtime_ui}；" if runtime_ui else ""
            return (
                f"该样本检测到 {total} 个空刷帧，占比 {rate}% ，严重度 {severity}。"
                f"主线程空刷负载占比 {main_pct}% ，主要活跃线程包括 {thread_names or '未知'}。"
                f"{ui_clause}现象上属于 VSync/JS 持续驱动的无效刷新；"
                f"当前最值得先看的根因源码是 {self._format_proc_source_scope(top_source)}，{reason}。"
            )
        return (
            f"该样本检测到 {total} 个空刷帧，占比 {rate}% ，严重度 {severity}。"
            f"主线程空刷负载占比 {main_pct}% ，主要活跃线程包括 {thread_names or '未知'}。"
            f"{f'运行态 UI 更接近 {runtime_ui}。' if runtime_ui else ''}"
            f"当前最优先假设是：{top_title}。"
        )

    def _render_phenomenon(
        self,
        overview: dict[str, Any],
        dominant_threads: list[dict[str, Any]],
        representative_frames: list[dict[str, Any]],
        top_hypothesis: dict[str, Any] | None,
    ) -> list[str]:
        breakdown = overview.get("detection_breakdown", {})
        top_threads = ", ".join(item.get("thread_name", "unknown") for item in dominant_threads[:3]) or "未知"
        lines = [
            f"- 空刷总量: {overview.get('total_empty_frames', 0)} | 占比: {overview.get('empty_frame_percentage', 0)}% | 严重度: {overview.get('severity_level', 'unknown')}",
            f"- 主线程空刷占比: {overview.get('main_thread_percentage_in_empty_frame', 0)}% | 主要线程: {top_threads}",
            f"- 检测拆分: direct_only={breakdown.get('direct_only', 0)}, rs_traced_only={breakdown.get('rs_traced_only', 0)}, both={breakdown.get('both', 0)}",
        ]
        if top_hypothesis:
            lines.append(f"- 现象判断: {top_hypothesis.get('title', '未知')}。")
        if representative_frames:
            frame = representative_frames[0]
            wakeup = " -> ".join(item.get("thread_name", "unknown") for item in frame.get("wakeup_threads", [])[:5])
            if wakeup:
                lines.append(f"- 关键链路: VSync#{frame.get('vsync')} 的唤醒链为 {wakeup}。")
            if frame.get("symbol_hints"):
                lines.append(f"- 关键符号: {', '.join(frame.get('symbol_hints', [])[:5])}")
        return lines

    def _render_scene(self, ui_snapshot_hints: list[dict[str, Any]], proc_source_hints: list[dict[str, Any]]) -> list[str]:
        lines = []
        runtime_ui = self._summarize_runtime_ui(ui_snapshot_hints)
        if runtime_ui:
            lines.append(f"- 运行场景: {runtime_ui}")
        lines.append("- 说明: 这里描述的是问题发生时的运行上下文，用于帮助缩小排查范围，不等于 UI 本身就是根因。")
        if proc_source_hints:
            top_scope = self._format_proc_source_scope(proc_source_hints[0])
            lines.append(f"- 与场景最接近的触发源码入口: {top_scope}")
        for item in ui_snapshot_hints[:6]:
            anchor_note = " | anchor" if item.get('runtime_anchor') else ""
            lines.append(
                f"- {item.get('name', 'unknown')} | kind={item.get('kind', 'unknown')}{anchor_note} | hits={item.get('count', 0)} | sources={', '.join(item.get('sources', [])[:3])}"
            )
        return lines

    def _render_top_suspects(
        self,
        proc_source_hints: list[dict[str, Any]],
        top_hypothesis: dict[str, Any] | None,
        ui_snapshot_hints: list[dict[str, Any]],
    ) -> list[str]:
        lines: list[str] = []
        if proc_source_hints:
            for idx, item in enumerate(proc_source_hints[:5], 1):
                ui_scope = self._infer_ui_scope(item, ui_snapshot_hints)
                lines.append(
                    f"### 嫌疑源码 {idx}: {self._format_proc_source_scope(item)}"
                )
                lines.append(
                    f"- 现象关联: {self._short_reason(item, ui_snapshot_hints)}"
                )
                lines.append(
                    f"- 证据: hits={item.get('hit_count', 0)}, direct={item.get('direct_hit_count', 0)}, perf={item.get('perf_hit_count', 0)}, frames={len(item.get('frame_vsyncs', []))}, threads={', '.join(item.get('thread_names', [])[:3]) or 'unknown'}"
                )
                lines.append(
                    f"- 触发符号: {', '.join(item.get('symbols', [])[:4]) or 'unknown'}"
                )
                if ui_scope:
                    lines.append(f"- 场景上下文: {ui_scope}")
                runtime_mapping = self._render_runtime_mapping(item, ui_snapshot_hints)
                if runtime_mapping:
                    lines.extend(runtime_mapping)
                lines.extend(self._render_decompiled_candidates(item, ui_snapshot_hints))
                lines.append("")
            return lines[:-1]

        lines.append("- 未命中可用的 `/proc` 用户态源码范围，当前只能依赖线程/VSync/UI 快照与反编译索引做模糊定位。")
        if top_hypothesis:
            lines.append(f"- 当前优先问题类型：{top_hypothesis.get('title', '未知')}。")
        return lines

    def _render_ui_snapshot(self, ui_snapshot_hints: list[dict[str, Any]]) -> list[str]:
        lines = []
        runtime_ui = self._summarize_runtime_ui(ui_snapshot_hints)
        if runtime_ui:
            lines.append(f"- Runtime focus: {runtime_ui}")
        for item in ui_snapshot_hints[:8]:
            anchor_note = " | anchor" if item.get('runtime_anchor') else ""
            lines.append(
                f"- {item.get('name', 'unknown')} | kind={item.get('kind', 'unknown')}{anchor_note} | hits={item.get('count', 0)} | sources={', '.join(item.get('sources', [])[:3])}"
            )
        return lines

    def _summarize_runtime_ui(self, ui_snapshot_hints: list[dict[str, Any]]) -> str:
        names = [item.get('name', '') for item in ui_snapshot_hints]
        home_names = [name for name in names if name in {'JdHome', 'TopTabContainer', 'MainTabContainer', 'HomeTnViewWrapper', 'TnFloorView', 'RecommendProductListView', 'SecondFloorH5Container'}]
        if home_names:
            return 'JdHome 首页容器 / 推荐流 / TN 区 (' + '、'.join(home_names[:5]) + ')'
        return '、'.join(name for name in names[:4] if name)

    def _render_runtime_mapping(self, item: dict[str, Any], ui_snapshot_hints: list[dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        runtime_names = {entry.get('name', '') for entry in ui_snapshot_hints}
        haystack = ' '.join([
            item.get('source_path', ''),
            ' '.join(item.get('symbols', [])),
            ' '.join(item.get('packages', [])),
            ' '.join(candidate.get('module_path', '') for candidate in item.get('decompiled_candidates', [])[:3]),
            ' '.join(candidate.get('owner_name', '') for candidate in item.get('decompiled_candidates', [])[:3]),
        ]).lower()

        if 'searchtn' in haystack and {'HomeTnViewWrapper', 'TnFloorView'} & runtime_names:
            lines.append('- 运行态映射: 命中 SearchTnContainerView，但当前 UI dump 的同类运行态组件更接近 HomeTnViewWrapper / TnFloorView。')
            lines.append('- 映射原因: 两边都表现为 TN 容器创建/数据处理链，源码名偏 search，运行态更像首页 TN 区复用容器。')
        if any(token in haystack for token in ('productlist', 'waterflowcomponent')) and 'RecommendProductListView' in runtime_names:
            lines.append('- 运行态映射: 命中 ProductList/WaterFlow 类源码，但当前运行态直接出现 RecommendProductListView，优先视为首页推荐瀑布流复用链。')
        return lines

    def _collect_fix_items(self, hypotheses: list[dict[str, Any]]) -> list[str]:
        ordered: list[str] = []
        for hypothesis in hypotheses:
            for item in hypothesis.get("fix_direction", []):
                if item not in ordered:
                    ordered.append(item)
        return ordered

    def _render_appendix(self, representative_frames: list[dict[str, Any]]) -> list[str]:
        lines = []
        if not representative_frames:
            return ["- 无代表帧可附录。"]
        for idx, frame in enumerate(representative_frames[:3], 1):
            lines.append(
                f"### Frame {idx}: VSync#{frame.get('vsync')} | thread={frame.get('thread_name', 'unknown')} | frame_load={frame.get('frame_load', 0)} | dur_ms={frame.get('dur_ms', 0)}"
            )
            if frame.get("wakeup_threads"):
                lines.append(
                    "- Wakeup chain: "
                    + " -> ".join(item.get("thread_name", "unknown") for item in frame.get("wakeup_threads", [])[:5])
                )
            if frame.get("symbol_hints"):
                lines.append(f"- Symbol hints: {', '.join(frame.get('symbol_hints', [])[:6])}")
            proc_hits = frame.get("all_proc_source_hits") or frame.get("proc_source_hits") or []
            if proc_hits:
                lines.append(
                    "- /proc source hits: " + " | ".join(self._format_frame_proc_hit(item) for item in proc_hits[:5])
                )
        return lines

    def _render_decompiled_candidates(self, item: dict[str, Any], ui_snapshot_hints: list[dict[str, Any]] | None = None) -> list[str]:
        candidates = sorted(
            item.get("decompiled_candidates", []),
            key=lambda candidate: self._runtime_candidate_sort_key(candidate, ui_snapshot_hints or []),
        )[:2]
        if not candidates:
            return ["- Decompiled scope: 未在当前索引中找到稳定映射"]

        lines = ["- 根因源码范围:"]
        for candidate in candidates:
            lines.append(f"  - {self._format_decompiled_candidate(candidate)}")
        return lines

    @staticmethod
    def _runtime_candidate_sort_key(candidate: dict[str, Any], ui_snapshot_hints: list[dict[str, Any]]) -> tuple[int, int, int, str, int]:
        runtime_names = {entry.get('name', '') for entry in ui_snapshot_hints}
        haystack = ' '.join([
            candidate.get('owner_name', ''),
            candidate.get('symbol_name', ''),
            candidate.get('module_path', ''),
            ' '.join(hit.get('ui_api', '') for hit in candidate.get('matched_ui_hits', [])),
        ]).lower()

        runtime_bonus = 0
        if runtime_names & {'JdHome', 'HomeTnViewWrapper', 'TnFloorView', 'RecommendProductListView', 'TopTabContainer', 'MainTabContainer'}:
            if any(token in haystack for token in ('jdhome', 'hometnviewwrapper', 'tnfloorview', 'recommendproductlistview', 'toptabcontainer', 'maintabcontainer', 'secondfloorh5container')):
                runtime_bonus += 60
            if any(token in haystack for token in ('silktncontainer', 'silktnalertcontainer', 'tnpagecontainer', 'tn', 'recommend', 'waterflow', 'cardcontainer', 'createcardcontainer', 'handletndata')):
                runtime_bonus += 26
            if any(token in haystack for token in ('categorysearchcontainer', 'poisearchcontainer', 'searchresultpage', 'searchproductlistpage')):
                runtime_bonus -= 30

        lifecycle_bonus = 1 if any(token in haystack for token in ('abouttoappear', 'initialrender', 'build', 'onpageshow')) else 0
        return (
            -runtime_bonus,
            -int(candidate.get('score', 0) or 0),
            -lifecycle_bonus,
            candidate.get('module_path', ''),
            int(candidate.get('line_start', 0) or 0),
        )

    @staticmethod
    def _format_proc_source_scope(item: dict[str, Any]) -> str:
        source_path = item.get("source_path", "")
        path_obj = Path(source_path) if source_path else None
        if path_obj and path_obj.name.lower() == "index.ts" and len(path_obj.parts) >= 2:
            short_path = "/".join(path_obj.parts[-2:])
        elif path_obj:
            short_path = path_obj.name
        else:
            short_path = item.get("owner_name", "unknown")
        lines = item.get("lines", [])[:4]
        return f"{short_path}:{'/'.join(str(line) for line in lines)}" if lines else short_path

    def _format_frame_proc_hit(self, item: dict[str, Any]) -> str:
        source_path = item.get("source_path", "")
        path_obj = Path(source_path) if source_path else None
        if path_obj and path_obj.name.lower() == "index.ts" and len(path_obj.parts) >= 2:
            short_path = "/".join(path_obj.parts[-2:])
        elif path_obj:
            short_path = path_obj.name
        else:
            short_path = item.get("owner_name", "unknown")
        return f"{short_path}:{item.get('line')}::{item.get('symbol_name', 'unknown')} [{item.get('via', 'unknown')}]"

    @staticmethod
    def _format_decompiled_candidate(item: dict[str, Any]) -> str:
        owner_name = item.get("owner_name", "unknown")
        symbol_name = item.get("symbol_name", "unknown")
        file_name = item.get("file", "unknown")
        line_start = item.get("line_start", 0)
        line_end = item.get("line_end", 0)
        module_path = item.get("module_path_short") or item.get("module_path") or "unknown"
        reasons = ", ".join(item.get("reasons", [])[:2])
        ui_hits = [hit.get("ui_api") for hit in item.get("matched_ui_hits", []) if hit.get("ui_api")]
        ui_note = f" | UI={', '.join(ui_hits[:2])}" if ui_hits else ""
        reason_note = f" | {reasons}" if reasons else ""
        return f"{owner_name}.{symbol_name} @ {file_name}:{line_start}-{line_end} ({module_path}{ui_note}{reason_note})"

    def _infer_ui_scope(self, item: dict[str, Any], ui_snapshot_hints: list[dict[str, Any]]) -> str:
        candidates = item.get("decompiled_candidates", [])[:3]
        haystack_parts = [item.get("source_path", "")]
        runtime_names = [entry.get("name", "") for entry in ui_snapshot_hints]
        haystack_parts.extend(runtime_names)
        for candidate in candidates:
            haystack_parts.extend(
                [
                    candidate.get("owner_name", ""),
                    candidate.get("symbol_name", ""),
                    candidate.get("module_path", ""),
                    " ".join(hit.get("ui_api", "") for hit in candidate.get("matched_ui_hits", [])),
                ]
            )
        haystack = " ".join(haystack_parts).lower()

        if any(token in haystack for token in ("jdhome", "hometnviewwrapper", "tnfloorview", "recommendproductlistview", "toptabcontainer", "maintabcontainer", "secondfloorh5container")):
            return "JdHome 首页容器 / 推荐流 / TN 区"
        if any(token in haystack for token in ("categorysearchcontainer", "searchtn", "jdrn_page", "searchboxtn")):
            return "搜索/TN 容器实现，但当前更可能复用于首页 TN 区"
        if any(token in haystack for token in ("productlistitem", "commoditylistpage", "waterflowcomponent", "productlisttopsearch")):
            return "商品流 / WaterFlow 实现，当前运行态更像首页推荐瀑布流"
        if any(token in haystack for token in ("flowskeleton", "skeleton", "skeletonscreen")):
            return "骨架屏占位列表 / 骨架卡片区"
        if any(token in haystack for token in ("silktnalertcontainer", "silktncontainer", "tnwrapcontainer", "tnpagecontainer")):
            return "TN 卡片容器 / 弹层承载区"
        if any(token in haystack for token in ("searchresultpage", "livestatuscomp")):
            return "搜索结果页结果流 / 状态角标区"
        if any(token in haystack for token in ("networkstatus", "statuscomp", "statuslayout")):
            return "网络状态条 / 状态提示区"
        return ""

    def _short_reason(self, item: dict[str, Any], ui_snapshot_hints: list[dict[str, Any]] | None = None) -> str:
        source_path = (item.get("source_path", "") or "").lower()
        symbols = " ".join(item.get("symbols", [])).lower()
        packages = " ".join(item.get("packages", [])).lower()
        haystack = " ".join([source_path, symbols, packages])
        runtime_names = {entry.get('name', '') for entry in (ui_snapshot_hints or [])}
        reasons = []

        if runtime_names & {'JdHome', 'HomeTnViewWrapper', 'TnFloorView', 'RecommendProductListView', 'TopTabContainer', 'MainTabContainer'}:
            reasons.append("当前运行态更接近首页 TN / 推荐流容器")
        elif any(token in haystack for token in ("search", "product", "list")):
            reasons.append("命中列表/TN 相关实现")

        if any(token in haystack for token in ("skeleton", "animation", "lottie")):
            reasons.append("涉及骨架屏/动画刷新")
        if any(token in haystack for token in ("createcontainer", "createcardcontainer", "itemcomponent", "initialrender", "handletndata")):
            reasons.append("命中容器创建或列表更新入口")
        if item.get("direct_hit_count", 0):
            reasons.append("代表帧直接命中")
        if item.get("perf_hit_count", 0):
            reasons.append("邻近 perf sample 重复出现")
        return "，".join(reasons[:3]) or "与空刷代表帧时间邻近且重复出现"
