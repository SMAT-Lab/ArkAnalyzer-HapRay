import { createI18n } from 'vue-i18n';
// 语言包
import zhCn from './zh-cn.ts';
import en from './en.ts';

const i18n = createI18n({
  legacy: false, // 设置为 false，启用 composition API 模式
  locale: 'zhCn',
  globalInjection: true, // 全局注册$t方法
  messages: {
    zhCn,
    en,
  },
});
export default i18n;
