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
from typing import List

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.exe_utils import ExeUtils

# Configuration constants
MAX_WORKERS = 4  # Optimal for I/O-bound tasks
ANALYZER_CLASSES = [
    'ComponentReusableAnalyzer',
    'PerfAnalyzer',
    'EmptyFrameAnalyzer',
    'FrameDropAnalyzer',
    'ColdStartAnalyzer',
    'GCAnalyzer',
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


def analyze_data(scene_dir: str) -> dict:
    """Main entry point for data analysis pipeline.

    Args:
        scene_dir: Root directory containing scene data
    """
    result = {}
    analyzers = _initialize_analyzers(scene_dir)
    if not analyzers:
        logging.error("No analyzers initialized. Aborting analysis.")
        return result

    hiperf_path = os.path.join(scene_dir, 'hiperf')
    if not os.path.exists(hiperf_path):
        logging.error("htrace directory not found: %s", hiperf_path)
        return result

    try:
        start_time = time.perf_counter()
        _process_steps_parallel(hiperf_path, scene_dir, analyzers)
        elapsed = time.perf_counter() - start_time
        logging.info("Parallel processing completed in %.2f seconds", elapsed)
    except Exception as e:
        logging.exception("Analysis pipeline failed: %s", str(e))
    finally:
        result = _finalize_analyzers(analyzers)
    return result


def _initialize_analyzers(scene_dir: str) -> List[BaseAnalyzer]:
    """Initialize all registered analyzers.

    Returns:
        List of initialized analyzer instances
    """
    analyzers = []
    for analyzer_class in ANALYZER_CLASSES:
        try:
            module_name = camel_to_snake(analyzer_class)
            module = __import__(f'hapray.analyze.{module_name}',
                                fromlist=[analyzer_class])
            cls = getattr(module, analyzer_class)
            analyzers.append(cls(scene_dir))
            logging.info("Initialized analyzer: %s", analyzer_class)
        except (ImportError, AttributeError) as e:
            logging.error("Failed to initialize %s: %s", analyzer_class, str(e))
    return analyzers


def _process_steps_parallel(
        hiperf_path: str,
        scene_dir: str,
        analyzers: List[BaseAnalyzer]
):
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
        logging.warning("No valid step directories found")
        return

    logging.info("Processing %d steps with %d workers", len(step_dirs), MAX_WORKERS)

    # Create a thread pool executor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Prepare futures for all steps
        futures = {}
        for step_dir in step_dirs:
            future = executor.submit(
                _process_single_step,
                step_dir,
                scene_dir,
                analyzers
            )
            futures[future] = step_dir

        # Process completed futures
        success_count = 0
        error_count = 0
        for future in as_completed(futures):
            step_dir = futures[future]
            try:
                future.result()  # Will re-raise any exceptions
                success_count += 1
                logging.debug("Step %s processed successfully", step_dir)
            except Exception as e:
                error_count += 1
                logging.error("Step %s processing failed: %s", step_dir, str(e))

    logging.info("Step processing completed: %d successes, %d errors", success_count, error_count)


def _process_single_step(
        step_dir: str,
        scene_dir: str,
        analyzers: List[BaseAnalyzer]
):
    """Process a single step directory with all analyzers.
    Args:
        step_dir: Step directory name
        scene_dir: Root scene directory
        analyzers: List of analyzer instances
    """
    htrace_file = os.path.join(scene_dir, 'htrace', step_dir, 'trace.htrace')
    trace_db = os.path.join(scene_dir, 'htrace', step_dir, 'trace.db')
    perf_file = os.path.join(scene_dir, 'hiperf', step_dir, 'perf.data')
    perf_db = os.path.join(scene_dir, 'hiperf', step_dir, 'perf.db')

    if not os.path.exists(perf_db) and os.path.exists(perf_file):
        logging.info("Converting perf to db for %s...", step_dir)
        if not ExeUtils.convert_data_to_db(perf_file, perf_db):
            logging.error("Failed to convert perf to db for %s", step_dir)
            return
    if not os.path.exists(trace_db) and os.path.exists(htrace_file):
        logging.info("Converting htrace to db for %s...", step_dir)
        if not ExeUtils.convert_data_to_db(htrace_file, trace_db):
            logging.error("Failed to convert htrace to db for %s", step_dir)
            return

    _run_analyzers(analyzers, step_dir, trace_db, perf_db)


def _run_analyzers(
        analyzers: List[BaseAnalyzer],
        step_dir: str,
        trace_db: str,
        perf_db: str
):
    """Execute all analyzers for a given step.

    Args:
        analyzers: List of analyzer instances
        step_dir: Current step directory name
        trace_db: Path to trace database
        perf_db: Path to perf database
    """
    for analyzer in analyzers:
        try:
            analyzer.analyze(step_dir, trace_db, perf_db)
        except Exception as e:
            logging.error("Analyzer %s failed on %s: %s", type(analyzer).__name__, step_dir, str(e))


def _finalize_analyzers(analyzers: List[BaseAnalyzer]) -> dict:
    """Finalize all analyzers and write reports."""
    result = {}
    for analyzer in analyzers:
        try:
            analyzer.write_report(result)
            logging.info("Report generated for %s", type(analyzer).__name__)
        except Exception as e:
            logging.error("Failed to generate report for %s: %s", type(analyzer).__name__, str(e))

    return result
