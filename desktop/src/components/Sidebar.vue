<template>
  <aside
    class="sidebar shrink-0 border-r border-border bg-sidebar"
    :style="{ width: `${width}px` }"
  >
    <nav class="sidebar-nav flex flex-col">
      <div class="sidebar-group">
        <a
          href="#"
          class="sidebar-item"
          :class="{ 'sidebar-item--active': !selected }"
          @click.prevent="$emit('navigate', { page: 'home' })"
        >
          <span class="sidebar-item__icon">🏠</span>
          <span class="sidebar-item__label">首页</span>
        </a>
      </div>
      <template v-for="menu in sidebarMenu" :key="menu.category">
        <div class="sidebar-group">
          <div class="sidebar-group-label">{{ menu.icon }} {{ menu.category }}</div>
          <a
            v-for="item in menu.items"
            :key="`${item.plugin_id}-${item.action}`"
            href="#"
            class="sidebar-item sidebar-item--indent"
            :class="{ 'sidebar-item--active': selected?.pluginId === item.plugin_id && selected?.action === item.action }"
            @click.prevent="$emit('navigate', { page: 'tool', pluginId: item.plugin_id, action: item.action })"
          >
            <span class="sidebar-item__icon">{{ item.icon }}</span>
            <span class="sidebar-item__label">{{ item.display_name }}</span>
          </a>
        </div>
      </template>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import type { SidebarMenu } from "../composables/usePlugins"

defineProps<{
  width: number
  sidebarMenu: SidebarMenu[]
  selected?: { pluginId: string; action: string } | null
  page?: "home" | "settings" | "tool"
}>()
defineEmits<{
  navigate: [payload: { page: "home" | "settings" | "tool"; pluginId?: string; action?: string }]
}>()
</script>
