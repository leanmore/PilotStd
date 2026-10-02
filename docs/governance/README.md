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
| [gates.md](gates.md) | 门禁清单 + 执行入口（`check_all.sh` 各模式与 pre-commit 钩子接线）；版本行 **v1.68~v1.73** 依次对应 R14-4a（#31 闭环 + #32-A 状态字典）、R14-4b（#32-B 后端字面量收敛）、R14-4c（#32-C 前后端闭环 + v61 迁移）、R14-4d（#32-D 测试收敛 + 哨兵，#32 闭环）、R14-5（适配器模板同步 + 台账归档与存续项校准）、R16（候选池 P0~P3：门禁受控测试自动化 / schema 门禁提示 / T-30 收口 / 两形近脚本改名 + T-16 计数归零）；v1.68 行另含 R14-4a 的 CI 修正（`test_status` 的 PyQt6 环境守卫）；2026-09-26 新增 **G-043 敏感端点审计接线**、**G-044 术语与禁用词检查**；2026-10-02 **G-047 基线格式变更**（`i18n_hardcoded_python_baseline.txt` → `.json`，`<路径>::<行数>` → `{路径: 行数}`）——原 `.txt` 扩展名命中入仓合规门禁的 `FILENAME_BLACKLIST`（`*.txt`），致 `repo-compliance` 作业在 CI run 37004092948 失败 | v1.73 + G-043/G-044 |
| [glossary.json](glossary.json) | 术语唯一数据源（G-044 门禁输入）：49 条术语的三语用词、`forbidden` 禁用词组、`aliases` 可接受写法，以及 `exempt_keys`（17）/ `exempt_terms`（10）两层白名单 | 活跃 |
| [notification_coverage.md](notification_coverage.md) | 通知系统覆盖度基线（41 事件 × i18n/e2e/审计/术语 四维度），新增事件的准入检查清单；由 `scripts/audit_notification_coverage.py`（G-045 门禁）扫描生成 | 活跃 |
| [verification-antipatterns.md](verification-antipatterns.md) | 验证与报告方法论的反模式集（口径 / 可复现性 / 检测器判别力 / 抽象时机），每条附可复现的判别方式 | 活跃 |
| [file-inclusion-criteria.md](file-inclusion-criteria.md) | 文件入仓五条规则（R1-R5） | v1.0 |
| [capabilities_registry.md](capabilities_registry.md) | 非功能性能力登记簿 | 活跃 |
| [../guides/refactoring-lessons.md](../guides/refactoring-lessons.md) | 拆分经验 + **拆分前检查项**（注释密度预估 / G-010 拆分证据；原 `refactoring_checklist.md` 已于 `efa7514a` 删除） | 活跃 |
| [archive_migration_protocol.md](archive_migration_protocol.md) | 归档文件强制迁移流程 | 活跃 |
| [../testing/known-issues.md](../testing/known-issues.md) | 已知问题追踪 | v1.0 |
| [../adr/ADR-001-modal-dialog-auto-clicker.md](../adr/ADR-001-modal-dialog-auto-clicker.md) | 模态对话框自动处理方案 | 已接受 |
| [../technical-debt.md](../technical-debt.md) | 技术债登记（**唯一数据源**；旧簿已归档） | 活跃 |
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
| [../guides/refactoring-lessons.md](../guides/refactoring-lessons.md) | 拆分前必查：新模块注释密度预估（G-012 ≥3%）、拆分证据与 500 行阻断档（G-010）；原 `refactoring_checklist.md` 已删除 | 重构全程对照 |
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
