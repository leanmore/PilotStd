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

### Inline 指令分级与文档要求

| 指令类型 | 判断条件 | 文档要求 |
|----------|----------|----------|
| 热修复 | 修bug、改配置、调整参数 | 直接执行，commit message 标注 [hotfix] |
| 功能开发 | 新增模块/适配器/接口 | 生成 spec-lite.md（≤30行） |
| 架构变更 | 跨模块重构、接口变更、数据模型变更、体系加固 | 完整 spec + plan |

spec-lite.md 模板（4个必填区块）：
- 用户指令摘要（≤5行）
- 采纳的关键设计决策（≤5条）
- 识别到的风险点及与现有架构的冲突（≤5条）
- 验证方式（测试用例/手动验证步骤）

模板文件：`docs/superpowers/specs/spec-lite-template.md`

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

G-025 触发条件扩展：
- `adapters/` 目录下任何 .py 文件变更 → 检查 `docs/reference/adapter-development.md` 是否同步更新
- 新增适配器 → 检查 `docs/superpowers/specs/` 目录下是否存在对应 spec-lite.md

完整门禁清单见 `docs/governance/gates.md`。

## 4. 验证与交付

### 4.1 .test_pass 验证文件

.test_pass 文件由 pytest session-finish hook 自动生成，也支持手动写入。

- 测试全通过 → 自动写入（`verification_type: "auto"`，含 `commit_hash`）
- 测试失败 → 自动删除 auto 类型文件
- 手动验证通过 → 允许执行者手动写入/追加（`verification_type: "manual"`，含时间戳+验证描述）
- Code Review 步骤检查：文件存在 + 时间戳在24小时内 + verification_type 有效 + commit_hash 与当前 HEAD 一致（或为 manual 类型） → 通过。否则阻断。

.test_pass 写入前置条件：
- 功能开发任务：spec-lite.md 必须存在于 `docs/superpowers/specs/` 目录
- 架构变更任务：spec + plan 双文档必须存在
- 无对应文档 → 验证无效，退回执行

### 4.2 交付报告模板

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

## 6. 收工流程

### 6.1 每日收工 — Knowledge Trigger

每次执行以下操作时，必须同步更新 `.claude/memory.md`：

| 触发事件 | 写入要求 |
|----------|----------|
| commit message 含"决策""范式""放弃""规范""重构"关键词 | 在 Memory 中追加对应条目 |
| 生成 spec/plan 文档 | 提取"设计决策"部分同步到 Memory |
| 放弃某个站点/方案/技术路线 | 必须在 Memory 中记录放弃原因和最终结论 |
| 新增/修改适配器开发规范 | 必须在 Memory 中记录规范变更 |

**兜底确认（不可省略）**：无论 commit message 是否包含关键词，收工前必须显式自问："本次工作是否产生了值得记录的设计决策/范式/放弃？"若答案为是，立即写入 Memory。

Memory 最后更新时间检查：CI pre-push hook 检查 `.claude/memory.md` 的 last commit 时间。
- >7天未更新 → 警告（不阻断）
- >14天未更新 → 阻断推送，要求先更新 Memory

### 6.2 每日收工 — 进度日志

收工前执行 `python scripts/gen_daily_log.py >> docs/archive/项目进度日志.md`
脚本自动生成当日 commit 列表草稿，执行者补充"关键进展"和"阻塞项"两个部分。

## 7. Ruff/MyPy 报错处理（"动哪改哪"的边界规则）

在修改文件时，如遇到 ruff/mypy 报错，按以下规则处理：

### 判断规则

| 场景 | 是否顺手修 | 判定依据 |
| :--- | :--- | :--- |
| **本次修改的文件**出现 ruff/mypy 报错 | ✅ **必须修** | 报错在修改范围内，不修无法通过门禁，不修也属于"改了但没改干净" |
| **本次未修改的文件**出现 ruff/mypy 报错 | ⚠️ **有条件修** | 仅当该文件与本次修改存在**直接依赖关系**（如被本次修改的函数调用）时才修，否则忽略 |
| **本次未修改且无依赖**的文件出现报错 | ❌ **不修** | 记录位置并告知用户，不擅自改动 |

### 执行流程

```
修改文件 → 运行 ruff/mypy
    ↓
报错出现在本次修改的文件？
    ├─ 是 → 必须修（属于"动哪改哪"范围内的收尾）
    └─ 否 → 报错文件是否被本次修改直接依赖（import/调用）？
                ├─ 是 → 顺手修（避免门禁因上游问题阻塞）
                └─ 否 → 不修，在报告中记录"另有 X 处无关报错，已跳过"
```

### 报告规范

当遇到未修改文件且有依赖的报错需要顺手修时，需在交付报告中说明：

```text
【额外修改】（因本次修改触发依赖链）
- file.py:45 修复 ruff E501（本次新增调用导致行超长）
- 原报错存在，因本次修改引用该函数而暴露，顺手修复
```

> "动哪改哪"不与"修报错"矛盾——修改文件后确保该文件干净，本身就是"改"的一部分。顺手修有依赖的报错属于"不因历史债务阻塞当前交付"，而非"顺手重构没坏的东西"。

### 多工具联合豁免指令生成规范

涉及 ≥2 个静态分析工具（如 Vulture + mypy、ESLint + tsc 等）的修复指令，**必须逐工具分节列出**，禁止合并表述。每节包含：

1.  **工具名称**
2.  **配置文件 / 源码位置**
3.  **精确配置内容**（可直接复制执行的代码/配置片段）
4.  **作用域边界**（明确该配置影响的文件范围）

验收标准须包含 N×N 交叉验证矩阵，确保每个工具的豁免仅作用于预期目标，不产生副作用。

> 📌 **来源**：CI-FIX-20260725-006 初版 Vulture+mypy 合并表述导致执行偏差，本规范为该事件的治理沉淀。
