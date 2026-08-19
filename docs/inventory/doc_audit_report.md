# 项目文档全面探索报告

> 审计日期：2026-08-19 · 总文档数：266 · 分批处理（每批 20 个）
> 状态：进行中（已完成第 1 批，共 14 批）
>
> **处置原则（2026-08-19 人工确认，后续批次沿用）**
> - ADR 编号冲突 →「待清理 - 重编号」：不自行改名，最终报告单独列出冲突项由人工重排
> - 硬编码路径（.claude/skills/ 等）→「待确认 - 环境依赖」：记录路径与引用位置，不修改
> - 疑似被取代文档 →「待确认 - 可能归档」：注明替代候选文档与判断依据
> - 工具生成产物 →「待清理 - 非项目文档」：建议加入 .gitignore 或从审计范围排除

## 1. 文档分类统计（终值）

| 类型 | 数量 | 说明 |
| :--- | :--- | :--- |
| 架构设计 | 9 | architecture 体系 + adapters/README + query/README |
| 功能规格 | 6 | 通知事件字典、公告 pipeline/sources、fixture-schema、功能规格说明书、模块与功能清单 |
| 操作指南 | 15 | 部署/配置/开发/测试指南等 |
| 治理文档 | 24 | CLAUDE.md、governance/*、门禁/规范/清单 |
| 分析报告 | 17 | 调查/审计/快照/技术债专项 |
| 决策记录 | 13 | ADR 目录（10 个文件含补录 ADR-006/007/008）+ decisions-summary |
| 设计记录 | 17 | superpowers specs/plans + 范式记录 |
| 知识库 | 5 | memory、经验沉淀、进度日志、附录 |
| 模板说明 | 1 | cookiecutter 适配器模板 README |
| 归档/历史 | 64 | CHANGELOG + archive/*（含 scripts/archive/README） |
| 待清理 - 非项目文档 | 49 | .pytest_cache×3、MIGRATION.md、venv 第三方文档 45 |
| 待确认 | 20 | 上表"待确认"状态项（含 README/STATUS/web-README） |

> **审计范围说明**：清单共 266 个文件。其中 `pilotstd_env/`（venv）第三方包自带文档 61 个 + `.pytest_cache/` 3 个为**非项目资产**（建议后续审计排除）；实际项目文档约 202 个。
> 批次覆盖：第 1 批 1-20、第 2 批 21-43、第 3 批 44-93、第 4 批 94-143、第 5 批 144-193、第 6 批 194-243、第 7 批 244-266 —— **1-266 全覆盖**（2026-08-19 复核：补录第二批遗漏的 ADR-006/007/008 共 3 个文件，路径对账零遗漏）。

## 2. 完整文档清单

| # | 路径 | 类型 | 状态 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | .claude/commands/self_review.md | 治理文档 | 保留 | AI 自检命令（Ruff+Mypy 流程），与当前门禁一致 |
| 2 | .claude/instructions.md | 治理文档 | 保留 | Claude 执行守则（技术调研前置），有 G-027 等门禁对应 |
| 3 | .claude/memory.md | 知识库 | 保留 | 结构化知识日志，CI pre-push 检查更新时间，2026-08-19 刚更新 |
| 4 | .claude/skills/commit/SKILL.md | 治理文档 | 待确认 - 环境依赖 | commit 技能流程；引用 `pilotstd_env/Scripts/python.exe`（L13），待确认该环境仍有效 |
| 5 | .github/PULL_REQUEST_TEMPLATE.md | 治理文档 | 保留 | PR 模板，三位一体治理体系执行确认 |
| 6 | .known-issues.md | 分析报告 | 保留 | 已知安全问题（SEC-001 已解决，保留审计轨迹） |
| 7 | .pytest_cache/README.md | 待清理 - 非项目文档 | 删除 | pytest 缓存自动生成，建议加入 .gitignore 或排除 |
| 8 | CHANGELOG.md | 归档/历史 | 保留 | 版本变更日志，持续维护 |
| 9 | CLAUDE.md | 治理文档 | 保留 | 项目核心指令（铁律/SOP/门禁），与 G-037 联动 |
| 10 | CONTRIBUTING.md | 操作指南 | 保留 | 贡献指南（E2E 后端入口、代码组织、pre-commit） |
| 11 | coverage_history/phase2_report.md | 分析报告 | 归档 | Phase2 补测执行报告（2026-08-01），历史性结果 |
| 12 | coverage_report_windows_final.md | 待确认 - 可能归档 | 保留 | Windows 覆盖率基线（2026-08-01，57% 锁定）；替代候选：docs/testing/coverage-report.md（自动生成） |
| 13 | docs/.local/压力测试方案.md | 操作指南 | 保留 | 压测方案 v10.0（975 行），与 tests/stress_driver.py 对应 |
| 14 | docs/adapters/README.md | 架构设计 | 保留 | 适配器维护清单（22 个适配器），注册表引用准确 |
| 15 | docs/adr/ADR-001-mixin-refactor-16-to-1.md | 决策记录 | 待清理 - 重编号 | Mixin 重构 16→1（状态：已关闭）；⚠️ 与 ADR-001-modal-dialog 编号重复 |
| 16 | docs/adr/ADR-001-modal-dialog-auto-clicker.md | 决策记录 | 待清理 - 重编号 | 模态对话框自动处理（已接受）；⚠️ 编号重复（两个 ADR-001） |
| 17 | docs/adr/ADR-002-handler-governance.md | 决策记录 | 保留 | Handler 混合策略治理（已落地） |
| 18 | docs/adr/ADR-003-persistence-pattern.md | 决策记录 | 保留 | 纯逻辑提取范式（已落地） |
| 19 | docs/adr/ADR-004-io-isolation.md | 决策记录 | 保留 | I/O 隔离模式（已落地） |
| 20 | docs/adr/ADR-005-event-bus.md | 决策记录 | 保留 | EventBus 重构（已落地） |
| 21 | docs/adr/README.md | 决策记录 | 保留 | ADR 索引；⚠️ 索引中 ADR-008/009 有编号无文件链接；001 仅引用 modal-dialog 版（印证编号冲突） |
| 22 | docs/analysis/gongbiaoku_search_audit.md | 分析报告 | 保留 | gongbiaoku 搜索排查（根因类型 B，search_reliability=medium），与 memory 2026-08-17 决策对应 |
| 23 | docs/analysis/query_metrics_routing_mismatch_20260816.md | 分析报告 | 保留 | std 路由错配根因分析存档；用途声明：未来重启路由优化时作上下文 |
| 24 | docs/analysis/site_classification_partial.md | 分析报告 | 保留 | 站点分类 v1.1（当前版本，含 ISO 试查询验证） |
| 25 | docs/analysis/site_classification_partial_v1.0.md | 分析报告 | 合并/归档 | v1.0 历史版本，已被 v1.1 明确取代（v1.1 首部标注历史版本） |
| 26 | docs/analysis/v1_cleanup_readiness.md | 分析报告 | 保留 | v1 清理安全评估（结论：需补充 v2 灰度数据后重评），动态文档 |
| 27 | docs/analysis/v1_vs_v2_routing_comparison.md | 分析报告 | 保留 | v1 vs v2 路由对比（10 个真实 Query） |
| 28 | docs/architecture.md | 架构设计 | 待确认 | 架构决策记录（Handler 组合模式等）；⚠️ 与 docs/adr/ 目录及 modules/overview 功能重叠，待确认分工 |
| 29 | docs/architecture/exact_match_refactor_spec.md | 设计记录 | 待确认 - 可能归档 | ExactMatchMixin 重构立项方案（草稿 2026-08-04）；待确认是否已被 ADR-001-mixin-refactor 覆盖落地 |
| 30 | docs/architecture/governance-summary.md | 分析报告 | 归档 | G-010 代码规模治理汇总（2026-06-28~30 历史治理记录） |
| 31 | docs/architecture/modules/manager.md | 架构设计 | 保留 | Manager 模块文档（G-031 映射），模块文档体系成员 |
| 32 | docs/architecture/modules/parser.md | 架构设计 | 待确认 | Parser 模块文档；⚠️ G-031 映射 `pilotstd/core/parser.py` 与模块路径 `pilotstd/scan/parser/` 不一致 |
| 33 | docs/architecture/modules/query.md | 架构设计 | 待确认 | Query 适配器模块文档；⚠️ 适配器数 8（7生产+1Mock）与 docs/adapters/README.md 的 22 不一致（可能统计口径不同） |
| 34 | docs/architecture/modules/scan.md | 架构设计 | 待确认 | Scan 模块文档；⚠️ 自注"实际模块在 pilotstd/scan/ 而非 core/"（G-031 映射存疑） |
| 35 | docs/architecture/modules/ui.md | 架构设计 | 保留 | UI 主窗口模块文档（Handler 组合模式） |
| 36 | docs/architecture/overview.md | 架构设计 | 待确认 | 架构总览（2026-07-27）；⚠️ 技术栈表 Python 3.11+，实际环境 Python 3.14（待确认） |
| 37 | docs/architecture/refactoring-analysis.md | 分析报告 | 归档 | 大文件包化分析（2026-06-30 已完成，自注合并已归档文档） |
| 38 | docs/architecture/technical-debt-registry.md | 治理文档 | 保留 | 技术债登记簿（维护规则明确，已跳过的测试 13 项） |
| 39 | docs/archive/2026-07-16-audit-reports/2026-07-03-win-startup-issues-investigation.md | 归档/历史 | 保留 | Win 启动问题调查（2026-07-03，已在 archive） |
| 40 | docs/archive/2026-07-16-audit-reports/app_websocket_audit.md | 归档/历史 | 保留 | WebSocket 审计（2026-06-29，已在 archive） |
| 41 | docs/archive/2026-07-16-audit-reports/ci_test_failure_investigation.md | 归档/历史 | 保留 | CI 测试失败调查（2026-06-29，已在 archive） |
| 42 | docs/archive/2026-07-16-audit-reports/cicd_inventory.md | 归档/历史 | 保留 | CI/CD 现状调查（2026-06-29，已在 archive） |
| 43 | docs/archive/2026-07-16-audit-reports/frontend_5features_status.md | 归档/历史 | 保留 | 前端 5 项功能状态调查（2026-06-29） |
| 44 | docs/archive/2026-07-16-audit-reports/frontend_polling_report.md | 归档/历史 | 保留 | 前端轮询机制调查（2026-06-28） |
| 45 | docs/archive/2026-07-16-audit-reports/licenses.md | 归档/历史 | 保留 | 依赖许可证清单（合规性参考） |
| 46 | docs/archive/2026-07-16-audit-reports/notification_trigger_candidates.md | 待确认 - 可能过时 | 保留 | 通知触发点候选清单（2026-06-28）；候选替代：docs/notification_event_dictionary.md（Q20 重构 2026-07-22） |
| 47 | docs/archive/2026-07-16-audit-reports/security_audit.md | 归档/历史 | 保留 | 安全审计报告（2026-06-29，三批修复完成） |
| 48 | docs/archive/2026-07-16-audit-reports/validity_checker_current_state.md | 待确认 - 可能过时 | 保留 | validity_checker 规则全览（2026-06-28）；时效性检查经 Q20 重构，规则可能已变 |
| 49 | docs/archive/2026-07-16-audit-reports/存量资产审计与去重行动计划书.md | 归档/历史 | 保留 | 存量资产审计与去重计划（2026-06-18） |
| 50 | docs/archive/2026-07-16-historical-plans/2026-06-11-stress-test-fixes.md | 归档/历史 | 保留 | 压测修复+启动优化实现计划（538 行，已完成的历史计划） |
| 51 | docs/archive/2026-07-16-historical-plans/2026-06-13-auto-pipeline-chain-fix.md | 归档/历史 | 保留 | 三表现层统一重构计划（773 行，已完成） |
| 52 | docs/archive/2026-07-16-historical-plans/2026-06-14-stress-fix-and-dedup.md | 归档/历史 | 保留 | 压测修复+重复代码清理计划（已完成） |
| 53 | docs/archive/2026-07-16-historical-plans/2026-06-15-batch2-fixes-design.md | 归档/历史 | 保留 | 待修清单第二批修复设计（状态：待实施→已完成） |
| 54 | docs/archive/2026-07-16-historical-plans/2026-06-15-batch2-fixes-plan.md | 归档/历史 | 保留 | 待修清单第二批修复实施计划（267 行，已完成） |
| 55 | docs/archive/2026-07-16-historical-plans/2026-06-15-quality-checker-design.md | 归档/历史 | 保留 | 代码质量检查框架设计（190 行） |
| 56 | docs/archive/2026-07-16-historical-plans/2026-06-15-quality-checker-plan.md | 归档/历史 | 保留 | 质量检查框架实现计划（931 行） |
| 57 | docs/archive/2026-07-16-historical-plans/2026-06-15-workflow-enforcement-design.md | 归档/历史 | 保留 | 规则执行强制机制设计（Hook 阻断+CLAUDE.md 触发重写） |
| 58 | docs/archive/2026-07-16-historical-plans/2026-06-15-workflow-enforcement-plan.md | 归档/历史 | 保留 | 规则执行强制机制实施计划（221 行） |
| 59 | docs/archive/2026-07-16-historical-plans/2026-06-16-全量压力测试计划.md | 归档/历史 | 保留 | 全量压测执行计划（43 行） |
| 60 | docs/archive/2026-07-16-historical-plans/2026-06-16-全量压力测试设计.md | 归档/历史 | 保留 | 全量压测执行设计（80 行） |
| 61 | docs/archive/2026-07-16-historical-plans/2026-06-16-压测问题修复计划.md | 归档/历史 | 保留 | 压测问题修复实现计划（252 行） |
| 62 | docs/archive/2026-07-16-historical-plans/2026-06-16-压测问题修复设计.md | 归档/历史 | 保留 | 压测问题修复设计（59 行） |
| 63 | docs/archive/2026-07-16-historical-plans/2026-06-17-ahbz-adapter-fix-design.md | 归档/历史 | 保留 | ahbz 适配器修复设计（124 行） |
| 64 | docs/archive/2026-07-16-historical-plans/2026-06-17-ahbz-adapter-fix-plan.md | 归档/历史 | 保留 | ahbz 适配器修复实施计划（537 行） |
| 65 | docs/archive/2026-07-16-historical-plans/2026-06-17-bucket-query-design.md | 归档/历史 | 保留 | 逐桶查询设计 V2（155 行） |
| 66 | docs/archive/2026-07-16-historical-plans/2026-06-18-test-fix-and-optimize-design.md | 归档/历史 | 保留 | 测试修复与优化设计（97 行） |
| 67 | docs/archive/2026-07-16-historical-plans/2026-06-18-test-fix-and-quality-plan.md | 归档/历史 | 保留 | 测试修复+引擎清理计划（807 行） |
| 68 | docs/archive/2026-07-16-historical-plans/2026-06-25-docker-auto-update-design.md | 归档/历史 | 保留 | Docker 重启即更新设计（48 行） |
| 69 | docs/archive/2026-07-16-historical-plans/2026-06-25-docker-auto-update-plan.md | 归档/历史 | 保留 | Docker 重启即更新实现计划（89 行） |
| 70 | docs/archive/2026-07-16-historical-plans/2026-06-25-web-four-pages-design.md | 归档/历史 | 保留 | Web 四独立页面设计（通知配置/日志/状态/时效性，70 行） |
| 71 | docs/archive/2026-07-16-historical-plans/2026-06-25-web-four-pages-plan.md | 归档/历史 | 保留 | Web 四页面实现计划（15 行） |
| 72 | docs/archive/2026-07-16-historical-plans/2026-07-01-build-isolation-design.md | 归档/历史 | 保留 | 桌面端/服务端构建体系隔离设计 v2（121 行） |
| 73 | docs/archive/2026-07-16-historical-plans/2026-07-01-build-isolation-plan.md | 归档/历史 | 保留 | 构建体系隔离重构实现计划（520 行） |
| 74 | docs/archive/2026-07-16-historical-plans/2026-07-09-migration-hardening-design.md | 归档/历史 | 保留 | 数据库迁移机制加固设计（36 行） |
| 75 | docs/archive/2026-07-16-historical-plans/2026-07-09-migration-hardening-plan.md | 归档/历史 | 保留 | 迁移机制加固实施计划（406 行） |
| 76 | docs/archive/2026-07-16-historical-plans/2026-07-12-notification-per-user-design.md | 归档/历史 | 保留 | 通知渠道按用户隔离设计 v1.1（139 行）；**已落地**（user_credentials/notification_policy 表） |
| 77 | docs/archive/2026-07-16-historical-plans/2026-07-12-notification-per-user-plan.md | 归档/历史 | 保留 | 通知按用户隔离实施计划（690 行）；已落地 |
| 78 | docs/archive/2026-07-16-historical-plans/2026-07-13-moviepilot-persistence-analysis.md | 归档/历史 | 保留 | MoviePilot 持久化策略分析（347 行，外部参考） |
| 79 | docs/archive/2026-07-16-historical-plans/architecture_migration_review.md | 归档/历史 | 保留 | 架构重构迁移完整性专项审查（85 行） |
| 80 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/architecture_compliance_audit.md | 归档/历史 | 保留 | 架构合规性审计（110 行，已被 refactoring-analysis.md 合并归档） |
| 81 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/architecture_layers.md | 归档/历史 | 保留 | 四层架构定义 v2.0（235 行，早期架构定义） |
| 82 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/code_smell_audit.md | 归档/历史 | 保留 | 废弃 API 与代码异味扫描（95 行） |
| 83 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/config_structure_analysis.md | 归档/历史 | 保留 | core/config.py 结构分析（90 行） |
| 84 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/db_structure_analysis.md | 归档/历史 | 保留 | core/db.py 结构分析（119 行） |
| 85 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/development.md | 待确认 - 可能过时 | 保留 | 旧开发指南（99 行）；候选替代：docs/development.md（待确认是否已取代） |
| 86 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/facade_analysis.md | 归档/历史 | 保留 | manager/facade.py 结构分析（137 行） |
| 87 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/folder_inventory.md | 归档/历史 | 保留 | 项目文件夹现状调查（303 行） |
| 88 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/function_split_plan.md | 归档/历史 | 保留 | 剩余函数拆分分析（249 行） |
| 89 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/functionality_inventory.md | 归档/历史 | 保留 | 业务功能现状调查（116 行） |
| 90 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/GATE_INDEX.md | 待确认 - 可能过时 | 保留 | 旧门禁索引 v1.0（195 行）；候选替代：docs/governance/gates.md（待确认） |
| 91 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/main_window_analysis.md | 归档/历史 | 保留 | ui/main_window.py 结构分析（84 行，已被 refactoring-analysis.md 合并） |
| 92 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/notification_system_status.md | 归档/历史 | 保留 | 通知系统实现状态报告（2026-06-29，纯调查）；⚠️ 通知系统经 Q20 重构，内容过时 |
| 93 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/organizer_service_analysis.md | 归档/历史 | 保留 | organizer_service 结构分析（86 行） |
| 94 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/parser_analysis.md | 归档/历史 | 保留 | scan/parser.py 结构分析（113 行） |
| 95 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/query_engine_analysis.md | 归档/历史 | 保留 | query/engine.py 结构分析（103 行） |
| 96 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/query_mixin_analysis.md | 归档/历史 | 保留 | query_mixin 结构分析（69 行） |
| 97 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/README.md | 归档/历史 | 保留 | 归档说明（GATE-15 治理完成，47 行） |
| 98 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/代码功能明细说明书.md | 归档/历史 | 保留 | 代码功能明细说明书 v1.3（2026-05-31，基于 67 文件 12,400 行）；⚠️ 代码已大改，内容过时 |
| 99 | docs/archive/2026-07-16-historical-plans/old-archive/2026-06-30/模块划分方案.md | 归档/历史 | 保留 | 早期模块划分方案（231 行） |
| 100 | docs/archive/2026-07-16-historical-plans/项目进度日志.md | 归档/历史 | 保留 | 历史进度日志（2026-07-04）；⚠️ 与 docs/archive/项目进度日志.md 并存，见 §7 |
| 101 | docs/archive/项目进度日志.md | 知识库 | 保留 | 项目进度日志（最后更新 2026-07-25，gen_daily_log.py 自动生成）；⚠️ 与 historical-plans/项目进度日志.md 重复，见 §7 |
| 102 | docs/ci-lessons.md | 治理文档 | 保留 | CI 修复经验总结（2026-08-20 更新，CLAUDE.md 引用） |
| 103 | docs/configuration/README.md | 操作指南 | 保留 | 系统配置说明（2026-07-27） |
| 104 | docs/deployment/README.md | 操作指南 | 保留 | 部署运维指南（2026-07-27） |
| 105 | docs/design/site_classification_v1.md | 设计记录 | 保留 | 站点分类方案 v1.1（被 analysis/site_classification_partial.md 引用为方案版本） |
| 106 | docs/development.md | 待确认 - 可能过时 | 保留 | 开发指南（2026-06-30）；⚠️ 仍描述 v0.54.0 的 4 个 Mixin（已重构为 Handler，ADR-001/002）；引用 docs/specs/模块与功能清单.md（路径待确认） |
| 107 | docs/development/documentation-policy.md | 治理文档 | 保留 | 文档同步策略（2026-06-30） |
| 108 | docs/development/g-010-enforcement.md | 治理文档 | 保留 | G-010 代码规模控制规则 v1.0（门禁详情）；⚠️ 与 governance/gates.md 的 G-010 条目为详情 vs 索引关系 |
| 109 | docs/development/session-store-design.md | 设计记录 | 保留 | 服务端会话存储设计 v1.0（2026-06-30）；已落地（docker/auth 会话管理） |
| 110 | docs/flaky_e2e.md | 分析报告 | 保留 | 不稳定 E2E 用例追踪（9 行，运维记录） |
| 111 | docs/governance/archive_migration_protocol.md | 治理文档 | 保留 | 归档迁移协议（零能力静默丢失） |
| 112 | docs/governance/capabilities_registry.md | 治理文档 | 保留 | 能力登记簿（自动生成，2026-08-19 更新） |
| 113 | docs/governance/development-flow.md | 治理文档 | 保留 | 决策请求规范（CLAUDE.md 引用） |
| 114 | docs/governance/file-inclusion-criteria.md | 治理文档 | 保留 | 文件入仓判断标准 |
| 115 | docs/governance/gates.md | 治理文档 | 保留 | 门禁清单索引（核心；⚠️ G-032 曾警告其引用不存在的 index.md/coverage-report.md，属既有警告） |
| 116 | docs/governance/governance-principles.md | 治理文档 | 保留 | 治理体系原则 |
| 117 | docs/governance/p3-review-checklist.md | 治理文档 | 保留 | P3 人工审查 Checklist |
| 118 | docs/governance/phase1-startup-checklist.md | 治理文档 | 保留 | Phase1 启动检查清单 v2.1 |
| 119 | docs/governance/PROJECT_GOVERNANCE.md | 待确认 - 可能过时 | 保留 | 项目治理总纲 v1.0（2026-06-29）；⚠️ 引用已迁移文件（docs/archive/2026-06-30/GATE_INDEX.md、docs/architecture_layers.md 均不存在），候选替代：governance-overview.md（v1.0.0） |
| 120 | docs/governance/prompt-crafting-guide.md | 治理文档 | 保留 | 提示词生产规范 |
| 121 | docs/governance/README.md | 治理文档 | 保留 | 治理文档中心索引 |
| 122 | docs/governance/rule-quickref.md | 治理文档 | 保留 | 非技术决策者规则速查表 |
| 123 | docs/governance/trinity-how-to-fix.md | 治理文档 | 保留 | Trinity 门禁修复指引 |
| 124 | docs/governance/trinity-technical-spec-v2.md | 治理文档 | 保留 | 三位一体技术规范 v2.1（已评审可执行） |
| 125 | docs/governance-overview.md | 治理文档 | 保留 | 治理体系总览 v1.0.0（2026-07-16，已落地）；⚠️ 内含测试数字为历史快照（942 passed 等） |
| 126 | docs/guides/cleanup-io-isolation-2.0.md | 设计记录 | 保留 | I/O 隔离 2.0 范式（P5-4 验证） |
| 127 | docs/guides/Docker使用指南.md | 操作指南 | 待确认 | Docker 使用指南（v1.0）；⚠️ 与 docs/deployment/README.md 内容重叠，见 §7 |
| 128 | docs/guides/download-flow-engine-pattern.md | 设计记录 | 保留 | 下载流纯逻辑提取范式（P5-3 验证） |
| 129 | docs/guides/persistence-engine-pattern.md | 设计记录 | 保留 | UI 持久化纯逻辑提取范式（P5-1 验证） |
| 130 | docs/guides/query-summary-engine-pattern.md | 设计记录 | 保留 | 数据分组纯逻辑提取范式（P5-5 验证） |
| 131 | docs/guides/refactoring-lessons.md | 知识库 | 保留 | 大函数拆分经验记录 |
| 132 | docs/guides/settings-io-engine-pattern.md | 设计记录 | 保留 | 配置管理纯逻辑提取范式（P5-2 验证） |
| 133 | docs/guides/人工测试方案.md | 操作指南 | 保留 | 人工测试方案 v3.1 |
| 134 | docs/guides/用户帮助文档.md | 操作指南 | 保留 | 用户帮助文档 v0.2.0 |
| 135 | docs/history/decisions-summary.md | 决策记录 | 保留 | 历史决策摘要（提炼自 historical-plans，仅收录采纳决策） |
| 136 | docs/index.md | 治理文档 | 保留 | 文档索引（CLAUDE.md 引用"不确定该读什么"入口） |
| 137 | docs/issues/router_v2_feedback.md | 分析报告 | 保留 | router_v2 能力模型反馈（memory 2026-08-17 引用） |
| 138 | docs/MIGRATION.md | 待清理 | 保留 | ⚠️ 自声明"临时迁移说明，将于 2026-10-16 删除"（101 行） |
| 139 | docs/migrations/README.md | 操作指南 | 保留 | 数据库迁移说明（2026-07-27，最新迁移 v44） |
| 140 | docs/notification_event_dictionary.md | 功能规格 | 保留 | 通知事件字典（Q20，32 事件，2026-07-22）；本次修复已核验与代码一致 |
| 141 | docs/observability/README.md | 操作指南 | 保留 | 监控与可观测性说明（2026-07-27） |
| 142 | docs/pending/NOTIFICATION_SURVEY_REPORT.md | 待确认 - 可能过时 | 保留 | 通知系统现状调查（2026-07-01）；⚠️ Q20 通知重构（07-22）前调查，内容已过时；pending/ 目录语义"待定"待人工决策 |
| 143 | docs/plans/P10_plan.md | 设计记录 | 建议归档 | P10 补全闭环计划；⚠️ 已闭环（2026-07-17/18 多轮记录），按 plans/README 规则应提炼 ADR 后归档 |
| 144 | docs/plans/README.md | 治理文档 | 保留 | 计划文档目录说明（仅 Active 计划） |
| 145 | docs/query/README.md | 架构设计 | 保留 | 查询引擎完整文档（2026-07-27） |
| 146 | docs/reference/adapter-development.md | 操作指南 | 保留 | 适配器开发指南（CLAUDE.md/G-025 引用，仍生效） |
| 147 | docs/reference/announcement-pipeline.md | 功能规格 | 保留 | 公告解析入库流程（CLAUDE.md 引用，仍生效） |
| 148 | docs/reference/announcement-sources.md | 功能规格 | 保留 | 公告来源标识映射表（自述唯一真相源，仍生效） |
| 149 | docs/reference/coding-standards.md | 治理文档 | 保留 | 编码规范（CLAUDE.md 引用，仍生效） |
| 150 | docs/reference/fixture-schema.md | 功能规格 | 保留 | 适配器 Fixture 统一 Schema v1.0（2026-07-24） |
| 151 | docs/reference/i18n-troubleshooting-sop.md | 操作指南 | 保留 | i18n 排查 SOP（PR 模板引用，关联技术债 #3） |
| 152 | docs/reference/pre-commit-checklist.md | 治理文档 | 保留 | 提交前自检清单（CLAUDE.md 引用，仍生效） |
| 153 | docs/reference/settings-ui-spec.md | 设计记录 | 保留 | Settings UI 组件规范（2026-08-05 根因调查沉淀） |
| 154 | docs/reference/sppt-8087-assessment.md | 待确认 | 保留 | SPPT 8087 平台评估（Task 0 完成，状态"待适配器立项"）；需确认是否已立项/实施 |
| 155 | docs/reference/ui-components.md | 设计记录 | 保留 | 前端 UI 组件规范（CLAUDE.md 引用） |
| 156 | docs/reference/版本管理规范.md | 治理文档 | 保留 | 语义化版本管理规范（Active） |
| 157 | docs/reference/附录一 标准代号完整清单.md | 知识库 | 保留 | 标准代号完整清单（Active，190 行） |
| 158 | docs/reference/环境需求.md | 操作指南 | 保留 | 环境需求 v1.0（Active） |
| 159 | docs/skipped_tests_manual_verification.md | 分析报告 | 保留 | Q20 字段一致性人工验证（2026-07-22）；本次修复已更新引用 |
| 160 | docs/specs/功能规格说明书.md | 待确认 - 可能过时 | 保留 | 功能规格说明书（690 行）；⚠️ 版本历史停留在 1.15（2026-06-16），7-8 月大量重构未反映，建议归档或重大更新 |
| 161 | docs/specs/模块与功能清单.md | 待确认 - 可能过时 | 保留 | 模块与功能清单（2026-06-30，被 docs/development.md 引用）；⚠️ 06-30 后 Mixin→Handler/Q22 适配器重构未反映 |
| 162 | docs/superpowers/plans/2026-07-23-ttbz-adapter-plan.md | 设计记录 | 待确认 | TTBZ 适配器实现计划（494 行）；⚠️ 对应 design 状态"待审批"，需确认适配器是否已实施（若已实施应归档） |
| 163 | docs/superpowers/plans/2026-08-16-stage5-http-decircularize-plan.md | 设计记录 | 保留 | 阶段5 HTTP 解耦实现计划（近期，对应 design） |
| 164 | docs/superpowers/reports/ci-risk-investigation-2026-08-06.md | 分析报告 | 保留 | GitHub CI 风险调查（2026-08-06） |
| 165 | docs/superpowers/specs/2026-07-20-g010-manual-split-design.md | 设计记录 | 保留 | G-010 补充拆分设计（12 文件手动拆分，已执行） |
| 166 | docs/superpowers/specs/2026-07-23-ttbz-adapter-design.md | 设计记录 | 待确认 | TTBZ 适配器设计（状态：待审批）；需确认是否已批准实施 |
| 167 | docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md | 设计记录 | 保留 | Q22-Q23 适配器批量开发总结（14 适配器 + 1 重构） |
| 168 | docs/superpowers/specs/2026-07-24-q22-q23-adapters-summary.md | 设计记录 | 合并 | ⚠️ 与 adapter-batch-q22-q23-summary 同日期同主题（14 适配器+1 重构），内容高度重复 |
| 169 | docs/superpowers/specs/2026-07-25-sysfix-trinity-hardening-spec-lite.md | 设计记录 | 保留 | 三位一体体系加固 spec-lite |
| 170 | docs/superpowers/specs/2026-07-30-vulture-dead-code-scan.md | 分析报告 | 保留 | Vulture 死代码扫描报告（handlers 目录） |
| 171 | docs/superpowers/specs/2026-08-14-validity-form-ui-refactor-spec-lite.md | 设计记录 | 保留 | 时效性表单 UI 重构 spec-lite（近期） |
| 172 | docs/superpowers/specs/2026-08-16-floating-button-drag-design.md | 设计记录 | 保留 | 悬浮按钮拖拽 spec-lite |
| 173 | docs/superpowers/specs/2026-08-16-rotated-logs-access-design.md | 设计记录 | 保留 | 轮转日志访问端点 spec-lite |
| 174 | docs/superpowers/specs/2026-08-16-stage5-http-decircularize-design.md | 设计记录 | 保留 | 阶段5 HTTP 解耦设计（架构变更） |
| 175 | docs/superpowers/specs/2026-08-16-task-progress-restore-design.md | 设计记录 | 保留 | 任务进度丢失修复 spec-lite |
| 176 | docs/superpowers/specs/2026-08-19-announce-notification-chain-fix-spec-lite.md | 设计记录 | 保留 | ⚠️ 本次任务生成 spec-lite（2026-08-19） |
| 177 | docs/superpowers/specs/spec-lite-template.md | 设计记录 | 保留 | spec-lite 模板 |
| 178 | docs/technical-debt.md | 治理文档 | 保留 | 技术债登记摘要（活跃维护，最后登记 2026-08-15）；与 technical-debt-registry.md 为摘要-详情分工（非重复） |
| 179 | docs/testing/coverage-report.md | 归档/历史 | 保留 | 覆盖率报告（自动生成产物，2026-08-19） |
| 180 | docs/testing/e2e-guide.md | 操作指南 | 保留 | E2E 测试指南（HTTP 边界集成） |
| 181 | docs/testing/e2e-test-manifest.md | 知识库 | 保留 | E2E 测试用例索引（2026-07-16） |
| 182 | docs/testing/engine-mock-guide.md | 操作指南 | 保留 | Engine/DB Mock 基础设施指南 |
| 183 | docs/testing/handler-health-report-2026-08-02.md | 分析报告 | 保留 | Handler 健康度报告（快照 2026-08-02） |
| 184 | docs/testing/integration-guide.md | 操作指南 | 保留 | 集成测试编写指南（HTTP 状态机） |
| 185 | docs/testing/known-issues.md | 分析报告 | 保留 | 测试已知问题（与根目录 .known-issues.md 主题不同，保留） |
| 186 | docs/testing/playbook.md | 知识库 | 保留 | GUI 层测试实战经验沉淀 |
| 187 | docs/testing/project-coverage-survey-2026-07-31.md | 分析报告 | 保留 | 覆盖率现状调查（305 行，快照） |
| 188 | docs/testing/testing-baseline.md | 治理文档 | 保留 | E2E+集成测试基线（每季度回顾） |
| 189 | docs/testing/trinity-system-health-survey-2026-07-31.md | 分析报告 | 保留 | 三位一体体系现状调查（317 行，快照） |
| 190 | docs/testing/下载适配器测试方案.md | 操作指南 | 保留 | 下载适配器测试方案 |
| 191 | docs/项目进度日志.md | 知识库 | 保留 | ⚠️ **第三份项目进度日志**（docs/ 根目录，最后更新 2026-07-24 Q22-Q23 周期）；与 historical-plans/、archive/ 两份并存，见 §7 |
| 192 | http-requests-inventory.md | 待确认 - 可能过时 | 保留 | HTTP 请求迁移清单（web/src 扫描产物，阶段 2.1）；⚠️ 与 2026-08-16 stage5-http-decircularize 计划关联，需确认迁移是否已完成 |
| 193 | local-session-notes.md | 待确认 | 保留 | 会话决策记录文件（development-flow.md §4.3 引用）；⚠️ 当前为空白文件，需确认是否仍在使用 |
| 194 | pilotstd/templates/adapter/{{ cookiecutter.adapter_name }}/README.md | 模板说明 | 保留 | cookiecutter 适配器模板自带说明（含 Jinja2 变量）；⚠️ 属代码模板组成部分（区别于独立文档），非项目说明文档 |
| 195 | pilotstd_env/Lib/site-packages/cookiecutter-2.7.1.dist-info/licenses/AUTHORS.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（cookiecutter AUTHORS） |
| 196 | pilotstd_env/Lib/site-packages/cyclonedx/contrib/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（cyclonedx） |
| 197 | pilotstd_env/Lib/site-packages/cyclonedx/schema/_res/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（cyclonedx schema） |
| 198 | pilotstd_env/Lib/site-packages/ddddocr/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（ddddocr） |
| 199 | pilotstd_env/Lib/site-packages/easyocr/DBNet/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（easyocr） |
| 200 | pilotstd_env/Lib/site-packages/fastapi/.agents/skills/fastapi/references/dependencies.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（fastapi agents） |
| 201 | pilotstd_env/Lib/site-packages/fastapi/.agents/skills/fastapi/references/other-tools.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（fastapi agents） |
| 202 | pilotstd_env/Lib/site-packages/fastapi/.agents/skills/fastapi/references/streaming.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（fastapi agents） |
| 203 | pilotstd_env/Lib/site-packages/fastapi/.agents/skills/fastapi/SKILL.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（fastapi agents） |
| 204 | pilotstd_env/Lib/site-packages/flask/sansio/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（flask） |
| 205 | pilotstd_env/Lib/site-packages/httpcore-1.0.9.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（httpcore） |
| 206 | pilotstd_env/Lib/site-packages/httpx-0.28.0.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（httpx） |
| 207 | pilotstd_env/Lib/site-packages/idna-3.15.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（idna） |
| 208 | pilotstd_env/Lib/site-packages/lazy_loader-0.5.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（lazy_loader） |
| 209 | pilotstd_env/Lib/site-packages/mypy/typeshed/stdlib/_typeshed/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（mypy typeshed） |
| 210 | pilotstd_env/Lib/site-packages/numpy/random/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy） |
| 211 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/_core/src/npysort/x86-simd-sort/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 212 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/fft/pocketfft/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 213 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 214 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/src/distributions/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 215 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/src/mt19937/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 216 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/src/pcg64/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 217 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/src/philox/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 218 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/src/sfc64/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 219 | pilotstd_env/Lib/site-packages/numpy-2.4.4.dist-info/licenses/numpy/random/src/splitmix64/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（numpy 子组件） |
| 220 | pilotstd_env/Lib/site-packages/olefile/doc/API.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 API 文档（olefile） |
| 221 | pilotstd_env/Lib/site-packages/olefile/doc/Contribute.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（olefile） |
| 222 | pilotstd_env/Lib/site-packages/olefile/doc/Home.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（olefile） |
| 223 | pilotstd_env/Lib/site-packages/olefile/doc/Install.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（olefile） |
| 224 | pilotstd_env/Lib/site-packages/olefile/doc/License.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（olefile） |
| 225 | pilotstd_env/Lib/site-packages/olefile/doc/OLE_Overview.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（olefile） |
| 226 | pilotstd_env/Lib/site-packages/onnxruntime/Privacy.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（onnxruntime） |
| 227 | pilotstd_env/Lib/site-packages/onnxruntime/tools/mobile_helpers/coreml_supported_mlprogram_ops.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（onnxruntime） |
| 228 | pilotstd_env/Lib/site-packages/onnxruntime/tools/mobile_helpers/coreml_supported_neuralnetwork_ops.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（onnxruntime） |
| 229 | pilotstd_env/Lib/site-packages/onnxruntime/tools/mobile_helpers/nnapi_supported_ops.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（onnxruntime） |
| 230 | pilotstd_env/Lib/site-packages/pip/_vendor/idna/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（pip 内置 idna） |
| 231 | pilotstd_env/Lib/site-packages/pip-26.1.1.dist-info/licenses/src/pip/_vendor/idna/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（pip 内置 idna） |
| 232 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/element-attributes.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 233 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/playwright-tests.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 234 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/request-mocking.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 235 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/running-code.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 236 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/session-management.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 237 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/spec-driven-testing.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 238 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/storage-state.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 239 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/test-generation.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 240 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/tracing.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 241 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/references/video-recording.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 242 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/cli-client/skill/SKILL.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright cli-client） |
| 243 | pilotstd_env/Lib/site-packages/playwright/driver/package/lib/tools/trace/SKILL.md | 待清理 - 非项目文档 | 排除 | AI 工具自带 skill 文档（playwright trace） |
| 244 | pilotstd_env/Lib/site-packages/playwright/driver/package/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（playwright driver） |
| 245 | pilotstd_env/Lib/site-packages/playwright/driver/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（playwright driver） |
| 246 | pilotstd_env/Lib/site-packages/pyparsing/ai/best_practices.md | 待清理 - 非项目文档 | 排除 | venv 第三方包文档（pyparsing） |
| 247 | pilotstd_env/Lib/site-packages/pyzmq-27.1.0.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（pyzmq） |
| 248 | pilotstd_env/Lib/site-packages/respx-0.23.1.dist-info/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（respx） |
| 249 | pilotstd_env/Lib/site-packages/scipy/fft/_duccfft/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（scipy 子组件） |
| 250 | pilotstd_env/Lib/site-packages/soupsieve-2.8.3.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（soupsieve） |
| 251 | pilotstd_env/Lib/site-packages/starlette-1.3.1.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（starlette） |
| 252 | pilotstd_env/Lib/site-packages/torchgen/packaged/autograd/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（torchgen） |
| 253 | pilotstd_env/Lib/site-packages/uvicorn-0.46.0.dist-info/licenses/LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（uvicorn） |
| 254 | pilotstd_env/Lib/site-packages/werkzeug/debug/shared/ICON_LICENSE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包许可文件（werkzeug 图标） |
| 255 | pilotstd_env/Lib/site-packages/win32comext/mapi/NOTICE.md | 待清理 - 非项目文档 | 排除 | venv 第三方包通知文件（win32comext） |
| 256 | pilotstd_env/Lib/site-packages/zmq/backend/cffi/README.md | 待清理 - 非项目文档 | 排除 | venv 第三方包 README（zmq） |
| 257 | README.md | 待确认 - 部分过时 | 保留 | 项目入口 README；⚠️ 数据过时：badge "Tests-942 passed"（历史）、"python-3.12+"（实际 3.14）、"6 个适配器"（实际 22）；✅ 引用路径全部有效（LICENSE/screenshots/desktop-requirements/docker-compose 已验证） |
| 258 | scripts/archive/README.md | 归档/历史 | 保留 | 归档脚本说明（migrate_preferences 已历史备份，3 行） |
| 259 | STATUS.md | 待确认 | 保留 | 项目状态（自动生成 generate_status_metrics.py，**未入 git**）；⚠️ 自述"本地状态文件，不入仓库"与自动生成并存；覆盖率 0.0%（生成时机问题）；HEAD commit b043a288 过时 |
| 260 | tech_debt_linux_ci.md | 分析报告 | 保留 | Linux CI 技术债专项（Windows 覆盖率任务交付物，113 行） |
| 261 | tests/.pytest_cache/README.md | 待清理 - 非项目文档 | 排除 | pytest 缓存产物 |
| 262 | web/.pytest_cache/README.md | 待清理 - 非项目文档 | 排除 | pytest 缓存产物 |
| 263 | web/README.md | 待清理 | 保留 | ⚠️ **Vite 默认模板 README**（未定制，5 行，Vue3 模板说明与项目无关，未入 git）；建议替换为项目专属说明或删除 |
| 264 | docs/adr/ADR-006-ui-hold-strategy.md | 决策记录 | 保留 | 纯 UI 编排文件维持策略（已落地，53 行）；【补录：第二批遗漏】 |
| 265 | docs/adr/ADR-007-favorite-archive-decouple.md | 决策记录 | 保留 | 收藏与归档下载解耦（已落地，101 行）；【补录：第二批遗漏】 |
| 266 | docs/adr/ADR-008-wait-worker-elimination.md | 决策记录 | 保留 | GUI 测试 _wait_worker 消除（已落地，81 行）；【补录：第二批遗漏】 |

## 3. 建议清理清单

| 路径 | 建议 | 理由 |
| :--- | :--- | :--- |
| .pytest_cache/README.md | 删除/排除 | pytest 缓存自动生成，非项目文档 |
| docs/MIGRATION.md | 到期删除 | 自声明"临时迁移说明，将于 2026-10-16 删除" |
| coverage_report_windows_final.md | 归档（待确认） | 覆盖率基线候选替代：docs/testing/coverage-report.md（自动生成） |
| docs/analysis/site_classification_partial_v1.0.md | 合并 | 已被 site_classification_partial.md (v1.1) 取代，可归档 |
| docs/architecture/exact_match_refactor_spec.md | 归档（待确认） | 草稿状态，需确认是否已被 ADR-001-mixin-refactor 覆盖 |

## 4. 建议合并清单

| 文档1 | 文档2 | 建议 |
| :--- | :--- | :--- |
| docs/adr/ADR-001-mixin-refactor-16-to-1.md | docs/adr/ADR-001-modal-dialog-auto-clicker.md | **编号冲突**（待清理 - 重编号）：两个 ADR-001；README 索引只认 modal-dialog 版；最终由人工重排 |
| coverage_history/phase2_report.md | coverage_report_windows_final.md | 同属覆盖率补测报告，可合并至 docs/testing/ 或归档 |
| docs/architecture.md | docs/architecture/overview.md + docs/adr/ | 功能重叠（架构决策 vs ADR），待确认分工后决定合并方向 |
| docs/archive/2026-07-16-historical-plans/项目进度日志.md | docs/archive/项目进度日志.md | 两份进度日志并存（历史快照 vs 自动生成），建议保留自动生成版、归档历史版 |
| docs/guides/Docker使用指南.md | docs/deployment/README.md | 部署/Docker 内容重叠，建议统一到 deployment/ |
| docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md | docs/superpowers/specs/2026-07-24-q22-q23-adapters-summary.md | ⚠️ 同日期同主题（Q22-Q23 适配器开发总结），内容高度重复，建议合并保留一份 |

## 5. ADR 编号冲突清单（由人工统一重排）

| 冲突文件 | 编号 | 说明 |
| :--- | :--- | :--- |
| docs/adr/ADR-001-mixin-refactor-16-to-1.md | 001 | 状态"已关闭"；README 索引未收录此文件（001 指向 modal-dialog 版） |
| docs/adr/ADR-001-modal-dialog-auto-clicker.md | 001 | 状态"已接受"；README 索引收录为 001 |
| docs/adr/README.md | 008/009 | 索引中有编号无对应文件（008 首页公告三栏分类、009 CronTrigger 调度） |

## 6. 数据不一致清单

| 文档 | 不一致点 | 依据 |
| :--- | :--- | :--- |
| docs/development.md | 仍描述 v0.54.0 的 4 个新 Mixin（CsresMixin 等），现已被 Handler 组合重构（ADR-001/002）消除；引用 docs/specs/模块与功能清单.md（路径待确认） | 与 ADR-001-mixin-refactor（已关闭）及代码对照 |
| docs/governance/PROJECT_GOVERNANCE.md | 引用 docs/archive/2026-06-30/GATE_INDEX.md 与 docs/architecture_layers.md，两路径均不存在（已迁移至 2026-07-16-historical-plans/old-archive/2026-06-30/） | 与清单实际路径对照 |
| docs/governance-overview.md | 内含 942 passed 等测试数字为历史快照（2026-07-16），当前统计已变化 | 与近期测试结果对照 |
| docs/architecture/modules/query.md | 适配器数 8（7生产+1Mock）vs docs/adapters/README.md 的 22 | 两文档直接对照 |
| docs/architecture/modules/parser.md / scan.md | G-031 映射路径与模块实际路径不符 | 与代码目录对照 |
| docs/archive/.../old-archive/代码功能明细说明书.md | 基于 2026-05-31 代码（67 文件 12,400 行），已严重过时 | 与当前代码规模对照 |
| docs/specs/功能规格说明书.md | 版本历史停留在 1.15（2026-06-16），7-8 月大量重构（Q20 通知、Q22-Q23 适配器、Handler、路由 v2）未反映 | 与代码变更对照 |
| docs/specs/模块与功能清单.md | 2026-06-30 生成，Mixin→Handler/Q22 适配器重构未反映 | 与代码结构对照 |
| docs/pending/NOTIFICATION_SURVEY_REPORT.md | 通知系统调查（2026-07-01），早于 Q20 通知重构（07-22） | 与事件字典/manager 实现对照 |
| http-requests-inventory.md | 阶段 2.1 HTTP 迁移清单；⚠️ 与 2026-08-16 stage5-http-decircularize 计划（偏好收编/循环解耦）关联，需确认迁移是否已落地 | 与 stage5 计划/web/src 现状对照 |
| README.md | badge "Tests-942 passed"（历史数字）、"python-3.12+"（实际 3.14）、"6 个适配器"（实际 22，Q22-Q23 后） | 与当前版本/适配器清单对照；✅ 引用路径全部有效（已验证） |
| STATUS.md | 自动生成 metrics 覆盖率 0.0%、HEAD commit b043a288 过时；自述"不入仓库"但文件存在于工作区（未 git 跟踪） | 与当前 HEAD/测试结果对照 |

## 7. 文档职责重叠清单

| 重叠组 | 文档 | 说明 |
| :--- | :--- | :--- |
| 开发指南 | docs/development.md vs old-archive/development.md | 新旧两份开发指南，旧版已入 archive |
| 治理总纲 | PROJECT_GOVERNANCE.md vs governance-overview.md vs governance-principles.md vs trinity-technical-spec-v2.md | 4 份治理体系文档并存，需确认分工（总纲/总览/原则/技术规范） |
| **进度日志（三份并存）** | historical-plans/项目进度日志.md vs docs/archive/项目进度日志.md vs docs/项目进度日志.md | ⚠️ 三份进度日志：historical-plans（07-04 快照）、archive/（gen_daily_log 自动生成）、docs/ 根目录（07-24 Q22-Q23 手动维护）；需确认权威版本并合并 |
| 部署指南 | docs/guides/Docker使用指南.md vs docs/deployment/README.md | Docker 使用 vs 部署运维 |
| 门禁规则 | docs/development/g-010-enforcement.md vs docs/governance/gates.md | 单门禁详情 vs 全量门禁索引 |
| 决策记录 | docs/history/decisions-summary.md vs docs/adr/ | 历史决策摘要 vs ADR 目录 |
| 技术债 | docs/technical-debt.md vs docs/architecture/technical-debt-registry.md | **摘要-详情分工**（technical-debt.md 自述"详细登记见 registry"），非重复；需确认分工是否明确维护 |
| Q22-Q23 总结 | 2026-07-24-adapter-batch-q22-q23-summary vs 2026-07-24-q22-q23-adapters-summary | 同主题两份总结，内容重复，建议合并 |

## 8. 审计范围过滤建议（新增）

| 建议 | 理由 |
| :--- | :--- |
| 清单生成时排除 `pilotstd_env/` | 46 个 venv 第三方包自带文档（LICENSE/README/API/skill doc）非项目资产，与 .venv/node_modules 同理 |
| 清单生成时排除 `tests/.pytest_cache/`、`web/.pytest_cache/`（行 264/265） | pytest 缓存产物 |
| web/README.md | Vite 默认模板说明（未定制，未入 git），建议替换为项目专属说明或删除 |
