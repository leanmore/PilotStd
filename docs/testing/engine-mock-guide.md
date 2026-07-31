# Engine/DB Mock 基础设施使用指南

> Phase 1 交付物。供扫射 Phase 2 使用。

## 快速开始

```python
from tests.fixtures.engine_mock_tree import (
    EngineCoreMock, MemoryDB, ChannelStub, ConfigStub, mini_bucket_mock_tree
)
```

## 组件说明

### EngineCoreMock

模拟 `EngineCore`，提供 `rotator`/`db`/`ctx`/`dispatch` 注入点。

```python
with EngineCoreMock() as core:
    core.rotator._sites["ahbz"] = mock_site_state
    core.rotator.get_cooldown_remaining("ahbz")  # → 秒数或 0
    handler = SomeHandler(core, routing, single)
```

### MemoryDB

SQLite `:memory:` 连接，含完整 notification 表 schema。

```python
with MemoryDB() as db:
    db.execute("INSERT INTO notification_log (...) VALUES (...)")
    rows = db.fetchall("SELECT * FROM notification_log")
```

### ChannelStub

模拟通知渠道，`send()` 记录调用历史。

```python
ch = ChannelStub("telegram", should_succeed=True)
assert ch.send(msg) is True
assert len(ch.sent) == 1  # 验证发送次数
```

### ConfigStub

模拟配置对象，支持点号分隔的多层 key。

```python
cfg = ConfigStub({"notification.enabled": True, "notification.quiet_hours_start": "22:00"})
assert cfg.get("notification.enabled") is True
```

### mini_bucket_mock_tree

一键构建 `MiniBucketHandler` 所需的完整 Mock 树。

```python
with mini_bucket_mock_tree({"site_a": {"cooldown_until": 0}}) as (core, routing, single):
    handler = MiniBucketHandler(core, routing, single)
    buckets = handler._build_mini_buckets(items, chain, weights)
```

## 已知限制

| 模块 | 当前覆盖率 | 未覆盖原因 | Phase 2 需补充 |
|------|:---:|------|------|
| `manager.py` | 47% (+8pp vs 基线39%) | `_init_channels` 需 mock `_CHANNEL_CLASSES` 字典和 `CredentialHelper` | 渠道类字典桩 |
| `_mini_bucket.py` | 40% | `_process_single_query`/`_run_mini_bucket_queries` 需完整查询引擎 | 单查询桩+线程池桩 |
| `channel.py` | 接口已验证 | `NotificationChannel` 是 ABC，具体实现在 channels/ 子模块 | 各渠道子类测试 |
| `_batch.py` | 60% 基线 | `BatchHandler` 需 `_BatchDispatchMixin` + EngineCore | 批量分派桩 |
| `_single.py` | 65% 基线 | `SingleQueryHandler` 需 Engine + adapter 注册表 | 适配器注册桩 |
| `_routing.py` | 48% 基线 | 评分器 + 全适配器链 | 评分器桩 |

## Phase 2 扫射集成

待 Phase 2 启动时，按以下优先级补全桩对象：

1. **渠道类字典桩** — mock `_CHANNEL_CLASSES` 使 `_init_channels` 可测试
2. **单查询桩** — mock `SingleQueryHandler` 的 search 方法
3. **批量分派桩** — mock `_BatchDispatchMixin` 的线程池
4. **适配器注册桩** — mock adapter registry 的懒加载函数
