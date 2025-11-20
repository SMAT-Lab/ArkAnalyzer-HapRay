"""
配置管理器 - 管理应用配置和工具路径
"""

import json
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """配置管理器"""

    _instance = None
    _config_file = 'config.json'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config_dir = Path.home() / '.hapray-gui'
        self.config_path = self.config_dir / self._config_file
        self.config: dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f'加载配置失败: {e}')
                self.config = {}
        else:
            self.config = self._get_default_config()
            self._save_config()

    def _get_default_config(self) -> dict[str, Any]:
        """获取默认配置"""
        # 获取项目根目录的父目录
        project_root = Path(__file__).parent.parent.parent
        return {
            'plugins': {
                'perf_testing': {
                    'path': str(project_root / 'perf_testing'),
                    'python': 'python',
                    'enabled': True,
                    'config': {},
                },
                'optimization_detector': {
                    'path': str(project_root / 'tools' / 'optimization_detector'),
                    'python': 'python',
                    'enabled': True,
                    'config': {},
                },
                'symbol_recovery': {
                    'path': str(project_root / 'tools' / 'symbol_recovery'),
                    'python': 'python',
                    'enabled': True,
                    'config': {},
                },
                'sa': {
                    'path': str(project_root / 'sa'),
                    'node': 'node',
                    'enabled': True,
                    'config': {},
                },
            },
            'tools': {
                # 保留旧配置以兼容
                'perf_testing': {
                    'path': str(project_root / 'perf_testing'),
                    'python': 'python',
                    'enabled': True,
                },
                'optimization_detector': {
                    'path': str(project_root / 'tools' / 'optimization_detector'),
                    'python': 'python',
                    'enabled': True,
                },
                'symbol_recovery': {
                    'path': str(project_root / 'tools' / 'symbol_recovery'),
                    'python': 'python',
                    'enabled': True,
                },
                'sa': {
                    'path': str(project_root / 'sa'),
                    'node': 'node',
                    'enabled': True,
                },
            },
            'ui': {
                'theme': 'light',
                'language': 'zh_CN',
                'window_width': 1200,
                'window_height': 800,
            },
            'output': {'default_dir': str(Path.home() / 'hapray_output')},
        }

    def _save_config(self):
        """保存配置"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f'保存配置失败: {e}')

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any):
        """设置配置值，支持点号分隔的嵌套键"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save_config()

    def get_tool_path(self, tool_name: str) -> Optional[str]:
        """获取工具路径（兼容旧代码，优先从plugins配置读取）"""
        # 先尝试从plugins配置读取
        plugin_path = self.get(f'plugins.{tool_name}.path')
        if plugin_path:
            return plugin_path
        # 回退到tools配置
        return self.get(f'tools.{tool_name}.path')

    def get_tool_config(self, tool_name: str) -> dict[str, Any]:
        """获取工具配置（兼容旧代码，优先从plugins配置读取）"""
        # 先尝试从plugins配置读取
        plugin_config = self.get(f'plugins.{tool_name}', {})
        if plugin_config:
            return plugin_config
        # 回退到tools配置
        return self.get(f'tools.{tool_name}', {})

    def get_plugin_path(self, plugin_id: str) -> Optional[str]:
        """获取插件路径"""
        return self.get(f'plugins.{plugin_id}.path')

    def get_plugin_config(self, plugin_id: str) -> dict[str, Any]:
        """获取插件配置"""
        return self.get(f'plugins.{plugin_id}', {})

    def is_tool_enabled(self, tool_name: str) -> bool:
        """检查工具是否启用（兼容旧代码）"""
        return self.get(f'tools.{tool_name}.enabled', True)

    def is_plugin_enabled(self, plugin_id: str) -> bool:
        """检查插件是否启用"""
        return self.get(f'plugins.{plugin_id}.enabled', True)

    def get_output_dir(self) -> str:
        """获取默认输出目录"""
        output_dir = self.get('output.default_dir')
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            return output_dir
        return str(Path.home() / 'hapray_output')
