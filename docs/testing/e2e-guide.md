# E2E 测试指南

P3 阶段建立的 HTTP 边界集成测试体系。验证外部 API 交互的正确性，mock 全部网络调用。

## 快速开始

```bash
# 安装依赖
pip install -r requirements-dev.txt

# 运行全部 E2E 测试（8 用例，~3.3s）
pytest tests/e2e/ -v

# 运行特定模块
pytest tests/e2e/test_detect_ip_e2e.py -v
pytest tests/e2e/test_gongbiaoku_query_e2e.py -v
```

## Mock 策略

| 被测 HTTP 库 | Mock 工具 | 模式 |
|-------------|----------|------|
| `requests` | `responses` | `@responses.activate` + `responses.add()` / `responses.replace()` |
| `httpx` | `respx` | `@respx.mock` + `respx.get().respond()` + Client 注入 |

### 通用原则

1. **安全基线**：先 mock 所有已知端点为失败（500），再 `replace` 需要测试的端点
2. **精确断言**：验证 `route.called` 确保 mock 被命中（防止假绿）
3. **零状态泄漏**：每个测试独立路由表，function 级隔离
4. **不测状态机**：多步 Session/Cookie/验证码链路属于集成测试范畴，不在 E2E scope 内

## 用例矩阵

| 模块 | 用例数 | Mock 工具 | 覆盖场景 |
|------|:--:|----------|---------|
| `detect_ip` | 4 | `responses` | 众数/平票/全败/无效内容 |
| `gongbiaoku.query_standards` | 4 | `respx` | 正常解析/空结果/HTTP错误/网络错误 |

## 添加新 E2E 测试

1. 确认目标函数满足：单次 HTTP 调用、无状态依赖、结构化返回
2. 选择合适的 mock 工具（requests → responses, httpx → respx）
3. 在 `tests/e2e/` 下新建 `test_<module>_e2e.py`
4. 至少覆盖：正常返回 + 空结果 + HTTP 错误 + 网络异常 四个场景

## CI 集成

E2E 测试在 `test-backend` job 中自动运行（无需 GUI/Qt 依赖）。`responses` 和 `respx` 已加入 CI 依赖安装步骤。

## 故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| `responses.calls` 为空 | mock URL 与请求 URL 不匹配 | 检查 query params / trailing slash |
| `respx` route 未命中 | `httpx.Client` 未被注入 | 确认使用 `GongBiaoKuAdapter(client=client)` 模式 |
| CI `ModuleNotFoundError: respx` | CI 未安装 respx | 检查 `.github/workflows/ci.yml` pip install 行 |
