<template>
    <!-- 测试步骤导航 -->
    <div class="step-nav">
        <div
v-for="(step, index) in testSteps" :key="index" :class="[
            'step-item',
            {
                active: currentStepIndex === step.id,
            },
        ]" @click="handleStepClick(step.id)">
            <div class="step-header">
                <span class="step-order">STEP {{ step.id }}</span>
                <span class="step-duration">{{ formatDuration(step.count) }}</span>
                <span class="step-duration">{{ formatEnergy(step.count) }}</span>
            </div>
            <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
        </div>
    </div>
    <div class="embed-container">
        <!-- 通过iframe嵌入静态HTML -->
        <iframe :srcdoc="htmlContent" class="html-iframe" frameborder="0" scrolling="auto"></iframe>
    </div>
</template>

<script lang='ts' setup>
import { ref, onMounted } from 'vue';
import { useJsonDataStore } from '../stores/jsonDataStore.ts';
import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';
import flameTemplateHtml from '../../../third-party/report.html?raw';
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData;
const script_start = '<script id="record_data" type="application/json">';
const script_end = atob('PC9zY3JpcHQ+PC9ib2R5PjwvaHRtbD4=');

const testSteps = ref(
    perfData!.steps.map((step, index) => ({
        //从1开始
        id: index + 1,
        step_name: step.step_name,
        count: step.count,
        round: step.round,
        perf_data_path: step.perf_data_path,
    }))
);

const currentStepIndex = ref(0);

// 处理步骤点击事件的方法
const handleStepClick = (stepId: number) => {
    currentStepIndex.value = stepId;
    if (jsonDataStore.flameGraph) {
        htmlContent.value = flameTemplateHtml + script_start + jsonDataStore.flameGraph['step'+stepId] + script_end;
    } else {
        htmlContent.value = flameTemplateHtml + script_start + script_end;
    }
};


// 格式化功耗信息
const formatEnergy = (milliseconds: number) => {
    const energy = calculateEnergyConsumption(milliseconds);
    return `核算功耗（mAs）：${energy}`;
};

// 格式化持续时间的方法
const formatDuration = (milliseconds: number) => {
    return `指令数：${milliseconds}`;
};

// 静态HTML文件路径（放在public目录下）
const htmlContent = ref(flameTemplateHtml + script_start + script_end);
onMounted(() => {
    handleStepClick(1)
})

</script>

<style scoped>
.embed-container {
    width: 100%;
    height: 100vh;
    /* 根据需求设置高度 */
    border: 1px solid #eee;
}

.html-iframe {
    width: 100%;
    height: 100%;
}

/* 步骤导航样式 */
.step-nav {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.step-item {
    background: white;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    transition: transform 0.2s;

    &:hover {
        transform: translateY(-2px);
    }

    &.active {
        border: 2px solid #2196f3;
    }
}

.step-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 0.9em;
}

.step-order {
    color: #2196f3;
    font-weight: bold;
}

.step-duration {
    color: #757575;
}

.step-duration-compare {
    color: #d81b60;
}

.step-name {
    font-weight: 500;
    margin-bottom: 12px;
    white-space: nowrap;
    /* 禁止文本换行 */
    overflow: hidden;
    /* 隐藏超出部分 */
    text-overflow: ellipsis;
    /* 显示省略号 */
}
</style>
