"""
插件基类 - 提供插件工具的基础功能
"""

import os
import sys
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
        tool_path = self.config.get_plugin_path(plugin_id)
        if tool_path:
            self.plugin_path = Path(tool_path).resolve()
        else:
            # 如果配置中没有，尝试使用 metadata 中的 plugin_dir（插件加载器添加的）
            plugin_dir = metadata.get('plugin_dir')
            if plugin_dir:
                plugin_path_obj = Path(plugin_dir)
                # 解析路径（处理相对路径和 ..），确保是绝对路径
                try:
                    self.plugin_path = plugin_path_obj.resolve()
                except (OSError, RuntimeError):
                    # 如果解析失败，尝试使用当前工作目录
                    if os.path.isabs(str(plugin_dir)):
                        self.plugin_path = Path(plugin_dir)
                    else:
                        self.plugin_path = Path(os.getcwd()) / plugin_dir
            else:
                self.plugin_path = Path()

        # 执行配置
        self.execution_config = metadata.get('execution', {})

        # 支持新格式（debug/release）和旧格式（type/mode）的兼容
        if 'debug' in self.execution_config or 'release' in self.execution_config:
            # 新格式：debug/release 模式
            if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
                # PyInstaller 打包后的环境，强制使用 release 模式
                self.execution_mode = 'release'
            else:
                # 默认使用 debug 模式
                self.execution_mode = 'debug'

        else:
            # 旧格式：type/mode（向后兼容）
            default_mode = self.execution_config.get('mode', 'dev')
            if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
                self.execution_mode = 'release'
            else:
                self.execution_mode = default_mode

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

    def get_parameters(self, action: Optional[str] = None) -> dict[str, Any]:
        """获取参数定义（从元数据中读取）

        Args:
            action: 如果指定 action，则从 actions 中获取该 action 的参数
        """
        # 如果指定了 action 且存在 actions 配置
        if action and 'actions' in self.metadata:
            action_config = self.metadata['actions'].get(action)
            if action_config:
                return action_config.get('parameters', {})
        # 否则返回全局参数（向后兼容）
        return self.metadata.get('parameters', {})

    def get_action_info(self, action: str) -> Optional[dict[str, Any]]:
        """获取指定 action 的信息"""
        if 'actions' in self.metadata:
            return self.metadata['actions'].get(action)
        return None

    def get_all_actions(self) -> list[str]:
        """获取所有支持的 action 列表"""
        if 'actions' in self.metadata:
            return list(self.metadata['actions'].keys())
        return []

    def get_action_mapping(self, action: Optional[str] = None) -> Optional[dict[str, Any]]:
        """获取 action 映射配置

        Args:
            action: action 名称，如果提供则从该 action 的配置中读取

        Returns:
            action_mapping 配置字典，格式：
            {
                "type": "position" | "remove" | "map",
                "command": ["command", "args", ...]  # 仅当 type 为 "map" 时存在
            }
        """
        # 优先从 action 配置中读取
        if action and 'actions' in self.metadata:
            action_config = self.metadata['actions'].get(action)
            if action_config and 'action_mapping' in action_config:
                return action_config.get('action_mapping')

        # 向后兼容：如果没有在 action 中配置，尝试从 execution 中读取
        execution_config = self.metadata.get('execution', {})
        return execution_config.get('action_mapping')

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

        # 检查脚本路径（get_cmd_script_path 已经包含了回退逻辑，会尝试脚本和exe）
        script_path_str = self.get_cmd_script_path()
        script_path = Path(script_path_str)
        # 解析路径（处理相对路径和 ..）
        script_path = script_path.resolve()

        if not script_path.exists():
            return False, f'脚本或可执行文件不存在: {script_path}'

        # 检查必需参数（从 params 中提取 action，如果存在）
        action = params.get('action')
        parameters = self.get_parameters(action)
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

    def get_cmd_executable(self) -> Optional[str]:
        """获取命令可执行文件路径（新格式）

        遍历 cmd 数组中的所有候选路径，返回第一个存在的可执行文件。
        支持相对路径（相对于插件目录）和系统 PATH 中的可执行文件。
        """
        if 'debug' in self.execution_config or 'release' in self.execution_config:
            mode_config = self.execution_config.get(self.execution_mode, {})
            cmd_config = mode_config.get('cmd', [])

            # 支持 cmd 作为数组格式或对象格式（向后兼容）
            if isinstance(cmd_config, list):
                # 新格式：cmd 是数组
                cmd_array = cmd_config
            elif isinstance(cmd_config, dict):
                # 旧格式：cmd 是对象，包含 defaults
                cmd_array = cmd_config.get('defaults', [])
            else:
                cmd_array = []

            if not cmd_array:
                return None

            # 遍历所有候选路径，找到第一个存在的可执行文件
            for cmd_item in cmd_array:
                executable = str(cmd_item).strip()

                # 特殊处理：如果是 "python"，尝试使用 sys.executable
                if executable.lower() in ('python', 'python3', 'python.exe', 'python3.exe'):
                    return sys.executable

                # 特殊处理：如果是 "node"，尝试查找 Node.js
                if executable.lower() in ('node', 'node.exe'):
                    # 首先尝试系统 PATH 中的 node
                    import shutil
                    node_path = shutil.which('node')
                    if node_path:
                        return node_path

                    # 如果系统没有 node，尝试查找打包的 node.exe
                    if self.plugin_path:
                        # 尝试在插件目录下查找
                        for node_name in ['node.exe', 'node']:
                            node_exe = self.plugin_path / node_name
                            if node_exe.exists():
                                return str(node_exe.resolve())

                        # 尝试在上级目录查找（可能在 tools 目录下）
                        tools_dir = self.plugin_path.parent
                        for node_name in ['node.exe', 'node']:
                            node_exe = tools_dir / node_name
                            if node_exe.exists():
                                return str(node_exe.resolve())

                    # 如果都找不到，返回 'node'（让系统报告错误）
                    return 'node'

                # 尝试解析为路径
                # 如果是相对路径（以 ./ 或 ../ 开头），相对于插件目录
                if executable.startswith('./') or executable.startswith('../'):
                    if self.plugin_path:
                        exe_path = self.plugin_path / executable
                        if exe_path.exists():
                            return str(exe_path)

                # 如果包含路径分隔符，尝试在插件目录下查找
                elif ('/' in executable or '\\' in executable) and self.plugin_path:
                    exe_path = self.plugin_path / executable
                    if exe_path.exists():
                        return str(exe_path.resolve())

                # 否则尝试在插件目录下查找
                if self.plugin_path:
                    # 尝试直接匹配
                    exe_path = self.plugin_path / executable
                    if exe_path.exists():
                        return str(exe_path.resolve())

                    # 尝试处理下划线和中划线的差异
                    if '-' in executable:
                        # 尝试将中划线替换为下划线
                        alt_executable = executable.replace('-', '_')
                        exe_path = self.plugin_path / alt_executable
                        if exe_path.exists():
                            return str(exe_path.resolve())
                    elif '_' in executable:
                        # 尝试将下划线替换为中划线
                        alt_executable = executable.replace('_', '-')
                        exe_path = self.plugin_path / alt_executable
                        if exe_path.exists():
                            return str(exe_path.resolve())

                # 尝试作为绝对路径
                exe_path_abs = Path(executable)
                if exe_path_abs.exists():
                    return str(exe_path_abs.resolve())

            # 如果都没找到，返回第一个作为默认值（让执行器报告错误）
            # 可能是系统 PATH 中的可执行文件
            first_cmd = str(cmd_array[0]).strip()
            # 如果第一个是 python，返回 sys.executable
            if first_cmd.lower() in ('python', 'python3', 'python.exe', 'python3.exe'):
                return sys.executable
            return first_cmd
        return None

    def get_cmd_script_path(self) -> str:
        """获取命令脚本路径（根据模式返回 Python 脚本或 exe 文件）"""
        # 确保 plugin_path 是绝对路径且已解析
        if self.plugin_path:
            self.plugin_path = self.plugin_path.resolve()

        # 支持新格式（debug/release）和旧格式（type/mode）的兼容
        if 'debug' in self.execution_config or 'release' in self.execution_config:
            # 新格式：debug/release 模式
            mode_config = self.execution_config.get(self.execution_mode, {})
            script_path_str = mode_config.get('script')  # 可选的脚本路径（字符串）

            # 对于 debug 模式，返回脚本路径
            if script_path_str:
                script_path = self.plugin_path / script_path_str
                if script_path.exists():
                    return str(script_path)
                # 即使不存在也返回（让执行器报告错误）
                return str(script_path)

        return ''
