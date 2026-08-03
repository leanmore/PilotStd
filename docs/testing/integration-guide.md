# 集成测试编写指南

P4 阶段建立的 HTTP 状态机集成测试体系。使用 `pytest-httpserver` 模拟外部 API 的完整协议链路。

## 快速开始

```bash
pip install pytest-httpserver
pytest tests/integration/ -v
```

## 架构决策

### 为什么用 pytest-httpserver 而非 responses/respx？

| 工具 | 适用场景 | 本项目用途 |
|------|---------|-----------|
| `responses` | 单次 HTTP 请求 mock（`requests` 库） | E2E: `detect_ip` |
| `respx` | 单次 HTTP 请求 mock（`httpx` 库） | E2E: `gongbiaoku` |
| **`pytest-httpserver`** | **多步状态机协议**（Cookie/Session/顺序验证） | Integration: `BaiduOcrProvider` |

`pytest-httpserver` 启动真实 HTTP 服务器，`requests.Session` 可自动管理 Cookie，无需手动模拟状态传递。适用于需要验证"第一步的 Cookie 传递到第二步"的场景。

### 为什么百度云可测而腾讯/阿里不可测？

| 提供商 | 认证方式 | 可测性 |
|--------|---------|:--:|
| 百度云 | `access_token` Bearer（query param） | ✅ URL 级别注入 |
| 腾讯云 | TC3-HMAC-SHA256 签名（请求头） | ❌ 签名嵌入请求体 hash |
| 阿里云 | 阿里云签名（请求头） | ❌ 同上 |

腾讯/阿里云的签名算法将请求体 hash 嵌入 `Authorization` 头，替换 URL 会导致签名失效。建议通过单元测试覆盖签名逻辑本身，HTTP 调用标记为 E2E scope。

## 编写规范

### 目录结构

```
tests/integration/
├── __init__.py
├── conftest.py          # 共享 fixtures (HTTPServer + monkeypatch)
└── test_baidu_ocr.py    # 按被测模块命名
```

### Fixture 命名约定

| 后缀 | 含义 | 示例 |
|------|------|------|
| `_server` | `pytest-httpserver` 实例 | `baidu_server` |
| `_provider` | 已注入 mock 的生产实例 | `baidu_provider` |

### Mock 粒度

```
✅ 正确: mock 外部 API 的 HTTP 层，测试生产代码的完整调用链
   monkeypatch safe_raw_post → 重定向到 httpserver → 测试 BaiduOcrProvider.recognize_pdf()

❌ 错误: mock 被测函数内部逻辑
   monkeypatch BaiduOcrProvider._get_access_token → 直接返回假 token
```

### 状态验证

```python
# ✅ 正确: 验证协议步骤的顺序和完整性
def _handle_ocr(request):
    if request.args.get("access_token") != MOCK_TOKEN:
        return Response(status=401)  # 验证 token 传递
    ...

# ✅ 正确: 直接操控内部状态模拟降级
provider._access_token = "INVALID_TOKEN"
provider._token_expire = time.time() + 3600  # 跳过缓存刷新
```

### 超时设置

所有 handler 函数应为同步、快速返回（<1ms）。若 handler 中有 `time.sleep()`，改用 `httpserver` 的延迟响应机制。

## Monkeypatch 模式

### 模式 1: URL 重定向（推荐）

```python
# conftest.py
@pytest.fixture
def baidu_provider(baidu_server, monkeypatch):
    import pilotstd.query.network as net
    base = baidu_server.url_for("/")[:-1]

    def _mock_get(url, *a, **kw):
        return net.safe_raw_get.__wrapped__(
            url.replace("https://aip.baidubce.com", base), *a, **kw
        )

    monkeypatch.setattr(net, "safe_raw_get", _mock_get)
    # 同样处理 safe_raw_post
```

### 模式 2: 内部状态操控

```python
# test_baidu_ocr.py
def test_invalid_token_returns_error(self, baidu_server, monkeypatch):
    # ... setup monkeypatch ...
    provider = BaiduOcrProvider(api_key="ak", secret_key="sk")
    # 操控缓存绕过 token 刷新
    provider._access_token = "INVALID_TOKEN"
    provider._token_expire = time.time() + 3600

    result = provider.recognize_pdf(MINIMAL_PDF)
    assert result.ok is False
```

## 故障排查

| 症状 | 根因 | 修复 |
|------|------|------|
| handler 返回 500 + `AttributeError: 'HTTPServer' object has no attribute 'Response'` | pytest-httpserver 1.x 无 `httpserver.Response` | 改用 `werkzeug.wrappers.Response` |
| token 缓存不生效 | `_token_expire` 默认值 0，`time.time() < 0` 为 False | 同时设置 `_access_token` 和 `_token_expire` |
| GET 请求 handler 读不到 body | `request.get_data()` 仅对 POST/PUT 有效 | GET 参数用 `request.args.get()` |
| `safe_raw_post` patch 不生效 | 被测模块 `lazy import` 在方法内部 | patch 定义站点 `pilotstd.query.network`，非调用站点 |
| parallel coverage 合并失败 | 不同 worker 的 `.coverage` 文件名冲突 | 使用 `--cov-config=tests/e2e/.coveragerc` 的 `parallel=true` |

## 基线刷新 SOP

1. 新增集成测试后，运行 `pytest tests/integration/ --cov=pilotstd --cov-report=term`
2. 记录新覆盖率到 `docs/testing/testing-baseline.md`
3. 若覆盖率显著下降（>2%），排查是否新增未测模块
4. 每季度回顾一次基线趋势，由团队共识决定是否调整目标覆盖范围
