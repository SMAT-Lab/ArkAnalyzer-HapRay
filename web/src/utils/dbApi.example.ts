/**
 * SQLite Worker API 使用示例
 * 
 * 这个文件展示了如何使用 dbApi 来操作 SQLite 数据库
 */

import { initDb, getDbApi } from './dbApi';

// 示例 1: 初始化数据库（从 window.dbData 读取）
async function example1() {
  // 数据库数据会从 window.dbData 自动读取（在 index.html 中定义）
  // WASM 数据会从 window.__sqlWasmBase64 自动读取（由插件内联）
  const db = await initDb();
  
  // 执行查询
  const results = await db.query('SELECT * FROM users WHERE age > ?', [18]);
  console.log('查询结果:', results);
  
  // 执行更新
  await db.exec('UPDATE users SET name = ? WHERE id = ?', ['New Name', 1]);
  
  // 关闭数据库
  await db.close();
}

// 示例 2: 使用自定义数据库数据初始化
async function example2() {
  // 如果有自定义的数据库数据（gzip+base64 格式）
  const customDbData = 'H4sIAAAAAAAAA...'; // base64 编码的 gzip 压缩数据库
  const db = await initDb(customDbData);
  
  // 执行查询
  const results = await db.query('SELECT * FROM products');
  console.log('产品列表:', results);
  
  await db.close();
}

// 示例 3: 使用单例模式
async function example3() {
  // 获取单例实例
  const db = getDbApi();
  
  // 初始化（只需要调用一次）
  await db.init();
  
  // 在应用的任何地方都可以使用同一个实例
  const results1 = await db.query('SELECT COUNT(*) as count FROM orders');
  console.log('订单数量:', results1);
  
  const results2 = await db.query('SELECT * FROM orders ORDER BY created_at DESC LIMIT 10');
  console.log('最新订单:', results2);
  
  // 应用退出时关闭
  // await db.close();
}

// 示例 4: 错误处理
async function example4() {
  try {
    const db = await initDb();
    
    // 执行可能出错的查询
    const results = await db.query('SELECT * FROM non_existent_table');
    
    await db.close();
  } catch (error) {
    console.error('数据库操作失败:', error);
  }
}

// 示例 5: 在 Vue 组件中使用
/*
import { ref, onMounted, onUnmounted } from 'vue';
import { initDb, getDbApi } from '@/utils/dbApi';

export default {
  setup() {
    const db = ref(null);
    const data = ref([]);
    
    onMounted(async () => {
      // 初始化数据库
      db.value = await initDb();
      
      // 加载数据
      data.value = await db.value.query('SELECT * FROM items');
    });
    
    onUnmounted(async () => {
      // 清理资源
      if (db.value) {
        await db.value.close();
      }
    });
    
    return {
      data
    };
  }
};
*/

