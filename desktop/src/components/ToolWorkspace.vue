<template>
  <div class="tool-workspace">
    <div v-if="plugin" class="tool-workspace__content">
      <header class="tool-workspace__header">
        <h1 class="tool-workspace__title">{{ toolName }}</h1>
        <p v-if="description" class="tool-workspace__desc">{{ description }}</p>
      </header>

      <div class="tool-workspace__main">
        <section class="tool-workspace__panel tool-workspace__params-panel">
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
                :disabled="isCurrentToolExecuting"
              >
                {{ isCurrentToolExecuting ? "执行中..." : "执行" }}
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

        <template v-if="outputPanelVisible">
          <div class="tool-workspace__output-wrapper">
            <div
              class="tool-workspace__output-resize-handle"
              role="separator"
              aria-label="调整输出面板高度"
              @mousedown="onOutputResizeStart"
            />
            <section
              class="tool-workspace__panel tool-workspace__output-panel"
              :style="{ height: `${outputPanelHeight}px` }"
            >
              <div class="tool-workspace__output-panel-header">
                <h2 class="tool-workspace__panel-title">执行输出</h2>
                <button
                  type="button"
                  class="tool-workspace__output-toggle"
                  aria-label="隐藏输出面板"
                  @click="outputPanelVisible = false"
                >
                  <svg class="size-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 12l6-6 6 6" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                </button>
              </div>
              <pre ref="outputPreRef" class="tool-workspace__output">{{ displayOutput }}</pre>
            </section>
          </div>
        </template>
        <div v-else class="tool-workspace__output-collapsed">
          <button
            type="button"
            class="tool-workspace__output-expand-btn"
            @click="outputPanelVisible = true"
          >
            <svg class="size-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 8l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            显示执行输出
          </button>
        </div>
      </div>
    </div>
    <div v-else class="tool-workspace__empty">
      请从左侧选择工具
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted, onBeforeUnmount, nextTick } from "vue"
import { invoke } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import type { PluginMetadata, ActionConfig, ParameterDef } from "../types"
import { isTauriEnv } from "../utils/tauri"
import { useToolStateCache, toolKey } from "../composables/useToolStateCache"

const hasTauri = isTauriEnv()
const { save: saveToolState, load: loadToolState, updateOutput: updateOutputInCache } = useToolStateCache()

const props = defineProps<{
  plugin: PluginMetadata | null
  action: string | null
  /** 命令行传入的初始参数，用于自动执行 */
  initialParams?: Record<string, unknown> | null
}>()

const emit = defineEmits<{
  executionFinished: []
}>()

const formData = ref<Record<string, unknown>>({})
const output = ref("")
const outputPreRef = ref<HTMLPreElement | null>(null)

/** 正在执行中的工具 key 集合，切换菜单后仍保持，用于按钮去使能 */
const executingToolKeys = ref<Set<string>>(new Set())

/** 各工具正在执行时的输出缓冲，key 为 toolKey */
const executingOutputBuffers = ref<Record<string, string>>({})

/** 输出面板是否显示 */
const outputPanelVisible = ref(true)
/** 输出面板高度（px） */
const outputPanelHeight = ref(260)
const OUTPUT_PANEL_MIN = 120
const OUTPUT_PANEL_MAX = 600

function onOutputResizeStart(e: MouseEvent) {
  if (e.buttons !== 1) return
  e.preventDefault()

  const onMove = (move: MouseEvent) => {
    outputPanelHeight.value = Math.min(
      OUTPUT_PANEL_MAX,
      Math.max(OUTPUT_PANEL_MIN, outputPanelHeight.value - move.movementY)
    )
  }

  const onUp = () => {
    document.removeEventListener("mousemove", onMove)
    document.removeEventListener("mouseup", onUp)
    document.body.style.cursor = ""
    document.body.style.userSelect = ""
  }

  document.body.style.cursor = "row-resize"
  document.body.style.userSelect = "none"
  document.addEventListener("mousemove", onMove)
  document.addEventListener("mouseup", onUp)
}
/** 动态 choices 缓存：paramKey -> string[] */
const dynamicChoicesCache = ref<Record<string, string[]>>({})
/** 正在加载动态 choices 的 paramKey 集合 */
const loadingChoicesKeys = ref<Set<string>>(new Set())
/** nargs 参数输入框的临时值（添加前的输入） */
const nargsInputTemp = ref<Record<string, string | number>>({})
/** choice multi_select 下拉框的当前选中值（添加前） */
const choiceMultiTemp = ref<Record<string, string>>({})

/** tool-output / tool-command 事件取消监听函数 */
let unlistenToolOutput: (() => void) | null = null
let unlistenToolCommand: (() => void) | null = null

/** 各工具的待追加 chunk 缓冲，用于 requestAnimationFrame 批量更新 */
const pendingChunksByTool = ref<Record<string, string[]>>({})
let rafScheduled = false

const MAX_OUTPUT_LEN = 100_000

function flushOutput() {
  const byTool = pendingChunksByTool.value
  const newPending = { ...byTool }
  const newBuffers = { ...executingOutputBuffers.value }
  let hasWork = false
  for (const [key, chunks] of Object.entries(byTool)) {
    if (chunks.length > 0) {
      hasWork = true
      const text = chunks.join("")
      newPending[key] = []
      const cur = newBuffers[key] ?? ""
      let next = cur + text
      if (next.length > MAX_OUTPUT_LEN) {
        next = next.slice(-MAX_OUTPUT_LEN)
      }
      newBuffers[key] = next
    }
  }
  if (!hasWork) {
    rafScheduled = false
    return
  }
  pendingChunksByTool.value = newPending
  executingOutputBuffers.value = newBuffers
  rafScheduled = false
}

function pushPendingChunk(toolKey: string, chunk: string) {
  const cur = pendingChunksByTool.value[toolKey] ?? []
  pendingChunksByTool.value = { ...pendingChunksByTool.value, [toolKey]: [...cur, chunk] }
}

onMounted(async () => {
  if (!hasTauri) return
  try {
    unlistenToolCommand = await listen<{ tool_key: string; command: string } | string>("tool-command", (event) => {
      const p = event.payload
      const toolKey = typeof p === "object" && p && "tool_key" in p ? p.tool_key : null
      const cmd = typeof p === "object" && p && "command" in p ? p.command : typeof p === "string" ? p : ""
      if (toolKey && cmd) {
        executingOutputBuffers.value = { ...executingOutputBuffers.value, [toolKey]: cmd }
      }
    })
    unlistenToolOutput = await listen<{ tool_key: string; chunk: string } | string>("tool-output", (event) => {
      const p = event.payload
      const toolKey = typeof p === "object" && p && "tool_key" in p ? p.tool_key : null
      const chunk = typeof p === "object" && p && "chunk" in p ? p.chunk : typeof p === "string" ? p : ""
      if (!toolKey || !chunk) return
      pushPendingChunk(toolKey, chunk)
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

onBeforeUnmount(() => {
  if (props.plugin?.id && props.action) {
    flushOutput()
    const key = toolKey(props.plugin.id, props.action)
    const outputToSave = executingOutputBuffers.value[key] ?? output.value
    saveToolState(key, {
      formData: formData.value,
      output: outputToSave,
      nargsInputTemp: nargsInputTemp.value,
      choiceMultiTemp: choiceMultiTemp.value,
      dynamicChoicesCache: dynamicChoicesCache.value,
      outputPanelVisible: outputPanelVisible.value,
    })
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

/** 当前工具 key */
const currentToolKey = computed(() =>
  props.plugin?.id && props.action ? toolKey(props.plugin.id, props.action) : null
)

/** 当前工具是否正在执行（切换回来时按钮仍应去使能） */
const isCurrentToolExecuting = computed(() =>
  !!currentToolKey.value && executingToolKeys.value.has(currentToolKey.value)
)

/** 展示用的 output：若当前工具有执行中的缓冲则显示缓冲，否则显示缓存的 output */
const displayOutput = computed(() => {
  const key = currentToolKey.value
  if (key && key in executingOutputBuffers.value) {
    return executingOutputBuffers.value[key]
  }
  return output.value
})

// 流式输出时：仅当用户在底部附近才自动滚动，避免上滑时被强制拉回
watch(displayOutput, () => {
  nextTick(() => {
    const el = outputPreRef.value
    if (el && isNearBottom(el)) {
      el.scrollTop = el.scrollHeight
    }
  })
})

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
  (newVal, oldVal) => {
    const [newPluginId, newAction] = newVal ?? [undefined, undefined]
    const [oldPluginId, oldAction] = (oldVal ?? [undefined, undefined]) as readonly [string | undefined, string | null]
    // 保存当前工具状态到缓存
    if (oldPluginId && oldAction) {
      flushOutput() // 先刷新待处理的 output chunks，确保保存完整
      const oldKey = toolKey(oldPluginId, oldAction)
      const outputToSave = executingOutputBuffers.value[oldKey] ?? output.value
      saveToolState(oldKey, {
        formData: formData.value,
        output: outputToSave,
        nargsInputTemp: nargsInputTemp.value,
        choiceMultiTemp: choiceMultiTemp.value,
        dynamicChoicesCache: dynamicChoicesCache.value,
        outputPanelVisible: outputPanelVisible.value,
      })
    }

    // 加载或初始化新工具状态
    if (newPluginId && newAction) {
      const newKey = toolKey(newPluginId, newAction)
      const cached = loadToolState(newKey)

      // 有 initialParams 时优先使用（CLI 传入），不恢复缓存
      if (props.initialParams && Object.keys(props.initialParams).length > 0) {
        initForm()
        output.value = ""
        dynamicChoicesCache.value = {}
        loadingChoicesKeys.value = new Set()
      } else if (cached) {
        // 从缓存恢复，与当前参数结构合并
        initForm()
        for (const [key, val] of Object.entries(cached.formData)) {
          if (key in parameters.value) {
            formData.value = { ...formData.value, [key]: val }
          }
        }
        for (const [key, val] of Object.entries(cached.nargsInputTemp)) {
          if (key in parameters.value) {
            nargsInputTemp.value = { ...nargsInputTemp.value, [key]: val }
          }
        }
        for (const [key, val] of Object.entries(cached.choiceMultiTemp)) {
          if (key in parameters.value) {
            choiceMultiTemp.value = { ...choiceMultiTemp.value, [key]: val }
          }
        }
        output.value = cached.output
        dynamicChoicesCache.value = { ...cached.dynamicChoicesCache }
        outputPanelVisible.value = cached.outputPanelVisible
        loadingChoicesKeys.value = new Set()
      } else {
        initForm()
        output.value = ""
        dynamicChoicesCache.value = {}
        loadingChoicesKeys.value = new Set()
      }
    }
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

// 命令行传入的 initialParams：应用后自动执行
watch(
  () => props.initialParams,
  (params) => {
    if (!params || !props.plugin || !props.action || Object.keys(params).length === 0) return
    nextTick(() => {
      for (const [key, param] of Object.entries(parameters.value)) {
        if (key in params) {
          const val = params[key]
          if (param.nargs) {
            formData.value = {
              ...formData.value,
              [key]: Array.isArray(val) ? val : val != null ? [val] : [],
            }
          } else {
            formData.value = { ...formData.value, [key]: val }
          }
        }
      }
      execute()
    })
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
  if (!hasTauri) {
    output.value = "请在 Tauri 环境中运行以执行工具"
    return
  }

  const key = toolKey(props.plugin.id, props.action)
  executingToolKeys.value = new Set([...executingToolKeys.value, key])
  executingOutputBuffers.value = { ...executingOutputBuffers.value, [key]: "" }
  output.value = ""

  try {
    const result = await invoke<{ success: boolean; message: string; output: string }>("execute_tool_command", {
      payload: {
        plugin_id: props.plugin.id,
        action: props.action,
        params: buildParamsForExecute(),
      },
    })
    flushOutput()
    const buf = executingOutputBuffers.value[key] ?? ""
    let finalOutput = buf
    if (result.output) {
      finalOutput += result.output
    }
    if (result.message) {
      finalOutput += (finalOutput ? "\n" : "") + result.message
    }
    executingOutputBuffers.value = { ...executingOutputBuffers.value, [key]: finalOutput }
  } catch (e) {
    flushOutput()
    const buf = executingOutputBuffers.value[key] ?? ""
    const finalOutput = buf + (buf ? "\n" : "") + `执行失败: ${e}`
    executingOutputBuffers.value = { ...executingOutputBuffers.value, [key]: finalOutput }
  } finally {
    executingToolKeys.value = new Set([...executingToolKeys.value].filter((k) => k !== key))
    const finalOutput = executingOutputBuffers.value[key] ?? ""
    if (key === currentToolKey.value) {
      output.value = finalOutput
    } else {
      updateOutputInCache(key, finalOutput)
    }
    const rest = { ...executingOutputBuffers.value }
    delete rest[key]
    executingOutputBuffers.value = rest
    emit("executionFinished")
  }
}
</script>
