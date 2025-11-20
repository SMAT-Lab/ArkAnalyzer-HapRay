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
import { spawnSync } from 'child_process';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import type { Ohpm } from '../../config/types';
import { getConfig } from '../../config';
import type { Component } from '../../types/component';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export class PkgIdentify {
    private ohpm: Map<string, Ohpm>;
    private npmm: Map<string, Ohpm>;
    private invalidNpmPkg: Set<string>;
    private temp: string;

    private constructor() {
        this.ohpm = new Map();
        this.npmm = new Map();
        this.invalidNpmPkg = new Set();
        this.temp = '.temp';
        fs.mkdirSync(this.temp, { recursive: true });

        getConfig().analysis.ohpm.forEach((pkg) => {
            pkg.filesSet = new Set(pkg.files);
            this.ohpm.set(pkg.name, pkg);
        });

        getConfig().analysis.npm.forEach((pkg) => {
            pkg.filesSet = new Set(pkg.files);
            this.npmm.set(pkg.name, pkg);
        });

        this.invalidNpmPkg = new Set(getConfig().analysis.invalidNpm);
    }

    public static getInstance(): PkgIdentify {
        return (this.instance ??= new PkgIdentify());
    }

    public save(output: string): void {
        fs.writeFileSync(path.join(output, 'npm.json'), JSON.stringify(Array.from(this.npmm.values())));
        fs.writeFileSync(path.join(output, 'invalid_npm.json'), JSON.stringify(Array.from(this.invalidNpmPkg)));
    }

    public async getNpmBasicInfo(pkgName: string): Promise<Ohpm | undefined> {
        logger.info(`npm view --json ${pkgName}`);
        let packInfo = spawnSync('npm', ['view', '--json', pkgName], { encoding: 'utf-8', shell: true });
        if (packInfo.status !== 0) {
            this.invalidNpmPkg.add(pkgName);
            return undefined;
        }

        try {
            let response = JSON.parse(packInfo.stdout) as {version: string, versions: Array<string>, main: string, module: string, types: string};
            let pkg: Ohpm = {
                name: pkgName,
                version: response.version,
                versions: response.versions,
                files: [],
            };
            pkg.main = response.main;
            pkg.module = response.module;
            pkg.types = response.types;
            return pkg;
        } catch {
            return undefined;
        }
    }

    public async getNpmInfo(pkgName: string, output: string): Promise<Ohpm | undefined> {
        let pkg = await this.getNpmBasicInfo(pkgName);
        if (!pkg) {
            return pkg;
        }

        logger.info(`npm pack --json ${pkgName}`);
        let packInfo = spawnSync('npm', ['pack', '--json', pkgName], {
            encoding: 'utf-8',
            shell: true,
            cwd: output,
        });

        if (packInfo.status !== 0) {
            return undefined;
        }

        try {
            let filesSet = new Set<string>();
            let packJson = JSON.parse(packInfo.stdout) as Array<{files: Array<{ path: string }>}>;
            packJson[0].files.forEach((entry: { path: string }) => {
                logger.info(`${entry.path}`);
                let matches = entry.path.match(/([\w\+\-\.\#\/]*)\.d\.(js|ts|ets|mjs|cjs)$/);
                if (matches) {
                    filesSet.add(matches[1]);
                    return;
                }
                matches = entry.path.match(/([\w\+\-\.\#\/]*)\.(js|ts|ets|mjs|cjs)$/);
                if (matches) {
                    filesSet.add(matches[1]);
                    return;
                }
            });

            pkg.filesSet = filesSet;
            pkg.files = Array.from(pkg.filesSet);
            return pkg;
        } catch {
            return;
        }
    }

    public async validXpmPackage(module: Component, onlineIdentifyThirdPart: boolean): Promise<boolean> {
        return this.validOhpmPackage(module) || (await this.validNpmjsPackage(module, onlineIdentifyThirdPart));
    }

    private async validNpmjsPackage(module: Component, onlineIdentifyThirdPart: boolean): Promise<boolean> {
        if (this.invalidNpmPkg.has(module.name)) {
            return false;
        }
        if (this.npmm.has(module.name)) {
            let pkg = this.npmm.get(module.name)!;
            return this.validPkg(pkg, module);
        }

        if (onlineIdentifyThirdPart) {
            let pkg = await this.getNpmInfo(module.name, this.temp);
            if (pkg) {
                this.npmm.set(module.name, pkg);
                return this.validPkg(pkg, module);
            }
        }
        return false;
    }

    private validOhpmPackage(module: Component): boolean {
        if (!this.ohpm.has(module.name)) {
            return false;
        }

        let pkg = this.ohpm.get(module.name)!;
        return this.validPkg(pkg, module);
    }

    private validPkg(pkg: Ohpm, module: Component): boolean {
        return this.checkerFiles(pkg, module);
    }

    private checkerFiles(pkg: Ohpm, module: Component): boolean {
        let matchCount = 0;
        const files = pkg.filesSet;
        if (!module.files) {
            return false;
        }
        for (const file of module.files) {
            if (files?.has(file)) {
                matchCount++;
            }
        }
        return matchCount / module.files.size >= 0.45;
    }

    private static instance: PkgIdentify | undefined;
}
