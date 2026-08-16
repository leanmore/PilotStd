<!--
  ⚠️ 用途声明（重要）
  此文档为 std 路由错配问题的根因分析存档，用于未来重启路由优化时作为上下文依据，避免重复排查。
  本文档仅作记录，不代表任何已落地的代码改动 —— 相关的路由代码修改已在保存本档后回退。
-->

# std 路由错配问题根因分析

> 归档日期：2026-08-16
> 分析对象：GB 国标被错误路由到行业专属站点的问题

## 一、问题概述

查询 `GB/T 12345-2020` 这类国家标准时，优先级链 `get_priority_chain()` 会把 **环保站点（mee）** 和 **食品安全站点（sppt）** 排到 **工标网（cssn）** 之前，导致国标被优先路由到行业专属站点，而这些站点并不收录全行业国标，造成查询错配、浪费配额、返回无意义结果。

## 二、根因链

1. `site_config.py` 的 `ADAPTER_DEFAULT_PROFILES` 中，行业站点错误配置了 GB 前缀：
   - `mee`（生态环境部）原配置 `std_prefixes: ["HJ", "GB"]`
   - `sppt`（食品安全）原配置 `std_prefixes: ["GB"]`
2. `scorer.py` 的 `score_adapter()` 第一步"标准号前缀精确匹配 +30"：只要查询词以某前缀开头，该适配器即 +30 分。
3. 于是 `GB/T` 查询对 mee、sppt 触发 GB 前缀匹配，各 +30 分，把它们顶到 cssn 之上。
4. 结果：国标优先路由到行业站点，而非通用国标站点。

## 三、证据报告（评分计算表）

以查询 `GB/T 12345-2020` 为例，评分公式 = base 权重 + 前缀匹配 +30 − 通用适配器降权 −10：

| 适配器 | base | 前缀匹配 | 通用降权 | 总分 | 是否应在 GB 链 |
|--------|------|----------|----------|------|----------------|
| std_gov | 70 | +30 (GB) | −10 | **90** | 是（通用国标站）|
| mee | 55 | +30 (GB) | 0 | **85** | 否（环保行业站）|
| sppt | 55 | +30 (GB) | 0 | **85** | 否（食品行业站）|
| cssn | 60 | +30 (GB/T) | −10 | **80** | 是（通用国标站）|

mee / sppt（85）排在 cssn（80）之前，形成错配。国标应只落在 `is_general=True` 的通用站点（std_gov、csres、cssn、ahbz 等）。

## 四、代码定位

- `pilotstd/query/site_config.py:124` — mee 适配器 `std_prefixes`（修复前 `["HJ", "GB"]`）
- `pilotstd/query/site_config.py:148` — sppt 适配器 `std_prefixes`（修复前 `["GB"]`）
- `pilotstd/query/routing/scorer.py:164-169` — 前缀精确匹配 +30 评分逻辑
- `pilotstd/query/routing/scorer.py:206` — `get_priority_chain()` 入口

## 五、修复建议

1. mee 移除 GB 前缀：`["HJ", "GB"]` → `["HJ"]`
2. sppt 移除 GB 前缀：`["GB"]` → `[]`（sppt 仅靠 `industries: ["食品"]` 关键词匹配 +20 参与评分）
3. 验证覆盖（`tests/test_routing_domain_filter.py`，本档保存时已回退）：
   - GB/T 不应出现在 mee / jtst / sppt / tdpress / ncha / miit / jjg 链中
   - HJ 应路由到 mee
   - NB/T 应路由到 energy / hbba
   - 未知代号空链保护：链不为空

## 六、关键认知修正：GB 为全行业国标

- **GB / GB/T / GB/Z 是国家标准，覆盖全行业**（机械、化工、食品、环保、计量等），不是任何单一行业专属。
- 此前把 GB 前缀加到 mee（环保）、sppt（食品）等行业站点，本质是把"国标"误当成"行业专属标准"。
- 正确路由原则：**国标 → `is_general=True` 的通用站点；行业标准 → 对应行业站点**（如 HJ→mee、JT→jtst、TB→tdpress）。
- 行业站点即使声明了 GB 前缀，也只收录其行业子集，不能承担全行业国标查询。
