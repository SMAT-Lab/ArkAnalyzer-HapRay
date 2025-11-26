# perf.db 查询性能优化总结

## 优化前 vs 优化后

### 性能对比

| 模式 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 标准模式 | ~2-3秒 | ~0.7秒 | **3-4倍** |
| 快速模式 | N/A | ~0.16秒 | **12-18倍** |

## 优化措施

### 1. 批量查询优化

**问题**: 原来对每个调用链都执行一次查询，导致 N+1 查询问题

**优化**:
- 批量获取所有调用链的数据
- 批量获取文件路径和符号名称
- 减少数据库往返次数

```python
# 优化前：逐个查询
for cc_id in callchain_ids:
    cursor.execute("SELECT ... WHERE callchain_id = ?", (cc_id,))

# 优化后：批量查询
cursor.execute("SELECT ... WHERE callchain_id IN (?, ?, ...)", callchain_ids)
```

### 2. 精确匹配优先

**问题**: 使用 `LIKE '%...%'` 查询很慢

**优化**:
- 先精确匹配 `data_dict` 表
- 使用 `name` 字段直接查询 `perf_callchain`
- 避免 JOIN `data_dict` 表

```python
# 优化前
WHERE dd.data LIKE '%0x4bc171c%'

# 优化后
WHERE data = 'entry.hap+0x4bc171c' OR data = 'entry.hap@0x4bc171c'
```

### 3. SQLite 性能参数

**优化**:
- 启用 WAL 模式：`PRAGMA journal_mode=WAL`
- 增加缓存大小：`PRAGMA cache_size=10000`
- 调整同步模式：`PRAGMA synchronous=NORMAL`

### 4. 减少数据获取

**优化**:
- 限制查询结果数量（LIMIT）
- 只查询必要的字段
- 快速模式跳过调用链上下文

### 5. 查询范围限制

**优化**:
- 只查询前 3 个调用链的上下文
- 只查询前 5-10 个调用链的 SO 文件
- 添加 `LIMIT` 子句

## 使用建议

### 快速模式（推荐用于批量查询）

```bash
# 快速查询，跳过调用链上下文
python3 query_hap_address_from_perfdb.py perf.db entry.hap+0x4bc171c --quick
```

**适用场景**:
- 批量查询多个地址
- 只需要基本信息（地址、SO 文件）
- 不需要调用链上下文

### 标准模式（详细分析）

```bash
# 标准查询，包含调用链上下文
python3 query_hap_address_from_perfdb.py perf.db entry.hap+0x4bc171c
```

**适用场景**:
- 需要查看完整的调用链
- 需要分析调用关系
- 需要查找相关的 SO 文件

### 详细模式（调试用）

```bash
# 详细模式，显示所有信息
python3 query_hap_address_from_perfdb.py perf.db entry.hap+0x4bc171c --verbose
```

## 性能测试结果

### 测试环境
- perf.db 大小: ~200MB
- perf_callchain 记录数: 数百万条
- file_id=224 (entry.hap) 记录数: 246,028 条

### 测试结果

```
快速模式: 0.159秒
标准模式: 0.683秒
详细模式: ~1.2秒
```

## 进一步优化建议

### 1. 添加索引（如果可能）

```sql
CREATE INDEX idx_perf_callchain_file_name ON perf_callchain(file_id, name);
CREATE INDEX idx_perf_callchain_callchain ON perf_callchain(callchain_id);
```

### 2. 查询结果缓存

对于重复查询的地址，可以添加缓存机制。

### 3. 并行查询

对于批量查询，可以使用多线程并行处理。

## 代码变更

主要优化点：
1. ✅ 批量查询调用链数据
2. ✅ 精确匹配 data_dict
3. ✅ SQLite 性能参数设置
4. ✅ 快速模式（跳过调用链上下文）
5. ✅ 减少不必要的数据获取
6. ✅ 限制查询范围

## 使用示例

```bash
# 快速查询（推荐）
time python3 query_hap_address_from_perfdb.py perf.db entry.hap+0x4bc171c --quick
# real    0m0.159s

# 标准查询
time python3 query_hap_address_from_perfdb.py perf.db entry.hap+0x4bc171c
# real    0m0.683s

# 详细查询
time python3 query_hap_address_from_perfdb.py perf.db entry.hap+0x4bc171c --verbose
# real    0m1.200s
```

