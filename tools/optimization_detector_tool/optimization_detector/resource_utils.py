"""
资源文件加载工具
处理打包后的资源文件加载问题
"""

import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    获取资源文件路径，兼容打包后的环境

    Args:
        relative_path: 相对于 optimization_detector 包的路径

    Returns:
        资源文件的绝对路径
    """
    try:
        # PyInstaller 打包后的环境
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # 打包后的临时目录
            base_path = Path(sys._MEIPASS)
            # 尝试多个可能的路径
            possible_paths = [
                base_path / 'optimization_detector' / relative_path,
                base_path / relative_path,
            ]
            for path in possible_paths:
                if path.exists():
                    return path

        # 开发环境：使用 importlib.resources
        try:
            from importlib.resources import files  # noqa: PLC0415

            resource_path = files('optimization_detector').joinpath(relative_path)
            # 尝试打开文件以检查是否存在
            try:
                with resource_path.open('rb'):
                    pass
                return Path(resource_path)
            except (OSError, FileNotFoundError):
                pass
        except (ImportError, AttributeError, TypeError):
            pass

        # 备选：相对路径（从当前文件的位置）
        current_file = Path(__file__).resolve()
        package_root = current_file.parent
        resource_path = package_root / relative_path
        if resource_path.exists():
            return resource_path

    except Exception:
        pass

    # 最后尝试：从环境变量或固定路径
    fallback_path = Path(relative_path)
    if fallback_path.is_absolute() and fallback_path.exists():
        return fallback_path

    # 如果都失败了，返回相对路径（让调用者处理错误）
    return Path(relative_path)


def get_models_dir() -> Path:
    """获取模型文件目录"""
    return get_resource_path('models')


def get_model_path(model_name: str) -> Path:
    """
    获取模型文件路径

    Args:
        model_name: 模型文件名或相对路径（相对于 models 目录）

    Returns:
        模型文件的绝对路径
    """
    models_dir = get_models_dir()
    model_path = models_dir / model_name

    # 如果找不到，尝试在 models 目录下查找
    if not model_path.exists() and models_dir.exists():
        for path in models_dir.rglob(model_name):
            if path.is_file():
                return path

    return model_path
