#!/usr/bin/env node

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

const https = require('https');
const fs = require('fs');
const path = require('path');

/**
 * 更新pub.dev包列表
 */
async function updatePubDevPackages() {
    return new Promise((resolve, reject) => {
        console.log('正在获取pub.dev包列表...');
        
        https.get('https://pub.dev/api/package-name-completion-data', (response) => {
            let data = '';
            
            response.on('data', (chunk) => {
                data += chunk;
            });
            
            response.on('end', () => {
                try {
                    const packages = JSON.parse(data);
                    const outputPath = path.join(__dirname, '../res/pub_dev_packages.json');
                    
                    fs.writeFileSync(outputPath, JSON.stringify(packages, null, 2), 'utf-8');
                    console.log(`✅ 成功更新pub.dev包列表，共 ${packages.length} 个包`);
                    resolve();
                } catch (error) {
                    console.error('❌ 解析pub.dev响应失败:', error.message);
                    reject(error);
                }
            });
        }).on('error', (error) => {
            console.error('❌ 获取pub.dev包列表失败:', error.message);
            reject(error);
        });
    });
}

/**
 * 更新Flutter版本映射
 */
async function updateFlutterVersions() {
    return new Promise((resolve, reject) => {
        console.log('正在获取Flutter版本映射...');

        https.get('https://flutter-ohos.obs.cn-south-1.myhuaweicloud.com/', (response) => {
            let data = '';

            response.on('data', (chunk) => {
                data += chunk;
            });

            response.on('end', () => {
                try {
                    const versions = {};

                    // 逐个Contents块解析，避免Key与LastModified错位
                    const contentsRegex = /<Contents>([\s\S]*?)<\/Contents>/g;
                    let contentMatch;
                    while ((contentMatch = contentsRegex.exec(data)) !== null) {
                        const block = contentMatch[1];
                        const keyMatch = block.match(/<Key>([^<]+)<\/Key>/);
                        const lastModifiedMatch = block.match(/<LastModified>([^<]+)<\/LastModified>/);
                        if (!keyMatch || !lastModifiedMatch) {
                            continue;
                        }
                        const key = keyMatch[1];
                        const lastModified = lastModifiedMatch[1];

                        // 捕获flutter/<40hex>/... 的任意组合，优先保留最新时间
                        const hexMatch = key.match(/flutter\/(?:[^\n<>/]*\/)?([0-9a-fA-F]{40})\//) || key.match(/flutter\/([0-9a-fA-F]{40})\//);
                        if (!hexMatch) {
                            continue;
                        }
                        const hex40 = hexMatch[1];

                        // 可选：仅选取与ohos相关的制品，如果你想严格限定，可开启以下判断
                        // if (!key.includes('ohos')) continue;

                        // 若已有记录，则保留最新的LastModified（ISO时间字符串可直接比较）
                        if (!versions[hex40] || (versions[hex40].lastModified < lastModified)) {
                            versions[hex40] = { lastModified };
                        }
                    }

                    const outputPath = path.join(__dirname, '../res/flutter_versions.json');
                    fs.writeFileSync(outputPath, JSON.stringify(versions, null, 2), 'utf-8');
                    console.log(`✅ 成功更新Flutter版本映射，共 ${Object.keys(versions).length} 个版本`);
                    resolve();
                } catch (error) {
                    console.error('❌ 解析Flutter版本XML失败:', error.message);
                    reject(error);
                }
            });
        }).on('error', (error) => {
            console.error('❌ 获取Flutter版本映射失败:', error.message);
            reject(error);
        });
    });
}

/**
 * 主函数
 */
async function main() {
    try {
        console.log('🚀 开始更新Flutter资源文件...\n');
        
        await updatePubDevPackages();
        console.log('');
        
        await updateFlutterVersions();
        console.log('');
        
        console.log('🎉 所有资源文件更新完成！');
    } catch (error) {
        console.error('💥 更新失败:', error.message);
        process.exit(1);
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    main();
}

module.exports = {
    updatePubDevPackages,
    updateFlutterVersions
};
