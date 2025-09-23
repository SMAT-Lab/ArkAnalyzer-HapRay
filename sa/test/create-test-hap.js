const JSZip = require('jszip');
const fs = require('fs');
const path = require('path');

async function createTestHap() {
    const zip = new JSZip();
    
    // 添加基本的HAP结构文件
    zip.file('config.json', JSON.stringify({
        "app": {
            "bundleName": "com.example.testapp",
            "version": {
                "code": 1000000,
                "name": "1.0.0"
            }
        }
    }, null, 2));
    
    // 添加一些SO文件（模拟不同框架）
    const soFiles = [
        'libs/arm64-v8a/libreact_core.so',
        'libs/arm64-v8a/libflutter.so', 
        'libs/arm64-v8a/libhermes.so',
        'libs/arm64-v8a/libmain.so'
    ];
    
    for (const soFile of soFiles) {
        // 创建模拟的SO文件内容（ELF头）
        const elfHeader = Buffer.from([
            0x7F, 0x45, 0x4C, 0x46, // ELF magic
            0x02, 0x01, 0x01, 0x00, // 64-bit, little-endian, version 1
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // padding
            0x03, 0x00, 0x3E, 0x00  // shared object, x86-64
        ]);
        zip.file(soFile, elfHeader);
    }
    
    // 添加一些资源文件
    zip.file('resources/icon.png', Buffer.from([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A // PNG header
    ]));
    
    zip.file('resources/config.json', JSON.stringify({
        "theme": "dark",
        "language": "zh-CN"
    }));
    
    // 添加JavaScript文件
    zip.file('js/main.js', `
// Main application entry point
console.log('Hello HAP Static Analyzer!');

function initApp() {
    console.log('Initializing application...');
}

initApp();
`);
    
    zip.file('js/vendor.min.js', `!function(e,t){"object"==typeof exports&&"undefined"!=typeof module?module.exports=t():"function"==typeof define&&define.amd?define(t):(e=e||self).Vue=t()}(this,function(){"use strict";return{}});`);
    
    // 添加Hermes字节码文件
    const hermesHeader = Buffer.from([
        0x1F, 0x1F, 0x1F, 0x1F, // Hermes magic
        0x48, 0x65, 0x72, 0x6D, 0x65, 0x73, 0x00, 0x00 // "Hermes"
    ]);
    zip.file('js/bundle.hbc', hermesHeader);
    
    // 添加嵌套的ZIP文件
    const nestedZip = new JSZip();
    nestedZip.file('nested-config.json', '{"nested": true}');
    nestedZip.file('nested-script.js', 'console.log("nested");');
    
    const nestedZipData = await nestedZip.generateAsync({type: 'nodebuffer'});
    zip.file('assets/nested-resources.zip', nestedZipData);
    
    // 生成HAP文件
    const hapData = await zip.generateAsync({type: 'nodebuffer'});
    const outputPath = path.join(__dirname, 'test-app.hap');
    
    fs.writeFileSync(outputPath, hapData);
    console.log(`Test HAP file created: ${outputPath}`);
    console.log(`File size: ${(hapData.length / 1024).toFixed(2)} KB`);
}

createTestHap().catch(console.error);
