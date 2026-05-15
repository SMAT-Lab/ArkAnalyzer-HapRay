"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import base64
import json
import logging
import os
import re
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from hapray.analyze import BaseAnalyzer
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.common.symbol_recovery_bridge import (
    default_symbol_recovery_output_dir,
    embed_symbol_recovery_report_into_hiperf_html,
    maybe_generate_symbol_recovery_html_for_step,
    maybe_run_symbol_recovery_for_step,
    probe_symbol_recovery_llm_runtime,
    resolve_symbol_recovery_root,
    run_symbol_recovery_agent_step2,
    symbol_recovery_report_name,
    symbol_recovery_replaced_html_name,
    symbol_recovery_should_run,
)
from hapray.core.config.config import Config
from hapray.mode.mode import Mode


_SR_EMBED_MARKER = b'<!-- hapray-symbol-recovery-embedded -->'


def _strip_symbol_recovery_embed(html_bytes: bytes) -> bytes:
    """Remove any previously-embedded symbol recovery panel from hiperf_report.html."""
    idx = html_bytes.find(_SR_EMBED_MARKER)
    if idx == -1:
        return html_bytes
    # The panel is always inserted before </body>; remove from marker onward.
    close_body = html_bytes.rfind(b'</body>')
    if close_body != -1 and idx < close_body:
        return html_bytes[:idx] + html_bytes[close_body:]
    return html_bytes[:idx]


class PerfAnalyzer(BaseAnalyzer):
    def __init__(self, scene_dir: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'more/flame_graph')
        self.time_ranges = time_ranges

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Run performance analysis"""
        if Config.get('mode') == Mode.COMMUNITY:
            return self._community_analyze_impl(step_dir, trace_db_path, perf_db_path, app_pids)
        return self._simple_analyze_impl(step_dir, trace_db_path, perf_db_path, app_pids)

    def _community_analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """COMMUNITY mode (0): original pure path, unchanged."""
        if step_dir == 'step1':
            args = ['perf', '-i', self.scene_dir]
            so_dir = Config.get('so_dir', None)
            if so_dir:
                args.extend(['-s', os.path.abspath(so_dir)])
            kind = self.convert_kind_to_json()
            if len(kind) > 0:
                args.extend(['-k', kind])
            if self.time_ranges:
                time_range_strings = []
                for tr in self.time_ranges:
                    time_range_str = f'{tr["startTime"]}-{tr["endTime"]}'
                    time_range_strings.append(time_range_str)
                args.extend(['--time-ranges'] + time_range_strings)
                logging.info('Adding time ranges to perf command: %s', time_range_strings)
            logging.debug('Running perf analysis with command: %s', ' '.join(args))
            ExeUtils.execute_hapray_cmd(args)

        sr_applied = self._maybe_apply_symbol_recovery(step_dir, perf_db_path)
        result = self.generate_hiperf_report(perf_db_path)
        if sr_applied:
            generated_html = self._maybe_generate_symbol_recovery_html(step_dir)
            self._maybe_embed_symbol_recovery_report(step_dir, perf_db_path, generated_html)
        return result

    def _simple_analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """SIMPLE mode (1): with perf_json_restored & backup/restore support."""
        perf_json_restored = bool(Config.get('perf_json_restored', False))

        if step_dir == 'step1':
            _saved_html = _saved_perf_json = None
            if perf_json_restored:
                step_path = Path(os.path.dirname(perf_db_path))
                html_p = step_path / 'hiperf_report.html'
                if html_p.is_file():
                    _saved_html = html_p.read_bytes()
                json_p = step_path / 'perf.json'
                if json_p.is_file():
                    _saved_perf_json = json_p.read_bytes()

            args = ['perf', '-i', self.scene_dir]
            so_dir = Config.get('so_dir', None)
            if so_dir:
                args.extend(['-s', os.path.abspath(so_dir)])
            kind = self.convert_kind_to_json()
            if len(kind) > 0:
                args.extend(['-k', kind])
            if self.time_ranges:
                time_range_strings = []
                for tr in self.time_ranges:
                    time_range_str = f'{tr["startTime"]}-{tr["endTime"]}'
                    time_range_strings.append(time_range_str)
                args.extend(['--time-ranges'] + time_range_strings)
                logging.info('Adding time ranges to perf command: %s', time_range_strings)

            logging.debug('Running perf analysis with command: %s', ' '.join(args))
            ExeUtils.execute_hapray_cmd(args)

            if perf_json_restored:
                step_path = Path(os.path.dirname(perf_db_path))
                if _saved_html is not None:
                    html = _strip_symbol_recovery_embed(_saved_html)
                    (step_path / 'hiperf_report.html').write_bytes(html)
                    logging.info('Restored original hiperf_report.html after perf -i')
                if _saved_perf_json is not None:
                    (step_path / 'perf.json').write_bytes(_saved_perf_json)
                    logging.info('Restored original perf.json after perf -i')

        sr_applied = self._maybe_apply_symbol_recovery(step_dir, perf_db_path)

        if perf_json_restored:
            perf_json_file = os.path.join(os.path.dirname(perf_db_path), 'perf.json')
            result = None
            if os.path.isfile(perf_json_file):
                with open(perf_json_file, encoding='utf-8') as f:
                    result = f.read()
                logging.info('Using existing perf.json (perf_json_restored=True): %s', perf_json_file)
            else:
                logging.warning('perf_json_restored=True but perf.json not found at %s', perf_json_file)
        else:
            result = self.generate_hiperf_report(perf_db_path)
        if sr_applied:
            generated_html = self._maybe_generate_symbol_recovery_html(step_dir)
            self._maybe_embed_symbol_recovery_report(step_dir, perf_db_path, generated_html)
        return result

    def _maybe_apply_symbol_recovery(self, step_dir: str, perf_db_path: str) -> bool:
        """在生成火焰图数据前，可选运行符号恢复并写回 perf.json。"""
        no_llm = bool(Config.get('symbol_recovery_no_llm', False))
        llm_ready = bool(Config.get('symbol_recovery_llm_ready', False))
        agent_mode = bool(Config.get('symbol_recovery_agent_mode', False))
        import_results_tpl = (Config.get('symbol_recovery_import_results', '') or '').strip()
        so_dir = (Config.get('so_dir', None) or '').strip()
        if not symbol_recovery_should_run(
            llm_ready=llm_ready,
            effective_so_dir=so_dir or None,
            perf_db_path=perf_db_path,
            no_llm_override=no_llm,
            agent_mode=agent_mode,
        ):
            return False
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        # update 集成路径：导出 load_decomposition_top_symbols.json（ecol 等拆解）并 --top-symbols-json；
        # 不用 perf.db 单 SQL 冒充拆解口径。
        stat_method = 'event_count'
        output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
        timeout_raw = Config.get('symbol_recovery_timeout', 0)
        try:
            tval = float(timeout_raw) if timeout_raw else 0.0
        except (TypeError, ValueError):
            tval = 0.0
        timeout_sec = tval if tval > 0 else None
        extras: list[str] = []
        ctx = (Config.get('symbol_recovery_context', '') or '').strip()
        if ctx:
            extras.extend(['--context', ctx])
        import_results: Optional[str] = None
        if import_results_tpl:
            import_results = import_results_tpl.replace('{step}', step_dir)
        out_dir = default_symbol_recovery_output_dir(self.scene_dir, step_dir, output_root)
        top_symbols_json = self._dump_load_decomposition_top_symbols(
            step_dir,
            perf_db_path,
            out_dir,
            so_dir=so_dir or None,
            top_n=top_n,
        )
        if top_symbols_json:
            extras.extend(['--top-symbols-json', str(top_symbols_json)])
        # 与 update 一致：优先使用「环境就绪 + 探测通过」的在线 LLM；否则走 Agent 编排（导出任务 + 导入）。
        # 未走 update 设置 Config 时，在本地补做一次探测。
        use_online_llm = bool(llm_ready and not no_llm and not agent_mode and not import_results)
        if use_online_llm:
            probe_cfg = Config.get('symbol_recovery_llm_probe_ok', None)
            if probe_cfg is None or probe_cfg == '':
                sr_probe = resolve_symbol_recovery_root()
                probe_ok, probe_msg = probe_symbol_recovery_llm_runtime(sr_probe, timeout_sec=5)
                if not probe_ok:
                    logging.warning(
                        'Symbol recovery LLM pre-check failed: %s. Using agent mode for this step.',
                        probe_msg,
                    )
                    use_online_llm = False
            elif not bool(probe_cfg):
                logging.warning('Symbol recovery LLM probe_ok is false in config; using agent mode for this step.')
                use_online_llm = False

        prompt_only = bool(not use_online_llm and not import_results)
        ok = maybe_run_symbol_recovery_for_step(
            self.scene_dir,
            step_dir,
            perf_db_path,
            effective_so_dir=so_dir,
            top_n=top_n,
            stat_method=stat_method,
            output_root=output_root,
            subprocess_timeout_sec=timeout_sec,
            extra_args=extras or None,
            prompt_only=prompt_only,
            import_llm_results=import_results,
        )
        if not ok:
            logging.warning(
                'Integrated symbol recovery did not complete for scene=%s step=%s',
                self.scene_dir,
                step_dir,
            )
            return False
        if prompt_only and not import_results:
            logging.info(
                '符号恢复 Agent 路径：若在 Cursor 中由当前对话 Agent 推断，请先确认所用模型（可询问「你是什么模型」）；'
                '或设置环境变量 HAPRAY_SYMBOL_RECOVERY_AGENT_CMD；否则使用 symbol_recovery 内联 OpenAI 兼容 API（依赖 .env / 环境变量）。'
            )
            inferred_json = self._run_agent_inference_for_symbol_recovery(out_dir, timeout_sec=timeout_sec)
            if not inferred_json:
                logging.warning(
                    'Agent mode: symbol recovery inference failed for scene=%s step=%s',
                    self.scene_dir,
                    step_dir,
                )
                return False
            ok = maybe_run_symbol_recovery_for_step(
                self.scene_dir,
                step_dir,
                perf_db_path,
                effective_so_dir=so_dir,
                top_n=top_n,
                stat_method=stat_method,
                output_root=output_root,
                subprocess_timeout_sec=timeout_sec,
                extra_args=extras or None,
                prompt_only=False,
                import_llm_results=inferred_json,
            )
            if not ok:
                logging.warning(
                    'Agent mode: inference results import failed for scene=%s step=%s: %s',
                    self.scene_dir,
                    step_dir,
                    inferred_json,
                )
                return False
            recovered_cnt = self._count_recovered_function_names(out_dir)
            if recovered_cnt <= 0:
                logging.warning(
                    'Agent mode: inference produced no valid function names for scene=%s step=%s; '
                    'skip symbol replacement to avoid stale/placeholder outputs',
                    self.scene_dir,
                    step_dir,
                )
                self._cleanup_stale_symbol_recovery_outputs(step_dir, output_root)
                return False
            logging.info(
                'Agent mode: symbol recovery completed with agent inference for scene=%s step=%s (%s)',
                self.scene_dir,
                step_dir,
                inferred_json,
            )
        return True

    @staticmethod
    def _count_recovered_function_names(out_dir: Path) -> int:
        """统计本轮 symbol_recovery_results.json 中有效推断名数量。"""
        result_path = out_dir / 'symbol_recovery_results.json'
        if not result_path.is_file():
            return 0
        try:
            payload = json.loads(result_path.read_text(encoding='utf-8', errors='replace'))
        except (OSError, json.JSONDecodeError):
            return 0
        if isinstance(payload, dict):
            items = payload.get('functions') or payload.get('results') or payload.get('tasks') or []
        elif isinstance(payload, list):
            items = payload
        else:
            items = []
        cnt = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            fn = str(it.get('function_name') or it.get('inferred_name') or '').strip()
            if fn:
                cnt += 1
        return cnt

    def _cleanup_stale_symbol_recovery_outputs(self, step_dir: str, output_root: Optional[str]) -> None:
        """当本轮无有效推断时，清理可能遗留的旧替换产物，避免误判成功。"""
        out_dir = default_symbol_recovery_output_dir(self.scene_dir, step_dir, output_root)
        candidates = [
            out_dir / 'symbol_recovery_external_results.json',
            Path(self.scene_dir) / 'hiperf' / step_dir / 'symbol_recovery_replacements.json',
            Path(self.scene_dir) / 'hiperf' / step_dir / 'hiperf_report_with_inferred_symbols.html',
        ]
        for p in candidates:
            try:
                if p.is_file():
                    p.unlink()
            except OSError:
                continue

    def _dump_load_decomposition_top_symbols(
        self, step_dir: str, perf_db_path: str, out_dir: Path, *, so_dir: Optional[str], top_n: int
    ) -> Optional[Path]:
        """从负载拆解数据（perf.json 的 counts[1]）提取待恢复 TopN 符号并落盘。"""
        from_excel = self._extract_top_symbols_from_load_excel(so_dir=so_dir, top_n=top_n)
        if from_excel:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / 'load_decomposition_top_symbols.json'
            payload = {'step': step_dir, 'top_n': top_n, 'symbols': from_excel, 'source': 'ecol_load_perf'}
            try:
                out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
                logging.info('Dumped load-decomposition top symbols from excel: %s (%d)', out_path, len(from_excel))
                return out_path
            except OSError:
                return None

        perf_json = Path(perf_db_path).parent / 'perf.json'
        if not perf_json.is_file():
            return None
        try:
            data = json.loads(perf_json.read_text(encoding='utf-8', errors='replace'))
        except (OSError, json.JSONDecodeError):
            return None
        symbol_map = data.get('SymbolMap') or {}
        file_list = data.get('symbolsFileList') or []
        recs = data.get('recordSampleInfo') or []
        if not isinstance(symbol_map, dict) or not isinstance(file_list, list) or not isinstance(recs, list):
            return None

        allowed_so_names = self._collect_allowed_so_names(so_dir)
        agg: dict[str, dict[str, object]] = {}
        for ev in recs:
            for proc in ev.get('processes', []) if isinstance(ev, dict) else []:
                for th in proc.get('threads', []) if isinstance(proc, dict) else []:
                    for lib in th.get('libs', []) if isinstance(th, dict) else []:
                        for fn in lib.get('functions', []) if isinstance(lib, dict) else []:
                            if not isinstance(fn, dict):
                                continue
                            sid = str(fn.get('symbol'))
                            s_info = symbol_map.get(sid) or {}
                            if not isinstance(s_info, dict):
                                continue
                            symbol = str(s_info.get('symbol') or '').strip()
                            if not self._is_offset_symbol(symbol):
                                continue
                            so_name, normalized_address = self._normalize_offset_symbol(symbol)
                            if not normalized_address:
                                continue
                            if allowed_so_names and so_name not in allowed_so_names:
                                continue
                            file_idx = s_info.get('file')
                            file_path = ''
                            if isinstance(file_idx, int) and 0 <= file_idx < len(file_list):
                                file_path = str(file_list[file_idx] or '')
                            if self._is_system_symbol(symbol, file_path):
                                continue
                            counts = fn.get('counts') or []
                            self_cost = int(counts[1]) if isinstance(counts, list) and len(counts) > 1 and counts[1] else 0
                            if self_cost <= 0:
                                continue
                            key = f'{file_path}::{normalized_address}'
                            if key not in agg:
                                agg[key] = {
                                    'file_path': file_path,
                                    'address': normalized_address,
                                    'so_name': so_name,
                                    'event_count': 0,
                                    'call_count': 0,
                                }
                            agg[key]['event_count'] = int(agg[key]['event_count']) + self_cost
                            agg[key]['call_count'] = int(agg[key]['call_count']) + 1
        ranked = sorted(agg.values(), key=lambda x: int(x.get('event_count') or 0), reverse=True)[:top_n]
        if not ranked:
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'load_decomposition_top_symbols.json'
        payload = {'step': step_dir, 'top_n': top_n, 'symbols': ranked}
        try:
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            logging.info('Dumped load-decomposition top symbols: %s (%d)', out_path, len(ranked))
            return out_path
        except OSError:
            return None

    @staticmethod
    def _is_offset_symbol(symbol: str) -> bool:
        """仅保留需要恢复的偏移地址符号（如 libxxx.so+0x1234）。"""
        if not symbol:
            return False
        return re.search(r'\+0x[0-9a-fA-F]+$', symbol) is not None

    @staticmethod
    def _normalize_offset_symbol(symbol: str) -> tuple[str, str]:
        """标准化地址为 libxxx.so+0x...，并返回 so_name。"""
        m = re.search(r'([^/\\\\]+\.so)\+(0x[0-9a-fA-F]+)$', symbol)
        if not m:
            return '', ''
        so_name = m.group(1)
        offset = m.group(2).lower()
        return so_name, f'{so_name}+{offset}'

    @staticmethod
    def _collect_allowed_so_names(so_dir: Optional[str]) -> set[str]:
        """收集 so_dir 下可恢复库名，用于过滤系统库噪音。"""
        if not so_dir:
            return set()
        root = Path(so_dir)
        if not root.exists():
            return set()
        if root.is_file() and root.suffix == '.so':
            return {root.name}
        names: set[str] = set()
        try:
            for p in root.rglob('*.so'):
                names.add(p.name)
        except OSError:
            return set()
        return names

    @staticmethod
    def _is_system_symbol(symbol: str, file_path: str) -> bool:
        """系统 SO 不参与恢复（设备上不可导出）。"""
        s = (symbol or '').lower()
        fp = (file_path or '').lower()
        system_prefixes = (
            '/system/',
            '/vendor/',
            '/apex/',
            '/chip_prod/',
            '/lib/',
            '/lib64/',
        )
        if any(fp.startswith(p) for p in system_prefixes):
            return True
        if any(p in s for p in ('/system/', '/vendor/', '/apex/')):
            return True
        return False

    def _extract_top_symbols_from_load_excel(self, *, so_dir: Optional[str], top_n: int) -> list[dict]:
        """优先从负载拆解导出的 ecol_load_perf_*.xlsx 提取 TopN 符号。"""
        report_dir = Path(self.scene_dir) / 'report'
        if not report_dir.is_dir():
            return []
        excels = sorted(report_dir.glob('ecol_load_perf_*.xlsx'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not excels:
            return []
        excel_path = excels[0]
        try:
            df = pd.read_excel(excel_path, sheet_name='ecol_load_hiperf_detail')
        except Exception:
            return []
        if df is None or df.empty:
            return []
        cols = [str(c) for c in df.columns]
        symbol_col = next((c for c in cols if 'Symbol' in c or 'symbol' in c.lower()), None)
        if not symbol_col:
            return []
        load_candidates = [
            c
            for c in cols
            if (('指令' in c) or ('instruction' in c.lower()))
            and ('Total' not in c and 'total' not in c.lower())
        ]
        if not load_candidates:
            return []
        # 优先使用“符号级指令数”列（通常列名最短，如“指令数/ָ����”），避免误选进程/线程总量列
        load_col = sorted(load_candidates, key=lambda x: len(str(x).strip()))[0]

        agg: dict[str, dict[str, object]] = {}
        for _, row in df.iterrows():
            if self._is_sys_sdk_row(row):
                continue
            symbol = str(row.get(symbol_col) or '').strip()
            if not self._is_offset_symbol(symbol):
                continue
            so_name, normalized_address = self._normalize_offset_symbol(symbol)
            if not normalized_address:
                continue
            file_path = str(row.get('文件') or row.get('file') or '').strip()
            if self._is_system_symbol(symbol, file_path):
                continue
            try:
                event_count = int(float(row.get(load_col) or 0))
            except (TypeError, ValueError):
                event_count = 0
            if event_count <= 0:
                continue
            if normalized_address not in agg:
                agg[normalized_address] = {
                    'file_path': file_path,
                    'address': normalized_address,
                    'so_name': so_name,
                    'event_count': 0,
                    'call_count': 0,
                }
            agg[normalized_address]['event_count'] = int(agg[normalized_address]['event_count']) + event_count
            agg[normalized_address]['call_count'] = int(agg[normalized_address]['call_count']) + 1
        ranked = sorted(agg.values(), key=lambda x: int(x.get('event_count') or 0), reverse=True)[:top_n]
        return ranked

    @staticmethod
    def _is_sys_sdk_row(row: pd.Series) -> bool:
        """按分类过滤系统 SO：SYS_SDK 统一视为系统库，不参与恢复。"""
        try:
            # 精确列优先（不同导表可能字段名不同）
            for key in ('category_name', 'categoryName', 'so_category', 'component_category'):
                if key in row and str(row.get(key) or '').strip().upper() == 'SYS_SDK':
                    return True
            for key in ('category', 'component_category_id'):
                if key in row:
                    val = str(row.get(key) or '').strip()
                    if val == '4':  # ComponentCategory.SYS_SDK
                        return True
            # 兜底：行内任一字段出现 SYS_SDK 文本
            for v in row.values:
                if isinstance(v, str) and 'SYS_SDK' in v.upper():
                    return True
        except Exception:
            return False
        return False

    def _run_agent_inference_for_symbol_recovery(
        self, out_dir: Path, *, timeout_sec: Optional[float]
    ) -> Optional[str]:
        """
        在同一次 update 内执行 Agent 推断，产出 external_results.json 并用于后续导入回填。
        """
        tasks = out_dir / 'symbol_recovery_llm_tasks.json'
        if not tasks.is_file():
            return None
        output_json = out_dir / 'symbol_recovery_external_results.json'
        if output_json.is_file():
            return str(output_json)
        sr_root = resolve_symbol_recovery_root()
        if sr_root is None:
            logging.warning('Agent inference skipped: symbol recovery root not found')
            return None

        env_cmd = (os.environ.get('HAPRAY_SYMBOL_RECOVERY_AGENT_CMD') or '').strip()
        if env_cmd:
            rendered = (
                env_cmd.replace('{tasks}', str(tasks))
                .replace('{output}', str(output_json))
                .replace('{out_dir}', str(out_dir))
                .replace('{scene}', self.scene_dir)
            )
            cmd = rendered
            use_shell = True
            timeout = None
            if timeout_sec and timeout_sec > 0:
                timeout = max(60, int(timeout_sec))
            logging.info('Running symbol_recovery agent inference command: %s', cmd)
            try:
                cp = subprocess.run(
                    cmd,
                    cwd=str(sr_root),
                    timeout=timeout,
                    check=False,
                    shell=use_shell,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    capture_output=True,
                )
            except subprocess.TimeoutExpired:
                logging.warning('Agent inference command timed out')
                return None
            except OSError as e:
                logging.warning('Agent inference command failed to start: %s', e)
                return None
            if cp.stdout:
                logging.info(cp.stdout[:8000])
            if cp.stderr:
                logging.info(cp.stderr[:8000])
            if cp.returncode != 0:
                logging.warning('Agent inference command exited with code %s', cp.returncode)
                return None
            if not output_json.is_file():
                logging.warning('Agent inference command completed but output missing: %s', output_json)
                return None
            return str(output_json)

        tmo = max(60, int(timeout_sec)) if timeout_sec and timeout_sec > 0 else None
        if not run_symbol_recovery_agent_step2(
            sr_root,
            tasks,
            output_json,
            timeout_sec=tmo,
            delay=0.5,
            resume=False,
            model=None,
        ):
            logging.warning('Agent inference Step2 did not produce: %s', output_json)
            return None
        return str(output_json)

    def _maybe_embed_symbol_recovery_report(
        self, step_dir: str, perf_db_path: str, generated_html: Optional[Path] = None
    ) -> None:
        """符号恢复成功后，将符号恢复报告嵌入 hiperf_report.html（iframe）。

        COMMUNITY mode: 优先嵌入增强版火焰图 HTML，回退到独立分析报告。
        SIMPLE mode:    增强版 HTML 已是完整页面，只嵌入独立分析报告不做重复嵌入。
        """
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        stat_method = (Config.get('symbol_recovery_stat_method', 'event_count') or 'event_count').strip()
        if stat_method not in ('event_count', 'call_count'):
            stat_method = 'event_count'
        output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
        out_dir = default_symbol_recovery_output_dir(self.scene_dir, step_dir, output_root)
        hiperf = Path(perf_db_path).parent / 'hiperf_report.html'

        if Config.get('mode') == Mode.COMMUNITY:
            # COMMUNITY mode: 原始行为，优先嵌入增强版 HTML
            generated = generated_html or (hiperf.parent / symbol_recovery_replaced_html_name(hiperf.name))
            detail = generated if generated.is_file() else out_dir / symbol_recovery_report_name(stat_method, top_n)
            embed_symbol_recovery_report_into_hiperf_html(hiperf, detail)
        else:
            # SIMPLE mode: 增强 HTML 已是完整替代品，只嵌入独立分析报告
            analysis_report = out_dir / symbol_recovery_report_name(stat_method, top_n)
            if analysis_report.is_file():
                embed_symbol_recovery_report_into_hiperf_html(hiperf, analysis_report)
            else:
                logging.info(
                    'Standalone analysis report not found (%s), skip embedding. '
                    'Enhanced HTML %s is already a complete replacement.',
                    analysis_report,
                    generated_html or (hiperf.parent / symbol_recovery_replaced_html_name(hiperf.name)),
                )

    def _maybe_generate_symbol_recovery_html(self, step_dir: str) -> Optional[Path]:
        """在 update 生成新的 hiperf_report.html 后，再补跑 symbol_recovery Step4。"""
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        stat_method = (Config.get('symbol_recovery_stat_method', 'event_count') or 'event_count').strip()
        if stat_method not in ('event_count', 'call_count'):
            stat_method = 'event_count'
        output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
        return maybe_generate_symbol_recovery_html_for_step(
            self.scene_dir,
            step_dir,
            top_n=top_n,
            stat_method=stat_method,
            output_root=output_root,
        )

    @staticmethod
    def convert_kind_to_json() -> str:
        kind = Config.get('kind', None)
        if kind is None:
            return ''

        kind_entry = {'name': 'APP_SO', 'kind': 1, 'components': []}

        for category in Config.get('kind', None):
            component = {'name': category['name'], 'files': category['files']}

            if 'thread' in category:
                component['threads'] = category['thread']

            kind_entry['components'].append(component)

        return json.dumps([kind_entry])

    @staticmethod
    def generate_hiperf_report(perf_path: str) -> Optional[str]:
        """生成火焰图报告，返回原始JSON字符串"""
        report_file = os.path.join(os.path.dirname(perf_path), 'hiperf_report.html')
        template_file = os.path.join(ExeUtils.get_tools_dir('web', 'hiperf_report_template.html'))
        if not os.path.exists(template_file):
            logging.warning('Not found file %s', template_file)
            return None
        perf_json_file = os.path.join(os.path.dirname(perf_path), 'perf.json')
        if not os.path.exists(perf_json_file):
            logging.warning('Not found file %s', perf_json_file)
            return None

        with open(perf_json_file, encoding='utf-8') as perf_json_file:
            all_json = perf_json_file.read()

        script_start = '<script id="record_data" type="application/gzip+json;base64">'
        script_end = '</script></body></html>'

        # 为HTML报告压缩数据
        compressed_bytes = zlib.compress(all_json.encode('utf-8'), level=9)
        base64_bytes = base64.b64encode(compressed_bytes)
        base64_all_json_str = base64_bytes.decode('ascii')

        with open(template_file, encoding='utf-8') as html_file:
            html_str = html_file.read()
        with open(report_file, 'w', encoding='utf-8') as report_html_file:
            report_html_file.write(html_str)
            report_html_file.write(script_start + base64_all_json_str + script_end)

        # 返回原始JSON字符串，供后续处理
        return all_json

    @staticmethod
    def filter_and_move_symbols(data, filter_rules):
        """
        在JSON数据中根据多个过滤规则过滤并移动符号到新的库，仅从指定源库拆分

        参数:
        data: 原始JSON数据
        filter_rules: 过滤规则列表，每个规则是一个字典，包含:
            - filter_symbols: 用于筛选符号的字符串列表（如["v8::", "Builtins_"]）
            - new_file: 新库的名称（如"/system/lib64/libarkweb_v8.so"）
            - source_file: 要拆分的源库名称（如"libarkweb_engine.so"）
        """
        # 预处理：为所有新库添加条目并记录索引映射
        new_lib_indices = {}
        for rule in filter_rules:
            new_lib_name = rule['new_file']
            if new_lib_name not in data['symbolsFileList']:
                data['symbolsFileList'].append(new_lib_name)
                new_lib_indices[new_lib_name] = len(data['symbolsFileList']) - 1

        # 处理每个过滤规则
        for rule in filter_rules:
            filter_str_list = rule['filter_symbols']  # 现在是一个字符串列表
            new_lib_name = rule['new_file']
            source_lib_name_regex = re.compile(rule['source_file'])
            filter_symbols_regex = [re.compile(s) for s in rule['filter_symbols']]

            # 获取新库的索引
            new_index = new_lib_indices[new_lib_name]

            # 查找源库的索引
            source_lib_indices = set()
            for idx, lib_path in enumerate(data['symbolsFileList']):
                if source_lib_name_regex.match(lib_path):
                    source_lib_indices.add(idx)

            if not source_lib_indices:
                logging.warning("警告: 未找到源库 '%s'，跳过符号拆分", rule['source_file'])
                continue

            filter_strs = ', '.join(f"'{fs}'" for fs in filter_str_list)
            logging.info("处理规则: 从 '%s' 移动包含 %s 的符号到 '%s'", rule['source_file'], filter_strs, new_lib_name)
            logging.info("找到源库 '%s' 的索引: %s", rule['source_file'], source_lib_indices)

            # 收集包含任一过滤字符串的符号的symbol ID
            filtered_symbol_ids = set()

            # 遍历SymbolMap，修改file字段并收集相关信息
            for key, sym_info in data['SymbolMap'].items():
                # 只处理源库中的符号
                if sym_info['file'] in source_lib_indices:
                    # 检查符号是否包含任一过滤字符串
                    symbol = sym_info['symbol']
                    for symbol_regex in filter_symbols_regex:
                        if symbol_regex.match(symbol):
                            # 记录symbol ID
                            symbol_id = int(key)
                            filtered_symbol_ids.add(symbol_id)

                            # 修改file字段为新的索引
                            sym_info['file'] = new_index
                            break

            logging.info('从源库中找到 %s 个匹配 %s 的符号', len(filtered_symbol_ids), filter_strs)
            PerfAnalyzer.process_record_sample(data, source_lib_indices, filtered_symbol_ids, new_index)

        return data

    @staticmethod
    def process_record_sample(data, source_lib_indices, filtered_symbol_ids, new_index):
        # 处理recordSampleInfo - 只遍历源库
        if 'recordSampleInfo' not in data:
            return
        for event_info in data['recordSampleInfo']:
            for process_info in event_info.get('processes', []):
                for thread_info in process_info.get('threads', []):
                    PerfAnalyzer.update_thread_libs(source_lib_indices, filtered_symbol_ids, new_index, thread_info)

    @staticmethod
    def update_thread_libs(source_lib_indices, filtered_symbol_ids, new_index, thread_info):
        # 为当前线程创建新的lib对象
        new_lib_obj = {'fileId': new_index, 'eventCount': 0, 'functions': []}

        # 处理线程中的每个lib
        libs = thread_info.get('libs', [])

        # 只处理源库
        for lib in libs:
            file_id = lib.get('fileId')
            if file_id not in source_lib_indices:
                continue  # 跳过非源库

            # 分离匹配和不匹配的函数
            filtered_functions = []
            remaining_functions = []
            filtered_event_count = 0

            for func in lib.get('functions', []):
                if func.get('symbol') in filtered_symbol_ids:
                    filtered_functions.append(func)
                    # 累加counts[1]的值
                    if len(func.get('counts', [])) > 1:
                        filtered_event_count += func['counts'][1]
                else:
                    remaining_functions.append(func)

            # 如果有匹配的函数，更新原lib和新lib
            if filtered_functions:
                # 更新原lib
                lib['functions'] = remaining_functions
                lib['eventCount'] = max(0, lib.get('eventCount', 0) - filtered_event_count)

                # 更新新lib
                new_lib_obj['functions'].extend(filtered_functions)
                new_lib_obj['eventCount'] += filtered_event_count

        # 如果有匹配的函数，将新lib添加到线程的libs中
        if new_lib_obj['functions']:
            libs.append(new_lib_obj)

    @staticmethod
    def apply_symbol_split_rules(perf_json_file: str) -> str:
        """应用符号拆分规则"""
        with open(perf_json_file, errors='ignore', encoding='UTF-8') as json_file:
            data = json.load(json_file)
        rules = []
        config_file = os.path.join(CommonUtils.get_project_root(), 'sa-cmd', 'res', 'perf', 'symbol_split.json')
        # 1. 从配置文件加载规则
        if config_file and os.path.exists(config_file):
            with open(config_file, encoding='UTF-8') as f:
                rules.extend(json.load(f))

        return json.dumps(PerfAnalyzer.filter_and_move_symbols(data, rules))
