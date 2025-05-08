import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import i18n from './i18n/index';
import { vscode } from './utils/vscode';
import { useJsonDataStore, type JSONData } from './stores/jsonDataStore.ts';

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
        jsonData: JSONData;
        compareJsonData: JSONData;
    }
}

if (window.jsonData) {
    jsonDataStore.setJsonData(window.jsonData,window.compareJsonData);
}
app.mount('#app');
