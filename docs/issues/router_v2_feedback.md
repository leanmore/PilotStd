# router_v2 能力模型反馈

> 阶段二路由引擎开发中发现的能力模型问题，按约束记录于此，不回改 `config/site_capabilities.yaml`。

## 1. search_reliability 大面积 unknown，reliability 排序失效

- **现状**：21 个站点中，20 个 `search_reliability=unknown`，仅 `gongbiaoku=medium`（阶段一任务 1.2 排查产出）。
- **影响**：L2/L3 排序按 reliability 权重（`unknown=0.0`）执行，20 个 unknown 站点权重相同，排序退化为 YAML 原始顺序（稳定排序）。reliability 排序在当前数据下仅能区分 gongbiaoku（medium）与其他站点，其余站点排序基本失效。
- **建议**：后续阶段对各站点做搜索可靠性排查（类似任务 1.2 对 gongbiaoku 的排查），回填 `search_reliability`（high/medium/low），使 reliability 排序真正生效。

## 2. historical_hit_rate 全为 0.0，L1 排序退化为稳定顺序

- **现状**：全部 21 个站点 `historical_hit_rate=0.0`（阶段一已确认 `query_metrics` 表无 per-site 命中率数据）。
- **影响**：L1 排序按 `historical_hit_rate` 降序执行，但全为 0.0 时排序退化为 YAML 原始顺序，无法体现真实历史命中率差异。
- **建议**：待路由引擎上线运行、`query_metrics` 累积 per-site 命中数据后，回填 `historical_hit_rate`，使 L1 排序生效。
