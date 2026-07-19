# PilotStd 治理体系总览

> 版本：v1.0.0
> 更新日期：2026-07-16
> 状态：✅ 已落地（P0-P8 全部完成）

---

## 三位一体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        三位一体治理体系                            │
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│   │    测试       │←──→│    门禁       │←──→│    文档       │       │
│   │              │    │              │    │              │       │
│   │ 942 passed   │    │ CI 并行      │    │ 架构策略     │       │
│   │ 7 skipped    │    │ 覆盖率护栏   │    │ 5 范式文档   │       │
│   │ 0 failed     │    │ Ruff+Mypy    │    │ 技术债登记   │       │
│   │ ~312s        │    │ 零容忍       │    │ 决策记录     │       │
│   └──────────────┘    └──────────────┘    └──────────────┘       │
│         ↑                   ↑                   ↑                │
│         └───────────────────┴───────────────────┘                │
│                        互相锚定，闭环验证                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## 一、测试支柱

### 全量测试

| 指标 | 数值 |
|------|------|
| 通过 | **942** |
| 跳过 | 7（网络依赖 / 环境依赖 / 平台依赖） |
| 失败 | **0** |
| 耗时 | ~327s（< 350s 红线） |

### Engine 单元测试

| Engine | 文件 | 方法 | 测试 | 覆盖率 |
|--------|------|------|------|--------|
| QueryFlowEngine | `query_flow_engine.py` | — | — | — |
| ActionsFlowEngine | `actions_flow_engine.py` | — | — | — |
| ArchiveFlowEngine | `archive_flow_engine.py` | — | — | — |
| PersistenceFlowEngine | `persistence_flow_engine.py` | 8 | 54 | 100% |
| SettingsConfigIOEngine | `settings_io_flow_engine.py` | 8 | 44 | 100% |
| DownloadFlowEngine | `download_flow_engine.py` | 4 | 39 | 100% |
| CleanupFlowEngine | `cleanup_flow_engine.py` | 2 | 28 | 100% |
| QuerySummaryFlowEngine | `query_summary_flow_engine.py` | 4 | 36 | 100% |
| DialogFlowEngine | `dialog_flow_engine.py` | 3 | 24 | 100% |
| TableHelperFlowEngine | `table_helper_flow_engine.py` | 2 | 19 | 100% |
| TableFlowEngine | `table_flow_engine.py` | 4 | 22 | 100% |
| ProjectFlowEngine | `project_flow_engine.py` | 3 | 18 | 100% |
| **合计** | — | **38+** | **284+** | **100%** |

### E2E 测试

| 覆盖范围 | 说明 |
|---------|------|
| 17 个 Handler | `_persistence`, `_settings_io`, `_download`, `_cleanup`, `_query_summary`, `_scan`, `_table`, `_table_helper`, `_theme`, `_dialog`, `_file_dialog`, `_file_tree`, `_export`, `_project`, `_settings`, `_announce`, `_auto` |
| P6 全链路 | `test_auto_pipeline.py` — scan→query→download→archive 完整流程 |

---

## 二、门禁支柱

### CI 配置

| Job | 命令 | 超时 | 重试 |
|-----|------|------|------|
| `test-e2e` | `pytest tests/gui/ -m e2e -v --maxfail=1` | 10 min | 1 次 |
| `test-unit-cov` | `pytest tests/gui/ --ignore-glob="*test_e2e*.py"` + `coverage report --include="*flow_engine*" --fail-under=85` | 5 min | 不重试 |

### 门禁规则

| 检查项 | 阈值 | 失败处理 |
|--------|------|---------|
| E2E 测试 | 全部通过 | 阻断合入 |
| 单元测试（不含 E2E） | 全部通过 | 阻断合入 |
| Engine 覆盖率 | ≥ 85%（实际 100%） | 阻断合入 |
| Ruff | 零错误 | 阻断合入 |
| Mypy | 零问题 | 阻断合入 |

---

## 三、文档支柱

### 架构策略

| 文档 | 内容 |
|------|------|
| [architecture.md](architecture.md) | Handler 组合模式 + 治理策略 + 纯 UI 编排文件清单 + 决策记录 |
| [governance-overview.md](governance-overview.md) | 本文档 — 三位一体总览 |
| [technical-debt.md](technical-debt.md) | 技术债登记（已清理 / 待处理 / 维持现状） |

### 范式文档（5 个）

| # | 文档 | 代表 Engine | 核心约束 |
|---|------|------------|---------|
| 1 | [persistence-engine-pattern.md](guides/persistence-engine-pattern.md) | PersistenceFlowEngine | 零 Qt，成对 serialize/deserialize |
| 2 | [settings-io-engine-pattern.md](guides/settings-io-engine-pattern.md) | SettingsConfigIOEngine | 默认值集中管理，严格类型检查 |
| 3 | [download-flow-engine-pattern.md](guides/download-flow-engine-pattern.md) | DownloadFlowEngine | 零 I/O，显式时间注入 |
| 4 | [cleanup-io-isolation-2.0.md](guides/cleanup-io-isolation-2.0.md) | CleanupFlowEngine | 目录树 dict 化，遍历与分析分离 |
| 5 | [query-summary-engine-pattern.md](guides/query-summary-engine-pattern.md) | QuerySummaryFlowEngine | 状态映射常量，安全字符串转换 |

### 其他治理文档

| 文档 | 说明 |
|------|------|
| [technical-debt-registry.md](architecture/technical-debt-registry.md) | 已跳过测试（13）+ 已接受设计决策（8） |
| [refactoring-lessons.md](guides/refactoring-lessons.md) | 大函数拆分经验（32 函数 + 11 包化） |
| [documentation-policy.md](development/documentation-policy.md) | 文档维护规则 |

### 模块架构文档

| 文档 | 说明 |
|------|------|
| [Manager 模块](architecture/modules/manager.md) | 业务门面层结构 |
| [Parser 模块](architecture/modules/parser.md) | 标准号解析器架构 |
| [Query 模块](architecture/modules/query.md) | 查询引擎架构 |
| [Scan 模块](architecture/modules/scan.md) | 文件扫描架构 |
| [UI 模块](architecture/modules/ui.md) | PyQt6 桌面端组件结构 |

---

## 四、版本信息

| 字段 | 值 |
|------|-----|
| 文档版本 | vX.Y.Z（待发布时由 CI 自动替换） |
| 更新日期 | 2026-07-16 |
| 全量测试 | 942 passed, 7 skipped, 0 failed (949 collected) |
| Engine 覆盖率 | 100%（12 Engine, 284+ tests） |
| CI 门禁 | E2E + Unit-Cov 并行，覆盖率护栏 ≥ 85% |
