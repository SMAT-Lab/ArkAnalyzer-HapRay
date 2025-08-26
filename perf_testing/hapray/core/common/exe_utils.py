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

import json
import logging
import os
import platform
import subprocess
from typing import Optional

from hapray.core.common.common_utils import CommonUtils
from hapray.core.config.config import Config

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
        raise OSError(f'Unsupported operating system: {system}')

    # Construct full path to the executable
    tool_path = os.path.join(project_root, 'hapray-toolbox', 'third-party', 'trace_streamer_binary', executable)

    # Validate executable exists
    if not os.path.exists(tool_path):
        raise FileNotFoundError(f'Trace streamer executable not found at: {tool_path}')

    # Set execute permissions for Unix-like systems
    if system in ('darwin', 'linux'):
        os.chmod(tool_path, 0o755)  # rwxr-xr-x

    return tool_path


class ExeUtils:
    """Utility class for executing external commands and tools"""

    # Path to the hapray-cmd.js script
    hapray_cmd_path = os.path.abspath(os.path.join(CommonUtils.get_project_root(), 'hapray-toolbox', 'hapray-cmd.js'))

    # Path to the trace streamer executable
    trace_streamer_path = _get_trace_streamer_path()

    @staticmethod
    def _get_so_dir_cache_file(output_db: str) -> str:
        """Get the cache file path for storing so_dir parameter info.

        Args:
            output_db: Path to the output database file

        Returns:
            Path to the cache file
        """
        cache_dir = os.path.dirname(output_db)
        db_name = os.path.splitext(os.path.basename(output_db))[0]
        return os.path.join(cache_dir, f'.{db_name}_so_dir_cache.json')

    @staticmethod
    def _should_regenerate_db(output_db: str, so_dir: Optional[str]) -> bool:
        """Check if the database should be regenerated based on so_dir changes.

        Args:
            output_db: Path to the output database file
            so_dir: Current so_dir parameter value

        Returns:
            True if database should be regenerated, False otherwise
        """
        # If database doesn't exist, always regenerate
        if not os.path.exists(output_db):
            return True

        cache_file = ExeUtils._get_so_dir_cache_file(output_db)

        # If cache file doesn't exist, regenerate and create cache
        if not os.path.exists(cache_file):
            return True

        try:
            with open(cache_file, encoding='utf-8') as f:
                cache_data = json.load(f)
                cached_so_dir = cache_data.get('so_dir_value')

            # Normalize paths for comparison
            current_so_dir = os.path.abspath(so_dir) if so_dir else None
            cached_so_dir = os.path.abspath(cached_so_dir) if cached_so_dir else None

            # If so_dir changed, regenerate
            return current_so_dir != cached_so_dir

        except (OSError, json.JSONDecodeError, KeyError):
            # If cache is corrupted, regenerate
            return True

    @staticmethod
    def _update_so_dir_cache(output_db: str, so_dir: Optional[str]):
        """Update the so_dir cache file with current parameter state.

        Args:
            output_db: Path to the output database file
            so_dir: Current so_dir parameter value
        """
        cache_file = ExeUtils._get_so_dir_cache_file(output_db)

        cache_data = {
            'so_dir_value': so_dir,
            'timestamp': os.path.getmtime(output_db) if os.path.exists(output_db) else None,
        }

        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except OSError as e:
            logger.warning('Failed to update so_dir cache: %s', str(e))

    @staticmethod
    def build_hapray_cmd(args: list[str]) -> list[str]:
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
    def execute_command(cmd: list[str], timeout: int = 1800) -> tuple[bool, Optional[str], Optional[str]]:
        """Executes a shell command and captures its output.

        Args:
            cmd: Command to execute as a list of strings
            timeout: Maximum time to wait for command completion in seconds (default: 30 minutes)

        Returns:
            Tuple (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout
            )

            # Log output appropriately
            if result.stdout:
                logger.debug('Command output [%s]:\n%s', ' '.join(cmd), result.stdout)
            if result.stderr:
                logger.warning('Command warnings [%s]:\n%s', ' '.join(cmd), result.stderr)

            logger.info('Command executed successfully: %s', ' '.join(cmd))
            return True, result.stdout, result.stderr

        except subprocess.TimeoutExpired as e:
            logger.error(
                'Command timed out after %d seconds: %s\nSTDOUT: %s\nSTDERR: %s',
                timeout,
                ' '.join(cmd),
                e.stdout,
                e.stderr,
            )
            return False, e.stdout, e.stderr

        except subprocess.CalledProcessError as e:
            logger.error(
                'Command failed with code %d: %s\nSTDOUT: %s\nSTDERR: %s',
                e.returncode,
                ' '.join(cmd),
                e.stdout,
                e.stderr,
            )
            return False, e.stdout, e.stderr

        except FileNotFoundError:
            logger.error('Command not found: %s', ' '.join(cmd))
            return False, None, None

    @staticmethod
    def execute_hapray_cmd(args: list[str], timeout: int = 1800) -> bool:
        """Executes a hapray command.

        Args:
            args: Arguments to pass to the hapray command
            timeout: Maximum time to wait for command completion in seconds (default: 30 minutes)

        Returns:
            True if execution was successful, False otherwise
        """
        cmd = ExeUtils.build_hapray_cmd(args)
        success, _, _ = ExeUtils.execute_command(cmd, timeout=timeout)
        return success

    @staticmethod
    def convert_data_to_db(data_file: str, output_db: str) -> bool:
        """Converts an .htrace file to a SQLite database.

        Uses the trace_streamer tool to perform the conversion.
        Only regenerates the database if the so_dir parameter has changed.

        Args:
            data_file: Path to input .htrace/.data file
            output_db: Path to output SQLite database

        Returns:
            True if conversion was successful, False otherwise
        """
        try:
            # Get current so_dir configuration
            so_dir = Config.get('so_dir', None)

            # Check if regeneration is needed
            if not ExeUtils._should_regenerate_db(output_db, so_dir):
                logger.info(
                    'Database %s is up-to-date with current so_dir configuration, skipping conversion', output_db
                )
                return True

            # Ensure output directory exists
            output_dir = os.path.dirname(output_db)
            os.makedirs(output_dir, exist_ok=True)

            # Prepare conversion command
            cmd = [ExeUtils.trace_streamer_path, data_file, '-e', output_db]

            # Add so_dir parameter if configured
            if so_dir:
                cmd.extend(['--So_dir', os.path.abspath(so_dir)])
                logger.info('Converting htrace to DB with so_dir: %s -> %s (so_dir: %s)', data_file, output_db, so_dir)
            else:
                logger.info('Converting htrace to DB: %s -> %s', data_file, output_db)

            # Execute conversion with extended timeout for large data files
            success, _, stderr = ExeUtils.execute_command(cmd, timeout=3600)  # 1 hour timeout

            if not success:
                logger.error('Conversion failed for %s: %s', data_file, stderr)
                return False

            # Verify output file was created
            if not os.path.exists(output_db):
                logger.error('Output DB file not created: %s', output_db)
                return False

            # Update cache with current so_dir state
            ExeUtils._update_so_dir_cache(output_db, so_dir)

            logger.info('Successfully converted %s to %s', data_file, output_db)
            return True

        except Exception as e:
            logger.exception('Unexpected error during conversion: %s', str(e))
            return False
