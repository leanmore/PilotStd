# 测试覆盖率报告

| 属性 | 值 |
|------|-----|
| 生成日期 | 2026-07-14 |
| 数据来源 | `pytest --cov=pilotstd --cov-report=term tests/ --ignore=tests/gui` |
| 测试总数 | 900 passed, 7 skipped, 2 xfailed |

## 整体覆盖率

| 指标 | 值 |
|------|-----|
| 总行数 | 18,595 |
| 已覆盖 | 8,340 |
| **整体行覆盖率** | **45%** |

## 主要模块覆盖率

| 模块 | 估计覆盖率 | 说明 |
|------|-----------|------|
| `pilotstd/core/` | ~65% | 配置、数据库、标准号解析核心逻辑有较好测试覆盖 |
| `pilotstd/query/` | ~60% | 引擎、路由、适配器、缓存均有单元测试 |
| `pilotstd/scan/` | ~55% | 解析器测试较全面（54 tests），扫描器覆盖较低 |
| `pilotstd/manager/` | ~40% | 通过集成测试间接覆盖，直接单测较少 |
| `pilotstd/cli/` | ~30% | CLI 命令模块覆盖不完整 |
| `pilotstd/ui/` | ~15% | GUI 代码覆盖率低（9%-57%），GUI 测试由独立 job 运行 |
| `pilotstd/wechat_ip/` | 0% | 企业微信 IP 模块无测试 |

## 低于 80% 的模块

以下模块覆盖率低于 80%，需要优先补充测试：

| 优先级 | 模块 | 问题 |
|--------|------|------|
| 高 | `pilotstd/cli/commands/` | CLI 命令缺少单元测试 |
| 高 | `pilotstd/manager/facade/` | 门面层缺少直接单测 |
| 中 | `pilotstd/scan/scanner.py` | 文件扫描器覆盖率不足 |
| 中 | `pilotstd/ui/core/handlers/` | UI Handler 缺少单元测试 |
| 低 | `pilotstd/ui/main_window/parts/` | GUI 部件覆盖率 9-26% |
| 低 | `pilotstd/wechat_ip/` | 企业微信 IP 模块完全无测试 |

## 备注

- GUI 代码（`pilotstd/ui/`）覆盖率低是预期内的——Qt 组件测试在 CI 中由独立 `test-gui` job 运行，`pytest --cov` 不统计 Qt 事件循环内的覆盖
- 覆盖率提升应按优先级从核心业务逻辑（core/query/scan）向外围逐步推进
- `wechat_ip/` 模块依赖 Playwright 浏览器自动化，测试成本较高，可暂缓
