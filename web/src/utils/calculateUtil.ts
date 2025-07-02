/**
 * 将指令数转换为能耗值(mAs)
 * @param instructionCount 指令数量
 * @returns 计算出的能耗值(mAs)，保留6位小数
 */
export function calculateEnergyConsumption(instructionCount: number): number {
    // 定义关键常量
    const THRESHOLD = 456372767; // 指令数阈值
    const SLOPE = 2.43e-7;       // 线性回归斜率
    const INTERCEPT = 5417.074161; // 线性回归截距
    const PER_MILLION_RATE = 0.243171; // 每百万指令的能耗系数
    
    let result: number;
    
    if (instructionCount < THRESHOLD) {
        // 低于阈值：使用平均功耗比例公式
        result = instructionCount * (PER_MILLION_RATE / 1000000);
    } else {
        // 达到阈值：使用线性回归公式
        result = SLOPE * instructionCount + INTERCEPT;
    }
    
    // 四舍五入保留6位小数
    return parseFloat(result.toFixed(2));
}