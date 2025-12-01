"""
文件工具类 - 提供文件操作相关功能
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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

    @staticmethod
    def get_project_root() -> Path:
        """获取项目根目录"""
        # 从当前文件向上查找，直到找到包含特定标记文件的目录
        current = Path(__file__).resolve()
        while current != current.parent:
            if (current / 'hapray-gui').exists() or (current / 'perf_testing').exists():
                return current
            current = current.parent
        return Path.cwd()

    @staticmethod
    def get_testcases() -> list[str]:
        """
        获取所有可用的测试用例名称
        从打包环境目录结构查找：tools/perf-testing/_internal/hapray/testcases

        Returns:
            测试用例名称列表（不包含.py扩展名）
        """
        project_root = FileUtils.get_project_root()

        # 打包环境：tools/perf-testing/_internal/hapray/testcases
        testcases_dir = project_root / 'tools' / 'perf-testing' / '_internal' / 'hapray' / 'testcases'

        if not testcases_dir.exists():
            return []

        testcases = []
        # 遍历所有子目录
        for app_dir in testcases_dir.iterdir():
            if not app_dir.is_dir() or app_dir.name.startswith('_'):
                continue
            # 查找所有.py文件（排除__init__.py）
            for py_file in app_dir.glob('*.py'):
                if py_file.name != '__init__.py':
                    # 去掉.py扩展名
                    testcase_name = py_file.stem
                    testcases.append(testcase_name)

        return sorted(testcases)

    @staticmethod
    def get_installed_apps() -> list[str]:
        """
        获取设备上已安装的应用包名列表
        使用 hdc shell bm dump -a 命令查询

        Returns:
            应用包名列表
        """
        apps = []
        try:
            result = subprocess.run(
                ['hdc', 'shell', 'bm', 'dump', '-a'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0 and result.stdout:
                # 解析 bm dump -n 输出
                # 输出格式可能是 JSON 或每行一个包名
                for raw_line in result.stdout.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith('#') or line.startswith('['):
                        continue
                    # 简单格式：直接使用整行作为包名, 过滤掉 com.huawei.* 和 com.ohos.* 的包名
                    if '.' in line and not line.startswith('com.huawei.') and not line.startswith('com.ohos.'):
                        apps.append(line)

            return sorted(set(apps)) if apps else []  # 去重并排序

        except subprocess.TimeoutExpired:
            logger.warning('获取应用列表超时')
            return []
        except FileNotFoundError:
            logger.warning('hdc 命令未找到，请确保已安装 HDC 工具并配置到 PATH')
            return []
        except Exception as e:
            logger.warning(f'获取应用列表时发生错误: {e}')
            return []
