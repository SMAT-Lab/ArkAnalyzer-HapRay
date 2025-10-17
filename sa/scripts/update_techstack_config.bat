@echo off
REM Copyright (c) 2025 Huawei Device Co., Ltd.
REM Licensed under the Apache License, Version 2.0 (the "License");
REM you may not use this file except in compliance with the License.
REM You may obtain a copy of the License at
REM
REM     http://www.apache.org/licenses/LICENSE-2.0
REM
REM Unless required by applicable law or agreed to in writing, software
REM distributed under the License is distributed on an "AS IS" BASIS,
REM WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
REM See the License for the specific language governing permissions and
REM limitations under the License.

echo 正在更新Flutter资源文件...
node update_flutter_resources.js
if %errorlevel% neq 0 (
    echo 更新失败！
    pause
    exit /b 1
)
echo 更新完成！
pause
