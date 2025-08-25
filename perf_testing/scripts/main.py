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
import multiprocessing
import os
import sys
from logging.handlers import RotatingFileHandler

from hapray.actions.compare_action import CompareAction
from hapray.actions.opt_action import OptAction
from hapray.actions.perf_action import PerfAction
from hapray.actions.update_action import UpdateAction
from hapray.core.config.config import Config


def configure_logging(log_file='HapRay.log'):
    """配置日志系统，同时输出到控制台和文件"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    file_handler = RotatingFileHandler(log_file, mode='a', maxBytes=10 * 1024 * 1024, backupCount=10, encoding='UTF-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


class HapRayCmd:
    def __init__(self):
        self._load_config()
        configure_logging('HapRay.log')

        actions = {
            'perf': PerfAction,
            'opt': OptAction,
            'update': UpdateAction,
            'compare': CompareAction,
        }

        parser = argparse.ArgumentParser(
            description='Code-oriented Performance Analysis for OpenHarmony Apps',
            usage=f'{sys.argv[0]} [action] [<args>]\nActions: {" | ".join(actions.keys())}',
            add_help=False,
        )

        parser.add_argument(
            'action',
            choices=list(actions.keys()),
            nargs='?',
            default='perf',
            help='Action to perform (perf: performance testing, opt: so optimization detection)',
        )
        # Parse action
        action_args = []
        if len(sys.argv[1:2]) > 0 and sys.argv[1:2][0] not in actions:
            action_args.append('perf')
            sub_args = sys.argv[1:]
        else:
            action_args = sys.argv[1:2]
            sub_args = sys.argv[2:]
        args = parser.parse_args(action_args)

        # Dispatch to action handler
        actions[args.action].execute(sub_args)

    def _load_config(self):
        """Loads application configuration from YAML file."""
        config_path = os.path.join(os.getcwd(), 'config.yaml')
        Config(config_path)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    HapRayCmd()
