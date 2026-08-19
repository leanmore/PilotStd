> ⚠️ **ARCHIVED (2026-08-19): 不再维护。** 已被 site_classification_partial.md (v1.1) 取代
>
---

# 标准查询站点分类分析结果（2026-08-17）

> 状态：已完成（21/21）。分类依据：`pilotstd/query/site_config.py` 的 `ADAPTER_DEFAULT_PROFILES` 配置 + 适配器代码证据。

## 分类汇总表

| site_name | level1 | level2 | industries | std_prefixes | source | completeness |
|-----------|--------|--------|-----------|-------------|--------|--------------|
| std_gov | 综合 | 国内综合 | [] | [GB, GB/T, GB/Z] | config_declared | 未知 |
| csres | 综合 | 国内综合 | [] | [GB, GB/T, GB/Z] | config_declared | 未知 |
| cssn | 综合 | 国内综合 | [] | [GB, GB/T] | config_declared | 未知 |
| ahbz | 综合 | 国内综合 | [] | [GB, GB/T, DB] | config_declared | 未知 |
| gongbiaoku | 综合 | 全综合 | [] | [] | config_declared | 未知 |
| njbz365 | 综合 | 全综合 | [] | [] | config_declared | 未知 |
| jjg | 特色 | 按标准类型区分 | [计量] | [JJG, JJF] | config_declared | 全量 |
| hbba | 特色 | 按标准类型区分 | [] | [SH,NB,HG,JB,YB,SY,CB,QB,FZ] | config_declared | 未知 |
| dbba | 特色 | 按标准类型区分 | [] | [DB] | config_declared | 未知 |
| ttbz | 特色 | 按标准类型区分 | [] | [T/] | config_declared | 未知 |
| iso_gov | 特色 | 按标准类型区分 | [] | [ISO, IEC, IEEE] | config_declared | 未知 |
| miit | 特色 | 按领域区分 | [工业] | [YD, SJ] | config_declared | 未知 |
| jtst | 特色 | 按领域区分 | [交通] | [JT, JTG, JTS] | config_declared | 未知 |
| mee | 特色 | 按领域区分 | [环保] | [HJ, GB] | config_declared | 未知 |
| nrsis | 特色 | 按领域区分 | [自然资源] | [DZ, TD] | config_declared | 未知 |
| sppt | 特色 | 按领域区分 | [食品] | [GB] | config_declared | 未知 |
| sppt_local | 特色 | 按领域区分 | [食品] | [DB] | config_declared | 未知 |
| tdpress | 特色 | 按领域区分 | [铁路] | [TB] | config_declared | 未知 |
| ncha | 特色 | 按领域区分 | [文物] | [WW] | config_declared | 未知 |
| energy | 特色 | 按领域区分 | [能源] | [NB, DL] | config_declared | 未知 |
| ccsn | 特色 | 按领域区分 | [工程建设] | [CECS] | config_declared | 未知 |

## 分类统计

- 综合站点：6 个（国内综合 4 + 全综合 2）
- 特色站点：15 个（按标准类型区分 5 + 按领域区分 10）
- 未分类：0 个

## 关键代码证据

- **iso_gov**：[iso_gov.py:58](pilotstd/query/adapters/iso_gov.py#L58) `if not any(kw in search_term.upper() for kw in ("ISO", "IEC")): return []` — 仅处理国际标准。
- **hbba**：[hbba.py:76-87](pilotstd/query/adapters/hbba.py#L76-L87) `_search_candidates` 无国际标准逻辑。
- **gongbiaoku**：[gongbiaoku.py:61-67](pilotstd/query/adapters/gongbiaoku.py#L61-L67) `query_standards` 用 `txt` 关键词，无前缀过滤。
- **njbz365**：[njbz365.py:72-121](pilotstd/query/adapters/njbz365.py#L72-L121) `bzbh` 字段解析，无前缀过滤。

## 方案修订建议

1. gongbiaoku/njbz365 国际标准能力需实际 ISO 试查询确认（代码无正向证据也无硬过滤）。
2. hbba 覆盖 9 种行业代号但无国标无国际，建议方案补充"行业综合"子类。
3. iso_gov 覆盖 ISO/IEC/IEEE 3 种代号，超出"按标准类型区分"单一代号定义。
