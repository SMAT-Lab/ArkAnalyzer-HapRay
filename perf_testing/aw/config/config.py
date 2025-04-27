import os.path

import yaml
from typing import Any, Dict

class ConfigError(Exception):
    """自定义配置异常"""
    pass

class ConfigObject:
    """将字典转换为可点属性访问的对象"""
    def __init__(self, data: Dict[str, Any]):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, ConfigObject(value))
            else:
                setattr(self, key, value)

class Config:
    _instance = None  # 单例实例
    _config_path = os.path.join(os.path.dirname(__file__), "config.yaml")  # 默认配置文件路径
    _data = None  # 配置数据

    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = None):
        if config_path:
            self._config_path = config_path
        if not self._data:
            self.reload()

    def reload(self):
        """重新加载配置文件"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
                self._data = ConfigObject(raw_data)
        except FileNotFoundError:
            raise ConfigError(f"配置文件未找到: {self._config_path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML 解析错误: {str(e)}")

    def __getattr__(self, name: str) -> Any:
        """通过属性访问配置项"""
        if self._data is None:
            raise ConfigError("配置未初始化，请先调用 reload()")
        return getattr(self._data, name)

    @property
    def config_path(self) -> str:
        """获取当前配置文件路径"""
        return self._config_path

    @classmethod
    def get(cls, key_path: str, default: Any = None) -> Any:
        """通过路径字符串获取配置（如 'database.host'）"""
        keys = key_path.split('.')
        value = cls._instance._data
        try:
            for key in keys:
                value = getattr(value, key)
            return value
        except AttributeError:
            if default is not None:
                return default
            raise ConfigError(f"配置项不存在: {key_path}")
