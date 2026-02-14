<template>
  <div class="tool-workspace">
    <div v-if="plugin" class="tool-workspace__content">
      <header class="tool-workspace__header">
        <h1 class="tool-workspace__title">{{ toolName }}</h1>
        <p v-if="description" class="tool-workspace__desc">{{ description }}</p>
      </header>

      <section class="tool-workspace__panel">
        <h2 class="tool-workspace__panel-title">参数配置</h2>
        <form class="tool-workspace__form" @submit.prevent="execute">
          <div
            v-for="[key, param] in parameterEntries"
            :key="key"
            class="tool-workspace__field"
            :class="{ 'tool-workspace__field--checkbox': param.type === 'bool' }"
          >
            <label class="tool-workspace__label">
              <span v-if="param.required" class="tool-workspace__required">*</span>
              {{ param.label || key }}
            </label>
            <div class="tool-workspace__control">
              <div
                v-if="(param.type === 'str' || param.type === 'file' || param.type === 'dir') && !param.nargs"
                class="tool-workspace__path-input-wrap"
              >
                <input
                  v-model="formData[key]"
                  type="text"
                  class="tool-workspace__input"
                  :placeholder="param.help"
                />
                <button
                  v-if="(param.type === 'file' || param.type === 'dir') && hasTauri"
                  type="button"
                  class="tool-workspace__browse-btn"
                  @click="browsePath(key, param.type)"
                >
                  浏览
                </button>
              </div>
              <div
                v-else-if="(param.type === 'str' || param.type === 'file' || param.type === 'dir') && param.nargs"
                class="tool-workspace__nargs-wrap"
              >
                <div class="tool-workspace__nargs-input-row">
                  <input
                    v-model="nargsInputTemp[key]"
                    type="text"
                    class="tool-workspace__input"
                    :placeholder="param.help"
                    @keydown.enter.prevent="addNargsItem(key, param)"
                  />
                  <button
                    v-if="(param.type === 'file' || param.type === 'dir') && hasTauri"
                    type="button"
                    class="tool-workspace__browse-btn"
                    @click="browsePathForNargs(key, param.type)"
                  >
                    浏览
                  </button>
                  <button type="button" class="tool-workspace__add-btn" @click="addNargsItem(key, param)">
                    添加
                  </button>
                </div>
                <ul v-if="getNargsItems(key).length > 0" class="tool-workspace__nargs-list">
                  <li
                    v-for="(item, idx) in getNargsItems(key)"
                    :key="`${key}-${idx}`"
                    class="tool-workspace__nargs-item"
                  >
                    <span class="tool-workspace__nargs-item-text">{{ item }}</span>
                    <button type="button" class="tool-workspace__nargs-remove" @click="removeNargsItem(key, idx)">
                      删除
                    </button>
                  </li>
                </ul>
              </div>
              <input
                v-else-if="param.type === 'int' && !param.nargs"
                v-model.number="formData[key]"
                type="number"
                class="tool-workspace__input"
              />
              <div v-else-if="param.type === 'int' && param.nargs" class="tool-workspace__nargs-wrap">
                <div class="tool-workspace__nargs-input-row">
                  <input
                    v-model.number="nargsInputTemp[key]"
                    type="number"
                    class="tool-workspace__input"
                    :placeholder="param.help"
                    @keydown.enter.prevent="addNargsItem(key, param)"
                  />
                  <button type="button" class="tool-workspace__add-btn" @click="addNargsItem(key, param)">
                    添加
                  </button>
                </div>
                <ul v-if="getNargsItems(key).length > 0" class="tool-workspace__nargs-list">
                  <li
                    v-for="(item, idx) in getNargsItems(key)"
                    :key="`${key}-${idx}`"
                    class="tool-workspace__nargs-item"
                  >
                    <span class="tool-workspace__nargs-item-text">{{ item }}</span>
                    <button type="button" class="tool-workspace__nargs-remove" @click="removeNargsItem(key, idx)">
                      删除
                    </button>
                  </li>
                </ul>
              </div>
              <label v-else-if="param.type === 'bool'" class="tool-workspace__checkbox-wrap">
                <input v-model="formData[key]" type="checkbox" class="tool-workspace__checkbox" />
                <span class="tool-workspace__checkbox-label">{{ param.help }}</span>
              </label>
              <select
                v-else-if="param.type === 'choice' && !isChoiceMulti(param)"
                v-model="formData[key]"
                class="tool-workspace__input tool-workspace__select"
              >
                <option value="">请选择</option>
                <option v-if="loadingChoicesKeys.has(key)" value="" disabled>加载中...</option>
                <option v-for="opt in getChoices(param, key)" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <div
                v-else-if="param.type === 'choice' && isChoiceMulti(param)"
                class="tool-workspace__choice-multi-wrap"
              >
                <div class="tool-workspace__nargs-input-row">
                  <select
                    v-model="choiceMultiTemp[key]"
                    class="tool-workspace__input tool-workspace__select"
                  >
                    <option value="">请选择</option>
                    <option v-if="loadingChoicesKeys.has(key)" value="" disabled>加载中...</option>
                    <option v-for="opt in getChoices(param, key)" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <button type="button" class="tool-workspace__add-btn" @click="addChoiceMultiItem(key)">
                    添加
                  </button>
                </div>
                <ul v-if="getChoiceMultiItems(key).length > 0" class="tool-workspace__nargs-list">
                  <li
                    v-for="(item, idx) in getChoiceMultiItems(key)"
                    :key="`${key}-${idx}`"
                    class="tool-workspace__nargs-item"
                  >
                    <span class="tool-workspace__nargs-item-text">{{ item }}</span>
                    <button type="button" class="tool-workspace__nargs-remove" @click="removeChoiceMultiItem(key, idx)">
                      删除
                    </button>
                  </li>
                </ul>
              </div>
              <div v-else class="tool-workspace__unsupported">暂不支持的类型: {{ param.type }}</div>
            </div>
          </div>

          <div class="tool-workspace__actions">
            <button
              type="submit"
              class="tool-workspace__btn tool-workspace__btn--primary"
              :disabled="executing"
            >
              {{ executing ? "执行中..." : "执行" }}
            </button>
            <button
              type="button"
              class="tool-workspace__btn tool-workspace__btn--secondary"
              @click="resetForm"
            >
              重置
            </button>
          </div>
        </form>
      </section>

      <section v-if="selectedHistoryRecord" class="tool-workspace__panel tool-workspace__output-panel">
        <h2 class="tool-workspace__panel-title">执行记录详情</h2>
        <div class="tool-workspace__history-detail">
          <div v-if="selectedHistoryRecord.command" class="tool-workspace__history-section">
            <h3 class="tool-workspace__history-label">执行命令</h3>
            <pre class="tool-workspace__history-pre">{{ selectedHistoryRecord.command }}</pre>
          </div>
          <div v-if="selectedHistoryRecord.output_path" class="tool-workspace__history-section">
            <h3 class="tool-workspace__history-label">输出路径</h3>
            <p class="tool-workspace__history-path">{{ selectedHistoryRecord.output_path }}</p>
            <button type="button" class="tool-workspace__btn tool-workspace__btn--primary" @click="openPath(selectedHistoryRecord.output_path!)">
              打开输出路径
            </button>
          </div>
          <div v-if="selectedHistoryRecord.result_dir" class="tool-workspace__history-section">
            <h3 class="tool-workspace__history-label">记录目录</h3>
            <button type="button" class="tool-workspace__btn tool-workspace__btn--secondary" @click="openPath(selectedHistoryRecord.result_dir!)">
              打开记录目录
            </button>
          </div>
          <div v-if="selectedHistoryRecord.output" class="tool-workspace__history-section">
            <h3 class="tool-workspace__history-label">执行日志</h3>
            <pre class="tool-workspace__history-pre tool-workspace__output">{{ selectedHistoryRecord.output }}</pre>
          </div>
        </div>
      </section>
      <section v-else-if="output || executing" class="tool-workspace__panel tool-workspace__output-panel">
        <h2 class="tool-workspace__panel-title">执行输出</h2>
        <pre ref="outputPreRef" class="tool-workspace__output">{{ output }}</pre>
      </section>
    </div>
    <div v-else class="tool-workspace__empty">
      请从左侧选择工具
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted, nextTick } from "vue"
import { invoke } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import type { PluginMetadata, ActionConfig, ParameterDef } from "../composables/usePlugins"
import type { ExecutionRecord } from "../composables/useHistory"

const props = defineProps<{
  plugin: PluginMetadata | null
  action: string | null
  selectedHistoryRecord?: ExecutionRecord | null
}>()

const emit = defineEmits<{
  executionFinished: []
}>()

const formData = ref<Record<string, unknown>>({})
const output = ref("")
const outputPreRef = ref<HTMLPreElement | null>(null)
const executing = ref(false)
/** 动态 choices 缓存：paramKey -> string[] */
const dynamicChoicesCache = ref<Record<string, string[]>>({})
/** 正在加载动态 choices 的 paramKey 集合 */
const loadingChoicesKeys = ref<Set<string>>(new Set())
/** nargs 参数输入框的临时值（添加前的输入） */
const nargsInputTemp = ref<Record<string, string | number>>({})
/** choice multi_select 下拉框的当前选中值（添加前） */
const choiceMultiTemp = ref<Record<string, string>>({})

const hasTauri = !!(window as { __TAURI__?: unknown }).__TAURI__

/** tool-output / tool-command 事件取消监听函数 */
let unlistenToolOutput: (() => void) | null = null
let unlistenToolCommand: (() => void) | null = null

/** 待追加的 chunk 缓冲，用于 requestAnimationFrame 批量更新 */
let pendingChunks: string[] = []
let rafScheduled = false

const MAX_OUTPUT_LEN = 100_000

function flushOutput() {
  if (pendingChunks.length === 0) return
  const text = pendingChunks.join("")
  pendingChunks = []
  output.value += text
  if (output.value.length > MAX_OUTPUT_LEN) {
    output.value = output.value.slice(-MAX_OUTPUT_LEN)
  }
  rafScheduled = false
}

onMounted(async () => {
  if (!hasTauri) return
  try {
    unlistenToolCommand = await listen<string>("tool-command", (event) => {
      if (executing.value) {
        const cmd = typeof event.payload === "string" ? event.payload : String(event.payload)
        output.value = cmd
      }
    })
    unlistenToolOutput = await listen<string>("tool-output", (event) => {
      if (!executing.value) return
      const chunk = typeof event.payload === "string" ? event.payload : String(event.payload)
      pendingChunks.push(chunk)
      if (!rafScheduled) {
        rafScheduled = true
        requestAnimationFrame(() => {
          flushOutput()
        })
      }
    })
  } catch {
    // 非 Tauri 环境或 listen 失败时忽略
  }
})

onUnmounted(() => {
  unlistenToolOutput?.()
  unlistenToolCommand?.()
})

/** 用户是否在底部附近（未手动上滑） */
function isNearBottom(el: HTMLElement): boolean {
  const threshold = 80
  return el.scrollHeight - el.scrollTop - el.clientHeight < threshold
}

// 流式输出时：仅当用户在底部附近才自动滚动，避免上滑时被强制拉回
watch(output, () => {
  nextTick(() => {
    const el = outputPreRef.value
    if (el && isNearBottom(el)) {
      el.scrollTop = el.scrollHeight
    }
  })
})

const actionConfig = computed<ActionConfig | null>(() => {
  if (!props.plugin?.actions || !props.action) return null
  return props.plugin.actions[props.action] ?? null
})

const parameters = computed<Record<string, ParameterDef>>(() => {
  return actionConfig.value?.parameters ?? {}
})

/** 按 plugin.json 中定义的顺序排列的 [key, param] 数组 */
const parameterEntries = computed<[string, ParameterDef][]>(() => {
  return Object.entries(parameters.value)
})

const toolName = computed(() => actionConfig.value?.name ?? props.plugin?.name ?? "")

const description = computed(() => actionConfig.value?.description ?? props.plugin?.description ?? "")

/** choice 多选：multi_select 或 nargs: "+" 等价 */
function isChoiceMulti(param: ParameterDef): boolean {
  return !!(param.multi_select || param.nargs === "+")
}

function getChoices(param: ParameterDef, paramKey: string): string[] {
  const c = param.choices
  if (Array.isArray(c)) return c.map(String)
  if (typeof c === "object" && c && "length" in c) return (c as string[]).map(String)
  if (typeof c === "string") return dynamicChoicesCache.value[paramKey] ?? []
  return []
}

async function openPath(path: string) {
  if (!hasTauri) return
  try {
    await invoke("open_path_command", { path })
  } catch {
    // 打开失败时静默处理
  }
}

async function browsePath(paramKey: string, paramType: string) {
  if (!hasTauri) return
  try {
    const { open } = await import("@tauri-apps/plugin-dialog")
    const selected = await open({
      directory: paramType === "dir",
      multiple: false,
      defaultPath: (formData.value[paramKey] as string) || undefined,
    })
    if (selected) {
      formData.value = { ...formData.value, [paramKey]: typeof selected === "string" ? selected : selected?.[0] ?? "" }
    }
  } catch {
    // 用户取消或出错时忽略
  }
}

async function loadDynamicChoices(paramKey: string, choicesFunc: string) {
  const hasTauri = !!(window as { __TAURI__?: unknown }).__TAURI__
  if (!hasTauri) return
  loadingChoicesKeys.value = new Set([...loadingChoicesKeys.value, paramKey])
  try {
    const list = await invoke<string[]>("get_dynamic_choices_command", { choicesFunc })
    dynamicChoicesCache.value = { ...dynamicChoicesCache.value, [paramKey]: list }
  } catch {
    dynamicChoicesCache.value = { ...dynamicChoicesCache.value, [paramKey]: [] }
  } finally {
    loadingChoicesKeys.value = new Set([...loadingChoicesKeys.value].filter((k) => k !== paramKey))
  }
}

function initForm() {
  const data: Record<string, unknown> = {}
  const temp: Record<string, string | number> = {}
  const choiceTemp: Record<string, string> = {}
  for (const [key, param] of Object.entries(parameters.value)) {
    if (param.type === "choice" && isChoiceMulti(param)) {
      data[key] = Array.isArray(param.default)
        ? (param.default as string[]).map(String)
        : param.default != null
          ? [String(param.default)]
          : []
    } else if (param.nargs) {
      data[key] = Array.isArray(param.default)
        ? [...(param.default as (string | number)[])]
        : param.default != null
          ? [param.default]
          : []
    } else {
      data[key] = param.default ?? (param.type === "bool" ? false : param.type === "int" ? 0 : "")
    }
    if (param.nargs) {
      temp[key] = param.type === "int" ? 0 : ""
    }
    if (param.type === "choice" && isChoiceMulti(param)) {
      choiceTemp[key] = ""
    }
  }
  formData.value = data
  nargsInputTemp.value = temp
  choiceMultiTemp.value = choiceTemp
}

function getChoiceMultiItems(paramKey: string): string[] {
  const val = formData.value[paramKey]
  return Array.isArray(val) ? val.map(String) : []
}

function addChoiceMultiItem(paramKey: string) {
  const selected = choiceMultiTemp.value[paramKey]
  if (!selected) return
  const arr = getChoiceMultiItems(paramKey)
  if (arr.includes(selected)) return
  formData.value = { ...formData.value, [paramKey]: [...arr, selected] }
}

function removeChoiceMultiItem(paramKey: string, index: number) {
  const arr = getChoiceMultiItems(paramKey)
  formData.value = {
    ...formData.value,
    [paramKey]: arr.filter((_, i) => i !== index),
  }
}

function getNargsItems(paramKey: string): (string | number)[] {
  const val = formData.value[paramKey]
  return Array.isArray(val) ? val : []
}

function addNargsItem(paramKey: string, param: ParameterDef) {
  const temp = nargsInputTemp.value[paramKey]
  const val = temp != null && temp !== "" ? (param.type === "int" ? Number(temp) : String(temp).trim()) : null
  if (val == null || (typeof val === "string" && !val)) return
  const arr = getNargsItems(paramKey)
  formData.value = { ...formData.value, [paramKey]: [...arr, val] }
  nargsInputTemp.value = { ...nargsInputTemp.value, [paramKey]: param.type === "int" ? 0 : "" }
}

function removeNargsItem(paramKey: string, index: number) {
  const arr = getNargsItems(paramKey)
  formData.value = {
    ...formData.value,
    [paramKey]: arr.filter((_, i) => i !== index),
  }
}

async function browsePathForNargs(paramKey: string, paramType: string) {
  if (!hasTauri) return
  try {
    const { open } = await import("@tauri-apps/plugin-dialog")
    const selected = await open({
      directory: paramType === "dir",
      multiple: false,
      defaultPath: (nargsInputTemp.value[paramKey] as string) || undefined,
    })
    if (selected) {
      const path = typeof selected === "string" ? selected : selected?.[0] ?? ""
      if (path) nargsInputTemp.value = { ...nargsInputTemp.value, [paramKey]: path }
    }
  } catch {
    // 用户取消或出错时忽略
  }
}

function resetForm() {
  initForm()
  output.value = ""
}

watch(
  () => [props.plugin?.id, props.action] as const,
  () => {
    initForm()
    output.value = ""
    dynamicChoicesCache.value = {}
    loadingChoicesKeys.value = new Set()
  },
  { immediate: true }
)

// 单独监听参数变化，确保动态 choices（如 get_installed_apps）在参数就绪时加载
watch(
  parameterEntries,
  (entries) => {
    for (const [key, param] of entries) {
      if (param.type === "choice" && typeof param.choices === "string") {
        loadDynamicChoices(key, param.choices)
      }
    }
  },
  { immediate: true }
)

function parseNargsValue(value: unknown, param: ParameterDef): unknown {
  if (!param.nargs) return value
  if (Array.isArray(value)) return value
  return []
}

function buildParamsForExecute(): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  for (const [key, param] of Object.entries(parameters.value)) {
    const raw = formData.value[key]
    if (param.nargs) {
      params[key] = parseNargsValue(raw, param)
    } else {
      params[key] = raw
    }
  }
  return params
}

async function execute() {
  if (!props.plugin || !props.action) return

  const hasTauri = !!(window as { __TAURI__?: unknown }).__TAURI__
  if (!hasTauri) {
    output.value = "请在 Tauri 环境中运行以执行工具"
    return
  }

  executing.value = true
  output.value = ""

  try {
    const result = await invoke<{ success: boolean; message: string; output: string }>("execute_tool_command", {
      payload: {
        plugin_id: props.plugin.id,
        action: props.action,
        params: buildParamsForExecute(),
      },
    })
    // 流式输出已在 listen 中追加，此处仅追加最终状态消息
    if (result.output) {
      output.value += result.output
    }
    if (result.message) {
      output.value += (output.value ? "\n" : "") + result.message
    }
  } catch (e) {
    output.value += (output.value ? "\n" : "") + `执行失败: ${e}`
  } finally {
    executing.value = false
    emit("executionFinished")
  }
}
</script>
