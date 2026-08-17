# v1 清理安全评估报告

> 生成日期：2026-08-17
> 评估对象：三级漏斗路由引擎 v2.0 灰度运行状态
> 数据来源：logs/router_v2_decisions.jsonl（埋点日志）

## 一、结论

**⚠️ 需补充数据**

当前 v2 灰度尚未积累足够样本量，不满足清理安全阈值。数据闭环（埋点 → 解析 → 回填）已就绪，需在 `ROUTING_ENGINE_VERSION=v2` 模式下运行足够查询后，重新执行本评估。

## 二、灰度样本量

| 指标 | 当前值 | 安全阈值 |
|------|--------|----------|
| v2 灰度查询数 | 0 | ≥ 1000 |
| 覆盖标准类型数 | 0 | 待统计 |

## 三、回归对比

| 指标 | v1 | v2 | 阈值 |
|------|----|----|------|
| 命中率 | 待采集 | 待采集 | v2 ≥ v1 × 0.95 |
| 平均延迟 | 待采集 | 待采集 | — |
| 错误率 | 待采集 | 待采集 | — |

> 需使用任务 4.1 埋点的 v1 精简日志（query_hash / hit_site / total_latency_ms）与 v2 完整日志做同期对照。

## 四、未覆盖场景

待样本量积累后，从日志中提取「v2 链上所有站点均失败的查询 Top 10」，逐一分析是否为 v1 能处理但 v2 遗漏的场景。当前无数据。

## 五、清理清单（暂不执行，待满足阈值）

| 文件/函数 | v1 职责 | 清理条件 |
|-----------|---------|----------|
| pilotstd/query/routing/scorer.py | 扁平评分器（get_priority_chain / score_adapter） | v2 灰度稳定 2 周 |
| pilotstd/query/engine/_single.py 的 v1 路径 | _step_get_priority_chain / _step_query_adapters | 同上 |
| pilotstd/query/engine/_routing.py 的 v1 路径 | _resolve_base_route / _apply_site_order | 同上 |
| pilotstd/query/engine/_mini_bucket.py 的 v1 分桶 | _build_mini_buckets 权重分桶 | 同上 |

## 六、下一步

1. 在 `ROUTING_ENGINE_VERSION=v2` 下运行 ≥1000 次真实查询，覆盖国标/行业/国际/模糊词/领域等类型。
2. 用 `scripts/analyze_router_logs.py` 产出指标，用 `scripts/backfill_capabilities.py` 回填 YAML。
3. 数据回填后重新评估，验证历史命中率与排序是否生效。
4. 满足阈值后，重新输出本报告（结论改为 ✅ 可清理），再执行 v1 清理。
