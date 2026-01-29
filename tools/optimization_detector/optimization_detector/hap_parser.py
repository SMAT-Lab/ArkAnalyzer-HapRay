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

HAP 解析器（Python 版本）

参考 TypeScript 版本的 `hap_parser.ts` 实现：
- 从 HAP 包中解析：
  - bundleName
  - versionCode
  - versionName
  - appName（支持从 resources.index 中解析 $string:xxx）
"""

import json
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from optimization_detector.resource_index_parser import ResourceIndexParser

logger = logging.getLogger(__name__)


@dataclass
class HapMetadata:
    """HAP 元数据"""

    hap_path: Path
    bundle_name: str = ""
    version_code: int = 0
    version_name: str = ""
    app_name: str = ""
    # 基于 zip 内文件修改时间推算的应用编译时间，格式 YYYY-MM-DD
    build_time: str = ""


class HapParser:
    """HAP 解析器

    用法：
        meta = HapParser.load_from_hap("path/to/app.hap")
        print(meta.bundle_name, meta.version_code, meta.version_name, meta.app_name)
    """

    @classmethod
    def load_from_hap(cls, hap_path: str | Path) -> HapMetadata:
        """从 HAP 文件解析元数据"""
        hap_path = Path(hap_path)
        logger.info("Parse HAP file %s", hap_path)

        meta = HapMetadata(hap_path=hap_path)

        if not hap_path.is_file():
            logger.error("HAP file not found: %s", hap_path)
            return meta

        try:
            with zipfile.ZipFile(hap_path, "r") as zf:
                # 1. 解析 module.json
                module = cls._read_module_json(zf)
                if module is None:
                    logger.error("HapParser: %s not found or invalid 'module.json'", hap_path)
                    return meta

                app_info = module.get("app") or {}
                meta.bundle_name = str(app_info.get("bundleName", "") or "")
                # versionCode 可能是数字或字符串，统一转为 int，失败则为 0
                version_code = app_info.get("versionCode", 0)
                try:
                    meta.version_code = int(version_code)
                except (TypeError, ValueError):
                    meta.version_code = 0

                meta.version_name = str(app_info.get("versionName", "") or "")

                # 2. 解析应用名 appName
                label = str(app_info.get("label", "") or "")
                meta.app_name = cls._resolve_app_name(label, zf)

                # 3. 基于 zip 内文件时间生成应用编译时间（取包内最新修改时间），格式 YYYY-MM-DD
                meta.build_time = cls._get_build_time(zf, hap_path)

        except zipfile.BadZipFile:
            logger.error("Invalid HAP (zip) file: %s", hap_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to parse HAP %s: %s", hap_path, exc)

        return meta

    @staticmethod
    def _get_build_time(zf: zipfile.ZipFile, hap_path: Path) -> str:
        """基于 zip 内 .pages.info 文件的修改时间推算编译时间，返回 YYYY-MM-DD；若无该文件或时间无效则用 HAP 文件 mtime。"""
        # 优先读取 .pages.info 条目的修改时间（根目录或任意路径下）
        pages_info_name = '.pages.info'
        if pages_info_name in zf.namelist():
            info = zf.getinfo(pages_info_name)
            y, mo, d, h, mi, s = info.date_time
            t = datetime(y, mo, d, h, mi, s)
            return t.strftime("%Y-%m-%d")
        return datetime.fromtimestamp(hap_path.stat().st_mtime).strftime("%Y-%m-%d")

    @staticmethod
    def _read_module_json(zf: zipfile.ZipFile) -> Optional[dict]:
        """读取并解析 module.json"""
        if "module.json" not in zf.namelist():
            return None

        try:
            with zf.open("module.json") as f:
                # module.json 一般是 UTF-8 文本
                data = f.read()
                text = data.decode("utf-8", errors="replace")
                return json.loads(text)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to read module.json from HAP")
            return None

    @staticmethod
    def _resolve_app_name(label: str, zf: zipfile.ZipFile) -> str:
        """根据 label 与 resources.index 解析应用名"""
        # 1. 如果 label 为空，直接返回空
        if not label:
            return ""

        # 2. 如果不是 $string: 前缀，直接当作应用名
        if not label.startswith("$string:"):
            return label

        # 3. 是 $string:xxx，需要从 resources.index 中解析
        key = label[len("$string:") :]

        if "resources.index" not in zf.namelist():
            return ""

        try:
            with zf.open("resources.index") as f:
                buf = f.read()
            parser = ResourceIndexParser(buf)
            value = parser.get_string_value(key)
            return value or ""
        except Exception:  # noqa: BLE001
            logger.exception("Failed to resolve appName from resources.index")
            return ""


__all__ = ["HapMetadata", "HapParser"]

