# 归档文档 — 2026-06-30

> 归档原因：GATE-15 代码规模治理完成（0 文件 >500 行，0 函数 >80 行）
> 归档日期：2026-06-30
> 相关提交：6bbb957

## 说明

本目录存放 2026-06-30 治理工作完成后退下的过时文档。这些文档分析了治理前的代码结构（大文件、大函数、代码异味），其分析结果已推动治理执行。治理完成后，文档内容不再反映当前代码状态。

## 归档清单

| # | 原路径 | 归档原因 |
|---|--------|---------|
| 1 | `code_smell_audit.md` | 11 个大文件列表已全部拆分 |
| 2 | `folder_inventory.md` | 文件数/行数已变更 |
| 3 | `architecture_layers.md` | 架构层文件路径过时 |
| 4 | `notification_system_status.md` | 通知状态已更新 |
| 5 | `functionality_inventory.md` | 部分功能状态变更 |
| 6 | `governance/GATE_INDEX.md` | GATE-15 已清零 |
| 7 | `governance/capabilities_registry.md` | 文件路径/行号已失效 |
| 8-16 | `*_analysis.md` (9 个) | 包化前大文件分析，已全部拆分 |
| 17 | `function_split_plan.md` | 拆分计划已完成 |
| 18 | `architecture_compliance_audit.md` | 文件数已变更 |
| 19 | `specs/代码功能明细说明书.md` | 行数过时 |
| 20 | `specs/模块划分方案.md` | 目录树过时 |
| 21 | `development.md` | 项目结构/测试数过时 |

## 替代文档

| 原文档 | 替代文档 |
|--------|---------|
| `code_smell_audit.md` + `folder_inventory.md` + `architecture_layers.md` | `docs/architecture/governance-summary.md` |
| `*_analysis.md` (9 个) | `docs/architecture/refactoring-analysis.md` |
| `function_split_plan.md` | `docs/architecture/governance-summary.md` |
| `notification_system_status.md` | `STATUS.md` |
| `GATE_INDEX.md` | `docs/development/gate-15-enforcement.md` |
| `development.md` | `docs/development.md` (重建) |
| `specs/代码功能明细说明书.md` + `specs/模块划分方案.md` | `docs/specs/模块与功能清单.md` |
