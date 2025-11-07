#!/usr/bin/env node

/**
 * 从不同源文件提取数据并替换 web/index.html 中的占位符
 * 
 * 替换的占位符：
 * - DB_WORKER_CODE_PLACEHOLDER (从 web/dist/index.html 读取)
 * - SQL_WASM_BASE64_PLACEHOLDER (从 web/dist/index.html 读取)
 * - DB_DATA_PLACEHOLDER (从 hapray_report.html 读取)
 * - JSON_DATA_PLACEHOLDER (从 hapray_report.html 读取)
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 文件路径
const SOURCE_HTML = path.resolve(__dirname, '../../hapray_report.html'); // 用于提取 DB_DATA 和 JSON_DATA
const DIST_HTML = path.resolve(__dirname, '../dist/index.html'); // 用于提取 DB_WORKER_CODE 和 SQL_WASM
const TARGET_HTML = path.resolve(__dirname, '../index.html');
const TEST_HTML = path.resolve(__dirname, '../test.html');

/**
 * 从 HTML 中提取 script 标签内容
 * @param {string} html - HTML 内容
 * @param {string} id - script 标签的 id
 * @returns {string} script 标签内的文本内容
 */
function extractScriptContent(html, id) {
  const regex = new RegExp(`<script[^>]*id="${id}"[^>]*>([\\s\\S]*?)<\\/script>`, 'i');
  const match = html.match(regex);
  if (match && match[1]) {
    return match[1].trim();
  }
  return null;
}

/**
 * 从 HTML 中提取 JSON 数据
 * @param {string} html - HTML 内容
 * @returns {string} JSON 字符串（不带引号，用于替换占位符）
 */
function extractJsonData(html) {
  // 匹配 const json = '...'; 或 const json = "...";
  // 注意：JSON 数据可能包含转义的引号，所以需要更复杂的匹配
  // 先尝试单引号
  let regex = /const\s+json\s*=\s*'([^']*(?:\\'[^']*)*)'\s*;/;
  let match = html.match(regex);
  if (match && match[1]) {
    // 处理转义的单引号
    return match[1].replace(/\\'/g, "'");
  }
  
  // 尝试双引号
  regex = /const\s+json\s*=\s*"([^"]*(?:\\"[^"]*)*)"\s*;/;
  match = html.match(regex);
  if (match && match[1]) {
    // 处理转义的双引号
    return match[1].replace(/\\"/g, '"');
  }
  
  return null;
}

/**
 * 替换 HTML 中的占位符
 * @param {string} html - HTML 内容
 * @param {Object} replacements - 替换映射对象
 * @returns {string} 替换后的 HTML
 */
function replacePlaceholders(html, replacements) {
  let result = html;
  
  for (const [placeholder, value] of Object.entries(replacements)) {
    if (value !== null && value !== undefined) {
      // 转义特殊字符（用于正则表达式）
      const escapedPlaceholder = placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(escapedPlaceholder, 'g');
      result = result.replace(regex, value);
      console.log(`✓ 替换 ${placeholder}`);
    } else {
      console.warn(`⚠ 未找到 ${placeholder} 的内容，跳过替换`);
    }
  }
  
  return result;
}

/**
 * 主函数
 */
function main() {
  console.log('开始从不同源文件提取数据并替换 web/index.html...\n');
  
  // 检查源文件是否存在
  if (!fs.existsSync(SOURCE_HTML)) {
    console.error(`错误: 源文件不存在: ${SOURCE_HTML}`);
    process.exit(1);
  }
  
  // 检查 dist/index.html 是否存在
  if (!fs.existsSync(DIST_HTML)) {
    console.error(`错误: dist/index.html 不存在: ${DIST_HTML}`);
    process.exit(1);
  }
  
  // 检查目标文件是否存在
  if (!fs.existsSync(TARGET_HTML)) {
    console.error(`错误: 目标文件不存在: ${TARGET_HTML}`);
    process.exit(1);
  }

  try {
    // 读取源 HTML 文件（用于提取 DB_DATA 和 JSON_DATA）
    console.log(`读取源文件 (hapray_report.html): ${SOURCE_HTML}`);
    const sourceHtml = fs.readFileSync(SOURCE_HTML, 'utf-8');
    
    // 读取 dist/index.html 文件（用于提取 DB_WORKER_CODE 和 SQL_WASM）
    console.log(`读取 dist/index.html: ${DIST_HTML}`);
    const distHtml = fs.readFileSync(DIST_HTML, 'utf-8');
    
    // 读取目标 HTML 文件
    console.log(`读取目标文件: ${TARGET_HTML}`);
    const targetHtml = fs.readFileSync(TARGET_HTML, 'utf-8');
    
    // 提取数据
    console.log('\n提取数据...');
    // 从 dist/index.html 提取
    const dbWorkerCode = extractScriptContent(distHtml, 'dbWorkerCode');
    const sqlWasmBase64 = extractScriptContent(distHtml, 'sqlWasmBase64');
    // 从 hapray_report.html 提取
    const dbData = extractScriptContent(sourceHtml, 'dbData');
    const jsonData = extractJsonData(sourceHtml);
    
    // 显示提取结果
    console.log(`  - dbWorkerCode (来自 dist/index.html): ${dbWorkerCode ? `${dbWorkerCode.length} 字符` : '未找到'}`);
    console.log(`  - sqlWasmBase64 (来自 dist/index.html): ${sqlWasmBase64 ? `${sqlWasmBase64.length} 字符` : '未找到'}`);
    console.log(`  - dbData (来自 hapray_report.html): ${dbData ? `${dbData.length} 字符` : '未找到'}`);
    console.log(`  - jsonData (来自 hapray_report.html): ${jsonData ? `${jsonData.length} 字符` : '未找到'}`);
    
    // 准备替换映射
    const replacements = {
      'DB_WORKER_CODE_PLACEHOLDER': dbWorkerCode,
      'SQL_WASM_BASE64_PLACEHOLDER': sqlWasmBase64,
      'DB_DATA_PLACEHOLDER': dbData,
      'JSON_DATA_PLACEHOLDER': jsonData,
    };
    
    // 执行替换
    console.log('\n执行替换...');
    const resultHtml = replacePlaceholders(targetHtml, replacements);
    
    // 检查是否有变化
    if (resultHtml === targetHtml) {
      console.log('\n⚠ 警告: 没有进行任何替换，可能占位符不存在或已替换');
    }
    
    // 写回文件
    console.log(`\n写入文件: ${TEST_HTML}`);
    fs.writeFileSync(TEST_HTML, resultHtml, 'utf-8');
    
    console.log('\n✓ 完成！');
    
  } catch (error) {
    console.error('错误:', error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// 运行主函数
main();

