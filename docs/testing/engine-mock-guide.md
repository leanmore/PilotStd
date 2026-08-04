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
| `_batch.py` | 60% 基线 | `BatchHandler` 需 `BatchDispatcher` + EngineCore | 批量分派桩 |
| `_single.py` | 65% 基线 | `SingleQueryHandler` 需 Engine + adapter 注册表 | 适配器注册桩 |
| `_routing.py` | 48% 基线 | 评分器 + 全适配器链 | 评分器桩 |

## Phase 2 待补桩清单

> 基线: 2026-07-31, TOTAL 59.77% (22582 stmts, 9084 missed).
> 目标: ≥62% 本地覆盖率，优先消化高 missed 模块。

### 高优先级（missed ≥ 30）

| 模块 | 语句数 | Missed | 当前覆盖率 | Mock 状态 |
|------|:---:|:---:|:---:|------|
| `core/notification/manager.py` | 213 | 51 | 76% | 需渠道类字典桩 |
| `core/notification/_format_utils.py` | 84 | 49 | 42% | 纯逻辑，无需 Mock |
| `core/notification/_builders_batch.py` | 109 | 38 | 65% | 需消息构建桩 |
| `core/notification/_credentials.py` | 58 | 26 | 55% | 需凭证桩 |
| `core/notification/_builders_system.py` | 91 | 21 | 77% | 需消息构建桩 |
| `core/notification/aggregate_buffer.py` | 150 | 21 | 86% | 纯逻辑 |
| `core/notification/channel.py` | 26 | 2 | 92% | ABC 接口已验证，子类待补 |
| `core/notification/channels/dingtalk.py` | 50 | 10 | 80% | ChannelStub 已就绪 |
| `core/notification/channels/feishu.py` | 33 | 6 | 82% | ChannelStub 已就绪 |
| `core/notification/channels/telegram.py` | 56 | 12 | 79% | ChannelStub 已就绪 |
| `core/notification/channels/wechat.py` | 30 | 5 | 83% | ChannelStub 已就绪 |
| `query/engine/_routing.py` | 129 | 67 | 48% | 需评分器桩 |
| `query/engine/_mini_bucket.py` | 159 | 38 | 76% | mini_bucket_mock_tree 已就绪 |
| `query/engine/_overflow.py` | 95 | 25 | 74% | 需溢出逻辑桩 |
| `query/engine/_metrics.py` | 80 | 25 | 69% | 需指标桩 |
| `query/engine/_single.py` | 99 | 8 | 92% | 剩余少量可补 |
| `query/engine/_core.py` | 61 | 22 | 64% | 需 EngineCoreMock |
| `query/rotator.py` | 226 | 88 | 61% | 需 rotator mock |

### 中优先级（missed 15-29）

| 模块 | 语句数 | Missed | 当前覆盖率 |
|------|:---:|:---:|:---:|
| `core/db/_migrate_v31_plus.py` | 95 | 6 | 94% |
| `core/db/database.py` | 240 | 58 | 76% |
| `core/db/migrations.py` | 241 | 46 | 81% |
| `core/logger.py` | 98 | 19 | 81% |
| `core/notification/renderer.py` | 171 | 16 | 91% |
| `core/notification_aggregator.py` | 127 | 23 | 82% |
| `query/cache.py` | 63 | 20 | 68% |

### 阻塞项

> 记录因路径/依赖问题无法补测的模块及原因。
> (待 Phase 2 执行过程中填充)

### 扫射优先级

1. **渠道类字典桩** — mock `_CHANNEL_CLASSES` 使 `_init_channels` 可测试
2. **`_format_utils.py`** — 纯逻辑，最高 ROI（49 missed, 无依赖）
3. **单查询桩** — mock `SingleQueryHandler` 的 search 方法
4. **批量分派桩** — mock `BatchDispatcher` 的线程池
5. **适配器注册桩** — mock adapter registry 的懒加载函数
