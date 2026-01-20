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
import tempfile
from typing import Optional

import yaml

from hapray.core.config.config import Config
from hapray.core.gui_agent.gui_agent import GuiAgentConfig
from hapray.core.gui_agent.gui_agent_runner import GUIAgentRunner, SceneResult
from hapray.core.gui_agent.realtime_analysis import RealTimeAnalysisProcess


def _run_scene_with_runner(
    app_package: str,
    scene: str,
    scene_idx: int,
    config: GuiAgentConfig,
    output_base_path: Optional[str] = None,
) -> Optional['SceneResult']:
    """
    Execute a single scene using GUIAgentRunner.run_testcase.

    Args:
        app_package: Application package name
        scene: Scene description
        scene_idx: Scene index
        config: GuiAgentConfig configuration object
        output_base_path: Output base path

    Returns:
        SceneResult object, or None if execution fails
    """
    # Determine output path
    if output_base_path:
        output_path = os.path.join(output_base_path, app_package, f'scene{scene_idx}')
    else:
        output_path = os.path.join(tempfile.gettempdir(), 'gui_agent_test', app_package, f'scene{scene_idx}')

    # Create temporary config file
    config_data = {
        'app_package': app_package,
        'scene': scene,
        'scene_idx': scene_idx,
        'scene_name': f'{app_package}_scene{scene_idx}',
        'gui_agent_config': {
            'model_base_url': config.model_base_url,
            'model_name': config.model_name,
            'model_temperature': config.model_temperature,
            'model_api_key': config.model_api_key,
            'max_steps': config.max_steps,
            'lang': config.lang,
            'verbose': config.verbose,
            'step_duration': config.step_duration,
            'analysis_workers': config.analysis_workers,
        },
    }

    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        temp_config_file = f.name

    try:
        # Call GUIAgentRunner.run_testcase
        device_id = config.device_id
        GUIAgentRunner.run_testcase(
            config_file=temp_config_file,
            output=output_path,
            device_id=device_id,
        )

        # Check execution result (by checking if output directory exists and contains report files)
        # Since run_testcase is a blocking call, reports should have been generated after execution
        test_info_path = os.path.join(output_path, 'testInfo.json')
        if os.path.exists(test_info_path):
            # Read test info for more details
            with open(test_info_path, encoding='utf-8') as f:
                test_info = json.load(f)

            # Check for errors (by checking steps.json or other methods)
            steps_path = os.path.join(output_path, 'steps.json')
            success = os.path.exists(steps_path)

            return SceneResult(
                scene=scene,
                success=success,
                result=test_info.get('scene', scene) if success else 'Execution completed but step info not found',
                error=None if success else 'Step info file not found',
            )
        # If testInfo.json doesn't exist, execution may have failed
        return SceneResult(
            scene=scene,
            success=False,
            result='',
            error='Test execution failed: test info file not generated',
        )

    except Exception as e:
        logging.error('Scene execution failed: %s', e, exc_info=True)
        return SceneResult(
            scene=scene,
            success=False,
            result='',
            error=str(e),
        )
    finally:
        # Clean up temporary config file
        try:
            if os.path.exists(temp_config_file):
                os.unlink(temp_config_file)
        except Exception as e:
            logging.warning('Failed to clean up temporary config file: %s', e)


def categorize_bundle(app_package: str) -> str:
    b = app_package.lower()
    if any(
        k in b
        for k in (
            'taobao',
            'tmall',
            'jd.',
            'pinduoduo',
            'vip',
            'dewu',
            'idlefish',
            'zhuanzhuan',
            'hippo',
            'ddmc',
            'samsclub',
            'damai',
            'cainiao',
        )
    ):
        return 'ecommerce'
    if any(k in b for k in ('alipay', 'bank', 'icbc', 'ccb', 'cmb', 'psbc', 'pingan')):
        return 'finance'
    if any(k in b for k in ('meituan', 'dianping', 'eleme', 'wuba', 'beike', 'anjuke', 'luckin', 'kfc', 'charge')):
        return 'life'
    if any(
        k in b
        for k in (
            'amap',
            'mtthm',
            'didi',
            'ctrip',
            'qunar',
            'tongcheng',
            'fliggy',
            'umetrip',
            'htinns',
            'abroad',
            'leo',
            'solar',
            'etc',
        )
    ):
        return 'travel'
    if any(
        k in b
        for k in ('aweme', 'kuaishou', 'bili', 'videohm', 'qiyi', 'youku', 'yangshipin', 'cmvideohm', 'taobaolive')
    ):
        return 'video'
    if any(k in b for k in ('qqmusic', 'kugou', 'music', 'ximalaya', 'ting', 'fm', 'read', 'novel')):
        return 'audio_reading'
    if any(k in b for k in ('weibo', 'mqq', 'xhs', 'zhihu', 'wechat')):
        return 'social'
    if any(
        k in b
        for k in (
            'dingtalk',
            'feishu',
            'meeting',
            'wps',
            'docs',
            'netdisk',
            'browser',
            'quark',
            'uc.',
            'tianyancha',
            'kimi',
        )
    ):
        return 'productivity'
    if any(k in b for k in ('news', 'article', 'dcar', 'autohome', 'yiche', 'hupu', 'zhibo8')):
        return 'news'
    if any(k in b for k in ('meitu', 'beautycam', 'retouch', 'lemon', 'camera')):
        return 'photo_video_edit'
    if any(k in b for k in ('zuoyebang', 'kuaiduizuoye', 'baicizhan', 'youdao', 'ihuman', 'jiaxiao', 'babybus')):
        return 'education'
    return 'general'


def get_scenes_from_config(app_package: str) -> list[str]:
    """
    Get category based on app package name and retrieve corresponding scene list from config.

    Args:
        app_package: Application package name

    Returns:
        List of scene descriptions
    """
    # Get app category
    category = categorize_bundle(app_package)
    logging.info('App %s categorized as: %s', app_package, category)

    # Get scenes from config
    try:
        config = Config()
        scenes = []

        # Use getattr to access gui-agent config (Python allows getattr to access attributes with special characters)
        try:
            gui_agent_config = getattr(config.data, 'gui-agent', None)
            if gui_agent_config and hasattr(gui_agent_config, 'scenes'):
                scenes_config = gui_agent_config.scenes
                if hasattr(scenes_config, category):
                    scenes = getattr(scenes_config, category)
        except AttributeError:
            pass

        if not scenes:
            # If category has no configured scenes, use default
            logging.warning('Category %s has no configured scenes, using default scenes', category)
            try:
                gui_agent_config = getattr(config.data, 'gui-agent', None)
                if gui_agent_config and hasattr(gui_agent_config, 'scenes'):
                    scenes_config = gui_agent_config.scenes
                    if hasattr(scenes_config, 'default'):
                        scenes = scenes_config.default
            except AttributeError:
                pass

        if scenes:
            logging.info('Retrieved %d scenes from config', len(scenes))
        else:
            logging.warning('No scene configuration found')

        return scenes if isinstance(scenes, list) else []
    except Exception as e:
        logging.error('Failed to get scene configuration: %s', e, exc_info=True)
        return []


def execute_scenes(app_packages: list[str], scenes: Optional[list[str]], config: GuiAgentConfig) -> int:
    """
    Execute scene tests.

    Args:
        app_packages: List of application package names
        scenes: List of scene descriptions (optional, if None, get from config based on app category)
        config: GuiAgentConfig configuration object

    Returns:
        Return code, 0 for success, non-zero for failure
    """
    if not app_packages:
        logging.error('No app package names provided')
        return 1

    # Initialize singleton RealTimeAnalysisProcess
    realtime_analyzer = RealTimeAnalysisProcess(
        max_workers=config.analysis_workers,
        logger=logging.getLogger(__name__),
    )
    realtime_analyzer.start()

    # Note: No need to create GuiAgent instance, as each scene is executed through GUIAgentRunner.run_testcase
    # in an independent test process, real-time analysis process is managed as a singleton

    try:
        all_results = []

        # Iterate through all apps
        for app_idx, app_package in enumerate(app_packages, 1):
            logging.info('=' * 50)
            logging.info('App %d/%d: %s', app_idx, len(app_packages), app_package)
            logging.info('=' * 50)

            # Determine scenes to execute for this app
            app_scenes = scenes
            if app_scenes is None or len(app_scenes) == 0:
                # If no scenes provided, get from config based on app category
                app_scenes = get_scenes_from_config(app_package)
                if not app_scenes:
                    logging.warning('App %s cannot get scenes from config, skipping', app_package)
                    continue

            if not app_scenes:
                logging.warning('App %s has no scenes to execute, skipping', app_package)
                continue

            # Iterate through all scenes for this app
            logging.info('App %s has %d scenes', app_package, len(app_scenes))
            for scene_idx, scene in enumerate(app_scenes, 1):
                logging.info('-' * 50)
                logging.info('App %s - Scene %d/%d: %s', app_package, scene_idx, len(app_scenes), scene)
                logging.info('-' * 50)

                # Execute scene using GUIAgentRunner.run_testcase
                result = _run_scene_with_runner(
                    app_package=app_package,
                    scene=scene,
                    scene_idx=scene_idx,
                    config=config,
                    output_base_path=config.report_path,
                )

                if result:
                    all_results.append(result)

                if result and result.success:
                    logging.info('Scene executed successfully: %s', result.result)
                elif result:
                    logging.error('Scene execution failed: %s', result.error)

        # Summarize all results
        if not all_results:
            logging.warning('No scenes executed')
            return 0

        success_count = sum(1 for r in all_results if r.success)
        failed_count = len(all_results) - success_count

        logging.info('=' * 50)
        logging.info('Scene Execution Summary')
        logging.info('=' * 50)
        logging.info('Total apps: %d', len(app_packages))
        logging.info('Total scenes: %d', len(all_results))
        logging.info('Successful: %d', success_count)
        logging.info('Failed: %d', failed_count)

        # Print detailed information
        for idx, result in enumerate(all_results, 1):
            status = '✓' if result.success else '✗'
            logging.info('%s Scene %d: %s', status, idx, result.scene)
            if result.success:
                logging.info('  Result: %s', result.result)
            else:
                logging.info('  Error: %s', result.error)

        # Wait for all real-time analysis tasks to complete
        try:
            logging.info('Waiting for all real-time analysis tasks to complete...')
            realtime_analyzer.wait_completion()
            logging.info('All real-time analysis tasks completed')
        except Exception as e:
            logging.warning('Error waiting for real-time analysis tasks: %s', e)

        return 0 if failed_count == 0 else 1

    except KeyboardInterrupt:
        logging.warning('Execution interrupted by user')
        # Wait for analysis tasks even on interruption
        try:
            if realtime_analyzer:
                realtime_analyzer.wait_completion()
        except Exception as e:
            logging.warning('Error waiting for real-time analysis tasks: %s', e)
        return 130
    except Exception as e:
        logging.error('Execution failed: %s', e, exc_info=True)
        # Wait for analysis tasks even on error
        try:
            if realtime_analyzer:
                realtime_analyzer.wait_completion()
        except Exception as e2:
            logging.warning('Error waiting for real-time analysis tasks: %s', e2)
        return 1
    finally:
        # Shutdown real-time analysis process
        try:
            if realtime_analyzer:
                realtime_analyzer.shutdown()
                logging.info('Real-time analysis process shutdown')
        except Exception as e:
            logging.warning('Error shutting down real-time analysis process: %s', e)
