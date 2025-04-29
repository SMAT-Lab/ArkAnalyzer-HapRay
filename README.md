# ArkAnalyzer-HapRay
Code-oriented Performance Analysis for OpenHarmony Apps

## build

```
npm install
npm run build
```

----

## Mac M系列芯片下使用指导

```bash
# 初始化环境，仅需要执行一次
./setup_darwin_arm64.sh

# 每次运行测试前执行
source HapRayVenv/bin/activate
cd perf_testing
python main.py
```
