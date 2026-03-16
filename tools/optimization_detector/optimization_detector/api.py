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

"""
Agentic API for optimization_detector.
Provides programmable entry points for Agent/Skill invocation.
"""

import logging
import multiprocessing
import os
from pathlib import Path
from typing import Any

from optimization_detector.errors import OptDetectorInputError, OptDetectorNoFilesError
from optimization_detector.file_info import FileCollector, FileInfo
from optimization_detector.optimization_detector import OptimizationDetector
from optimization_detector.report_formatters import OutputFormat, ReportFormatterFactory

logger = logging.getLogger(__name__)


def _resolve_input_paths(input_path: str | list[str] | Path) -> list[str]:
    """Resolve input to a list of absolute paths (files or directories)."""
    if isinstance(input_path, Path):
        input_path = str(input_path)
    if isinstance(input_path, str):
        input_path = [input_path]

    resolved = []
    for p in input_path:
        p = str(p)
        if not os.path.exists(p):
            raise OptDetectorInputError(f"Input path does not exist: {p}", path=p)
        resolved.append(os.path.abspath(p))
    return resolved


def check_prerequisites() -> tuple[bool, list[str], list[str]]:
    """
    Check if prerequisites for optimization detection are satisfied.

    Returns:
        Tuple of (ok, missing_items, suggestions).
        - ok: True if all prerequisites are met.
        - missing_items: List of missing dependencies or issues.
        - suggestions: List of suggested actions to fix issues.
    """
    missing = []
    suggestions = []

    # Check TensorFlow
    try:
        import tensorflow as tf  # noqa: F401
    except ImportError:
        missing.append("tensorflow")
        suggestions.append("pip install tensorflow")

    # Check elftools
    try:
        from elftools.elf.elffile import ELFFile  # noqa: F401
    except ImportError:
        missing.append("pyelftools")
        suggestions.append("pip install pyelftools")

    # Check model file
    try:
        from importlib.resources import files
        model_path = files('optimization_detector').joinpath('models/aarch64-flag-lstm-converted.h5')
        if not os.path.exists(str(model_path)):
            missing.append("model file (aarch64-flag-lstm-converted.h5)")
            suggestions.append("Ensure optimization_detector package is properly installed with model assets")
    except Exception as e:
        missing.append(f"model resolution: {e}")
        suggestions.append("Reinstall optimization_detector package")

    ok = len(missing) == 0
    return ok, missing, suggestions


def detect_optimization(
    input_path: str | list[str] | Path,
    *,
    output: str | None = None,
    output_format: str | list[str] | None = None,
    jobs: int = 1,
    timeout: int | None = None,
    enable_lto: bool = True,
    enable_opt: bool = True,
    return_dict: bool = True,
    save_reports: bool = True,
) -> dict[str, Any]:
    """
    Detect optimization level and LTO for binary files (SO/AR/HAP/HSP/APK/HAR).

    Agentic API: callable from Python, returns structured result for Agent parsing.

    Args:
        input_path: File or directory path(s). Supports .so, .a, .hap, .hsp, .apk, .har.
        output: Output file path. Default 'binary_analysis_report.xlsx' when save_reports=True.
        output_format: 'excel'|'json'|'csv'|'xml' or list. Inferred from output path if None.
        jobs: Number of parallel workers (default 1).
        timeout: Timeout per file in seconds (default None).
        enable_lto: Enable LTO detection (default True).
        enable_opt: Enable optimization level detection (default True).
        return_dict: Return structured dict (default True). If False, returns raw data.
        save_reports: Save reports to files (default True). If False, only returns in-memory result.

    Returns:
        Dict with keys:
        - success: bool
        - summary: {file_count, analyzed_count, failed_count, skipped_count, output_files, ...}
        - data: list of (sheet_name, records) when return_dict=True
        - error: str (only when success=False)

    Raises:
        OptDetectorInputError: Input path does not exist.
        OptDetectorNoFilesError: No valid binary files found.
    """
    resolved = _resolve_input_paths(input_path)
    file_collector = FileCollector()
    try:
        all_file_infos: list[FileInfo] = []
        for p in resolved:
            infos = file_collector.collect_binary_files(p)
            all_file_infos.extend(infos)

        if not all_file_infos:
            raise OptDetectorNoFilesError(
                f"No valid binary files found in: {resolved}",
                path=resolved[0] if resolved else None,
            )

        logger.info("Collecting binary files from: %s, found %d files", resolved, len(all_file_infos))

        multiprocessing.freeze_support()
        detector = OptimizationDetector(
            workers=jobs,
            timeout=timeout,
            enable_lto=enable_lto,
            enable_opt=enable_opt,
        )
        raw_data = detector.detect_optimization(all_file_infos)

        # raw_data: list of (sheet_name, pd.DataFrame)
        summary = _build_summary(raw_data, all_file_infos)
        output_files: list[str] = []

        if save_reports:
            out_path = output or "binary_analysis_report.xlsx"
            fmt_input = output_format
            if fmt_input is not None and not isinstance(fmt_input, list):
                fmt_input = [fmt_input]
            formats = ReportFormatterFactory.normalize_output_formats(fmt_input, out_path)
            base_path = out_path if len(formats) <= 1 else os.path.splitext(out_path)[0]
            for fmt in formats:
                fmt_enum = OutputFormat(fmt)
                ext = ReportFormatterFactory.get_extension_for_format(fmt_enum)
                file_path = base_path if len(formats) == 1 else base_path + ext
                formatter = ReportFormatterFactory.create(fmt_enum, file_path)
                formatter.save(raw_data)
                output_files.append(formatter.output_path)
            summary["output_files"] = output_files

        if not return_dict:
            return {"success": True, "summary": summary, "data": raw_data, "error": None}

        # Convert to list of dicts for Agent-friendly format
        data = []
        for sheet_name, df in raw_data:
            records = df.to_dict("records")
            data.append({"sheet": sheet_name, "records": records, "count": len(records)})

        return {
            "success": True,
            "summary": summary,
            "data": data,
            "error": None,
        }
    finally:
        file_collector.cleanup()


def _build_summary(raw_data: list[tuple[str, Any]], file_infos: list[FileInfo]) -> dict[str, Any]:
    """Build summary dict from raw data."""
    if not raw_data:
        return {
            "file_count": len(file_infos),
            "analyzed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "output_files": [],
        }

    _, df = raw_data[0]
    status_col = "Status" if "Status" in df.columns else None
    analyzed = failed = skipped = 0
    if status_col:
        for s in df[status_col]:
            s_str = str(s)
            if "Successfully Analyzed" in s_str:
                analyzed += 1
            elif "Analysis Failed" in s_str:
                failed += 1
            else:
                skipped += 1

    return {
        "file_count": len(file_infos),
        "analyzed_count": int(analyzed),
        "failed_count": int(failed),
        "skipped_count": int(skipped),
        "output_files": [],
    }
