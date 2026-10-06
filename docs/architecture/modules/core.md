# 模块文档：核心引擎（Core）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/core/` |
| G-031 映射 | `pilotstd/core/`（2026-09-25 落地：`DOC_SYNC_MAP` 已含该条，改任何 core 文件都会要求同步本文件） |
| 核心类 | `Database` / `ConfigManager` / `CacheManager` / `NotificationManager` |
| 子模块数 | 105 个 `.py`（新增 `_migrate_v66_announcement_record_final_name.py`：名称决策③结果落库，2026-10-05 名称解析统一批次二）（**口径**：`pilotstd/core/` 递归全部 `.py`，含 `__init__.py`、不含 `__pycache__`；**截至 2026-10-05**；顶层 = 3 个包 config / db / notification + 23 个直属模块。**该行由 G-048 门禁锁定**——增删包内 `.py` 必须同批改本行，否则提交被阻断） |
| Schema 版本 | `CURRENT_SCHEMA_VERSION = 66`（`db/_constants.py`；v66＝announcement_record 追加 `final_name` 列 + 从 pending_lookup 回填，2026-10-05 名称解析统一批次二） |
| 状态 | 活跃 |

## 模块职责

PilotStd 三端（CLI / WinUI / Docker）共享的基础设施层：数据库封装与迁移、配置持久化、缓存、通知分发、安全（密钥/密码哈希/路径防护）与通用工具。被 `pilotstd/manager/`、`pilotstd/query/`、`docker/` 等上层模块统一引用，是引擎的"地基"。

## 架构

```
pilotstd/core/
│
├── db/                        # 数据库封装 + 版本迁移
│   ├── database.py            # Database：sqlite3 封装（WAL + 外键 + 线程本地连接 + 迁移执行）
│   ├── migrations.py          # 迁移注册表（装饰器 migration(N) 注册，按版本顺序执行）
│   ├── _constants.py          # CURRENT_SCHEMA_VERSION + MIGRATIONS 字典
│   ├── _migration_checksum.py # 迁移校验和（防篡改/防回潮；三级：通过/自愈/阻断）
│   └── _migrate_*.py          # v2~v65 各版本迁移实现（大版本拆分独立文件，控 G-010）
│                              # 分段文件：_migrate_v2_v15 / _v16_v49 / _v31_plus /
│                              # _v37_plus / _v44 / _v50 ~ _v60（最新 v60 删 user_favorites 死列）
│
├── config/                    # 配置管理
│   ├── manager.py             # ConfigManager：点分隔 JSON 持久化 + 原子替换
│   ├── paths.py               # get_data_dir / get_db_path / get_library_root
│   ├── crypto.py              # Fernet Key 管理与加密解密
│   ├── defaults.py            # 默认配置
│   ├── migrate.py             # 配置迁移
│   ├── service.py             # 配置读写服务（Web/Win 共用）
│   └── settings_schema.py     # 配置 Schema 校验（含 tasks.* 定时任务登记表：
│                              #   auto_scan / auto_announce / date_reminder /
│                              #   auto_health_check / auto_archive_retry 各一对
│                              #   enabled+cron；2026-09-25 补登 auto_archive_retry_*）
│
├── notification/              # 通知系统
│   ├── manager.py             # NotificationManager：事件 → 渠道分发 + 聚合装配（**包根改为惰性导出**，见下行；**构建器注册表由 `event_spec` 派生**，2026-10-03 步 B D2，有效行 481 → 397）
│   ├── __init__.py            # 包根惰性导出：`NotificationManager` 改为**取用时才 import**（2026-10-03 步 B D3）——此前"导入本包"即拖入通知全栈（构建器/渠道/凭证），`config/defaults` 派生订阅规则时会被牵连；现 import 期只剩 channel/events 链
│   ├── _manager_ops.py        # 日志/查询/清理/WS 广播（组合式 NotificationOps，2026-09-26 拆出）
│   ├── _dispatcher.py — 事件分发；**阶段 D 可见性解耦**（2026-10-03）
│   │    关闭投递（`_enabled=False`）时仍写 `notification_log`（status=`skipped`，不调用渠道
│   │    `send()`、不进投递健康统计）；回滚开关 `NOTIFY_RECORD_WHEN_DISABLED=v0`。
│   ├── telegram_receiver.py — TG 接收通道（B2b-3，2026-10-03）
│   │    长轮询（默认，应用主动拉取，不需要对外地址）与 webhook（走 B2b-1 端点）双模式；
│   │    `receive_mode` 是**运行时配置**（`defaults.py`），**不进 channel_spec**。
│   │    线程生命周期由 `NotificationManager.start/stop_telegram_receiver()` 管理，
│   │    `shutdown()` 收停；**不在构造时自动启动**（桌面端/测试不连外网）。
│   ├── callback_service.py / callback_store.py — 回调闭环与持久化幂等（B2b，2026-10-03）
│   │    `handle_callback`：解析 token（仅用于定位密钥）→ 验签 → **持久化幂等** → 服务端角色
│   │    授权 → 执行动作（ignore/snooze 写 ack_status；retry 请求重投）。
│   │    `LogBackedReplayGuard`：复用 `notification_log`（`correlation_id` 存事件号、
│   │    `event_type='callback'`、`sent_at` 供 TTL 清理）⇒ **无新建表、无迁移号**。
│   ├── user_moments.py — 用户时刻清单（**第二 SSOT**，阶段 C，2026-10-03）
│   │    36 个 Docker 侧用户时刻（逐行转录自 00-framework §1.1），提供
│   │    `moments_without_event()` / `events_without_moment()` / `unknown_event_keys()`；
│   │    声明的例外（#5 无事件、3 个多余事件无时刻）写成常量，放宽必须同时改常量与测试。
│   ├── callback.py — 回调验签/动作授权/防重放骨架（阶段 B 基础先行，2026-10-03）
│   │    `verify_callback`（telegram/dingtalk/feishu 逐渠道；企微按缺口 1/2 一律 501 不猜协议）、
│   │    `authorize_action`（仅管理员；角色必须来自服务端，不信任载荷身份）、
│   │    `ReplayGuard`（进程内幂等窗口，接口可换成 DB 实现）、`parse_envelope`（载荷归一）。
│   │    **不含公网端点**：`POST /api/notification/callback/{channel}` 属 B2b（需部署侧定对外地址）。
│   ├── channels/feishu.py — 飞书渠道：**签名校验已实现**（2026-10-03）
│   │    配了签名密钥时请求体带 `timestamp`（秒）+ `sign`；算法为
│   │    `base64(HMAC-SHA256(key="timestamp\nsecret"))`——与钉钉**互换 key/msg 布局**，勿互相套用。
│   ├── interaction.py — 交互能力底座（阶段 B 基础先行，2026-10-03）
│   │    `ChannelCapabilities`（能否回调/能否编辑/编辑锚点/说明键）+ `MessageHandle`
│   │    （渠道无关改写句柄 `(channel, anchor, value)`；锚点闭集 `message_id` / `out_track_id`）。
│   │    渠道 `capabilities` 如实声明：TG 可回调+可编辑；钉钉/飞书可回调不可编辑（缺口 6 /
│   │    Webhook 形态无 message_id）；企微两者皆不启用（缺口 1/2 未闭合）。
│   ├── channels/dingtalk.py — 钉钉渠道：**双读**（阶段 S，2026-10-03）
│   │    旧形态＝群机器人 Webhook + 可选加签（逐字保留）；企业级形态＝应用凭证 + 机器人编码
│   │    + 卡片模板 ID + 群会话 ID，经 `/v1.0/oauth2/accessToken` 取令牌后创建并投递互动卡片。
│   │    优先级：企业级字段齐全 ⇒ 企业级；否则回落 Webhook；两者都配 ⇒ 企业级优先（记一行 info）。
│   │    卡片负载结构在渲染层（`renderer.DingTalkCardRenderer.render_card`），渠道层只负责投递。
│   │    **边界（勿动）**：本表按**数据字典**口径维护——中文是 i18n 真实标题的匹配契约，
│   │    不是文案；不 i18n 化、不进 G-047 基线、不做逐行豁免（理由见文件头）。
│   ├── tiered.py — 分档节流与耗时埋点（阶段 B3，2026-10-03）
│   │    `LONG_STAGE_SECONDS=30`（与桌面熔断窗口同源）/ `LONG_STAGE_THROTTLE_SECONDS=60`
│   │    （`platform/notify.py` 的 W3 常量**引用本值** ⇒ 两端一致、无第二份 60）；
│   │    `TieredThrottle`（长阶段同主题 60 秒一条）/ `tier_of`（**只升档不降档**）/\
│   │    `build_context`（耗时并入 `notification_log.task_context` JSON，**无需迁移号**）。
│   ├── _topic_index.py（顶层）— 主题索引数据（2026-10-03 从 notification_aggregator 拆出）
│   │    `_TOPIC_BY_EVENT`（41 条 i18n 标题→主题）+ `_LEGACY_TOPIC_KEYWORDS`（10 组跨语言兜底）。
│   │    **领域数据字典、非文案、勿 i18n**（详见该文件头）。
│   ├── notification_aggregator.py（顶层）— 桌面聚合适配层；2026-10-03 新增公开 `topic_of(title, body)`
│   │                            # （`_extract_topic` 的只读入口），供托盘分档节流与聚合分组**同源**
│   ├── _suppression_queue.py  # 静音时段暂存与补发（组合式 SuppressionQueue：判静音/入队/到期补发；2026-10-03 步 C B1 从 manager.py 拆出，manager 保留同名薄转发与白名单再导出）
│   ├── _dispatcher.py         # 发送编排（模块级函数 send_event/validate_message/do_send/send_now/record_delivery/send_delivery_alert，宿主入参；2026-10-03 步 C B2 从 manager.py 拆出，manager 只留同名一行委托）
│   ├── （2026-10-05 P2 分段接入 · 二）：**飞书**（`channels/feishu.py`）已接入——卡片是 `elements[]`，
│   │   故 `_split_card()` **按元素装填**成多张卡片（单元素超预算时对该元素 `content` 走
│   │   `split_for_channel`），第 2 张起在末元素追加「续 N/M」；`_send_card()` 承载原请求/判定。
│   │   ⇒ **四渠道（telegram / wecom / dingtalk / feishu）全部接入分段**，超长不再整条发出去
│   ├── （2026-10-05 P2 分段接入 · 一）：**企业微信**（`channels/wechat.py`，**2048 字节**口径）
│   │   与**钉钉群机器人**（`channels/dingtalk.py::_send_webhook`，4000 字符保守值）已接入
│   │   `split_for_channel`——`send()` 内按段循环、抽出 `_send_segment` / `_send_webhook_text`
│   │   承载原请求与响应判定（**任一段失败即整体失败，不静默丢段**）；未超长时单段（零行为变更）。
│   │   **飞书**（卡片 `elements[]`，需按元素分片）**待接**，见统筹日程 P2 备注
│   ├── channels/              # wechat / feishu / dingtalk / telegram 渠道适配
│   ├── （2026-10-05 阶段 4 · P6 · **收口：配置粒度切档开关**）：`stage.py` 新增
│   │   `is_config_layers_enabled()`（**阶段 ≥ 4 为真**）——策略层"类别层优先"的**整档开关**：
│   │   为真时 `_policy.get_channels_for_event()` 对 `event_classes` 非空的行只用类别层；
│   │   为假（回滚档 ≤ 3）时对**所有行**按旧 `events` 逐事件匹配 ⇒ `NOTIFY_REDESIGN_STAGE=3`
│   │   能**完整复原**阶段 3 行为（第 1 层回滚开关不再只是改数字）。`_policy` 经 `_manager_ops`
│   │   （唯一集成点）取该谓词，故 `stage`/`mapping` 仍只被允许的模块引用
│   ├── （2026-10-05 阶段 4 · P6 · **4b-2：前端双层 + 吞错可见化**）：前端 `NotificationConfig.vue` 以
│   │   **类别层（10 类）为主入口**、把 41 项业务事件收进折叠的"高级"层；保存时**两层都写**
│   │   （`putNotificationPolicy` 带 `event_classes`）；**吞错可见化**——策略读/写失败一律 `console.warn`
│   │   （**ASCII**，G-040 只管用户文案）+ UI 提示，且**区分"策略 API 失败"与"策略为空"**。
│   │   缓存判据由 4b-1 的 `spec_hash` 承载（层结构变化 ⇒ 前端内容级缓存自动失效重建）。
│   │   另：`pilotstd/core/topic_index_data.json` 登记 `desktop_toast → desktop`（新主题，聚合分组用；
│   │   主题是内部数据串、无 i18n 文案）
│   ├── （2026-10-05 阶段 4 · P6 · **4b-1：层级结构进 spec_hash + 策略 PUT 双层**）：
│   │   `channel_spec.spec_payload()` 增两块——`notify_events`（类别层 10 类，取自 `mapping.NOTIFY_EVENTS`）
│   │   与 `event_class_map`（事件→类别，取自 `EVENT_MAPPINGS`）；二者**进入被哈希的负载** ⇒
│   │   "层结构变了 ⇒ `spec_hash` 必变 ⇒ 前端内容级缓存必失效"（用户裁定：单一版本源优于另立层版本字段）。
│   │   `docker/api/notification_policy.py::PolicyUpdateRequest` 增 `event_classes` 并转发给
│   │   `save_policy(...)`（4a 已支持该参数，两层互不覆盖：`None`＝不动该层、`[]`＝清空）
│   ├── （2026-10-05 阶段 4 · P6 · **4c：平台层事件登记**）：`desktop_toast` 由"方案 B 显式声明未覆盖"
│   │   转为**正式登记**（Q10 裁决）——`events.py` 新增常量 + `ALL_EVENTS` 条目（**41 → 42**）、
│   │   `event_spec.py` 新增规格（归 `system_health`、`task_kind=""`、`subscribable=False`、
│   │   `payload_keys=frozenset()`、`trigger_file` 指向真实产出点 `notification_aggregator.py`）、
│   │   新增构建器 `_builders_system._build_desktop_toast_message`（空值兜底，不产空文本）与三语键
│   │   `notification.system.desktop_toast.*`。**双清单生死线**：两侧必须同改，
│   │   `event_spec.py` 的导入期断言会拦下"只改一侧"——反向验证见
│   │   `tests/test_notification_desktop_toast.py::test_one_sided_change_fails_at_import`（子进程内制造不一致）
│   ├── （2026-10-05 阶段 4 · P6 · **4a：策略双读**）：`notification_policy` 新增 **`event_classes`** 列
│   │   （迁移 **v68**，TEXT 存 JSON，默认 `'[]'`；编号实证空闲，`CURRENT_SCHEMA_VERSION` 67→68）。
│   │   `_policy.py` 读侧**双读**（裁定 4 甲"新字段优先"）：`event_classes` 非空 ⇒ **只用类别层**（按
│   │   `notify_event` 10 类匹配，**不并入** `events`——并集会让"关闭某类"失效）；为空 ⇒ 回退 `events`
│   │   （逐事件匹配）——**这条回退路径是第 1 层回滚开关 `NOTIFY_REDESIGN_STAGE=3` 的技术前提**。
│   │   `get_policies` 两层原样返回；`save_policy` 新增可选参 `event_classes`，**两层互不覆盖**
│   │   （传 `None`＝不动该层，传 `[]`＝清空）。JSON 解析一律走防御式 `_loads_str_list`（坏值回退 `[]`）。
│   │   **防腐**："事件→类别"查询经 `_manager_ops.notify_event_of()` 转一手——mapping 只允许有一个
│   │   集成点（`tests/test_notification_stage2b_wiring.py::TestWiringBoundaries` 会拦下第二处）
│   ├── task/                  # **任务视角投影（2026-10-05 P4b-1）**：`model.py` 定义 `Task`/`TaskItem`/
│   │   # `TaskProgress`（纯数据 + 纯计算，**不 import DB**）；权威状态源仍是既有 `task_queue`，
│   │   # 本包**不新建主表、不写任务状态**（避免双源/双写）。口径来源 `02-目标架构.md §2.3`：
│   │   # `Task.derive_correlation_id()` ＝ `{task_kind}:{started_at[:19]}`（`started_at` 空 ⇒ 空串，
│   │   # 避免未开始的任务被误判为"批次"而走①批次聚合）；`TaskProgress.should_push` 为进度节流闸
│   │   # （首推/跨 10% 阈值/换阶段/终局 ⇒ True），`mark_pushed()` 保证同一进度不重复推
│   │   # （支撑"同一 message_id 反复 edit"）。`manager.py`（投影入口，2026-10-05 P4b-2）＝**只读**
│   │   # `TaskQueue`：`list_tasks()` **一次批量 `get_all()` 后内存构造**（防 N+1）、`get_task()` 单条、
│   │   # `progress_of()` 产快照、`_loads_result_json()` 防御式解析（空/非串/坏 JSON/非字典 ⇒ `{}`，永不抛）。
│   │   # **硬约束**：不写任务状态、**不触发任何通知**（`task_progress` 维持"只加数据结构"裁决）、
│   │   # 不改聚合键与 `notification_policy`。`TERMINAL_STATUSES` **两套词表都认**
│   │   # （设计 `succeeded/abandoned` ＋ 实际 `completed/cancelled`），否则真实终局会被节流闸拦住
│   ├── （2026-10-05 P1 灰度开关）：`aggregate_buffer.agg_key_mode()` 读 `NOTIFY_AGG_KEY`——
│   │   `v2`（默认）＝分层键；`v1`＝**旧键**（`事件类型[<SEP>实体]`）供回滚/灰度；
│   │   未设置 ⇒ v2（不告警）；**非法值 ⇒ 回退 v2 并 `logger.warning`**（按取值去重，避免刷日志）——
│   │   不静默吞配置错误（P-107 精神：问题要可见）；该日志为**开发者诊断**，用 ASCII，不进 i18n 资源（G-047）。
│   │   `_events_in_group`/`_group_entity` 同步**分模式取段**（v1 取第 1/第 2 段；v2 ①取末段、②取第 2 第 3 段）
│   │   ——否则 v1 下按实体刷新会失效
│   ├── （2026-10-05 需求①/②收口）：①**失败明细分组合计**——`build_failed_items_block` 按
│   │   `(error_type, standard_number, standard_name)` **归并**，每行"总数"列为该组合条数、
│   │   `ListBlock.total` 为失败条数**总和**（需求原文"各自总数有多少"；退化成逐条一行会刷屏）；
│   │   ②**日常场景共用"日常桶"**——`_group_key` 的②路径对 `notify_event == "user_activity"`
│   │   （公告拉取/收藏）**或 `task_kind == "favorite_download"`**（收藏转下载，类别属 `task_*`）
│   │   一律返回 `2<SEP>daily` ⇒ 需求②三场景在同一时间窗内**合成一条**（信息不丢由 Z-21 全量块保留保证）；
│   │   其余类别（非收藏链的任务终局/告警）仍按 `notify_event × target_id` 分组
│   ├── （2026-10-05 通知聚合 B1 · E2 批次键搬运）：`_dispatcher.py::send_event` 在构建消息后把 payload 的
│   │   **`correlation_id`** 搬进 `NotificationMessage.correlation_id`（空值＝"非批次路径"）——构建器**不感知批次**，
│   │   批次标识由调用方在导入/批量入口生成（如 `download_batch()` 的 `dl-<uuid8>`）；该键决定聚合器走
│   │   ①批次键（整批一条）还是 ②日常键（按实体分组）
│   ├── （2026-10-05 通知聚合 B1 · 分段）：`renderer.py` 新增 `CHANNEL_TEXT_LIMITS`
│   │   （telegram 4096 字符，官方；wecom 2048 **字节**，官方口径按 UTF-8 计；feishu 4096／dingtalk 4000
│   │   **标注未验证**，取保守值）与 `split_for_channel(text, channel)`——**按渲染后（含转义）长度**判定，
│   │   优先在换行处切、超长单行硬切，**段间标「续 N/M」**（i18n `notification.segment.continued`），
│   │   **不做行数截断**（`MAX_FAILED_ROWS` 作废）；`channels/telegram.py::send` 已接入
│   │   （逐段独立重试，任一段失败即整体失败）
│   ├── aggregate_buffer.py    # 聚合缓冲（窗口内合并同类事件）；**2026-10-05 Z-21**：`_send_merged` 由"仅保留首条 blocks 作骨架"改为**全部条目按到达序拼接**（旧实现丢失第 2..N 条明细；新语义支撑聚合需求①②），身份字段（`message_id`/`correlation_id`）显式搬运约束保持不变；**同日分组键分层（B1-4）**：`_group_key` 按批次标识分流——①有 `correlation_id` ⇒ `1<SEP>批次<SEP>notify_event`（整批一条，**不含 target_id**）／②无 ⇒ `2<SEP>notify_event<SEP>target_id`（`notify_event` 为空回退 `event_type`）；`_events_in_group` **按模式取段**、`_group_entity` 仅 ② 返回实体；`flush()` 对 ①批次组不再按实体筛选（否则永不刷新）。**窗口机制（`_timers`/`_window_start`/`_buffers`）未改动**
│   ├── （2026-10-05 S-1 分类体系扩展）：`event_spec.py` 的 `notify_event` 由 6 类实值扩为 **10 类全集**——
│   │   `task_lifecycle` 拆为 **`task_progress`（过程型）/ `task_result`（成功终局）/ `task_failure`（失败终局）**，
│   │   新增 **`user_activity`**（公告拉取 4 事件 + `favorite_created` + `favorite_abandoned_summary`），
│   │   `normalize_complete` / `archive_complete` 因"按批汇总"改归 `batch_summary`；
│   │   `mapping.NOTIFY_EVENTS` 同步为 10 成员并**取消"7±1"数量封顶**（改为"清单以 `event_spec.py` 为准"）
│   ├── （2026-10-05 通知聚合 B1-3）：`event_spec.py` 的 4 个汇总事件（`batch_query_summary` /
│   │   `batch_download_complete` / `normalize_complete` / `archive_complete`）的 `payload_keys` 追加
│   │   **`failed_items`**；其中 `archive_complete` **按实现对齐**为 `{"category_stats","count","directories","failed_items"}`
│   │   （移除从未传入的 `elapsed_ms`/`standard_number`/`status`/`target_id`）。契约方向：
│   │   `payload_keys`（声明）必须被触发方实际提供，验证见 `tests/test_notification_e2e.py` 的
│   │   `TRIGGER_KEYS` 表（已同批更新 4 条）
│   ├── （2026-10-05 通知聚合 B1 · 数据结构层）：`channel.py` 的 `NotificationMessage` 新增
│   │   **`failed_items: list[dict[str, str]]`**（默认空列表 ⇒ 零行为变更）——一次批量导入/汇总的**逐条失败清单**，
│   │   固定 4 列 `standard_number` / `standard_name`（空 ⇒ `-`）/ `error_type`（枚举键
│   │   `not_found`/`parse`/`network`/`timeout`/`unknown`）/ `error_message`（≤120 字符）；
│   │   落库列为 `notification_log.failed_items`（TEXT 存 JSON，迁移 **v67**）
│   ├── channel.py / events.py / _policy.py / _credentials.py
│   ├── （2026-10-05 通知聚合 B1 · 渲染与 i18n）：两个汇总构建器（`_builders_batch._build_normalize_complete_message`
│   │   与 `_builders_system._build_archive_complete_message`）把 payload 的 `failed_items` 渲染为
│   │   **`ListBlock`**（共用 `_builders_batch.build_failed_items_block()`，4 列口径；**不做行数截断**——
│   │   超长由渠道侧分段）；列名翻译在渲染层 `renderer._LIST_FIELD_KEYS` 登记 4 个字段
│   │   （`standard_number`/`standard_name`/`error_type`/`error_message`；**不登记会渲染为「字段」占位**）；
│   │   `error_type` 的**取值**由构建器侧 `_ERROR_TYPE_KEYS` 先翻译（not_found/parse/network/timeout/unknown →
│   │   i18n 键），i18n 资源已补齐 zh_CN / en / zh_TW
│   ├── channel_spec.py        # 四渠道声明的唯一来源（键/字段/掩码/控件形态/状态规则，2026-10-03 步 A C1）
│   ├── event_spec.py          # 41 个事件声明的唯一来源（15 字段：投影/构建器指针/文案前缀/**模块 i18n 键**/默认渠道/级别/触发文件/载荷键/审计标志/聚合**ASCII 枚举**；2026-10-03 步 B，**D1/D2/D3 均已接入**：mapping / manager / config-defaults）；**2026-10-05 B1 收口**：新增 `LEVEL_ORDER = ("info","warning","error")`（级别**唯一排序口径**，严重度序；`levels` 须为其**保序子序列**，**允许跳级**如 `("info","error")`），断言位于 `tests/test_notification_e2e.py::TestLevelOrder`（全量事件校验）
│   ├── blocks.py / renderer.py / desktop_formatter.py / _format_utils.py
│   ├── _builders_batch.py / _builders_system.py / _builders_validity.py
│   ├── _builders_task_results.py  # 扫描/查询/归档/规范化/状态迁移/公告抓取类模板（2026-09-26 拆出）
│   └── _message_builders.py       # 构建器重导出（管理器只从这里 import，换文件不影响调用方）
│
├── 安全与工具
│   ├── security.py            # 密码哈希（bcrypt）/ 会话令牌
│   ├── frozen.py              # 冻结（PyInstaller exe）环境检测
│   ├── path_guard.py          # 路径穿越防护
│   ├── audit.py               # 审计日志
│   ├── cache_manager.py       # 版本驱动失效策略缓存
│   ├── task_history.py / task_status.py
│   ├── validity_checker.py / _validity_pipeline.py
│   ├── file_index.py / _file_index_query.py  # 本地索引与查询；**批次三 B3-d**：缓存命中后**展示名** `std_name` 按回退链 ③决策→②查询→①解析 重算（**纯内存、不回查 DB、无 N+1**），`found_name` 保持「②查询名」语义不变（D5）；**B3-e**：`get_full_info()` 的返回字典显式带入 `final_name`（上游提供时③优先，缺列时 `None` 不影响），并由 `tests/test_file_index_resolved_name.py` 锁定接线
│   ├── name_resolution.py     # 标准名称「最高可得阶段」回退链：③决策名 `final_name` → ②查询名（standard_info_cache.result_json 的 `standard_name`）→ ①解析名 `std_name`；**对外边界统一全写 `standard_name`，DB 存储列名不动**（2026-10-05 名称解析统一批次一；承接 2026-06-20「名称决策」专项的 `source_name`/`normalized_name`/`final_name` 语义）；**批次三 B3-a 增批量入口 `fetch_resolved_names()`**（固定两次数据查询 + 内存映射 + 超 900 号自动分块，供收藏列表/导出等接口避免 N+1）
│   ├── file_utils.py / download_utils.py / export_utils.py
│   ├── std_utils.py           # 标准号分类（classify_std_code → "gb" 等）
│   ├── context.py / logger.py / project.py / settings_utils.py
│   └── notification_aggregator.py
```

## 关键机制

- **数据库迁移**：`Database.__init__` → `_run_migrations()` 按 `CURRENT_SCHEMA_VERSION`（当前 **65**）顺序执行未完成迁移；迁移函数注册于 `MIGRATIONS` 字典，执行结果（版本 + 校验和）写入 `_schema_version`；每次新增迁移需 `_constants.py` 版本号 +1 并同步本文件——**该同步自 2026-09-25 起由 G-031 强制**（`scripts/check_g_031_docs_sync.py` 的 `DOC_SYNC_MAP` 含 `pilotstd/core/` → 本文件；此前只有文档里的口头约定，没有门禁拦截）。新增迁移涉及 `CREATE INDEX` / `ALTER TABLE` 等结构操作时，先查 `sqlite_master` 确认表存在再执行（防御从旧版本跳跃升级场景，参考 v53/v59 实现）。**迁移校验和的三级语义**（2026-09-26 修正，技术债 #28）：`_schema_version.checksum` 存的是**标准化哈希**（`norm_checksum`，剥离注释/空行/行首缩进）；校验时 ① 存储值 == 标准化值 → **通过**（注释/空行变化不改变标准化值，故「只改注释」同样放行）；② 存储值 == **当前 raw 哈希**（历史 raw 口径、源码未变）→ WARNING + 自愈为标准值；③ 其余 → **抛 `DatabaseError` 阻断启动**（P-106「已执行迁移源码不可变」由此真正生效）。**不要**改回「当前源码 raw != norm 就自愈」：`norm_source()` 去缩进使任何带缩进函数恒有 raw != norm（实测 59/59），那会让第 ③ 条永不可达。**v60**（`_migrate_v60_drop_favorite_retry_columns.py`）是首个 `DROP COLUMN` 迁移：删 `user_favorites.archive_retry_count`/`last_archive_attempt` 两列死列（技术债 #16 残留，唯一读取方随 #16 旧响应键一并删除）。依赖 `DROP COLUMN` 需 SQLite ≥ 3.35（本地 3.50.4、容器基础镜像 `python:3.12-slim` 的 Debian 自带 libsqlite3 ≥ 3.40）；为防旧库无法删列时**阻断启动**，删列失败降级为告警日志（两列零读取方，留下只是 schema 未收敛）。**v62**（`_migrate_v62_notification_log_identity.py`，2026-10-02，通知架构重设计阶段 1a）给 `notification_log` 追加 4 个**通知身份**列：`message_id`（消息稳定 ID，回调据此定位渠道消息）、`correlation_id`（同一次业务运行的关联键）、`delivery_status`（**投递态** pending/sent/failed/suppressed/edited）、`ack_status`（回执态 none/delivered/read/acted）——全部 `NOT NULL DEFAULT` 且**不动既有 `status` 列**（那是**业务结果态** success/failure，两者语义不同，复用会让历史数据被误读）。新增迁移**只加列**、列取值来自 `NotificationMessage` 新字段默认值，故对既有 11 列的取值与全部调用点零行为变更；契约由 `tests/test_notification_stage1a_identity.py`（旧 11 列逐列相等 / 聚合搬运 / 补发白名单往返 / 迁移幂等）锁定。**v63**（`_migrate_v63_notification_log_task_view.py`，2026-10-02，阶段 1b）继续给 `notification_log` 追加 4 个**任务视角**列：`task_id`（关联 `task_queue.task_id`）、`notify_event`（三层模型的 7 类通知事件之一）、`content_type`（6 种内容类型之一）、`task_context`（任务上下文快照）。**`task_context` 的列类型选 `TEXT`（存 JSON 串）**，理由：① 本仓非标量落库一律走 TEXT + `json.dumps/loads`（如 `notification_queue.event_data`、`user_preferences.preference_value`），可复用同一编解码模块 `notification/_json_codec.py`；② SQLite 的 JSON1 扩展（`json_extract` 等）在旧库/精简构建上不保证存在，不依赖它；③ 该列只整存整取、不做 SQL 层查询，无需可索引的结构化列。**空值约定（显式）**：`{}`/`None`/空串/缺键在读回后**一律得到 `{}`，互不可区分**——唯一消费方是 dataclass 字段（默认值本就是 `{}`），引入"缺键哨兵"只会让调用方多写无收益的分支；该约定由契约测试钉死。**非法输入**（非 dict、非法 JSON、不可序列化对象）一律回退 `{}` 并记 warning，**绝不抛**——通知是旁路链路，格式异常不得吃掉整条通知。契约由 `tests/test_notification_stage1b_fields.py`（往返保真 / 空值不可区分 / 非法输入 / 聚合搬运 / 补发往返 / 迁移幂等，26 例）锁定。**v64**（`_migrate_v64_notification_log_interactive.py`，2026-10-02，阶段 1c）再追加 4 个**交互能力**列：`actions`（动作规格列表）、`callback_data`（**纯字符串**，≤64 字节，格式 `v1|<message_id:16>|<action:12>|<arg:32>`）、`attachments`（附件规格列表）、`channel_message_ids`（渠道名 → 渠道消息 ID）。**4 列同为 `TEXT`**（`callback_data` 本就是字符串；其余 3 列与 `task_context` 同款存 JSON 文本，理由同上）。新增模块 `notification/specs.py` 定义 `ActionSpec`/`AttachmentSpec`（均 `@dataclass(frozen=True)`）与闭集词表 `ACTIONS`（view_detail/open_logs/retry/ignore/snooze/mark_done）、`ACTION_STYLES`、`ATTACHMENT_KINDS`；`specs_to_jsonable()` 负责"规格对象 → 字典列表"（已解析过的 dict **原样透传**，保证往返幂等），配合 `_json_codec.dumps` 落库、`loads_list` 还原（**解码侧给纯 dict 列表，不重建 dataclass**——避免库中旧版本字段与当前 dataclass 不匹配导致构造失败吃掉整条通知）。**`ActionSpec.__hash__` 手写**：`frozen=True` 只阻止重新赋值，dataclass 自动 `__hash__` 仍会哈希全部字段，而 `args` 是 dict（不可哈希）会抛 `TypeError`；故哈希只取不可变字段（等于按动作身份哈希），`__eq__` 仍含 `args`。**`channel_message_ids` 的语义约定在此钉死**（阶段 3 编辑消息的前置）：键取自 `channel.py::CHANNEL_KEY_WHITELIST`（wechat/dingtalk/feishu/telegram，桌面与 Web 不计入——无句柄/无推送）、值恒为该渠道返回的消息 ID 字符串、**未投递的渠道用"键缺席"表达（不是 `None` 值）**、将来新增渠道须与本元组同批扩展（2026-10-03 步 A C1 起：白名单与 `_CHANNEL_CLASSES` 均由 `channel_spec.py` 声明派生，两者的互相比对已退化为同源验证，契约用例改为「spec 声明的实现类名 == `channels/` 源码中实际定义的渠道子类名」的跨层比对）。契约由 `tests/test_notification_stage1c_fields.py`（规格数据类型 / 落库形态 / "编解码是唯一转换路径" / 聚合深拷贝与重置 / 补发往返 / 渠道白名单 / 迁移幂等，29 例）锁定。**v65**（`_migrate_v65_notification_log_task_kind.py`，2026-10-02，阶段 2.5a）追加 `task_kind` 列（`TEXT NOT NULL DEFAULT ''`）——它是**标量**（不经 `_json_codec`，与 1a/1b/1c 的非标量列形成对照），值域为 `pilotstd/core/notification/mapping.py::TASK_KINDS`（九值业务域名词）。**双 SSOT 约定**：`task_kind` 是**通知视角**的 SSOT（"用户交办的是哪类事"），`task_type` 是**执行队列视角**的 SSOT（"哪个任务在跑"，值域 `pilotstd/task/models.py::TaskType`）；两者不同轴（实测交集仅 scan/query/organize），由 `mapping.task_kind_to_task_type()` 做**单向翻译**（无反向函数，避免"一对多需要猜"的后门）。契约由 `tests/test_notification_stage1b_fields.py` 与 `tests/test_notification_stage2b_wiring.py::TestTaskKindPersisted`（表驱动：41 事件 × 期望 `task_kind` 落库正确性）锁定。
- **配置**：点分隔键（如 `network.timeout`）持久化到 JSON，写时原子替换；frozen 环境下目录回退到 `%APPDATA%/PilotStd`。**写盘语义（#31-P2 / R14-3a，2026-10-01）**：`ConfigManager.__init__ → _load()` **仅在①文件不存在（首次运行）②补默认值/迁移旧键实际改动了内存态** 时写盘；已存在且内容完整的配置**构造后零写盘**；`set()` 只改内存，需显式 `save()` 才落盘；损坏文件仍先备份 `config.json.corrupted.<ts>` 再以默认值初始化并写盘。**动机与量化**：原实现无条件 `save()`＝“每构造一次 = 读一次 + 写一次”，而热路径 `query/routing/scorer.py::get_profile()` 每次新建实例 → 单批查询实测 **save() 135 次／get_profile 577 ms**（≈519 KiB 无谓覆盖写）；修复后 **save() 2 次／153 ms**，同时大幅收窄“多实例 last-writer-wins 覆盖用户刚改配置”的窗口。契约由 `tests/unit/core/config/test_manager_dirty.py`（7 例：首建写盘／完整则零写盘／补默认值写一次／旧键迁移写一次／set+save 持久化／损坏备份／reload 零写盘）锁定。**下载节奏参数** `download.batch_size / long_rest / max_workers / max_retries / min_delay / max_delay` 由 facade 构造 `DownloadEngine`/`SessionManager` 时读取，手动批量下载与收藏下载链共用同一口径（暂不暴露 Web/Win 界面）。**定时任务键** `tasks.*_enabled` + `tasks.*_cron` 是三方一致契约：`settings_schema.py`（登记）↔ `docker/api/settings.py::_SCHEDULED_JOBS`（读写成对 + 保存时重排）↔ `docker/scheduler.py::start_scheduler()`（启动时注册），任一环漏项都会表现为"设置页改了不生效"（TD-20）。 **共享实例与失效通知数据流（#31-P1 / R14-3b，2026-10-01）**：`manager.get_shared_config(path=None)` 按**绝对路径**缓存 ConfigManager 实例（`_SHARED_INSTANCES`），热路径 `query/routing/scorer.py::get_profile()`、站点配置 `query/site_config/_loader.py`、统一访问层 `ConfigService` 均从它取实例（原先各自新建）。**失效链**：`ConfigManager.save()` 原子写盘成功后 → `_publish_config_written(self)` → ① 若缓存中的实例**不是写入者**（GUI 设置页 `ui/core/handlers/_settings*.py`／Web `docker/api/settings.py` 各持独立实例）→ 从缓存移除（陈旧）；② 无论哪种情况都同步回调 `_INVALIDATION_LISTENERS`（参数＝配置绝对路径）→ 站点配置模块的清缓存回调把 `_site_config_cache` 置 None → 下次读取重建即拿到新值。`invalidate_shared_config(path)` 供“外部改动配置文件”的场景显式失效。**明确不用基于时间的静默 TTL**（会掩盖“配置已改但读不到”的 bug）；`_SHARED_LOCK` 为**可重入锁**——首次运行会在 `_load()` 内写盘并发布通知（同线程重入），重入锁同时保证同一路径并发首次获取只产生一个实例。契约由 `tests/unit/core/config/test_manager_shared.py`（8 例）与 `tests/unit/query/routing/test_scorer_hot_path_config.py`（4 例：热路径构造 ≤2／稳态 0 构造／GUI 写盘后热路径读到新值／站点缓存被清）锁定。 **状态值字典（#32-A / R14-4a，2026-10-01）**：`core/status.py` 是状态值的**权威字典**——`Status` 枚举的 value 与现网中文字符串**逐字一致**（零行为变化，API/DB/前端比较全部兼容）；`STATUS_I18N_KEYS` / `STATUS_EN_KEYS` 为 B/C 阶段「后端英文枚举 + 前端 enum→i18n key」预留映射脚手架；`normalize_status()` 提供 `废止` → `已废止` 别名归一；命名集合（`ABOLISHED_STATUSES` / `ABOLISHED_STATUSES_WITH_EXPIRED` / `EXPIRED_STATUSES` / `NON_OVERRIDABLE_STATUSES` / `API_VALID_STATUSES`）收敛了原先散落在 9 处的容器定义（`manager/classifier.py`、`manager/facade/_organize.py|_query.py|_query_subsystem.py`、`organizer/mover.py`、`core/notification/_format_utils.py`、`ui/core/handlers/auto_flow_engine.py|query_flow_engine.py`、`docker/api/standards.py`），**取值集合与重构前逐一等价**（`tests/unit/core/test_status.py` 断言 4/5/3/含待确认/API-tuple 五种口径）。**本阶段不替换业务字面量**（B 阶段）、不改 DB 迁移脚本、不改 API 返回字符串。**R15 再保险（2026-10-01，随 T-35 观察项）**：`ConfigManager.save()` 在 `os.replace` **之前**把现有文件复制为 `config.json.bak`（失败不阻断写盘），`_load()` 解析失败时**优先**从该备份回滚（成功即 `save()` 回写并告警；备份不可用才退化为原有的「备份 `.corrupted.<ts>` + 默认值初始化」路径）——即在**不引入跨进程文件锁**的前提下，把"并发写丢一次配置"的恢复成本压到接近 0。**R15 补记（2026-10-01）**：`validity_checker.py::register_new_standard` 的 `INSERT` 原把状态写成 SQL 文本里的 `'未知'` （AST 口径的收敛覆盖不到），已改为占位符参数 `Status.UNKNOWN.value` —— 至此 `pilotstd/` 内**再无内嵌状态字面量**。**B 阶段（R14-4b，2026-10-01）起**：`pilotstd/core/**`（`validity_checker.py`／`file_index.py`／`_file_index_query.py`／`_validity_pipeline.py`）内的状态字面量已改引 `Status.*.value`（零行为变化、逐处等价）；同一收敛按域分批推进（query → manager → ui → docker）。**C 阶段（R14-4c，2026-10-01）**：状态字典成为**API 契约来源**——`status_key(value)` 把数据值映射为稳定英文键（active/upcoming/withdrawn/superseded/voided/expired/pending/unknown，未知回退 `unknown`），`resolve_status_filter(raw)` 让过滤入参**同时接受英文键与历史中文值**（老书签/旧前端不受影响）；`/api/standards/status`、`/api/query/results`、`/api/pending/requery` 的每条记录在原有中文 `status` 之外新增 `status_key`（**向后兼容**），前端据此做与界面语言无关的比较（原 13 处中文比较的 `i18n-allow` 豁免全部消除）。**v61 迁移（同批）**：`_migrate_v61_enum_status_defaults.py` 把 `file_index.status` / `standard_validity.status` 的**列默认值**收敛到字典（`Status.ACTIVE.value` / `Status.UNKNOWN.value`）——默认值已等于枚举值时**不重建表**（现网库全部命中，零数据搬动）；仅当出现漂移才走 SQLite 12 步重建修复并保留数据与索引；`CURRENT_SCHEMA_VERSION` 随之 60 → **61**。遵守 P-106：不改动 v2/v3/v16 等历史迁移源码。
- **主题分组 i18n 契约（2026-09-26 专项）**：`core/notification_aggregator.py::_extract_topic` 原用**简体中文关键词**猜测主题，致 `失败`(zh_CN) 命中而 `失敗`(zh_TW) 不命中、英文标题全不命中，其余落「标题前 8 字符 + `_`」兜底 → **同一事件在不同语言下归入不同分组、跨语言完全不合并**（实测 39 事件 × 3 语言 **65 条**落兜底）。修法改为 i18n 契约驱动：扫三语语言包取 `notification.*` 下全部 `.title*` 键（47 键，实测 39/39 可映射到事件），建「标题 → 主题」精确索引 + **6 条模板正则**（覆盖 `第 {round} 轮…` 这类裸值占位符），标题含动态计数时先剔成对括号再匹配；原简体关键词表保留为**第 4 层回退**（自定义标题向后兼容）。`_TOPIC_BY_EVENT` 显式给出 39 事件 → 11 主题的映射，主题名沿用既有词汇故桌面分组语义不变。**终检**：276 条渲染样本落兜底 **0**、跨语言不一致 **0**；契约由 `tests/test_notification_aggregator_topic_i18n.py`（20 例）锁定。同批确认 **`_BUFFER_WINDOW = 0.3s` 设计意图正确、不变更**——它是桌面 toast 合并窗口，与服务端 `DEFAULT_WINDOW_SECONDS = 5.0s` 分属两条独立链路，不对齐是有意为之。
- **聚合续期时序（2026-09-26 专项）**：`notification/aggregate_buffer.py::_on_timer` 的续期由「固定完整窗口」改为「`min(窗口, 到 MAX_WINDOW_SECONDS 的剩余时间)`」，剩余不足 `min(窗口×0.1, 0.05)` 时直接强制发送；阈值随窗口缩放而非固定值——固定 0.1s 在小窗口（测试用 0.05s）下会大于窗口本身，导致提前发送失去精度意义。**缺陷上界**：原实现用 `elapsed < MAX_WINDOW_SECONDS` 判定，该条件只保证"下一次续期会超时"，而那次续期可能跨过上界**最多一个窗口 w** → 越界上界为 `MAX + w`（生产 `w=5s/MAX=300s` 即 305s）。**实测判别**：`window=0.2s/max=0.3s` 时旧实现强制发送于 409ms（上界 300ms，越界 109ms），新实现落在界内；`tests/test_scheduler_timer_drift.py`（14 例，含上界守卫/续期次数/慢发送不阻塞 enqueue/无忙等待/并发不丢不重/故障恢复/极小窗口）对该比例 1 FAIL 其余 pass。**同批改进**：原早退路径在 `with self._lock` **内**调用 `_send_merged`（满窗路径在锁外）——两条发送路径现统一移到锁外，网络 IO 不再阻塞其它分组的 `enqueue`。**新增观测**：强制发送时告警记录"实际耗时 / 上界 / 偏差 ms"，续期时调试记录"下次触发时刻"。**过程更正**：专项分析前两次各错一次（先断言必然越界一个完整窗口——`w` 整除 `MAX` 时其实不越界；再由该整除特例错误推广为"永不越界"），最终结论以多比例实测为准；此更正已记入 `notification_coverage.md` §六。
- **i18n 语言状态执行上下文安全（2026-09-26 专项）**：`i18n/__init__.py` 的当前语言由模块级全局 `_lang`/`_current` 改为 `contextvars.ContextVar`（`_lang_var`，默认值即 `DEFAULT_LANGUAGE = "zh_CN"`）。**修复的缺陷**：原实现下任意线程调用 `set_language()` 会改写**所有**线程看到的语言，而 `t()` 的调用方（通知构建器 `_builders_*.py`、渲染器 `renderer.py`、聚合器 `aggregate_buffer.py`）都在 `ThreadPoolExecutor`（6 文件）与 `asyncio`（8 文件）中执行，会渲染出错误语言的文案。**选型**：不用 `threading.local()`（asyncio 下同一线程多任务共享，不安全）；不加锁（锁无法表达"同一线程内嵌套切换"，且给热路径加锁引入无谓竞争）；不再缓存翻译映射（`_translations[lang]` 是 O(1) 字典取值，缓存副本会让"语言"与"映射"两份状态可能不一致）。**API**：`set_language`/`get_language`/`t`/`_` 签名不变；新增 `language()` 上下文管理器（基于 `ContextVar.set()` 返回的 token，嵌套与异常路径均精确恢复）、`SUPPORTED_LANGUAGES`、`DEFAULT_LANGUAGE`。**兜底**：非法语言码回退 `DEFAULT_LANGUAGE` 并告警（不静默接受——未知语言会让 `_translations.get(lang, {})` 取到空表，进而使 `t()` 全量返回键名，比回退更难排查）；`get_language()` 永不返回 None。**行为变更（有意）**：子线程/子任务不继承其它线程设过的值，一律从默认语言开始（原全局语义下"工作线程跟随最后设置者"是竞态而非特性）；`asyncio.create_task` 仍按 contextvars 语义继承创建时的上下文。**性能**：同口径实测每次翻译 +0.096 µs（0.182 → 0.278 µs），单条通知典型 3–6 次 `t()` 调用故额外开销 ~0.6 µs，相对该通知的网络耗时（10^5 µs 量级）可忽略；`t()`/`_()` 内联 `_lang_var.get()` 以免多套一层函数调用（实测会让每次翻译近倍增至 ~0.32 µs）。契约由 `tests/test_i18n_thread_safety.py`（17 例：多线程竞争/线程池/嵌套切换/异步隔离/兜底）锁定。
- **登录失败安全告警（2026-09-26，第 8 批 P0 事件）**：事件 `security_login_failed`（构建器 `_build_security_login_failed_message`，载荷 `from_ip`/`failures`/`window_seconds`/`username`，level=warning）。触发点在 `docker/auth.py::login` 的失败分支，经 `_notify_login_failure()` → `write_audit(action="LOGIN_FAILED")` + `NotificationManager.send_event`。**阈值门控**：`LOGIN_FAILURE_ALERT_THRESHOLD = 5`，与限流闸门 `MAX_ATTEMPTS = 100` **故意解耦**（后者为压测放宽，作告警阈值几乎不会触发）；按 IP 在 `LOCKOUT_SECONDS` 窗口内累计，且**只在恰好达到阈值时发一次**（继续失败不刷屏；登录成功 `clear_login_failures` 清空后可再次触发）。**未认证路径**：`send_event` 之外显式传 `user_id=None` 写审计（`audit_logs` 允许 NULL，v45 迁移口径）；告警/审计任何异常都不得改变 401 响应语义。**审计与文案均不含密码**。事件同时满足 e2e 契约的四个断言（注册/构建器/触发点/字段双向一致），故不在 `SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED` 豁免集内。同批把 `POST /api/login` 纳入 G-043 敏感端点清单，并把门禁扫描范围扩到 `docker/auth.py`。契约由 `tests/test_security_login_failed.py`（11 例）锁定。
- **列表字段名 i18n（2026-09-26，第 6 批）**：`notification/renderer.py` 新增 `_field_label()` 与 `_LIST_FIELD_KEYS` 映射，把 `ListBlock.items` 的**数据字段名**翻译为展示文本。**修复的缺陷**：`FeishuCardRenderer._render_list` 原实现取 `block.items[0].keys()` 原样作表头（`header_cells = [... f"**{k}**"]`），中文用户在飞书卡片表格里看到 `number` / `name` 这类英文数据键；`BlockRenderer._render_list`（纯文本基类）同理渲染出 `number: GB/T 1-2024`。字段名 → i18n 键：`notification.renderer.field.{number,name,status,detail,path,reason}`；未登记或翻译缺失时回退为通用占位 `notification.renderer.field.unknown`（「字段」/「欄位」/「Field」），**绝不回退为原始键名**——暴露内部字段名正是本批要消除的问题。**只翻译字段名，行数据原样保留**；调用期取 `t()`，故 `set_language` 后表头随之变化。契约由 `tests/test_notification_renderer.py::TestListFieldLabelI18n`（5 例）锁定。注：`TelegramRenderer._render_list` 早已只显示值（丢弃键名），无需修改；`DesktopRenderer` 的 `f"{key}：{value}"` 同属此类问题，但本批范围限飞书表头，未纳入。
- **通知聚合/去重职责边界（2026-09-26，第 4 批：职责固化）**：项目内有**三套**名字相近但层次不同的机制，此前边界模糊，现于代码注释与本表固化，**禁止越界**：

  | 层次 | 组件 | 唯一职责 | 明确不做 |
  |------|------|---------|---------|
  | L1 服务端聚合 | `notification/aggregate_buffer.NotificationAggregator` | 时间窗口聚合：按「事件类型 × 关联实体」累积，窗口/数量双触发，生成摘要后投递 | 不做消息格式化（→ `renderer.py`）、渠道路由与发送（→ `manager._send_now` / `channels/`）、静音时段判断（→ `manager._is_quiet_hours`）、桌面去重；**不派生** `target_id` |
  | L2 桌面协调 | `core/notification_aggregator.NotificationAggregator`（单例） | 桌面托盘的暂停/恢复、自动暂停触发（30s 内 3 条警告/错误 → 暂停 5 分钟）、暂停状态持久化、桥接 L1 | 不自己合并消息（委托 L1）；`_extract_topic` 把标题映射为主题串作为 `target_id`，是桌面链路的实体标识来源 |
  | L3 瞬时防抖 | `platform/notify.py:_check_dedup` | 3 秒内**同标题字面相同**的托盘气泡丢弃（防重绘） | 不做主题分组、不合并内容 |

  **关键事实（易误判）**：① L2 与 L3 是**独立链路、不共享状态**——L1 服务 `manager.send_event` 触发的服务端通知（Web / Webhook / 定时任务），L2 服务 `platform/notify.py` 触发的桌面托盘通知，两者仅通过"L2 持有 L1 实例并委托 `push()`"相连；② L3 与 L2 **在调用路径上互斥**：`NotifyService.show/show_warning` 在 `auto_pause_enabled` 为假时走 `_check_dedup` + 立即显示，为真时走 `should_show()` → L1（0.3 秒窗口合并），同一时刻只有一条生效；③ `_do_send` 只做"是否聚合"的分支决策，合并逻辑全部委托 L1。渠道层（`channels/`）**没有任何消息合并逻辑**——钉钉的 URL 加签是签名计算，与布局无关。
- **通知渠道异常处理（2026-09-26）**：`notification/channels/{dingtalk,feishu,wechat}.py` 的错误响应体读取分支（`except Exception: pass`）统一为「记录 `read_exc` + 以 `<body 读取失败: ...>` 标记回填 `body` + `logger.debug`」，三个渠道的外层 `logger.warning` 统一补 `exc_info=True`。**动机**：原 `pass` 使"服务端未返回 body"与"body 读取失败"两种情形在日志里不可区分（都表现为 `body=`），且外层告警丢异常栈。捕获本身**不是**吞错——外层已设置 `last_error`、记录告警并 `return False`，故内层只影响诊断文本丰富度。全链路审计脚本的吞错计数由此从 3 归零（`scripts/audit_notification_chain.py --scope notification`）。
- **聚合分组键（2026-09-26，第 3 批：target_id 分组修复）**：`notification/aggregate_buffer.py` 的缓冲键由「仅事件类型」改为「**事件类型 × 关联实体**」——`_group_key()` 用 US 分隔符（`\x1f`）拼接 `event_type` 与 `target_id`，`_events_in_group()` / `_group_entity()` 负责还原，使 `_on_timer` / `flush` / `shutdown` 的发送都能取回真实事件类型。**修复的缺陷**：`channel.py` 的 `target_id` 字段注释承诺"同 event_type 下按 target_id 分组"，且 `manager.py` 一路透传该字段，但 `enqueue` 只按 `msg.event_type` 建键——不同业务对象（不同任务、不同标准）的通知被合并进同一条"聚合通知（N 条）"，用户无法分辨各自结果。`target_id` 缺失（空串或纯空白）时回退为纯事件类型分组（同类仍聚合，绝不把不同实体混为一组）。**同批对齐三处默认值不一致**：`notification.aggregate_enabled` 的 manager 回退值 `False` → `True`（与 `defaults.py:79` 及 `events.py` 的"所有事件均经聚合器"声明一致；原回退值会让缺该键的旧配置静默关闭聚合）；`DEFAULT_WINDOW_SECONDS` 60 → 5、`DEFAULT_BATCH_SIZE` 20 → 50（与 `defaults.py` 的 `aggregate_window_seconds` / `aggregate_max_events` 同口径，避免"直接构造聚合器"与生产行为分叉；生产路径由 manager 显式传值，故这两个常量只在测试/独立调用时生效）。契约由 `tests/test_aggregate_buffer.py::TestGroupKeyUsesTargetId`（6 例）锁定；原 `test_same_event_type_merged_after_shutdown` 断言的正是缺陷行为（合并成 1 条 / count=5），已改写为 `test_different_target_ids_not_merged_after_shutdown`（2 条 / count={2,3}）。**未修（预存）**：`_on_timer` 在未达 `MAX_WINDOW_SECONDS` 时"发送当前缓冲并续期"，意味着每过一个窗口都可能发一条，最长延迟可能超过 300s 一个窗口——属预存问题，另排工单。
- **安全告警投递（2026-09-26，第 2 批安全审计闭环）**：新增 `notification/security_notifier.py`。**它绝不调用 `NotificationManager.send_event`**——凭证类告警必须在"新凭证落库之前"送达**旧**渠道，而 manager 路径的三重延迟会让告警流向攻击者控制的新地址：① 聚合缓冲（`notification.aggregate_enabled` 默认 True）只入队，实际发送推迟到窗口到期；② 静音时段命中时写入 `notification_queue` 表延后补发；③ `send_event` 首行受 `notification.enabled`（默认 False）门控。故该模块按"指定用户"读旧凭证 → 构造**临时渠道实例** → `concurrent.futures` 并发同步 `send()`（总超时 5s 封顶）→ 才允许调用方落库。三个新事件（`notification_credential_changed` / `security_password_changed` / `security_token_refreshed`）仍登记于 `events.py` 并配 `_builders_system.py` 构建器，但**有意豁免** `tests/test_notification_e2e.py` 的"必须有 send_event 触发点"契约（见该文件 `SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED`），投递正确性由 `tests/test_p0_security_endpoints.py` 锁定（含"send 必须先于 set_channel"的顺序断言）。紧急降级开关是**环境变量** `PILOTSTD_SECURITY_NOTIFY_ENABLED` 而非配置文件——凭证变更端点自身能写配置，放配置里等于给攻击者一个关闭告警的把手。`client_ip(request)` 对测试替身做类型校验（`MagicMock` 的任意属性都返回 Mock，直接入审计 detail 会让 `json.dumps` 崩溃）。
- **通知**：事件驱动 → 渠道独立适配（企业微信/飞书/钉钉/Telegram），支持聚合缓冲与桌面格式化。模板文案统一走 i18n 层级键且**在调用期取 `t()`**（模块级求值会把语言固化在 import 时刻，运行时切换语言失效）；状态类判定使用数据口径（`_format_utils.is_abolished_status`），**禁止拿展示文案参与逻辑比较**（en/zh_TW 下 `t(...)` 与数据中的中文状态永不相等）；渲染层 / 聚合层 / 桌面层 / 渠道层的用户可见文案亦已外置为 `notification.renderer.*`、`notification.aggregated.body.*`、`notification.desktop.level.*`、`notification.channel.*`、`notification.channel_test.*`、`notification.manager.*` 键族；发送层不再追加标准号（与 telegram 同口径 `57f58a6c`，避免与构建器渲染重复）。构建器按「语义阶段」分文件（2026-09-26 G-010 治理）：`_builders_batch.py` 只留下载/收藏/批次类，`_builders_task_results.py` 承接扫描/查询/归档/规范化/状态迁移/公告抓取类——两者**无共享模块级符号**（AST 实测），故拆分不产生反向依赖；调用方一律经 `_message_builders.py` 重导出，增删构建器文件不需要改管理器。管理器本体同轮拆出 `_manager_ops.py`（写发送日志 / 日志分页查询 / 已读标记 / 未读计数 / 过期清理）：这 5 个方法只依赖数据库连接，与「事件 → 渠道分发」主流程无共享局部状态。**采用组合而非继承**——`tests/test_architecture_mixin_guard.py` 明令除 `_WindowLifecycleMixin`（Qt 硬约束）外禁止新增 Mixin，并指定 Composition（ADR-010）；第一版为换取“调用点零改动”用了 Mixin，被该守护测试拦下后改为 `self.ops = NotificationOps(self)`，对外接口相应改为 `mgr.ops.get_logs(...)` 等（`docker/api/notification.py`、`docker/scheduler.py`、测试已同步）。ops 持有宿主引用而不是拷贝 `_db`：只有调用期读取才与拆分前各方法体逐字节不变的语义一致。**WebSocket 广播已彻底移除（阶段 0，2026-10-02）**：原 `NotificationManager.__init__` 的 `ws_broadcast` 形参、`self._ws_broadcast` 属性、`_send_now` 尾部的 `_broadcast_to_ws` 调用与 `_manager_ops.broadcast_to_ws` 方法全部删除——生产唯一构造点（`pilotstd/manager/facade/_base.py:250/:271`）从未传该回调，故 `_ws_broadcast` 恒为 `None`、广播线程永不创建（服务端实现已于 `1784ecbe` 删除）。Web 端通知改为 **30 秒轮询 `GET /api/notification/logs`**（`web/src/composables/useNotification.ts`，含页面隐藏时暂停）。设计方案见 [通知架构重设计](../../plans/notification-redesign/06-阶段0-1实施方案.md)。
