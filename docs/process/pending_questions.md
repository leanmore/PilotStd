# 待确认问题（Pending Questions）

- **Created**: 2026-08-19T21:23:00+08:00
- **Updated**: 2026-08-19T21:23:00+08:00
- **来源批次**: 第 1 批（项目入口）

---

## Q1-1 [P1] README.md 适配器数量统一
- **问题**: README.md L15 写"6 个适配器"，L75 写"7 个适配器"，实际代码 22 个（Q22-Q23 新增后，docs/adapters/README.md 已确认 22 个）。
- **选项**: A) 更新为 22（与 docs/adapters/README.md 一致）；B) 改为不写数量（写"多站点适配器"避免再漂移）。
- **影响**: README 入口数据准确性。

## Q1-2 [P1] README.md badge 更新策略
- **问题**: L6 "Tests-942 passed" 为 2026-07 历史快照；当前后端用例 3530+。README badge 是否应改为动态（GitHub Actions badge 显示最新状态）而非写死数字？
- **影响**: 入口文档可信度。

## Q1-3 [P3] CLAUDE.md "日志唯一入口"表述
- **问题**: L9 禁止 `_log()`/print，但未明确允许模块级 `logging.getLogger`。实际代码（notification/manager.py 等）广泛使用模块级 logger，LoggerManager 仅是初始化入口。新执行者可能误读。
- **建议**: 在 CLAUDE.md 补充一句澄清（如"模块内使用 logging.getLogger(__name__)，LoggerManager 负责初始化配置"），或保持现状。

## Q1-4 [P1] 进度日志权威版本
- **问题**: 项目存在 3 份进度日志：`docs/archive/项目进度日志.md`（CLAUDE.md L139 指向，自动生成）、`docs/archive/2026-07-16-historical-plans/项目进度日志.md`（07-04 快照）、`docs/项目进度日志.md`（07-24 手动维护）。权威版本未定。
- **建议**: 确定 1 份为权威（如 archive/ 自动生成版），其余归档/删除，并同步 CLAUDE.md L139 指向。

---

## 第 2 批新增问题

## Q2-1 [P1] modules/query.md 断链修复
- **问题**: `docs/architecture/modules/query.md:77` 引用 `../query-engine.md`，该路径不存在（实际为 `docs/query/README.md`）。规则 4 禁止断链。
- **建议**: 修改为 `../query/README.md`。

## Q2-2 [P1] 适配器口径统一（第 2 批）
- **问题**: overview.md L42/L116 写"22 个"，modules/query.md 写"8 个（7+1Mock）"，README.md L15/L75 写"6/7 个"。权威 = registry.py 注册 21 个生产适配器（+1 测试 Mock 不注册）。
- **建议**: 统一表述为"21 个生产查询适配器（另有 1 个测试 Mock）"，文档仅引用 registry.py 作为 SSOT。

## Q2-3 [P2] overview.md 路由描述与 v2
- **问题**: overview.md L110-113 仍描述 `_routing.py` 7 层决策树；v2 路由（router_v2.py 三级漏斗）已灰度（ROUTING_ENGINE_VERSION 环境变量控制，默认 v1，memory 2026-08-17）。
- **建议**: 确认是否更新 overview 以反映 v2（或标注"v1/v2 灰度中"）。

## Q2-4 [P2] architecture.md L55 验收数字
- **问题**: "后端测试 763 passed"为 2026-07-11 验收快照，当前 3530+。
- **建议**: 保留为历史验收记录并标注日期，或更新。

---

> 规则：本文件中的问题在阶段 B（操作规划）前需人工裁决；未裁决项进入阶段 B 的"待确认"区。

---

## 决策记录（人工裁决 2026-08-19T21:40）

| 问题 | 决策 | 执行说明 |
| :--- | :--- | :--- |
| Q1-1 | ✅ 闭环 | 适配器数量权威口径 = 21 生产 + 1 Mock（共 22），依据 registry.py:27-50；证据链已入 reading_notes_batch_1.md §5 |
| Q2-1 | ✅ 修复断链 | modules/query.md:77 → docs/query/README.md；前置：全局 grep query-engine.md 确认无其他引用，有则一并更新 |
| Q2-2 | ✅ 统一口径 | 所有文档适配器数量统一为"21 个生产适配器 + 1 个 Mock 适配器（共 22 个）"，必须写明构成，禁止只写总数 |
| Q2-3 | ✅ 更新路由描述至 v2 | 基于 router_v2 代码更新 overview.md 路由描述；只写已实现内容（三级漏斗），不推测未落地设计；细节不全时标注 `<!-- TODO: 补充 v2 路由细节 -->` |
| Q2-4 | ✅ 更新统计数字 | architecture.md L236"6 个 ADR"→8；同时扫描该文档其他过时统计（模块数/测试数），依据代码现状更新，注明数据来源和日期 |
| 架构四层 | ✅ 采纳 | DOCUMENTATION_MAP.md 新增"文档分层体系"章节（L0 入口/L1 总览/L2 决策/L3 模块），四层不合并；越界内容下沉到对应层 |

---

## 决策记录（人工裁决 2026-08-19T22:05，第 3 批）

| 问题 | 决策 | 执行说明 |
| :--- | :--- | :--- |
| Q3-1 | ✅ ADR-001-mixin 重编号为 ADR-010 | 依据：① README 索引已只收录 modal-dialog 版（mixin 版被"替代"而非"删除"）；② mixin 重构是独立技术决策。执行：重命名 `ADR-001-mixin-refactor-16-to-1.md` → `ADR-010-mixin-refactor.md`；文件头标注 `Status: Superseded by ADR-001-modal-dialog (测试基础设施)`；两文件建立双向交叉引用；同步 README 索引与 architecture.md 引用 |
| Q3-2 | ✅ 008/009 补独立文件 | 依据：ADR 核心价值是"决策可追溯性"，内联无法独立引用/标记状态/索引。执行：为 008（首页公告三栏分类）、009（CronTrigger 调度）各建独立 ADR 文件（Context/Decision/Consequences 结构），内容从 README 内联处提取；README 内联描述保留为摘要+链接 |
| Q3-3 | ✅ 统一 5 态标记 | ✅ Accepted（已采纳）/ ♻️ Superseded（已取代，注明取代者）/ ⛔ Rejected（已拒绝）/ 🗄 Deprecated（已废弃）/ 📝 Proposed（已提议）。全局扫描替换现有混用标记（✅/♻已修订/已接受/已关闭） |
| 交叉引用 | ✅ 补全 | ADR-010 增加 "Related ADRs" 章节（ADR-007~011 Handler 组合系列，说明两阶段重构先后关系）；architecture.md 决策速查表补入 mixin 重构条目；ADR-001-modal-dialog 增加 `Supersedes: ADR-010` 标记 |

## 决策记录（人工裁决 2026-08-19T22:25，第 4 批）

| 问题 | 决策 | 执行说明 |
| :--- | :--- | :--- |
| Q4-1 | ✅ 降级为历史快照 | governance-overview.md → 重命名 `governance-overview-ARCHIVED.md`（或移入 docs/archive/），顶部加 `> ⚠️ ARCHIVED: 历史快照，不再维护。当前系统总览请参阅 docs/overview.md`；若含 trinity-spec 未覆盖的高价值架构演进信息，提取后归档原文件 |
| Q4-2 | ✅ 修复 3 处断链 | 前置：全局 grep 确认 GATE_INDEX / architecture_layers / refactoring_checklist 实际替代路径。①有对应新文件→更新链接；②功能已合并（如 gates.md）→指向合并后章节；③彻底废弃→删除引用并补说明。**严禁编造路径** |
| Q4-3 | ✅ 核对并更新实现状态 | 读取 enforcement/guardrails.py 源码；已实现→trinity-spec 改"✅ 已实现（见 enforcement/guardrails.py）"；部分实现→"⚠️ 部分实现（已实现 A/B，待实现 C）"。**必须附代码行号依据** |
| Q4-4 | ✅ 合并后删除手动版 | 比对 docs/项目进度日志.md（手动）与 docs/archive/项目进度日志.md（权威）；手动版独有信息追加到权威版或 docs/archive/historical_notes.md；删除手动版；CLAUDE.md 及索引只保留权威版链接 |
| Q4-5 | ✅ 全面核验引用 | governance-principles.md 所有链接有效性检查（HTTP/本地路径），修复死链记录依据 |
| 治理分层 | ✅ 采纳 | DOCUMENTATION_MAP.md 治理体系模块：L0 执行手册（CLAUDE.md）/ L1 流程总纲（PROJECT_GOVERNANCE）/ L2 技术规格（trinity-spec）/ L3 治理原则（principles）/ L4 历史快照（overview-ARCHIVED） |

---

## 第 4 批新增问题

## Q4-1 [P1] governance-overview.md 处置
- **问题**: Engine 单元测试表 3 个 Engine（TableHelper/Table/Dialog）已被 08-02 死代码清理删除（文件不存在），L58 "12 Engine"与 L46-48 空行矛盾；"942 passed"为 07-16 快照。
- **建议**: A) 降级为历史快照（标注日期+已失效范围）；B) 大更新至当前状态；C) 并入 trinity-spec。需人工选择。

## Q4-2 [P1] PROJECT_GOVERNANCE.md 断链修复
- **问题**: 3 处引用失效（GATE_INDEX @ archive/2026-06-30、architecture_layers.md、refactoring_checklist.md 均不存在）。
- **建议**: 更新为实际路径（GATE_INDEX → 2026-07-16-historical-plans/old-archive/2026-06-30/）或删除失效引用行。

## Q4-3 [P1] enforcement/guardrails.py 实现状态
- **问题**: trinity-spec 五位交付物清单中 guardrails.py 标注"🔜 待实现"，但文件已存在。
- **建议**: 核对 guardrails.py 内容与规范 §4 接口（validate_prompt/session_bootstrap 等）是否已实现；已实现则更新规范状态。

## Q4-4 [P1] docs/项目进度日志.md（手动版）去留
- **问题**: 三份进度日志并存；权威版已定为 docs/archive/项目进度日志.md（自动生成，CLAUDE.md 引用）。
- **建议**: docs/项目进度日志.md（07-24 手动版）合并入权威版后删除；historical-plans/ 版归档保留。

## Q4-5 [P2] governance-principles 引用核验
- **问题**: 引用 G-029 脚本与 .github/scripts/check-repo-compliance.sh，存在性待确认。
- **建议**: 核验后修复失效引用（若有）。

---

## 第 3 批新增问题

## Q3-1 [P0] ADR-001 冲突重编号
- **问题**: `ADR-001-mixin-refactor-16-to-1.md` 与 `ADR-001-modal-dialog-auto-clicker.md` 同编号；README 索引只认 modal-dialog 版。
- **建议**: 人工决定 mixin-refactor 版新编号（如 ADR-010），或并入 architecture.md；需同步 README 索引与引用。

## Q3-2 [P1] ADR-008/009 空档处理
- **问题**: 索引登记 008（首页公告三栏分类）、009（CronTrigger 调度）但无独立文件；009 详情写在 README L34-37。
- **建议**: A) 补建 ADR-008/009 独立文件（依据 README 内联说明+代码）；B) 索引改为内联记录并标注"无独立文件"。需确认 008 是否与公告前端三栏实现对应（docker/api/announce.py 三栏分组已实现，memory 有记录）。

## Q3-3 [P2] ADR 状态词汇统一
- **问题**: 现有状态混用（✅/♻/已接受/已关闭），无规范。
- **建议**: 统一为 `✅ 已落地 / ♻ 已修订 / 📝 已提议 / ⛔ 已废弃 / 🗄 已关闭`，并同步 README 索引。

---

## 第 5 批新增问题

## Q5-1 [P1] session-store-design.md 固定密钥方案处置
- **问题**: 文档 L26 记录固定密钥方案 `"pilotstd_jwt_secret_2026_fixed_key"`，但实际 `docker/auth.py` 为 `os.environ.get("JWT_SECRET") or secrets.token_urlsafe(32)`（随机 token）。
- **建议**: A) 文档标注"方案未采纳，实际采用随机 token"（设计记录应反映最终决策）；B) 更新文档为现状。需确认该设计是否曾被部分实施。

## Q5-2 [P2] documentation-policy.md 断链与矛盾
- **问题**: ① L104 引用不存在的 gate-15-enforcement.md；② L20 声称 capabilities_registry"移出仓库"（实际在仓）；③ L197 声称 archive"不入仓"（实际有文件被跟踪）。
- **建议**: 修复引用（指向 check_g_015_relative_imports.py）+ 修正 2 处入仓状态描述（git 实证为准）。

## Q5-3 [P2] specs/ 两件归档
- **问题**: 功能规格说明书（1.15 止于 06-16）与模块与功能清单（06-30）严重过时。
- **建议**: 归档至 docs/archive/，DOCUMENTATION_MAP 标注替代文档（architecture/modules/* + adapters/README.md）。

---

## 决策记录（人工裁决 2026-08-19T22:50，第 5 批）

| 问题 | 决策 | 执行说明 |
| :--- | :--- | :--- |
| Q5-1 | ✅ 标注"已修订"并补充依据 | session-store-design.md L26 固定密钥处添加：`> ⚠️ 已修订 (2026-08-19): 实际实现未采纳固定密钥方案，改为每次启动生成随机 Token。依据：docker/auth.py (secrets.token_urlsafe)`。**严禁抹除原设计**；若文档整体无指导价值可整体 ARCHIVED |
| Q5-2 | ✅ 最高优先级修复元规范 | documentation-policy.md：① 断链 gate-15-enforcement.md → 全局 grep 确认，无替代则删除引用或指向 gates.md；② capabilities_registry"移出仓库"→修正为"当前在仓内（git ls-files 实证），后续计划移出"或删"移出"表述；③ archive"不入仓"→修正为"部分历史文件仍被 Git 跟踪（遗留状态），新归档原则上不入仓"。**修改必须附 git ls-files 实证** |
| Q5-3 | ✅ 执行归档 | specs/ 功能规格说明书 + 模块与功能清单 → 移入 docs/archive/specs/ 或原位加 `> ⚠️ ARCHIVED` 警告头；DOCUMENTATION_MAP 归入"历史归档"区 |
| 元规范声明 | ✅ 采纳 | DOCUMENTATION_MAP.md 顶部声明：`⚠️ 本文档地图的生成与维护遵循 docs/governance/documentation-policy.md 中定义的入仓标准与归档协议。若地图内容与该 Policy 冲突，以 Policy 为准（并提 Issue 修复地图）` |

---

## 第 6 批结论（无新待确认问题）

| 处置 | 文档 | 依据 |
| :--- | :--- | :--- |
| 归档 | docs/analysis/site_classification_partial_v1.0.md | v1.1 首部明确"历史版本"（取代关系实证） |
| 归档 | docs/superpowers/specs/2026-07-30-vulture-dead-code-scan.md | 08-02 已执行清理，纯历史快照 |
| 保留 | 其余 14 个分析/快照文档 | 有指导价值/自述存档用途/动态有效性（见 reading_notes_batch_6.md） |
