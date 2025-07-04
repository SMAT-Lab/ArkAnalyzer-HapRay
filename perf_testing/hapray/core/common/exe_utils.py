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
import platform
import subprocess
from typing import List, Tuple, Optional

from hapray.core.common.common_utils import CommonUtils

# Initialize logger
logger = logging.getLogger(__name__)


def _get_trace_streamer_path() -> str:
    """Gets the path to the trace_streamer executable based on the current OS.

    Returns:
        Path to the trace_streamer executable

    Raises:
        OSError: For unsupported operating systems
        FileNotFoundError: If the executable doesn't exist
    """
    # Get the root directory of the project
    project_root = CommonUtils.get_project_root()

    # Determine OS-specific executable name
    system = platform.system().lower()
    if system == 'windows':
        executable = 'trace_streamer_window.exe'
    elif system == 'darwin':  # macOS
        executable = 'trace_streamer_mac'
    elif system == 'linux':
        executable = 'trace_streamer_linux'
    else:
        raise OSError(f"Unsupported operating system: {system}")

    # Construct full path to the executable
    tool_path = os.path.join(
        project_root,
        'hapray-toolbox',
        'third-party',
        'trace_streamer_binary',
        executable
    )

    # Validate executable exists
    if not os.path.exists(tool_path):
        raise FileNotFoundError(f"Trace streamer executable not found at: {tool_path}")

    # Set execute permissions for Unix-like systems
    if system in ('darwin', 'linux'):
        os.chmod(tool_path, 0o755)  # rwxr-xr-x

    return tool_path


class ExeUtils:
    """Utility class for executing external commands and tools"""

    # Path to the hapray-cmd.js script
    hapray_cmd_path = os.path.abspath(os.path.join(
        CommonUtils.get_project_root(),
        'hapray-toolbox',
        'hapray-cmd.js'
    ))

    # Path to the trace streamer executable
    trace_streamer_path = _get_trace_streamer_path()

    @staticmethod
    def build_hapray_cmd(args: List[str]) -> List[str]:
        """Constructs a command for executing hapray-cmd.js.

        Args:
            args: Arguments to pass to the hapray command

        Returns:
            Full command as a list of strings
        """
        return ['node', ExeUtils.hapray_cmd_path, 'hapray', *args]

    @staticmethod
    def execute_command_check_output(cmd, timeout=120000):
        ret = 'error'
        try:
            ret = subprocess.check_output(cmd, timeout=timeout, stderr=subprocess.STDOUT, shell=True)
            return ret.decode('gbk', 'ignore').encode('utf-8')
        except subprocess.CalledProcessError as e:
            logger.error('cmd->%s excute error output=%s', cmd, e.output)
        except subprocess.TimeoutExpired as e:
            logger.error('cmd->%s excute error output=%s', cmd, e.output)
        return ret

    @staticmethod
    def execute_command(cmd: List[str]) -> Tuple[bool, Optional[str], Optional[str]]:
        """Executes a shell command and captures its output.

        Args:
            cmd: Command to execute as a list of strings

        Returns:
            Tuple (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # Log output appropriately
            if result.stdout:
                logger.debug("Command output [%s]:\n%s", ' '.join(cmd), result.stdout)
            if result.stderr:
                logger.warning("Command warnings [%s]:\n%s", ' '.join(cmd), result.stderr)

            logger.info("Command executed successfully: %s", ' '.join(cmd))
            return True, result.stdout, result.stderr

        except subprocess.CalledProcessError as e:
            logger.error(
                "Command failed with code %d: %s\nSTDOUT: %s\nSTDERR: %s",
                e.returncode,
                ' '.join(cmd),
                e.stdout,
                e.stderr
            )
            return False, e.stdout, e.stderr

        except FileNotFoundError:
            logger.error("Command not found: %s", ' '.join(cmd))
            return False, None, None

    @staticmethod
    def execute_hapray_cmd(args: List[str]) -> bool:
        """Executes a hapray command.

        Args:
            args: Arguments to pass to the hapray command

        Returns:
            True if execution was successful, False otherwise
        """
        cmd = ExeUtils.build_hapray_cmd(args)
        success, _, _ = ExeUtils.execute_command(cmd)
        return success

    @staticmethod
    def convert_data_to_db(data_file: str, output_db: str) -> bool:
        """Converts an .htrace file to a SQLite database.

        Uses the trace_streamer tool to perform the conversion.

        Args:
            data_file: Path to input .htrace/.data file
            output_db: Path to output SQLite database

        Returns:
            True if conversion was successful, False otherwise
        """
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_db)
            os.makedirs(output_dir, exist_ok=True)

            # Prepare conversion command
            cmd = [
                ExeUtils.trace_streamer_path,
                data_file,
                '-e',
                output_db
            ]

            logger.info("Converting htrace to DB: %s -> %s", data_file, output_db)

            # Execute conversion
            success, _, stderr = ExeUtils.execute_command(cmd)

            if not success:
                logger.error("Conversion failed for %s: %s", data_file, stderr)
                return False

            # Verify output file was created
            if not os.path.exists(output_db):
                logger.error("Output DB file not created: %s", output_db)
                return False

            logger.info("Successfully converted %s to %s", data_file, output_db)
            return True

        except Exception as e:
            logger.exception("Unexpected error during conversion: %s", str(e))
            return False
