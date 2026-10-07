# 开发指南

> 更新日期：2026-06-30
> 适用于 G-010 治理后的项目结构

## 环境搭建

```bash
# 创建虚拟环境
python -m venv pilotstd_env
# 激活 (Windows)
pilotstd_env\Scripts\activate
# 安装依赖
pip install -r requirements.txt
```

## 目录结构

详见 [模块与功能清单](docs/specs/模块与功能清单.md) 和 [治理汇总](docs/architecture/governance-summary.md)。

关键变化（v0.54.0）：
- 11 个包化目录（`config/`, `db/`, `facade/`, `engine/`, `parser/`, `ocr/`, `main_window/`, `workers/`, `query/`, `organize/`, `commands/`）
- 所有文件 ≤500 行，所有函数 ≤80 行
- 4 个新 mixin：`CsresMixin`, `MiniBucketMixin`, `ReportMixin`, `MessageBuildersMixin`

## 运行测试

```bash
# 全量测试
python -m pytest tests/ -q

# 跳过 E2E 网络依赖
python -m pytest tests/ -q -k "not e2e"

# 单个测试文件
python -m pytest tests/test_query.py -v
```

当前状态：771 PASS / 6 SKIP / 0 FAIL

## 代码质量

```bash
# Ruff 检查
ruff check pilotstd docker

# 自动修复
ruff check --fix pilotstd docker

# 格式化
ruff format pilotstd docker

# Mypy 类型检查
mypy pilotstd docker --follow-imports=skip

# 死代码检测
vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=80
```

## 数据库迁移

```bash
# 迁移文件位置
pilotstd/core/db/migrations.py     # 迁移函数定义
pilotstd/core/db/_constants.py     # CURRENT_SCHEMA_VERSION

# 添加新迁移
# 1. 在 migrations.py 中添加 @migration(N) 装饰的函数
# 2. 在 _constants.py 中更新 CURRENT_SCHEMA_VERSION
```

## 本地检查与自动修复

### Pre-commit 自动修复

提交时，Husky pre-commit hook 自动执行以下检查（配置于 `.husky/pre-commit`）：

| 步骤 | 检查项 | 阻断？ | 说明 |
|------|--------|--------|------|
| vue-tsc | 前端类型检查 | 阻断 | `pnpm vue-tsc -b --noEmit` |
| lint-staged | 前端代码格式化 | 阻断 | 仅暂存文件 |
| G-002 | DatePicker 导入门禁 | 阻断 | 禁止直接导入 `primevue/datepicker` |
| G-010 | 代码规模控制 | 阻断 | 文件≤500行，函数≤80行 |
| G-011 | 动态属性完整性 | 阻断 | 所有 `self.xxx` 有对应定义 |
| Ruff auto-fix | Python 代码修复 | 不阻断 | `ruff check --fix` + `ruff format`，仅暂存文件 |

Ruff 自动修复步骤会在提交时自动修复暂存 Python 文件中的可自动修复问题（如未使用导入、格式问题），修复后自动重新暂存。

### 手动执行

```bash
# 完整门禁检查
bash scripts/check_all.sh

# 仅 G-010
python scripts/check_g_010_code_size.py

# 仅 G-011
python scripts/check_g_011_attr_integrity.py
```

## G-010 代码规模控制

| 规则 | 红线 | 说明 |
|------|------|------|
| 文件行数 | ≤500 | `wc -l <file>` |
| 函数行数 | ≤80 | AST 解析 |

详见 [G-010 规则](development/g-010-enforcement.md)。

## 常用命令

| 用途 | 命令 |
|------|------|
| 检查大文件 | `find pilotstd docker -name '*.py' -exec wc -l {} + \| sort -rn \| head -20` |
| 启动 Docker API | `cd docker && uvicorn app:app --host 0.0.0.0 --port 8000` |
| 构建 Docker 镜像 | `docker build -t pilotstd .` |
| 前端类型检查 | `cd web && npm run type-check` |
| 前端构建 | `cd web && npm run build` |

## CI/CD 工作流与 Action 版本

工作流位于 `.github/workflows/`，共 4 个：`ci.yml`（主流水线：lint-fast / test-backend / test-frontend /
test-e2e / frontend-e2e / test-gui-* / e2e-coverage / security-scan / repo-compliance / docker / exe / version）、
`governance-check.yml`、`gui-race-probe.yml`、`trinity-gate.yml`。

**Action 版本口径（2026-10-07 升级）**：全部 Action 钉在**首个使用 `node24` 运行时的主版本**上，
以消除平台侧「Node.js 20 is deprecated」告警；当前为：

| Action | 版本 |
|---|---|
| `actions/checkout` | `v5` |
| `actions/setup-python` | `v6` |
| `actions/setup-node` | `v5` |
| `actions/upload-artifact` | `v6` |
| `actions/download-artifact` | `v7` |
| `docker/build-push-action` | `v7` |
| `docker/login-action` | `v4` |
| `docker/setup-buildx-action` | `v4` |
| `pnpm/action-setup` | `v5` |
| `softprops/action-gh-release` | `v3` |
| `actions/github-script` | `v8` |

**为什么钉「首个 node24 主版本」而不是最新版**：升级幅度最小 ⇒ 行为变更面最小；
**升级前必做两步静态校验**（本项目实测流程）：

1. 读目标版本 `action.yml` 的 `runs.using`，确认是 `node24`（避免「升了版仍在 node20」）；
2. 把工作流里实际传的 `with:` 参数与目标版本 `inputs` 逐项比对（防「参数被移除」类破坏性变更）。

**注意**：`docker/build-push-action` 与 `docker/setup-buildx-action` 必须**同批升级**（版本互相要求）；
`actions/upload-artifact` 与 `actions/download-artifact` 也应同批升级（产物格式同代）。

**E2E 可观测性（2026-10-07 补）**：`web/playwright.config.ts` 配置 `reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]]` 与 `outputDir: 'test-results'`；
配合既有的 `use.screenshot: 'only-on-failure'` / `use.trace: 'retain-on-failure'` ⇒
**汇总视图（HTML 报告）+ 单条用例现场（截图/trace）三者齐备**；CI 的 `frontend-e2e` 作业用
`actions/upload-artifact` 同时上传 `web/playwright-report/` 与 `web/test-results/`（报告恒产出 ⇒
不会再出现「No files were found」告警）。**新增 e2e 用例或调整产物路径时，须同步这三处**：
config 的 `outputFolder`/`outputDir`、工作流上传 `path`、本节说明。

**环境版本声明**：`ci.yml` 顶部 `env` 定义 `PYTHON_VERSION: '3.12'` 与 `NODE_VERSION: '22'`；
容器基础镜像为 `python:3.12-slim`；`pyproject.toml` 声明 `requires-python >= 3.12`。

## 相关文档

| 文档 | 路径 |
|------|------|
| 治理汇总 | `docs/architecture/governance-summary.md` |
| 包化分析 | `docs/architecture/refactoring-analysis.md` |
| 重构经验 | `docs/guides/refactoring-lessons.md` |
| 文档策略 | `docs/development/documentation-policy.md` |
| 会话存储 | `docs/development/session-store-design.md` |
| 技术债 | `docs/technical-debt.md` |
