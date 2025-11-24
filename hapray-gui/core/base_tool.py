"""
工具基类 - 定义所有工具的通用接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    message: str
    output_path: Optional[str] = None
    error: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class BaseTool(ABC):
    """工具基类，所有工具都需要继承此类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        """
        获取工具参数定义
        返回格式: {
            'param_name': {
                'type': 'str|int|bool|file|dir',
                'label': '参数显示名称',
                'required': True/False,
                'default': 默认值,
                'help': '参数说明'
            }
        }
        """
        pass

    @abstractmethod
    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证参数
        返回: (是否有效, 错误信息)
        """
        pass

    @abstractmethod
    def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        执行工具
        返回: ToolResult
        """
        pass

    def get_name(self) -> str:
        """获取工具名称"""
        return self.name

    def get_description(self) -> str:
        """获取工具描述"""
        return self.description
