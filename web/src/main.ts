import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import i18n from './i18n/index';
import { vscode } from './utils/vscode';
import { useJsonDataStore } from './stores/jsonDataStore.ts';
import { changeBase64Str2Json } from './utils/jsonUtil.ts';
import { initDb } from './utils/dbApi.ts';

const app = createApp(App);
app.config.globalProperties.$vscode = vscode;
app.use(i18n);
app.use(createPinia());
app.use(router);
app.use(ElementPlus);
// 获取存储实例
const jsonDataStore = useJsonDataStore();

declare global {
    interface Window {
        initialPage: string;
        jsonData: string;
        frameJsonData: string;
        emptyFrameJson: string;
        compareJsonData: string;
        dbData: string; // gzip+base64 格式的 SQLite 数据库文件
        baseMark: string;
        compareMark: string;
        dataType: string;
    }
}

/**
 * 从 <script type="text/plain"> 标签读取数据
 * @param id 脚本标签的 id
 * @returns 脚本标签的内容，如果不存在则返回空字符串
 */
function getDataFromScript(id: string): string {
    const scriptElement = document.getElementById(id);
    if (scriptElement && scriptElement.textContent !== null) {
        return scriptElement.textContent;
    }
    return '';
}

window.dbData = getDataFromScript('dbData');
if (window.dbData) {
    (async function initDatabase() {
        try {
            console.log('Initializing database from window.dbData...');
            await initDb(window.dbData); // 会自动从 window.dbData 和 window.__sqlWasmBase64 读取
            console.log('Database initialized successfully');
        } catch (error) {
            console.error('Failed to initialize database:', error);
        }
    })();
} else {
    console.log('No database data found, skipping database initialization');
    if (window.dbData) {
        console.log('Database data exists but appears to be placeholder or empty');
        console.log('Data type:', typeof window.dbData);
        console.log('Data length:', window.dbData.length);
        console.log('Is placeholder:', window.dbData === 'DB_DATA_PLACEHOLDER');
    }
}

// 加载 JSON 数据
if (window.jsonData) {
    jsonDataStore.setJsonData(
        changeBase64Str2Json(window.jsonData, window.dataType), 
        changeBase64Str2Json(window.compareJsonData, window.dataType)
    );
}


// 启动应用
app.mount('#app');