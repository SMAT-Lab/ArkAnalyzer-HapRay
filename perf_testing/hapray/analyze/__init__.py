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

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.exe_utils import ExeUtils

# Configuration constants
MAX_WORKERS = 8  # Optimal for I/O-bound tasks
ANALYZER_CLASSES = [
    'ComponentReusableAnalyzer',
    'PerfAnalyzer',
    'FrameLoadAnalyzer',  # 提前执行，作为数据收集前驱
    'EmptyFrameAnalyzer',  # 使用缓存的帧负载数据
    'FrameDropAnalyzer',  # 使用缓存的帧负载数据
    'VSyncAnomalyAnalyzer',  # VSync异常分析器
    'ColdStartAnalyzer',
    'GCAnalyzer',
    'FaultTreeAnalyzer',
    'CovAnalyzer',
    # Add more analyzers here
]


def camel_to_snake(name: str) -> str:
    """Convert CamelCase class name to snake_case module name.

    Example:
        'ComponentReusableAnalyzer' -> 'component_reusable_analyzer'
    """
    # Insert underscore before capital letters (except first character)
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    # Insert underscore between lowercase and capital letters
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def analyze_data(scene_dir: str, time_ranges: list[dict] = None) -> dict:
    """Main entry point for data analysis pipeline.

    Args:
        scene_dir: Root directory containing scene data
        time_ranges: Optional list of time range filters, each containing 'startTime' and 'endTime' in nanoseconds
    """
    total_start_time = time.time()
    logging.info('=== Starting data analysis pipeline for %s ===', scene_dir)

    result = {}

    # Phase 1: Initialize analyzers
    init_start_time = time.time()
    analyzers = _initialize_analyzers(scene_dir)
    init_time = time.time() - init_start_time
    logging.info('Phase 1: Analyzer initialization completed in %.2f seconds (%d analyzers)', init_time, len(analyzers))

    if not analyzers:
        logging.error('No analyzers initialized. Aborting analysis.')
        return result

    hiperf_path = os.path.join(scene_dir, 'hiperf')
    if not os.path.exists(hiperf_path):
        logging.error('hiperf directory not found: %s', hiperf_path)
        return result

    # Phase 2: Parallel step processing
    try:
        processing_start_time = time.time()
        logging.info('Phase 2: Starting parallel step processing...')
        _process_steps_parallel(hiperf_path, scene_dir, analyzers)
        processing_time = time.time() - processing_start_time
        logging.info('Phase 2: Parallel processing completed in %.2f seconds', processing_time)
    except Exception as e:
        processing_time = time.time() - processing_start_time
        logging.exception('Phase 2: Analysis pipeline failed after %.2f seconds: %s', processing_time, str(e))

    # Phase 3: Finalize and generate reports
    try:
        finalize_start_time = time.time()
        logging.info('Phase 3: Starting report finalization...')
        result = _finalize_analyzers(analyzers)
        finalize_time = time.time() - finalize_start_time
        logging.info('Phase 3: Report finalization completed in %.2f seconds', finalize_time)
    except Exception as e:
        finalize_time = time.time() - finalize_start_time
        logging.exception('Phase 3: Report finalization failed after %.2f seconds: %s', finalize_time, str(e))
        result = {}

    # Overall summary
    total_time = time.time() - total_start_time
    logging.info('=== Data analysis pipeline completed in %.2f seconds ===', total_time)
    logging.info(
        'Phase breakdown: Init=%.2fs, Processing=%.2fs, Finalization=%.2fs',
        init_time,
        processing_time if 'processing_time' in locals() else 0,
        finalize_time if 'finalize_time' in locals() else 0,
    )

    return result


def _initialize_analyzers(scene_dir: str) -> list[BaseAnalyzer]:
    """Initialize all registered analyzers.

    Returns:
        List of initialized analyzer instances
    """
    analyzers = []
    for analyzer_class in ANALYZER_CLASSES:
        try:
            module_name = camel_to_snake(analyzer_class)
            module = __import__(f'hapray.analyze.{module_name}', fromlist=[analyzer_class])
            cls = getattr(module, analyzer_class)
            analyzers.append(cls(scene_dir))
            logging.info('Initialized analyzer: %s', analyzer_class)
        except (ImportError, AttributeError) as e:
            logging.error('Failed to initialize %s: %s', analyzer_class, str(e))
    return analyzers


def _process_steps_parallel(hiperf_path: str, scene_dir: str, analyzers: list[BaseAnalyzer]):
    """Process all steps in parallel using a thread pool.

    Args:
        hiperf_path: Path to hiperf directory
        scene_dir: Root scene directory
        analyzers: List of analyzer instances
    """
    # Collect all valid step directories
    step_dirs = []
    for step_dir in os.listdir(hiperf_path):
        step_path = os.path.join(hiperf_path, step_dir)
        if os.path.isdir(step_path):
            step_dirs.append(step_dir)

    if not step_dirs:
        logging.warning('No valid step directories found')
        return

    logging.info('Processing %d steps with %d workers', len(step_dirs), MAX_WORKERS)

    # Create a thread pool executor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Prepare futures for all steps
        futures = {}
        for step_dir in step_dirs:
            future = executor.submit(_process_single_step, step_dir, scene_dir, analyzers)
            futures[future] = step_dir

        # Process completed futures with timing
        success_count = 0
        error_count = 0
        step_times = []

        for future in as_completed(futures):
            step_dir = futures[future]
            step_start = time.time()
            try:
                future.result()  # Will re-raise any exceptions
                success_count += 1
                step_time = time.time() - step_start
                step_times.append((step_dir, step_time))
                logging.info('Step %s processed successfully in %.2f seconds', step_dir, step_time)
            except Exception as e:
                error_count += 1
                step_time = time.time() - step_start
                step_times.append((step_dir, step_time))
                logging.error('Step %s processing failed after %.2f seconds: %s', step_dir, step_time, str(e))

    # Log step processing summary
    logging.info('Step processing completed: %d successes, %d errors', success_count, error_count)

    if step_times:
        # Sort by processing time, slowest first
        step_times.sort(key=lambda x: x[1], reverse=True)
        total_step_time = sum(time for _, time in step_times)
        avg_step_time = total_step_time / len(step_times)

        logging.info('Step processing time summary:')
        logging.info('  Total time: %.2f seconds, Average: %.2f seconds', total_step_time, avg_step_time)
        logging.info('  Step times (slowest first):')
        for step_dir, step_time in step_times:
            percentage = (step_time / total_step_time) * 100 if total_step_time > 0 else 0
            logging.info('    %s: %.2f seconds (%.1f%%)', step_dir, step_time, percentage)


def _process_single_step(step_dir: str, scene_dir: str, analyzers: list[BaseAnalyzer]):
    """Process a single step directory with all analyzers.
    Args:
        step_dir: Step directory name
        scene_dir: Root scene directory
        analyzers: List of analyzer instances
    """
    step_start_time = time.time()
    logging.info('Starting processing for step %s', step_dir)

    htrace_file = os.path.join(scene_dir, 'htrace', step_dir, 'trace.htrace')
    trace_db = os.path.join(scene_dir, 'htrace', step_dir, 'trace.db')
    perf_file = os.path.join(scene_dir, 'hiperf', step_dir, 'perf.data')
    perf_db = os.path.join(scene_dir, 'hiperf', step_dir, 'perf.db')

    # Data conversion phase
    conversion_start_time = time.time()

    if not os.path.exists(perf_db) and os.path.exists(perf_file):
        logging.info('Converting perf to db for %s...', step_dir)
        perf_convert_start = time.time()
        if not ExeUtils.convert_data_to_db(perf_file, perf_db):
            logging.error('Failed to convert perf to db for %s', step_dir)
            return
        perf_convert_time = time.time() - perf_convert_start
        logging.info('Perf conversion for %s completed in %.2f seconds', step_dir, perf_convert_time)

    if not os.path.exists(trace_db) and os.path.exists(htrace_file):
        logging.info('Converting htrace to db for %s...', step_dir)
        trace_convert_start = time.time()
        if not ExeUtils.convert_data_to_db(htrace_file, trace_db):
            logging.error('Failed to convert htrace to db for %s', step_dir)
            return
        trace_convert_time = time.time() - trace_convert_start
        logging.info('Htrace conversion for %s completed in %.2f seconds', step_dir, trace_convert_time)

    conversion_total_time = time.time() - conversion_start_time
    logging.info('Data conversion phase for %s completed in %.2f seconds', step_dir, conversion_total_time)

    # Analysis phase
    analysis_start_time = time.time()
    _run_analyzers(analyzers, step_dir, trace_db, perf_db)
    analysis_time = time.time() - analysis_start_time

    step_total_time = time.time() - step_start_time
    logging.info(
        'Step %s processing completed in %.2f seconds (conversion: %.2f, analysis: %.2f)',
        step_dir,
        step_total_time,
        conversion_total_time,
        analysis_time,
    )


def _run_analyzers(analyzers: list[BaseAnalyzer], step_dir: str, trace_db: str, perf_db: str):
    """Execute all analyzers for a given step.

    Args:
        analyzers: List of analyzer instances
        step_dir: Current step directory name
        trace_db: Path to trace database
        perf_db: Path to perf database
    """
    total_start_time = time.time()
    analyzer_times = []

    logging.info('Starting analysis for step %s with %d analyzers', step_dir, len(analyzers))

    for i, analyzer in enumerate(analyzers, 1):
        analyzer_name = type(analyzer).__name__
        start_time = time.time()

        try:
            logging.info('[%d/%d] Starting %s for step %s...', i, len(analyzers), analyzer_name, step_dir)
            analyzer.analyze(step_dir, trace_db, perf_db)

            elapsed_time = time.time() - start_time
            analyzer_times.append((analyzer_name, elapsed_time))

            logging.info(
                '[%d/%d] Completed %s for step %s in %.2f seconds',
                i,
                len(analyzers),
                analyzer_name,
                step_dir,
                elapsed_time,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            analyzer_times.append((analyzer_name, elapsed_time))

            logging.error(
                '[%d/%d] Analyzer %s failed on %s after %.2f seconds: %s',
                i,
                len(analyzers),
                analyzer_name,
                step_dir,
                elapsed_time,
                str(e),
            )

    total_elapsed = time.time() - total_start_time

    # 记录所有分析器的执行时间统计
    logging.info('Analysis completed for step %s in %.2f seconds total', step_dir, total_elapsed)
    logging.info('Analyzer execution times for step %s:', step_dir)

    # 按执行时间排序，最慢的在前面
    analyzer_times.sort(key=lambda x: x[1], reverse=True)
    for analyzer_name, elapsed_time in analyzer_times:
        percentage = (elapsed_time / total_elapsed) * 100 if total_elapsed > 0 else 0
        logging.info('  %s: %.2f seconds (%.1f%%)', analyzer_name, elapsed_time, percentage)


def _finalize_analyzers(analyzers: list[BaseAnalyzer]) -> dict:
    """Finalize all analyzers and write reports."""
    result = {}
    total_start_time = time.time()
    report_times = []

    logging.info('Starting report generation for %d analyzers', len(analyzers))

    for i, analyzer in enumerate(analyzers, 1):
        analyzer_name = type(analyzer).__name__
        start_time = time.time()

        try:
            logging.info('[%d/%d] Generating report for %s...', i, len(analyzers), analyzer_name)
            analyzer.write_report(result)

            elapsed_time = time.time() - start_time
            report_times.append((analyzer_name, elapsed_time))

            logging.info(
                '[%d/%d] Report generated for %s in %.2f seconds', i, len(analyzers), analyzer_name, elapsed_time
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            report_times.append((analyzer_name, elapsed_time))

            logging.error(
                '[%d/%d] Failed to generate report for %s after %.2f seconds: %s',
                i,
                len(analyzers),
                analyzer_name,
                elapsed_time,
                str(e),
            )

    total_elapsed = time.time() - total_start_time

    # 记录报告生成时间统计
    logging.info('Report generation completed in %.2f seconds total', total_elapsed)
    logging.info('Report generation times:')

    # 按执行时间排序，最慢的在前面
    report_times.sort(key=lambda x: x[1], reverse=True)
    for analyzer_name, elapsed_time in report_times:
        percentage = (elapsed_time / total_elapsed) * 100 if total_elapsed > 0 else 0
        logging.info('  %s: %.2f seconds (%.1f%%)', analyzer_name, elapsed_time, percentage)

    return result
