# 聚合搜索 P0：3 站「站点 × 查询类型」矩阵验证（2026-11-27）

> 目的：在开并发之前先摸清各站对「精确号 / 半精确 / 关键词模糊」的真实支持度与延迟，
> 作为 `AggregationService` 候选站点、置信度与超时参数的输入依据。
> 执行：`python scripts/query_aggregate_matrix.py --live`（真实联网，2026-11-27 19:2x）。

## 1. 实测矩阵（3 站 × 3 类型 = 9/9 全部有返回）

| 站点 | 查询类型 | 用例 | 结果 | 条数 | 耗时 ms | 首条号 |
|---|---|---|---:|---:|---:|---|
| `std_gov` | exact | `GB/T 1.1-2020` | ✅ | 3 | 2080 | GB/T 1.1-2020 |
| `std_gov` | semi | `GB/T 1.1` | ✅ | 3 | 572 | GB/T 1.1-2020 |
| `std_gov` | keyword | `压力容器` | ✅ | 10 | 586 | GB/T 48564-2026 |
| `dbba` | exact | `DB50/T 950-2026` | ✅ | 1 | 1874 | DB50/T 950-2026 |
| `dbba` | semi | `DB50/T 950` | ✅ | 2 | 297 | DB50/T 950-2026 |
| `dbba` | keyword | `地方标准` | ✅ | 15 | 442 | DB34/T 5513-2026 |
| `api_webstore` | exact | `API 610-2004` | ✅ | 1 | 2082 | **API STD 610-2026** |
| `api_webstore` | semi | `API 610` | ✅ | 1 | 282 | API STD 610-2026 |
| `api_webstore` | keyword | `centrifugal pump` | ✅ | 10 | 340 | API STD 610-2026 |

## 2. 关键结论（据此定 P0 参数）

1. **三站都支持关键词模糊**（此前提案里对 `api_webstore` 的「模糊弱」判断需修正：英文关键词可用，
   但**只返回最新版**——`API 610-2004` 被命中为 `API STD 610-2026`，属站点语义不是 bug）；
2. **延迟分布**：首次请求 1.9-2.1s（建连 + 会话初始化），后续 0.28-0.59s ⇒
   P0 单站超时默认 **8s** 足够，总预算 12s 合理；首站预热可在 P1 用后台 warmup 优化；
3. **关键词结果量大**（10-15 条）⇒ 聚合层需 **max_sites 6 + 每站取前 N 条（P1 增加 `per_site_limit`，默认 10）**，
   避免合并结果爆炸；
4. **`dbba` 关键词跨省**（「地方标准」命中 DB34）⇒ UI 需显示来源站与省份信息（置信度 `keyword`）；
5. **精确号是聚合主路径**：三站 exact 全部命中，confidence=`exact` 判定有效。

## 3. P0 实现核对（与矩阵对应）

| P0 能力 | 实现 | 落点 |
|---|---|---|
| 默认关闭 | `query.aggregate.enabled=false`；关闭时 API 返回 409、不发网络请求 | `pilotstd/core/config/defaults.py`、`pilotstd/query/aggregation.py` |
| 并发闸门 | 线程池 `max_concurrency=4`；单站超时 8s；总预算 12s；单站失败隔离 | 同上 |
| 按站限速 | 同站最小间隔 0.5s（进程内） | 同上 |
| 合并去重 | 按标准号归一（`parse_std_number`）合并 → `sources[]` | 同上 |
| 置信度 | exact / keyword | 同上 |
| API | `POST /api/query/aggregate`（只读，不落库） | `docker/api/query_aggregate.py` |
| 单测 | 9 例（关闭/合并/排序/超时/异常/max_sites/JSON） | `tests/test_query_aggregation.py` |

## 4. 测试包（给验收用）

```bash
# 1) 单测（离线，CI 可跑）
python -m pytest tests/test_query_aggregation.py -q          # 9 passed

# 2) 矩阵（离线计划 / 真实联网）
python scripts/query_aggregate_matrix.py                     # 打印计划
python scripts/query_aggregate_matrix.py --live              # 9 项实测（本报告数据）

# 3) API 冒烟（部署 0.210.0 后；默认关闭时返回 409）
curl -s -X POST http://192.168.1.18:9028/api/query/aggregate \
  -H 'Content-Type: application/json' -d '{"query":"GB/T 1.1-2020"}'
```

## 5. P1 待办（下一阶段）

- 每站结果上限 `query.aggregate.per_site_limit`（默认 10）与站点预热（warmup）；
- 熔断接入（复用 adapter circuit breaker）+ 聚合指标写 `query_metrics`；
- 缓存命中（`cache.py`，TTL 300s）；
- 3 站扩展到全站矩阵（24 站）作为 P2 UI 的置信度依据。
