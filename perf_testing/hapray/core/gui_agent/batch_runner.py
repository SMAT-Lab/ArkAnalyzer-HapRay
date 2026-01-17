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
from hapray.core.gui_agent import GuiAgentConfig
from hapray.core.gui_agent.gui_agent import SceneResult
from hapray.core.gui_agent.gui_agent_runner import GUIAgentRunner


def _run_scene_with_runner(
    app_package: str,
    scene: str,
    scene_idx: int,
    config: GuiAgentConfig,
    output_base_path: Optional[str] = None,
) -> Optional['SceneResult']:
    """
    使用 GUIAgentRunner.run_testcase 执行单个场景

    Args:
        app_package: 应用包名
        scene: 场景描述
        scene_idx: 场景索引
        config: GuiAgentConfig 配置对象
        output_base_path: 输出基础路径

    Returns:
        SceneResult 对象，如果执行失败则返回 None
    """
    # 确定输出路径
    if output_base_path:
        output_path = os.path.join(output_base_path, app_package, f'scene{scene_idx}')
    else:
        output_path = os.path.join(tempfile.gettempdir(), 'gui_agent_test', app_package, f'scene{scene_idx}')

    # 创建临时配置文件
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

    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        temp_config_file = f.name

    try:
        # 调用 GUIAgentRunner.run_testcase
        device_id = config.device_id
        GUIAgentRunner.run_testcase(
            config_file=temp_config_file,
            output=output_path,
            device_id=device_id,
        )

        # 检查执行结果（通过检查输出目录是否存在和包含报告文件）
        # 由于 run_testcase 是阻塞调用，执行完成后应该已经生成报告
        test_info_path = os.path.join(output_path, 'testInfo.json')
        if os.path.exists(test_info_path):
            # 读取测试信息以获取更多详情
            with open(test_info_path, encoding='utf-8') as f:
                test_info = json.load(f)

            # 检查是否有错误（通过检查 steps.json 或其他方式）
            steps_path = os.path.join(output_path, 'steps.json')
            success = os.path.exists(steps_path)

            return SceneResult(
                scene=scene,
                success=success,
                result=test_info.get('scene', scene) if success else '执行完成但未找到步骤信息',
                error=None if success else '未找到步骤信息文件',
            )
        # 如果连 testInfo.json 都不存在，说明执行可能失败了
        return SceneResult(
            scene=scene,
            success=False,
            result='',
            error='测试执行失败：未生成测试信息文件',
        )

    except Exception as e:
        logging.error(f'执行场景失败: {e}', exc_info=True)
        return SceneResult(
            scene=scene,
            success=False,
            result='',
            error=str(e),
        )
    finally:
        # 清理临时配置文件
        try:
            if os.path.exists(temp_config_file):
                os.unlink(temp_config_file)
        except Exception as e:
            logging.warning(f'清理临时配置文件失败: {e}')


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
    根据应用包名获取分类，并从配置中获取对应的场景列表

    Args:
        app_package: 应用包名

    Returns:
        场景描述列表
    """
    # 获取应用分类
    category = categorize_bundle(app_package)
    logging.info(f'应用 {app_package} 分类为: {category}')

    # 从配置中获取场景
    try:
        config = Config()
        scenes = []

        # 直接使用 getattr 访问 gui-agent 配置（Python 允许使用 getattr 访问包含特殊字符的属性）
        try:
            gui_agent_config = getattr(config.data, 'gui-agent', None)
            if gui_agent_config and hasattr(gui_agent_config, 'scenes'):
                scenes_config = gui_agent_config.scenes
                if hasattr(scenes_config, category):
                    scenes = getattr(scenes_config, category)
        except AttributeError:
            pass

        if not scenes:
            # 如果分类对应的场景不存在，使用 default
            logging.warning(f'分类 {category} 没有配置场景，使用 default 场景')
            try:
                gui_agent_config = getattr(config.data, 'gui-agent', None)
                if gui_agent_config and hasattr(gui_agent_config, 'scenes'):
                    scenes_config = gui_agent_config.scenes
                    if hasattr(scenes_config, 'default'):
                        scenes = scenes_config.default
            except AttributeError:
                pass

        if scenes:
            logging.info(f'从配置中获取到 {len(scenes)} 个场景')
        else:
            logging.warning('未找到任何场景配置')

        return scenes if isinstance(scenes, list) else []
    except Exception as e:
        logging.error(f'获取场景配置失败: {e}', exc_info=True)
        return []


def execute_scenes(app_packages: list[str], scenes: Optional[list[str]], config: GuiAgentConfig) -> int:
    """
    执行场景测试

    Args:
        app_packages: 应用包名列表
        scenes: 场景描述列表（可选，如果为None则从配置中根据应用分类获取）
        config: GuiAgentConfig 配置对象

    Returns:
        返回码，0表示成功，非0表示失败
    """
    if not app_packages:
        logging.error('未提供应用包名')
        return 1

    # 注意：不再需要创建 GuiAgent 实例，因为每个场景都通过 GUIAgentRunner.run_testcase
    # 在独立的测试进程中执行，实时分析进程会在各自的 GUIAgentRunner 实例中管理

    try:
        all_results = []
        task_id = 1

        # 遍历所有应用
        for app_idx, app_package in enumerate(app_packages, 1):
            logging.info('=' * 50)
            logging.info(f'应用 {app_idx}/{len(app_packages)}: {app_package}')
            logging.info('=' * 50)

            # 确定该应用要执行的场景
            app_scenes = scenes
            if app_scenes is None or len(app_scenes) == 0:
                # 如果没有提供 scenes，从配置中根据应用分类获取
                app_scenes = get_scenes_from_config(app_package)
                if not app_scenes:
                    logging.warning(f'应用 {app_package} 无法从配置中获取场景，跳过')
                    continue

            if not app_scenes:
                logging.warning(f'应用 {app_package} 没有场景要执行，跳过')
                continue

            # 遍历该应用的所有场景
            logging.info(f'应用 {app_package} 共有 {len(app_scenes)} 个场景')
            for scene_idx, scene in enumerate(app_scenes, 1):
                logging.info('-' * 50)
                logging.info(f'应用 {app_package} - 场景 {scene_idx}/{len(app_scenes)}: {scene}')
                logging.info('-' * 50)

                # 使用 GUIAgentRunner.run_testcase 执行场景
                result = _run_scene_with_runner(
                    app_package=app_package,
                    scene=scene,
                    scene_idx=task_id,
                    config=config,
                    output_base_path=config.report_path,
                )

                if result:
                    all_results.append(result)
                task_id += 1

                if result and result.success:
                    logging.info(f'场景执行成功: {result.result}')
                elif result:
                    logging.error(f'场景执行失败: {result.error}')

        # 汇总所有结果
        if not all_results:
            logging.warning('没有执行任何场景')
            return 0

        success_count = sum(1 for r in all_results if r.success)
        failed_count = len(all_results) - success_count

        logging.info('=' * 50)
        logging.info('Scene Execution Summary')
        logging.info('=' * 50)
        logging.info(f'Total apps: {len(app_packages)}')
        logging.info(f'Total scenes: {len(all_results)}')
        logging.info(f'Successful: {success_count}')
        logging.info(f'Failed: {failed_count}')

        # 打印详细信息
        for idx, result in enumerate(all_results, 1):
            status = '✓' if result.success else '✗'
            logging.info(f'{status} Scene {idx}: {result.scene}')
            if result.success:
                logging.info(f'  Result: {result.result}')
            else:
                logging.info(f'  Error: {result.error}')

        # 注意：实时分析任务会在每个 GUIAgentRunner 实例的 teardown 中处理
        # 由于 run_testcase 是阻塞调用，每个场景执行完成后，实时分析应该已经完成或正在后台执行
        logging.info('所有场景执行完成，实时分析任务由各自的 GUIAgentRunner 实例管理')

        return 0 if failed_count == 0 else 1

    except KeyboardInterrupt:
        logging.warning('Execution interrupted by user')
        return 130
    except Exception as e:
        logging.error(f'Execution failed: {e}', exc_info=True)
        return 1
