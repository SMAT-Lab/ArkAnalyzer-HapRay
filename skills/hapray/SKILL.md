---
name: hapray
description: |
  HapRay (ArkAnalyzer-HapRay) 是鸿蒙应用性能分析工具集。Use when analyzing OpenHarmony/HarmonyOS app performance, HAP static analysis, perf testing, symbol recovery, optimization detection (SO/LTO), or when the user mentions HapRay, 鸿蒙性能, 今日头条性能分析.
---

# HapRay - 鸿蒙应用性能分析工具集

HapRay 提供 HAP 静态分析、性能测试、符号恢复、SO 优化检测等能力。项目地址：https://gitcode.com/SMAT/ArkAnalyzer-HapRay

## When to Use

- 鸿蒙/HarmonyOS 应用性能分析
- HAP 包技术栈分析、SO 优化级别检测
- perf 性能数据采集与报告生成
- 符号恢复、缺失符号推断

## 工具与入口

| 工具 | 路径 | 用途 |
|------|------|------|
| opt-detector | opt-detector/optimization_detector | SO 编译优化与 LTO 检测 |
| perf_testing | perf_testing/ | 性能测试、GUI Agent |
| static_analyzer | tools/static_analyzer | HAP 技术栈、perf 场景分析 |
| symbol_recovery | tools/symbol_recovery | 符号恢复与 LLM 分析 |

## opt-detector（SO 优化检测）

本 skill 内置 opt-detector 源码，位于 `opt-detector/optimization_detector/`。

**首次使用前**，Agent 必须执行安装（任选其一）：
```bash
cd <skill_install_dir>/opt-detector/optimization_detector && pip install -e .
# 或
<skill_install_dir>/opt-detector/scripts/setup.sh
```

**CLI**：`opt-detector -i /path/to/binaries -o report.xlsx -f excel json -j 4`

**Python API**：
```python
from optimization_detector import detect_optimization, check_prerequisites
result = detect_optimization("/path/to/so/dir", output="report.xlsx", output_format=["excel", "json"], jobs=4, return_dict=True)
```

## 安装本仓库 Skill

```bash
npx skills add https://gitcode.com/SMAT/ArkAnalyzer-HapRay -g -y
```
