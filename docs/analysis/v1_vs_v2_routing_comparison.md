# v1 vs v2 路由选择对比报告

> 生成日期：2026-08-17
> 对比范围：10 个真实 Query（覆盖国标/环保/国际/模糊词/领域/地方/兜底）

## 对比结果

| Query | v1 首选 | v1 链（前5） | v2 首选 | v2 链（前5） | v2 层级 |
|-------|---------|-------------|---------|-------------|---------|
| GB/T 12345-2020 | std_gov | std_gov→mee→sppt→cssn→ahbz | std_gov | std_gov→csres→cssn | L1 |
| GB 12345-2020 | std_gov | std_gov→mee→sppt→cssn→ahbz | std_gov | std_gov→csres→cssn | L1 |
| HJ 123-2020 | mee | mee→std_gov→jjg→iso_gov→hbba | mee | mee | L1 |
| ISO 9001:2015 | iso_gov | iso_gov→std_gov→jjg→hbba→miit | njbz365 | njbz365 | L2 |
| IEC 62304 | iso_gov | iso_gov→std_gov→jjg→hbba→miit | njbz365 | njbz365 | L2 |
| 食品安全管理体系 | sppt | sppt→sppt_local→std_gov→jjg→iso_gov | njbz365 | njbz365 | L3 |
| TB 123-2020 | tdpress | tdpress→std_gov→jjg→iso_gov→hbba | tdpress | tdpress | L1 |
| JJG 123-2020 | jjg | jjg→std_gov→iso_gov→hbba→miit | jjg | jjg | L1 |
| DB11/T 123-2020 | dbba | dbba→sppt_local→ahbz→std_gov→jjg | dbba | dbba | L1 |
| 随机无意义字符串 | std_gov | std_gov→jjg→iso_gov→hbba→miit | njbz365 | njbz365 | L3 |

## 关键差异

1. **国标查询**：v1 扁平评分可能将国标路由到 mee（其 `std_prefixes` 含 GB 的历史缺陷）；v2 的三级漏斗 L1 只匹配 `supported_types`，mee 已修正为 `[HJ]`，国标不再误路由到 mee。
2. **国际标准**：v1 评分器将 ISO 路由到 iso_gov；v2 因 iso_gov 的 `is_international=false`（阶段一设计），ISO 查询跳过 L1 直接进入 L2 命中全综合站 njbz365。
3. **模糊关键词**：v1 可能路由到任意行业站；v2 的纯关键词查询跳过 L1/L2 直接进入 L3 探索层（全综合站）。
4. **可观测性**：v2 每个站点带 decisions 记录（含 L1/L2/L3 层级），v1 仅返回无解释的站点列表。
