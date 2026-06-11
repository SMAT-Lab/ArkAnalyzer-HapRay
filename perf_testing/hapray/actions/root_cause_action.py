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
from pathlib import Path

import yaml

from hapray.analyze.llm_root_cause import run_empty_frame_analysis
from hapray.analyze.llm_root_cause.runner import run_comprehensive_analysis
from hapray.core.common.action_return import ActionExecuteReturn
from hapray.core.config.config import Config

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
except Exception:
    pass


_LLM_SERVICE_TYPE = os.getenv('LLM_SERVICE_TYPE', '').lower()
_LLM_API_KEY_ENV_MAP = {
    'poe': 'POE_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'claude': 'ANTHROPIC_API_KEY',
    'deepseek': 'DEEPSEEK_API_KEY',
}
_LLM_BASE_URL_MAP = {
    'poe': 'https://api.poe.com/v1',
    'openai': 'https://api.openai.com/v1',
    'claude': 'https://api.anthropic.com/v1',
    'deepseek': 'https://api.deepseek.com/v1',
}
_LLM_MODEL_ENV_MAP = {
    'poe': 'POE_MODEL',
    'openai': 'OPENAI_MODEL',
    'claude': 'CLAUDE_MODEL',
    'deepseek': 'DEEPSEEK_MODEL',
}


class RootCauseAction:
    """LLM-powered root cause analysis for HapRay performance reports."""

    @staticmethod
    def execute(args) -> ActionExecuteReturn:
        parser = argparse.ArgumentParser(
            description='LLM root cause analysis for HapRay performance reports',
            prog='hapray root-cause',
        )
        parser.add_argument(
            '--report-dir',
            required=True,
            help='HapRay step report directory (contains summary.json, trace_emptyFrame.json, etc.)',
        )
        parser.add_argument(
            '--checker',
            default='comprehensive',
            choices=['comprehensive', 'empty-frame'],
            help='Analysis checker: comprehensive (default, multi-signal) or empty-frame (legacy, empty-frame only)',
        )
        parser.add_argument(
            '--categories',
            default=None,
            help=(
                'comprehensive 模式下精选信号类别（逗号分隔），如 '
                'cpu-hotspot,frame-load,thread,ipc,so-load,component-reuse,memory,empty-frame,'
                'frame-stats,ui-animate,fault-hilog；不填则全部可用信号'
            ),
        )
        parser.add_argument(
            '--output',
            default=None,
            help='Output path for the root cause Markdown report (default: <report-dir>/root_cause.md). A companion <stem>_evidence.md is always written alongside it.',
        )
        parser.add_argument(
            '--index-dir',
            default=None,
            help='Source code index directory (contains symbol_index.jsonl / ui_index.jsonl)',
        )
        parser.add_argument(
            '--source-dir',
            default=None,
            help='Application source tree directory (*.ts / *.ets / *.callgraph.json). '
            'Enables with_source LLM mode when combined with --index-dir.',
        )
        parser.add_argument(
            '--llm-mode',
            default='analyze',
            choices=['analyze', 'with_source'],
            help='LLM analysis mode: analyze (default, reasons from evidence only) or '
            'with_source (reads source code for line-level fix recommendations, '
            'requires --source-dir; auto-selected when --source-dir is provided)',
        )
        parser.add_argument(
            '--config',
            default=None,
            help='Path to a full LLM config YAML (highest priority; replaces all defaults).',
        )
        parser.add_argument(
            '--llm-tokens',
            default=None,
            dest='llm_tokens',
            help='Deprecated legacy token YAML. Prefer shared env/.env variables: '
            'LLM_SERVICE_TYPE, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL.',
        )
        parser.add_argument(
            '--api-key',
            default=None,
            help='Deprecated one-off override. Prefer LLM_API_KEY or service-specific env variables.',
        )
        parser.add_argument(
            '--base-url',
            default=None,
            help='Deprecated one-off override. Prefer LLM_BASE_URL.',
        )
        parser.add_argument(
            '--model',
            default=None,
            help='Deprecated one-off override. Prefer LLM_MODEL or service-specific model env variables.',
        )
        parser.add_argument(
            '--skip-llm',
            action='store_true',
            help='Skip LLM call; root_cause.md will contain a structured summary with Pending Agent Inference placeholders (different from root_cause_evidence.md)',
        )
        parser.add_argument(
            '--stream',
            action='store_true',
            help='Stream LLM output to stdout',
        )

        parsed = parser.parse_args(args)

        report_dir = Path(parsed.report_dir)
        if not report_dir.exists():
            logging.error('Report directory does not exist: %s', report_dir)
            return (1, '')

        if parsed.index_dir and not Path(parsed.index_dir).exists():
            logging.error('Index directory does not exist: %s', parsed.index_dir)
            return (1, '')

        if parsed.source_dir and not Path(parsed.source_dir).exists():
            logging.error('Source directory does not exist: %s', parsed.source_dir)
            return (1, '')

        llm_config = RootCauseAction._load_config(parsed)
        if llm_config is None:
            return (1, '')

        output_path = parsed.output or str(report_dir / 'root_cause.md')

        try:
            logging.info('Starting LLM root cause analysis...')
            logging.info('  Report dir : %s', report_dir)
            logging.info('  Checker    : %s', parsed.checker)
            logging.info('  LLM mode   : %s', parsed.llm_mode)
            logging.info('  Output     : %s', output_path)

            if parsed.checker == 'comprehensive':
                enabled_categories = None
                if parsed.categories:
                    enabled_categories = [c.strip() for c in parsed.categories.split(',') if c.strip()]
                run_comprehensive_analysis(
                    report_dir=str(report_dir),
                    output_path=output_path,
                    llm_config=llm_config,
                    index_dir=parsed.index_dir,
                    source_dir=parsed.source_dir,
                    llm_mode=parsed.llm_mode,
                    stream=parsed.stream,
                    skip_llm=parsed.skip_llm,
                    enabled_categories=enabled_categories,
                )
            else:
                run_empty_frame_analysis(
                    report_dir=str(report_dir),
                    output_path=output_path,
                    llm_config=llm_config,
                    index_dir=parsed.index_dir,
                    source_dir=parsed.source_dir,
                    llm_mode=parsed.llm_mode,
                    stream=parsed.stream,
                    skip_llm=parsed.skip_llm,
                )

            logging.info('Root cause analysis complete: %s', output_path)
            return (0, output_path)

        except FileNotFoundError as exc:
            logging.error('Required file not found: %s', exc)
            return (1, '')
        except Exception as exc:
            logging.error('Root cause analysis failed: %s', exc, exc_info=True)
            return (1, '')

    @staticmethod
    def _load_config(parsed) -> dict | None:
        """Build the LLM config dict.

        Mirrors tools/symbol_recovery:
        - .env is loaded automatically
        - Agent orchestration is the default execution path
        - shared environment variables are used by the opt-in local API path
        - missing API key is not fatal here; runner will export an Agent task

        Priority:
        1. HAPRAY_ROOT_CAUSE_EXECUTION=agent (default) drives Agent task export
        2. HAPRAY_ROOT_CAUSE_EXECUTION=api enables local API execution
        3. --api-key / --base-url / --model legacy one-off overrides
        4. LLM_* / service-specific environment variables
        5. --config or config.yaml llm_root_cause defaults
        6. --llm-tokens legacy YAML overlay
        """
        if parsed.config:
            config_path = Path(parsed.config)
            if not config_path.exists():
                logging.error('Config file does not exist: %s', config_path)
                return None
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            except Exception as exc:
                logging.error('Failed to read config file: %s', exc)
                return None
            # Apply CLI flags on top even for --config
            return RootCauseAction._apply_cli_and_env(config, parsed)

        # Base: hapray config.yaml defaults
        config = RootCauseAction._config_from_hapray()

        # Merge token/credentials file only when explicitly requested.  We no
        # longer auto-discover local token YAML; symbol_recovery-style env/.env
        # configuration is the unified path.
        tokens_cfg = RootCauseAction._load_tokens_file(getattr(parsed, 'llm_tokens', None))
        if tokens_cfg:
            for section, values in tokens_cfg.items():
                if isinstance(values, dict) and isinstance(config.get(section), dict):
                    config[section].update(values)
                else:
                    config[section] = values

        return RootCauseAction._apply_cli_and_env(config, parsed)

    @staticmethod
    def _apply_cli_and_env(config: dict, parsed) -> dict:
        """Apply shared env/.env config, then legacy CLI overrides."""
        llm_cfg = config.setdefault('llm', {})

        env_key = RootCauseAction._load_env_api_key()
        env_base_url = os.environ.get('LLM_BASE_URL') or _LLM_BASE_URL_MAP.get(_LLM_SERVICE_TYPE)
        env_model = RootCauseAction._load_env_model()

        if env_key:
            llm_cfg['api_key'] = env_key
        if env_base_url:
            llm_cfg['base_url'] = env_base_url
        if env_model:
            llm_cfg['model'] = env_model
        if _LLM_SERVICE_TYPE:
            # Keep the same OpenAI-compatible integration surface as symbol_recovery
            llm_cfg['provider'] = 'openai'

        # Legacy explicit CLI overrides still win when used.
        if parsed.api_key:
            llm_cfg['api_key'] = parsed.api_key
        if parsed.base_url:
            llm_cfg['base_url'] = parsed.base_url
        if parsed.model:
            llm_cfg['model'] = parsed.model
        return config

    @staticmethod
    def _load_env_api_key() -> str:
        env_key = os.environ.get('LLM_API_KEY')
        if env_key:
            return env_key
        service_key_name = _LLM_API_KEY_ENV_MAP.get(_LLM_SERVICE_TYPE)
        if service_key_name:
            return os.environ.get(service_key_name, '')
        return ''

    @staticmethod
    def _load_env_model() -> str:
        env_model = os.environ.get('LLM_MODEL')
        if env_model:
            return env_model
        service_model_name = _LLM_MODEL_ENV_MAP.get(_LLM_SERVICE_TYPE)
        if service_model_name:
            return os.environ.get(service_model_name, '')
        return ''

    @staticmethod
    def _load_tokens_file(explicit_path: str | None) -> dict | None:
        """Load LLM token/credentials YAML.

        If explicit_path is given, load that file (error if missing).
        Otherwise return None; root-cause now follows symbol_recovery and uses
        shared env/.env variables instead of auto-discovered token files.
        """
        if explicit_path:
            tokens_path = Path(explicit_path)
            if not tokens_path.exists():
                logging.error('LLM tokens file does not exist: %s', tokens_path)
                return None
            try:
                with open(tokens_path, encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                logging.info('Loaded LLM tokens from: %s', tokens_path)
                return data
            except Exception as exc:
                logging.warning('Failed to read LLM tokens file %s: %s', tokens_path, exc)
                return None

        return None

    @staticmethod
    def _config_from_hapray() -> dict:
        """Read the llm_root_cause section from hapray's main config.yaml."""
        try:
            hapray_cfg = Config.get_instance().config
            llm_section = hapray_cfg.get('llm_root_cause', {})
            if llm_section:
                return llm_section
        except Exception:
            pass
        # Minimal default — works in skip-llm mode without any config
        return {'llm': {}, 'analysis': {'language': 'zh', 'top_n_hotspots': 10}}
