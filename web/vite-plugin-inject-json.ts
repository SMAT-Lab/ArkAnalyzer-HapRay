import { Plugin } from 'vite';
import fs from 'fs';

const injectJson: Plugin = {
  name: 'inject-json',
  transformIndexHtml(html) {
    if (process.env.NODE_ENV === 'development') {
      const jsonScript = fs.readFileSync('test_perf.json', { encoding: 'utf-8' });
      return html.replace('JSON_DATA_PLACEHOLDER', jsonScript);
    }
    return html;
  },
};

export default injectJson;
