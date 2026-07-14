# 覆盖率报告

| 属性 | 值 |
|------|-----|
| 生成日期 | 2026-07-14 |
| 测试框架 | pytest + pytest-cov |
| 测试范围 | `tests/`（排除 gui/、e2e、pipeline_router 等） |
| 测试结果 | 811 passed, 2 skipped, 85 deselected, 2 xfailed |

## 整体覆盖率

**行覆盖率: 36.7%**（18,595 条语句，11,774 条未覆盖）

> **注意**：`pilotstd/ui/` 子目录（6,092 条语句）在 headless 环境下覆盖率为 0%，GUI 测试在 CI 中由独立 `test-gui` job 运行。排除 UI 代码后，后端覆盖率为 **45.4%**。

## 各模块覆盖率

| 模块 | 语句数 | 覆盖率 | 状态 |
|------|--------|--------|:--:|
| `pilotstd/models.py` | 62 | 98.4% | ✅ |
| `pilotstd/quality/` | 65 | 92.3% | ✅ |
| `pilotstd/__init__.py` | 11 | 81.8% | ✅ |
| `pilotstd/cli/` | 350 | 81.1% | ✅ |
| `pilotstd/i18n/` | 35 | 74.3% | ❌ |
| `pilotstd/task/` | 255 | 71.4% | ❌ |
| `pilotstd/scan/` | 788 | 70.9% | ❌ |
| `pilotstd/download/` | 417 | 69.1% | ❌ |
| `pilotstd/query/` | 2,416 | 67.5% | ❌ |
| `pilotstd/pipeline/` | 196 | 66.8% | ❌ |
| `pilotstd/platform/` | 167 | 62.3% | ❌ |
| `pilotstd/core/` | 3,128 | 62.3% | ❌ |
| `pilotstd/organizer/` | 152 | 61.2% | ❌ |
| `pilotstd/announcement/` | 1,316 | 41.4% | ❌ |
| `pilotstd/manager/` | 2,342 | 37.9% | ❌ |
| `pilotstd/tasks/` | 181 | 6.1% | ❌ |
| `pilotstd/monitor/` | 226 | 0.0% | ❌ |
| `pilotstd/ui/` | 6,092 | 0.0% | ❌ |
| `pilotstd/wechat_ip/` | 396 | 0.0% | ❌ |

## 低于 80% 阈值模块清单

以下 14 个模块覆盖率低于 80%，按覆盖率从高到低排列：

| # | 模块 | 覆盖率 | 语句数 | 主要缺口 |
|---|------|--------|--------|---------|
| 1 | `pilotstd/i18n/` | 74.3% | 35 | 语言回退路径未覆盖 |
| 2 | `pilotstd/task/` | 71.4% | 255 | `scheduler.py` 0% |
| 3 | `pilotstd/scan/` | 70.9% | 788 | `watcher.py` 0%, `filename_normalizer.py` 0% |
| 4 | `pilotstd/download/` | 69.1% | 417 | `openstd_download.py` 19% |
| 5 | `pilotstd/query/` | 67.5% | 2,416 | `csres.py` 27%, `rotator.py` 32% |
| 6 | `pilotstd/pipeline/` | 66.8% | 196 | `router.py` 67% |
| 7 | `pilotstd/platform/` | 62.3% | 167 | `notify.py` 0% |
| 8 | `pilotstd/core/` | 62.3% | 3,128 | 通知渠道(26-39%), `validity_checker.py` 34% |
| 9 | `pilotstd/organizer/` | 61.2% | 152 | `mover.py` 42% |
| 10 | `pilotstd/announcement/` | 41.4% | 1,316 | `monitor.py` 0%, `matcher.py` 16% |
| 11 | `pilotstd/manager/` | 37.9% | 2,342 | 6 个 service 0%, facade 多数 <30% |
| 12 | `pilotstd/tasks/` | 6.1% | 181 | `favorite_download.py` 0% |
| 13 | `pilotstd/monitor/` | 0.0% | 226 | 全模块无测试 |
| 14 | `pilotstd/wechat_ip/` | 0.0% | 396 | 全模块无测试 |
| — | `pilotstd/ui/` | 0.0% | 6,092 | GUI 代码，需 Qt 环境（独立 job 运行） |

## 门禁状态

| 门禁 | 阈值 | 当前值 | 状态 |
|------|------|--------|:--:|
| G-034 覆盖率阈值 | ≥ 80% | 36.7% | ❌ 不通过 |

> **说明**：G-034 在当前覆盖率水平下会持续阻断。建议在覆盖率提升到 80% 之前暂不启用 G-034，或将阈值调整为阶段性目标（如 40% → 50% → 80% 渐进式提升）。

## 覆盖率历史

| 日期 | 覆盖率 | 测试数 | 变更说明 |
|------|--------|--------|---------|
| 2026-07-14 | 36.7% | 811 | 初始覆盖率基线（pytest --cov 实测） |
