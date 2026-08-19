# 精读笔记 — 第 7 批（最终批：README 类 / plans / 孤儿扫描）

- **Created**: 2026-08-19T23:20:00+08:00
- **Updated**: 2026-08-19T23:20:00+08:00
- **批次状态**: 待确认（等待精读阶段最终 Gate）
- **精读深度判定留痕**: 依据指令"README 类速核一致性、plans 区分状态、孤儿扫描"→ README 类**结构速核+重点段精读**；plans **状态实证**；孤儿**全局 grep 实证**

---

## 1. README 类文档评估（4 个 + query/README）

| 文档 | 判定 | 说明 |
| :--- | :--- | :--- |
| docs/configuration/README.md（121 行） | ✅ 保留 | config.json 完整 Schema 表（存储/扫描/查询/公告/时效性/熔断/通知），引用 defaults.py 源码位置；入口性质合理，**无"胖 README"问题** |
| docs/deployment/README.md（96 行） | ✅ 保留 | 部署流程（后端/前端/Docker），标准操作指南 |
| docs/observability/README.md（126 行） | ✅ 保留 | 9 个 Metrics 计数器（触发/阈值/排查方向/日志格式）+ query_metrics 表 + Grafana；运维操作手册性质，非业务逻辑 |
| docs/migrations/README.md（133 行） | ✅ 保留 | 迁移版本清单 + 重点迁移说明（v43/v44）+ 执行规范 |
| docs/query/README.md（215 行） | ✅ 保留，⚠️ v2 未反映 | 查询引擎完整文档（ADAPTER_TYPE_MAP 路由链/7 层决策树）——**仍描述 v1 路由**（Q2-3 v2 更新时一并处理）；同时是 modules/query.md L77 断链的**替代目标**（Q2-1，已验证存在） |

**结论**：5 个 README 类均为合理入口/操作文档，无"胖 README"需下沉；唯一待办是 query/README 的 v2 更新（挂 Q2-3）。

## 2. superpowers/plans 状态区分

| 文档 | 状态判定 | 证据 | 处置 |
| :--- | :--- | :--- | :--- |
| 2026-07-23-ttbz-adapter-plan.md（494 行） | ✅ **已执行完毕** | `pilotstd/query/adapters/ttbz.py` 存在（Test-Path True），TTBZ 适配器已实现 | **归档**（对应 design 同为"待审批"但已落地 → 一并归档候选） |
| 2026-08-16-stage5-http-decircularize-plan.md（67 行） | ⚠️ **进行中/部分完成** | 存在未勾选 `- [ ]` 项（app-auth.test.ts）；http.ts 中 registerHttpHandlers 不存在（0 处） | **保留，标记"进行中"** |

## 3. 孤儿文档扫描（全局 grep 实证）

### 3.1 非孤儿（有代码/文档引用，需在地图收录）
| 文档 | 引用方 |
| :--- | :--- |
| spec-lite-template.md | **CLAUDE.md L37**（模板文件） |
| ADR-001-mixin-refactor-16-to-1.md | **tests/test_architecture_mixin_guard.py L36**（⚠️ Q3-1 重编号时**必须同步更新此测试引用**） |
| i18n-troubleshooting-sop.md | scripts/check_i18n_key_count.py L15 |
| v1_vs_v2_routing_comparison.md | scripts/compare_v1_v2_routing.py L6/30（生成脚本） |
| gongbiaoku_search_audit.md | .claude/memory.md（2026-08-17 决策） |

### 3.2 真孤儿但功能性（建议挂入 DOCUMENTATION_MAP 解决孤儿状态）
p3-review-checklist、trinity-how-to-fix、fixture-schema、settings-ui-spec、sppt-8087-assessment、flaky_e2e、engine-mock-guide、skipped_tests_manual_verification、router_v2_feedback、handler-health-report、trinity-system-health-survey、NOTIFICATION_SURVEY_REPORT —— **均无代码/文档引用，但具功能价值 → 地图收录后即"被索引"，不再孤儿**

### 3.3 真孤儿且过时/草稿（归档候选）
- exact_match_refactor_spec.md（草稿，无引用，疑被 ADR-001-mixin 覆盖）
- vulture-dead-code-scan.md（已决策归档）
- site_classification_partial_v1.0.md（已决策归档）
- superpowers/specs 历史系列（07-20~08-14 各 spec-lite/design）：设计留痕，无引用但保留（spec-lite 体系要求）

## 4. 精读阶段总结（第 1-7 批）

### 4.1 覆盖
- **8 批精读**：入口 → 架构 → ADR → 治理 → 设计/指南 → 分析/快照 → README/plans/孤儿 → 剩余归档收尾
- 项目文档 ≈202 个：核心（入口/架构/ADR/治理）**逐字精读**，功能/设计**重点精读**，分析/快照**速读+时效判断**，历史归档**元数据扫描**

### 4.2 主要产出
- 7 份精读笔记（reading_notes_batch_1~7）+ 待确认问题清单（Q1~Q5 系列，多数已闭环）
- **证据链驱动的决策**：ADR 重编号（Q3-1）、断链修复（Q2-1/Q4-2/Q5-2）、口径统一（Q2-2）、路由 v2（Q2-3）、归档清单（Q4-1/Q5-3/Q6）
- **孤儿扫描**：5 个非孤儿（代码引用）+ 12 个功能性孤儿（地图收录）+ 归档候选

### 4.3 待阶段 C 执行的操作汇总（来自 Q1~Q6 决策）
| 类别 | 操作 | 决策来源 |
| :--- | :--- | :--- |
| 重编号 | ADR-001-mixin → ADR-010 + 双向引用 + README/architecture/测试同步 | Q3-1 |
| 补建 | ADR-008/009 独立文件 | Q3-2 |
| 状态统一 | ADR 5 态标记全局替换 | Q3-3 |
| 修复断链 | modules/query.md:77、PROJECT_GOVERNANCE ×3、documentation-policy L104 | Q2-1/Q4-2/Q5-2 |
| 口径统一 | 适配器"21+1"、README 数据、architecture ADR 数 | Q2-2/Q2-4 |
| 归档 | overview→ARCHIVED、specs×2、analysis v1.0、vulture-scan、ttbz-plan、exact-match-spec | Q4-1/Q5-3/Q6/Q7 |
| 更新 | overview 路由 v2、session-store 修订标记、guardrails 状态 | Q2-3/Q5-1/Q4-3 |
| 删除 | docs/项目进度日志.md（手动版，合并后） | Q4-4 |
| 产出 | DOCUMENTATION_MAP.md（含分层体系+治理元规范声明+分析快照区） | 阶段 C |
