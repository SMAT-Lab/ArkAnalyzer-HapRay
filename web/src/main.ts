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
        baseMark: string;
        compareMark: string;
    }
}

if (window.jsonData) {
    jsonDataStore.setJsonData(changeBase64Str2Json(window.jsonData), changeBase64Str2Json(window.compareJsonData));
}
app.mount('#app');
