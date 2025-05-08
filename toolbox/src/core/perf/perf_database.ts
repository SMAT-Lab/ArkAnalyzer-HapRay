import fs from 'fs';
import sqlJs from 'sql.js';
import { TestStep } from './perf_analyzer';
import { PerfEvent, PerfSymbolDetailData } from './perf_analyzer_base';
import { Readable } from 'stream';
import { ComponentCategory } from '../component';

export interface Instruction {
    name: string;
    count: number;
    category?: number;
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

    async insertTestSteps(db: sqlJs.Database, steps: TestStep[]): Promise<void> {
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
        } catch (err) {
            db.exec('ROLLBACK');
        } finally {
            stmt.free();
        }
    }

    async insertRecords(
        db: sqlJs.Database,
        osVersion: string,
        scene: string,
        records: PerfSymbolDetailData[]
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
                    $componentName: record.componentName || null,
                    $componentCategory: record.componentCategory,
                    $originKind: record.originKind || null,
                });
                stmt.step();
                stmt.reset();
            }
            db.exec('COMMIT');
        } catch (err) {
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

    async queryOverview(): Promise<Instruction[]> {
        const db = await this.initialize();
        const results = db.exec(`SELECT component_category, SUM(perf_symbol_details.symbol_events) as instructions
            FROM perf_symbol_details GROUP BY perf_symbol_details.component_category`);
        if (results.length === 0) {
            return [];
        }

        let overView: Instruction[] = [];
        results[0].values.map((row: any) => {
            overView.push({
                category: row[0] as number,
                name: ComponentCategory[row[0] as number],
                count: row[1] as number,
            });
        });
        db.close();
        return overView;
    }

    async queryFilesByStep(stepId: number): Promise<Instruction[]> {
        const SQL = `SELECT file, SUM(file_events) as instrucions
            from perf_symbol_details
            where step_id = :stepId
            GROUP BY file
            ORDER BY instructions DESC`;
        const SQLAll = `SELECT file, SUM(file_events) as instrucions
            from perf_symbol_details
            GROUP BY file
            ORDER BY instructions DESC`;
        const db = await this.initialize();
        const results = stepId === -1 ? db.exec(SQLAll) : db.exec(SQL, [stepId]);
        if (results.length === 0) {
            return [];
        }

        let filelist: Instruction[] = [];
        results[0].values.map((row: any) => {
            filelist.push({
                name: row[0] as string,
                count: row[1] as number,
            });
        });
        db.close();
        return filelist;
    }

    async queryFileSymbolsByStep(stepId: number, file: string): Promise<Instruction[]> {
        const SQL = `SELECT symbol, SUM(symbol_events) as instructions
            from perf_symbol_details
            where step_id = :stepId and file = :file
            GROUP BY symbol
            ORDER BY instructions DESC`;
        const SQLAll = `SELECT symbol, SUM(symbol_events) as instructions
            from perf_symbol_details
            where file = :file
            GROUP BY symbol
            ORDER BY instructions DESC`;
        const db = await this.initialize();
        const results = stepId === -1 ? db.exec(SQLAll, [file]) : db.exec(SQL, [stepId, file]);
        if (results.length === 0) {
            return [];
        }

        let symbols: Instruction[] = [];
        results[0].values.map((row: any) => {
            symbols.push({
                name: row[0] as string,
                count: row[1] as number,
            });
        });
        db.close();
        return symbols;
    }

    async queryFilelist(category: number): Promise<Instruction[]> {
        const SQL = `SELECT file, SUM(file_events)
            from perf_symbol_details
            where component_category = :category
            GROUP BY file`;

        const db = await this.initialize();
        const results = db.exec(SQL, [category]);
        if (results.length === 0) {
            return [];
        }

        let filelist: Instruction[] = [];
        results[0].values.map((row: any) => {
            filelist.push({
                name: ComponentCategory[row[0] as number],
                count: row[1] as number,
            });
        });
        db.close();
        return filelist;
    }

    async queryTestSteps(): Promise<TestStep[]> {
        const SQL = `SELECT id, name, start, end from perf_test_step`;

        const db = await this.initialize();
        const results = db.exec(SQL);
        if (results.length === 0) {
            return [];
        }

        let steps: TestStep[] = [];
        results[0].values.map((row: any) => {
            steps.push({
                id: row[0] as number,
                name: row[1] as string,
                start: row[2] as number,
                end: row[3] as number,
            });
        });
        db.close();
        return steps;
    }
}

export async function getProcessesNameFromDb(dbpath: string): Promise<string[]> {
    let SQL = await sqlJs();
    const db = new SQL.Database(fs.readFileSync(dbpath));
    let processes: string[] = [];

    try {
        // 读取所有线程信息
        const results = db.exec(
            `SELECT thread_name from perf_thread WHERE thread_id = process_id and thread_name LIKE '%.%'`
        );
        if (results.length === 0) {
            return processes;
        }

        processes = results[0].values
            .filter((v: any) => {
                return !(v[0] as string).endsWith('.elf') && (v[0] as string).indexOf(':') < 0;
            })
            .map((v: any) => v[0] as string);
    } finally {
        db.close();
    }

    return processes;
}
