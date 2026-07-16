# PilotStd 文档索引

> 最后更新：2026-07-16
> 治理状态：✅ P5 12 Engine 100% 覆盖 | ✅ 测试全绿 (942 PASS, 7 SKIP, 0 FAIL) | ✅ CI 门禁并行化

---

## 文档导航

### 入门

| 文档 | 说明 |
|------|------|
| [STATUS.md](../STATUS.md) | 项目当前状态、版本、阻塞项 |
| [CHANGELOG.md](../CHANGELOG.md) | 版本变更记录 |
| [开发指南](development.md) | 环境搭建、测试、常用命令 |
| [CI 修复经验](ci-lessons.md) | CI 常见问题分类、根因分析与防复发清单 |

### 架构与治理

| 文档 | 说明 |
|------|------|
| [治理体系总览](governance-overview.md) | 三位一体（测试 + 门禁 + 文档）总览 |
| [架构决策记录](architecture.md) | Handler 组合模式 + 治理策略 + 纯 UI 编排文件清单 |
| [技术债登记](technical-debt.md) | 已清理 / 待处理 / 维持现状 |
| [技术债登记簿](architecture/technical-debt-registry.md) | 已跳过测试 + 已接受设计决策 |
| [治理汇总](architecture/governance-summary.md) | G-010 治理全过程 (7 阶段) |
| [文档同步策略](development/documentation-policy.md) | 文档维护规则 |
| [计划文档](plans/README.md) | 当前活跃的计划与方案（Active） |
| [模块与功能清单](specs/模块与功能清单.md) | 当前包化后模块结构 |

### 设计文档

| 文档 | 说明 |
|------|------|
| [重构经验](guides/refactoring-lessons.md) | 拆分模式 + 反模式 |
| [Persistence 范式](guides/persistence-engine-pattern.md) | 序列化/反序列化 Engine 模式 |
| [SettingsIO 范式](guides/settings-io-engine-pattern.md) | 配置管理 Engine 模式 |
| [DownloadFlow 范式](guides/download-flow-engine-pattern.md) | I/O 隔离 1.0 Engine 模式 |
| [Cleanup 范式](guides/cleanup-io-isolation-2.0.md) | I/O 隔离 2.0 Engine 模式 |
| [QuerySummary 范式](guides/query-summary-engine-pattern.md) | 数据分组 Engine 模式 |
| [会话存储设计](development/session-store-design.md) | JWT + 内存会话存储 |

### 历史文档

| 目录 | 说明 |
|------|------|
| [历史决策摘要](history/decisions-summary.md) | 已采纳的核心决策索引（含归档链接） |
| [历史归档](archive/2026-07-16-historical-plans/) | Phase 1 隔离的历史计划/设计文档 |

### 参考

| 文档 | 说明 |
|------|------|
| [E2E 测试索引](testing/e2e-test-manifest.md) | E2E 测试用例清单（28 个，覆盖 18 个 Handler） |
| [附录：标准代号清单](reference/附录一 标准代号完整清单.md) | 国内/国际标准代号全集 |
| [环境需求](reference/环境需求.md) | Python/Docker/Node 版本 |
| [版本管理规范](reference/版本管理规范.md) | 语义化版本 + 发布流程 |

### 用户指南

| 文档 | 说明 |
|------|------|
| [Docker 使用指南](guides/Docker使用指南.md) | Docker 部署 |
| [用户帮助文档](guides/用户帮助文档.md) | CLI/WinUI 使用 |
| [人工测试方案](guides/人工测试方案.md) | 手动测试流程 |

---

## 归档记录

| 日期 | 原因 | 文件数 | 详情 |
|------|------|--------|------|
| 2026-06-30 | G-010 治理完成 | 20 | `archive/2026-06-30/README.md` |
