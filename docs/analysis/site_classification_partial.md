# 标准查询站点分类分析结果 v1.1（2026-08-17）

> 方案版本：v1.1（`docs/design/site_classification_v1.md`）
> 状态：已完成（21/21）。包含 ISO 试查询验证。
> 历史版本：`site_classification_partial_v1.0.md`

## 试查询结果

| 站点 | 查询词 | 返回结果 | 结论 |
|------|--------|---------|------|
| gongbiaoku | ISO 9001 / IEC 62304 | 返回无关国标（GB 消防/建筑） | 国际能力未通过验证 |
| njbz365 | ISO 9001 / IEC 62304 | 正确返回 ISO/IEC 标准 | 国际能力已验证 |

## 分类汇总表（10 字段）

| site_name | level1 | level2 | industries | std_prefixes | source | completeness | intl_verified | notes | judgment_basis |
|-----------|--------|--------|-----------|-------------|--------|--------------|---------------|-------|----------------|
| hbba | 综合 | 国内综合 | [] | [SH,NB,HG,JB,YB,SY,CB,QB,FZ] | config_declared | 未知 | - | | 9 种独立行业代号体系，各计 1 种 |
| ahbz | 综合 | 国内综合 | [] | [GB,GB/T,DB] | config_declared | 未知 | - | | 国标(1) + 地方标准DB(1) = 2 种 |
| gongbiaoku | 综合 | 国内综合 | [] | [] | config_declared | 未知 | false | ⚠️ 搜索可靠性存疑：ISO 关键词被模糊匹配为无关国标，建议排查搜索逻辑 | ISO 试查询返回无关国标，国际能力未通过验证 |
| njbz365 | 综合 | 全综合 | [] | [] | config_declared | 未知 | true | | ISO/IEC 试查询正确返回国际标准 |
| std_gov | 特色 | 按标准类型区分 | [] | [GB,GB/T,GB/Z] | config_declared | 未知 | - | 国标专用平台（覆盖全领域国标） | 国标体系 1 种 |
| csres | 特色 | 按标准类型区分 | [] | [GB,GB/T,GB/Z] | config_declared | 未知 | - | 国标专用平台（覆盖全领域国标） | 国标体系 1 种 |
| cssn | 特色 | 按标准类型区分 | [] | [GB,GB/T] | config_declared | 未知 | - | 国标专用平台（覆盖全领域国标） | 国标体系 1 种 |
| jjg | 特色 | 按标准类型区分 | [计量] | [JJG,JJF] | config_declared | 全量 | - | | 计量技术规范（方案3.2明确示例） |
| dbba | 特色 | 按标准类型区分 | [] | [DB] | config_declared | 未知 | - | | 地方标准 1 种 |
| ttbz | 特色 | 按标准类型区分 | [] | [T/] | config_declared | 未知 | - | | 团体标准 1 种 |
| iso_gov | 特色 | 按标准类型区分 | [] | [ISO,IEC,IEEE] | config_declared | 未知 | - | | 国际标准聚合（同维度），代码硬过滤 ISO/IEC |
| miit | 特色 | 按领域区分 | [工业] | [YD,SJ] | config_declared | 未知 | - | | 工信部工业领域 |
| jtst | 特色 | 按领域区分 | [交通] | [JT,JTG,JTS] | config_declared | 未知 | - | | 交通运输领域 |
| mee | 特色 | 按领域区分 | [环保] | [HJ,GB] | config_declared | 未知 | - | GB 仅限环保类国标（领域约束优先） | 环保领域（HJ+环保类GB） |
| nrsis | 特色 | 按领域区分 | [自然资源] | [DZ,TD] | config_declared | 未知 | - | | 自然资源领域 |
| sppt | 特色 | 按领域区分 | [食品] | [GB] | config_declared | 未知 | - | | 食品安全国标领域 |
| sppt_local | 特色 | 按领域区分 | [食品] | [DB] | config_declared | 未知 | - | | 食品安全地方标准领域 |
| tdpress | 特色 | 按领域区分 | [铁路] | [TB] | config_declared | 未知 | - | | 铁路领域 |
| ncha | 特色 | 按领域区分 | [文物] | [WW] | config_declared | 未知 | - | | 文物领域 |
| energy | 特色 | 按领域区分 | [能源] | [NB,DL] | config_declared | 未知 | - | | 能源领域 |
| ccsn | 特色 | 按领域区分 | [工程建设] | [CECS] | config_declared | 未知 | - | | 工程建设领域 |

## 分类统计

- 综合站点：4 个（国内综合 3 + 全综合 1）
- 特色站点：17 个（按标准类型区分 7 + 按领域区分 10）
- 未分类：0 个

## 与 v1.0 的归类变化

| 站点 | v1.0 | v1.1 | 原因 |
|------|------|------|------|
| std_gov | 国内综合 | 按标准类型（国标） | GB/GB/T/GB/Z 计 1 种 |
| csres | 国内综合 | 按标准类型（国标） | 同上 |
| cssn | 国内综合 | 按标准类型（国标） | 同上 |
| hbba | 按标准类型 | 国内综合 | 9 种行业代号各计 1 种 |
| gongbiaoku | 全综合（待确认） | 国内综合 | ISO 试查询返回无关国标 |
| njbz365 | 全综合（待确认） | 全综合 | ISO/IEC 试查询正确返回 |
