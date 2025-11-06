import { Plugin } from 'vite';
import fs from 'fs';
import path from 'path';
import { gzipSync } from 'zlib';

/**
 * Vite 插件：在构建最后阶段注入 JSON 和 DB 数据到 HTML
 * 替换 HTML 中的 JSON_DATA_PLACEHOLDER 和 DB_DATA_PLACEHOLDER
 */
export default function injectDataPlugin(): Plugin {
  const projectRoot = path.resolve(__dirname);
  
  return {
    name: 'inject-data',
    // 使用 closeBundle 钩子，确保在所有构建完成后执行（在 vite-plugin-singlefile 之后）
    closeBundle() {
      const outputDir = path.resolve(projectRoot, 'dist');
      const htmlFile = path.resolve(outputDir, 'index.html');
      
      console.log('[inject-data] closeBundle - 开始注入数据到 HTML');
      console.log('[inject-data] closeBundle - HTML 文件路径:', htmlFile);
      
      if (!fs.existsSync(htmlFile)) {
        console.warn('[inject-data] closeBundle - ⚠️ HTML 文件不存在:', htmlFile);
        return;
      }
      
      let html = fs.readFileSync(htmlFile, 'utf-8');
      let hasChanges = false;
      
      // 1. 处理 JSON_DATA_PLACEHOLDER
      if (html.includes('JSON_DATA_PLACEHOLDER')) {
        console.log('[inject-data] closeBundle - 处理 JSON_DATA_PLACEHOLDER');
        
        let jsonDataStr = '';
        const jsonFilePath = path.resolve(projectRoot, 'test_perf.json');
        
        if (fs.existsSync(jsonFilePath)) {
          try {
            const jsonContent = fs.readFileSync(jsonFilePath, 'utf-8');
            console.log('[inject-data] closeBundle - ✅ 从文件读取 JSON 数据:', jsonFilePath, '大小:', jsonContent.length, 'chars');
            
            // 压缩 JSON 数据（与生产环境保持一致：gzip + base64）
            const jsonBuffer = Buffer.from(jsonContent, 'utf-8');
            const compressedJson = gzipSync(jsonBuffer, { level: 9 });
            jsonDataStr = compressedJson.toString('base64');
            
            console.log('[inject-data] closeBundle - ✅ JSON 压缩完成，压缩后大小:', compressedJson.length, 'bytes');
            console.log('[inject-data] closeBundle - ✅ JSON Base64 编码完成，编码后大小:', jsonDataStr.length, 'chars');
            
            const compressionRatio = ((1 - compressedJson.length / jsonBuffer.length) * 100).toFixed(1);
            console.log('[inject-data] closeBundle - JSON 压缩率:', compressionRatio + '%');
          } catch (error) {
            console.error('[inject-data] closeBundle - ❌ 读取或处理 JSON 文件失败:', error);
            jsonDataStr = Buffer.from('{}', 'utf-8').toString('base64'); // 默认空对象的 base64
          }
        } else {
          console.warn('[inject-data] closeBundle - ⚠️ JSON 文件不存在，使用空对象:', jsonFilePath);
          jsonDataStr = Buffer.from('{}', 'utf-8').toString('base64');
        }
        
        // 替换占位符（需要转义单引号，因为 HTML 中使用单引号）
        html = html.replace(/JSON_DATA_PLACEHOLDER/g, jsonDataStr.replace(/'/g, "\\'"));
        hasChanges = true;
        console.log('[inject-data] closeBundle - ✅ JSON_DATA_PLACEHOLDER 已替换');
      }
      
      // 2. 处理 DB_DATA_PLACEHOLDER
      if (html.includes('DB_DATA_PLACEHOLDER')) {
        console.log('[inject-data] closeBundle - 处理 DB_DATA_PLACEHOLDER');
        
        const dbFilePath = path.resolve(projectRoot, 'hapray_report.db');
        
        if (fs.existsSync(dbFilePath)) {
          try {
            // 读取数据库文件
            const dbData = fs.readFileSync(dbFilePath);
            console.log('[inject-data] closeBundle - ✅ 读取数据库文件:', dbFilePath, '大小:', dbData.length, 'bytes');
            
            // 使用 gzip 压缩（level 9 最大压缩）
            const compressedData = gzipSync(dbData, { level: 9 });
            console.log('[inject-data] closeBundle - ✅ Gzip 压缩完成，压缩后大小:', compressedData.length, 'bytes');
            
            // Base64 编码
            const base64Data = compressedData.toString('base64');
            console.log('[inject-data] closeBundle - ✅ Base64 编码完成，编码后大小:', base64Data.length, 'chars');
            
            // 计算压缩率
            const compressionRatio = ((1 - compressedData.length / dbData.length) * 100).toFixed(1);
            console.log('[inject-data] closeBundle - 压缩率:', compressionRatio + '%');
            
            // 替换占位符
            html = html.replace(/DB_DATA_PLACEHOLDER/g, base64Data);
            hasChanges = true;
            console.log('[inject-data] closeBundle - ✅ DB_DATA_PLACEHOLDER 已替换');
          } catch (error) {
            console.error('[inject-data] closeBundle - ❌ 处理数据库文件失败:', error);
            // 如果处理失败，替换为空字符串
            html = html.replace(/DB_DATA_PLACEHOLDER/g, '');
            hasChanges = true;
          }
        } else {
          console.warn('[inject-data] closeBundle - ⚠️ 数据库文件不存在，使用空字符串:', dbFilePath);
          // 如果文件不存在，替换为空字符串
          html = html.replace(/DB_DATA_PLACEHOLDER/g, '');
          hasChanges = true;
        }
      }
      
      // 3. 保存修改后的 HTML
      if (hasChanges) {
        fs.writeFileSync(htmlFile, html, 'utf-8');
        console.log('[inject-data] closeBundle - ✅ HTML 文件已更新');
      } else {
        console.log('[inject-data] closeBundle - ℹ️ 未找到需要替换的占位符，跳过');
      }
    },
  };
}

