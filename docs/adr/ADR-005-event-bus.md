# ADR-005: EventBus 事件总线重构（P9）

> 日期：2026-07-16
> 状态：✅ 已落地
> 关联：[[ADR-002]]

---

## 背景

`_scan.py`、`_query.py`、`_download.py`、`_archive.py` 之间存在通过构造函数回调参数（`run_scan_cb`、`run_query_cb` 等）传递的隐式耦合，`_auto.py` 依赖 4 个 Handler 的具体回调签名。

---

## 决策

引入单例 `EventBus`（`pilotstd/ui/core/event_bus.py`，零第三方依赖），提供 `subscribe`/`unsubscribe`/`publish` API。

### 关键设计

- `QMutex` 保护 `_subscribers` 读写（跨线程安全）
- `QMetaObject.invokeMethod` + `Qt.QueuedConnection` 将回调切换至主线程执行
- 订阅默认使用 `weakref`，Handler 销毁时自动解绑
- 测试隔离：`EventBus.reset()` 清空单例状态，`autouse` fixture 自动注入

### 迁移范围

| Handler | 发布事件 |
|---------|---------|
| `_scan.py` | `scan.batch_ready`, `scan.finished`, `scan.error` |
| `_query.py` | `query.finished`, `query.error` |
| `_download.py` | `download.progress`, `download.finished`, `download.error` |
| `_archive.py` | `archive.progress`, `archive.error`, `archive.finished` |
| `_auto.py` | `auto.stage.<stage>`, `auto.pipeline.finished`, `auto.pipeline.error` |

### 向后兼容

所有原有回调/信号连接完整保留，事件发布为追加行为。Handler 对外接口签名不变。

`_core.py` 使用构造函数注入模式，无需方法级调用点替换。

---

## 测试覆盖

`tests/gui/test_event_bus_integration.py` — 单例 + 订阅/取消 + 线程安全 + 弱引用 + Auto Pipeline 事件 + Handler 迁移回归。

---

## 实施阶段

| 阶段 | 内容 | 状态 |
|------|------|:--:|
| A1 | 基础设施（EventBus 单例 + 测试） | ✅ |
| A2 | Handler 迁移（scan/query/download/archive/auto） | ✅ |
| A3 | 集成测试 + 回归验证 | ✅ |
