# 适配器节点 A2 报告：4 站「解析 → 路由 → 适配器」复评（2026-11-25）

> 节点拆分见 `docs/plans/2026-11-25-master-plan.md` §5：A1 规则修复（=批次 10，已随 lane-parse 合入）
> → **A2 三站做足复评（本报告）** → A3 福建复测 → A4 省份粒度路由 / POST 检索口径。

## 1. 一句话结论

**A2 通过**：A1 的解析修复已让 3 个已落地站点的「解析 → 路由 → 真实检索」全链路打通
（API Webstore / ASME / 重庆 cqis 均联网命中真实数据）；**福建仍 BLOCKED**（DNS 可解析、
`220.160.53.32` 全端口 TCP 超时），A3 维持阻塞、不实现。

## 2. 在线冒烟结果（真实网络，2026-11-25 23:4x）

命令：`python scripts/smoke_adapters.py --live`

| 站点 | 样例 | 结果 | 耗时 |
|---|---|---|---|
| `api_webstore`（API Webstore） | `API 610-2004` | **1 条**：`API STD 610-2026`（现行） | 2.3s |
| `asme`（ASME） | `ASME B16.5-2020` | **1 条**：`ASME B16.5-2025`（被代替） | 1.6s |
| `cqis`（重庆 DB50） | `DB50/T`（关键词） | **20 条**真实 DB50 号（如 `DB50/T 950-2026 荣昌卤鹅加工技术规范`） | 2.1s |
| ` fj`（福建） | — | **BLOCKED**：`pt.fjbz.org.cn` / `www.fjbz.org.cn` → `220.160.53.32`，TCP 80/443/8060 全超时 | — |

> 说明：`DB50/T 1234-2021` 这种**不存在**的号返回 0 条属正确行为；改按真实号
> `DB50/T 950-2026` 复测命中 1 条（见 §4 复核）。

## 3. 解析 → 路由一致性（A1 修复的直接收益）

`python scripts/smoke_adapters.py`（离线，零网络）实测：

| 样例 | 解析结果 | 路由链 |
|---|---|---|
| `API 610-2004` | `code=API, number=610, year=2004` | `api_webstore` |
| `API SPEC 6D-2021` | `code=API, number=6, num_prefix=SPEC, num_suffix=D` | `api_webstore` |
| `API 579-1/ASME FFS-1` | `code=API, number=579, part=1`（联合标准取主标准） | `api_webstore` |
| `ASME B16.5-2020` | `code=ASME, number=16, part=5, num_prefix=B` | `asme` |
| `ASME PTC 4-2013` | `code=ASME, number=4, num_prefix=PTC`（修复前代号被吞成 `ASMEPTC`） | `asme` |
| `ASME BPVC Section VIII Div.1-2021` | `code=ASME, number=8, part=1, num_prefix=VIII` | `asme` |
| `DB50/T 1234-2021` | `code=DB50T, number=1234, year=2021` | `dbba, cqis` |
| `GB/T 1.1-2020` | `code=GBT, number=1, part=1, year=2020` | `std_gov, csres, cssn` |

**回归锁定**：`tests/test_adapter_site_conformance.py`（15 例，离线）——
① A1 的 4 类解析形态；② 4 站路由链（含「ASME 不得落 `ahbz`/`njbz365` 兜底站」）；
③ DB50 必含 `cqis`；④ 福建不进入任何默认路由。

## 4. 本轮复核项与结论

| 复核项 | 结论 |
|---|---|
| ASME 系列词（PTC/CSD）是否仍污染代号 | ✅ 已修（A1）：`num_prefix` 正确，路由走 `asme` |
| API 多段后缀（`SPEC 6D`/`TR 938-C`）与联合标准 | ✅ 已修（A1）：后缀/part 保留，路由走 `api_webstore` |
| 重庆 DB50 是否真正命中（非「0 条假通过」） | ✅ 用真实号 `DB50/T 950-2026` 复核命中 1 条 |
| API Webstore 是否仍受 401/token 影响 | ✅ 本次直连命中（token 自愈逻辑未触发） |
| 福建是否可接入 | ❌ BLOCKED：DNS→`220.160.53.32`，TCP 80/443/8060 全超时（与 2026-11-24 侦查一致） |

## 5. A4 待办（需要产品口径，先登记不实现）

1. **省份粒度路由**：目前 DB50 走 `dbba → cqis` 链；若要求「重庆地方标准只打重庆站点」，
   需在 `site_capabilities.yaml` 增加 `province: 重庆` 维度并调整 `_extract_industry`/路由评分（schema 评估）；
2. **POST 检索口径**：API Webstore 走 Coveo POST、cqis 走 POST，两者均已有实现；若统一「POST 优先」，
   会影响既有 3 个 GET 站点，需单独一批（不阻塞 A2）。

## 6. 交付物

| 文件 | 说明 |
|---|---|
| `scripts/smoke_adapters.py` | 4 站冒烟工具：默认离线打印解析+路由；`--live` 做 3 站真实检索 |
| `tests/test_adapter_site_conformance.py` | 15 例离线一致性契约（解析→路由→站点选择 + 福建阻塞事实） |
| `docs/reference/adapter-development.md` §9.4 | 冒烟工具用法登记 |
| 本报告 | A2 结论与 A4 待办 |

## 7. 后续（2026-11-26 用户裁定）

- **福建站：放弃**（已评估无互补价值，详见 `docs/plans/2026-11-26-fujian-site-eval.md`）；
- 适配器节点 A3 关闭；A4（省份路由）已随 D-2 合入，A2 结论保持。
