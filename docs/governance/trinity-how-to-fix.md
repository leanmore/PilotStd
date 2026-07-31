# Trinity Gate 修复指引

> 当 CI `trinity-gate.yml` 门禁失败时，按本指引排查修复。
> 所有门禁也可在本地运行：`bash scripts/check_all.sh --deep --docs`

---

## G-030：技术债联动检查

**失败含义**：你在源代码中新增了 `# TECH-DEBT:` 或 `# TODO(debt):` 标记，但未同步更新技术债登记簿。

**修复步骤**：
1. 确认新增标记是否确实为技术债（而非临时注释）
2. 在 `docs/technical-debt.md` 中新增对应条目，包含：模块、描述、计划修复时间
3. 将登记簿变更纳入同一次提交

**豁免方式**：
- 如果标记位于 `docs/`、`tests/`、`scripts/` 目录 → 自动豁免
- 如果标记是存量代码（非本次新增）→ 自动豁免

---

## G-032：文档健康度守护

**失败含义**：自动生成的文档（STATUS.md 指标区、coverage-report.md）可能损坏、过期或被手动篡改。

### 子检查 1：生成器存活

**失败含义**：自动生成文档缺少 `AUTO-GENERATED` 标记或生成时间超过 2 小时。

**修复步骤**：
```bash
# 本地重新生成文档
bash scripts/check_all.sh --docs
```

### 子检查 2：人工层新鲜度

**失败含义**：人工维护的文档超过允许的最大未更新天数。

| 文档类别 | 最大天数 | 涉及文档 |
|---------|:---:|------|
| 核心状态 | 7 天 | STATUS.md, known-issues.md, CHANGELOG.md |
| 架构规范 | 30 天 | trinity-technical-spec-v2.md, gates.md, development-flow.md, architecture.md |
| 治理文档 | 60 天 | PROJECT_GOVERNANCE.md, capabilities_registry.md, governance-principles.md |

**修复步骤**：
1. 检查对应文档是否需要更新
2. 如需要 → 更新内容后重新提交
3. 如确实无需更新 → 编辑文档任意位置（如更新末尾的"最后检查日期"注释）以刷新修改时间

### 子检查 3：交叉引用完整性

**失败含义**：文档中引用的文件路径不存在。

**修复步骤**：
1. 检查引用的文件是否被重命名、移动或删除
2. 更新文档中的引用路径

### 子检查 4：数据源唯一性

**失败含义**：STATUS.md 的人工编辑区包含覆盖率、测试数等应由自动生成层维护的数值。

**修复步骤**：
1. 删除手工写入的数值
2. 运行 `bash scripts/check_all.sh --docs` 重新生成
3. 如果该数值确实需要人工维护，在行尾添加 `[legacy-manual]` 标记（30 天宽限期内有效）

---

## G-033：ADR 完整性检查

**失败含义**：检测到架构变更（修改了 `pilotstd/core/`、`docs/architecture/`、`.github/workflows/` 等），但没有伴随有效的 ADR。

**修复步骤**：
1. 确认当前变更是否属于架构变更
2. 如果是 → 在 `docs/adr/` 中创建新 ADR（复制现有 ADR 模板），Status 设为 `accepted` 或 `implemented`
3. 如果不是 → 检查是否误修改了架构文件，或本次变更确实不涉及架构决策（可忽略警告）

**ADR 模板**：
```markdown
# ADR-XXX: {简短标题}

## Status
accepted

## Context
{为什么需要做这个决策}

## Decision
{做了什么决策}

## Consequences
{决策带来的影响}
```

---

## G-010：代码规模控制

**失败含义**：某个 Python 文件超过 500 行，或某个函数超过 80 行。

**修复步骤**：
1. 将大文件拆分为多个子模块（参考 `query/engine/` 目录的拆分方式）
2. 将大函数提取为独立辅助函数

---

## G-011：动态属性完整性

**失败含义**：代码中对对象动态赋值了属性，但未在 `__slots__` 中声明。

**修复步骤**：
1. 在类定义中添加 `__slots__` 声明
2. 或改用 `@property` 装饰器

---

## G-012：SQL Schema / 注释密度

**失败含义**：
- SQL Schema：代码中的 SQL 查询引用了数据库中不存在的列/表
- 注释密度：Python 文件的注释率低于阈值

**修复步骤**：
- SQL Schema：检查数据库迁移是否已执行，或 SQL 中是否有拼写错误
- 注释密度：为关键逻辑添加注释（需为 `# TECH-DEBT:` 格式标记明确豁免）

---

## 本地调试

所有门禁均可在本地运行，无需等待 CI：

```bash
# 快速检查（<10 秒）
bash scripts/check_all.sh --fast

# 文档生成 + 守护（<30 秒）
bash scripts/check_all.sh --docs

# 全量深度检查（<60 秒）
bash scripts/check_all.sh --deep

# 一键全跑
bash scripts/check_all.sh --all
```
