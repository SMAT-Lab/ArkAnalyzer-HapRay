# DFX可编程方案XVM跟踪函数调用次数

## 配置XVM跟踪函数
**函数配置规则**：[PATH:name | PATH:OFFSET]，XVM不成熟，仅支持配置export的符号，配置偏移地址时跟踪无结果。PATH为应用加载so地址，可以从cat /proc/{pid}/maps中获取
```yaml
xvm:
  symbols:
    - /data/storage/el1/bundle/libs/arm64/libtest_suite.so:Add
    - /data/storage/el1/bundle/libs/arm64/libtest_suite.so:RegisterTest_suiteModule
```
**调用次数报告路径**：/hiperf/step{i}/xvmtrace_result.txt