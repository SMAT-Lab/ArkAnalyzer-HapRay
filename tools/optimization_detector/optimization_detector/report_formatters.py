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

import json
import logging
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import pandas as pd

from optimization_detector.excel_utils import ExcelReportSaver


class OutputFormat(Enum):
    """支持的输出格式枚举"""

    EXCEL = 'excel'
    JSON = 'json'
    CSV = 'csv'
    XML = 'xml'


class BaseReportFormatter(ABC):
    """报告格式化器基类"""

    def __init__(self, output_path: str):
        """
        初始化报告格式化器

        :param output_path: 输出文件路径
        """
        self.output_path = os.path.abspath(output_path)
        self._ensure_output_dir()

    def _normalize_output_path(self) -> str:
        """规范化输出路径，确保扩展名正确"""
        base_path = os.path.splitext(self.output_path)[0]
        return base_path + self.get_file_extension()

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        output_dir = os.path.dirname(self.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

    @abstractmethod
    def get_file_extension(self) -> str:
        """获取文件扩展名"""
        pass

    @abstractmethod
    def save(self, data: list[tuple[str, pd.DataFrame]]) -> None:
        """
        保存报告数据

        :param data: 数据列表，每个元素为 (sheet_name, dataframe) 元组
        """
        pass


class ExcelReportFormatter(BaseReportFormatter):
    """Excel 格式报告格式化器"""

    def __init__(self, output_path: str):
        super().__init__(output_path)
        # 确保扩展名为 .xlsx
        self.output_path = self._normalize_output_path()

    def get_file_extension(self) -> str:
        return '.xlsx'

    def save(self, data: list[tuple[str, pd.DataFrame]]) -> None:
        """保存为 Excel 格式"""
        report_saver = ExcelReportSaver(self.output_path)
        for sheet_name, df in data:
            report_saver.add_sheet(df, sheet_name)
        report_saver.save()
        logging.info('Excel report saved to: %s', self.output_path)


class JsonReportFormatter(BaseReportFormatter):
    """JSON 格式报告格式化器"""

    def __init__(self, output_path: str):
        super().__init__(output_path)
        # 确保扩展名为 .json
        self.output_path = self._normalize_output_path()

    def get_file_extension(self) -> str:
        return '.json'

    def save(self, data: list[tuple[str, pd.DataFrame]]) -> None:
        """保存为 JSON 格式"""
        result = {}

        for sheet_name, df in data:
            # 将 DataFrame 转换为字典列表
            records = df.to_dict('records')
            result[sheet_name] = {
                'count': len(records),
                'data': records,
            }

        # 添加元数据
        result['metadata'] = {
            'format': 'json',
            'version': '1.0',
            'total_sheets': len(data),
        }

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logging.info('JSON report saved to: %s', self.output_path)


class CsvReportFormatter(BaseReportFormatter):
    """CSV 格式报告格式化器"""

    def __init__(self, output_path: str):
        super().__init__(output_path)
        # 确保扩展名为 .csv
        self.output_path = self._normalize_output_path()

    def get_file_extension(self) -> str:
        return '.csv'

    def save(self, data: list[tuple[str, pd.DataFrame]]) -> None:
        """保存为 CSV 格式"""
        if len(data) == 1:
            # 单个工作表，直接保存为单个 CSV 文件
            sheet_name, df = data[0]
            df.to_csv(self.output_path, index=False, encoding='utf-8-sig')
            logging.info('CSV report saved to: %s', self.output_path)
        else:
            # 多个工作表，保存为多个 CSV 文件
            base_path = os.path.splitext(self.output_path)[0]
            for sheet_name, df in data:
                # 清理工作表名称，使其适合作为文件名
                safe_sheet_name = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in sheet_name)
                output_path = f'{base_path}_{safe_sheet_name}.csv'
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
                logging.info('CSV report saved to: %s', output_path)


class XmlReportFormatter(BaseReportFormatter):
    """XML 格式报告格式化器"""

    def __init__(self, output_path: str):
        super().__init__(output_path)
        # 确保扩展名为 .xml
        self.output_path = self._normalize_output_path()

    def get_file_extension(self) -> str:
        return '.xml'

    def save(self, data: list[tuple[str, pd.DataFrame]]) -> None:
        """保存为 XML 格式"""
        root = ET.Element('report')
        root.set('format', 'xml')
        root.set('version', '1.0')

        metadata = ET.SubElement(root, 'metadata')
        ET.SubElement(metadata, 'total_sheets').text = str(len(data))

        for sheet_name, df in data:
            sheet_elem = ET.SubElement(root, 'sheet')
            sheet_elem.set('name', sheet_name)
            sheet_elem.set('count', str(len(df)))

            # 添加列信息
            columns_elem = ET.SubElement(sheet_elem, 'columns')
            for col in df.columns:
                col_elem = ET.SubElement(columns_elem, 'column')
                col_elem.text = str(col)

            # 添加数据行
            data_elem = ET.SubElement(sheet_elem, 'data')
            for _, row in df.iterrows():
                row_elem = ET.SubElement(data_elem, 'row')
                for col in df.columns:
                    cell_elem = ET.SubElement(row_elem, 'cell')
                    cell_elem.set('column', str(col))
                    value = row[col]
                    cell_elem.text = str(value) if pd.notna(value) else ''

        # 格式化 XML
        self._indent_xml(root)

        # 写入文件
        tree = ET.ElementTree(root)
        tree.write(self.output_path, encoding='utf-8', xml_declaration=True)
        logging.info('XML report saved to: %s', self.output_path)

    @staticmethod
    def _indent_xml(elem, level=0):
        """格式化 XML，添加缩进"""
        indent = '\n' + level * '  '
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + '  '
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                XmlReportFormatter._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        elif level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


class ReportFormatterFactory:
    """报告格式化器工厂类"""

    @staticmethod
    def create(formatter_type: OutputFormat, output_path: str) -> BaseReportFormatter:
        """
        创建报告格式化器

        :param formatter_type: 输出格式类型
        :param output_path: 输出文件路径
        :return: 格式化器实例
        """
        formatters = {
            OutputFormat.EXCEL: ExcelReportFormatter,
            OutputFormat.JSON: JsonReportFormatter,
            OutputFormat.CSV: CsvReportFormatter,
            OutputFormat.XML: XmlReportFormatter,
        }

        formatter_class = formatters.get(formatter_type)
        if formatter_class is None:
            raise ValueError(f'Unsupported output format: {formatter_type}')

        return formatter_class(output_path)

    @staticmethod
    def get_supported_formats() -> list[str]:
        """获取支持的格式列表"""
        return [fmt.value for fmt in OutputFormat]

    @staticmethod
    def is_format_supported(format_str: str) -> bool:
        """检查格式是否支持"""
        try:
            OutputFormat(format_str.lower())
            return True
        except ValueError:
            return False

    @staticmethod
    def detect_format_from_path(file_path: str) -> Optional[OutputFormat]:
        """
        从文件路径推断输出格式

        :param file_path: 文件路径
        :return: 输出格式，如果无法推断则返回 None
        """
        ext = os.path.splitext(file_path)[1].lower()
        ext_to_format = {
            '.xlsx': OutputFormat.EXCEL,
            '.json': OutputFormat.JSON,
            '.csv': OutputFormat.CSV,
            '.xml': OutputFormat.XML,
        }
        return ext_to_format.get(ext)

    @staticmethod
    def get_extension_for_format(formatter_type: OutputFormat) -> str:
        """
        获取指定格式的文件扩展名

        :param formatter_type: 输出格式类型
        :return: 文件扩展名（包含点号）
        """
        formatters = {
            OutputFormat.EXCEL: '.xlsx',
            OutputFormat.JSON: '.json',
            OutputFormat.CSV: '.csv',
            OutputFormat.XML: '.xml',
        }
        return formatters.get(formatter_type, '.xlsx')

    @staticmethod
    def normalize_output_formats(formats: Optional[list[str]], output_path: str) -> list[str]:
        """
        规范化输出格式列表

        :param formats: 用户指定的格式列表，如果为 None 则从文件路径推断
        :param output_path: 输出文件路径
        :return: 规范化后的格式列表
        """
        if formats is None:
            # 从文件扩展名推断格式
            detected_format = ReportFormatterFactory.detect_format_from_path(output_path)
            if detected_format:
                logging.info('Auto-detected output format: %s', detected_format.value)
                return [detected_format.value]
            # 默认使用 Excel 格式
            logging.info('Using default output format: %s', OutputFormat.EXCEL.value)
            return [OutputFormat.EXCEL.value]
        # 转换为小写并去重
        return list(dict.fromkeys(fmt.lower() for fmt in formats))

    @staticmethod
    def save_reports(data: list[tuple[str, pd.DataFrame]], formats: Optional[list[str]], output_path: str) -> list[str]:
        """
        保存报告到指定格式的文件

        :param data: 报告数据列表，每个元素为 (sheet_name, dataframe) 元组
        :param formats: 输出格式列表，如果为 None 则从文件路径推断
        :param output_path: 输出文件路径
        :return: 保存的文件路径列表
        """
        # 规范化输出格式
        output_formats = ReportFormatterFactory.normalize_output_formats(formats, output_path)

        # 处理基础输出路径（多格式时移除扩展名）
        base_output_path = output_path
        if len(output_formats) > 1:
            base_output_path = os.path.splitext(output_path)[0]

        saved_files = []
        for fmt in output_formats:
            # 为每个格式生成文件路径
            fmt_enum = OutputFormat(fmt)
            if len(output_formats) == 1:
                # 单个格式，使用原始输出路径（格式化器会自动处理扩展名）
                file_path = base_output_path
            else:
                # 多个格式，为每个格式生成带扩展名的文件
                ext = ReportFormatterFactory.get_extension_for_format(fmt_enum)
                file_path = base_output_path + ext

            # 创建格式化器并保存报告
            formatter = ReportFormatterFactory.create(fmt_enum, file_path)
            formatter.save(data)
            saved_files.append(formatter.output_path)
            logging.info('Report saved to: %s', formatter.output_path)

        if len(saved_files) > 1:
            logging.info('All reports saved: %s', ', '.join(saved_files))

        return saved_files
