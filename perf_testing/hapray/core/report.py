import json
import logging
import os
import subprocess
from typing import List, Optional

from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FrameAnalyzer import FrameAnalyzer
from hapray.core.config.config import Config

class ReportGenerator:
    """Generates and updates performance analysis reports"""

    def __init__(self):
        self.perf_testing_dir = CommonUtils.get_project_root()
        self.hapray_cmd_path = self._get_hapray_cmd_path()

    def _get_hapray_cmd_path(self) -> str:
        """Get the absolute path to hapray-cmd.js"""
        cmd_path = os.path.abspath(os.path.join(
            self.perf_testing_dir, 'hapray-toolbox', 'hapray-cmd.js'
        ))

        if not os.path.exists(cmd_path):
            raise FileNotFoundError(f'HapRay command not found at {cmd_path}')

        return cmd_path

    def update_report(self, scene_dir: str, so_dir: Optional[str] = None) -> bool:
        """Update an existing performance report"""
        return self._generate_report(
            scene_dirs=[scene_dir],
            scene_dir=scene_dir,
            so_dir=so_dir,
            skip_round_selection=True
        )

    def generate_report(
            self,
            scene_dirs: List[str],
            scene_dir: str,
            so_dir: Optional[str] = None
    ) -> bool:
        """Generate a new performance analysis report"""
        return self._generate_report(
            scene_dirs,
            scene_dir,
            so_dir,
            skip_round_selection=False
        )

    def _generate_report(
            self,
            scene_dirs: List[str],
            scene_dir: str,
            so_dir: Optional[str],
            skip_round_selection: bool
    ) -> bool:
        """Core method for report generation and updating"""
        # Step 1: Select round (only for new reports)
        if not skip_round_selection:
            if not self._select_round(scene_dirs, scene_dir):
                logging.error("Round selection failed, aborting report generation")
                return False

        # Step 2: Perform perf analysis
        if not self._run_perf_analysis(scene_dir, so_dir):
            logging.error("Performance analysis failed, aborting report generation")
            return False

        # Step 3: Analyze frame drops
        self._analyze_frame_drops(scene_dir)

        # Step 4: Generate HTML report
        self._create_html_report(scene_dir)

        logging.info(f"Report successfully {'updated' if skip_round_selection else 'generated'} for {scene_dir}")
        return True

    def _select_round(self, scene_dirs: List[str], scene_dir: str) -> bool:
        """Select the best round for report generation"""
        if not scene_dirs:
            logging.error("No scene directories provided for round selection")
            return False

        cmd = [
            'node', self.hapray_cmd_path,
            'hapray', 'dbtools',
            '--choose',
            '-i', scene_dir
        ]

        logging.debug(f"Selecting round with command: {' '.join(cmd)}")
        return self._execute_hapray_command(cmd, "Round selection")

    def _run_perf_analysis(self, scene_dir: str, so_dir: Optional[str]) -> bool:
        """Run performance analysis"""
        cmd = ['node', self.hapray_cmd_path, 'hapray', 'dbtools', '-i', scene_dir]

        if so_dir:
            cmd.extend(['-s', so_dir])

        kind = self.convert_kind_to_json()
        if len(kind) > 0:
            cmd.extend(['-k', kind])

        logging.debug(f"Running perf analysis with command: {' '.join(cmd)}")
        return self._execute_hapray_command(cmd, "Performance analysis")

    def _analyze_frame_drops(self, scene_dir: str) -> None:
        """Analyze frame drops and log results"""
        logging.info(f"Starting frame drops analysis for {scene_dir}")

        try:
            if FrameAnalyzer.analyze_frame_drops(scene_dir):
                logging.info(f"Successfully analyzed frame drops for {scene_dir}")
            else:
                logging.warning(f"Frame drop analysis completed with warnings for {scene_dir}")
        except Exception as e:
            logging.error(f"Frame drop analysis failed for {scene_dir}: {str(e)}")

    def _create_html_report(self, scene_dir: str) -> None:
        """Create the final HTML report"""
        try:
            perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
            frame_data_path = os.path.join(scene_dir, 'htrace', 'frame_analysis_summary.json')
            template_path = os.path.join(
                self.perf_testing_dir, 'hapray-toolbox', 'res', 'report_template.html'
            )
            output_path = os.path.join(scene_dir, 'report', 'hapray_report.html')

            # Create directory structure if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Inject performance data
            self._inject_json_to_html(
                json_path=perf_data_path,
                placeholder='JSON_DATA_PLACEHOLDER',
                html_path=template_path,
                output_path=output_path
            )

            # Inject frame analysis data
            self._inject_json_to_html(
                json_path=frame_data_path,
                placeholder='FRAME_JSON_PLACEHOLDER',
                html_path=output_path,
                output_path=output_path
            )

            logging.info(f"HTML report created at {output_path}")
        except Exception as e:
            logging.error(f"Failed to create HTML report: {str(e)}")

    def _execute_hapray_command(self, cmd: List[str], action_name: str) -> bool:
        """Execute a hapray command with proper error handling"""
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.stdout:
                logging.debug(f"{action_name} output: {result.stdout}")

            if result.stderr:
                logging.warning(f"{action_name} warnings: {result.stderr}")

            logging.info(f"{action_name} completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            error_msg = f"{action_name} failed with code {e.returncode}"
            if e.stdout:
                logging.error(f"{action_name} stdout: {e.stdout}")
            if e.stderr:
                logging.error(f"{action_name} stderr: {e.stderr}")
            logging.error(error_msg)
            return False

        except FileNotFoundError:
            logging.error("Node.js command not found. Please ensure Node.js is installed and in PATH.")
            return False

    @staticmethod
    def _inject_json_to_html(
            json_path: str,
            placeholder: str,
            html_path: str,
            output_path: str
    ) -> None:
        """Inject JSON data into an HTML template"""
        # Validate paths
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"HTML template not found: {html_path}")

        # Load JSON data
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        # Validate JSON structure
        if not isinstance(json_data, list) or not json_data:
            raise ValueError(f"Invalid JSON format in {json_path}: expected non-empty array")

        # Load HTML template
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Prepare JSON string (use first element for perf data, full array for frames)
        if placeholder == 'JSON_DATA_PLACEHOLDER':
            json_str = json.dumps(json_data[0], indent=2, ensure_ascii=False)
        else:
            json_str = json.dumps(json_data, indent=2, ensure_ascii=False)

        # Inject JSON into HTML
        updated_html = html_content.replace(placeholder, json_str)

        # Save the updated HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated_html)

        logging.debug(f"Injected {json_path} into {output_path}")

    @staticmethod
    def convert_kind_to_json() -> str:
        kind = Config.get('kind', None)
        if kind is None:
            return ''
    
        kind_entry = {
            "name": 'APP_SO',
            "kind": 1,
            "components": []
        }

        for category in Config.get('kind', None):
            component = {
                "name": category['name'],
                "files": category['files']
            }
            
            if 'thread' in category:
                component["threads"] = category['thread']
                
            kind_entry["components"].append(component)

        return json.dumps([kind_entry])