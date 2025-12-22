"""
结果处理器 - 处理工具执行结果
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.base_tool import ToolResult
from core.config_manager import ConfigManager


class ResultProcessor:
    """结果处理器"""

    def __init__(self, output_dir: Optional[str] = None):
        self.config = ConfigManager()
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(self.config.get_output_dir())

    def save_result(self, tool_name: str, result: ToolResult, params: dict[str, Any], action_name: str = None, menu_category: str = None) -> str:
        """
        保存执行结果

        Args:
            tool_name: 工具名称
            result: 执行结果
            params: 参数
            action_name: 动作名称（可选）
            menu_category: 菜单分类（可选）

        Returns:
            保存的文件路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_dir = self.output_dir / tool_name / timestamp
        result_dir.mkdir(parents=True, exist_ok=True)

        # 保存结果JSON
        result_file = result_dir / 'result.json'
        result_data = {
            'tool_name': tool_name,
            'action_name': action_name,
            'menu_category': menu_category,
            'timestamp': timestamp,
            'success': result.success,
            'message': result.message,
            'output_path': result.output_path,
            'error': result.error,
            'params': params,
            'data': result.data,
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        # 如果结果有输出路径，创建符号链接或复制
        if result.output_path and os.path.exists(result.output_path):
            link_path = result_dir / Path(result.output_path).name
            try:
                if os.path.isdir(result.output_path):
                    # 对于目录，创建符号链接
                    if os.name == 'nt':  # Windows
                        shutil.copytree(result.output_path, link_path, dirs_exist_ok=True)
                    else:
                        os.symlink(result.output_path, link_path)
                # 对于文件，创建符号链接或复制
                elif os.name == 'nt':  # Windows
                    shutil.copy2(result.output_path, link_path)
                else:
                    os.symlink(result.output_path, link_path)
            except Exception as e:
                print(f'创建输出链接失败: {e}')

        return str(result_dir)

    def get_result_history(self, tool_name: Optional[str] = None) -> list[dict[str, Any]]:
        """获取结果历史"""
        history = []

        if tool_name:
            tool_dir = self.output_dir / tool_name
            if not tool_dir.exists():
                return history
            dirs = [d for d in tool_dir.iterdir() if d.is_dir()]
        else:
            dirs = []
            for tool_dir in self.output_dir.iterdir():
                if tool_dir.is_dir():
                    dirs.extend([d for d in tool_dir.iterdir() if d.is_dir()])

        for result_dir in sorted(dirs, reverse=True):
            result_file = result_dir / 'result.json'
            if result_file.exists():
                try:
                    with open(result_file, encoding='utf-8') as f:
                        result_data = json.load(f)
                        history.append(result_data)
                except Exception as e:
                    print(f'读取结果文件失败: {e}')

        return history

    def get_result(self, result_path: str) -> Optional[dict[str, Any]]:
        """获取指定路径的结果"""
        result_file = Path(result_path) / 'result.json'
        if result_file.exists():
            try:
                with open(result_file, encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f'读取结果文件失败: {e}')
        return None
