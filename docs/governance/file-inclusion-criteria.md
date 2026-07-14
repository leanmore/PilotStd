# 文件入仓判断标准

| 属性 | 值 |
|------|-----|
| 状态 | 已批准 |
| 版本 | v1.0 |
| 批准日期 | 2026-07-14 |
| 关联门禁 | `repo-compliance` job（`.github/workflows/ci.yml`） |
| 关联脚本 | `scripts/check-repo-compliance.sh` |
| 审核人 | 项目治理顾问 |

## 一、设计原则

PilotStd 的 GitHub 仓库定位为：**展示橱窗 + 成品交付 + 构建流水线**。

基于此定位，并非所有项目文件都应进入仓库。入仓判断遵循以下核心原则：

1. **只入仓"成品"**：源码、构建配置、测试、文档、自动化脚本——这些是项目的"交付物"
2. **不入仓"草稿"**：设计笔记、调研报告、临时计划、个人备忘——这些是"过程产物"
3. **不入仓"大文件"**：二进制资源、训练数据、模型文件——这些应通过外部存储管理
4. **路径即语义**：文件存放位置应反映其用途和生命周期
5. **门禁前置拦截**：不合规文件在 CI 阶段被拦截，不入主分支

## 二、五条入仓规则

| 编号 | 规则名称 | 判定方式 | 设计意图 |
|------|---------|---------|---------|
| R1 | 白名单放行 | 路径前缀匹配 `pilotstd/` `docker/` `web/src/` `tests/` `.github/` `docs/architecture/` `docs/specs/` `docs/development/` `docs/governance/` `docs/guides/` `assets/`；根目录精确匹配 `README.md` `CHANGELOG.md` `CONTRIBUTING.md` 等 13 个文件 | 这些路径是项目"成品"的标准存放位置 |
| R2 | 黑名单拦截 | 路径前缀匹配 `docs/archive/` `docs/pending/` `docs/superpowers/` `reports/` | 这些路径存放的是"过程产物"，不应进入主分支 |
| R3 | 文件名模式拦截 | 文件名匹配 `*_plan.md` `*_design.md` `*_report.md` `*_survey*.md` `*.txt` | 这些文件名模式暗示文件是"草稿"或"临时记录" |
| R4 | 根目录可疑文件拦截 | 根目录下 `.md` `.png` `.json` 文件不在 R1 白名单中则拦截 | 根目录应保持整洁，只保留项目级关键文件 |
| R5 | G-019 路径守卫 | 检查 `pilotstd/core/path_guard.py` 是否包含 `/inbox` 和 `/standards` 字符串 | 确保关键路径守卫常量未被意外删除 |

## 三、规则执行方式

- **执行位置**：`.github/workflows/ci.yml` 中的 `repo-compliance` job
- **触发条件**：每次 push 到任意分支
- **执行脚本**：`scripts/check-repo-compliance.sh`
- **失败后果**：CI 流水线阻断，不合规文件无法合入 main 分支
- **检查范围**：仅检查本次 push 中新增的文件，不追溯历史

## 四、例外处理流程

当需要入仓的文件类型不在白名单中，但确实符合"成品交付"定位时，按以下流程处理：

1. **提交 Issue**：说明新增文件类型、用途、为何需要入仓
2. **讨论确认**：由项目维护者评估是否应加入白名单
3. **更新规则**：确认后，同步更新：
   - 本文件中的白名单/规则表
   - `scripts/check-repo-compliance.sh` 中的对应逻辑
   - `.github/workflows/ci.yml` 中的门禁配置（如有必要）
4. **合规入仓**：规则更新后，新增文件类型方可提交

临时绕过：如因紧急情况需要临时绕过（如 hotfix），需在 PR 描述中明确说明，并在合入后 3 个工作日内补全上述流程。

## 五、版本历史

| 版本 | 日期 | 变更说明 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-07-14 | 初始版本，基于 check-repo-compliance.sh 脚本内容提取 | 项目治理顾问 |

## 六、相关链接

| 链接 | 用途 |
|------|------|
| `.github/workflows/ci.yml` | 门禁执行位置 |
| `scripts/check-repo-compliance.sh` | 门禁脚本源码 |
| `docs/governance/gates.md` | 全部门禁索引 |
| `docs/architecture/decisions/ADR-001-repo-boundary.md` | 入仓标准对应的架构决策（待创建） |
