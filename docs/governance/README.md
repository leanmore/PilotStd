# PilotStd 治理文档中心

## 文档索引

| 文档 | 用途 | 状态 |
|------|------|------|
| [governance-principles.md](governance-principles.md) | 治理体系元原则（三件套、决策链、门禁设计） | v1.0 |
| [trinity-technical-spec-v2.md](trinity-technical-spec-v2.md) | 三位一体技术规范（测试 → 门禁 → 文档闭环、强制执行层规格） | v2.1（2026-09-21 复核） |
| [development-flow.md](development-flow.md) | 决策请求协议 + `[假设失效]` 衔接 + 规则固化信号机制 + **§8 多分支合并全组合冲突侦察** | 已定稿（2026-09-26 补 §8） |
| [prompt-crafting-guide.md](prompt-crafting-guide.md) | 提示词生产规范 + context-ref v2 + rollback 三级分级 | 已定稿 |
| [rule-quickref.md](rule-quickref.md) | 非技术决策者规则速查表（业务语言翻译） | 已定稿 |
| [phase1-startup-checklist.md](phase1-startup-checklist.md) | Phase 1 唯一准入标准（启动检查清单） | v2.1 |
| [gates.md](gates.md) | 门禁清单 + 执行入口（`check_all.sh` 各模式与 pre-commit 钩子接线） | v1.19 |
| [file-inclusion-criteria.md](file-inclusion-criteria.md) | 文件入仓五条规则（R1-R5） | v1.0 |
| [capabilities_registry.md](capabilities_registry.md) | 非功能性能力登记簿 | 活跃 |
| [refactoring_checklist.md](refactoring_checklist.md) | 重构前后操作清单 | 活跃 |
| [archive_migration_protocol.md](archive_migration_protocol.md) | 归档文件强制迁移流程 | 活跃 |
| [../testing/known-issues.md](../testing/known-issues.md) | 已知问题追踪 | v1.0 |
| [../adr/ADR-001-modal-dialog-auto-clicker.md](../adr/ADR-001-modal-dialog-auto-clicker.md) | 模态对话框自动处理方案 | 已接受 |
| [../architecture/technical-debt-registry.md](../architecture/technical-debt-registry.md) | 技术债登记 | 活跃 |
| [../../CONTRIBUTING.md](../../CONTRIBUTING.md) | 贡献指南 | 活跃 |

---

# 能力遗产治理框架

## 为什么有这个框架？

在软件开发中，**非功能性能力**（后台线程、定时心跳、观测日志、缓存等）在代码重构时容易被忽略，导致功能静默丢失。

本框架通过**能力登记 + 重构检查 + 归档协议 + 自动化门禁**四层机制，确保这些能力在代码演进中得到守护。

### 真实案例

2026-05-31，`stress_01_pipeline.py` 中实现了 `ProgressReporter`（每30秒输出查询进度）和 `heartbeat()`（心跳线程防卡死）。2026-06-10，v4.1 重构将文件归档为 `_archived.py`，这两个能力**静默丢失**。直到 2026-06-22 用户执行全量压测时才发现进度输出缺失——**12天的静默期**。

如果当时有此框架，归档前的"能力提取"步骤会自动发现这两个能力，阻止静默丢失。

## 核心文档

| 文档 | 用途 | 何时阅读 |
|------|------|---------|
| [capabilities_registry.md](capabilities_registry.md) | 所有模块非功能性能力的唯一登记簿 | 重构前必查 |
| [refactoring_checklist.md](refactoring_checklist.md) | 重构前后必须执行的操作清单 | 重构全程对照 |
| [archive_migration_protocol.md](archive_migration_protocol.md) | 归档文件时的强制迁移流程 | 执行 `git mv` 归档前 |

## 工具脚本

| 工具 | 用途 | 何时运行 |
|------|------|---------|
| `bash scripts/extract_capabilities.sh <file>` | 提取单个文件的能力清单（AST 静态分析） | 重构前 / 归档前 |
| `python tests/test_observability.py --check-all` | 验证所有必需能力是否存活 | PR 提交前 / CI 自动运行 |
| `bash scripts/check_no_migrating.sh` | 检查登记簿是否有未解决的迁移项 | CI 自动运行（阻断合并） |

## 核心工作流

```
重构前 → 查登记簿 + 运行 extract_capabilities.sh → 记录待迁移能力
重构中 → 逐项迁移或明确放弃（commit 中说明理由）
重构后 → 更新登记簿 + 运行 test_observability.py --check-all
PR提交 → 填写 PR 模板中的"能力迁移状态"表 → CI 自动检查
归档前 → 运行 extract_capabilities.sh 并确保迁移完成
```

## 红线（不可违反）

1. **禁止**在未运行 `extract_capabilities.sh` 的情况下执行 `git mv` 归档文件
2. **禁止**在 `capabilities_registry.md` 中存在 `migrating` 条目时合并 PR（CI 会阻断）
3. **禁止**在 `test_observability.py --check-all` 存在 FAIL 时合并 PR（CI 会阻断）

## 能力登记簿字段说明

| 字段 | 说明 | 可选值 |
|------|------|--------|
| 模块路径 | 能力所在的文件 | 相对于项目根目录 |
| 能力名称 | 简短描述 | — |
| 实现位置 | 文件:行号 或 类.方法 | — |
| 类型 | 能力分类 | 后台线程 / 观测日志 / 缓存 / 生命周期管理 / 其他 |
| 必需性 | 重要程度 | `required`（缺失 CI 阻断）/ `recommended` / `optional` |
| 登记日期 | 首次登记日期 | YYYY-MM-DD |
| 状态 | 当前状态 | `active` / `deprecated` |

## 常见问题

**Q: 我新增了一个后台线程，需要登记吗？**

A: 需要。在 `capabilities_registry.md` 中对应模块下新增一条记录，状态为 `active`，必需性根据重要性标记 `required` 或 `recommended`。

**Q: 我重构时发现某能力已不再需要，可以删除吗？**

A: 可以。但必须在 `capabilities_registry.md` 中将状态改为 `deprecated`，并在 commit message 中说明删除理由，而非静默删除。

**Q: 紧急修复也需要走这个流程吗？**

A: 紧急修复（Bug Fix）若涉及代码修改但未改变模块结构，只需运行 `test_observability.py --check-all` 确认无 FAIL 即可，无需完整走重构流程。若涉及文件归档或模块重构，则必须走完整流程。

**Q: 登记簿中的能力太多了，我能跳过吗？**

A: `--required-only` 参数仅检查 `required` 级别能力。CI 也仅对 `required` 级别 FAIL 进行阻断。`recommended` 和 `optional` 级别的 WARN 不会阻断合并。
