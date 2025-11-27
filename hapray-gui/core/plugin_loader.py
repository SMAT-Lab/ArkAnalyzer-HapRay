"""
插件加载器 - 自动发现和加载插件（基于描述文件）
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

from core.base_tool import BaseTool
from core.logger import get_logger
from core.plugin_base import PluginTool

logger = get_logger(__name__)


class PluginLoader:
    """插件加载器"""

    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        初始化插件加载器

        Args:
            plugins_dir: 插件目录路径，默认为项目根目录下的 tools 目录
        """
        if plugins_dir is None:
            # 默认使用项目根目录下的 tools 目录
            # 在打包后的环境中，从可执行文件位置推断工具目录
            if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
                # PyInstaller 打包后的情况
                exe_dir = Path(sys.executable).parent
                # 尝试多个可能的路径
                possible_paths = [
                    exe_dir / 'tools',  # 如果tools在exe同级目录
                    exe_dir.parent / 'tools',  # 如果tools在exe父目录
                    exe_dir.parent,  # 直接使用父目录作为插件根目录
                ]
                plugins_dir = None
                for path in possible_paths:
                    if path.exists():
                        plugins_dir = path
                        break
                if plugins_dir is None:
                    # 如果都找不到，使用exe父目录
                    plugins_dir = exe_dir.parent
            else:
                # 开发环境
                plugins_dir = Path(__file__).parent.parent.parent
        self.plugins_dir = Path(plugins_dir).resolve()
        self.plugins: dict[str, BaseTool] = {}
        self.plugin_metadata: dict[str, dict[str, Any]] = {}

    def discover_plugins(self) -> list[str]:
        """
        发现所有插件（只需要 plugin.json）

        Returns:
            插件ID列表
        """
        plugin_ids = []
        if not self.plugins_dir.exists():
            logger.warning(f'插件目录不存在: {self.plugins_dir}')
            return plugin_ids

        # 遍历插件目录
        for item in self.plugins_dir.iterdir():
            if not item.is_dir():
                continue

            # 只检查是否包含 plugin.json
            plugin_json = item / 'plugin.json'

            if plugin_json.exists():
                plugin_id = item.name
                plugin_ids.append(plugin_id)
                logger.info(f'发现插件: {plugin_id}')
            else:
                logger.debug(f'跳过目录 {item.name}（缺少 plugin.json）')

        return plugin_ids

    def load_plugin_metadata(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """
        加载插件元数据

        Args:
            plugin_id: 插件ID（目录名，用于定位插件）

        Returns:
            插件元数据字典，如果加载失败返回 None
        """
        plugin_dir = self.plugins_dir / plugin_id
        plugin_json = plugin_dir / 'plugin.json'

        if not plugin_json.exists():
            logger.error(f'插件 {plugin_id} 的 plugin.json 不存在')
            return None

        try:
            with open(plugin_json, encoding='utf-8') as f:
                metadata = json.load(f)

            # 验证必需的字段
            required_fields = ['name', 'description', 'version']
            for field in required_fields:
                if field not in metadata:
                    logger.error(f'插件 {plugin_id} 的 plugin.json 缺少必需字段: {field}')
                    return None

            # 从 plugin.json 中读取 id 字段，如果没有则使用目录名作为回退
            if 'id' not in metadata:
                metadata['id'] = plugin_id
                logger.warning(f'插件 {plugin_id} 的 plugin.json 中没有 id 字段，使用目录名作为插件ID')
            # 如果存在 id 字段，直接使用（无需额外赋值）

            # 添加目录路径（确保是绝对路径）
            plugin_dir_resolved = plugin_dir.resolve()
            metadata['plugin_dir'] = str(plugin_dir_resolved)

            return metadata
        except json.JSONDecodeError as e:
            logger.error(f'解析插件 {plugin_id} 的 plugin.json 失败: {e}')
            return None
        except Exception as e:
            logger.error(f'加载插件 {plugin_id} 的元数据失败: {e}')
            return None

    def load_plugin(self, plugin_id: str) -> Optional[str]:
        """
        加载单个插件（基于描述文件）

        Args:
            plugin_id: 插件目录名（用于定位插件）

        Returns:
            成功加载时返回实际的插件ID，失败返回 None
        """
        # 加载元数据
        metadata = self.load_plugin_metadata(plugin_id)
        if metadata is None:
            return None

        try:
            # 从元数据中获取实际的插件ID（从 plugin.json 的 id 字段读取）
            actual_plugin_id = metadata.get('id', plugin_id)

            # 检查是否已存在相同ID的插件
            if actual_plugin_id in self.plugins:
                logger.warning(f'插件ID {actual_plugin_id} 已存在，跳过加载（目录: {plugin_id}）')
                return None

            # 直接使用 PluginTool 基类创建插件实例
            plugin_instance = PluginTool(plugin_id=actual_plugin_id, metadata=metadata)

            # 存储插件实例和元数据（使用实际的插件ID作为键）
            self.plugins[actual_plugin_id] = plugin_instance
            self.plugin_metadata[actual_plugin_id] = metadata

            logger.info(f'成功加载插件: {actual_plugin_id} ({metadata["name"]}) [目录: {plugin_id}]')
            return actual_plugin_id
        except Exception as e:
            logger.error(f'实例化插件 {plugin_id} 失败: {e}', exc_info=True)
            return None

    def load_all_plugins(self) -> list[str]:
        """
        加载所有发现的插件

        Returns:
            成功加载的插件ID列表（使用 plugin.json 中定义的 id）
        """
        plugin_dirs = self.discover_plugins()
        loaded_plugins = []

        for plugin_dir in plugin_dirs:
            actual_plugin_id = self.load_plugin(plugin_dir)
            if actual_plugin_id:
                loaded_plugins.append(actual_plugin_id)

        logger.info(f'共加载 {len(loaded_plugins)}/{len(plugin_dirs)} 个插件')
        return loaded_plugins

    def get_plugin(self, plugin_id: str) -> Optional[BaseTool]:
        """
        获取插件实例

        Args:
            plugin_id: 插件ID

        Returns:
            插件实例，如果不存在返回 None
        """
        return self.plugins.get(plugin_id)

    def get_plugin_metadata(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """
        获取插件元数据

        Args:
            plugin_id: 插件ID

        Returns:
            插件元数据，如果不存在返回 None
        """
        return self.plugin_metadata.get(plugin_id)

    def get_all_plugins(self) -> dict[str, BaseTool]:
        """
        获取所有已加载的插件

        Returns:
            插件ID到插件实例的字典
        """
        return self.plugins.copy()

    def get_all_plugin_metadata(self) -> dict[str, dict[str, Any]]:
        """
        获取所有插件的元数据

        Returns:
            插件ID到元数据的字典
        """
        return self.plugin_metadata.copy()
