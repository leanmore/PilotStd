# 实施设计总纲 + Docker 端阶段 D 详细设计

> **本轮性质**：实施设计（**上一轮"不写实施细节"约束解除**）。本文件**只设计、不实施**。
> **上游**：[00-framework.md](00-framework.md)（方案框架）、[01-channel-capabilities.md](01-channel-capabilities.md)（渠道能力）、[02-framework-update.md](02-framework-update.md)（框架更新 + 分档策略）
> **本轮五项裁决（全部同意）**：① 警告绕过静默但不延迟、可合并；② 分档阈值先补埋点；③ 阶段 S 先做 TG + 钉钉；④ 终局汇总按渠道能力处理；⑤ 凭证迁移平滑双读。另：企微/飞书证据缺口保留，阶段 S 暂不排入。
> **约定**：行号均为 2026-10-03 实测；文件引用格式 `路径:行号`。

---

## 摘要（决策者读）

**总纲**
1. **Docker 端 5 阶段**：**D（可见性解耦）→ A（聚合键二元）∥ S（形态升级：TG+钉钉）→ B（低频编辑+回调+分档节流）→ C+E（治理重组+清单处置）**；**Windows 端 3 阶段**：W1（任务中心改造）→ W2（共享事件分流）→ W3（分档节流对齐）。
2. **D 最先做**（决策者已定：它改变所有后续阶段的验证口径）；**S 是 B 的前置**；**A 与 S 可并行**（改的文件不重叠）；**W2 必须先于 C**（C 要按端重排清单）。
3. **推荐推进**：`D → (A ∥ S) → B → W2 → C+E`；W1 与 W3 依附 W2，W1 可随时并行。

**阶段 D（本轮详细设计）**
4. **D 的目标**：`notification.enabled=False` 时**仍构建并写库一条日志**（`status="skipped"`），但**跳过渠道 `send()` 与聚合器**。
5. **改动面 6 处**：后端 2（`manager.py` 3 行换 3 行、`_manager_ops.py` 新增 1 方法 + `log()` 加 1 参数）、前端 3（`NotificationLogsView.vue` 3 处状态映射、2 份语言文件的 `skipped` 键与开关文案）、**`docker/api/notification.py` 零改动**。
6. **硬约束**：`pilotstd/core/notification/manager.py` **有效行 498 / 阻断线 500**（`scripts/check_g_010_code_size.py:29`）→ 改动必须**净增 0 有效行**，故新逻辑全部落在 `_manager_ops.py`。
7. **既有测试锁定点**：`tests/test_notification_manager.py:127-132` 断言"关闭时记录 `通知功能未启用` 的 DEBUG 日志"→ **该文案与 logger 名必须保留**（本设计用 `self._mgr.__class__.__module__` 取同一 logger）。
8. **回滚**：新增独立环境开关 `NOTIFY_RECORD_WHEN_DISABLED=v1|v0`（默认 `v1`），`v0` 恢复"关闭即完全静默"，与 `NOTIFY_AGG_KEY` 同模式（`pilotstd/core/notification/stage.py:60-93`）。
9. **风险最高处**：日志量从 0 变为"每事件 1 行"；未读计数的语义（待裁决 N1）；前端 `statusLabel` 现有**二元回退**会把 `skipped` 显示成"失败"（必须同批修）。
10. **工作量：小～中**（后端约 25 有效行；前端 3 处 + 2 个语言键；测试新增 8 个 + 回归 1 个锁定用例）。

---

# 第一部分：实施设计总纲

## 1.1 阶段清单

| 端 | 序 | 阶段 | 一句话说明 |
|---|---|---|---|
| Docker | 1 | **D 可见性解耦** | 关闭推送后仍写库日志（Web 可查历史） |
| Docker | 2 | **A 聚合键二元切换** | 聚合键从 `event_type × target_id` 切到 `notify_event × target_id` |
| Docker | 3 | **S 形态升级** | 渠道从"群机器人 Webhook"升级为企业级形态（**先 TG + 钉钉**） |
| Docker | 4 | **B 交互** | 低频编辑（状态/回执/汇总）+ 回调 + 分档节流 |
| Docker | 5 | **C+E 治理重组 + 清单处置** | 门禁输入源改为「用户时刻 × 事件」双向闭包；多余/重复事件处置 |
| Windows | 1 | **W1 任务中心改造** | 行单位从任务改为"一次用户操作"，用户语言 |
| Windows | 2 | **W2 共享事件分流** | 事件按端分流（Windows→托盘；Docker→渠道） |
| Windows | 3 | **W3 分档节流对齐** | 托盘气泡遵守分档节流（长阶段 60 秒） |

**不在本轮范围**：企微/飞书形态升级（证据缺口未闭合，见 [01](01-channel-capabilities.md) §五）、原阶段 3 的"消息编辑做进度原地更新"（已裁决作废）。

## 1.2 每阶段一行说明（目标 / 验收 / 回滚）

| 阶段 | 目标 | 验收标准 | 回滚方式 |
|---|---|---|---|
| **D** | 关闭推送时仍写 `notification_log` | 关闭投递→有日志且渠道 `send()` 未被调用；启用→与现状逐项一致 | `NOTIFY_RECORD_WHEN_DISABLED=v0` |
| **A** | 聚合键切 `notify_event × target_id` | v1/v2 对照分组断言 + 批上限仍生效 + 采样无 429 恶化 | `NOTIFY_AGG_KEY=v1`（既有裁决机制） |
| **S** | TG + 钉钉升到企业级形态并可发卡片 | 两渠道发送成功 + 凭证双读兼容旧配置 | 逐渠道回退旧形态（凭证双读期内可切） |
| **B** | 三类低频编辑 + 回调 + 分档节流 | 编辑闭环、回调验签与越权拒绝、长阶段 60 秒节流 | `NOTIFY_REDESIGN_STAGE=2` |
| **C+E** | 用户时刻 SSOT 进代码 + 清单收敛 | 三连门禁 EXIT=0 + 双向闭包断言 + 前端双层渲染 | `NOTIFY_REDESIGN_STAGE=3` + 订阅映射回滚 |
| **W1** | 任务中心改用户视角 | 真实操作一轮可读、"清除"语义正确 | 纯 UI 回退 |
| **W2** | 共享事件按端分流 | 长任务离席仍收托盘气泡；事件不再两头都不落 | 分流开关回退 |
| **W3** | 托盘气泡按分档节流 | 长任务期间气泡条数符合分档规则 | 关闭节流开关 |

## 1.3 依赖关系与推进顺序

```
              ┌──────────────────────── Docker 端 ────────────────────────┐
   D ──┬──► A ──┐
       │        ├──► B ──► C+E
       └──► S ──┘                    ▲
                                     │ （W2 必须先于 C）
              ┌──── Windows 端 ───┐  │
   W1 ──► W2 ─┴───────────────────┴──┘ ──► W3
```

| 关系 | 说明 |
|---|---|
| **D → 全部** | D 改变"关闭时的可观测性"，是所有后续阶段验证口径的前提（决策者已定"最先做"） |
| **S → B** | 形态是交互的前置：无回调形态则编辑与回调无法落地 |
| **A ∥ S** | 可并行：A 只动聚合缓冲，S 只动渠道层与凭证读取，文件不重叠 |
| **W2 → C** | C 要按端重排"用户时刻 × 事件"清单，而 W2 决定"哪些 `send_event` 属于哪一端" |
| **W2 → W3** | W3 只对"已分流到托盘"的事件做节流，故排在 W2 之后 |
| **W1 ∥ 一切** | 纯 UI 改造，不碰通知链路 |

**推荐推进顺序**：**D →（A ∥ S）→ B → W2 → C+E**，W1 可随时并行，W3 在 W2 通过后收尾。

## 1.4 与已有框架的对应

| 本总纲阶段 | 来源 | 对应章节 |
|---|---|---|
| D | 本轮五项裁决 ①（`_enabled` 解耦已裁决） | [02](02-framework-update.md) §一 #1、§四 4.1 |
| A | 原阶段 2.5b 修订版（只做二元） | [00](00-framework.md) §2.3；[notification-redesign/03](../notification-redesign/03-实施路径.md) §3.3 |
| S | **新增**（形态是交互前置） | [02](02-framework-update.md) §2.3、§四 4.1 |
| B | 原阶段 3 重定义（分渠道双向 + 低频编辑） | [02](02-framework-update.md) §2.2–2.3；裁决 ④ |
| C+E | 原阶段 4 修订 + 清单处置 | [00](00-framework.md) §2.3；裁决 ②（用户时刻 SSOT） |
| W1 | 任务中心改造（已裁决） | [00](00-framework.md) §三 |
| W2 | 共享事件分流（原待裁决 7 的建议 (c)） | [00](00-framework.md) §3.5、§四 #3 |
| W3 | **新增**（分档节流需两端一致） | [02](02-framework-update.md) §四种 W3 |

**与原设计的显式冲突（已裁决，记录备查）**：
- `00-framework` §2.3 原写"阶段 3 **大幅收缩**：只做 URL 按钮、不做回调/编辑" → 已由 [02](02-framework-update.md) §2.3 重定义，**本总纲以 02 为准**。
- 原 Q2 裁决"先 Telegram 双向，再做飞书" → 本轮裁决改为"**先 TG + 钉钉**；企微/飞书待证据补齐"。
- 原 Q4 裁决"聚合键切**三元组**" → 阶段 A 改为**二元**（`correlation_id` 至今恒空，见 [00](00-framework.md) §2.3）。

---

# 第二部分：Docker 端阶段 D 详细设计

## 2.1 现状分析

### 2.1.1 早退逻辑：关闭 = 什么都不做

`pilotstd/core/notification/manager.py:294-296`：

```python
294:        if not self._enabled:
295:            logger.debug("通知功能未启用，跳过事件 %s 的发送", event_type)
296:            return
```

—— 这是**事件送进通知链路的唯一入口**（`send_event` 定义于 `:278`）。它一返回，**消息不构建、`notification_log` 不写、渠道不调用**。

`_enabled` 的解析（`manager.py:144-148`）：

```python
144:        self._enabled = config.get("notification.enabled", False)
145:        # 用户级配置优先：user_preferences 表（数据库）覆盖 config.json，保证 Web 端设置实际生效
146:        db_enabled = self._read_user_enabled()
147:        if db_enabled is not None:
148:            self._enabled = db_enabled
```

且 `manager.py:153-154` —— **渠道只在启用时才初始化**：

```python
153:        if self._enabled:
154:            self._init_channels()
```

⇒ 关闭状态下 `self._channels` 为空字典。**这一事实决定了设计**：不能简单地把早退删掉让它走 `_do_send`，否则 `_send_now`（`:350-379`）会对每个"渠道"走到 `channel is None` 分支，写入 `status="failed"` + `error_msg="渠道未初始化"` 的**假失败行**。

### 2.1.2 日志写入点：与投递强耦合

`pilotstd/core/notification/_manager_ops.py:58-106` 的 `NotificationOps.log()` 是**唯一**写 `notification_log` 的地方：

- 调用者只有 `manager.py:357`（渠道不可用）、`:375`（正常/失败）、`:378`（异常）——**三处全在 `_send_now` 内**。
- ⇒ "写日志"目前在物理上**只能由投递过程触发**，这正是"关闭推送 = 不记录"的**结构性原因**（不是某个 if 判断，而是没有第二条调用路径）。
- INSERT 覆盖 24 列（`:69-76` 列名、`:77-104` 取值），**不含 `is_read`**（依赖建表默认 0，见 `pilotstd/core/db/_migrate_v16_v49.py:41`）。
- 失败**静默**（`:105-106` 只记 warning）——**新路径必须沿用这一口径**。

### 2.1.3 已存在但当前用不上的查询链路

| 能力 | 位置 | 现状 |
|---|---|---|
| 分页查询 | `_manager_ops.py:110-154` `get_logs()` | 已实现（含 `status`/`channel`/`is_read` 筛选） |
| 标记已读 | `_manager_ops.py:157-166` | 已实现 |
| 未读计数 | `_manager_ops.py:168-171` | 已实现 |
| 保留期清理 | `_manager_ops.py:175-182` `cleanup_logs(days=30)` | **已被定时任务调用**：`docker/scheduler.py:200`（函数体）、`:206`（注册）、`:367`（间隔任务） |
| HTTP 端点 | `docker/api/notification.py:342-383`（`GET /api/notification/logs`）、`:386`（已读）、`:404`（未读计数）、`:415`（删除） | 已实现，**原样透传 `status` 字符串**（`:376`） |
| Web 视图 | `web/src/views/NotificationLogsView.vue`（431 行） | 已实现（列表 + 筛选 + 详情 + 清理） |
| Web 轮询 | `web/src/composables/useNotification.ts:16`（`POLL_INTERVAL_MS = 30_000`）、`:98`（拉 `page_size=20`） | 已实现，30 秒轮询 |

⇒ **D 阶段不需要新建任何查询/展示能力**，只需让"关闭状态"也能产出日志行——这是 D 工作量小的根本原因。

### 2.1.4 耦合的实测后果

- 本地三份数据库的 `notification_log` 实测：当前库 **0 行**、`data/pilotstd.db.bak` **0 行**、7 月备份 **2 行**（[02](02-framework-update.md) §3.1 表 #6）。
- ⇒ 因 `notification.enabled` 默认 `False`（`pilotstd/core/config/defaults.py:54`），**系统历史上几乎没写过通知日志**；关闭推送的用户在 Web 端**看不到任何历史**。

### 2.1.5 必须兼容的既有测试（硬约束）

`tests/test_notification_manager.py:127-132`：

```python
127:    def test_disabled_logs_debug(self, mgr, caplog):
128:        """阶段四：通知功能关闭时记录 DEBUG 日志（不再完全静默）。"""
129:        mgr._enabled = False
130:        with caplog.at_level("DEBUG", logger="pilotstd.core.notification.manager"):
131:            mgr.send_event("test_event", {"k": 1})
132:        assert any("通知功能未启用" in r.message for r in caplog.records)
```

⇒ **该用例锁定了"关闭时记录 `通知功能未启用` 的 DEBUG 日志"**。D 阶段改动后：
1. 文案必须**原样保留**；
2. 日志必须从 **logger 名 `pilotstd.core.notification.manager`** 发出——否则 `caplog.at_level(..., logger=...)` 生效的是目标 logger，而 `_manager_ops` 模块自身的 DEBUG 记录会因 effective level 为 WARNING 被丢弃，用例失败。

## 2.2 目标行为

### 2.2.1 "投递"与"记录/可见"的分离边界

| 环节 | 启用推送（`_enabled=True`） | **关闭推送（`_enabled=False`）** | 说明 |
|---|---|---|---|
| 构建消息（`_build_message`） | ✅ | ✅ **构建** | 日志需要 title/body |
| 投影回填（`apply_mapping`） | ✅ | ✅ **回填** | Web 端按 `notify_event`/`task_kind` 筛选需要它 |
| 契约校验（`_validate_message`） | ✅ | ✅ **校验** | 与主路径同口径，避免空行 |
| 解析目标渠道（`_policy.get_channels_for_event`） | ✅ | ❌ **不做** | 关闭时不涉及渠道；也避免为纯记录引入 DB 策略查询 |
| 写 `notification_log` | ✅（每渠道一行） | ✅ **每事件一行**（`channel=""`、`status="skipped"`） | 核心变更 |
| 聚合器（`aggregator.enqueue`） | ✅ | ❌ **不进入** | 聚合的目的是减少**投递**条数；无投递即无聚合 |
| 静默时段（`_is_quiet_hours`） | ✅（延迟入队） | ❌ **不适用** | 静默是"延迟投递"，无投递则无意义 |
| 渠道 `send()` | ✅ | ❌ **绝不调用** | 验收断言点 |
| 投递健康度（`_record_delivery`） | ✅ | ❌ **不记录** | 未投递 ≠ 投递失败（否则会误触发"通知投递失败"告警） |

### 2.2.2 新增的状态取值

| 列 | 取值 | 语义 |
|---|---|---|
| `notification_log.status` | **`"skipped"`**（新增） | 该事件**未投递**（推送关闭），仅记录 |
| `notification_log.channel` | `""`（空串） | 关闭状态无渠道参与（不是"渠道失败"） |
| `notification_log.error_msg` | `""` | 无错误——**不得**复用 `failed` + 错误文案（否则前端显示为失败） |
| `msg.delivery_status` | `"skipped"`（落库前设置） | 该列是投递态；默认 `"pending"` 会误导（永远不会变 success） |
| `notification_log.is_read` | `1` | **建议**：不打扰未读计数（关闭状态没有"新通知"可读）→ 见待裁决 **N1** |

## 2.3 改动清单（文件:行号）

### 2.3.1 后端 ①：`pilotstd/core/notification/manager.py:294-296` —— 净增 0 有效行

**约束**：该文件**有效行 498**（实测），G-010 阻断线 **500**（`scripts/check_g_010_code_size.py:29 MAX_FILE_LINES = 500`；`:30 WARN_FILE_LINES = 400`）→ **必须净增 0**。

```python
# 改前（294-296，3 有效行）
        if not self._enabled:
            logger.debug("通知功能未启用，跳过事件 %s 的发送", event_type)
            return

# 改后（3 有效行，净增 0）
        if not self._enabled:
            self.ops.record_suppressed(event_type, event_data)
            return
```

- DEBUG 文案**移入** `record_suppressed`，但**用 manager 的 logger 名**发出（见 2.3.2）→ `tests/test_notification_manager.py:127-132` 保持绿。
- 若评审倾向"文案留在原处"，则改后为 4 有效行 → 有效行 499 ≤ 500（**仍合规但只剩 1 行余量**）；**本设计推荐净增 0 方案**。

### 2.3.2 后端 ②：`pilotstd/core/notification/_manager_ops.py` —— 新增 1 方法 + `log()` 加 1 参数

**（a）新增 `record_suppressed()`**，插入位置：`log()` 之后（`:106` 之后、`get_logs()` 之前），保持"日志族方法聚在一起"。

```python
    # 阶段 D：关闭推送不等于不记录——把事件写成一行 status="skipped" 的日志。
    # 为什么不复用 _send_now 的日志路径：关闭时渠道未初始化（manager.py:153-154），
    # 走那条路会对每个目标渠道写出 status="failed" 的假失败行（channel is None 分支）。
    # 为什么用宿主的 logger 名：tests/test_notification_manager.py:127-132 以
    # caplog.at_level(..., logger="pilotstd.core.notification.manager") 锁定该 DEBUG 文案，
    # 从本模块自身的 logger 发出会因 effective level 不足而被丢弃。
    def record_suppressed(self, event_type: str, event_data: dict[str, Any]) -> None:
        """关闭推送时记录一条"未投递"日志（不构建渠道、不做聚合、不写健康度）。"""
        logging.getLogger(self._mgr.__class__.__module__).debug(
            "通知功能未启用，跳过事件 %s 的发送", event_type
        )
        try:
            msg = self._mgr._build_message(event_type, event_data)
            self.apply_mapping(msg, event_type, event_data)
        except Exception as e:      # noqa: BLE001 — 记录失败不得影响主业务流程
            logger.warning("记录未投递事件失败: event=%s error=%s", event_type, e)
            return
        try:
            self._mgr._validate_message(msg, event_type)
        except ValueError as e:
            logger.error("构建器契约校验失败，事件 %s 已跳过记录: %s", event_type, e)
            return
        msg.delivery_status = "skipped"
        self.log(event_type, "", msg, "skipped", "", datetime.now().isoformat(), is_read=1)
```

**要点**：
- `self._mgr._build_message` / `_validate_message` 是**既有私有方法**（`manager.py:569`、`:315`）——`NotificationOps` 已经在用宿主的私有属性（`_manager_ops.py:44-47` 的 `_db` 属性代理），**同口径**，不引入新风格。
- **不调用** `_policy.get_channels_for_event`、`aggregator.enqueue`、`_is_quiet_hours`、`_record_delivery`、`_send_now`。
- 异常一律**降级可见、不致命**（与 `log()` 静默失败、`apply_mapping` 的 `:198-205` 同口径）。

**（b）`log()` 增加 `is_read` 参数**（`:58-66` 签名 + `:69-76` 列名 + `:77-104` 取值）：

```python
# 签名（原 58-66）
    def log(self, event_type, channel, msg, status, error_msg, sent_at, is_read: int = 0) -> None:
# INSERT 列名（原 69-76）追加 "is_read"；VALUES 追加一个占位符（24 → 25 个 ?）
# 取值元组（原 77-104）末尾追加 `is_read`
```

- **三处既有调用点无需改动**（`manager.py:357,375,378` 用位置参数，新参数有默认值 `0` = 建表默认值，行为逐字节不变）。
- ⚠️ 占位符数量与列名数量必须同步（24→25）；`INSERT` 语句是单一长字符串，改一处漏一处会**运行期报错被 `:105-106` 静默吞掉**→ 测试必须覆盖"行数 +1"。

### 2.3.3 后端 ③：`docker/api/notification.py` —— **零改动**（已核实）

| 端点 | 行号 | 是否需要改 |
|---|---|---|
| `GET /api/notification/logs` | `:342-383` | **不改**：`:376` 原样透传 `r["status"]`，新值 `skipped` 直接可用；`:370-379` 的 10 字段不含 `delivery_status`（前端口径不变） |
| `GET /api/notification/unread-count` | `:404` | **不改**（行为随 `is_read=1` 自然不计入） |
| `GET/PUT /api/notification/config` | `:110`、`:165` | **不改**：`enabled` 仍是唯一开关，语义在文档/文案层澄清（2.3.4） |
| `DELETE /api/notification/logs` | `:415` | **不改** |
| 定时清理 | `docker/scheduler.py:200` | **不改**：`cleanup_logs(days=retention_days)` 已按 `sent_at` 清理，新行自动纳入保留期 |

### 2.3.4 前端 ①：`web/src/views/NotificationLogsView.vue` —— 3 处

| # | 位置 | 现状 | 改动 |
|---|---|---|---|
| 1 | `:113-117` `statusOptions` | 仅 `success` / `failed` 两个筛选项 | 增加 `{ label: t('notification.logs.status.skipped'), value: 'skipped' }` |
| 2 | `:131-135` `statusSeverity` | `success`→success、`failed`→danger、其余→info | 增加 `if (s === 'skipped') return 'info'`（显式分支，避免依赖 fallthrough） |
| 3 | `:137-139` `statusLabel` | **二元回退**：`s === 'success' ? 成功 : 失败` | 改为映射表（`success`/`failed`/`skipped`），**否则 `skipped` 会显示成"失败"** |

⚠️ **第 3 处是必修项**（不是优化）：现状把任何非 `success` 值渲染为"失败"，D 阶段上线后**每一行未投递日志都会显示为红色"失败"**。

**顺带发现（不在 D 范围，登记不改）**：`:107-112` 的 `channelOptions` 只列了 `wechat`/`telegram`/`feishu` 三项，**缺 `dingtalk`**；`:120-124` 的 `CHANNEL_KEYS` 同样缺 `dingtalk`（未知渠道原样回显，故 `dingtalk` 会显示英文键名）。

### 2.3.5 前端 ②：语言文件 —— 新增 1 键 + 复核 1 键

| 文件 | 键 | 动作 |
|---|---|---|
| `web/src/locales/zh-CN.json` | `notification.logs.status.skipped` | **新增**（现 `notification.logs.status` = `{all, success, failed, read, unread}`，实测无 `skipped`） |
| `web/src/locales/en.json` | 同上 | **新增**（保持三语对齐口径） |
| 两份语言文件 | `notification.config.enable_all`（现值"启用通知"） | **复核文案**：D 后该开关语义收窄为"启用**推送**"，建议改为"启用推送"或补充 hint（属文案裁决，见 N2） |

### 2.3.6 前端 ③：`web/src/composables/useNotification.ts` —— **不改**

- `:16` `POLL_INTERVAL_MS = 30_000`、`:98` `getNotificationLogs({page:1, page_size:20})` 逻辑不变。
- 但**行为后果**：未投递行会出现在 30 秒轮询的通知列表里（`:100` `messages.value = items.map(normalize)` 不过滤 `is_read`）→ 是否应让 `skipped` 行**不出现在通知列表**（只出现在日志页）是语义裁决，见 **N1**。

### 2.3.7 后端 ④（回滚开关）：`pilotstd/core/notification/stage.py`

新增独立开关（**不复用** `NOTIFY_REDESIGN_STAGE`——D 不在 `0/1/2/2.5/3/4` 序列内，`stage.py:63` `KNOWN_STAGES`）：

| 位置 | 内容 |
|---|---|
| `stage.py:60` 附近 | 新增 `ENV_RECORD_WHEN_DISABLED = "NOTIFY_RECORD_WHEN_DISABLED"` |
| `:50-58` `__all__` | 新增导出 `is_suppressed_record_enabled` |
| 文件末尾（`:112` 后） | 新增谓词：读环境变量，`v1`/`v0` 判定；**非法值回退默认 `v1` 并记 warning**（沿用 `:84-93` 的既有口径） |
| `record_suppressed`（2.3.2） | 首行加守卫：未开启则**恢复完全静默**（只发 DEBUG、直接 return） |

文件规模充裕（`stage.py` 112 行 raw / 约 60 有效行），不触及 G-010。

## 2.4 验收判据（可断言）

| # | 判据 | 断言方式 |
|---|---|---|
| V1 | 关闭推送，触发事件 → `notification_log` **有 1 行** | `SELECT COUNT(*) FROM notification_log` 由 0 → 1 |
| V2 | 关闭推送 → 渠道 **`send()` 未被调用** | `mock_channel.send.assert_not_called()` |
| V3 | 关闭推送 → 该行 `status="skipped"`、`channel=""`、`error_msg=""`、`delivery_status="skipped"`、`is_read=1` | 逐列断言 |
| V4 | 关闭推送，Web 端能查到 | `GET /api/notification/logs` 返回该行且 `status=="skipped"` |
| V5 | 关闭推送 → **聚合器与健康度未被触碰** | `aggregator.enqueue.assert_not_called()`、`delivery_health.record.assert_not_called()` |
| V6 | 启用推送 → **与现状逐项一致**（回归） | 既有通知测试全绿（含 `test_send_event_with_aggregator_disabled`、`:150-160` 的聚合/bypass 用例） |
| V7 | `NOTIFY_RECORD_WHEN_DISABLED=v0` → 恢复现状（关闭即无日志） | 同 V1 断言 `COUNT(*)==0` |
| V8 | **G-010 有效行 ≤500** | `python scripts/check_g_010_code_size.py` 退出码 0，且 `manager.py` 有效行 **≤498** |
| V9 | 前端不再把 `skipped` 显示为"失败" | `statusLabel('skipped')` 返回 `status.skipped` 文案（组件测试） |

## 2.5 回滚方式

| 层 | 手段 | 回滚后行为 |
|---|---|---|
| **首选（不改代码、不迁移数据）** | 环境变量 **`NOTIFY_RECORD_WHEN_DISABLED=v0`** | 关闭推送 = 完全静默（与现状逐字节一致） |
| 次选 | 代码回退 `manager.py:294-296` 的 3 行 + 移除 `record_suppressed` + `log()` 参数（新增参数有默认值，回退不影响 DB） | 同上 |
| **无需回滚** | DB 无 schema 变更（无迁移号）；`status="skipped"` 是**行内值**，旧代码读到它只是不识别（前端回滚后会把 skipped 显示为"失败"→ 故前端与后端**必须同批上线**） | — |

⚠️ **前后端必须同批**：仅回滚后端时，前端不会收到 `skipped`（无影响）；**仅回滚前端时**，`skipped` 行会显示为"失败"（V9 失守）。

## 2.6 测试用例清单

### 2.6.1 单测（新增 8 个，建议置于 `tests/test_notification_stage_d_record.py`）

| # | 用例名 | 断言要点 |
|---|---|---|
| U1 | `test_disabled_writes_one_log_row` | 关闭 + 触发事件 → `notification_log` 行数 +1 |
| U2 | `test_disabled_log_row_fields` | `status="skipped"`、`channel=""`、`error_msg=""`、`delivery_status="skipped"`、`is_read=1` |
| U3 | `test_disabled_never_calls_channel_send` | 渠道 mock 的 `send` 未被调用（核心断言） |
| U4 | `test_disabled_skips_aggregator_and_health` | `aggregator` 不进入、`delivery_health.record` 未被调用 |
| U5 | `test_disabled_keeps_debug_message` | **复用既有口径**：`caplog.at_level("DEBUG", logger="pilotstd.core.notification.manager")` 下能捕获 `通知功能未启用` |
| U6 | `test_disabled_build_failure_only_warns` | 构建抛异常 → 不抛到调用方、不写行、只 warning |
| U7 | `test_disabled_empty_message_skips_row` | `_validate_message` 抛 ValueError → 不写行、记 error |
| U8 | `test_env_v0_restores_silence` | `NOTIFY_RECORD_WHEN_DISABLED=v0` → 不写行（回滚判据） |
| U9 | `test_env_invalid_falls_back_to_v1` | 非法值（`abc`）→ 按 `v1` 生效 + warning（沿用 `stage.py` 既有口径） |
| U10 | `test_log_is_read_default_unchanged` | `log()` 不传 `is_read` 时写 0（既有 3 个调用点行为不变） |

### 2.6.2 集成测试（新增 2 个，建议置于 `tests/test_notification_api.py`）

| # | 用例名 | 断言要点 |
|---|---|---|
| I1 | `test_logs_endpoint_returns_skipped` | 关闭 + 触发 → `GET /api/notification/logs` 返回该项且 `status=="skipped"` |
| I2 | `test_unread_count_excludes_skipped` | 关闭 + 触发 N 次 → `GET /api/notification/unread-count` 不增加 |

### 2.6.3 前端测试（新增/改 2 个）

| # | 位置 | 断言要点 |
|---|---|---|
| F1 | `web/src/views/NotificationLogsView.test.ts`（已有文件） | `statusLabel('skipped')` ≠ 失败文案；筛选下拉含 `skipped` 选项 |
| F2 | 同上 | `statusSeverity('skipped') === 'info'` |

### 2.6.4 回归测试（必须全绿）

| 范围 | 说明 |
|---|---|
| `tests/test_notification_manager.py` | **含锁定用例 `:127-132`**（V6 的前置） |
| `tests/test_notification_manager_extended.py` | `test_init_disabled_no_channels`（`:20-24`）断言 `_enabled is False` → 语义不变，须仍绿 |
| `tests/test_notification_core.py`、`test_notification_api.py`、`test_notification_stage2b_*.py` | 通知链路既有行为 |
| `tests/test_notification_e2e.py` | 41 事件覆盖（G-045 联动） |
| 门禁 | `bash scripts/check_all.sh --fast` 退出码 0（**须含 G-010 与 G-029 测试联动**） |

## 2.7 风险与边界

| # | 项 | 判断 | 依据 |
|---|---|---|---|
| R1 | **静默时段是否变化** | **不变** | 静默分支在 `_do_send`（`manager.py:340-342`），关闭路径在 `send_event` 早退处**之前**就返回 → 不会经过静默判定。语义上"静默 = 延迟投递"，关闭态无投递，故无冲突 |
| R2 | **聚合器是否变化** | **不变** | 关闭路径不调用 `aggregator.enqueue`（`manager.py:346`）；聚合器实例仍在 `__init__:162-175` 按 `aggregate_enabled` 创建（与 `_enabled` 无关），故判据 V5 需断言"未入队"而非"未创建" |
| R3 | **与阶段 0/1/2/2.5 是否冲突** | **不冲突** | 0（前端轮询/WS 清理）与 D 正交；1（12 列）已落地，D 只**填**这些列；2/2.5a 的 `apply_mapping` 被 D 复用（`_manager_ops.py:185-208`，谓词 `is_mapping_enabled()` 不因关闭状态改变） |
| R4 | **日志量增长** | **中风险** | 关闭态从 0 行变为"每事件 1 行"。保留期 30 天的清理已存在（`docker/scheduler.py:200`），但**需在实施时确认 `notification_cleanup` 任务本身处于启用状态**（`:367` 的间隔注册与 `tasks.*_enabled` 默认值需核）。参考量级：历史事故记录 `notification_log` 1,148 条（`tests/test_delivery_health.py:6`） |
| R5 | **误触发"通知投递失败"告警** | **已规避** | 关闭路径不调用 `_record_delivery`（该函数在 `manager.py:383-398`，仅 `_send_now` 内调用）→ 未投递不会被计入健康度 |
| R6 | **G-010 余量** | **高风险（设计已规避）** | `manager.py` 有效行 **498** / 阻断 **500**（`scripts/check_g_010_code_size.py:29`）→ 本设计净增 0；实施时**任何**额外行都会踩线，须在同批拆分或压缩 |
| R7 | **`log()` 占位符数量** | **中风险** | 24→25 的列名/占位符/取值三处必须同步；错配会被 `:105-106` 静默吞掉 → 由 U1/U10 覆盖 |
| R8 | **前后端不同批** | **中风险** | 见 2.5 的表（仅回滚前端 → `skipped` 显示为"失败"） |
| R9 | **未读语义** | **待裁决（N1）** | 本设计取 `is_read=1`；若决策者要求未投递行也计入未读，则改 `is_read=0` 并调整 I2 |
| R10 | **桌面端是否受影响** | **不受影响** | `_enabled` 在 Windows 端同样默认 False（`defaults.py:54`），且桌面端不写 `notification_log` 的查询链路；D 会让桌面端事件**也开始写日志行**（因为共用 manager）——这是**预期内的副作用**，需在 W2 一并评估（见 N3） |

## 2.8 工作量预估

| 部分 | 内容 | 预估 |
|---|---|---|
| 后端 | `manager.py` 3 行 + `_manager_ops.py` 1 方法（约 25 有效行）+ `log()` 参数 + `stage.py` 1 谓词 | **0.5 天** |
| 前端 | `NotificationLogsView.vue` 3 处 + 2 个语言键（+ 开关文案复核） | **0.3 天** |
| 测试 | 单测 10 + 集成 2 + 前端 2 + 回归跑通 | **0.5 天** |
| **合计** | — | **约 1.5 天（小～中）** |

---

## 待裁决清单（本轮新增）

| # | 待裁决点 | 备选 | 建议 + 理由 |
|---|---|---|---|
| **N1** | 未投递（`skipped`）日志行是否计入**未读**、是否出现在 Web **通知列表**？ | (a) `is_read=1`、不出现在通知列表（只进日志页） (b) `is_read=0`、计入未读 (c) `is_read=1` 但仍在通知列表显示 | **(a)**：关闭推送时用户明确表示"不要打扰"，未投递项计入未读会造成"关不掉的红点"；但需要前端在 `useNotification.ts:100` 的 `normalize` 处过滤 `status==='skipped'`（**该过滤不在本设计改动面内**，若选 (a) 需追加 1 处前端改动） |
| **N2** | `notification.config.enable_all` 的文案是否改为"启用推送"？ | (a) 改文案（+ hint 说明"关闭后仍记录历史"） (b) 保持"启用通知" (c) 改文案并同时新增一个"记录"开关 | **(a)**：D 之后该开关**只控制投递**，文案不改则与行为不符；(c) 违背 R-008 最小改动 |
| **N3** | Windows 端事件在 D 之后**也会写库日志**（共用 manager），是否接受？ | (a) 接受（桌面与 Docker 共用一份日志） (b) 在 W2 分流时让桌面端不写库日志 (c) 给日志行加"来源端"标识 | **(a)（暂）**：桌面端 `_enabled` 默认 False → D 后桌面事件会写库，可让 W1 的任务中心复用这批记录（潜在收益）；若选 (c) 需新增列（超出 D 范围） |
| **N4** | 回滚开关默认值何时从 `v1` 定稿为"无开关"？ | (a) D 交付即默认 `v1`，观察一段后移除开关 (b) 永久保留开关 | **(a)**：与 `NOTIFY_AGG_KEY` 同模式（[notification-redesign/03](../notification-redesign/03-实施路径.md) §3.0 的"独立紧急回滚开关"先例），稳定后移除可减少配置面 |

---

## 附：可复算命令

```powershell
# ── 现状核对 ──
python -c "import pathlib;p=pathlib.Path('pilotstd/core/notification/manager.py');raw=p.read_text(encoding='utf-8').splitlines();print('effective=',len([l for l in raw if l.strip() and not l.strip().startswith('#')]))"
Select-String -Path pilotstd\core\notification\manager.py -Pattern 'if not self\._enabled|def send_event|def _build_message|def _validate_message|def _send_now'
Select-String -Path pilotstd\core\notification\_manager_ops.py -Pattern 'def log|INSERT INTO notification_log|def get_logs|def cleanup_logs|def apply_mapping'
Select-String -Path scripts\check_g_010_code_size.py -Pattern 'MAX_FILE_LINES|WARN_FILE_LINES'
Select-String -Path tests\test_notification_manager.py -Pattern 'test_disabled_logs_debug' -Context 0,6
Select-String -Path docker\api\notification.py -Pattern '/api/notification/logs|r\["status"\]'
Select-String -Path web\src\views\NotificationLogsView.vue -Pattern 'statusOptions|statusSeverity|statusLabel|channelOptions'
python -c "import json,pathlib;d=json.loads(pathlib.Path('web/src/locales/zh-CN.json').read_text(encoding='utf-8'));print(d['notification']['logs']['status'])"
Select-String -Path pilotstd\core\notification\stage.py -Pattern 'ENV_STAGE|KNOWN_STAGES|HIGHEST_STABLE_STAGE|def is_'
# ── 验收（实施后）──
python scripts/check_g_010_code_size.py
bash scripts/check_all.sh --fast
```

**自检**：代码引用 40+ 处（`路径:行号`，均经回读校验）；无 schema 变更、无迁移号；与 `notification-redesign` 的三处冲突已在 §1.4 显式列出。
