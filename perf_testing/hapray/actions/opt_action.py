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

import argparse
import logging

from hapray import VERSION
from hapray.optimization_detector.optimization_detector import OptimizationDetector


class OptAction:
    """Handles binary optimization analysis actions."""

    @staticmethod
    def execute(args):
        """Executes binary optimization detection workflow."""
        parser = argparse.ArgumentParser(description="Analyze binary files for optimization flags",
                                         prog='ArkAnalyzer-HapRay opt')
        parser.add_argument('-v', '--version',
                            action='version',
                            version=f'%(prog)s {VERSION}',
                            help="Show program's version number and exit"
                            )
        parser.add_argument("--input", "-i", required=True,
                            help="Directory containing binary files to analyze")
        parser.add_argument("--output", "-o", default="binary_analysis_report.xlsx",
                            help="Output Excel file path (default: binary_analysis_report.xlsx)")
        parser.add_argument("--jobs", "-j", type=int, default=1,
                            help="Number of parallel jobs (default: 1)")
        parsed_args = parser.parse_args(args)

        logging.info(f"Starting binary optimization analysis on: {parsed_args.input}")
        detector = OptimizationDetector(parsed_args.jobs)
        detector.detect_optimization(parsed_args.input, parsed_args.output)
        logging.info(f"Analysis report saved to: {parsed_args.output}")
