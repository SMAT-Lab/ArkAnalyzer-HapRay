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

import os
import threading
from importlib.resources import files
from typing import Any, Optional

import yaml


class ConfigError(Exception):
    """自定义配置异常"""


class ConfigObject:
    """将字典转换为可点属性访问的对象"""

    def __init__(self, data: dict[str, Any]):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, ConfigObject(value))
            else:
                setattr(self, key, value)


def deep_merge(default: dict, custom: dict) -> dict:
    """深度合并两个字典，custom中的值覆盖default中的值"""
    merged = default.copy()
    for key, value in custom.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class Config:
    _instance = None  # 单例实例
    _lock = threading.Lock()  # 线程安全锁
    _default_config_path = files('hapray.core.config').joinpath('config.yaml')  # 默认配置文件路径
    _user_config_path = None  # 用户自定义配置文件路径
    _data = None  # 配置数据
    _initialized = False  # 是否已初始化标志

    def __new__(cls, *args, **kwargs):
        """单例模式实现（线程安全）"""
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, user_config_path: Optional[str] = None):
        """初始化配置，只在第一次调用时加载配置"""
        if not self._initialized:
            with self._lock:
                if not self._initialized:  # 双重检查锁定
                    self._user_config_path = user_config_path
                    self.reload()
                    self._initialized = True

    @property
    def data(self):
        return self._data

    def reload(self):
        """重新加载配置文件，合并默认配置和用户配置"""
        try:
            # 加载默认配置
            default_config = self._load_config(self._default_config_path)

            # 加载用户配置（如果存在）
            user_config = {}
            if self._user_config_path and os.path.exists(self._user_config_path):
                user_config = self._load_config(self._user_config_path)

            # 合并配置（用户配置覆盖默认配置）
            merged_config = deep_merge(default_config, user_config)
            self._data = ConfigObject(merged_config)

        except FileNotFoundError as e:
            raise ConfigError(f'配置文件未找到: {str(e)}') from e
        except yaml.YAMLError as e:
            raise ConfigError(f'YAML 解析错误: {str(e)}') from e

    def _load_config(self, path) -> dict:
        """加载YAML配置文件"""
        try:
            if isinstance(path, str):
                # 处理文件路径
                with open(path, encoding='utf-8') as f:
                    return yaml.safe_load(f)
            else:
                # 处理importlib.resources路径
                return yaml.safe_load(path.read_text(encoding='utf-8'))
        except FileNotFoundError as e:
            raise ConfigError(f'配置文件未找到: {str(path)}') from e

    def __getattr__(self, name: str) -> Any:
        """通过属性访问配置项"""
        if self._data is None:
            raise ConfigError('配置未初始化，请先调用 reload()')
        return getattr(self._data, name)

    @property
    def default_config_path(self) -> str:
        """获取默认配置文件路径"""
        return str(self._default_config_path)

    @property
    def user_config_path(self) -> Optional[str]:
        """获取用户配置文件路径"""
        return self._user_config_path

    def set_user_config_path(self, path: str):
        """设置用户配置路径并重新加载配置"""
        with self._lock:
            self._user_config_path = path
            self.reload()

    @classmethod
    def get(cls, key_path: str, default: Any = None) -> Any:
        """通过路径字符串获取配置（如 'database.host'）"""
        if cls._instance is None:
            Config()
        keys = key_path.split('.')
        value = cls._instance.data
        try:
            for key in keys:
                value = getattr(value, key)
            if value is None and default is not None:
                return default
            return value
        except AttributeError:
            return default

    @classmethod
    def set(cls, key_path: str, value: Any):
        """
        设置配置值（支持点分隔路径）

        :param key_path: 配置路径（如 "hiperf.duration"）
        :param value: 要设置的值

        """
        if cls._instance is None:
            Config()

        keys = key_path.split('.')
        # 更新配置对象
        obj = cls._instance.data
        for key in keys[:-1]:
            obj = getattr(obj, key)
        setattr(obj, keys[-1], value)
