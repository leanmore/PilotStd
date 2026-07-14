# 已知问题

| 属性 | 值 |
|------|-----|
| 状态 | 活跃 |
| 版本 | v1.0 |
| 创建日期 | 2026-07-14 |
| 关联 | `tests/test_adapters.py`、`tests/test_e2e_adapters.py` |

本文档记录当前已知但尚未修复的问题。已修复的问题不在此列。

## 一、未修复问题

### 1. njbz365 适配器多词前缀 match_status 返回 "mismatch"

| 属性 | 值 |
|------|-----|
| 问题描述 | `parse_std_number` 多词前缀修复后（如 `DIN EN` → code=`DINEN`），njbz365 适配器的 `match_result` 逻辑未同步调整，导致多词前缀标准（DIN EN、BS EN ISO）的匹配状态返回 `"mismatch"` 而非 `"exact"` |
| 影响范围 | njbz365 适配器对多词前缀国外标准的查询匹配 |
| 当前状态 | 已标记 xfail（`test_din_exact_match`、`test_bs_exact_match`），不影响 CI |
| 测试位置 | `tests/test_adapters.py::TestNjbz365Adapter::test_din_exact_match`、`test_bs_exact_match` |
| 计划修复 | 同步 njbz365 适配器的 `match_result` 调用逻辑，使其与 `parse_std_number` 的多词前缀输出一致，然后移除 xfail |

### 2. StdGovAdapter 端到端测试依赖外部 API

| 属性 | 值 |
|------|-----|
| 问题描述 | `test_e2e_adapters.py` 中 `test_gb_exact_match` 直接调用 `StdGovAdapter.query_with_strategy()` 发起真实 HTTP 请求，无法在 CI 环境中可靠运行 |
| 影响范围 | 仅影响 CI 中的端到端测试覆盖 |
| 当前状态 | 已标记 `@unittest.skip("外部 API 依赖 — CI 中跳过")` |
| 测试位置 | `tests/test_e2e_adapters.py::TestStdGovAdapter::test_gb_exact_match` |
| 计划修复 | 使用 mock HTTP 响应替代真实请求，或将此测试移入需要网络环境的独立测试套件 |

## 二、测试收集排除项

以下测试文件未纳入 pytest 自动收集（通过 `tests/conftest.py` 中 `collect_ignore` 排除）：

| 文件 | 排除原因 |
|------|---------|
| `stress_selfcheck.py` | 独立压测脚本，含模块级 `sys.exit` |
| `stress_web.py` | 独立压测脚本 |
| `stress_docker.py` | 独立压测脚本 |
| `stress_cli.py` | 独立压测脚本 |
| `stress_runner.py` | 独立压测脚本入口 |
| `stress_driver.py` | 已废弃，由 stress_runner.py + stress_cli.py 替代 |
| `stress_winui.py` | 由 stress_runner.py 显式调用 |
| `gui/` | GUI 测试需 Qt 环境，CI 中由独立 job 运行 |

## 三、门禁联动

当以下文件发生变更时，需确认关联的已知问题是否有进展或需更新：

| 变更文件 | 关联问题 |
|----------|---------|
| `pilotstd/query/adapters/njbz365.py` | 问题 1（match_status 逻辑） |
| `pilotstd/core/std_utils.py`（`parse_std_number`） | 问题 1（多词前缀解析） |
| `pilotstd/query/adapters/std_gov.py` | 问题 2（端到端测试） |

## 四、版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0 | 2026-07-14 | 初始版本，记录 njbz365 match_status 和 StdGovAdapter e2e 两个已知问题 |
