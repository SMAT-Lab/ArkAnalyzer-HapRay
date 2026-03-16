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

"""Custom exceptions for optimization_detector, enabling Agent to handle errors by type."""


class OptDetectorError(Exception):
    """Base exception for optimization detector."""

    def __init__(self, message: str, path: str | None = None):
        super().__init__(message)
        self.message = message
        self.path = path


class OptDetectorInputError(OptDetectorError):
    """Input path does not exist or is invalid."""

    pass


class OptDetectorNoFilesError(OptDetectorError):
    """No valid binary files found in input path(s)."""

    pass


class OptDetectorTimeoutError(OptDetectorError):
    """Analysis timed out for a file."""

    pass


class OptDetectorAnalysisError(OptDetectorError):
    """Analysis failed for a file (e.g., ELF read error, feature extraction failed)."""

    pass
