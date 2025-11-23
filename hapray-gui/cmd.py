"""
HapRay GUI 命令行入口
读取插件并生成命令行接口
"""

import argparse
import sys
from typing import Any, Optional

from core.logger import get_logger
from core.plugin_loader import PluginLoader
from core.tool_executor import ToolExecutor

logger = get_logger(__name__)


class CLI:
    """命令行接口类"""

    def __init__(self):
        self.plugin_loader = PluginLoader()
        self.tool_executor = ToolExecutor()
        self.parser = argparse.ArgumentParser(
            prog='ArkAnalyzer-HapRay',
            description='HapRay 命令行工具 - 基于插件的工具集合',
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.action_to_plugin: dict[str, str] = {}  # action -> plugin_id 映射
        self.use_action_routing = False  # 是否使用 action 路由
        self._build_action_mapping()
        self._load_commands()

    def _build_action_mapping(self):
        """构建 action 到插件的映射"""
        plugin_ids = self.plugin_loader.load_all_plugins()
        action_count: dict[str, int] = {}  # 统计每个 action 出现的次数

        for plugin_id in plugin_ids:
            plugin = self.plugin_loader.get_plugin(plugin_id)
            if not plugin:
                continue

            # 获取所有支持的 action
            actions = plugin.get_all_actions()
            for action in actions:
                action_count[action] = action_count.get(action, 0) + 1
                self.action_to_plugin[action] = plugin_id

        # 检查所有 action 是否唯一（每个 action 只对应一个插件）
        self.use_action_routing = all(count == 1 for count in action_count.values())

        if self.use_action_routing:
            logger.info('所有 action 唯一，使用 action 路由模式')
        else:
            logger.info('存在重复 action，使用插件 ID 路由模式')

    def _load_commands(self):
        """加载命令（action 或插件 ID）"""
        if self.use_action_routing:
            # 使用 action 作为子命令
            self.subparsers = self.parser.add_subparsers(dest='action', help='可用命令', metavar='COMMAND')
            for action, plugin_id in self.action_to_plugin.items():
                plugin = self.plugin_loader.get_plugin(plugin_id)
                metadata = self.plugin_loader.get_plugin_metadata(plugin_id)
                if not plugin or not metadata:
                    continue

                # 获取 action 信息
                action_info = plugin.get_action_info(action)
                if not action_info:
                    continue

                action_info.get('name', action)
                description = action_info.get('description', '')

                subparser = self.subparsers.add_parser(action, help=description, description=description)

                # 根据 action 的参数定义添加命令行参数
                parameters = plugin.get_parameters(action)
                for param_name, param_def in parameters.items():
                    self._add_argument(subparser, param_name, param_def)
        else:
            # 使用插件 ID 作为子命令（向后兼容）
            self.subparsers = self.parser.add_subparsers(dest='plugin_id', help='可用插件', metavar='PLUGIN')
            plugin_ids = self.plugin_loader.load_all_plugins()
            for plugin_id in plugin_ids:
                plugin = self.plugin_loader.get_plugin(plugin_id)
                metadata = self.plugin_loader.get_plugin_metadata(plugin_id)
                if not plugin or not metadata:
                    continue

                metadata.get('name', plugin_id)
                description = metadata.get('description', '')
                subparser = self.subparsers.add_parser(plugin_id, help=description, description=description)

                # 根据插件参数定义添加命令行参数（向后兼容）
                parameters = plugin.get_parameters()
                for param_name, param_def in parameters.items():
                    self._add_argument(subparser, param_name, param_def)

    def _add_argument(self, parser: argparse.ArgumentParser, param_name: str, param_def: dict[str, Any]):
        """添加命令行参数"""
        param_type = param_def.get('type', 'str')
        label = param_def.get('label', param_name)
        help_text = param_def.get('help', '')
        required = param_def.get('required', False)
        default = param_def.get('default')
        # 如果提供了默认值，则不需要用户必须提供该参数
        if default is not None:
            required = False
        short_name = param_def.get('short')  # 短选项，如 'i', 'o', 'j'
        nargs = param_def.get('nargs')  # 多个值，如 '+', '*'

        # 将参数名转换为命令行格式（下划线转连字符）
        arg_name = param_name.replace('_', '-')
        # 创建长参数名
        long_name = f'--{arg_name}'

        # 构建参数列表（可能包含短选项）
        arg_names = [long_name]
        if short_name:
            arg_names.insert(0, f'-{short_name}')

        # 根据类型设置不同的参数选项
        if param_type == 'bool':
            # 布尔类型使用 store_true 或 store_false
            action = 'store_true' if not default else 'store_false'
            parser.add_argument(
                *arg_names,
                action=action,
                default=default if default is not None else False,
                help=help_text or label,
            )
        elif param_type == 'choice':
            # 选择类型
            choices = param_def.get('choices', [])
            parser.add_argument(
                *arg_names,
                type=str,
                choices=choices,
                default=default,
                required=required,
                help=f'{help_text} (可选值: {", ".join(choices)})' if help_text else label,
            )
        elif param_type == 'int':
            # 整数类型
            # 如果 nargs 指定为 '+' 或 '*'，则支持多个值
            kwargs = {
                'type': int,
                'default': default,
                'required': required,
                'help': help_text or label,
            }
            if nargs:
                kwargs['nargs'] = nargs
            parser.add_argument(*arg_names, **kwargs)
        elif param_type in ('file', 'dir'):
            # 文件或目录类型
            kwargs = {
                'type': str,
                'default': default,
                'required': required,
                'help': help_text or label,
            }
            if nargs:
                kwargs['nargs'] = nargs
            parser.add_argument(*arg_names, **kwargs)
        else:
            # 字符串类型（默认）
            kwargs = {
                'type': str,
                'default': default,
                'required': required,
                'help': help_text or label,
            }
            # 根据参数名推断是否需要多个值
            if nargs:
                kwargs['nargs'] = nargs
            elif param_name in ('run_testcases', 'devices', 'perfs', 'traces', 'pids', 'time_ranges'):
                # 这些参数在 README.md 中支持多个值
                kwargs['nargs'] = '+'
            parser.add_argument(*arg_names, **kwargs)

    def _convert_args_to_params(self, args: argparse.Namespace) -> dict[str, Any]:
        """将 argparse Namespace 转换为参数字典"""
        params = {}
        for key, value in vars(args).items():
            if key in ('plugin_id', 'action'):
                continue
            # 将命令行参数名转换回原始格式（连字符转下划线）
            param_name = key.replace('-', '_')
            params[param_name] = value
        return params

    def _execute_plugin(self, plugin_id: str, action: Optional[str], params: dict[str, Any]) -> int:
        """执行插件"""
        plugin = self.plugin_loader.get_plugin(plugin_id)
        if not plugin:
            logger.error(f'插件 {plugin_id} 不存在')
            return 1

        # 如果使用 action 路由，需要将 action 添加到参数中
        if action:
            params['action'] = action

        # 验证参数
        is_valid, error_msg = plugin.validate_parameters(params)
        if not is_valid:
            logger.error(f'参数验证失败: {error_msg}')
            return 1

        # 获取元数据
        metadata = self.plugin_loader.get_plugin_metadata(plugin_id)

        # 获取脚本路径和工作目录
        script_path = plugin.get_cmd_script_path()

        # 检查是否是新的 execution 格式（debug/release）
        execution_config = metadata.get('execution', {})
        if 'debug' not in execution_config and 'release' not in execution_config:
            logger.error(f'插件 {plugin_id} execution 配置错误，请使用格式（debug/release）')
            return 1

        # 打印执行信息
        plugin_name = metadata.get('name', plugin_id)
        if action:
            action_info = plugin.get_action_info(action)
            if action_info:
                plugin_name = action_info.get('name', plugin_name)
        logger.info(f'执行插件: {plugin_name} ({plugin_id})')
        if action:
            logger.info(f'Action: {action}')
        logger.info(f'脚本路径: {script_path}')

        # 使用 cmd 配置中的可执行文件
        cmd_executable = plugin.get_cmd_executable()
        if not cmd_executable:
            logger.error('无法获取命令可执行文件')
            return 1

        # 获取插件根目录
        plugin_root_dir = None
        if hasattr(plugin, 'plugin_path') and plugin.plugin_path:
            plugin_root_dir = str(plugin.plugin_path.resolve())

        # 获取 action_mapping 配置（从 action 配置中读取）
        action_mapping = plugin.get_action_mapping(action)

        # 使用统一的执行函数
        result = self.tool_executor.execute_tool(
            plugin_id=plugin_id,
            executable_path=cmd_executable,
            script_path=script_path,
            params=params,
            plugin_root_dir=plugin_root_dir,
            callback=lambda line: logger.info(line),
            action_mapping=action_mapping,
        )

        # 检查执行结果
        if result.success:
            logger.info('执行成功')
            if result.output_path:
                logger.info(f'输出路径: {result.output_path}')
            return 0
        logger.error(f'执行失败: {result.message}')
        if result.error:
            logger.info(result.error)
        return 1

    def run(self, args: Optional[list[str]] = None) -> int:
        """运行命令行接口"""
        parsed_args = self.parser.parse_args(args)

        if self.use_action_routing:
            # 使用 action 路由
            if not parsed_args.action:
                self.parser.print_help()
                return 1

            # 根据 action 找到对应的插件
            plugin_id = self.action_to_plugin.get(parsed_args.action)
            if not plugin_id:
                logger.error(f'Action {parsed_args.action} 未找到对应的插件')
                return 1

            # 转换参数
            params = self._convert_args_to_params(parsed_args)

            # 执行插件
            return self._execute_plugin(plugin_id, parsed_args.action, params)
        # 使用插件 ID 路由（向后兼容）
        if not parsed_args.plugin_id:
            self.parser.print_help()
            return 1

        # 转换参数
        params = self._convert_args_to_params(parsed_args)

        # 执行插件
        return self._execute_plugin(parsed_args.plugin_id, None, params)


def main():
    """主函数"""
    try:
        cli = CLI()
        sys.exit(cli.run())
    except KeyboardInterrupt:
        logger.info('用户中断')
        sys.exit(130)
    except Exception as e:
        logger.error(f'程序执行失败: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
