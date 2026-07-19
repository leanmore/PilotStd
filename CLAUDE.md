# PilotStd 项目核心指令

你是 PilotStd 项目的开发 AI。严格遵守以下规则。不存在例外。

## 1. 核心铁律

- 严禁硬编码密码、Token、密钥
- 严禁裸 `except`，必须捕获具体异常
- 日志唯一入口：`LoggerManager()`，禁止 `print` 或 `_log()`
- 写新函数前，先搜索 `pilotstd/core/` 和 `pilotstd/query/`，禁止重复造轮子
- 提交信息格式：Conventional Commits（feat/fix/refactor/docs/test/chore/ci/style/perf/build/revert），禁止手动打 Tag

## 2. 强制工作流（三位一体 SOP）

每次任务严格执行以下五步。禁止跳过任何一步。

1. **读文档**：根据触发条件表，主动读取相关文档
2. **写代码**：遵循范式，确保测试覆盖
3. **跑门禁**：提交前运行 `scripts/check_all.sh`，确保零错误
4. **更文档**：涉及架构/API/DB/技术债变更时，同步更新对应文档
5. **交付**：输出交付报告，包含文件清单、测试结果、门禁结果、自审报告

### 读文档触发条件表

| 触发条件 | 必须读取的文档 |
|----------|---------------|
| 任何代码修改任务 | `docs/governance/development-flow.md` |
| 涉及数据库/Schema | `docs/architecture.md` |
| 涉及公告解析/入库 | `docs/reference/announcement-pipeline.md` |
| 涉及公告来源判断 | `docs/reference/announcement-sources.md` |
| 涉及前端 UI 组件 | `docs/reference/ui-components.md` |
| 涉及 CI/CD 或门禁 | `docs/ci-lessons.md` |
| 涉及门禁配置变更 | `docs/governance/gates.md` |
| 涉及架构决策 | `docs/adr/` |
| 涉及技术债 | `docs/technical-debt.md` |
| 编写新代码时 | `docs/reference/coding-standards.md` |
| 提交代码前 | `docs/reference/pre-commit-checklist.md` |
| 不确定该读什么 | `docs/index.md` |

### 冲突处理

若发现文档与代码现状不一致，必须同步修正文档使其与代码一致。在交付报告中说明差异原因及修改内容。禁止仅标记"文档过期"而不修复。

## 3. 门禁规则与强制执行层

### 3.1 强制执行层（不可绕过）

- **Git Hooks**：`pre-commit` 拦截本地门禁未通过的提交；`commit-msg` 拦截格式错误的提交信息
- **CI 硬阻断**：全量测试、架构变更无 ADR 等重度检查，在 CI 阶段做最终物理拦截
- **CI 失败后**：先写归因分析（含"如何防止同类问题再次发生"），再修代码。禁止跳过归因直接改代码

### 3.2 门禁分级介入时机

| 门禁 | 介入时机 | 理由 |
|------|----------|------|
| G-010 单文件行数 | 编码时（IDE 提示）+ 提交时（Hook） | 写的时候就该知道超了 |
| G-031 Ruff/Mypy | 编码时（IDE 实时）+ 提交时（Hook） | 即时反馈，秒级响应 |
| G-020 死引用 | 提交时（Hook） | 写完一轮代码后统一扫描 |
| 文档同步检查 | 提交时（Hook 检查 docs/ 变更）+ CI 兜底 | 本地警告，CI 硬拦截 |
| G-030 全量测试 | CI | 耗时较长，本地全量运行不现实 |
| G-034 新函数有测试 | CI | 需分析 diff 判断是否新增函数 |

完整门禁清单见 `docs/governance/gates.md`。

## 4. 交付报告模板

任务结束时必须输出以下清单。每一项都必须如实填写，禁止留空。

- [ ] **文档同步**：已根据代码变更同步更新相关文档 / 本次无文档变更（必须说明理由）
- [ ] **测试**：新增/修改代码已有测试覆盖；`pytest` 全量通过
- [ ] **门禁**：`scripts/check_all.sh` 通过（零错误）；密钥扫描无硬编码敏感信息
- [ ] **自审**：逐项确认指令要求已满足

## 5. 常用命令

- 全量检查：`scripts/check_all.sh`
- 测试：`pytest`
- 前端测试：`npm run test`
- 死代码检查：`vulture pilotstd/` / `npx ts-prune`
