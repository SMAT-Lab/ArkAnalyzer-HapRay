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
import sys
from pathlib import Path

from hapray.core.common.action_return import ActionExecuteReturn


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
            default='empty-frame',
            choices=['empty-frame'],
            help='Analysis checker type (default: empty-frame)',
        )
        parser.add_argument(
            '--output',
            default=None,
            help='Output path for the root cause Markdown report (default: <report-dir>/root_cause.md)',
        )
        parser.add_argument(
            '--index-dir',
            default=None,
            help='Decompiled code index directory (contains symbol_index.jsonl / ui_index.jsonl)',
        )
        parser.add_argument(
            '--decompiled-dir',
            default=None,
            help='Decompiled source tree directory (*.ts / *.callgraph.json). '
                 'Enables code_review LLM mode when combined with --index-dir.',
        )
        parser.add_argument(
            '--llm-mode',
            default='polish',
            choices=['polish', 'code_review'],
            help='LLM analysis mode: polish (default) or code_review',
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
            help='Path to an LLM token/credentials YAML (llm: api_key / base_url / model). '
                 'Auto-discovered at hapray/core/config/llm_tokens.local.yaml when not specified.',
        )
        parser.add_argument(
            '--api-key',
            default=None,
            help='LLM API key — one-off override, takes precedence over config files.',
        )
        parser.add_argument(
            '--base-url',
            default=None,
            help='LLM base URL — one-off override.',
        )
        parser.add_argument(
            '--model',
            default=None,
            help='LLM model name — one-off override.',
        )
        parser.add_argument(
            '--skip-llm',
            action='store_true',
            help='Skip LLM call; output deterministic report only',
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

        if parsed.decompiled_dir and not Path(parsed.decompiled_dir).exists():
            logging.error('Decompiled directory does not exist: %s', parsed.decompiled_dir)
            return (1, '')

        llm_config = RootCauseAction._load_config(parsed)
        if llm_config is None:
            return (1, '')

        output_path = parsed.output or str(report_dir / 'root_cause.md')

        try:
            from hapray.analyze.llm_root_cause import run_empty_frame_analysis

            logging.info('Starting LLM root cause analysis...')
            logging.info('  Report dir : %s', report_dir)
            logging.info('  LLM mode   : %s', parsed.llm_mode)
            logging.info('  Output     : %s', output_path)

            run_empty_frame_analysis(
                report_dir=str(report_dir),
                output_path=output_path,
                llm_config=llm_config,
                index_dir=parsed.index_dir,
                decompiled_dir=parsed.decompiled_dir,
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
        """Build the LLM config dict with the following priority (highest first):

        1. --config <file>       complete config replacement (all sections)
        2. --api-key / --base-url / --model   explicit one-off CLI overrides
        3. --llm-tokens <file>   explicit token/credentials file
        4. llm_tokens.local.yaml auto-discovered beside config.yaml (gitignored)
        5. config.yaml llm_root_cause: section   tracked defaults
        6. LLM_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY   env-var fallback
        """
        import yaml

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

        # Merge token/credentials file (explicit path or auto-discovered)
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
        """Apply --api-key / --base-url / --model overrides and env-var fallback."""
        if parsed.api_key:
            config.setdefault('llm', {})['api_key'] = parsed.api_key
        if parsed.base_url:
            config.setdefault('llm', {})['base_url'] = parsed.base_url
        if parsed.model:
            config.setdefault('llm', {})['model'] = parsed.model

        if not config.get('llm', {}).get('api_key'):
            env_key = (
                os.environ.get('LLM_API_KEY')
                or os.environ.get('ANTHROPIC_API_KEY')
                or os.environ.get('OPENAI_API_KEY')
            )
            if env_key:
                config.setdefault('llm', {})['api_key'] = env_key

        return config

    @staticmethod
    def _load_tokens_file(explicit_path: str | None) -> dict | None:
        """Load LLM token/credentials YAML.

        If explicit_path is given, load that file (error if missing).
        Otherwise auto-discover llm_tokens.local.yaml beside config.yaml.
        """
        import yaml

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

        # Auto-discover beside config.yaml
        config_dir = Path(__file__).parent.parent / 'core' / 'config'
        auto_path = config_dir / 'llm_tokens.local.yaml'
        if not auto_path.exists():
            return None
        try:
            with open(auto_path, encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            logging.info('Auto-loaded LLM tokens: %s', auto_path)
            return data
        except Exception as exc:
            logging.warning('Failed to read auto-discovered LLM tokens %s: %s', auto_path, exc)
            return None

    @staticmethod
    def _config_from_hapray() -> dict:
        """Read the llm_root_cause section from hapray's main config.yaml."""
        try:
            from hapray.core.config.config import Config
            hapray_cfg = Config.get_instance().config
            llm_section = hapray_cfg.get('llm_root_cause', {})
            if llm_section:
                return llm_section
        except Exception:
            pass
        # Minimal default — works in skip-llm mode without any config
        return {'llm': {}, 'analysis': {'language': 'zh', 'top_n_hotspots': 10}}
