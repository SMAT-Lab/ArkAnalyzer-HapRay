"""
插件基类 - 提供插件工具的基础功能
"""

from pathlib import Path
from typing import Any, Optional

from core.base_tool import BaseTool, ToolResult
from core.config_manager import ConfigManager


class PluginTool(BaseTool):
    """插件工具基类，所有插件都应该继承此类"""

    def __init__(self, plugin_id: str, metadata: dict[str, Any]):
        """
        初始化插件工具

        Args:
            plugin_id: 插件ID
            metadata: 插件元数据（从 plugin.json 加载）
        """
        name = metadata.get('name', plugin_id)
        description = metadata.get('description', '')
        super().__init__(name, description)

        self.plugin_id = plugin_id
        self.metadata = metadata
        self.config = ConfigManager()

        # 获取插件目录
        # 优先从配置中获取路径（这是实际工具所在的路径）
        tool_path = self.config.get_plugin_path(plugin_id) or self.config.get_tool_path(plugin_id)
        if tool_path:
            self.plugin_path = Path(tool_path)
        else:
            # 如果配置中没有，尝试使用 metadata 中的 plugin_dir（插件加载器添加的）
            plugin_dir = metadata.get('plugin_dir')
            if plugin_dir:
                self.plugin_path = Path(plugin_dir)
            else:
                self.plugin_path = Path()

        # 执行配置
        self.execution_config = metadata.get('execution', {})
        self.executor_type = self.execution_config.get('type', 'python')  # python 或 node
        self.execution_mode = self.execution_config.get('mode', 'dev')  # dev 或 release

    def get_script_path(self) -> str:
        """获取脚本路径（根据模式返回 Python 脚本或 exe 文件）"""
        if self.execution_mode == 'release':
            # Release 模式：返回 exe 文件路径
            exe_config = self.execution_config.get('exe', {})

            # 如果指定了 exe 路径
            if 'path' in exe_config:
                exe_path = self.plugin_path / exe_config['path']
                if exe_path.exists():
                    return str(exe_path)

            # 默认查找常见 exe 文件名
            default_exes = exe_config.get('defaults', [])
            for exe_name in default_exes:
                exe_path = self.plugin_path / exe_name
                if exe_path.exists():
                    return str(exe_path)

            # 如果都没找到，返回第一个默认值
            if default_exes:
                return str(self.plugin_path / default_exes[0])

            # 最后尝试常见的 exe 文件名
            plugin_name = self.plugin_id.replace('_', '-')
            for common in [f'{plugin_name}.exe', 'main.exe', 'cli.exe']:
                common_path = self.plugin_path / common
                if common_path.exists():
                    return str(common_path)

            # 如果都没找到，返回默认路径
            return str(self.plugin_path / f'{plugin_name}.exe')
        # Dev 模式：返回 Python 脚本路径
        script_config = self.execution_config.get('script', {})

        # 如果指定了脚本路径
        if 'path' in script_config:
            script_path = self.plugin_path / script_config['path']
            if script_path.exists():
                return str(script_path)

        # 默认查找常见入口文件
        default_scripts = script_config.get('defaults', [])
        for script_name in default_scripts:
            script_path = self.plugin_path / script_name
            if script_path.exists():
                return str(script_path)

        # 如果都没找到，返回第一个默认值
        if default_scripts:
            return str(self.plugin_path / default_scripts[0])

        # 最后尝试常见的入口文件
        for common in ['main.py', 'cli.py', 'index.js', 'bundle.js']:
            common_path = self.plugin_path / common
            if common_path.exists():
                return str(common_path)

        return str(self.plugin_path / 'main.py')

    def get_execution_mode(self) -> str:
        """获取执行模式"""
        return self.execution_mode

    def is_release_mode(self) -> bool:
        """检查是否为发布模式"""
        return self.execution_mode == 'release'

    def get_working_dir(self) -> Optional[str]:
        """获取工作目录"""
        working_dir_config = self.execution_config.get('working_dir')
        if working_dir_config:
            if isinstance(working_dir_config, str):
                # 相对路径，相对于插件目录
                working_dir = self.plugin_path / working_dir_config
            else:
                # 绝对路径
                working_dir = Path(working_dir_config)

            if working_dir.exists():
                return str(working_dir)

        # 默认使用插件目录
        return str(self.plugin_path) if self.plugin_path.exists() else None

    def get_parameters(self) -> dict[str, Any]:
        """获取参数定义（从元数据中读取）"""
        return self.metadata.get('parameters', {})

    def get_config_schema(self) -> dict[str, Any]:
        """获取配置项定义（从元数据中读取）"""
        return self.metadata.get('config', {})

    def get_config_value(self, config_key: str, default: Any = None) -> Any:
        """
        获取插件配置值

        Args:
            config_key: 配置键名（支持点号分隔的嵌套键）
            default: 默认值

        Returns:
            配置值
        """
        return self.config.get(f'plugins.{self.plugin_id}.config.{config_key}', default)

    def set_config_value(self, config_key: str, value: Any):
        """
        设置插件配置值

        Args:
            config_key: 配置键名（支持点号分隔的嵌套键）
            value: 配置值
        """
        self.config.set(f'plugins.{self.plugin_id}.config.{config_key}', value)

    def get_all_config(self) -> dict[str, Any]:
        """获取所有插件配置"""
        return self.config.get(f'plugins.{self.plugin_id}.config', {})

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证参数"""
        # 检查插件路径
        if not self.plugin_path.exists():
            return False, f'插件路径不存在: {self.plugin_path}'

        # 检查脚本路径
        script_path = Path(self.get_script_path())
        if not script_path.exists():
            return False, f'脚本文件不存在: {script_path}'

        # 检查必需参数
        parameters = self.get_parameters()
        for param_name, param_def in parameters.items():
            if param_def.get('required', False) and (param_name not in params or not params[param_name]):
                label = param_def.get('label', param_name)
                return False, f"必需参数 '{label}' 未提供"

        # 执行自定义验证规则（如果存在）
        validation_config = self.metadata.get('validation', {})
        if validation_config.get('custom', False):
            # 执行自定义验证逻辑
            return self._validate_custom_rules(params, validation_config)

        return True, None

    def _validate_custom_rules(
        self, params: dict[str, Any], validation_config: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        执行自定义验证规则

        Args:
            params: 参数字典
            validation_config: 验证配置

        Returns:
            (是否有效, 错误信息)
        """
        # 获取验证规则
        rules = validation_config.get('rules', [])

        # 执行每个规则
        for rule in rules:
            rule_type = rule.get('type')

            if rule_type == 'file_exists':
                # 检查文件是否存在
                param_name = rule.get('param')
                if param_name in params and params[param_name]:
                    file_path = Path(params[param_name])
                    if not file_path.exists():
                        return False, f'文件不存在: {file_path}'

            elif rule_type == 'dir_exists':
                # 检查目录是否存在
                param_name = rule.get('param')
                if param_name in params and params[param_name]:
                    dir_path = Path(params[param_name])
                    if not dir_path.exists():
                        return False, f'目录不存在: {dir_path}'

            elif rule_type == 'one_of':
                # 检查至少一个参数必须提供
                param_names = rule.get('params', [])
                provided = [name for name in param_names if name in params and params[name]]
                if not provided:
                    labels = [self.get_parameters().get(name, {}).get('label', name) for name in param_names]
                    return False, f'至少需要提供以下参数之一: {", ".join(labels)}'

            elif rule_type == 'conditional':
                # 条件验证：如果某个参数存在，则检查其他参数
                condition_param = rule.get('condition')
                if condition_param in params and params[condition_param]:
                    required_params = rule.get('required', [])
                    for req_param in required_params:
                        if req_param not in params or not params[req_param]:
                            label = self.get_parameters().get(req_param, {}).get('label', req_param)
                            return (
                                False,
                                f"当提供 '{condition_param}' 时，'{label}' 是必需的",
                            )

        # 特殊处理：符号恢复插件的模式验证
        if self.plugin_id == 'symbol_recovery':
            excel_file = params.get('excel_file')
            perf_data = params.get('perf_data')

            if excel_file and not Path(excel_file).exists():
                # Excel模式
                return False, f'Excel文件不存在: {excel_file}'
            if perf_data and not Path(perf_data).exists():
                # Perf模式
                return False, f'perf.data文件不存在: {perf_data}'

        return True, None

    def execute(self, params: dict[str, Any]) -> ToolResult:
        """执行工具（实际执行在ToolExecutor中完成）"""
        return ToolResult(success=True, message='工具将在ToolExecutor中执行')

    def get_executor_type(self) -> str:
        """获取执行器类型"""
        return self.executor_type
