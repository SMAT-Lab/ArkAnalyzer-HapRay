import fs from 'fs';
import readXlsxFile from 'read-excel-file/node';
import writeXlsxFile from 'write-excel-file/node';
import { ComponentConfig, SubComponentConfig } from '../src/config/types';

export async function json2xlsx(output: string): Promise<void> {
    let kindData: { type?: any; value: any }[][] = [];
    kindData.push([
        { value: '一级分类' },
        { value: '类型值' },
        { value: '二级分类' },
        { value: '文件' },
        { value: '线程' },
    ]);

    let config = JSON.parse(fs.readFileSync('res/perf/kind.json', 'utf-8')) as ComponentConfig[];

    for (let domain of config) {
        for (let component of domain.components) {
            if (!component.name) {
                component.name = domain.name;
            }
            let componentData: { type?: any; value: any }[][] = [];
            for (const file of component.files) {
                componentData.push([
                    { value: domain.name },
                    { value: domain.kind, type: Number },
                    { value: component.name },
                    { value: file },
                    { value: '' },
                ]);
            }
            if (component.threads) {
                for (let i = 0; i < component.threads.length; i++) {
                    if (i < component.files.length) {
                        componentData[i][4].value = component.threads[i];
                    } else {
                        componentData.push([
                            { value: domain.name },
                            { value: domain.kind, type: Number },
                            { value: component.name },
                            { value: '' },
                            { value: component.threads[i] },
                        ]);
                    }
                }
            }
            kindData.push(...componentData);
        }
    }

    await writeXlsxFile([kindData], {
        sheets: ['kind'],
        filePath: output,
    });
}

export async function xlsx2json(file: string): Promise<void> {
    let kindMap = new Map<string, ComponentConfig>();

    let rows = await readXlsxFile(file);
    for (const row of rows) {
        if (row === rows[0]) {
            continue;
        }

        if (!kindMap.has(row[0] as string)) {
            kindMap.set(row[0] as string, {
                name: row[0] as string,
                kind: row[1] as number,
                components: [],
            });
        }

        let subSystem = kindMap.get(row[0] as string)!;
        let existComponent = false;
        for (const component of subSystem.components) {
            if (component.name === (row[2] as string)) {
                if ((row[3] as string)?.length > 0) {
                    component.files.push(row[3] as string);
                }

                if ((row[4] as string)?.length > 0) {
                    if (!component.threads) {
                        component.threads = [];
                    }
                    component.threads?.push(row[4] as string);
                }
                existComponent = true;
                break;
            }
        }

        if (existComponent) {
            continue;
        }

        let component: SubComponentConfig = { name: row[2] as string, files: [] };
        if ((row[3] as string)?.length > 0) {
            component.files.push(row[3] as string);
        }
        if ((row[4] as string)?.length > 0) {
            if (!component.threads) {
                component.threads = [];
            }
            component.threads?.push(row[4] as string);
        }
        subSystem.components.push(component);
    }

    for (const [_, domain] of kindMap) {
        for (let component of domain.components) {
            component.files.sort((a: string, b: string) => {
                return a.localeCompare(b);
            });
        }
        domain.components.sort((a, b) => {
            if (a.name! === domain.name) {
                return 1;
            }
            return a.name!.localeCompare(b.name!);
        });
    }
    fs.writeFileSync('kind.json', JSON.stringify(Array.from(kindMap.values()), null, 4));
}

(async function () {
    await xlsx2json('doc/线程文件分类规则.xlsx');
    // await json2xlsx('doc/线程文件分类规则.xlsx');
})();
