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
from typing import Any, Optional


class BaseModel:
    """Database model base class

    Subclasses must define:
    - table_name: Table name
    - fields: Field definition dictionary, e.g., {'column_name': 'TEXT', 'column2': 'INTEGER'}
    """

    table_name: str = ''
    fields: dict[str, str] = {}

    # Base fields that are automatically added and should not be in fields definition
    BASE_FIELDS = ('step_id', 'id')

    def __init__(self, **kwargs):
        """Initialize model instance

        Args:
            **kwargs: Field values
        """
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes step_id and id, as they are added automatically during save)

        Returns:
            Dictionary representation of the model
        """
        result = {}
        for key in self.fields:
            # step_id and id are base fields, should not be in fields definition or to_dict
            if key not in self.BASE_FIELDS and hasattr(self, key):
                result[key] = getattr(self, key)
        return result

    @classmethod
    def get_table_name(cls) -> str:
        """Get table name

        Returns:
            Table name string
        """
        return cls.table_name

    @classmethod
    def get_fields(cls) -> dict[str, str]:
        """Get field definitions

        Returns:
            Field definition dictionary
        """
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

        # SQLite database configuration - all analyzers share the same database file
        self._db_name = 'hapray_report'
        self._db_path: Optional[str] = None
        self._db_conn: Optional[sqlite3.Connection] = None
        # Analyzer type identifier (used to distinguish results from different analyzers)
        self._analyzer_type = self.__class__.__name__
        # Table name (subclasses can override get_table_name() method or set this attribute)
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
        """Get database file path

        Returns:
            Full path to the database file
        """
        if self._db_path is None:
            report_dir = os.path.join(self.scene_dir, 'report')
            os.makedirs(report_dir, exist_ok=True)
            self._db_path = os.path.join(report_dir, f'{self._db_name}.db')
        return self._db_path

    def get_db_connection(self) -> sqlite3.Connection:
        """Get or create database connection

        Returns:
            SQLite database connection object
        """
        if self._db_conn is None:
            db_path = self.get_db_path()
            # Set timeout to support multiple connections
            self._db_conn = sqlite3.connect(db_path, timeout=30.0)
            # Enable row factory to access results by column name
            self._db_conn.row_factory = sqlite3.Row
            # Enable foreign key constraints
            self._db_conn.execute('PRAGMA foreign_keys = ON')
            # Set WAL mode for better concurrent access
            self._db_conn.execute('PRAGMA journal_mode = WAL')
        return self._db_conn

    def close_db_connection(self):
        """Close database connection"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    def exec_sql(self, sql: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """Execute SQL statement (no return value)

        Args:
            sql: SQL statement
            params: Parameter tuple (optional)

        Returns:
            Cursor object after execution
        """
        conn = self.get_db_connection()
        if params:
            return conn.execute(sql, params)
        return conn.execute(sql)

    def query_sql(self, sql: str, params: Optional[tuple] = None) -> list[sqlite3.Row]:
        """Execute SQL query statement

        Args:
            sql: SQL query statement
            params: Parameter tuple (optional)

        Returns:
            Query result list
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.fetchall()

    def commit(self):
        """Commit database transaction"""
        if self._db_conn:
            self._db_conn.commit()

    def get_table_name(self) -> Optional[str]:
        """Get table name used by the analyzer

        Subclasses can override this method to customize table name,
        or set self._table_name in __init__.

        Returns:
            Table name, or None if table name feature is not used
        """
        return self._table_name

    @staticmethod
    def step_dir_to_step_id(step_dir: str) -> int:
        """Convert step_dir string to step_id integer

        Args:
            step_dir: Step directory string, e.g., 'step1', '1', 'step10', etc.

        Returns:
            Step ID integer, e.g., 'step1' -> 1, '1' -> 1, 'step10' -> 10

        Raises:
            ValueError: If unable to extract number from step_dir
        """
        # Remove 'step' prefix if present (case-insensitive)
        step_str = step_dir.replace('step', '').replace('Step', '')
        try:
            return int(step_str)
        except ValueError:
            raise ValueError(f'Cannot extract step_id from step_dir: {step_dir}') from None

    def create_table(self, table_name: str, schema: str, if_not_exists: bool = True):
        """Create database table

        Args:
            table_name: Table name
            schema: Table structure definition (column definition part of CREATE TABLE statement)
            if_not_exists: Whether to use IF NOT EXISTS clause
        """
        if_not_exists_clause = 'IF NOT EXISTS' if if_not_exists else ''
        sql = f'CREATE TABLE {if_not_exists_clause} {table_name} ({schema})'
        self.exec_sql(sql)
        self.commit()
        self.logger.debug('Created table: %s', table_name)

    def create_index(self, index_name: str, table_name: str, columns: str, unique: bool = False):
        """Create index

        Args:
            index_name: Index name
            table_name: Table name
            columns: Column names (can be multiple columns, comma-separated)
            unique: Whether to create unique index
        """
        unique_clause = 'UNIQUE' if unique else ''
        sql = f'CREATE {unique_clause} INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})'
        self.exec_sql(sql)
        self.commit()
        self.logger.debug('Created index: %s on %s(%s)', index_name, table_name, columns)

    def insert_data(self, table_name: str, data: dict, replace: bool = False) -> int:
        """Insert data into table

        Args:
            table_name: Table name
            data: Data dictionary, key is column name, value is column value
            replace: If True, use INSERT OR REPLACE, otherwise use INSERT

        Returns:
            Inserted row ID
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        action = 'INSERT OR REPLACE' if replace else 'INSERT'
        sql = f'{action} INTO {table_name} ({columns}) VALUES ({placeholders})'

        cursor = self.exec_sql(sql, tuple(data.values()))
        self.commit()
        return cursor.lastrowid

    def batch_insert_data(self, table_name: str, data_list: list[dict], replace: bool = False):
        """Batch insert data into table

        Args:
            table_name: Table name
            data_list: List of data dictionaries
            replace: If True, use INSERT OR REPLACE, otherwise use INSERT
        """
        if not data_list:
            return

        # Get union of all dictionary keys
        all_keys = set()
        for data in data_list:
            all_keys.update(data.keys())

        columns = list(all_keys)
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['?' for _ in columns])
        action = 'INSERT OR REPLACE' if replace else 'INSERT'
        sql = f'{action} INTO {table_name} ({columns_str}) VALUES ({placeholders})'

        conn = self.get_db_connection()
        # Prepare data, ensure all dictionaries have the same keys
        values_list = []
        for data in data_list:
            values = [data.get(key) for key in columns]
            values_list.append(tuple(values))

        conn.executemany(sql, values_list)
        self.commit()
        self.logger.debug('Batch inserted %d rows into %s', len(data_list), table_name)

    def save_data(self, step_id: int, data: dict, replace: bool = False) -> int:
        """Save data to analyzer table (automatically adds step_id)

        Args:
            step_id: Step ID (INTEGER)
            data: Data dictionary (does not include id and step_id, step_id will be added automatically)
            replace: If True, use INSERT OR REPLACE, otherwise use INSERT

        Returns:
            Inserted row ID

        Raises:
            ValueError: If table name is None
        """
        table_name = self.get_table_name()
        if not table_name:
            raise ValueError('Table name is not set. Override get_table_name() or set self._table_name in __init__')

        # Ensure data does not include id and step_id (if included, use the passed value)
        data_with_step = data.copy()
        data_with_step['step_id'] = step_id

        return self.insert_data(table_name, data_with_step, replace)

    def batch_save_data(self, step_id: int, data_list: list[dict], replace: bool = False):
        """Batch save data to analyzer table (automatically adds step_id)

        Args:
            step_id: Step ID (INTEGER)
            data_list: List of data dictionaries (each dict does not include id and step_id, step_id will be added automatically)
            replace: If True, use INSERT OR REPLACE, otherwise use INSERT

        Raises:
            ValueError: If table name is None
        """
        table_name = self.get_table_name()
        if not table_name:
            raise ValueError('Table name is not set. Override get_table_name() or set self._table_name in __init__')

        if not data_list:
            return

        # Add step_id to each data dictionary
        data_list_with_step = []
        for data in data_list:
            data_with_step = data.copy()
            data_with_step['step_id'] = step_id
            data_list_with_step.append(data_with_step)

        self.batch_insert_data(table_name, data_list_with_step, replace)

    def create_model_table(self, model_class: type[BaseModel], if_not_exists: bool = True):
        """Create table based on model class (automatically includes id and step_id fields)

        Args:
            model_class: Model class (inherits from BaseModel)
            if_not_exists: Whether to use IF NOT EXISTS clause
        """
        table_name = model_class.get_table_name()
        if not table_name:
            raise ValueError(f'Model {model_class.__name__} does not define table_name')

        fields = model_class.get_fields()
        if not fields:
            raise ValueError(f'Model {model_class.__name__} does not define fields')

        # Build field definition string
        field_definitions = []
        for field_name, field_type in fields.items():
            # step_id is a base field, should not be in fields definition
            if field_name != 'step_id':
                field_definitions.append(f'{field_name} {field_type}')

        additional_columns = ', '.join(field_definitions) if field_definitions else ''
        self.create_analyzer_table(additional_columns, if_not_exists, table_name)

    def create_analyzer_table(
        self, additional_columns: str = '', if_not_exists: bool = True, table_name: Optional[str] = None
    ):
        """Create analyzer table (automatically includes id and step_id fields)

        Args:
            additional_columns: Additional column definitions (optional), format like 'column1 TEXT, column2 INTEGER'
            if_not_exists: Whether to use IF NOT EXISTS clause
            table_name: Table name (optional, if not provided, use self.get_table_name())

        Raises:
            ValueError: If table name is None
        """
        if table_name is None:
            table_name = self.get_table_name()

        if not table_name:
            raise ValueError('Table name is not set. Override get_table_name() or set self._table_name in __init__')

        # Base column definitions: id and step_id (step_id is INTEGER)
        base_columns = """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id INTEGER NOT NULL
        """

        # If there are additional columns, add comma separator
        schema = f'{base_columns.strip()}, {additional_columns.strip()}' if additional_columns else base_columns.strip()

        self.create_table(table_name, schema, if_not_exists)

        # Automatically create step_id index
        self.create_index(f'idx_{table_name}_step_id', table_name, 'step_id')

    def save_model(self, step_id: int, model: BaseModel, replace: bool = False) -> int:
        """Save model instance to database (automatically adds step_id)

        Args:
            step_id: Step ID (INTEGER)
            model: Model instance
            replace: If True, use INSERT OR REPLACE, otherwise use INSERT

        Returns:
            Inserted row ID
        """
        table_name = model.get_table_name()
        data = model.to_dict()
        data['step_id'] = step_id
        return self.insert_data(table_name, data, replace)

    def batch_save_models(self, step_id: int, models: list[BaseModel], replace: bool = False):
        """Batch save model instances to database (automatically adds step_id)

        Args:
            step_id: Step ID (INTEGER)
            models: List of model instances
            replace: If True, use INSERT OR REPLACE, otherwise use INSERT
        """
        if not models:
            return

        # Get table name from first model (assume all models are of the same type)
        table_name = models[0].get_table_name()

        # Convert to list of dictionaries
        data_list = []
        for model in models:
            data = model.to_dict()
            data['step_id'] = step_id
            data_list.append(data)

        self.batch_insert_data(table_name, data_list, replace)


class AnalyzerHelper:
    """Helper class for analyzer operations"""

    _pid_cache: dict[str, list] = {}

    @staticmethod
    def get_app_pids(scene_dir: str, step_id: str) -> list:
        """Get application process ID list

        Args:
            scene_dir: Scene directory path
            step_id: Step ID, e.g., 'step1' or '1'

        Returns:
            List of process IDs
        """
        # Check cache
        cache_key = f'{scene_dir}-{step_id}'
        if cache_key in AnalyzerHelper._pid_cache:
            logging.debug('Using cached PID data: %s', cache_key)
            return AnalyzerHelper._pid_cache[cache_key]

        try:
            # Process step_id, remove 'step' prefix
            step_number = int(step_id.replace('step', ''))

            # Build pids.json file path
            pids_json_path = os.path.join(scene_dir, 'hiperf', f'step{step_number}', 'pids.json')

            if not os.path.exists(pids_json_path):
                logging.warning('No pids.json found at %s', pids_json_path)
                return []

            # Read JSON file
            with open(pids_json_path, encoding='utf-8') as f:
                pids_data = json.load(f)

            # Extract pids and process_names
            pids = pids_data.get('pids', [])
            process_names = pids_data.get('process_names', [])

            if not pids or not process_names:
                logging.warning('No valid pids or process_names found in %s', pids_json_path)
                return []

            # Ensure pids and process_names have the same length
            if len(pids) != len(process_names):
                logging.warning(
                    'Mismatch between pids (%s) and process_names (%s) in %s',
                    len(pids),
                    len(process_names),
                    pids_json_path,
                )
                # Take the shorter length
                min_length = min(len(pids), len(process_names))
                pids = pids[:min_length]
                process_names = process_names[:min_length]

            # Cache PID data
            AnalyzerHelper._pid_cache[cache_key] = pids

            logging.debug('Cached PID data: %s, PIDs: %s', step_id, len(pids))
            return pids

        except Exception as e:
            logging.error('Failed to get app PIDs: %s', str(e))
            return []
