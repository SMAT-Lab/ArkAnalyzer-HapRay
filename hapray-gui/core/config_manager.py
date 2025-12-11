"""
配置管理器 - 管理应用配置和工具路径
"""

import json
import sys
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
        # 默认输出目录：相对于exe文件的目录
        executable_dir = Path(sys.executable).parent
        default_output_dir = executable_dir / 'hapray_output'

        return {
            'plugins': {},
            'ui': {
                'theme': 'light',
                'language': 'zh_CN',
                'window_width': 1200,
                'window_height': 800,
            },
            'output': {'default_dir': str(default_output_dir)},
            'global': {
                'output_dir': './hapray_output',
                'log_level': 'INFO',
            },
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

    def get_plugin_path(self, plugin_id: str) -> Optional[str]:
        """获取插件路径"""
        return self.get(f'plugins.{plugin_id}.path')

    def get_plugin_config(self, plugin_id: str) -> dict[str, Any]:
        """获取插件配置"""
        return self.get(f'plugins.{plugin_id}', {})

    def is_plugin_enabled(self, plugin_id: str) -> bool:
        """检查插件是否启用"""
        return self.get(f'plugins.{plugin_id}.enabled', True)

    def get_output_dir(self) -> str:
        """获取默认输出目录"""
        output_dir = self.get('output.default_dir')
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            return output_dir

        # 默认输出目录：相对于exe文件的目录
        executable_dir = Path(sys.executable).parent
        default_dir = executable_dir / 'hapray_output'
        default_dir.mkdir(parents=True, exist_ok=True)
        return str(default_dir)

    def get_global_config(self, key: str, default: Any = None) -> Any:
        """
        获取全局配置值

        Args:
            key: 配置键名
            default: 默认值

        Returns:
            配置值
        """
        return self.get(f'global.{key}', default)

    def set_global_config(self, key: str, value: Any):
        """
        设置全局配置值

        Args:
            key: 配置键名
            value: 配置值
        """
        self.set(f'global.{key}', value)

    def get_all_global_config(self) -> dict[str, Any]:
        """获取所有全局配置"""
        return self.get('global', {})
