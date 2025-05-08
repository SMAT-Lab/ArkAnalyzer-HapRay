/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import fs from 'fs';
import path from 'path';

export interface Project {
    bundleName: string;
    versionName: string;
    versionId: string;
    scenes: string[];
}

export const PROJECT_ROOT = '.arkanalyzer';
const PROJECT_FILE = 'project.json';

export class AnalyzerProjectBase {
    protected workspace: string;
    protected projectRoot: string;
    protected project: Project;

    constructor(workspace: string) {
        this.workspace = workspace;
        this.projectRoot = path.join(workspace, PROJECT_ROOT);
        this.project = { bundleName: '', scenes: [], versionId: '', versionName: '' };
        this.loadProject();
    }

    public getWorkspace(): string {
        return this.workspace;
    }

    public getProject(): Project {
        return this.project;
    }

    public getProjectRoot(): string {
        return this.projectRoot;
    }

    public saveProject(): void {
        fs.writeFileSync(path.join(this.projectRoot, PROJECT_FILE), JSON.stringify(this.project));
    }

    private loadProject(): void {
        if (!fs.existsSync(this.projectRoot)) {
            fs.mkdirSync(this.projectRoot, { recursive: true });
        }

        const projectFile = path.join(this.projectRoot, PROJECT_FILE);
        if (fs.existsSync(projectFile)) {
            this.project = JSON.parse(fs.readFileSync(projectFile, { encoding: 'utf-8' }));
        }
    }
}
