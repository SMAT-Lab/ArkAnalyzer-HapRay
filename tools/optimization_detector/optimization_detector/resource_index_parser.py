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

resources.index 解析器（Python 版本）

参考 TypeScript 版本 `resource_index_parser.ts`：
- 解析 HarmonyOS HAP 包中的 resources.index
- 提取字符串资源（ResType.STRING），并支持按 key 获取对应 value
"""


from enum import IntEnum


class BufferHelper:
    """二进制读取辅助类（小端序）"""

    def __init__(self, data: bytes) -> None:
        self._buf = data
        self._offset = 0

    def read_int32(self) -> int:
        value = int.from_bytes(self._buf[self._offset : self._offset + 4], "little", signed=True)
        self._offset += 4
        return value

    def read_int16(self) -> int:
        value = int.from_bytes(self._buf[self._offset : self._offset + 2], "little", signed=True)
        self._offset += 2
        return value

    def read_string(self, length: int) -> str:
        buf = self._buf[self._offset : self._offset + length]
        # 去掉末尾的 0 终止符
        if buf and buf[-1] == 0:
            buf = buf[:-1]
        value = buf.decode("utf-8", errors="replace")
        self._offset += length
        return value

    def set_offset(self, offset: int) -> None:
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


class ResType(IntEnum):
    VALUES = 0
    ANIMATOR = 1
    DRAWABLE = 2
    LAYOUT = 3
    MENU = 4
    MIPMAP = 5
    RAW = 6
    XML = 7
    INTEGER = 8
    STRING = 9
    STRINGARRAY = 10
    INTARRAY = 11
    BOOLEAN = 12
    DIMEN = 13
    COLOR = 14
    ID = 15
    THEME = 16
    PLURALS = 17
    FLOAT = 18
    MEDIA = 19
    PROF = 20
    SVG = 21
    PATTERN = 22
    INVALID_RES_TYPE = -1


class ResourceIndexParser:
    """resources.index 解析器"""

    def __init__(self, data: bytes) -> None:
        self._helper = BufferHelper(data)
        # 对应 TS 中的: Array<Map<string, string>>
        self._string_value_map: list[dict[str, str]] = []
        self._load_resource_index()

    # 对齐 TS API
    def get_string_value(self, key: str) -> str:
        """根据 key 获取字符串资源值，不存在时返回空字符串"""
        for m in self._string_value_map:
            if key in m:
                return m[key]
        return ""

    # 内部解析逻辑（基本与 TS 版本一一对应）
    def _load_resource_index(self) -> None:
        # 跳过 header（128 字节字符串 + 4 字节 version?）
        self._helper.read_string(128)
        self._helper.read_int32()

        key_count = self._helper.read_int32()
        for _ in range(key_count):
            # 4 字节 tag / id
            self._helper.read_string(4)
            offset = self._helper.read_int32()
            self._parse_idss(offset)

            key_params_count = self._helper.read_int32()
            for _ in range(key_params_count):
                self._helper.read_int32()
                self._helper.read_int32()

    def _parse_idss(self, offset: int) -> None:
        back = self._helper.get_offset()
        self._helper.set_offset(offset)

        tag = self._helper.read_string(4)
        if tag != "IDSS":
            self._helper.set_offset(back)
            raise ValueError("Not found IDSS.")

        # 为当前 idss 创建一个 map
        string_map: dict[str, str] = {}
        self._string_value_map.append(string_map)

        count = self._helper.read_int32()
        for _ in range(count):
            _res_id = self._helper.read_int32()
            id_offset = self._helper.read_int32()
            self._parse_res_value(string_map, id_offset)

        self._helper.set_offset(back)

    def _parse_res_value(self, string_map: dict[str, str], offset: int) -> None:
        back = self._helper.get_offset()
        self._helper.set_offset(offset)

        # 跳过前 3 个 int32（与 TS 版一致）
        self._helper.read_int32()
        res_type = self._helper.read_int32()
        self._helper.read_int32()

        if res_type == ResType.STRING:
            value_len = self._helper.read_int16()
            value = self._helper.read_string(value_len)
            name_len = self._helper.read_int16()
            name = self._helper.read_string(name_len)
            string_map[name] = value

        self._helper.set_offset(back)


__all__ = ["ResourceIndexParser"]

