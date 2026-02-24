<template>
  <div class="settings-view">
    <div class="settings-layout">
      <nav class="settings-nav">
        <div class="settings-nav-section">
          <div class="settings-nav-group">插件配置</div>
          <template v-if="pluginsWithConfig.length === 0">
            <div
              class="settings-nav-item"
              :class="{ active: activeSection === 'plugins' }"
              @click="activeSection = 'plugins'"
            >
              插件配置
            </div>
          </template>
          <template v-else>
            <div
              v-for="plugin in pluginsWithConfig"
              :key="plugin.id"
              class="settings-nav-item settings-nav-item--plugin"
              :class="{ active: activePluginId === plugin.id }"
              @click="selectPlugin(plugin.id)"
            >
              {{ plugin.name }}
            </div>
          </template>
        </div>
      </nav>

      <div class="settings-content">
        <div v-show="activeSection === 'plugins'" class="settings-panel">
          <div v-if="pluginsWithConfig.length === 0" class="settings-empty">
            <h2 class="settings-panel-title">插件配置</h2>
            <p class="settings-panel-desc">
              根据已加载插件的 config 配置项动态生成，配置保存至 ~/.hapray-gui/config.json。
            </p>
            <p class="settings-empty-text">暂无插件配置项，或插件尚未加载。</p>
            <button
              type="button"
              class="settings-btn-secondary"
              :disabled="loading"
              @click="reloadPlugins"
            >
              {{ loading ? "加载中..." : "重新加载插件" }}
            </button>
          </div>

          <template v-else-if="activePlugin">
            <div class="settings-panel-header">
              <h2 class="settings-panel-title">{{ activePlugin.name }}</h2>
              <p v-if="activePlugin.config?.description" class="settings-panel-desc">
                {{ activePlugin.config.description }}
              </p>
            </div>
            <form @submit.prevent="saveConfig" class="settings-form">
              <div
                v-for="[key, item] in configItemEntries"
                :key="key"
                class="settings-form-row"
                :class="{ 'settings-form-row--checkbox': item.type === 'bool' }"
              >
                <label class="settings-form-label">
                  <span v-if="item.required" class="settings-form-required">*</span>
                  {{ item.label }}
                </label>
                <div class="settings-form-control">
                  <input
                    v-if="item.type === 'str'"
                    v-model="formData[activePlugin.id]![key]"
                    type="text"
                    class="settings-input"
                    :placeholder="item.help"
                  />
                  <input
                    v-else-if="item.type === 'int'"
                    v-model.number="formData[activePlugin.id]![key]"
                    type="number"
                    class="settings-input"
                  />
                  <label v-else-if="item.type === 'bool'" class="settings-checkbox-wrap">
                    <input
                      v-model="formData[activePlugin.id]![key]"
                      type="checkbox"
                      class="settings-checkbox"
                    />
                    <span class="settings-checkbox-label">{{ item.help || item.label }}</span>
                  </label>
                  <select
                    v-else-if="item.type === 'choice'"
                    v-model="formData[activePlugin.id]![key]"
                    class="settings-input settings-select"
                  >
                    <option
                      v-for="opt in getChoices(item)"
                      :key="String(opt)"
                      :value="opt"
                    >
                      {{ opt }}
                    </option>
                  </select>
                  <p v-else class="settings-unsupported">暂不支持类型: {{ item.type }}</p>
                </div>
                <p v-if="item.help && item.type !== 'bool'" class="settings-form-hint">
                  {{ item.help }}
                </p>
              </div>
              <button
                type="submit"
                class="settings-btn-primary"
                :disabled="saving"
              >
                {{ saving ? "保存中..." : "保存" }}
              </button>
            </form>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue"
import { usePlugins } from "../composables/usePlugins"
import { useConfig } from "../composables/useConfig"
import type { ConfigItemDef } from "../types"

const { plugins, loadPlugins, loading } = usePlugins()
const { config, loadConfig, saveConfig: persistConfig, getPluginConfig } = useConfig()

const activeSection = ref<"plugins">("plugins")
const activePluginId = ref<string | null>(null)
const saving = ref(false)
const formData = ref<Record<string, Record<string, unknown>>>({})

const pluginsWithConfig = computed(() =>
  plugins.value.filter((p) => p.config?.items && Object.keys(p.config.items).length > 0),
)

const activePlugin = computed(() => {
  if (!activePluginId.value) return null
  return pluginsWithConfig.value.find((p) => p.id === activePluginId.value) ?? null
})

/** 按 plugin.json 中定义的顺序排列的 [key, item] 数组 */
const configItemEntries = computed<[string, ConfigItemDef][]>(() => {
  const items = activePlugin.value?.config?.items ?? {}
  return Object.entries(items)
})

function selectPlugin(pluginId: string) {
  activePluginId.value = pluginId
}

function getChoices(item: ConfigItemDef): unknown[] {
  if (!item.choices) return []
  if (Array.isArray(item.choices)) return item.choices
  return []
}

function initFormData() {
  const next: Record<string, Record<string, unknown>> = {}
  for (const plugin of pluginsWithConfig.value) {
    next[plugin.id] = {}
    const saved = getPluginConfig(plugin.id)
    for (const [key, item] of Object.entries(plugin.config?.items ?? {})) {
      next[plugin.id][key] = saved[key] ?? item.default ?? (item.type === "bool" ? false : "")
    }
  }
  formData.value = next
}

async function saveConfig() {
  saving.value = true
  try {
    const merged = { ...config.value }
    const pluginsConfig = { ...((merged.plugins as Record<string, Record<string, unknown>>) ?? {}) }
    for (const [pluginId, values] of Object.entries(formData.value)) {
      const existing = pluginsConfig[pluginId] ?? {}
      if (existing.config && typeof existing.config === "object" && !Array.isArray(existing.config)) {
        pluginsConfig[pluginId] = {
          ...existing,
          config: { ...(existing.config as Record<string, unknown>), ...values },
        }
      } else {
        pluginsConfig[pluginId] = { ...existing, ...values }
      }
    }
    merged.plugins = pluginsConfig
    await persistConfig(merged)
  } catch (e) {
    console.error("保存配置失败:", e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadPlugins()
  await loadConfig()
  initFormData()
})

watch(
  pluginsWithConfig,
  (list) => {
    initFormData()
    if (list.length > 0) {
      const valid = activePluginId.value && list.some((p) => p.id === activePluginId.value)
      if (!valid) activePluginId.value = list[0].id
    } else {
      activePluginId.value = null
    }
  },
  { deep: true },
)

async function reloadPlugins() {
  await loadPlugins()
  initFormData()
}
</script>

<style scoped>
.settings-view {
  max-width: 960px;
  margin: 0 auto;
}

.settings-layout {
  display: flex;
  min-height: 400px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--background-base);
}

.settings-nav {
  width: 200px;
  flex-shrink: 0;
  padding: 12px 0;
  border-right: 1px solid var(--border);
  background: var(--sidebar);
}

.settings-nav-section {
  padding: 0 8px;
}

.settings-nav-group {
  padding: 8px 12px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted-foreground);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.settings-nav-item {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--muted-foreground);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.settings-nav-item:hover {
  color: var(--foreground);
  background: var(--border);
}

.settings-nav-item.active {
  color: var(--foreground);
  font-weight: 500;
  background: var(--border);
}

.settings-nav-item--plugin {
  padding-left: 20px;
}

.settings-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

.settings-panel {
  padding: 24px 32px 32px;
}

.settings-panel-header {
  margin-bottom: 24px;
}

.settings-panel-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 4px;
}

.settings-panel-desc {
  font-size: 13px;
  color: var(--muted-foreground);
  margin: 0;
  line-height: 1.5;
}

.settings-empty {
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-empty .settings-panel-desc {
  margin-bottom: 8px;
}

.settings-empty-text {
  font-size: 14px;
  color: var(--muted-foreground);
  margin: 0;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-form-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 16px;
  align-items: flex-start;
}

.settings-form-row--checkbox {
  align-items: center;
}

.settings-form-label {
  font-size: 13px;
  padding-top: 8px;
  line-height: 1.4;
}

.settings-form-required {
  color: #dc2626;
  margin-right: 2px;
}

.settings-form-control {
  min-width: 0;
}

.settings-form-hint {
  grid-column: 2;
  font-size: 12px;
  color: var(--muted-foreground);
  margin: 4px 0 0;
  line-height: 1.4;
}

.settings-input {
  width: 100%;
  max-width: 400px;
  padding: 6px 10px;
  font-size: 13px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background-base);
  color: var(--foreground);
  outline: none;
  transition: border-color 0.15s;
}

.settings-input:focus {
  border-color: var(--muted-foreground);
}

.settings-input::placeholder {
  color: var(--muted-foreground);
  opacity: 0.7;
}

.settings-select {
  cursor: pointer;
  appearance: auto;
}

.settings-checkbox-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
}

.settings-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--foreground);
  cursor: pointer;
}

.settings-checkbox-label {
  color: var(--muted-foreground);
}

.settings-unsupported {
  font-size: 12px;
  color: var(--muted-foreground);
  margin: 0;
}

.settings-btn-primary {
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--background-base);
  background: var(--foreground);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.15s;
  align-self: flex-start;
}

.settings-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.settings-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-btn-secondary {
  padding: 6px 12px;
  font-size: 13px;
  color: var(--foreground);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  align-self: flex-start;
}

.settings-btn-secondary:hover:not(:disabled) {
  background: var(--border);
}

.settings-btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
