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

## 相关文档

| 文档 | 路径 |
|------|------|
| 治理汇总 | `docs/architecture/governance-summary.md` |
| 包化分析 | `docs/architecture/refactoring-analysis.md` |
| 重构经验 | `docs/guides/refactoring-lessons.md` |
| 文档策略 | `docs/development/documentation-policy.md` |
| 会话存储 | `docs/development/session-store-design.md` |
| 技术债 | `docs/architecture/technical-debt-registry.md` |
