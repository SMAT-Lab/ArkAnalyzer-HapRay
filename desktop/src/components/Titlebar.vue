<template>
  <header
    class="h-10 shrink-0 bg-background-base flex items-center relative border-b border-border"
    data-tauri-drag-region
  >
    <div
      :class="[
        'flex items-center w-full min-w-0',
        mac ? '' : 'pl-2',
        windows ? '' : 'pr-6',
      ]" data-tauri-drag-region @mousedown="onDrag"
    >
      <template v-if="mac">
        <div class="w-[72px] h-full shrink-0" data-tauri-drag-region />
      </template>
      <div class="flex-1 h-full" data-tauri-drag-region />
      <div class="flex gap-3 shrink-0 flex-1 justify-end items-center pr-2" data-tauri-drag-region>
        <button
          type="button"
          class="sidebar-toggle group size-6 rounded flex items-center justify-center hover:bg-border"
          @click="$emit('toggle-sidebar')" aria-label="切换左侧边栏" :aria-expanded="sidebarOpen"
        >
          <div class="relative flex items-center justify-center size-4">
            <svg class="size-4 absolute inset-0 group-hover-hide" viewBox="0 0 20 20" fill="currentColor">
              <template v-if="sidebarOpen">
                <path
                  d="M2.91732 2.91602L7.91732 2.91602L7.91732 17.0827H2.91732L2.91732 2.91602Z"
                  fill="currentColor"
                />
                <path
                  d="M2.91732 2.91602L17.084 2.91602M2.91732 2.91602L2.91732 17.0827M2.91732 2.91602L7.91732 2.91602M17.084 2.91602L17.084 17.0827M17.084 2.91602L7.91732 2.91602M17.084 17.0827L2.91732 17.0827M17.084 17.0827L7.91732 17.0827M2.91732 17.0827H7.91732M7.91732 17.0827L7.91732 2.91602"
                  stroke="currentColor" stroke-linecap="square"
                />
              </template>
              <template v-else>
                <path
                  d="M2.91675 2.91699L2.91675 2.41699L2.41675 2.41699L2.41675 2.91699L2.91675 2.91699ZM17.0834 2.91699L17.5834 2.91699L17.5834 2.41699L17.0834 2.41699L17.0834 2.91699ZM17.0834 17.0837L17.0834 17.5837L17.5834 17.5837L17.0834 17.5837L17.0834 17.0837ZM2.91675 17.0837L2.41675 17.0837L2.41675 17.5837L2.91675 17.5837L2.91675 17.0837ZM7.41674 17.0837L7.41674 17.5837L8.41674 17.5837L8.41674 17.0837L7.91674 17.0837L7.41674 17.0837ZM8.41674 2.91699L8.41674 2.41699L7.41674 2.41699L7.41674 2.91699L7.91674 2.91699L8.41674 2.91699ZM2.91675 2.91699L2.91675 3.41699L17.0834 3.41699L17.0834 2.91699L17.0834 2.41699L2.91675 2.41699L2.91675 2.91699ZM17.0834 2.91699L16.5834 2.91699L16.5834 17.0837L17.0834 17.0837L17.5834 17.0837L17.5834 2.91699L17.0834 2.91699ZM17.0834 17.0837L17.0834 16.5837L2.91675 16.5837L2.91675 17.0837L2.91675 17.5837L17.0834 17.5837L17.0834 17.0837ZM2.91675 17.0837L3.41675 17.0837L3.41675 2.91699L2.91675 2.91699L2.41675 2.91699L2.41675 17.0837L2.91675 17.0837ZM7.91674 17.0837L8.41674 17.0837L8.41674 2.91699L7.91674 2.91699L7.41674 2.91699L7.41674 17.0837L7.91674 17.0837Z"
                  fill="currentColor"
                />
              </template>
            </svg>
            <svg class="size-4 absolute inset-0 group-hover-show" viewBox="0 0 20 20" fill="currentColor">
              <path
                d="M2.91732 2.91602L7.91732 2.91602L7.91732 17.0827H2.91732L2.91732 2.91602Z" fill="currentColor"
                fill-opacity="0.4"
              />
              <path
                d="M2.91732 2.91602L17.084 2.91602M2.91732 2.91602L2.91732 17.0827M2.91732 2.91602L7.91732 2.91602M17.084 2.91602L17.084 17.0827M17.084 2.91602L7.91732 2.91602M17.084 17.0827L2.91732 17.0827M17.084 17.0827L7.91732 17.0827M2.91732 17.0827H7.91732M7.91732 17.0827L7.91732 2.91602"
                stroke="currentColor" stroke-linecap="square"
              />
            </svg>
            <svg class="size-4 absolute inset-0 group-active-show" viewBox="0 0 20 20" fill="currentColor">
              <template v-if="sidebarOpen">
                <path
                  d="M2.91675 2.91699L2.91675 2.41699L2.41675 2.41699L2.41675 2.91699L2.91675 2.91699ZM17.0834 2.91699L17.5834 2.91699L17.5834 2.41699L17.0834 2.41699L17.0834 2.91699ZM17.0834 17.0837L17.0834 17.5837L17.5834 17.5837L17.0834 17.5837L17.0834 17.0837ZM2.91675 17.0837L2.41675 17.0837L2.41675 17.5837L2.91675 17.5837L2.91675 17.0837ZM7.41674 17.0837L7.41674 17.5837L8.41674 17.5837L8.41674 17.0837L7.91674 17.0837L7.41674 17.0837ZM8.41674 2.91699L8.41674 2.41699L7.41674 2.41699L7.41674 2.91699L7.91674 2.91699L8.41674 2.91699ZM2.91675 2.91699L2.91675 3.41699L17.0834 3.41699L17.0834 2.91699L17.0834 2.41699L2.91675 2.41699L2.91675 2.91699ZM17.0834 2.91699L16.5834 2.91699L16.5834 17.0837L17.0834 17.0837L17.5834 17.0837L17.5834 2.91699L17.0834 2.91699ZM17.0834 17.0837L17.0834 16.5837L2.91675 16.5837L2.91675 17.0837L2.91675 17.5837L17.0834 17.5837L17.0834 17.0837ZM2.91675 17.0837L3.41675 17.0837L3.41675 2.91699L2.91675 2.91699L2.41675 2.91699L2.41675 17.0837L2.91675 17.0837ZM7.91674 17.0837L8.41674 17.0837L8.41674 2.91699L7.91674 2.91699L7.41674 2.91699L7.41674 17.0837L7.91674 17.0837Z"
                  fill="currentColor"
                />
              </template>
              <template v-else>
                <path
                  d="M2.91732 2.91602L7.91732 2.91602L7.91732 17.0827H2.91732L2.91732 2.91602Z"
                  fill="currentColor"
                />
                <path
                  d="M2.91732 2.91602L17.084 2.91602M2.91732 2.91602L2.91732 17.0827M2.91732 2.91602L7.91732 2.91602M17.084 2.91602L17.084 17.0827M17.084 2.91602L7.91732 2.91602M17.084 17.0827L2.91732 17.0827M17.084 17.0827L7.91732 17.0827M2.91732 17.0827H7.91732M7.91732 17.0827L7.91732 2.91602"
                  stroke="currentColor" stroke-linecap="square"
                />
              </template>
            </svg>
          </div>
        </button>
        <button
          type="button"
          class="sidebar-toggle group size-6 rounded flex items-center justify-center hover:bg-border"
          @click="$emit('toggle-history-sidebar')" aria-label="切换执行记录侧边栏" :aria-expanded="historySidebarOpen"
        >
          <div class="relative flex items-center justify-center size-4">
            <svg class="size-4 absolute inset-0 group-hover-hide" viewBox="0 0 20 20" fill="currentColor">
              <template v-if="historySidebarOpen">
                <path d="M12.0827 2.91602L17.0827 2.91602L17.0827 17.0827L12.0827 17.0827L12.0827 2.91602Z" fill="currentColor" />
                <path d="M2.91602 2.91602L17.0827 2.91602L17.0827 17.0827L2.91602 17.0827M2.91602 2.91602L2.91602 17.0827M2.91602 2.91602L12.0827 2.91602L12.0827 17.0827L2.91602 17.0827" fill="none" stroke="currentColor" stroke-linecap="square" />
              </template>
              <template v-else>
                <path d="M17.0832 2.91699L17.5832 2.91699L17.5832 2.41699L17.0832 2.41699L17.0832 2.91699ZM2.91651 2.91699L2.91651 2.41699L2.41651 2.41699L2.41651 2.91699L2.91651 2.91699ZM2.9165 17.0837L2.4165 17.0837L2.4165 17.5837L2.9165 17.5837L2.9165 17.0837ZM17.0832 17.0837L17.0832 17.5837L17.5832 17.5837L17.0832 17.0837L17.0832 17.0837ZM11.5832 17.0837L11.5832 17.5837L12.5832 17.5837L12.5832 17.0837L12.0832 17.0837L11.5832 17.0837ZM12.5832 2.91699L12.5832 2.41699L11.5832 2.41699L11.5832 2.91699L12.0832 2.91699L12.5832 2.91699ZM17.0832 2.91699L17.0832 2.41699L2.91651 2.41699L2.91651 2.91699L2.91651 3.41699L17.0832 3.41699L17.0832 2.91699ZM2.91651 2.91699L2.41651 2.91699L2.4165 17.0837L2.9165 17.0837L3.4165 17.0837L3.41651 2.91699L2.91651 2.91699ZM2.9165 17.0837L2.9165 17.5837L17.0832 17.5837L17.0832 17.0837L17.0832 16.5837L2.9165 16.5837L2.9165 17.0837ZM17.0832 17.0837L17.5832 17.0837L17.5832 2.91699L17.0832 2.91699L16.5832 2.91699L16.5832 17.0837L17.0832 17.0837ZM12.0832 17.0837L12.5832 17.0837L12.5832 2.91699L12.0832 2.91699L11.5832 2.91699L11.5832 17.0837L12.0832 17.0837Z" fill="currentColor" />
              </template>
            </svg>
            <svg class="size-4 absolute inset-0 group-hover-show" viewBox="0 0 20 20" fill="currentColor">
              <path v-if="historySidebarOpen" d="M12.0827 2.91602L17.0827 2.91602L17.0827 17.0827L12.0827 17.0827L12.0827 2.91602Z" fill="currentColor" fill-opacity="40%" />
              <path v-else d="M12.0827 2.91602L2.91602 2.91602L2.91602 17.0827L12.0827 17.0827L12.0827 2.91602Z" fill="currentColor" fill-opacity="40%" />
              <path d="M2.91602 2.91602L17.0827 2.91602L17.0827 17.0827L2.91602 17.0827M2.91602 2.91602L2.91602 17.0827M2.91602 2.91602L12.0827 2.91602L12.0827 17.0827L2.91602 17.0827" fill="none" stroke="currentColor" stroke-linecap="square" />
            </svg>
            <svg class="size-4 absolute inset-0 group-active-show" viewBox="0 0 20 20" fill="currentColor">
              <template v-if="historySidebarOpen">
                <path d="M17.0832 2.91699L17.5832 2.91699L17.5832 2.41699L17.0832 2.41699L17.0832 2.91699ZM2.91651 2.91699L2.91651 2.41699L2.41651 2.41699L2.41651 2.91699L2.91651 2.91699ZM2.9165 17.0837L2.4165 17.0837L2.4165 17.5837L2.9165 17.5837L2.9165 17.0837ZM17.0832 17.0837L17.0832 17.5837L17.5832 17.5837L17.0832 17.0837L17.0832 17.0837ZM11.5832 17.0837L11.5832 17.5837L12.5832 17.5837L12.5832 17.0837L12.0832 17.0837L11.5832 17.0837ZM12.5832 2.91699L12.5832 2.41699L11.5832 2.41699L11.5832 2.91699L12.0832 2.91699L12.5832 2.91699ZM17.0832 2.91699L17.0832 2.41699L2.91651 2.41699L2.91651 2.91699L2.91651 3.41699L17.0832 3.41699L17.0832 2.91699ZM2.91651 2.91699L2.41651 2.91699L2.4165 17.0837L2.9165 17.0837L3.4165 17.0837L3.41651 2.91699L2.91651 2.91699ZM2.9165 17.0837L2.9165 17.5837L17.0832 17.5837L17.0832 17.0837L17.0832 16.5837L2.9165 16.5837L2.9165 17.0837ZM17.0832 17.0837L17.5832 17.0837L17.5832 2.91699L17.0832 2.91699L16.5832 2.91699L16.5832 17.0837L17.0832 17.0837ZM12.0832 17.0837L12.5832 17.0837L12.5832 2.91699L12.0832 2.91699L11.5832 2.91699L11.5832 17.0837L12.0832 17.0837Z" fill="currentColor" />
              </template>
              <template v-else>
                <path d="M12.0827 2.91602L17.0827 2.91602L17.0827 17.0827L12.0827 17.0827L12.0827 2.91602Z" fill="currentColor" />
                <path d="M2.91602 2.91602L17.0827 2.91602L17.0827 17.0827L2.91602 17.0827M2.91602 2.91602L2.91602 17.0827M2.91602 2.91602L12.0827 2.91602L12.0827 17.0827L2.91602 17.0827" fill="none" stroke="currentColor" stroke-linecap="square" />
              </template>
            </svg>
          </div>
        </button>
        <button
          type="button" class="settings-btn size-6 rounded flex items-center justify-center hover:bg-border"
          @click="$emit('open-settings')" aria-label="设置"
        >
          <svg class="size-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
            <path
              d="M7.62516 4.46094L5.05225 3.86719L3.86475 5.05469L4.4585 7.6276L2.0835 9.21094V10.7943L4.4585 12.3776L3.86475 14.9505L5.05225 16.138L7.62516 15.5443L9.2085 17.9193H10.7918L12.3752 15.5443L14.9481 16.138L16.1356 14.9505L15.5418 12.3776L17.9168 10.7943V9.21094L15.5418 7.6276L16.1356 5.05469L14.9481 3.86719L12.3752 4.46094L10.7918 2.08594H9.2085L7.62516 4.46094Z"
            />
            <path
              d="M12.5002 10.0026C12.5002 11.3833 11.3809 12.5026 10.0002 12.5026C8.61945 12.5026 7.50016 11.3833 7.50016 10.0026C7.50016 8.62189 8.61945 7.5026 10.0002 7.5026C11.3809 7.5026 12.5002 8.62189 12.5002 10.0026Z"
            />
          </svg>
        </button>
      </div>
      <!-- 始终挂载 data-tauri-decorum-tb，供 Decorum 在首帧找到；非 Windows 用 v-show 隐藏 -->
      <div v-show="windows" class="flex flex-row items-center shrink-0">
        <div class="w-6 shrink-0" />
        <div data-tauri-decorum-tb class="titlebar-decorum flex flex-row" />
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"

withDefaults(
  defineProps<{ sidebarOpen: boolean; historySidebarOpen?: boolean }>(),
  { historySidebarOpen: false }
)
defineEmits<{ "toggle-sidebar": []; "toggle-history-sidebar": []; "open-settings": [] }>()

const mac = ref(false)
const windows = ref(false)

import { isTauriEnv } from "../utils/tauri"

const isTauri = isTauriEnv

const interactive = (target: EventTarget | null): boolean => {
  if (!(target instanceof Element)) return false
  const selector =
    "button, a, input, textarea, select, option, [role='button'], [role='menuitem'], [contenteditable='true'], [contenteditable=''], [data-tauri-decorum-tb]"
  return !!target.closest(selector)
}

const onDrag = async (e: MouseEvent) => {
  if (e.buttons !== 1) return
  if (interactive(e.target)) return
  if (!isTauri()) return

  const { getCurrentWindow } = await import("@tauri-apps/api/window")
  const win = getCurrentWindow()
  if (!win?.startDragging) return

  e.preventDefault()
  win.startDragging().catch(() => undefined)
}

onMounted(async () => {
  if (!isTauri()) return

  const { type: osType } = await import("@tauri-apps/plugin-os")
  const os = await osType()
  mac.value = os === "macos"
  windows.value = os === "windows"

  const { getCurrentWebviewWindow } = await import("@tauri-apps/api/webviewWindow")
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches
  const value = dark ? "dark" : "light"
  const win = getCurrentWebviewWindow()
  if (win?.setTheme) {
    await win.setTheme(value).catch(() => undefined)
  }

  const mq = window.matchMedia("(prefers-color-scheme: dark)")
  mq.addEventListener("change", async () => {
    const d = window.matchMedia("(prefers-color-scheme: dark)").matches
    const v = d ? "dark" : "light"
    const w = getCurrentWebviewWindow()
    if (w?.setTheme) await w.setTheme(v).catch(() => undefined)
  })
})
</script>
