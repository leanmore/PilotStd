# 项目测试覆盖率现状调查报告

> **调查日期**：2026-07-31
> **数据来源**：本地 `pytest --cov=pilotstd --cov-branch` 扫描 + CI 配置 + 代码目录结构 + 项目文档
> **扫描范围**：`pilotstd/` 全部模块（含 UI），排除 `docker/`、`tests/`、`scripts/`
> **说明**：本地覆盖率扫描仅作只读基线，未修改任何代码或配置

---

## 1. 现有测试套件盘点

### 1.1 总览

| 层级 | 测试文件数 | 测试用例数 | 框架 | 运行环境 |
|------|-----------|-----------|------|---------|
| 后端（非GUI） | 128 | 2,366 | pytest | Linux CI (`ubuntu-latest`) |
| GUI 单元测试 | 50 | ~1,000 | pytest-qt | Windows CI (`windows-latest`) |
| GUI E2E 测试 | 18 | 28 | pytest-qt (`@pytest.mark.e2e`) | Windows CI |
| 前端单元测试 | 22 | 113 | vitest + happy-dom | Linux CI |
| 前端 E2E 测试 | 1 | ~3 | Playwright | Linux CI |
| 压测脚本 | 7 | — | pytest (手动) | 手动执行 |

**源码 vs 测试文件比**：384:212 ≈ **1.8:1**（测试密度较高）

### 1.2 后端测试（tests/，排除 tests/gui/）

**测试文件分类**：

| 类别 | 文件数 | 代表性文件 |
|------|--------|-----------|
| 核心模块测试 | 20 | `test_core.py`, `test_core_config.py`, `test_core_db_modules.py` |
| 查询引擎测试 | 12 | `test_query.py`, `test_engine_single.py`, `test_rotator.py` |
| 适配器测试 | 5 | `test_adapters.py`, `test_e2e_adapters.py`, `test_samr_api.py` |
| 管理器/Facade 测试 | 15 | `test_manager.py`, `test_manager_unit.py`, `test_facade_*.py` |
| 公告测试 | 8 | `test_announcement_*.py`, `test_channels_announcement.py` |
| 通知测试 | 10 | `test_notification_*.py` |
| 扫描/解析测试 | 5 | `test_parser.py`, `test_scanner.py`, `test_scan_misc.py` |
| CLI 测试 | 3 | `test_cli.py`, `test_argparse.py`, `test_execution.py` |
| Docker/API 测试 | 5 | `test_docker_api.py`, `test_docker_auth.py`, `test_health.py` |
| 其他专项测试 | 45 | 数据迁移、路由、安全性、i18n、行业查找等 |

**CI 排除项**（共 9 项）：
- `tests/gui/` — 需 Qt 环境
- `tests/test_regression_architecture.py` — 需 Qt（导入 `_actions_ops`）
- `*test_ui*.py` — 需 Qt
- `test_scan_misc.py`, `test_groups23_remaining.py`, `test_last_push.py` — 耗时或特殊依赖
- `test_unified_progress.py` — 需 Qt
- `test_ci_scan_fix.py` — 特定环境
- 2 个 deselect 项（文件操作/CLI move）

### 1.3 GUI 测试（tests/gui/）

**测试文件分类**：

| 类别 | 文件数 | 说明 |
|------|--------|------|
| FlowEngine 纯逻辑测试 | 17 | 测试 `*_flow_engine.py`，无 Qt 依赖 |
| E2E 集成测试 | 18 | `@pytest.mark.e2e` 标记，运行完整工作流 |
| Handler 胶水层测试 | 2 | `test_download_handler_c1.py`, `test_log_handler.py` |
| 覆盖率专项测试 | 12 | `test_coverage_*.py`，针对低覆盖模块 |
| 其他 GUI 功能测试 | 29 | 主窗口、对话框、菜单、表格、工作流等 |

**运行策略**：
- CI test-unit-cov job：`tests/gui/` + `test_regression_architecture.py`，排除 `*test_e2e*.py`
- CI test-e2e job：仅 `tests/gui/ -m e2e`，Windows 环境 + pytest-qt

### 1.4 前端测试（web/src/）

**测试分布**：

| 目录 | 文件数 | 用例数 |
|------|--------|--------|
| `views/` | 10 | ~50 |
| `components/` | 7 | ~30 |
| `composables/` | 2 | ~15 |
| `stores/` | 1 | ~10 |
| `api/` | 1 | ~8 |

**前端 E2E**：`web/e2e/dashboard/quick-actions.spec.ts`（Playwright，1 文件 3 用例）

---

## 2. 现有覆盖率配置与数据

### 2.1 后端覆盖率配置

**配置位置**：`pyproject.toml` `[tool.coverage.report]`（无 `.coveragerc` 文件）

```toml
[tool.coverage.report]
fail_under = 0                     # 整体门禁由 CI 分层命令控制
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if __name__ == .__main__.:",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if False:",
]
```

**CI 覆盖率策略（test-unit-cov job）**：

| 层 | 目标 | 阈值 | 实际（2026-07-14 基线） |
|----|------|------|------------------------|
| FlowEngine（纯逻辑） | `handlers/*_flow_engine.py` | **≥95%** | 100%（CI badge） |
| Handler（胶水层） | `handlers/*.py`（排除 FlowEngine） | **≥20%** | 未公布 |
| 整体 | 全部 handlers | **≥68%** | 未公布 |

来源：`.github/workflows/ci.yml` L326-345

### 2.2 GUI 覆盖率收集机制

- **ci.yml test-unit-cov**：`--cov=pilotstd/ui/core/handlers/` 仅在 Windows runner 上收集
- **本地 conftest**（`tests/gui/conftest.py`）：**无** `coverage.process_startup` 或 `sitecustomize` 配置
- GUI 测试的覆盖率收集**完全依赖 `pytest-cov` 的默认行为**，未使用 `coverage.process_startup` 多进程钩子
- 由于 `pilotstd/ui/` 整体（6,092 条语句）在无 GUI 环境覆盖率为 0%，后端覆盖率中被自动排除

### 2.3 前端覆盖率配置

**状态：无覆盖率工具链**

`web/vite.config.ts` 中 `test` 配置：
```ts
test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts'],
    setupFiles: [resolve(__dirname, 'src/test-setup.ts')],
}
```

- 未安装 `@vitest/coverage-v8` 或 `@vitest/coverage-istanbul`
- 无 `coverage` 配置段
- CI `test-frontend` job 无覆盖率步骤
- 前端覆盖率数据**完全缺失**

### 2.4 本地扫描基线（2026-07-31）

```
pytest --cov=pilotstd --cov-branch --cov-report=term-missing -q
  --ignore=tests/gui/ --ignore=tests/test_regression_architecture.py
  --ignore-glob="*test_ui*.py"

结果：2,358 passed, 1 failed (E2E 适配器网络依赖), 7 skipped
总语句：22,582 | 缺失：11,445 | 行覆盖：48%
```

> **注意**：此扫描排除了 GUI 测试，`pilotstd/ui/` 整体为 0%。排除 UI 后，核心后端覆盖率约 **48%**（较 7/14 的 40.3% 提升 7.7 个百分点，测试数从 1,003 → 2,366）。

---

## 3. 覆盖缺口分析

### 3.1 覆盖率 <60% 的模块

| 模块 | 语句数 | 行覆盖 | 主要缺口 |
|------|--------|--------|---------|
| `pilotstd/ui/` | 6,092 | **0%** | 需 Qt 环境，headless 无法测量 |
| `pilotstd/wechat_ip/` | 396 | ~17% | browser.py, cookie_mgr.py, scheduler.py |
| `pilotstd/monitor/` | 226 | ~25% | config.py 34%, handler.py 19%, scheduler.py 18% |
| `pilotstd/tasks/` | 181 | ~15% | favorite_download.py 17%, date_reminder.py 12% |
| `pilotstd/manager/` | 2,342 | ~38% | 6 个 service 0-30%, facade 部分 <50% |
| `pilotstd/announcement/` | 1,316 | ~41% | monitor.py 0%, _announce_fetch.py 21% |
| `pilotstd/query/adapters/mock.py` | 18 | **0%** | 用于 GUI 测试，后端测试不执行 |
| `pilotstd/scan/filename_normalizer.py` | 7 | **0%** | 未编写测试 |
| `pilotstd/scan/watcher.py` | 82 | **0%** | 未编写测试（文件监控守护线程） |
| `pilotstd/task/scheduler.py` | 51 | **0%** | 未编写测试 |
| `pilotstd/platform/notify.py` | 55 | **0%** | 未编写测试（平台通知） |
| `pilotstd/core/notification/_format_utils.py` | 84 | **3%** | 格式化工具函数，仅 3% |

### 3.2 覆盖率 ≥80% 的模块（亮点）

| 模块 | 行覆盖 | 说明 |
|------|--------|------|
| `pilotstd/models.py` | 98% | 数据模型，全面覆盖 |
| `pilotstd/quality/` | 97% | 代码质量检查 |
| `pilotstd/core/std_utils.py` | 97% | 标准号解析工具 |
| `pilotstd/scan/parser/` | 87-100% | 解析器子模块 |
| `pilotstd/query/adapters/`（大部分） | 84-96% | 14 个适配器覆盖良好 |
| `pilotstd/download/models.py` | 100% | 下载模型 |
| `pilotstd/core/db/` | ~85% | 数据库迁移与查询 |

### 3.3 FlowEngine vs Handler 分层分析

**FlowEngine 层（纯逻辑，零 Qt 依赖）**：

| 文件 | 设计意图 | 测试状态 |
|------|---------|---------|
| `actions_flow_engine.py` (17行) | 管线统计收集 | GUI conftest 测试覆盖 |
| `announce_flow_engine.py` (41行) | 公告状态判定 | 专门测试文件 |
| `archive_flow_engine.py` (55行) | 归档状态标签 | 专门测试文件 |
| `auto_flow_engine.py` (18行) | 自动分类逻辑 | 专门测试文件 |
| `cleanup_flow_engine.py` (41行) | 清理目录树操作 | 专门测试文件 |
| `dialog_flow_engine.py` (28行) | 对话框状态管理 | 专门测试文件 |
| `download_flow_engine.py` (100行) | 下载过滤/调度 | 专门测试文件 |
| `file_tree_flow_engine.py` (34行) | 文件树路径处理 | 专门测试文件 |
| `persistence_flow_engine.py` (48行) | 序列化/反序列化 | 专门测试文件 |
| `project_flow_engine.py` (25行) | 项目管理逻辑 | 专门测试文件 |
| `query_flow_engine.py` (87行) | 查询结果构建 | 专门测试文件 |
| `query_summary_flow_engine.py` (38行) | 汇总分桶 | 专门测试文件 |
| `scan_flow_engine.py` (92行) | 扫描状态机 | 专门测试文件 |
| `settings_io_flow_engine.py` (91行) | 配置读写 | 专门测试文件 |
| `table_flow_engine.py` (25行) | 表格数据操作 | 专门测试文件 |
| `table_helper_flow_engine.py` (20行) | 辅助工具方法 | 专门测试文件 |
| `toolbar_flow_engine.py` (25行) | 工具栏状态机 | 专门测试文件 |

**共 17 个 FlowEngine，CI 要求 ≥95% 覆盖率**。每个都有对应的 `test_*_flow_engine.py` 测试文件。

**Handler 层（Qt 胶水层）**：

| 文件 | 行数 | 说明 |
|------|------|------|
| `_announce.py` | 108 | 公告 UI Handler |
| `_archive.py` | 190 | 归档 UI Handler |
| `_auto.py` | 164 | 自动管线 Handler |
| `_cleanup.py` | 219 | 清理 UI Handler |
| `_dialog.py` | 121 | 对话框 Handler |
| `_download.py` | 186 | 下载 UI Handler |
| `_export.py` | 122 | 导出 Handler |
| `_file_dialog.py` | 41 | 文件对话框 |
| `_file_tree.py` | 176 | 文件树 Handler |
| `_persistence.py` | 60 | 持久化 Handler |
| `_project.py` | 57 | 项目 Handler |
| `_query.py` | 196 | 查询 UI Handler |
| `_query_summary.py` | 201 | 查询汇总 Handler |
| `_scan.py` | 142 | 扫描 UI Handler |
| `_settings.py` | 329 | 设置 Handler |
| `_settings_io.py` | 214 | 设置 IO Handler |
| `_table.py` | 114 | 表格 Handler |
| `_table_helper.py` | 160 | 表格辅助 Handler |
| `_theme.py` | 90 | 主题 Handler |
| `_ui_setup.py` | 69 | UI 初始化 |

**共 20 个 Handler，CI 要求 ≥20% 覆盖率**。大部分覆盖率来自 GUI E2E 测试的执行路径。

### 3.4 GUI 模块覆盖率的测量局限

- **真实缺口**：Handler 中有未触达的错误处理分支、冷门对话框路径
- **测量局限**：headless CI 无法运行 Qt 测试，导致 6,092 行统计为 0%；实际在 Windows CI 中通过 `test-unit-cov` 收集了 `handlers/` 的部分覆盖
- **根本原因**：`tests/gui/conftest.py` 未使用 `coverage.process_startup`，多进程 Worker（QueryWorker 等）覆盖率无法追踪

### 3.5 覆盖率门禁设计评估

**现有设计**：

```
test-unit-cov job (Windows only):
  --cov=pilotstd/ui/core/handlers/
  → FlowEngine: fail-under=95 (纯逻辑层，严格)
  → Handler:    fail-under=20 (胶水层，宽容)
  → Overall:    fail-under=68
```

**优点**：
- 分层阈值合理：纯逻辑严控、胶水层放宽
- 覆盖率范围限定在 `handlers/` 子目录，避免全项目扫描的噪音

**缺陷**：
1. **后端覆盖率无门禁**：`test-backend` job 不收集覆盖率，无全项目基线监控
2. **前端覆盖率完全缺失**：无 `@vitest/coverage-v8` 配置
3. **多进程 Worker 覆盖丢失**：`coverage.process_startup` 未配置
4. **无趋势监控**：`coverage-report.md` 仅包含 3 个历史数据点，非自动更新
5. **分支覆盖率未启用门禁**：CI 中用 `--cov-branch` 但门禁只看行覆盖

---

## 4. 测试基础设施

### 4.1 后端工具链

| 工具 | 版本/状态 | 用途 |
|------|----------|------|
| pytest | 9.0.3 | 测试框架 |
| pytest-cov | 7.1.0 | 覆盖率收集 |
| pytest-qt | 4.2.0 | Qt GUI 测试 |
| pytest-xdist | 3.8.0 | 并行测试（`-n auto`） |
| pytest-rerunfailures | CI 安装 | E2E 重试（`--reruns 3`） |

**配置位置**：`pyproject.toml` `[tool.coverage.report]`（覆盖率）、`tests/conftest.py`（markers、collect_ignore、fixtures）、`tests/gui/conftest.py`（GUI 专用）

### 4.2 前端工具链

| 工具 | 版本 | 用途 |
|------|------|------|
| vitest | 4.1.7 | 测试框架 |
| happy-dom | 20.9.0 | DOM 模拟 |
| @vue/test-utils | 2.4.10 | Vue 组件测试 |
| @playwright/test | 1.62.0 | E2E 测试 |
| **@vitest/coverage-v8** | **未安装** | — |

### 4.3 CI 策略

| 维度 | 后端 (test-backend) | 前端 (test-frontend) | GUI E2E (test-e2e) | GUI 单元 (test-unit-cov) | 前端 E2E (frontend-e2e) |
|------|---------------------|---------------------|--------------------|------------------------|------------------------|
| Runner | ubuntu-latest | ubuntu-latest | windows-latest | windows-latest | ubuntu-latest |
| 并行 | `-n auto` | vitest 内置 | 单线程 | 单线程 | Playwright |
| 超时 | — | — | 10min | 25min | 15min |
| 重试 | — | — | `--reruns 3` | — | — |
| Flaky 检测 | 无 | 无 | 隐式（reruns） | 无 | 无 |
| 覆盖率 | 无 | **无** | 无 | `--cov`（分层门禁） | 无 |

### 4.4 Mock / 测试数据管理

| 组件 | 位置 | 说明 |
|------|------|------|
| MockQueryAdapter | `tests/adapters/mock.py` | 固定返回 `status="现行"` 的查询结果 |
| MockDownloadAdapter | `tests/adapters/mock_download.py` | 模拟下载适配器 |
| Mock HTTP | `tests/mocks/mock_http.py` | HTTP 请求模拟 |
| Mock Database | `tests/mocks/mock_database.py` | 数据库模拟 |
| GUI Fixtures | `tests/gui/fixtures/` | 测试用标准文件样本 |
| Template DB | `tests/gui/conftest.py` | Session 级模板 DB，37 个迁移仅执行一次 |
| 网络阻断 | `tests/gui/conftest.py:_block_all_network_requests` | Session 级 responses mock，拦截所有 HTTP |
| QMessageBox patch | `tests/gui/conftest.py:_auto_patch_qmessagebox` | Session 级，所有对话框返回预设值 |
| SmartDialogInterceptor | `tests/gui/helpers/dialog_handler.py` | Qt 事件过滤器，自动关闭弹窗 |

---

## 5. 历史趋势

### 5.1 覆盖率变化（来源：`docs/testing/coverage-report.md`）

| 日期 | 后端覆盖率 | 测试数 | 变更 |
|------|-----------|--------|------|
| 2026-07-14 | **36.7%** | 811 | 初始基线 |
| 2026-07-14 | 37.4% | 902 | +91 tests，新增 5 个测试文件 |
| 2026-07-14 | **40.3%** | 1,003 | +192 tests，重新启用 4 个排除测试 |
| 2026-07-31 | **48.0%** | 2,366 | +1,363 tests，本地扫描基线 |

### 5.2 覆盖率变动分析

**显著提升模块**（自 7/14 以来）：
- `pilotstd/scan/parser/` — 87-100%（新增 edition_detect, parser 专项测试）
- `pilotstd/query/routing/` — scorer.py 95%（新增 scorer 测试）
- `pilotstd/core/notification/` — 多模块 74-100%（新增 10 个通知测试文件）
- `pilotstd/organizer/` — mover.py 100%, industry_lookup.py 98%

**回落/停滞模块**：
- `pilotstd/tasks/` — 仍 ~15%（favorite_download、date_reminder 无测试）
- `pilotstd/monitor/` — 仍 ~25%（无新增测试）
- `pilotstd/wechat_ip/` — 仍 ~17%（企业微信 IP 模块，无测试）

---

## 6. 核心发现与建议

### 6.1 关键发现

1. **前端覆盖率工具链完全缺失** — 无 `@vitest/coverage-v8`，无法量化前端测试质量
2. **后端覆盖率从 36.7% → 48.0%**，2,366 用例（较基线 +1,555），进步显著
3. **FlowEngine 层架构设计优秀** — 纯逻辑提取 + 一一对应测试，CI 门禁 95%
4. **0% 覆盖的 6 个模块需关注** — 并非所有都值得测试（如 `mock.py` 本身就是测试工具）
5. **多进程 Worker 覆盖丢失** — 无 `coverage.process_startup` 配置
6. **GUI 覆盖率数据不可靠** — 6,092 行 0% 仅表示 headless 无法测量，不代表无测试
7. **无自动化趋势监控** — `coverage-report.md` 需手动更新

### 6.2 改进建议（优先级排序）

| 优先级 | 建议 | 投入 | 收益 |
|--------|------|------|------|
| P0 | 前端添加 `@vitest/coverage-v8`，设基线门禁 ≥60% | 低 | 前端测试质量可量化 |
| P0 | 后端 test-backend job 新增覆盖率收集 + 趋势上传 | 低 | 阻止覆盖率倒退 |
| P1 | 配置 `coverage.process_startup` 追踪 Worker 子进程 | 中 | GUI 测试覆盖率准确 |
| P1 | 为 `pilotstd/task/scheduler.py` 编写测试（0%→≥80%） | 中 | 核心调度器安全保障 |
| P2 | 为 `pilotstd/monitor/` 编写测试 | 中 | 文件监控安全保障 |
| P2 | 为 `pilotstd/wechat_ip/` 编写测试（或标记为可选） | 低 | 企业微信 IP 模块保障 |
| P3 | CI 添加覆盖率趋势徽章 + 自动化报告 | 中 | 可视化趋势 |

---

## 7. 数据来源索引

| 数据项 | 来源 |
|--------|------|
| 测试文件/用例计数 | `pytest --collect-only` 本地执行 |
| 前端测试计数 | `npx vitest run` 本地执行 |
| 覆盖率行级数据 | `pytest --cov=pilotstd --cov-branch --cov-report=term-missing` 本地扫描（2026-07-31） |
| 历史覆盖率趋势 | `docs/testing/coverage-report.md`（2026-07-14 基线） |
| CI 覆盖率配置 | `.github/workflows/ci.yml` L296-345 |
| 覆盖率排除规则 | `pyproject.toml` `[tool.coverage.report]` |
| 测试排除规则 | `tests/conftest.py` `collect_ignore` + CI `--ignore` 参数 |
| GUI 测试配置 | `tests/gui/conftest.py` |
| 前端测试配置 | `web/vite.config.ts` `test` 段 |
| Mock 实现 | `tests/adapters/`, `tests/mocks/`, `tests/gui/helpers/` |
| 已知问题 | `docs/testing/known-issues.md` |
| 文档化覆盖率 | `STATUS.md`（测试数 771 → 但实际已到 2,366，文档未同步更新） |
