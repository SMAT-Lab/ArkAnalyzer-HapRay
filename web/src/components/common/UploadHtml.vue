<template>
  <div class="upload-section">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>对比数据上传</span>
        </div>
      </template>
      <div class="upload-content">
        <!-- 版本标识设置 -->
        <div class="version-marks-section">
          <h4>版本标识设置</h4>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="基线标识:">
                <el-input v-model="baseMark" placeholder="请输入基线版本标识" size="small" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="对比标识:">
                <el-input v-model="compareMark" placeholder="请输入对比版本标识" size="small" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <input ref="fileInputRef" type="file" accept=".html" style="display: none" @change="onFileInputChange" />
        <el-button type="primary" @click="handleUploadAndProcess">
          <el-icon class="el-icon--upload"><i class="el-icon-upload"></i></el-icon>
          上传并生成对比html文件
        </el-button>
        <div class="el-upload__tip" style="margin-top: 10px; color: #888;">
          请选择对比html文件，将自动处理对比结果并下载到本地，另存为新html文件。
        </div>
        <p v-if="statusMessage" class="status-message">{{ statusMessage }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const fileInputRef = ref<HTMLInputElement | null>(null);
const statusMessage = ref<string>('');

// 版本标识
const baseMark = ref('base');
const compareMark = ref('compare');

const handleUploadAndProcess = () => {
  // 设置window对象的标识值
  window.baseMark = baseMark.value;
  window.compareMark = compareMark.value;

  fileInputRef.value?.click();
};

const onFileInputChange = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files && input.files[0];
  if (!file) return;

  statusMessage.value = '正在处理文件...';
  try {
    const reader = new FileReader();
    reader.readAsText(file);
    await new Promise(() => {
      reader.onload = () => {
        const htmlContent = reader.result as string;
       
        // 替换对比数据和版本标识
        const newHtmlContent = htmlContent
          .replace(/'\/tempCompareJsonData\/'/g, JSON.stringify(window.jsonData))
          .replace('window.jsonData = json','window.jsonData = compareJson')
          .replace('window.compareJsonData = compareJson','window.compareJsonData = json')
          .replace(/'WINDOW_BASE_MARK_PLACEHOLDER'/g, JSON.stringify(window.baseMark))
          .replace(/'WINDOW_COMPARE_MARK_PLACEHOLDER'/g, JSON.stringify(window.compareMark));

        const blob = new Blob([newHtmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const compareFileName = file.name.replace(/\.[^/.]+$/, '');
        const originalFileName = window.location.pathname.substring(window.location.pathname.lastIndexOf('/') + 1).replace(/\.[^/.]+$/, '');
        const a = document.createElement('a');
        a.href = url;
        a.download = `${originalFileName}_VS_${compareFileName}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        statusMessage.value = '文件处理并保存成功';

      };
      reader.onerror = () => {
        statusMessage.value = '文件读取失败';

      };
    });
  } catch (error) {
    statusMessage.value = '处理文件时出错';

    console.error(error);
  } finally {
    // 清空input，允许再次选择同一个文件
    if (fileInputRef.value) fileInputRef.value.value = '';
  }
};
</script>

<style scoped>
.upload-section {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.upload-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.el-upload__tip {
  font-size: 13px;
  color: #888;
}

.status-message {
  margin-top: 10px;
  color: #2196f3;
  font-size: 14px;
}

.el-button {
  margin-bottom: 8px;
}

.version-marks-section {
  margin-bottom: 20px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.version-marks-section h4 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 14px;
  font-weight: 600;
}

.el-form-item {
  margin-bottom: 8px;
}

.el-form-item label {
  font-size: 13px;
  color: #666;
  font-weight: 500;
}
</style>
