# 通知模块拆分（阶段 P）：职责盘点 + 拆分方案 + 实施设计

> **本轮性质**：只设计、不实施。**约束：禁止新增 mixin**（含多重继承拼装）。
> **上游**：[03-impl-design-D.md](03-impl-design-D.md)（D 阶段设计，其最大障碍正是本文件要解决的 `manager.py` 行数）、[00-framework.md](00-framework.md)
> **决策者裁决**：`manager.py` 必须先拆（阶段 P 独立批次，作为 D 的前置）；拆分范围含整个 `pilotstd/core/notification/`；加防膨胀门禁；禁止新增 mixin。
> **口径**：规模统计一律沿用 G-010 口径（`scripts/check_g_010_code_size.py:73-110`：排除空行与 `#` 注释行）；行号均为 2026-10-03 实测。

---

## 摘要（决策者读）

1. **全目录 29 个 Python 文件、合计 4,530 有效行**；`manager.py` **498**（距 500 阻断线**仅 2 行**，唯一超 400 警告线者）。**下一批瓶颈已出现**：`_builders_system.py` **400**、`_builders_batch.py` **392** —— 拆分产物**绝不能**放进这两个文件。
2. **`manager.py` 共 45 个成员条目**：模块样板 92 行、生命周期装配 133、构建器注册与消息构建 71、主发送链 69、静音队列 68、投递健康度 46、日志/策略/测试入口 14（类体 407 含类 docstring）。**无任何函数超 80 行**（最大 `__init__` 65）。
3. **对外耦合面很宽**：178 处 `._xxx` 私有访问；`_CHANNEL_CLASSES` 被 **19 处 `mock.patch`** 锁定；`_QUEUE_MESSAGE_FIELDS` 被 **5 处测试 import**；`logger` 被 1 处 patch；生产代码还直接读 `NotificationManager` 的 3 个私有属性（`docker/api/notification.py` 7 处 `_cred_helper`）。
4. **决定性约束（本轮最重要发现）**：`tests/test_aggregate_buffer.py:551-556` 用 `MagicMock(spec=NotificationManager)` + `NotificationManager._validate_message.__get__(mgr)` 调用真方法 —— `spec=` 的 mock **只认类上存在的属性**，因此**转发体一旦访问实例独有属性（`__init__` 里赋的那些）就会 AttributeError**。⇒ 被这种模式调用的方法**必须纯函数化，转发体零 `self` 访问**。
5. **已有 mixin 门禁**：`tests/test_architecture_mixin_guard.py:9,27-28` 按类名 `endswith("Mixin")` 扫描，白名单仅 `_WindowLifecycleMixin`；目录内 **未发现任何 mixin**（13 处继承全是正规基类：`NotificationBlock`/`NotificationChannel(ABC)`/`BlockRenderer`）。ADR-010 已把 16 个 mixin 收敛到 1 个，并规定未来用 **Composition + `_DispatchContext`**（`docs/adr/ADR-010-mixin-refactor.md:74`）。
6. **提出 2 个方案**：**方案 A（两块纯函数化，manager ≈ 320 行，测试零改动）** 与 **方案 B（四块 + `_ManagerContext`，manager ≈ 220 行，但有 2 处测试静默失效风险）**。**我倾向 A**：余量已足够（180 行），且 A 是 B 的子集，可增量演进。
7. **零行为变更判据 6 条**（Z1–Z6），逐条可断言（测试三元组不变 / 签名快照比对 / 调用序列比对 / 类属性契约 / 行数上限 / 门禁 EXIT=0）。
8. **防膨胀门禁**：建议新增 **G-048**（`gates.md` 现最大编号 G-047），只管 `pilotstd/core/notification/**`；阈值 410/370 可立即上线（现存最大 400），350 则需存量白名单（见待裁决 N2）。

---

# 第一部分：职责盘点

## 1.1 目录规模（29 文件，按有效行降序）

| 有效行 | 原始行 | 距 500 | 距 400 | 档位 | 文件 |
|---|---|---|---|---|---|
| **498** | 609 | **2** | -98 | ⚠️WARN | `pilotstd/core/notification/manager.py` |
| **400** | 473 | 100 | **0** | ok（临界） | `pilotstd/core/notification/_builders_system.py` |
| **392** | 468 | 108 | **8** | ok（临界） | `pilotstd/core/notification/_builders_batch.py` |
| 361 | 485 | 139 | 39 | ok | `pilotstd/core/notification/aggregate_buffer.py` |
| 303 | 450 | 197 | 97 | ok | `pilotstd/core/notification/renderer.py` |
| 256 | 324 | 244 | 144 | ok | `pilotstd/core/notification/security_notifier.py` |
| 213 | 257 | 287 | 187 | ok | `pilotstd/core/notification/_builders_task_results.py` |
| 204 | 237 | 296 | 196 | ok | `pilotstd/core/notification/_builders_validity.py` |
| 183 | 233 | 317 | 217 | ok | `pilotstd/core/notification/channels/telegram.py` |
| 171 | 279 | 329 | 229 | ok | `pilotstd/core/notification/mapping.py` |
| 167 | 209 | 333 | 233 | ok | `pilotstd/core/notification/_manager_ops.py` |
| 164 | 213 | 336 | 236 | ok | `pilotstd/core/notification/_credentials.py` |
| 149 | 176 | 351 | 251 | ok | `pilotstd/core/notification/_format_utils.py` |
| 111 | 144 | 389 | 289 | ok | `pilotstd/core/notification/channels/dingtalk.py` |
| 98 | 145 | 402 | 302 | ok | `pilotstd/core/notification/delivery_health.py` |
| 98 | 129 | 402 | 302 | ok | `pilotstd/core/notification/events.py` |
| 92 | 110 | 408 | 308 | ok | `pilotstd/core/notification/_policy.py` |
| 91 | 122 | 409 | 309 | ok | `pilotstd/core/notification/_json_codec.py` |
| 80 | 105 | 420 | 320 | ok | `pilotstd/core/notification/channels/feishu.py` |
| 77 | 105 | 423 | 323 | ok | `pilotstd/core/notification/specs.py` |
| 76 | 112 | 424 | 324 | ok | `pilotstd/core/notification/stage.py` |
| 73 | 96 | 427 | 327 | ok | `pilotstd/core/notification/channels/wechat.py` |
| 53 | 110 | 447 | 347 | ok | `pilotstd/core/notification/channel.py` |
| 51 | 56 | 449 | 349 | ok | `pilotstd/core/notification/_message_builders.py`（纯重导出） |
| 48 | 72 | 452 | 352 | ok | `pilotstd/core/notification/desktop_formatter.py` |
| 42 | 51 | 458 | 358 | ok | `pilotstd/core/notification/__init__.py` |
| 38 | 59 | 462 | 362 | ok | `pilotstd/core/notification/blocks.py` |
| 35 | 49 | 465 | 365 | ok | `pilotstd/core/notification/channels/base.py` |
| 6 | 9 | 494 | 394 | ok | `pilotstd/core/notification/channels/__init__.py` |

**合计 4,530 有效行**（复算命令见附录）。

**三条结论**：
1. **`manager.py` 是唯一逼近阻断线的文件**，也是唯一处于警告档（>400）的文件。
2. **`_builders_system.py`(400) 与 `_builders_batch.py`(392) 是下一批瓶颈**——它们分别是 41 个构建器中的 14 个与 12 个的落点。⇒ **本次拆分的新文件不得复用这两个模块**。
3. 目录内**多数文件 < 220 行**（21/29），说明"小文件 + 单一职责"在本目录已是常态，`manager.py` 是唯一的例外。

## 1.2 `manager.py` 成员盘点（45 条目）

**文件级**：有效行 **498** / 原始 609。**无函数超过 80 有效行**（G-010 函数阻断档，`:182-185`）。

| 起止 | 成员 | 有效行 | 职责分类 | 被外部访问 |
|---|---|---|---|---|
| 6–69 | imports（**含 `_message_builders` 的 44 行导入块** `:18-61`） | 64 | ①模块样板 | — |
| 71 | `logger` | 1 | ①模块样板 | **mock.patch ×1** |
| 74–78 | `_log_trace_id` | 4 | ①模块样板 | — |
| 80–85 | `_CHANNEL_CLASSES` | 6 | ②契约常量 | `_format_utils.py:103,110` + **patch ×19** |
| 92–114 | `_QUEUE_MESSAGE_FIELDS` | 17 | ②契约常量 | **测试 import ×5** |
| 124–205 | `NotificationManager.__init__` | 65 | ③生命周期装配 | 生产构造 ×3 |
| 208–210 | `enabled`（property） | 3 | ③生命周期装配 | — |
| 212–241 | `_read_user_enabled` | 29 | ③生命周期装配 | — |
| 243–274 | `_init_channels` | 32 | ③生命周期装配 | — |
| 518–521 | `shutdown` | 4 | ③生命周期装配 | `docker/app.py:267-268` |
| 523–567 | `_init_event_builders` | 45 | ④构建器注册 | — |
| 569–574 | `_build_message` | 6 | ④消息构建 | **替换 ×2** |
| 600–601 | `_format_standard_status_changed_aggregated` | 2 | ④构建器注册 | — |
| 315–336 | `_validate_message` | 18 | ④消息构建 | **类属性绑定 ×2** |
| 278–313 | `send_event` | 31 | ⑤主发送链 | `facade/_base.py` 调用 |
| 338–348 | `_do_send` | 9 | ⑤主发送链 | **替换 ×1** |
| 350–379 | `_send_now` | 29 | ⑤主发送链 | **替换 ×8** |
| 436–448 | `_is_quiet_hours` | 13 | ⑥静音队列 | 直调 ×5 |
| 450–480 | `_enqueue_notification` | 25 | ⑥静音队列 | 直调 ×4 |
| 482–516 | `release_suppressed_notifications` | 30 | ⑥静音队列 | `docker/scheduler.py` 调用 |
| 383–398 | `_record_delivery` | 15 | ⑦投递健康度 | 直调 ×10+ |
| 400–432 | `_send_delivery_alert` | 31 | ⑦投递健康度 | **替换 ×1** |
| 583–587 | `_log` | 5 | ⑧日志/策略转发 | **替换 ×3** |
| 605–606 | `get_policies` | 2 | ⑧日志/策略转发 | `docker/api/notification.py:442` |
| 608–609 | `save_policy` | 2 | ⑧日志/策略转发 | `docker/api/notification.py:453` |
| 592–596 | `test_send` | 5 | ⑨测试入口 | `docker/api/notification.py:317` |

**按职责汇总的规模**（有效行）：

| 职责 | 有效行 |
|---|---|
| ①模块样板（imports/logger/工具） | 69 |
| ②契约常量 | 23 |
| ③生命周期装配 | 133 |
| ④构建器注册与消息构建 | 71 |
| ⑤主发送链 | 69 |
| ⑥静音与补发队列 | 68 |
| ⑦投递健康度 | 46 |
| ⑧日志/策略转发 | 9 |
| ⑨测试入口 | 5 |
| 类 docstring 等 | ~5 |
| **合计** | **498** |

**`__init__` 内的 13 个实例属性**（`:125-191`）：`_cfg`、`_db`、`_user_id`、`_policy`、`_cred_helper`、`_enabled`（`:144` 与 `:148` 两次赋值）、`aggregator`、`ops`、`_aggregate_enabled`、`_delivery_health_enabled`、`delivery_health`、`_sending_delivery_alert`。
⇒ 这 13 个是"实例独有属性"——**§摘要第 4 条的约束正是针对它们**。

## 1.3 对外接口与私有访问

### 1.3.1 公开接口

| 符号 | 消费者 | 证据 |
|---|---|---|
| `NotificationManager` | 门面 + Docker API + 测试 | `pilotstd/core/notification/__init__.py:12`（再导出）；`pilotstd/manager/facade/_base.py:12,256,279`；`docker/api/notification.py:11` |
| `_CHANNEL_CLASSES`（私有但被跨模块 import） | `_format_utils.py:103,110`（函数内延迟导入） | `pilotstd/core/notification/_format_utils.py:103` |
| `_QUEUE_MESSAGE_FIELDS`（私有但被测试 import） | 5 处 | `tests/test_notification_stage1a_identity.py:268`、`stage1b:292`、`stage1c:334`、`stage2b_wiring:314,338` |

### 1.3.2 `mock.patch` 路径（拆分最易"静默失效"的地方）

| patch 目标 | 处数 | 证据 |
|---|---|---|
| `pilotstd.core.notification.manager._CHANNEL_CLASSES` | **19** | `tests/test_format_utils.py:121,135,145,158,183,202,217,230,253,268,281,303,322,339,353,381,397,411,428` |
| `pilotstd.core.notification.manager.logger` | **1** | `tests/test_aggregate_buffer.py:592` |

### 1.3.3 私有成员被访问/替换（178 处命中，按模式归类）

| 模式 | 成员 | 代表证据 | 对拆分的含义 |
|---|---|---|---|
| **类属性绑定** | `_validate_message` | `tests/test_aggregate_buffer.py:552,563`（`__get__(mgr)`，mgr 是 `MagicMock(spec=…)`） | 必须**保持类属性是函数**，且**转发体不得访问实例独有属性** |
| **实例方法整体替换** | `_send_now`(8)、`_log`(3)、`_build_message`(2)、`_do_send`(1)、`_send_delivery_alert`(1) | `test_delivery_health.py:276`、`test_notification_combo_patch.py:145`、`test_aggregate_buffer.py:583,586` | 内部调用点必须写 `self.<name>(…)`（**不能**改成 `self.<delegate>.<name>(…)`） |
| **实例方法直接调用** | `_record_delivery`、`_is_quiet_hours`、`_enqueue_notification`、`release_suppressed_notifications` | `test_delivery_health.py:283`、`test_notification_manager.py:73`、`stage1a:286`、`round3:89` | 名字必须仍可在实例上取到 |
| **实例属性赋值** | `_enabled`、`_channels`、`_policy`、`_cfg`、`_db`、`_user_id`、`_cred_helper`、`_sending_delivery_alert`、`_EVENT_BUILDERS` | `test_notification_manager.py:124,137`、`test_format_utils.py:79-87`、`test_p0_security_endpoints.py:123` | 这些属性必须**继续存在于实例上**，且读取点必须走宿主属性 |
| **`__new__` 绕过 `__init__`** | `_record_delivery`/`_send_now`/`_send_delivery_alert` | `tests/test_delivery_health.py:269` | 这些方法的实现**不能依赖 `__init__` 建立的中间组件** |
| **生产代码读私有属性** | `_cred_helper`(7)、`_channels`/`_user_id`(3)、`_db`(1) | `docker/api/notification.py:115,116,187,200,218,281,283`；`_format_utils.py:107,116,118`；`_manager_ops.py:47` | 属性名不可改（生产耦合） |

### 1.3.4 由盘点导出的三条拆分硬规则（**本轮新增判断**）

| # | 规则 | 依据 |
|---|---|---|
| **H1** | 被 `mock.patch` 的**模块级名字**（`_CHANNEL_CLASSES`/`logger`），其**读取点必须仍在 `manager.py` 内**（或经 `manager` 模块属性读取）；否则 patch 会**静默失效**（测试仍绿但测的不是同一件事） | 19 处 patch 打在 `manager` 模块属性上 |
| **H2** | 被 `spec=` mock 或以 `__get__` 绑定调用的方法（`_validate_message`），其转发体**不得访问任何实例独有属性** → 首选**模块级纯函数化** | `MagicMock(spec=…)` 只认类属性 |
| **H3** | 会在运行时被整体替换的方法（`_send_now`/`_do_send`/`_log`/`_build_message`/`_send_delivery_alert`），**内部调用点必须保持 `self.<name>(…)`**；搬走的实现若需回调它们，必须经**宿主引用**（`self._mgr._send_now(…)`，与 `_manager_ops.py:47` 的 `self._mgr._db` 同口径） | 8+3+2+1+1 处替换 |

## 1.4 已有 mixin 盘点

**结论：未发现 mixin。**

| 项 | 事实 | 证据 |
|---|---|---|
| 目录内 `*Mixin` 类名 | **0 个** | 对 29 文件全量 AST 扫描（附录命令） |
| 目录内继承关系 | 13 处，全部为正规基类/抽象基类 | `blocks.py:21,28,36,45`（→ `NotificationBlock`，`blocks.py:14` 是空基类）；`channels/base.py:22`（`NotificationChannel(ABC)`）；`channels/{dingtalk,feishu,telegram,wechat}.py:23/18/61/18`；`renderer.py:178,254,309,421`（→ `BlockRenderer`，`renderer.py:62`） |
| 既有门禁 | `tests/test_architecture_mixin_guard.py`：按**类名 `endswith("Mixin")`** 判定，白名单仅 `_WindowLifecycleMixin`（`:9`），违规即 FAIL（`:27-35`） | 同文件 `:27-28` |
| 历史裁决 | ADR-010「Mixin 16→1」：15 个 mixin 转为 6 种模式；**策略固化 = "未来新增跨切面逻辑，优先使用 Composition + `_DispatchContext` 模式"** | `docs/adr/ADR-010-mixin-refactor.md:32-41,66-70,74` |

**两处门禁薄弱点（本轮新增判断，仅报告不改）**：
1. 判定只看**类名后缀**——"多重继承但不叫 `*Mixin`"可以绕过。
2. 未约束**基类个数**——`class X(A, B)` 形式的拼装不会被拦。

---

# 第二部分：拆分方案

## 2.1 方案 A：两块纯函数化剥离（**推荐**）

### 2.1.1 拆成几块

| 新文件 | 内容来源（`manager.py` 行号） | 对外接口（**纯函数**） | 预计有效行 |
|---|---|---|---|
| `_event_registry.py` | 导入块 `:18-61`、`_init_event_builders` `:523-567`（映射表部分）、`_build_message` `:569-574`（构建部分）、`_validate_message` `:315-336`、`_format_standard_status_changed_aggregated` `:600-601` | `build_registry() -> dict[str, Callable]`、`build_message(registry, event_type, data) -> NotificationMessage`、`validate_message(msg, event_type) -> None` | ~130 |
| `_suppression_queue.py` | `_QUEUE_MESSAGE_FIELDS` `:92-114`、`_is_quiet_hours` `:436-448`、`_enqueue_notification` `:450-480`、`release_suppressed_notifications` `:482-516` | `is_quiet_hours(cfg, now=None) -> bool`、`enqueue_suppressed(db, msg, channels) -> None`、`release_suppressed(db) -> int`、`QUEUE_MESSAGE_FIELDS` | ~95 |

### 2.1.2 职责边界（什么进去、什么不进）

| 块 | **进去** | **不进** |
|---|---|---|
| `_event_registry.py` | 41 个构建器的导入与 `事件名 → 构建器` 映射；消息构建；**纯校验**（只读 `msg`/`event_type`）；状态变更聚合格式化器 | 渠道解析、日志写入、`_EVENT_BUILDERS` 的**持有**（仍由宿主实例持有，见下） |
| `_suppression_queue.py` | 静音时段判定（纯函数，入参 `cfg`）；静音期入队；补发重建；**队列字段契约常量** | 渠道发送（补发最终回调宿主的 `_send_now`）、健康度记账 |
| **不进任何新文件** | 主发送链、投递健康度、生命周期装配、契约常量 `_CHANNEL_CLASSES`、`logger` | —— |

### 2.1.3 块与块的交互（**组合/委托，零 mixin**）

```
NotificationManager（宿主，仍是唯一对外类）
├── self.ops : NotificationOps          （既有组合，_manager_ops.py:38）
├── self._EVENT_BUILDERS : dict         （宿主持有；由 _event_registry.build_registry() 产出）
└── 5 个同名薄方法（转发，转发体零/最小 self 访问）
      _build_message()  → build_message(self._EVENT_BUILDERS, event_type, data)
      _validate_message()→ validate_message(msg, event_type)          ← 零 self 访问（H2）
      _is_quiet_hours() → is_quiet_hours(self._cfg)
      _enqueue_notification() → enqueue_suppressed(self._db, msg, channels)
      release_suppressed_notifications() → release_suppressed(self._db)
```

**关键点（H3 的落地）**：`_suppression_queue.release_suppressed` 需要投递时，**不持有渠道对象**，而是由宿主传入回调：
`release_suppressed(db, send_now=self._send_now)` —— 这样测试替换 `mgr._send_now` 后，补发路径依然走替换后的实现。

### 2.1.4 对现有调用方的影响

| 调用方 | 是否需改 |
|---|---|
| `pilotstd/manager/facade/_base.py`（构造与持有） | **不改** |
| `docker/api/notification.py`（`_cred_helper` 等 7 处） | **不改** |
| `docker/scheduler.py`（`release_suppressed_notifications`、`ops.cleanup_logs`） | **不改**（同名方法仍在） |
| `pilotstd/core/notification/_format_utils.py:103,110`（`from .manager import _CHANNEL_CLASSES`） | **不改**（方案 A 不动 `_CHANNEL_CLASSES`） |
| `pilotstd/core/notification/__init__.py:12` | **不改** |

### 2.1.5 对现有测试的影响：**0 处需改**

| 测试模式 | 为何仍成立 |
|---|---|
| `mock.patch("…manager._CHANNEL_CLASSES")` ×19 | `_CHANNEL_CLASSES` **未移动**，仍在 `manager.py`（`:80-85`），且唯一读取点 `manager.py:248` 仍在文件内 ⇒ patch 语义不变（满足 H1） |
| `mock.patch("…manager.logger")` ×1 | `logger` **未移动**（`:71`） |
| `from …manager import _QUEUE_MESSAGE_FIELDS` ×5 | `manager.py` 以 `from ._suppression_queue import QUEUE_MESSAGE_FIELDS as _QUEUE_MESSAGE_FIELDS` **再导出同一对象** ⇒ `is` 相等、`in` 断言不变 |
| `NotificationManager._validate_message.__get__(mgr)` ×2 | 类属性仍是函数；转发体**零 `self` 访问** ⇒ 在 `MagicMock(spec=…)` 上可用（满足 H2） |
| `mgr._send_now = lambda …` ×8 | `_send_now` **未移动**，内部调用点仍是 `self._send_now(…)`（满足 H3） |
| `mgr._enqueue_notification(msg, ch)` ×4 | 同名薄方法仍在类上 |
| `mgr._is_quiet_hours()` ×5 | 同名薄方法仍在类上 |
| `tests/test_notification_manager.py::TestSuppressedQueueFieldRoundTrip` | `_QUEUE_MESSAGE_FIELDS` 语义与内容不变 |

### 2.1.6 拆完后 `manager.py` 预计行数

`498 − 200（移出） + 20（薄方法 + 导入 + 再导出）` ≈ **318 有效行**（距 500 余量 **182**，且退出 400 警告档）。

### 2.1.7 取舍

- **为什么这样拆**：只动"**不访问 self 状态**"的部分（ADR-010 的第一种模式"纯函数化"，`ADR-010:36`），因此**不触碰任何测试耦合点**；风险与工作量都最低。
- **不这样拆的代价**：若把主发送链也搬走，需引入"宿主回调"（H3）与懒初始化（见方案 B），测试风险陡增；而 A 已给出 182 行余量，足够后续 5 个阶段（D/A/S/B/C+E）各加约 30 行。
- **可演进性**：A 是 B 的子集，后续若再逼近上限，可增量叠加 B 的第三、第四块——**不必一次到位**。

## 2.2 方案 B：四块 + `_ManagerContext`（彻底）

### 2.2.1 拆成几块

在方案 A 的两块之上，再拆两块 + 一个上下文对象：

| 新文件 | 内容来源 | 对外接口 | 预计有效行 |
|---|---|---|---|
| `_channel_registry.py` | `_read_user_enabled` `:212-241`、`_init_channels` `:243-274`、`enabled` `:208-210` | `read_user_enabled(db, user_id)`、`build_channels(cfg, cred_helper, user_id, db, channel_classes)`、`CHANNEL_CLASSES` | ~80 |
| `_health.py` | `_record_delivery` `:383-398`、`_send_delivery_alert` `:400-432` | `record_delivery(health, channel, ok, host)`、`send_delivery_alert(host, channel, reason, samples, failures)` | ~60 |
| `_manager_context.py` | 新增（无来源） | `@dataclass(frozen=True) class _ManagerContext`（`cfg`/`db`/`user_id`/`policy`/`cred_helper`/`channels`/`aggregator`/`health`） | ~25 |

**交互模式**：仿项目既有先例 `pilotstd/query/engine/_batch_dispatcher.py:42-52`（`@dataclass(frozen=True)` 上下文）+ `:61-62`（构造时 `self._ctx = ctx` 注入）。

### 2.2.2 与方案 A 相同的部分

调用方影响、`_CHANNEL_CLASSES` 处理方式、薄方法转发策略**完全一致**。

### 2.2.3 方案 B 的两处额外风险（**必须显式处理**）

| # | 风险 | 证据 | 处理 |
|---|---|---|---|
| **B-1** | `_record_delivery` 被 `NotificationManager.__new__(NotificationManager)` 的实例调用（**绕过 `__init__`**），此时 `__init__` 建立的中间组件不存在 → 若转发体访问 `self._health` 会 `AttributeError` | `tests/test_delivery_health.py:269-283` | 转发目标改为**惰性 property**（首次访问时构造）或 `_record_delivery` 留在 `manager.py` |
| **B-2** | `_CHANNEL_CLASSES` 若搬走，且新模块内部按**自己的模块属性**读取，则 19 处 `mock.patch("…manager._CHANNEL_CLASSES")` 会**静默失效**（测试仍绿但不再生效） | `tests/test_format_utils.py` 19 处 | 必须保持"读取点经 `manager` 模块属性"（H1），或同批迁移 19 处 patch 目标（改测试） |

### 2.2.4 拆完后 `manager.py` 预计行数

`318（方案 A 结果） − 70（生命周期） − 46（健康度） + 18（薄方法）` ≈ **220 有效行**（距 500 余量 280）。

### 2.2.5 取舍

- **为什么这样拆**：一次到位，后续阶段几乎不可能再逼近上限；且更接近 ADR-010 的终局形态（组合注入 + 上下文对象）。
- **不这样拆的代价**：B-1/B-2 两处**静默失效**风险需要额外设计与验证成本；薄方法数量翻倍（约 15 个），样板占比上升。

## 2.3 方案对比与建议

| 维度 | 方案 A | 方案 B |
|---|---|---|
| 新文件数 | 2 | 4 + 1 上下文 |
| `manager.py` 预计 | ~318 | ~220 |
| 距 500 余量 | 182 | 280 |
| 测试改动 | **0** | 0（若正确处理 B-1）或 19 处（若不动 H1） |
| 新增薄方法 | 5 | ~15 |
| 静默失效风险 | **无** | **2 处**（B-1/B-2） |
| ADR-010 契合度 | 纯函数化（第一种模式） | 纯函数化 + 组合注入 + `_DispatchContext` |
| 工作量 | ~1.5 天 | ~3 天 |

**如果让我选：方案 A，理由有三**——
1. **余量已足够**：182 行 > 后续 5 个阶段预估增量（约 150 行）之和；
2. **零静默失效**：A 不触碰任何 patch 目标与 `spec=` 调用点；
3. **可增量演进**：A ⊂ B，将来若真的再触线，再叠 B 的第三块即可，**不需要现在承担 B 的风险**。

**为什么不用 mixin（即使 mixin 更省代码）**：

| # | 理由 | 证据 |
|---|---|---|
| 1 | **项目已明令禁止且有守护门禁**：除 `_WindowLifecycleMixin` 外，任何 `*Mixin` 类名即 FAIL | `tests/test_architecture_mixin_guard.py:9,27-35` |
| 2 | **ADR-010 已裁决其代价**：Mixin 导致"继承层次过深、MRO 冲突频发、**单元测试困难（需 mock 整个宿主类）**、职责边界模糊"；16→1 的收敛正是为解决这些 | `ADR-010:26-28,46-61` |
| 3 | **本模块的测试形态与 mixin 根本冲突**：本模块大量依赖"**在实例上单独替换某个方法**"（`_send_now` 8 处、`_log` 3 处、`_build_message` 2 处）与"**以类属性 `__get__` 绑定单个方法**"（`_validate_message` 2 处）。mixin 把方法摊进同一个类的 MRO，**无法在不 mock 整个宿主的前提下单独定位与替换**——这正是 ADR-010 记录的原始痛点 | `test_delivery_health.py:276`、`test_notification_combo_patch.py:145`、`test_aggregate_buffer.py:552` |
| 4 | **行数收益可由组合等价获得**：本方案的薄方法转发达到了与 mixin 同样的"把实现搬出 `manager.py`"效果，且不引入 MRO | §2.1.6 |

---

# 第三部分：阶段 P 实施设计

## 3.1 实施步骤

| 步 | 内容 | 独立可交付 |
|---|---|---|
| **P0** | **基线固化**：跑全量测试并记录 `(passed, failed, skipped)`；跑 `bash scripts/check_all.sh --fast`；记录 28 个文件的 G-010 有效行快照（脚本输出） | 是（仅记录） |
| **P1** | **新建 `_event_registry.py`**：搬导入块与三个纯函数 + 映射表构建；`manager.py` **暂不切换**（新文件此刻无人引用） | 是 |
| **P2** | **切换构建器块**：`manager.py` 删除 `:18-61` 导入块与 `_build_message`/`_validate_message`/`_init_event_builders`/`_format_…_aggregated` 的方法体，改为薄方法 + `self._EVENT_BUILDERS = build_registry()` | 是 |
| **P3** | **新建 `_suppression_queue.py` + 切换静音块**：搬 4 个成员并再导出 `_QUEUE_MESSAGE_FIELDS`；`release_suppressed_notifications` 改为传宿主回调 `self._send_now` | 是 |
| **P4** | **回归与核对**：全量测试三元组与 P0 比对；有效行核对（`manager.py` ≤ 340）；签名快照比对 | 是 |
| **P5** | **防膨胀门禁上线**（G-048，见 §3.7）：脚本 + 挂载 `check_all.sh` + 登记 `docs/governance/gates.md`；若改了治理文档，须跑 `python scripts/generate_capabilities.py` 并把 `capabilities_registry.md` 纳入同一 commit | 是 |

## 3.2 验收判据（零行为变更，逐条可断言）

| # | 判据 | 断言方式 |
|---|---|---|
| **Z1** | **全量测试通过数不变** | P0 与 P4 各跑一次 `python -m pytest -q`，比对 `(passed, failed, skipped)` **三元组逐项相等**；基线数字以 P0 实测为准（**不引用 `STATUS.md` 的历史值**，该文件标注 `[legacy-manual]`） |
| **Z2** | **对外接口签名不变** | 对 `NotificationManager.{__init__,send_event,enabled,shutdown,test_send,get_policies,save_policy,release_suppressed_notifications}` 与模块级 `_log_trace_id`，用 `inspect.signature` 生成快照文本，P0/P4 逐字比对（可写成一次性脚本） |
| **Z3** | **关键行为逐项一致** | ① **发送**：同一组输入分别驱动 `_do_send` 的三分支（静音 / 聚合 / 直发），用 `MagicMock` 记录调用序列并与 P0 快照比对；② **聚合**：`aggregator.enqueue(msg, channels, target_id=…)` 的实参逐项相等；③ **静音**：`_is_quiet_hours()` 在既有 6 个时点输入下结果不变（已有用例 `tests/test_notification_manager.py:72-89`）；④ **日志**：`_log` 的 6 个位置实参逐项相等（已有 `tests/test_notification_combo_patch.py:150` 断言 `call_args.args`） |
| **Z4** | **类属性与模块契约不变** | ① `callable(NotificationManager._validate_message)` 且 `NotificationManager._validate_message.__get__` 可用；② `manager._QUEUE_MESSAGE_FIELDS is _suppression_queue.QUEUE_MESSAGE_FIELDS`；③ `set(manager._CHANNEL_CLASSES) == set(CHANNEL_KEY_WHITELIST)`（既有断言 `tests/test_notification_stage1c_fields.py:426`） |
| **Z5** | **行数达标** | `manager.py` 有效行 ≤ **340**（方案 A 目标 ~318，留 22 行缓冲）；新文件各自 ≤ **200** |
| **Z6** | **门禁全绿** | `python scripts/check_g_010_code_size.py`、G-048 脚本、`bash scripts/check_all.sh --fast` 三者 **EXIT=0** |

## 3.3 回滚方式

| 项 | 说明 |
|---|---|
| 性质 | **纯重构**：无 schema 变更、无迁移号、无配置项变更、无对外接口变更 |
| 手段 | `git revert <P1..P5 各自 commit>`（**按步回滚**：P1/P2/P3 各自独立 commit，可单独回退；P2 与 P3 无相互依赖） |
| 回滚后 | 行为与拆分前**逐字节**一致（因无行为变更，回滚不产生残留） |
| 粒度建议 | **P1 与 P2 同一批次合并为一个 commit 更安全**（避免出现"新文件无引用"的中间态）；若分两 commit，则回滚 P2 即恢复原状、P1 留下的新文件无害 |

## 3.4 风险与边界

| # | 风险 | 判断 | 依据/对策 |
|---|---|---|---|
| R1 | 19 处 `_CHANNEL_CLASSES` patch | **方案 A 无风险**（不动该常量）；方案 B 有静默失效风险 | `test_format_utils.py` 19 处；H1 |
| R2 | `spec=` mock 上的转发体 | **方案 A 已规避**（`_validate_message` 纯函数化）；这是本轮最重要的约束 | `test_aggregate_buffer.py:551-556`；H2 |
| R3 | `__new__` 型测试 | **方案 A 无风险**（`_record_delivery` 不搬）；方案 B 需惰性 property | `test_delivery_health.py:269` |
| R4 | **循环导入** | 新模块**禁止在模块级 import `manager`**（`manager` 已被 `__init__.py:12` 与 `_manager_ops.py:33` 依赖，反向依赖会成环） | `_format_utils.py:103` 已用函数内延迟导入规避同类问题 |
| R5 | `_QUEUE_MESSAGE_FIELDS` 的"唯一数据源"契约 | 拆分后**必须仍是同一对象**（宿主再导出，不得复制字面量） | `manager.py:87-91` 注释明示"两侧各写一份字面量的历史写法一旦漂移…被静默丢弃"；`TestSuppressedQueueFieldRoundTrip` 锁定 |
| R6 | G-012 注释密度 | 薄方法需 docstring，会抵消部分净减（已计入估算：5 个薄方法约 +15 行） | 门禁 G-012 在 `--fast` 内 |
| R7 | **目录总量膨胀** | 拆分会使目录合计有效行**上升**（新文件的模块头/导入/docstring 样板） | 当前 4,530；门禁须同时管单文件与总量（§3.7） |
| R8 | mixin 门禁的绕过面 | 现有门禁只按类名判定，不拦"多基类拼装" | `test_architecture_mixin_guard.py:27-28`；建议 G-048 补一条（待裁决 N4） |
| R9 | `docker/api/notification.py` 的 7 处 `_cred_helper` | **不改属性名**即可（方案 A 不动它） | `docker/api/notification.py:115-283` |

## 3.5 测试策略

| 类 | 内容 |
|---|---|
| **现有测试** | **零改动**（方案 A）。特别复核 3 个文件：`tests/test_format_utils.py`（19 处 patch）、`tests/test_aggregate_buffer.py`（`spec=` + `__get__`）、`tests/test_notification_manager.py`（`_QUEUE_MESSAGE_FIELDS` + 静音 6 例） |
| **新增：契约锁定测试（3 个）** | ① `_validate_message` 可在 `MagicMock(spec=NotificationManager)` 上 `__get__` 绑定并被调用（**把 H2 变成回归防线**）；② `manager._QUEUE_MESSAGE_FIELDS is _suppression_queue.QUEUE_MESSAGE_FIELDS`；③ `set(manager._CHANNEL_CLASSES) == set(CHANNEL_KEY_WHITELIST)`（既有断言已在 `stage1c_fields.py:426`，此处只做"拆分后仍成立"的显式化） |
| **新增：纯函数直测（建议 6-8 个）** | `validate_message` 的空消息/单字段/空白字符 3 例（对应既有 `test_aggregate_buffer.py:556-573` 的三态，但**不再依赖 manager 实例**）；`is_quiet_hours` 的跨午夜/白天/禁用 3 例；`build_registry()` 的"键集合 == ALL_EVENTS"1 例；`release_suppressed(db, send_now=…)` 的回调被调用 1 例 —— **这是拆分带来的可测性收益**（ADR-010 记录的原痛点是"需 mock 整个宿主类"） |
| **新增：结构门禁测试（2 个）** | ① `manager.py` 有效行 ≤ 340；② 该目录无 `*Mixin`（复用既有 `test_architecture_mixin_guard.py`，不重复造） |
| **不需要** | 新增集成测试（行为由现有 e2e + 单测覆盖，Z3 已给出行为比对方法） |

## 3.6 工作量预估

| 步 | 预估 |
|---|---|
| P0 基线 | 0.2 天 |
| P1+P2 构建器块 | 0.5 天 |
| P3 静音块 | 0.4 天 |
| P4 回归与核对 | 0.4 天 |
| P5 门禁 | 0.5 天 |
| **合计** | **约 2 天**（方案 A）；方案 B 约 3～3.5 天 |

## 3.7 防膨胀门禁设计

**编号**：**G-048**（`docs/governance/gates.md` 现用至 **G-047**，`:G-047` 为最大）。
**脚本**：`scripts/check_g_048_notification_size.py`。
**作用域**：仅 `pilotstd/core/notification/**/*.py`（不动全局 G-010 阈值——全局收紧会误伤其他目录）。

**建议规则**：

| 规则 | 阈值 | 理由 |
|---|---|---|
| 单文件有效行 | **> 410 阻断；> 370 警告** | 现存最大 400（`_builders_system.py`）→ **可立即上线、零存量违规**；同时把"下一批瓶颈"提前变成警告（400/392 两个文件在启动时各出 1 条警告，正是想要的信号） |
| 目录合计有效行 | **≤ 4800**（当前 4,530，留 ~6%） | 防止"拆分 = 总量膨胀"（R7）；实施时应按 P4 实测值定稿 |
| 多基类 | 该目录内除白名单（`NotificationBlock`/`NotificationChannel`/`BlockRenderer` 及其子类）外，**禁止多基类定义** | 补 mixin 门禁的绕过面（R8） |

**触发**：挂到 `check_all.sh --fast` 的 gates 段（与 G-010 相邻）。
**上线附带要求**（实施时勿漏）：
1. 登记 `docs/governance/gates.md`（该文件受 **G-031 文档联动同步**约束）；
2. 按 `AGENTS.md` §七，修改 `docs/` 治理文档须执行 `python scripts/generate_capabilities.py` 并把 `capabilities_registry.md` 纳入**同一 commit**；
3. `G-029 测试联动`：新增门禁脚本属 `scripts/`，需确认是否触发测试同步要求。

**阈值取舍的张力（诚实说明）**：若把上限设为 **350**，则 `_builders_system.py`(400) 与 `_builders_batch.py`(392) **在门禁上线当天即阻断**，必须同时给这两者一个"存量白名单"，否则 P5 无法交付。因此**建议 410**，把"清理这两个文件"作为**后续独立批次**（见待裁决 N2/N5）。

---

## 待裁决清单

| # | 待裁决点 | 备选 | 建议 + 理由 |
|---|---|---|---|
| **N1** | 拆分方案选 A 还是 B | (a) 方案 A（两块纯函数化） (b) 方案 B（四块 + Context） (c) A 先做、留 B 为后续可选 | **(c)**：A 给 182 行余量已足够，零静默失效；B 可增量叠加，不必现在承担 B-1/B-2 风险 |
| **N2** | 防膨胀门禁阈值 | (a) 410 阻断 / 370 警告（零存量违规） (b) 350 阻断 + 存量白名单 (c) 不设单文件上限，只设目录总量 | **(a)**：(b) 会让 `_builders_system.py`(400)/`_builders_batch.py`(392) 当天阻断，P5 无法独立交付 |
| **N3** | 目录总量上限取值 | (a) 4800 (b) 按 P4 实测值 +5% 定稿 (c) 不设 | **(b)**：当前 4,530 是重构前基线，拆分后总量会变，**应实测后定稿**而非现在拍板 |
| **N4** | 是否补"禁多基类"规则 | (a) 补（G-048 内） (b) 只沿用现有类名门禁 | **(a)**：现有门禁只按类名判定（`test_architecture_mixin_guard.py:27-28`），"多基类拼装"可绕过 |
| **N5** | `_builders_system.py`(400) / `_builders_batch.py`(392) 是否纳入本次拆分 | (a) 不纳入（本批只拆 `manager.py`） (b) 一并拆 | **(a)**：决策者本批目标是 `manager.py` 的前置拆分；把目录瓶颈一次清完会显著放大风险与工作量，建议独立立项 |
| **N6** | P1 与 P2 是否合并为一个 commit | (a) 合并（避免"新文件无引用"中间态） (b) 分开（回滚粒度更细） | **(a)**：拆分的价值在"切换"，新文件单独提交会留下无引用的死文件（且可能触发覆盖率/死代码门禁） |

---

## 附：可复算命令

```powershell
# ── 目录规模（G-010 同口径）──
python scripts/check_g_010_code_size.py
python -c "import pathlib;d=pathlib.Path('pilotstd/core/notification');rows=[(len([l for l in f.read_text(encoding='utf-8').splitlines() if l.strip() and not l.strip().startswith('#')]), str(f)) for f in d.rglob('*.py')];[print(n,f) for n,f in sorted(rows, reverse=True)]"
# ── manager.py 成员（AST）──
python -c "import ast,pathlib;p=pathlib.Path('pilotstd/core/notification/manager.py');t=ast.parse(p.read_text(encoding='utf-8'));[print(n.lineno,n.end_lineno,n.name) for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.ClassDef))]"
# ── 被 patch / 被 import 的模块级名字（H1 的证据）──
Get-ChildItem tests -Recurse -File -Filter *.py | Select-String 'notification\.manager\._CHANNEL_CLASSES|notification\.manager\.logger'
Get-ChildItem tests -Recurse -File -Filter *.py | Select-String 'from pilotstd\.core\.notification\.manager import'
# ── spec= mock 与 __get__ 绑定（H2 的证据）──
Select-String -Path tests\test_aggregate_buffer.py -Pattern 'MagicMock\(spec=NotificationManager\)|__get__'
# ── __new__ 型测试（B-1 的证据）──
Select-String -Path tests\test_delivery_health.py -Pattern '__new__\(NotificationManager\)'
# ── mixin 门禁与目录内 mixin（A.4）──
Get-Content tests\test_architecture_mixin_guard.py
python -c "import ast,pathlib;d=pathlib.Path('pilotstd/core/notification');[print(f'{f}:{n.lineno}:{n.name}') for f in d.rglob('*.py') for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))) if isinstance(n,ast.ClassDef) and n.name.endswith('Mixin')]"
# ── 门禁挂载与编号 ──
Select-String -Path docs\governance\gates.md -Pattern 'G-0\d\d' -AllMatches
Get-Content scripts\check_all.sh -TotalCount 40
```

**自检**：代码引用 60+ 处（`路径:行号`，内容级回读校验见提交前脚本）；规模统计与 `scripts/check_g_010_code_size.py` 同口径，可复算；本轮**未改任何代码**。
