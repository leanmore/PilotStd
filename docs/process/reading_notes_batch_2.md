# 精读笔记 — 第 2 批（架构总览）

- **Created**: 2026-08-19T21:35:00+08:00
- **Updated**: 2026-08-19T21:35:00+08:00
- **批次状态**: 待确认（等待人类 Gate 确认）
- **精读深度判定留痕**: 依据审计描述「architecture.md = 架构设计/与 adr 重叠待确认」「overview.md = 架构总览/技术栈 3.11 待确认」「modules/* = 模块文档」→ 判定 **architecture.md + overview.md 逐字精读，modules/manager.md + query.md 重点章节精读，parser/scan/ui.md 复用审计首部+架构.md 引用（速读）**

---

## 1. docs/architecture.md（239 行，逐字）

### 1.1 内容
Handler 组合模式（2026-07-11）→ Handler 层治理策略（ADR-002/003/004/005/006 引用）→ 死代码清理记录（2026-08-02 Phase1/2）→ 决策记录表（P5 系列）→ 公告数据模型（双表）→ 收藏与归档（ADR-007）→ 迁移校验机制。

### 1.2 证据链（规则 1 留痕）
| 发现 | 依据 | 状态 |
| :--- | :--- | :--- |
| L236 "ADR 目录 — 6 个架构决策记录"过时 | 实际 `docs/adr/` 8 个 ADR 文件（001×2 + 002~008） | ⚠️ 过时，需更新为 8 |
| L55 "后端测试 763 passed"为历史验收数字 | 当前后端用例 3530+（STATUS.md metrics） | ⚠️ 历史数字，可保留作验收快照或更新 |
| L121 "handlers/ 21→7 实际使用类，总文件 48→28" | 2026-08-02 清理记录，与 memory 2026-08-17/technical-debt 一致 | ✅ 有效 |
| 公告双表模型（announcement_record 活跃 / announcements 停滞） | 与本会话公告修复调研一致（matcher.py 写 announcement_record） | ✅ 有效且重要 |
| 迁移校验机制（_norm_source + SHA-256 checksum） | 与 P10_plan 闭环记录一致（2026-07-17） | ✅ 有效 |

### 1.3 交叉引用核验
- L67/L93/L139/L145 引用 ADR-002/003/004/005/006 ✅ 均存在（含补录的 ADR-006）
- L79-83 引用 guides/*-pattern（5 个）✅ 均存在
- L237-238 引用 technical-debt.md + technical-debt-registry.md ✅ 均存在（摘要-详情分工）

## 2. docs/architecture/overview.md（199 行，逐字）

### 2.1 内容
技术栈 → 模块关系图（mermaid）→ 核心模块职责 → 数据流向（标准查询完整链路）→ 批量查询旁路 → 数据库表全景 → 关键设计决策。

### 2.2 证据链
| 发现 | 依据 | 状态 |
| :--- | :--- | :--- |
| L42/L116 "22 个查询适配器"（含 Mock 口径） | registry.py ALL_ADAPTERS 21 个注册（本会话已核实） | ⚠️ 口径问题：22=21 生产+1 Mock（Mock 不注册）；建议统一为"21 个生产（+1 测试 Mock）" |
| L9 "Python 3.11+" | 实际环境 Python 3.14（venv 3.14.2） | ⚠️ 过时 |
| L110-113 路由描述（_routing.py 7 层决策树） | v2 路由已上线（router_v2.py 三级漏斗，memory 2026-08-17 记录 ROUTING_ENGINE_VERSION 灰度） | ⚠️ 未反映 v2；需确认 overview 更新策略（v1 灰度中，可能有意保留 v1 描述） |
| L143 GB 优先级链 ahbz(30%)/std_gov(40%)/njbz365(25%)/csres(5%) | docs/adapters/README.md 与 registry 一致 | ✅ 有效 |
| 数据库表全景 12 表 | 与 migrations v44 对照（favorite_downloads=v44、batch_state=v43） | ✅ 基本有效（待完整 migrations 核验，属第 3+ 批范围） |

## 3. modules/manager.md（93 行，重点精读）

- 结构准确：ManagerCore 依赖容器（22+ 字段）、facade/ 8 个 Handler、Service 层 13 个服务
- 与代码对照：facade/ 目录文件一致 ✅
- L21 "22+ 依赖" — 与 ManagerCore dataclass 字段数待精确核验（不阻断）

## 4. modules/query.md（77 行，重点精读）

### 4.1 证据链（严重过时）
| 发现 | 依据 | 状态 |
| :--- | :--- | :--- |
| L18-27 适配器清单仅 8 个（7 生产+1 Mock） | registry.py 实际 21 个生产（缺 ccsn/cssn/energy/gongbiaoku/jjg/jtst/mee/miit/ncha/nrsis/sppt/sppt_local/tdpress/ttbz） | ⚠️ **严重过时**（Q22-Q23 前） |
| **L77 断链**：[查询引擎](../query-engine.md) 不存在 | 实际文档为 `docs/query/README.md`；`docs/query-engine.md` 不存在 | 🔴 **断链（规则 4）** |
| L33 "5 步渐进搜索" 与 base.py | 与 adapter 基类 `_search_progressive` 一致 | ✅ 有效 |

## 5. 交叉关联
- architecture.md 是"决策记录+架构说明"混合体，与 adr/（正式 ADR）、overview.md（总览）、modules/*（模块详情）四层关系：**架构.md = 决策速查 + 关键模型；ADR = 正式决策；overview = 系统总览；modules = 模块详情**。审计 §7 的"功能重叠"实为分层互补，建议在 DOCUMENTATION_MAP 中明确分工而非合并。
- modules/query.md 的适配器清单与 docs/adapters/README.md（22 口径）双份并存 → 建议以 registry.py 为 SSOT，文档只引用。

## 6. 操作需求草案（供阶段 B 汇总）
| 动作 | 目标 | 优先级 | 证据 |
| :--- | :--- | :--- | :--- |
| 修正 | architecture.md L236 ADR 数（6→8） | P2 | docs/adr/ 目录 8 文件 |
| 修正 | overview.md Python 3.11+→3.14 | P2 | venv 3.14.2 |
| 修正/确认 | overview.md + modules/query.md 适配器口径（21 生产 + 1 Mock） | P1 | registry.py:27-50 |
| **修复断链** | modules/query.md L77 `../query-engine.md` → `../query/README.md` | P1 | 路径验证不存在 |
| 更新/确认 | modules/query.md 适配器清单（8→21）或改为引用 docs/adapters/README.md | P1 | registry.py |
| 确认 | overview.md 路由描述是否更新为 v2（或标注 v1 灰度中） | P2 | ROUTING_ENGINE_VERSION 灰度状态 |
