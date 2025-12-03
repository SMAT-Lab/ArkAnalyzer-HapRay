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

import hashlib
import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from enum import Enum
from typing import Optional

import arpy
from elftools.elf.elffile import ELFFile

# File analysis status mapping
FILE_STATUS_MAPPING = {
    'analyzed': 'Successfully Analyzed',
    'skipped': 'Skipped (System Library)',
    'failed': 'Analysis Failed',
}


class FileType(Enum):
    SO = 1
    AR = 2
    NOT_SUPPORT = 0xFF


class FileInfo:
    """Represents information about a binary file"""

    TEXT_SECTION = '.text'
    CACHE_DIR = 'files_results_cache'

    def __init__(self, absolute_path: str, logical_path: Optional[str] = None):
        self.absolute_path = absolute_path
        self.logical_path = logical_path or absolute_path
        self.file_size = self._get_file_size()
        self.file_hash = self._calculate_file_hash()
        self.file_id = self._generate_file_id()
        if absolute_path.endswith('.a'):
            self.file_type = FileType.AR
        elif absolute_path.endswith('.so'):
            self.file_type = FileType.SO
        else:
            self.file_type = FileType.NOT_SUPPORT

    def __repr__(self) -> str:
        return f'FileInfo({self.logical_path}, size={self.file_size}, hash={self.file_hash[:8]}...)'

    def to_dict(self) -> dict:
        return {
            'absolute_path': self.absolute_path,
            'logical_path': self.logical_path,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'file_id': self.file_id,
        }

    def extract_dot_text(self) -> list[int]:
        """Extract .text segment data"""
        if self.file_type == FileType.SO:
            return self._extract_so_dot_text(self.absolute_path)
        if self.file_type == FileType.AR:
            return self._extract_archive_dot_text()
        return []

    def _extract_so_dot_text(self, file_path) -> list[int]:
        try:
            with open(file_path, 'rb') as f:
                elf = ELFFile(f)
                section = elf.get_section_by_name(self.TEXT_SECTION)
                if section:
                    return list(section.data())
        except Exception as e:
            logging.error('Failed to extract .text section from %s: %s', file_path, e)
        return []

    def _extract_archive_dot_text(self) -> list[int]:
        text_data = []
        try:
            ar = arpy.Archive(self.absolute_path)
            for name in ar.namelist():
                elf = ELFFile(ar.open(name))
                section = elf.get_section_by_name(self.TEXT_SECTION)
                if section:
                    text_data.extend(list(section.data()))
        except Exception as e:
            logging.error('Failed to extract archive file %s: %s', self.absolute_path, e)
        return text_data

    def _get_file_size(self) -> int:
        return os.path.getsize(self.absolute_path)

    def _calculate_file_hash(self) -> str:
        with open(self.absolute_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _generate_file_id(self) -> str:
        base_name = os.path.basename(self.absolute_path).replace(' ', '_')
        unique_id = f'{base_name}_{self.file_hash}'
        return self.file_hash if len(unique_id) > 200 else unique_id


class FileCollector:
    def __init__(self):
        self.temp_dirs = []

    def cleanup(self):
        for temp_dir in self.temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def collect_binary_files(self, input_path: str) -> list[FileInfo]:
        """Collect binary files for analysis"""
        file_infos = []
        if os.path.isfile(input_path):
            if input_path.endswith(('.so', '.a')):
                file_infos.append(FileInfo(input_path))
            elif input_path.endswith(('.hap', '.hsp', '.apk', '.har')):
                file_infos.extend(self._extract_hap_file(input_path))
        elif os.path.isdir(input_path):
            for root, _, _files in os.walk(input_path):
                for file in _files:
                    file_path = os.path.join(root, file)
                    if file.endswith(('.so', '.a')):
                        logical_path = os.path.relpath(file_path, input_path)
                        file_infos.append(FileInfo(file_path, logical_path))
                    elif file.endswith(('.hap', '.hsp', '.apk', '.har')):
                        file_infos.extend(self._extract_hap_file(file_path))
        return file_infos

    def _is_tar_gz(self, file_path: str) -> bool:
        """Check if file is a tar.gz/gzip compressed tar file"""
        try:
            with open(file_path, 'rb') as f:
                magic = f.read(2)
                return magic == b'\x1f\x8b'  # gzip magic number
        except Exception:
            return False

    def _extract_hap_file(self, hap_path: str) -> list[FileInfo]:
        """Extract SO files from HAP/HSP/APK/HAR archives and return FileInfo objects"""
        extracted_files = []
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)

        # Check if file is tar.gz format (gzip compressed)
        if self._is_tar_gz(hap_path):
            try:
                with tarfile.open(hap_path, 'r:gz') as tar_ref:
                    for member in tar_ref.getmembers():
                        if member.isfile():
                            file_path = member.name
                            # Handle both 'package/' prefix and direct paths
                            if file_path.startswith('package/'):
                                file_path = file_path[8:]  # Remove 'package/' prefix
                            if (
                                file_path.startswith('libs/arm64') or file_path.startswith('lib/arm64')
                            ) and file_path.endswith('.so'):
                                output_path = os.path.join(temp_dir, file_path)
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                with tar_ref.extractfile(member) as src, open(output_path, 'wb') as dest:
                                    dest.write(src.read())
                                file_info = FileInfo(
                                    absolute_path=output_path, logical_path=f'{hap_path}/{member.name}'
                                )
                                extracted_files.append(file_info)
            except Exception as e:
                logging.error('Failed to extract tar.gz file %s: %s', hap_path, e)
        else:
            # Try zip format
            try:
                with zipfile.ZipFile(hap_path, 'r') as zip_ref:
                    for file in zip_ref.namelist():
                        if (file.startswith('libs/arm64') or file.startswith('lib/arm64')) and file.endswith('.so'):
                            output_path = os.path.join(temp_dir, file[5:])
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            with zip_ref.open(file) as src, open(output_path, 'wb') as dest:
                                dest.write(src.read())
                            file_info = FileInfo(absolute_path=output_path, logical_path=f'{hap_path}/{file}')
                            extracted_files.append(file_info)
            except Exception as e:
                logging.error('Failed to extract HAP file %s: %s', hap_path, e)
        return extracted_files
