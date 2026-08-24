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
import os
import subprocess
import sys
from typing import Optional

from hapray import VERSION
from hapray.core.build import (
    HarmonyProject,
    build_devecocli_args,
    check_signing_config,
    extract_so_from_hap,
    find_devecocli,
    find_hdc,
)
from hapray.core.common.action_return import ActionExecuteReturn

logger = logging.getLogger(__name__)

DEVECO_CLI_NOT_FOUND_HINT = (
    'devecocli not found in PATH. Install it first:\n'
    '  npm install -g @deveco/deveco-cli@latest\n'
    'See https://gitcode.com/<deveco-cli repo> for details.'
)

DEFAULT_BUILD_MODE = 'debug'
DEFAULT_PRODUCT = 'default'


class BuildAction:
    """Builds a HarmonyOS project's debug HAP via deveco-cli and extracts .so symbols.

    This action wraps `devecocli build` to produce a debug-mode HAP (with symbolicated
    .so files) from a HarmonyOS source project. After building, it locates the artifact
    HAP and extracts all .so files to a specified output directory, which can be fed
    directly into HapRay's symbol recovery (``update --so_dir``) and SKILL §0 ``so_dir``.

    Prerequisites:
        - ``devecocli`` installed and in PATH (``npm install -g @deveco/deveco-cli``)
        - DevEco Studio or Command Line Tools installed (devecocli auto-detects)
        - A valid HarmonyOS project directory containing ``build-profile.json5``
    """

    @staticmethod
    def execute(args) -> ActionExecuteReturn:
        """Execute the build workflow."""
        parser = argparse.ArgumentParser(
            description='Build HarmonyOS debug HAP via deveco-cli and extract .so symbols',
            prog='ArkAnalyzer-HapRay build',
        )
        parser.add_argument(
            '-v', '--version', action='version',
            version=f'%(prog)s {VERSION}',
        )
        parser.add_argument(
            '-p', '--project-dir', required=True,
            help='HarmonyOS project root directory (containing build-profile.json5)',
        )
        parser.add_argument(
            '--build-mode', default=DEFAULT_BUILD_MODE,
            help=f'Build mode (default: {DEFAULT_BUILD_MODE})',
        )
        parser.add_argument(
            '--product', default=DEFAULT_PRODUCT,
            help=f'Product name defined in build-profile.json5 (default: {DEFAULT_PRODUCT})',
        )
        parser.add_argument(
            '--modules', nargs='*', default=None,
            help='Modules to build (format: module or module@target). '
                 'Auto-detected if omitted (single entry module).',
        )
        parser.add_argument(
            '--so-output-dir', default=None,
            help='Directory to extract .so files for symbol recovery. '
                 'Default: <project_dir>/build/hapray_so_symbols/',
        )
        parser.add_argument(
            '--no-extract-so', action='store_true',
            help='Skip .so extraction after build',
        )
        parser.add_argument(
            '--install', action='store_true',
            help='Install the built HAP to a connected device after build',
        )
        parser.add_argument(
            '--device', default=None,
            help='Target device serial for installation (auto-detected if omitted)',
        )
        parser.add_argument(
            '--uninstall', action='store_true',
            help='Uninstall existing app before installation',
        )
        parser.add_argument(
            '--timeout', type=int, default=1800,
            help='Build timeout in seconds (default: 1800 = 30 minutes)',
        )

        parsed = parser.parse_args(args)

        action = BuildAction()
        return action.run(
            project_dir=parsed.project_dir,
            build_mode=parsed.build_mode,
            product=parsed.product,
            modules=parsed.modules,
            so_output_dir=parsed.so_output_dir,
            extract_so=not parsed.no_extract_so,
            install=parsed.install,
            device_sn=parsed.device,
            uninstall=parsed.uninstall,
            timeout=parsed.timeout,
        )

    def run(
        self,
        project_dir: str,
        build_mode: str = DEFAULT_BUILD_MODE,
        product: str = DEFAULT_PRODUCT,
        modules: Optional[list[str]] = None,
        so_output_dir: Optional[str] = None,
        extract_so: bool = True,
        install: bool = False,
        device_sn: Optional[str] = None,
        uninstall: bool = False,
        timeout: int = 1800,
    ) -> ActionExecuteReturn:
        """Run build + optional .so extraction + optional install.

        Returns:
            (exit_code, project_dir) — project_dir is the "reports_path" equivalent
            for the tool-result contract. The hapray-tool-result.json will be written
            beside it, enriched with hap_path / so_dir / bundle_name / build_mode.
        """
        project_dir = os.path.abspath(project_dir)
        if not os.path.isdir(project_dir):
            logging.error('Project directory not found: %s', project_dir)
            return (1, '')

        devecocli = find_devecocli()
        if not devecocli:
            logging.error(DEVECO_CLI_NOT_FOUND_HINT)
            return (1, '')

        try:
            project = HarmonyProject.discover(project_dir)
        except FileNotFoundError as e:
            logging.error('Invalid HarmonyOS project: %s', e)
            return (1, '')
        except ValueError as e:
            logging.error('Failed to parse project: %s', e)
            return (1, '')

        try:
            modules_to_build = project.determine_modules_to_build(modules)
        except ValueError as e:
            logging.error('%s', e)
            return (1, '')

        try:
            bundle_name = project.get_bundle_name()
        except FileNotFoundError:
            bundle_name = ''
            logging.warning('Could not determine bundleName from AppScope/app.json5')

        logging.info('Project: %s', project_dir)
        logging.info('Bundle: %s', bundle_name or '(unknown)')
        logging.info('Modules: %s', ', '.join(modules_to_build))
        logging.info('Build mode: %s, product: %s', build_mode, product)

        # 1. 检查签名配置
        sign_info = check_signing_config(project_dir)
        if sign_info['needs_signature']:
            logging.warning('Signing config is missing or invalid (storeFile not found).')
            logging.info('Attempting auto-signature generation via devecocli signature generate...')

            # 先检查是否已登录；未登录则自动触发登录流程
            auth_ok = self._check_auth(devecocli)
            if not auth_ok:
                logging.info('Huawei developer account not logged in. Starting login flow...')
                logging.info('A browser window will open for OAuth authentication. Please complete login in the browser.')
                auth_ok = self._do_login(devecocli)
                if not auth_ok:
                    logging.error(
                        'Login failed or was cancelled.\n'
                        'Please run manually in a terminal:\n'
                        '  devecocli auth login\n'
                        'Then re-run this build command.'
                    )
                    return (1, project_dir)
                logging.info('Login successful. Continuing with signature generation...')

            # 自动生成签名
            sign_ok = self._generate_signature(devecocli, project_dir, product, timeout)
            if not sign_ok:
                logging.error(
                    'Auto-signature generation failed.\n'
                    'Please run manually in a terminal:\n'
                    '  devecocli signature generate --force\n'
                    'Then re-run this build command.'
                )
                return (1, project_dir)
            logging.info('Signature generated successfully')
        else:
            logging.info('Signing config OK (storeFile: %s)', sign_info['store_file'])

        # 2. 构建
        cli_args = build_devecocli_args(project_dir, build_mode, product, modules_to_build)
        cmd = [devecocli] + cli_args

        logging.info('Executing: %s', ' '.join(cmd))
        logging.info('(cwd=%s, timeout=%ss)', project_dir, timeout)

        try:
            result = subprocess.run(
                cmd,
                cwd=project_dir,
                timeout=timeout,
                stdout=sys.stdout,
                stderr=sys.stderr,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logging.error('Build timed out after %s seconds', timeout)
            return (1, project_dir)
        except OSError as e:
            logging.error('Failed to execute devecocli: %s', e)
            return (1, project_dir)

        if result.returncode != 0:
            logging.error('Build failed with exit code %s', result.returncode)
            return (result.returncode, project_dir)

        logging.info('Build completed successfully')

        # 3. 定位产物
        hap_path = ''
        so_dir = ''
        so_files: list[str] = []

        first_module = modules_to_build[0]
        try:
            hap_path = project.find_artifact_path(first_module, product, 'default')
            logging.info('HAP artifact: %s', hap_path)
        except (FileNotFoundError, ValueError) as e:
            logging.warning('Could not locate HAP artifact for module %s: %s', first_module, e)

        # 4. 抽取 .so
        if extract_so and hap_path:
            if not so_output_dir:
                so_output_dir = os.path.join(project_dir, 'build', 'hapray_so_symbols')
            try:
                so_files = extract_so_from_hap(hap_path, so_output_dir)
                so_dir = so_output_dir
                logging.info('Extracted %d .so files to %s', len(so_files), so_dir)
                if so_files:
                    logging.info('  .so files: %s', ', '.join(os.path.basename(f) for f in so_files))
            except Exception as e:
                logging.error('Failed to extract .so from HAP: %s', e)

        # 5. 安装到设备
        if install and hap_path:
            install_ok = self._install_to_device(hap_path, bundle_name, device_sn, uninstall)
            if not install_ok:
                logging.warning('Installation failed; HAP is still built at %s', hap_path)

        self._last_result = {
            'hap_path': hap_path,
            'so_dir': so_dir,
            'so_count': len(so_files),
            'bundle_name': bundle_name,
            'build_mode': build_mode,
            'product': product,
            'modules': modules_to_build,
            'installed': install and hap_path,
        }

        return (0, project_dir)

    def _check_auth(self, devecocli: str) -> bool:
        """检查 devecocli 是否已登录华为开发者账号。"""
        try:
            result = subprocess.run(
                [devecocli, 'auth', 'status'],
                capture_output=True, text=True, timeout=30, check=False,
            )
            output = (result.stdout or '') + (result.stderr or '')
            return 'Not logged in' not in output and result.returncode == 0
        except Exception:
            return False

    def _do_login(self, devecocli: str) -> bool:
        """执行 devecocli auth login，等待用户在浏览器完成 OAuth 登录。

        devecocli auth login 会提示 "Press Enter to open browser for login..."，
        需要通过 stdin 发送回车键触发浏览器打开。然后阻塞等待用户在浏览器中
        完成 OAuth 认证，登录成功后进程退出。
        超时 300 秒（5 分钟）。
        """
        login_timeout = 300  # 5 分钟，用户需要在浏览器中完成登录
        logging.info('Executing: %s auth login (timeout=%ss)', devecocli, login_timeout)
        try:
            # devecocli auth login 会先打印 "Press Enter to open browser..."
            # 需要通过 stdin 自动发送回车键，让 devecocli 打开浏览器
            result = subprocess.run(
                [devecocli, 'auth', 'login'],
                timeout=login_timeout,
                stdout=sys.stdout,
                stderr=sys.stderr,
                check=False,
                # 自动发送一个回车键（\n），触发 devecocli 打开浏览器
                input='\n',
                text=True,
            )
        except subprocess.TimeoutExpired:
            logging.error('Login timed out after %s seconds. Please try again.', login_timeout)
            return False
        except OSError as e:
            logging.error('Failed to execute devecocli auth login: %s', e)
            return False

        if result.returncode != 0:
            logging.warning('devecocli auth login returned non-zero exit code: %s', result.returncode)
            return False

        # 验证登录是否成功
        return self._check_auth(devecocli)

    def _generate_signature(self, devecocli: str, project_dir: str, product: str, timeout: int) -> bool:
        """调用 devecocli signature generate 自动生成签名材料。"""
        cmd = [devecocli, 'signature', 'generate', '--product', product, '--force']
        logging.info('Executing: %s (cwd=%s)', ' '.join(cmd), project_dir)
        try:
            result = subprocess.run(
                cmd, cwd=project_dir, timeout=timeout,
                stdout=sys.stdout, stderr=sys.stderr, check=False,
            )
            return result.returncode == 0
        except Exception as e:
            logging.error('Signature generation error: %s', e)
            return False

    def _install_to_device(
        self, hap_path: str, bundle_name: str, device_sn: Optional[str], uninstall: bool
    ) -> bool:
        """安装 HAP 到设备。"""
        hdc = find_hdc()
        if not hdc:
            logging.error('hdc not found in PATH. Cannot install to device.')
            return False

        # 检测设备
        try:
            list_result = subprocess.run(
                [hdc, 'list', 'targets'], capture_output=True, text=True, timeout=10, check=False,
            )
            devices = [line.strip() for line in list_result.stdout.splitlines() if line.strip()]
            if not devices:
                logging.error('No devices connected. Cannot install.')
                return False
        except Exception as e:
            logging.error('Failed to list devices: %s', e)
            return False

        target = device_sn or devices[0]
        logging.info('Installing to device: %s', target)

        # 卸载旧版本
        if uninstall and bundle_name:
            logging.info('Uninstalling %s...', bundle_name)
            subprocess.run([hdc, '-t', target, 'shell', 'bm', 'uninstall', '-n', bundle_name],
                           capture_output=True, text=True, timeout=30, check=False)

        # 安装
        install_cmd = [hdc, '-t', target, 'install', hap_path]
        try:
            result = subprocess.run(
                install_cmd, capture_output=True, text=True, timeout=120, check=False,
            )
            output = (result.stdout or '') + (result.stderr or '')
            if result.returncode == 0 and 'error' not in output.lower():
                logging.info('Install successful: %s', hap_path)
                return True
            logging.error('Install failed: %s', output.strip())
            return False
        except Exception as e:
            logging.error('Install error: %s', e)
            return False

    def get_build_result(self) -> dict:
        """返回最近一次构建的结构化结果（供契约层读取）。"""
        return getattr(self, '_last_result', {})
