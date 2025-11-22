"""
HapRay GUI 命令行入口
读取插件并生成命令行接口
"""
import argparse
import sys
from pathlib import Path
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
        self.subparsers = self.parser.add_subparsers(
            dest='plugin_id', help='可用插件', metavar='PLUGIN'
        )
        self._load_plugins()

    def _load_plugins(self):
        """加载所有插件并创建子命令"""
        plugin_ids = self.plugin_loader.load_all_plugins()
        if not plugin_ids:
            logger.warning('未发现任何插件')

        for plugin_id in plugin_ids:
            plugin = self.plugin_loader.get_plugin(plugin_id)
            metadata = self.plugin_loader.get_plugin_metadata(plugin_id)
            if not plugin or not metadata:
                continue

            # 创建子命令解析器
            plugin_name = metadata.get('name', plugin_id)
            description = metadata.get('description', '')
            subparser = self.subparsers.add_parser(
                plugin_id, help=description, description=description
            )

            # 根据插件参数定义添加命令行参数
            parameters = plugin.get_parameters()
            for param_name, param_def in parameters.items():
                self._add_argument(subparser, param_name, param_def)

    def _add_argument(self, parser: argparse.ArgumentParser, param_name: str, param_def: dict[str, Any]):
        """添加命令行参数"""
        param_type = param_def.get('type', 'str')
        label = param_def.get('label', param_name)
        help_text = param_def.get('help', '')
        required = param_def.get('required', False)
        default = param_def.get('default', None)
        short_name = param_def.get('short', None)  # 短选项，如 'i', 'o', 'j'
        nargs = param_def.get('nargs', None)  # 多个值，如 '+', '*'

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
            if key == 'plugin_id':
                continue
            # 将命令行参数名转换回原始格式（连字符转下划线）
            param_name = key.replace('-', '_')
            params[param_name] = value
        return params

    def _execute_plugin(self, plugin_id: str, params: dict[str, Any]) -> int:
        """执行插件"""
        plugin = self.plugin_loader.get_plugin(plugin_id)
        if not plugin:
            logger.error(f'插件 {plugin_id} 不存在')
            return 1

        # 验证参数
        is_valid, error_msg = plugin.validate_parameters(params)
        if not is_valid:
            logger.error(f'参数验证失败: {error_msg}')
            return 1

        # 获取脚本路径和工作目录
        script_path = plugin.get_script_path()
        working_dir = plugin.get_working_dir()
        executor_type = plugin.get_executor_type()

        # 打印执行信息
        metadata = self.plugin_loader.get_plugin_metadata(plugin_id)
        plugin_name = metadata.get('name', plugin_id)
        logger.info(f'执行插件: {plugin_name} ({plugin_id})')
        logger.info(f'脚本路径: {script_path}')

        # 特殊处理：确保 action 参数在 perf_testing 插件中被正确处理
        # tool_executor 会将 action 作为命令的第一个参数
        # 这里我们只需要确保 params 中包含 action，executor 会自动处理

        # 根据执行器类型执行工具
        if executor_type == 'python':
            result = self.tool_executor.execute_python_tool(
                tool_name=plugin_name,
                script_path=script_path,
                params=params,
                working_dir=working_dir,
                callback=lambda line: print(line, flush=True),
            )
        elif executor_type == 'node':
            result = self.tool_executor.execute_node_tool(
                tool_name=plugin_name,
                script_path=script_path,
                params=params,
                working_dir=working_dir,
                callback=lambda line: print(line, flush=True),
            )
        else:
            logger.error(f'不支持的执行器类型: {executor_type}')
            return 1

        # 检查执行结果
        if result.success:
            logger.info('执行成功')
            if result.output_path:
                logger.info(f'输出路径: {result.output_path}')
            return 0
        else:
            logger.error(f'执行失败: {result.message}')
            if result.error:
                print(result.error, file=sys.stderr)
            return 1

    def run(self, args: Optional[list[str]] = None) -> int:
        """运行命令行接口"""
        parsed_args = self.parser.parse_args(args)

        if not parsed_args.plugin_id:
            # 如果没有指定插件，显示帮助信息
            self.parser.print_help()
            return 1

        # 转换参数
        params = self._convert_args_to_params(parsed_args)

        # 执行插件
        return self._execute_plugin(parsed_args.plugin_id, params)


def main():
    """主函数"""
    cli = CLI()
    sys.exit(cli.run())


if __name__ == '__main__':
    main()

