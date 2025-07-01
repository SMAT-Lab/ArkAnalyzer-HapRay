<template>
    <div>
      <el-upload
        class="upload-demo"
        action="#"
        :show-file-list="false"
        accept=".html"
        @change="handleFileChange"
      >
        <el-button type="primary">上传对比html文件</el-button>
      </el-upload>
      <el-button :disabled="!selectedFile" @click="processAndSaveFile">生成对比html文件</el-button>
      <p v-if="statusMessage">{{ statusMessage }}</p>
    </div>
</template>
  
<script setup lang="ts">
  import { ref } from 'vue';
  import { ElMessage } from 'element-plus';
  import type { UploadFile } from 'element-plus';
  
  // 存储选中的文件
  const selectedFile = ref<File | null>(null);
  // 存储状态信息
  const statusMessage = ref<string>('');
  
  // 处理文件选择事件
  const handleFileChange = (file: UploadFile) => {
    if (file.raw instanceof File) {
      selectedFile.value = file.raw;
    } else {
      selectedFile.value = null;
    }
  };
  
  // 处理并保存文件
  const processAndSaveFile = async () => {
    if (selectedFile.value) {
      statusMessage.value = '正在处理文件...';
      try {
        const reader = new FileReader();
        reader.readAsText(selectedFile.value);
  
        await new Promise((resolve) => {
          reader.onload = () => {
            const htmlContent = reader.result as string;
            const newHtmlContent = htmlContent.replace(
              /window\.compareJsonData = compareJson;/g,
              'window.compareJsonData = json;'
            ).replace(/window\.jsonData = json;/g,'window.jsonData = compareJson;').replace(/'\/tempCompareJsonData\/'/g,JSON.stringify(window.jsonData));
  
            console.log(newHtmlContent)
            const blob = new Blob([newHtmlContent], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
  
            const a = document.createElement('a');
            a.href = url;
            const compareFileName = selectedFile.value!.name.replace(/\.[^/.]+$/, '');
            const originalFileName = window.location.pathname.substring(window.location.pathname.lastIndexOf('/') + 1).replace(/\.[^/.]+$/, '')
            a.download = `${originalFileName}_VS_${compareFileName}.html`;
            a.click();
  
            URL.revokeObjectURL(url);
            statusMessage.value = '文件处理并保存成功';
            ElMessage.success('文件处理并保存成功');
            resolve(null);
          };
  
          reader.onerror = () => {
            statusMessage.value = '读取文件时出错';
            ElMessage.error('读取文件时出错');
            resolve(null);
          };
        });
      } catch (error) {
        statusMessage.value = '处理文件时出错';
        ElMessage.error('处理文件时出错');
        console.error(error);
      }
    }
  };
</script>
  
<style scoped>
  .upload-demo {
    margin-bottom: 10px;
  }
</style>