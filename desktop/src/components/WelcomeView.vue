<template>
  <div class="py-12 text-center">
    <h1 class="text-xl font-medium">欢迎使用 ArkAnalyzer-HapRay</h1>
    <p class="mt-2 text-muted-foreground">请从左侧选择工具开始使用</p>
    <p v-if="loading" class="mt-4 text-sm text-muted-foreground">正在加载插件...</p>
    <p v-else-if="error" class="mt-4 text-sm text-red-500">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  loading?: boolean
  error?: string | null
}>()
</script>
