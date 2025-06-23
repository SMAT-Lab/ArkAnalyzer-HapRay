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
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from hapray.analyze.base_analyzer import BaseAnalyzer

# Configuration constants
MAX_WORKERS = 4  # Optimal for I/O-bound tasks
ANALYZER_CLASSES = [
    'ComponentReusableAnalyzer',
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


def data_analyze(scene_dir: str):
    """Main entry point for data analysis pipeline.

    Args:
        scene_dir: Root directory containing scene data
    """
    analyzers = _initialize_analyzers(scene_dir)
    if not analyzers:
        logging.error("No analyzers initialized. Aborting analysis.")
        return

    htrace_path = os.path.join(scene_dir, 'htrace')
    if not os.path.exists(htrace_path):
        logging.error(f"htrace directory not found: {htrace_path}")
        return

    try:
        start_time = time.perf_counter()
        _process_steps_parallel(htrace_path, scene_dir, analyzers)
        elapsed = time.perf_counter() - start_time
        logging.info(f"Parallel processing completed in {elapsed:.2f} seconds")
    except Exception as e:
        logging.exception(f"Analysis pipeline failed: {str(e)}")
    finally:
        _finalize_analyzers(analyzers)


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
            logging.info(f"Initialized analyzer: {analyzer_class}")
        except (ImportError, AttributeError) as e:
            logging.error(f"Failed to initialize {analyzer_class}: {str(e)}")
    return analyzers


def _process_steps_parallel(
        htrace_path: str,
        scene_dir: str,
        analyzers: List[BaseAnalyzer]
):
    """Process all steps in parallel using a thread pool.

    Args:
        htrace_path: Path to htrace directory
        scene_dir: Root scene directory
        analyzers: List of analyzer instances
    """
    # Collect all valid step directories
    step_dirs = []
    for step_dir in os.listdir(htrace_path):
        step_path = os.path.join(htrace_path, step_dir)
        if os.path.isdir(step_path):
            step_dirs.append(step_dir)

    if not step_dirs:
        logging.warning("No valid step directories found")
        return

    logging.info(f"Processing {len(step_dirs)} steps with {MAX_WORKERS} workers")

    # Create a thread pool executor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Prepare futures for all steps
        futures = {}
        for step_dir in step_dirs:
            future = executor.submit(
                _process_single_step,
                step_dir,
                htrace_path,
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
                logging.debug(f"Step {step_dir} processed successfully")
            except Exception as e:
                error_count += 1
                logging.error(f"Step {step_dir} processing failed: {str(e)}")

    logging.info(f"Step processing completed: {success_count} successes, {error_count} errors")


def _process_single_step(
        step_dir: str,
        htrace_path: str,
        scene_dir: str,
        analyzers: List[BaseAnalyzer]
):
    """Process a single step directory with all analyzers.

    Args:
        step_dir: Step directory name
        htrace_path: Path to htrace directory
        scene_dir: Root scene directory
        analyzers: List of analyzer instances
    """
    step_path = os.path.join(htrace_path, step_dir)
    trace_db = os.path.join(step_path, 'trace.db')
    perf_db = os.path.join(scene_dir, 'hiperf', step_dir, 'perf.db')

    if not all(os.path.exists(db) for db in [trace_db, perf_db]):
        raise FileNotFoundError(f"Missing DB files for step {step_dir}")

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
            logging.error(f"Analyzer {type(analyzer).__name__} failed on {step_dir}: {str(e)}")


def _finalize_analyzers(analyzers: List[BaseAnalyzer]):
    """Finalize all analyzers and write reports."""
    for analyzer in analyzers:
        try:
            analyzer.write_report()
            logging.info(f"Report generated for {type(analyzer).__name__}")
        except Exception as e:
            logging.error(f"Failed to generate report for {type(analyzer).__name__}: {str(e)}")