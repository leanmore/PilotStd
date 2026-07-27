# 查询引擎完整文档

> 最后更新：2026-07-27

## 路由策略

### ADAPTER_TYPE_MAP 完整定义 [src: `pilotstd/query/search_strategy.py:252-294`]

标准代号 → 适配器路由链的映射表。`_resolve_base_route()` [src: `pilotstd/query/engine/_routing.py:35`] 的 7 层决策树以此为核心。

| 类型 | 路由链 | 权重 |
|------|--------|------|
| `gb` | `[ahbz, std_gov, njbz365, csres]` | 30:40:25:5 |
| `industry` | `[cssn, miit, hbba, njbz365, csres]` | 无权重(轮询) |
| `db` | `[dbba, ahbz, std_gov, csres]` | 无权重 |
| `iso/iec/ieee/astm/asme/api` | `[iso_gov, ahbz, std_gov, csres]` | 无权重 |
| `foreign` | `[njbz365, ahbz, ...]` | 无权重 |
| `group` | `[ttbz, ahbz, ...]` | 无权重 |
| `env` ~ `cultural` | 各专业适配器 + `[ahbz, std_gov]` 兜底 | 无权重 |

### 路由决策树

```
_resolve_base_route(logical_code)      [_routing.py:35-77]
  ├─ 1. CODE_ROUTES 硬编码表?          [_constants.py:40-57]
  │   ISO/IEC → [iso_gov, ahbz, njbz365]
  │   DB{11-71}/T → [dbba, ahbz, njbz365]
  │   WW → [ncha, std_gov]
  ├─ 2. re ^DB\d{2,4}(?:/T)?$          [_routing.py:39]
  │   → [dbba, njbz365]
  ├─ 3. classify_std_code()             [std_utils.py:15-61]
  │   → ADAPTER_TYPE_MAP[type]
  ├─ 4. FOREIGN_CODE_SET?               [_routing.py:61-72]
  │   → [ahbz, njbz365]
  ├─ 5. len ≤ 4?                        [_routing.py:73]
  │   → [hbba, njbz365, csres]
  └─ 6. 兜底                             [_routing.py:75]
      → [ahbz, njbz365]
```

优先级链最终通过 `_get_priority()` [src: `_routing.py:105`] 叠加用户 `site_order` + `_filter_available_adapters()`（冷却过滤）生成。

### 渐进式搜索 [src: `pilotstd/query/adapters/base.py:115-172`]

每个适配器的 `query_with_strategy()` 内部执行 5 步渐进搜索：

```
完整号直搜 → 空格回退 → 去前缀 → 去年份 → build_code_variants 补充变体
```

匹配评分 [src: `pilotstd/query/search_strategy.py:179-185`]：
- `exact` = 100（直接接受）
- `newer` = 80（溢出链重试）
- `older` = 50（溢出链重试）
- `code_only` = 20（溢出链重试）
- `mismatch` = 0（丢弃）

## 分桶策略

### 一级分桶 [src: `pilotstd/query/engine/_batch_dispatch.py:92-105`]

```python
_bucket_items(parsed_list)
  └─ for item in parsed_list:
       key = _routing._bucket_key(item[0])  # 路由链[0] = 主站点
       buckets[key].append((index, item))
```

分桶依据：路由链的第一个站点。**不查询配额**。

### 二级小桶 [src: `pilotstd/query/engine/_mini_bucket.py:44-110`]

```python
_build_mini_buckets(chain, items, weights)
  ├─ 有权重 → 按权重比例分配（如 GB: ahbz 30% → std_gov 40% → njbz365 25% → csres 5%）
  ├─ 无权重 → 轮询分配（chain[(i // 50) % len(chain)]）
  └─ _MINI_BUCKET_SIZE = 50
```

### 执行流程 [src: `_mini_bucket.py:196-275`]

```
_run_mini_bucket_queries(ctx, mini_buckets, chain, adapter_map, quota, rotator)
  for mb in mini_buckets:
    ├─ 错峰 5 秒 (_MINI_BUCKET_STAGGER)
    ├─ 冷却检测 → 回退 / 整桶溢出
    ├─ 配额检测 → quota.get_search_remaining(assigned) < len(mb) → 整桶溢出
    └─ _process_single_query() 逐条执行
```

**关键问题**：配额不足时整桶 50 条溢出，不尝试用剩余配额执行部分条目。

### 溢出回收 [src: `pilotstd/query/engine/_overflow.py:101-193`]

```
_handle_overflow()
  └─ _process_overflow_item(idx, item, chain, state)
       for site in chain[start:]:
         ├─ 冷却检测 → 跳过
         ├─ 溢出配额检测 → 跳过
         └─ _try_overflow_site() → ≥100 分采纳
       → chain_exhausted → status="待确认"
```

## 配额与冷却机制

### SiteRotator [src: `pilotstd/query/rotator.py:40-62`]

```
SiteState:
  max_requests: 200     # 每轮最大请求数
  daily_limit: 800      # 日配额
  cooldown_seconds: 600 # 冷却时长(默认10分钟)
  request_count: 0      # 当前轮次计数
  daily_count: 0        # 当日累计
  cooldown_until: 0.0   # 冷却到期时间戳
  consecutive_errors: 0 # 连续错误计数
```

**状态流转**：
```
[正常] → request_count >= max_requests → [冷却]
[正常] → consecutive_errors >= 3 → [切换URL/进入冷却]
[冷却] → time.now() >= cooldown_until → [恢复: request_count=0, errors=0]
[日终] → daily_date != today → [重置 daily_count]
```

**冷却 jitter** [src: `rotator.py:325-328`]：`_enter_cooldown()` 应用 ±10% 随机抖动，防止多线程同时恢复导致请求风暴。

### DailyQuotaTracker [src: `pilotstd/query/daily_quota.py:82-97`]

- SQLite 持久化，`(site_name, query_date)` 为键
- 默认 500/天，自然日 00:00 重置
- 详情页预留：`csres=30, njbz365=50, hbba=30`

### 配额检查位置汇总

| 阶段 | 位置 | 检查方式 |
|------|------|----------|
| 单条查询 | `_single.py:99` | `quota.get_search_remaining(name) <= 0` |
| 小桶执行 | `_mini_bucket.py:239` | `remaining < len(mini)` → 整桶溢出 |
| 溢出重试 | `_overflow.py:135` | `_try_overflow(site)` → 站点跳过 |
| 路由过滤 | `rotator.py:93` | `daily_count >= daily_limit` → `all_used` |

## 断点续传机制

### batch_state 表 [src: `pilotstd/core/db/migrations.py:427-439`]

| 字段 | 类型 | 说明 |
|------|------|------|
| `batch_id` | TEXT PK | 批次唯一标识 `batch-YYYYMMDD-HHMMSS-PID` |
| `status` | TEXT | pending/running/completed/failed/paused |
| `total_items` | INTEGER | 批次总条目数 |
| `completed_items` | INTEGER | 已完成数 |
| `failed_items` | INTEGER | 失败数 |
| `overflow_pool` | TEXT(JSON) | 待溢出重试条目列表 `[(idx, [item]), ...]` |
| `adapter_quota_snapshot` | TEXT(JSON) | 中断时适配器状态快照 |

### adapter_quota_snapshot Schema v1 [src: `pilotstd/query/engine/_metrics.py:64-82`]

```json
{
  "version": 1,
  "captured_at": 1753632000.0,
  "adapters": {
    "ahbz": {
      "cooldown_until": 1753635000.0,
      "request_count_in_window": 150,
      "daily_count": 600,
      "consecutive_errors": 0
    }
  }
}
```

### 恢复流程

```
1. 查询 batch_state WHERE status IN ('interrupted', 'paused')
2. 读取 overflow_pool → 恢复溢出队列
3. 读取 adapter_quota_snapshot → apply_adapter_snapshot(rotator, snapshot)
   - cooldown_until 取 max（防止覆盖新冷却）
   - 未知适配器 skip + warning
4. 重入 query_batch_parsed() → _handle_overflow() 处理剩余条目
```

### 写入时机 [src: `pilotstd/query/engine/_batch_dispatch.py:347-365`]

`_finalize_batch()` 末尾执行 `INSERT OR REPLACE INTO batch_state`，非阻断（异常仅记录日志）。

## 22 个适配器摘要

详见 [docs/adapters/README.md](../adapters/README.md)。关键性能指标：

| 适配器 | 日配额 | 路由角色 | 命中率影响 |
|--------|--------|----------|-----------|
| ahbz | 800 | GB 首选(30%) | 极高 |
| std_gov | 800 | GB 主力(40%) | 高 |
| csres | 200 | 最终兜底(5%) | 24h 硬冷却风险 |
| energy | 100 | 能源标准主站 | 配额最低+纯IP |
| cssn | 1000 | 行业首选 | 配额最高 |

## Metrics 计数器

| Key | 含义 | 触发条件 | [src] |
|-----|------|----------|------|
| `matched` | 成功匹配 | 单条查询成功 | `_single.py:114` |
| `quota_exhausted` | 配额耗尽 | 站点日配额用尽 | `_single.py:101` |
| `site_cooling` | 运行时冷却 | 查询前检测到冷却 | `_single.py:~108` |
| `overflow` | 桶溢出 | 冷却/配额致整桶溢出 | `_mini_bucket.py:237,252` |
| `chain_exhausted` | 链耗尽 | 溢出链所有站点失败 | `_overflow.py:158` |
| `csres_meltdown` | CSRES熔断 | 连续5次失败 | `_csres.py:81-93` |
| `bucket_crash` | 桶崩溃 | 桶线程异常 | `_batch_dispatch.py:273` |
| `parse_failed` | 解析失败 | 适配器查询异常 | `_mini_bucket.py:148` |
| `validate_failed` | 校验失败 | 解析结果校验不通过 | `_result_builder.py:133` |
