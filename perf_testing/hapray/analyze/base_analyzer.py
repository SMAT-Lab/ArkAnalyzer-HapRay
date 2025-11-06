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
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, Dict


class BaseModel:
    """数据库模型基类
    
    子类需要定义:
    - table_name: 表名
    - fields: 字段定义字典，格式如 {'column_name': 'TEXT', 'column2': 'INTEGER'}
    """
    
    table_name: str = ''
    fields: Dict[str, str] = {}
    
    def __init__(self, **kwargs):
        """初始化模型实例
        
        Args:
            **kwargs: 字段值
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（排除 step_id 和 id，因为会在保存时自动添加）"""
        result = {}
        for key in self.fields.keys():
            # step_id 和 id 是基础字段，不需要在 fields 中定义，也不应该包含在 to_dict 中
            if key not in ('step_id', 'id') and hasattr(self, key):
                result[key] = getattr(self, key)
        return result
    
    @classmethod
    def get_table_name(cls) -> str:
        """获取表名"""
        return cls.table_name
    
    @classmethod
    def get_fields(cls) -> Dict[str, str]:
        """获取字段定义"""
        return cls.fields


class BaseAnalyzer(ABC):
    """
    Abstract base class for all data analyzers.
    """

    def __init__(self, scene_dir: str, report_path: str):
        """Initialize base analyzer.

        Args:
            scene_dir: Root directory of the scene
            report_path: report path of result dict
        """
        self.results: dict[str, Any] = {}
        self.scene_dir = scene_dir
        self.report_path = report_path
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # SQLite 数据库配置 - 所有分析器共享同一个数据库文件
        self._db_name = 'hapray_report'
        self._db_path: Optional[str] = None
        self._db_conn: Optional[sqlite3.Connection] = None
        # 分析器类型标识（用于区分不同分析器的结果）
        self._analyzer_type = self.__class__.__name__
        # 表名（子类可以重写 get_table_name() 方法或设置此属性）
        self._table_name: Optional[str] = None

    def analyze(self, step_dir: str, trace_db_path: str, perf_db_path: str):
        """Public method to execute analysis for a single step.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database
        """
        try:
            start_time = time.time()
            pids = AnalyzerHelper.get_app_pids(self.scene_dir, step_dir)
            result = self._analyze_impl(step_dir, trace_db_path, perf_db_path, pids)
            if result:
                self.results[step_dir] = result
            self.logger.info(
                'Analysis completed for step %s in %.2f seconds [%s]',
                step_dir,
                time.time() - start_time,
                self.report_path,
            )
        except Exception as e:
            self.logger.error('Analysis failed for step %s: %s [%s]', step_dir, str(e), self.report_path)
            self.results[step_dir] = {'error': str(e)}

    @abstractmethod
    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Implementation of the analysis logic.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database

        Returns:
            Analysis results as a dictionary
        """

    def write_report(self, result: dict):
        """Write analysis results to JSON report."""
        if not self.results:
            self.logger.warning('No results to write. Skipping report generation for %s', self.report_path)
            return

        try:
            file_path = os.path.join(self.scene_dir, 'report', self.report_path.replace('/', '_') + '.json')
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False)
            self.logger.info('Report successfully written to %s', file_path)
        except Exception as e:
            self.logger.exception('Failed to write report: %s', str(e))

        dict_path = self.report_path.split('/')
        v = result
        for key in dict_path:
            if key == dict_path[-1]:
                break
            if key not in v:
                v[key] = {}
            v = v[key]
        v[dict_path[-1]] = self.results

    def get_db_path(self) -> str:
        """获取数据库文件路径
        
        Returns:
            数据库文件的完整路径
        """
        if self._db_path is None:
            report_dir = os.path.join(self.scene_dir, 'report')
            os.makedirs(report_dir, exist_ok=True)
            self._db_path = os.path.join(report_dir, f'{self._db_name}.db')
        return self._db_path
    
    def get_db_connection(self) -> sqlite3.Connection:
        """获取或创建数据库连接
        
        Returns:
            SQLite 数据库连接对象
        """
        if self._db_conn is None:
            db_path = self.get_db_path()
            self._db_conn = sqlite3.connect(db_path, timeout=30.0)  # 设置超时，支持多连接
            self._db_conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            # 设置外键约束
            self._db_conn.execute('PRAGMA foreign_keys = ON')
            # 设置 WAL 模式以支持更好的并发访问
            self._db_conn.execute('PRAGMA journal_mode = WAL')
        return self._db_conn
    
    def close_db_connection(self):
        """关闭数据库连接"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
    
    def exec_sql(self, sql: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """执行 SQL 语句（不返回结果）
        
        Args:
            sql: SQL 语句
            params: 参数元组（可选）
            
        Returns:
            执行后的 cursor 对象
        """
        conn = self.get_db_connection()
        if params:
            return conn.execute(sql, params)
        return conn.execute(sql)
    
    def query_sql(self, sql: str, params: Optional[tuple] = None) -> List[sqlite3.Row]:
        """执行 SQL 查询语句
        
        Args:
            sql: SQL 查询语句
            params: 参数元组（可选）
            
        Returns:
            查询结果列表
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.fetchall()
    
    def commit(self):
        """提交数据库事务"""
        if self._db_conn:
            self._db_conn.commit()
    
    def get_table_name(self) -> Optional[str]:
        """获取分析器使用的表名
        
        子类可以重写此方法来自定义表名，或者在 __init__ 中设置 self._table_name。
        
        Returns:
            表名，如果为 None 则不使用表名功能
        """
        return self._table_name
    
    @staticmethod
    def step_dir_to_step_id(step_dir: str) -> int:
        """将 step_dir 字符串转换为 step_id 整数
        
        Args:
            step_dir: 步骤目录字符串，如 'step1', '1', 'step10' 等
            
        Returns:
            步骤 ID 整数，如 'step1' -> 1, '1' -> 1, 'step10' -> 10
            
        Raises:
            ValueError: 如果无法从 step_dir 中提取数字
        """
        # 移除 'step' 前缀（如果有）
        step_str = step_dir.replace('step', '').replace('Step', '')
        try:
            return int(step_str)
        except ValueError:
            raise ValueError(f'Cannot extract step_id from step_dir: {step_dir}')
    
    def create_table(self, table_name: str, schema: str, if_not_exists: bool = True):
        """创建数据库表
        
        Args:
            table_name: 表名
            schema: 表结构定义（CREATE TABLE 语句的列定义部分）
            if_not_exists: 是否使用 IF NOT EXISTS 子句
        """
        if_not_exists_clause = 'IF NOT EXISTS' if if_not_exists else ''
        sql = f'CREATE TABLE {if_not_exists_clause} {table_name} ({schema})'
        self.exec_sql(sql)
        self.commit()
        self.logger.debug('Created table: %s', table_name)

    def create_index(self, index_name: str, table_name: str, columns: str, unique: bool = False):
        """创建索引
        
        Args:
            index_name: 索引名称
            table_name: 表名
            columns: 列名（可以是多个列，用逗号分隔）
            unique: 是否创建唯一索引
        """
        unique_clause = 'UNIQUE' if unique else ''
        sql = f'CREATE {unique_clause} INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})'
        self.exec_sql(sql)
        self.commit()
        self.logger.debug('Created index: %s on %s(%s)', index_name, table_name, columns)
    
    def insert_data(self, table_name: str, data: dict, replace: bool = False) -> int:
        """插入数据到表中
        
        Args:
            table_name: 表名
            data: 数据字典，key 为列名，value 为值
            replace: 如果为 True，使用 INSERT OR REPLACE，否则使用 INSERT
            
        Returns:
            插入的行 ID
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        action = 'INSERT OR REPLACE' if replace else 'INSERT'
        sql = f'{action} INTO {table_name} ({columns}) VALUES ({placeholders})'
        
        cursor = self.exec_sql(sql, tuple(data.values()))
        self.commit()
        return cursor.lastrowid
    
    def batch_insert_data(self, table_name: str, data_list: list[dict], replace: bool = False):
        """批量插入数据到表中
        
        Args:
            table_name: 表名
            data_list: 数据字典列表
            replace: 如果为 True，使用 INSERT OR REPLACE，否则使用 INSERT
        """
        if not data_list:
            return
        
        # 获取所有字典的键的并集
        all_keys = set()
        for data in data_list:
            all_keys.update(data.keys())
        
        columns = list(all_keys)
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['?' for _ in columns])
        action = 'INSERT OR REPLACE' if replace else 'INSERT'
        sql = f'{action} INTO {table_name} ({columns_str}) VALUES ({placeholders})'
        
        conn = self.get_db_connection()
        # 准备数据，确保所有字典都有相同的键
        values_list = []
        for data in data_list:
            values = [data.get(key) for key in columns]
            values_list.append(tuple(values))
        
        conn.executemany(sql, values_list)
        self.commit()
        self.logger.debug('Batch inserted %d rows into %s', len(data_list), table_name)
    
    def save_data(self, step_id: int, data: dict, replace: bool = False) -> int:
        """保存数据到分析器表（自动添加 step_id）
        
        Args:
            step_id: 步骤 ID（INTEGER）
            data: 数据字典（不包含 id 和 step_id，会自动添加 step_id）
            replace: 如果为 True，使用 INSERT OR REPLACE，否则使用 INSERT
            
        Returns:
            插入的行 ID
            
        Raises:
            ValueError: 如果表名为 None
        """
        table_name = self.get_table_name()
        if not table_name:
            raise ValueError('Table name is not set. Override get_table_name() or set self._table_name in __init__')
        
        # 确保 data 中不包含 id 和 step_id（如果包含则使用传入的值）
        data_with_step = data.copy()
        data_with_step['step_id'] = step_id
        
        return self.insert_data(table_name, data_with_step, replace)
    
    def batch_save_data(self, step_id: int, data_list: list[dict], replace: bool = False):
        """批量保存数据到分析器表（自动添加 step_id）
        
        Args:
            step_id: 步骤 ID（INTEGER）
            data_list: 数据字典列表（每个字典不包含 id 和 step_id，会自动添加 step_id）
            replace: 如果为 True，使用 INSERT OR REPLACE，否则使用 INSERT
            
        Raises:
            ValueError: 如果表名为 None
        """
        table_name = self.get_table_name()
        if not table_name:
            raise ValueError('Table name is not set. Override get_table_name() or set self._table_name in __init__')
        
        if not data_list:
            return
        
        # 为每个数据字典添加 step_id
        data_list_with_step = []
        for data in data_list:
            data_with_step = data.copy()
            data_with_step['step_id'] = step_id
            data_list_with_step.append(data_with_step)
        
        self.batch_insert_data(table_name, data_list_with_step, replace)
    
    def create_model_table(self, model_class: Type[BaseModel], if_not_exists: bool = True):
        """基于模型类创建表（自动包含 id 和 step_id 字段）
        
        Args:
            model_class: 模型类（继承自 BaseModel）
            if_not_exists: 是否使用 IF NOT EXISTS 子句
        """
        table_name = model_class.get_table_name()
        if not table_name:
            raise ValueError(f'Model {model_class.__name__} does not define table_name')
        
        fields = model_class.get_fields()
        if not fields:
            raise ValueError(f'Model {model_class.__name__} does not define fields')
        
        # 构建字段定义字符串
        field_definitions = []
        for field_name, field_type in fields.items():
            # step_id 是基础字段，不需要在 fields 中定义
            if field_name != 'step_id':
                field_definitions.append(f'{field_name} {field_type}')
        
        additional_columns = ', '.join(field_definitions) if field_definitions else ''
        self.create_analyzer_table(additional_columns, if_not_exists, table_name)
    
    def create_analyzer_table(self, additional_columns: str = '', if_not_exists: bool = True, table_name: Optional[str] = None):
        """创建分析器表（自动包含 id 和 step_id 字段）

        Args:
            additional_columns: 额外的列定义（可选），格式如 'column1 TEXT, column2 INTEGER'
            if_not_exists: 是否使用 IF NOT EXISTS 子句
            table_name: 表名（可选，如果不提供则使用 self.get_table_name()）

        Raises:
            ValueError: 如果表名为 None
        """
        if table_name is None:
            table_name = self.get_table_name()

        if not table_name:
            raise ValueError('Table name is not set. Override get_table_name() or set self._table_name in __init__')

        # 基础列定义：id 和 step_id（step_id 为 INTEGER）
        base_columns = '''
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id INTEGER NOT NULL
        '''

        # 如果有额外列，添加逗号分隔
        if additional_columns:
            schema = f'{base_columns.strip()}, {additional_columns.strip()}'
        else:
            schema = base_columns.strip()

        self.create_table(table_name, schema, if_not_exists)

        # 自动创建 step_id 索引
        self.create_index(f'idx_{table_name}_step_id', table_name, 'step_id')

    def save_model(self, step_id: int, model: BaseModel, replace: bool = False) -> int:
        """保存模型实例到数据库（自动添加 step_id）
        
        Args:
            step_id: 步骤 ID（INTEGER）
            model: 模型实例
            replace: 如果为 True，使用 INSERT OR REPLACE，否则使用 INSERT
            
        Returns:
            插入的行 ID
        """
        table_name = model.get_table_name()
        data = model.to_dict()
        data['step_id'] = step_id
        return self.insert_data(table_name, data, replace)
    
    def batch_save_models(self, step_id: int, models: List[BaseModel], replace: bool = False):
        """批量保存模型实例到数据库（自动添加 step_id）
        
        Args:
            step_id: 步骤 ID（INTEGER）
            models: 模型实例列表
            replace: 如果为 True，使用 INSERT OR REPLACE，否则使用 INSERT
        """
        if not models:
            return
        
        # 获取第一个模型的表名（假设所有模型都是同一类型）
        table_name = models[0].get_table_name()
        
        # 转换为字典列表
        data_list = []
        for model in models:
            data = model.to_dict()
            data['step_id'] = step_id
            data_list.append(data)
        
        self.batch_insert_data(table_name, data_list, replace)

class AnalyzerHelper:
    _pid_cache = {}

    @staticmethod
    def get_app_pids(scene_dir: str, step_id: str) -> list:
        """获取应用进程ID列表

        Args:
            scene_dir: 场景目录路径
            step_id: 步骤ID，如'step1'或'1'

        Returns:
            list: 进程ID列表
        """
        # 检查缓存
        cache_key = f'{scene_dir}-{step_id}'
        if cache_key in AnalyzerHelper._pid_cache:
            logging.debug('使用已缓存的PID数据: %s', cache_key)
            return AnalyzerHelper._pid_cache[cache_key]

        try:
            # 处理step_id，去掉'step'前缀
            step_number = int(step_id.replace('step', ''))

            # 构建pids.json文件路径
            pids_json_path = os.path.join(scene_dir, 'hiperf', f'step{step_number}', 'pids.json')

            if not os.path.exists(pids_json_path):
                logging.warning('No pids.json found at %s', pids_json_path)
                return []

            # 读取JSON文件
            with open(pids_json_path, encoding='utf-8') as f:
                pids_data = json.load(f)

            # 提取pids和process_names
            pids = pids_data.get('pids', [])
            process_names = pids_data.get('process_names', [])

            if not pids or not process_names:
                logging.warning('No valid pids or process_names found in %s', pids_json_path)
                return []

            # 确保pids和process_names长度一致
            if len(pids) != len(process_names):
                logging.warning(
                    'Mismatch between pids (%s) and process_names (%s) in %s',
                    len(pids),
                    len(process_names),
                    pids_json_path,
                )
                # 取较短的长度
                min_length = min(len(pids), len(process_names))
                pids = pids[:min_length]
                process_names = process_names[:min_length]

            # 缓存PID数据
            AnalyzerHelper._pid_cache[cache_key] = pids

            logging.debug('缓存PID数据: %s, PIDs: %s', step_id, len(pids))
            return pids

        except Exception as e:
            logging.error('Failed to get app PIDs: %s', str(e))
            return []
