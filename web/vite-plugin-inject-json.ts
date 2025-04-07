import { Plugin, PluginOption } from 'vite';
import { readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';

const injectJson: Plugin = {
    name: 'inject-json',
    transformIndexHtml(html) {
        // const jsonScript = `<script>window.jsonData = ${JSON.stringify(injectedJson)};</script>`;
        //const jsonScript = `<script src='data.js'></script>`;
    //     const jsonScript = `<script>
    //     const json = JSON_DATA_PLACEHOLDER;
    //   window.jsonData = json 
    //   </script>
    //   `;
        const jsonScript = ``;
        html = html.replace('</body>', `${jsonScript}</body>`);
        return html;
    }
};

export default injectJson;