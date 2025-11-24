"""
文件工具类 - 提供文件操作相关功能
"""

from pathlib import Path
from typing import Optional


class FileUtils:
    """文件工具类"""

    @staticmethod
    def select_file(title: str = '选择文件', filter: str = 'All Files (*.*)') -> Optional[str]:
        """选择文件（需要在GUI中实现）"""
        # 这个方法应该在GUI模块中实现
        pass

    @staticmethod
    def select_directory(title: str = '选择目录') -> Optional[str]:
        """选择目录（需要在GUI中实现）"""
        # 这个方法应该在GUI模块中实现
        pass

    @staticmethod
    def ensure_directory(path: str) -> Path:
        """确保目录存在"""
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @staticmethod
    def is_file(path: str) -> bool:
        """检查是否为文件"""
        return Path(path).is_file()

    @staticmethod
    def is_directory(path: str) -> bool:
        """检查是否为目录"""
        return Path(path).is_dir()

    @staticmethod
    def exists(path: str) -> bool:
        """检查路径是否存在"""
        return Path(path).exists()

    @staticmethod
    def get_file_size(path: str) -> int:
        """获取文件大小（字节）"""
        return Path(path).stat().st_size

    @staticmethod
    def list_files(directory: str, pattern: str = '*') -> list[str]:
        """列出目录中的文件"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return []
        return [str(f) for f in dir_path.glob(pattern) if f.is_file()]

    @staticmethod
    def list_directories(directory: str) -> list[str]:
        """列出目录中的子目录"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return []
        return [str(d) for d in dir_path.iterdir() if d.is_dir()]
