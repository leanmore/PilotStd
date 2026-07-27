# 监控与可观测性

> 最后更新：2026-07-27

## 9 个 Metrics 计数器

所有计数器由 [pilotstd/query/engine/_metrics.py](pilotstd/query/engine/_metrics.py) `QueryMetrics` 类管理，通过 [pilotstd/query/engine/_batch.py](pilotstd/query/engine/_batch.py) `try/finally` 块写入 `query_metrics` 表。

### 计数器详解

#### 1. `matched` — 成功匹配
- **触发**：[`_single.py:114`](pilotstd/query/engine/_single.py#L114) `_step_query_adapters()` 查询结果 `is_found()=True`
- **阈值**：< 50% 需排查
- **排查方向**：检查适配器状态、配额是否耗尽、路由策略是否匹配
- **日志**：`查询 [%s] ✓%s(%s) tried=%s`

#### 2. `quota_exhausted` — 配额耗尽
- **触发**：[`_single.py:101`](pilotstd/query/engine/_single.py#L101) 站点日配额用尽
- **阈值**：> 批次 10% 需扩容
- **排查方向**：检查 `daily_quota` 表当日用量、调整 daily_limit
- **日志**：`%s(%s) 今日配额已用尽，跳过`

#### 3. `site_cooling` — 运行时冷却
- **触发**：[`_single.py:~108`](pilotstd/query/engine/_single.py#L108) 查询前 `get_cooldown_remaining > 0`
- **阈值**：> 批次 20% 需检查冷却配置
- **排查方向**：检查 `adapter_state` 表 `cooldown_until`、调整 `max_requests`
- **日志**：`[RUNTIME_COOLDOWN] 跳过=%s 原因=运行时冷却`

#### 4. `overflow` — 桶溢出
- **触发**：[`_mini_bucket.py:237,252`](pilotstd/query/engine/_mini_bucket.py#L237) 冷却/配额致整桶溢出
- **阈值**：> 批次 30% 需优化分桶策略
- **排查方向**：降低 `_MINI_BUCKET_SIZE`、增加溢出配额
- **日志**：`[MINI_BUCKET] mb=%d 站点=%s 无回退 溢出=%d`

#### 5. `chain_exhausted` — 链耗尽
- **触发**：[`_overflow.py:158`](pilotstd/query/engine/_overflow.py#L158) 溢出链所有站点均不可用
- **阈值**：> 0 即需关注
- **排查方向**：检查所有站点冷却/配额状态、扩大路由链
- **日志**：`查询 [%s] [NG] tried=%s`

#### 6. `csres_meltdown` — CSRES 熔断
- **触发**：[`_csres.py:81-93`](pilotstd/query/engine/_csres.py#L81) 连续 5 次失败
- **阈值**：> 0 即需告警
- **排查方向**：检查 csres 站点可访问性、24h 硬冷却是否触发
- **日志**：`[CSRES_MELTDOWN] 连续失败=%d/%d 已处理=%d 丢弃=%d`

#### 7. `bucket_crash` — 桶崩溃
- **触发**：[`_batch_dispatch.py:273`](pilotstd/query/engine/_batch_dispatch.py#L273) 桶线程异常
- **阈值**：> 0 即需 P1 告警
- **排查方向**：查看完整 traceback 日志、桶内数据完整性
- **日志**：`桶执行异常: %s` + full traceback

#### 8. `parse_failed` — 解析失败
- **触发**：[`_mini_bucket.py:148`](pilotstd/query/engine/_mini_bucket.py#L148) 适配器查询异常
- **阈值**：> 20% 需排查
- **排查方向**：检查适配器网络连通性、API 返回格式变更
- **日志**：`查询 [%s %s-%s] 异常 @%s`

#### 9. `validate_failed` — 校验失败
- **触发**：[`_result_builder.py:133`](pilotstd/scan/parser/_result_builder.py#L133) 解析结果校验不通过
- **阈值**：> 30% 需检查扫描文件命名规范
- **排查方向**：查看 `[VALIDATE_FAILED]` 日志中的 `reasons` 列表
- **日志**：`[VALIDATE_FAILED] code=%r number=%d year=%d reasons=%s`

## query_metrics 表结构 [src: `migrations.py:441-452`]

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `batch_id` | TEXT NOT NULL | 批次 ID，外键→`batch_state.batch_id` |
| `metric_key` | TEXT NOT NULL | 计数器名称（如 `matched`） |
| `metric_value` | INTEGER NOT NULL | 计数值 |
| `recorded_at` | TEXT | 记录时间 |

索引：[src: `migrations.py:449-451`] `idx_query_metrics_batch ON (batch_id, metric_key)`

## Grafana 推荐面板

| 面板名称 | 公式 | 告警阈值 |
|----------|------|----------|
| 命中率 | `matched / (matched + parse_failed + validate_failed + chain_exhausted)` | < 50% |
| 校验失败率 | `validate_failed / (matched + validate_failed)` | > 30% |
| 溢出率 | `overflow / total_items` | > 30% |
| 桶崩溃告警 | `bucket_crash > 0` | P1 告警 |
| CSRES 熔断告警 | `csres_meltdown > 0` | P2 告警 |

## 日志规范

### 级别使用标准

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 详细追踪（缓存命中/未命中、路由细节） | `[RUNTIME_COOLDOWN]`、`[CACHE]` |
| INFO | 正常业务流程 | `查询 [%s] ✓`、`[MINI_BUCKET]` |
| WARNING | 可恢复异常（配额耗尽、冷却、截断） | `[QUOTA]`、`冷却中`、`截断` |
| ERROR | 需人工介入（桶崩溃、CSRES 熔断） | `桶执行异常`、`[CSRES_MELTDOWN]` |

### 结构化字段要求

所有日志行应包含以下可 grep 的结构化前缀：

```
[组件] 关键字段=值 关键字段=值
```

示例：
```
[MINI_BUCKET] mb=3 站点=ahbz 冷却→std_gov
[VALIDATE_FAILED] code='GB/T' number=0 year=2024 reasons=['invalid_number(0)']
[BUCKET_CRASH] affected=50 error=TimeoutException
```

### 敏感信息脱敏

- API Key / Token：日志中替换为 `***`
- 用户 ID：保留用于审计
- 文件路径：仅记录相对路径（相对于 `storage.root_dir`）

## 常见告警处理

| 告警 | 可能原因 | 排查步骤 | 修复方案 |
|------|----------|----------|----------|
| `bucket_crash > 0` | 桶线程发生未预期异常 | 1. 查看完整 traceback 2. 检查桶内数据 3. 重试 | 修复异常根因；确保溢出池写入兜底 |
| `csres_meltdown > 0` | csres 站点连续失败 | 1. `curl http://www.csres.com` 2. 检查24h硬冷却标记 | 等待冷却恢复；或临时从路由链中移除 csres |
| `chain_exhausted` 持续增长 | 所有备选站点不可用 | 1. 逐个检查站点冷却 2. 检查日配额 | 扩大路由链；增加 daily_limit |
| `validate_failed` 突增 | 扫描到非标准格式文件 | 1. 查看 `[VALIDATE_FAILED]` reasons 2. 检查文件名 | 规范文件命名；或扩展解析器正则 |
