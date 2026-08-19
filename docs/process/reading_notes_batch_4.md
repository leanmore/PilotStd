# 精读笔记 — 第 4 批（治理体系）

- **Created**: 2026-08-19T22:15:00+08:00
- **Updated**: 2026-08-19T22:15:00+08:00
- **批次状态**: 待确认（等待人类 Gate 确认）
- **精读深度判定留痕**: 依据审计描述「治理文档=核心」「PROJECT_GOVERNANCE/overview 重叠待确认」+ 指令重点（重叠/冲突/职责越界 + CLAUDE.md 关系）→ 4 份总纲类文档（PROJECT_GOVERNANCE 114 行 / governance-principles 99 行 / governance-overview 138 行 / trinity-spec 410 行）**逐字精读 + 路径实证核验**；gates.md / development-flow.md 等支撑文档复用前期精读。

---

## 1. 四份"治理总纲"文档维度定位（核心结论）

| 文档 | 版本/日期 | 维度 | 一句话定位 | 状态判定（证据） |
| :--- | :--- | :--- | :--- | :--- |
| PROJECT_GOVERNANCE.md | v1.0 / 06-29 | 流程 | 能力-门禁-架构"三件套"总纲（新增能力/门禁/重构流程 + 治理角色） | ⚠️ **引用路径全部失效**（见 §3） |
| governance-principles.md | v1.0 / 07-14 | 原则 | 治理元原则（三支柱/门禁设计原则/承诺追踪/关联分析） | ✅ 有效（理念性，不过时） |
| governance-overview.md | v1.0.0 / 07-16 | 快照 | 三位一体状态快照（测试 Engine 表 + 门禁 + 文档支柱） | 🔴 **严重过时**（08-02 清理后 Engine 表失效） |
| trinity-technical-spec-v2.md | v2.1 / 07-27 | 规格 | 三位一体技术规范（15 章：核心原则/交付物/强制执行层/健康度/提交粒度） | ⚠️ 部分未落地（guardrails.py 状态待核验） |

**结论：四份不是简单重复，是"流程 / 原则 / 快照 / 规格"四个维度**——但快照（overview）已失效、总纲（PROJECT_GOVERNANCE）引用已断，需修复而非合并。

## 2. CLAUDE.md 与 governance/ 的关系（指令重点）

**结论：互补，非重复。**

| 维度 | CLAUDE.md | governance/ |
| :--- | :--- | :--- |
| 定位 | 执行者操作手册（铁律/SOP/门禁时机/收工流程） | 治理体系规范（原则/规格/流程） |
| 读者 | Claude Code（执行者） | 体系本身 + 决策者 + 参谋 |
| 门禁描述 | §3 摘要（何时介入 G-010/020/025/030/031/034） | gates.md 详情（完整门禁清单）→ **摘要-详情分工** |
| 联动 | 触发表引用 governance 文档（L50 gates.md 等） | G-037 强制触发表与 index.md 对齐 |

**唯一重叠风险**：CLAUDE.md §3 门禁规则 vs gates.md —— 已确认是摘要-详情分工（非重复，无需合并）。

## 3. 证据链（规则 1 留痕）

| 发现 | 依据 | 状态 |
| :--- | :--- | :--- |
| governance-overview Engine 表失效（TableHelper/Table/Dialog 3 个 Engine 仍列出） | `pilotstd/ui/core/handlers/table_flow_engine.py`、`table_helper_flow_engine.py`、`dialog_flow_engine.py` 均**不存在**（08-02 死代码清理 Phase 2 删除，architecture.md L116-119 记录） | 🔴 严重过时 |
| governance-overview L58 "12 Engine, 284+ tests" 与 L46-48 三个空行自相矛盾 | 表格 12 行中 3 行无数据（Query/Actions/Archive） | 🔴 数据矛盾 |
| PROJECT_GOVERNANCE L92/93/95 引用失效 | `docs/archive/2026-06-30/GATE_INDEX.md`、`docs/architecture_layers.md`、`docs/governance/refactoring_checklist.md` 均 **False**（不存在） | 🔴 断链×3 |
| trinity-spec 五位交付物：prompt-crafting-guide / rule-quickref / development-flow / local-session-notes / guardrails.py | 前 4 个文件存在（local-session-notes 为空文件）；`enforcement/guardrails.py` **存在**（规范标注"待实现"，需确认实现状态） | ⚠️ 待确认 |
| governance-overview L136 "942 passed" 快照 | 当前后端用例 3530+ | ⚠️ 历史快照 |
| governance-principles 引用的 G-029 / check-repo-compliance.sh | 文件存在（scripts/check_g_029_test_coverage.py 需确认，.github/scripts/check-repo-compliance.sh 需确认） | 待确认 |

## 4. Q1-4 三份进度日志裁决（指令要求）

| 版本 | 路径 | 证据 | 建议 |
| :--- | :--- | :--- | :--- |
| **权威版** | `docs/archive/项目进度日志.md` | CLAUDE.md L139 指向它；gen_daily_log.py 自动生成（最后更新 07-25） | 保留为权威 |
| 历史快照 | `docs/archive/2026-07-16-historical-plans/项目进度日志.md` | 07-04 快照，已被 archive/ 版覆盖 | 归档保留 |
| 手动版 | `docs/项目进度日志.md` | 07-24 手动维护（Q22-Q23 周期），与自动生成版职责冲突 | **建议合并入权威版后删除**（或明确为"周期总结"单独保留） |

## 5. 治理文档分层建议（供 DOCUMENTATION_MAP 落地）

| 层 | 文档 | 动作 |
| :--- | :--- | :--- |
| 执行手册 | CLAUDE.md | 保留（L0 入口） |
| 技术规格 | trinity-technical-spec-v2.md | 保留（唯一权威规格） |
| 原则 | governance-principles.md | 保留 |
| 总纲-流程 | PROJECT_GOVERNANCE.md | **修 3 处断链引用**（GATE_INDEX/architecture_layers/refactoring_checklist 路径） |
| 状态快照 | governance-overview.md | **降级为历史快照**（标注 2026-07-16，Engine 表失效）或大更新；建议并入 trinity-spec 或标注过期 |
| 门禁清单 | gates.md | 保留（与 CLAUDE.md §3 摘要-详情分工） |

## 6. 操作需求草案（供阶段 B 汇总）

| 动作 | 目标 | 优先级 | 证据 |
| :--- | :--- | :--- | :--- |
| 修断链 | PROJECT_GOVERNANCE.md 3 处失效引用 | P1 | §3 路径验证 |
| 降级/更新 | governance-overview.md（Engine 表 + 快照数据） | P1 | §3 文件不存在验证 |
| 确认 | enforcement/guardrails.py 实现状态（规范标"待实现"但文件存在） | P1 | 文件存在 vs 规范状态 |
| 裁决 | docs/项目进度日志.md（手动版）去留 | P1 | Q1-4 分析 |
| 保留 | governance-principles.md / trinity-spec-v2.md | — | 有效 |
