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
import sqlJs from 'sql.js';
import type { PerfSymbolDetailData, TestStep } from './perf_analyzer_base';
import { PerfEvent } from './perf_analyzer_base';
import { Readable } from 'stream';
import { ComponentCategory } from '../component';

export interface Instruction {
    name: string;
    count: number;
    category?: number;
    stepId?: number;
}

export class PerfDatabase {
    private SQL: Promise<sqlJs.SqlJsStatic>;
    private dbpath: string;

    constructor(dbpath: string) {
        this.SQL = sqlJs();
        this.dbpath = dbpath;
    }

    async initializeDatabase(db: sqlJs.Database): Promise<void> {
        db.exec(`
            CREATE TABLE IF NOT EXISTS perf_symbol_details (
                test_version TEXT,
                test_scene_name TEXT,
                step_id INTEGER,
                event_type TEXT,
                process_id INTEGER,
                process_name TEXT,
                process_events INTEGER,
                thread_id INTEGER,
                thread_name TEXT,
                thread_events INTEGER,
                file TEXT,
                file_events INTEGER,
                symbol TEXT,
                symbol_events INTEGER,
                symbol_total_events INTEGER,
                component_name TEXT,
                component_category INTEGER,
                origin_kind INTEGER
            );

            CREATE TABLE IF NOT EXISTS perf_test_step (
                id INTEGER,
                name TEXT,
                start INTEGER,
                end INTEGER
            );
        `);
    }

    async initialize(): Promise<sqlJs.Database> {
        const SQL = await this.SQL;
        let db: sqlJs.Database;

        if (fs.existsSync(this.dbpath)) {
            const buffer = fs.readFileSync(this.dbpath);
            db = new SQL.Database(buffer);
        } else {
            db = new SQL.Database();
            await this.initializeDatabase(db);
            const data = db.export();
            fs.writeFileSync(this.dbpath, Buffer.from(data));
        }

        return db;
    }

    insertTestSteps(db: sqlJs.Database, steps: Array<TestStep>): void {
        const stmt = db.prepare(`
            INSERT INTO perf_test_step VALUES($id, $name, $start, $end);
        `);

        try {
            db.exec('BEGIN TRANSACTION');
            for (const step of steps) {
                stmt.bind({
                    $id: step.id,
                    $name: step.name,
                    $start: step.start,
                    $end: step.end,
                });
                stmt.step();
                stmt.reset();
            }
            db.exec('COMMIT');
        } catch {
            db.exec('ROLLBACK');
        } finally {
            stmt.free();
        }
    }

    async insertRecords(
        db: sqlJs.Database,
        osVersion: string,
        scene: string,
        records: Array<PerfSymbolDetailData>
    ): Promise<void> {
        const stmt = db.prepare(`
            INSERT INTO perf_symbol_details VALUES (
                $version, $scene, $stepIdx, $eventType, $pid, $processName, $processEvents,
                $tid, $threadName, $threadEvents, $file, $fileEvents, $symbol,
                $symbolEvents, $symbolTotalEvents,
                $componentName, $componentCategory, $originKind
            );    
        `);

        try {
            db.exec('BEGIN TRANSACTION');
            for (const record of records) {
                stmt.bind({
                    $version: osVersion,
                    $scene: scene,
                    $stepIdx: record.stepIdx,
                    $eventType: PerfEvent[record.eventType],
                    $pid: record.pid,
                    $processName: record.processName,
                    $processEvents: record.processEvents,
                    $tid: record.tid,
                    $threadName: record.threadName,
                    $threadEvents: record.threadEvents,
                    $file: record.file,
                    $fileEvents: record.fileEvents,
                    $symbol: record.symbol,
                    $symbolEvents: record.symbolEvents,
                    $symbolTotalEvents: record.symbolTotalEvents,
                    $componentName: record.componentName ?? null,
                    $componentCategory: record.componentCategory,
                    $originKind: record.originKind ?? null,
                });
                stmt.step();
                stmt.reset();
            }
            db.exec('COMMIT');
        } catch {
            db.exec('ROLLBACK');
        } finally {
            stmt.free();
        }
    }

    async close(db: sqlJs.Database): Promise<void> {
        await this.writeDatabaseStream(db);
        db.close();
    }

    async writeDatabaseStream(db: sqlJs.Database): Promise<void> {
        return new Promise((resolve, reject) => {
            const writeStream = fs.createWriteStream(this.dbpath);
            const buffer = db.export();

            const readable = new Readable({
                read() {
                    this.push(buffer);
                    this.push(null);
                },
            });

            readable
                .pipe(writeStream)
                .on('finish', () => {
                    resolve();
                })
                .on('error', reject);
        });
    }

    async queryOverview(): Promise<Array<Instruction>> {
        const db = await this.initialize();
        const results = db.exec(`SELECT component_category, SUM(symbol_events) as count, step_id
            FROM perf_symbol_details GROUP BY component_category, step_id`);
        if (results.length === 0) {
            return [];
        }

        let overView: Array<Instruction> = [];
        const rows = results[0].values as Array<Array<number>>;
        rows.map((row: Array<number>) => {
            overView.push({
                category: row[0],
                name: ComponentCategory[row[0]],
                count: row[1],
                stepId: row[2],
            });
        });
        db.close();
        return overView;
    }

    async queryStepsInstruction(): Promise<Array<Instruction>> {
        const db = await this.initialize();
        const results =
            db.exec(`SELECT perf_test_step.id, perf_test_step.name, SUM(perf_symbol_details.symbol_events) as count
            FROM perf_symbol_details 
                INNER JOIN perf_test_step
                ON perf_symbol_details.step_id = perf_test_step.id
            GROUP BY perf_test_step.id, perf_test_step.name order by count DESC`);
        if (results.length === 0) {
            return [];
        }

        let overView: Array<Instruction> = [];
        const rows = results[0].values as Array<[number, string, number]>;
        rows.map((row: [number, string, number]) => {
            overView.push({
                stepId: row[0],
                name: row[1],
                count: row[2],
            });
        });
        db.close();
        return overView;
    }

    async queryFilesByStep(stepId: number): Promise<Array<Instruction>> {
        const SQL = `SELECT file, SUM(file_events) as count, component_category
            from perf_symbol_details
            where step_id = :stepId
            GROUP BY file, component_category
            ORDER BY count DESC`;
        const SQLAll = `SELECT file, SUM(file_events) as count, component_category
            from perf_symbol_details
            GROUP BY file, component_category
            ORDER BY count DESC`;
        const db = await this.initialize();
        const results = stepId === -1 ? db.exec(SQLAll) : db.exec(SQL, [stepId]);
        if (results.length === 0) {
            return [];
        }

        let filelist: Array<Instruction> = [];
        const rows = results[0].values as Array<[string, number, number]>;
        rows.map((row: [string, number, number]) => {
            filelist.push({
                name: row[0],
                count: row[1],
                category: row[2],
            });
        });
        db.close();
        return filelist;
    }

    async queryFileSymbolsByStep(stepId: number, file: string): Promise<Array<Instruction>> {
        const SQL = `SELECT symbol, SUM(symbol_events) as count
            from perf_symbol_details
            where step_id = :stepId and file = :file
            GROUP BY symbol
            ORDER BY count DESC`;
        const SQLAll = `SELECT symbol, SUM(symbol_events) as count
            from perf_symbol_details
            where file = :file
            GROUP BY symbol
            ORDER BY count DESC`;
        const db = await this.initialize();
        const results = stepId === -1 ? db.exec(SQLAll, [file]) : db.exec(SQL, [stepId, file]);
        if (results.length === 0) {
            return [];
        }

        let symbols: Array<Instruction> = [];
        const rows = results[0].values as Array<[string, number]>;
        rows.map((row: [string, number]) => {
            symbols.push({
                name: row[0],
                count: row[1],
            });
        });
        db.close();
        return symbols;
    }

    async queryFilelist(category: number): Promise<Array<Instruction>> {
        const SQL = `SELECT file, SUM(file_events)
            from perf_symbol_details
            where component_category = :category
            GROUP BY file`;

        const db = await this.initialize();
        const results = db.exec(SQL, [category]);
        if (results.length === 0) {
            return [];
        }

        let filelist: Array<Instruction> = [];
        const rows = results[0].values as Array<[number, number]>;
        rows.map((row: [number, number]) => {
            filelist.push({
                name: ComponentCategory[row[0]],
                count: row[1],
            });
        });
        db.close();
        return filelist;
    }

    async queryTestSteps(): Promise<Array<TestStep>> {
        const SQL = 'SELECT id, name, start, end from perf_test_step';

        const db = await this.initialize();
        const results = db.exec(SQL);
        if (results.length === 0) {
            return [];
        }

        let steps: Array<TestStep> = [];
        const rows = results[0].values as Array<[number, string, number, number]>;
        rows.map((row: [number, string, number, number]) => {
            steps.push({
                id: row[0],
                groupId: 1,
                name: row[1],
                start: row[2],
                end: row[3],
            });
        });
        db.close();
        return steps;
    }
}

export async function getProcessesNameFromDb(dbpath: string): Promise<Array<string>> {
    let SQL = await sqlJs();
    const db = new SQL.Database(fs.readFileSync(dbpath));
    let processes: Array<string> = [];

    try {
        // 读取所有线程信息
        const results = db.exec(
            "SELECT thread_name from perf_thread WHERE thread_id = process_id and thread_name LIKE '%.%'"
        );
        if (results.length === 0) {
            return processes;
        }
        
        const rows = results[0].values as Array<[string]>;
        processes = rows
            .filter((v: [string]) => {
                return !v[0].endsWith('.elf') && v[0].indexOf(':') < 0;
            })
            .map((v: [string]) => v[0]);
    } finally {
        db.close();
    }

    return processes;
}
