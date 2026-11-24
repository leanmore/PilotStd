# P1-6 企微 vs TG 通知信息量对齐摸底（通知模板对照表）

| 项目 | 值 |
|------|-----|
| 任务包 | P1-6「企微 vs TG 通知信息量对齐」摸底 |
| 日期 | 2026-11-24 |
| 性质 | **只读摸底**；不改代码 / 配置 / 其他文档，不 commit |
| 探针脚本 | `C:\Temp\p1_render_probe.py`（真实构建器 × 四渠道真实渲染器，44 事件全量）、`C:\Temp\p1_notify_prod_probe3.py`（生产只读日志）、`C:\Temp\p1_prod_sql.py` / `p1_prod_sql2.py`、`p1_prod_channels.py`、`p1_prod_policy.py`、`p1_prod_diag.py`（生产只读 GET / SELECT） |
| 样本规模 | 事件 44/44 全量渲染；生产通知日志 2608 行中取最近 100 行 + 业务事件名全量分布 + 7 条 `actions` 诊断 + 策略/渠道配置 |
| 结论一句话 | **模板层 43 个适用事件中 37 个满足「动作+对象+结果」，6 个不满足（5 缺对象、1 缺结果）**；**渠道层真正的信息量差在企微应用形态（模板卡片）——34/44 个事件的卡片正文比 TG 少至少一个核心字段（级别 27、详情链接 7、列表计数/完整列表链接 5，含重叠）**；另发现 **TG 反向缺口：`auto_backup` 成功通知在 TG 渲染期抛 `TypeError` 导致整条丢失（生产 log id=2034 实证）**。 |

> **已查阅（文档依据，非记忆）**
> - `docs/governance/notification_coverage.md` §二 覆盖度矩阵、§一-B 渠道派生一致性（41 事件基线，已落后于代码 44）
> - `docs/notification_event_dictionary.md` 全量事件字典（32 事件，Q20 旧版，含已合并的 `standard_expired`）
> - `docs/reference/notification-field-contract.md` §一（`NotificationMessage` 字段/动作白名单）、§二 源码位置
> - `docs/reference/notification-user-guide.md` §二（四层模板结构与"各渠道为什么不一样"）
> - `docs/analysis/2026-11-21-notification-channel-analysis.md` §2 渠道清单、§3.2 四渠道表达差异（**该文部分结论已被 2026-11-21 的 D-2 提交 `3d4fbc09` 推翻，见 §2.3 注**）
> - `docs/onboarding/08-known-boundaries.md` #16（重试覆盖）、#18（铃铛渠道重复）、#9（聚合现状）、#29（配置空白容错）
> - `docs/architecture/modules/core.md` 通知子系统段
>
> **实测证据**：生产 `http://192.168.1.18:9028`（`/api/health` version=`0e92e5d2…`、schema 76；`git diff 0e92e5d2..HEAD -- pilotstd/core/notification` 为空 ⇒ **生产与本地的通知子系统源码一致**）。本地构建器+渲染器实跑产物见 `C:\Temp\p1_render_samples.{json,md}`、`p1_render_facts.json`。

---

## 0. 结论摘要（先看这里）

1. **事件全集 44 个**（`pilotstd/core/notification/events.py:94-142` 的 `ALL_EVENTS`），与事件规格 44 条一一对应（`event_spec.py:126` 断言）。文档仍写 41（`notification_coverage.md:31`）、32（事件字典）、41（用户指南）——**文档数量滞后，本报告以代码 44 为准**。
2. **「动作+对象+结果」判据**：严格满足 **37/43**（排除 1 个不适用；37 里含 3 个"弱项"，仍建议修补）；**6 个不满足**——缺对象 5 个（`scan_empty`、`query_empty`、`archive_failed`、`normalize_failed`、`auto_pipeline_summary`）、缺结果 1 个（`download_started`）；另 3 个为"弱项"（`validity_system_failed` 弱对象、`security_token_refreshed` 弱对象、`security_password_changed` 弱结果）。**无事件缺「动作」**（标题/正文都表达了动作）。
3. **企微真正的信息量差集中在"应用形态（模板卡片）"这条路径**：`WeChatCardRenderer.render_card()` 只消费 `blocks`，**不渲染级别前缀、不渲染 `message.link`、ListBlock 丢「共 N 条」与 `detail_url`**。受影响的不是几个事件，而是 **34/44** 个事件至少丢一个核心字段：
   - 级别不可见：**27** 个 warning/error 事件；
   - 详情链接不可见：**7** 个带 `message.link` 的事件；
   - 列表计数/完整列表链接不可见：**5** 个用 ListBlock 的事件（与上面有重叠）。
   企微 **Webhook 形态（markdown）与 TG 基本对齐**（同一 `BlockRenderer.render()` 骨架：级别前缀、详情行、markdown 链接齐全），只有分片口径（2048 字节 vs 4096 字符）与列表符号差异。
4. **反向缺口（TG 少于企微）**：`auto_backup` 成功通知把 float `size_mb` 直接塞进 `KeyValueBlock.value`，TG 渲染器 `_escape(value)` 抛 `TypeError` → **TG 整条收不到，企微正常**。生产日志已留下 1 条实证失败：`id=2034 / telegram / "expected string or bytes-like object, got 'float'" / 2026-10-26`。
5. **生产实际配置**（只读接口核对）：企微 = **应用形态**（`corpid`/`agentid`/`corpsecret` 齐、`webhook_url` 空 ⇒ 走 `template_card`）；TG 已启用。生产策略：**企微按"类别层"10 类全开**，**TG 按逐事件显式订阅 36 个** ⇒ 事件覆盖面 企微 **≥** TG（TG 未订阅 8 个，其中 7 个企微能收到），但**单条信息量** 企微 < TG（卡片丢字段）。
6. **不适用 / 隐藏**（按用户判据，不要求对齐）：交互型回调按钮（retry/ignore/snooze/mark_done，全库无生产者 + 企微 `supports_buttons=False`）、图片/附件（四渠道均未实现发送）、`desktop_toast`（平台层桌面回显，不经 `send_event`）、`standard_expired`（已合并进 `standard_status_changed`，仅剩废弃常量）、企微 Webhook 形态的按钮能力（markdown 无按钮）。

---

## 1. 事件全集（44）+ 数据来源

### 1.1 数据来源（读取顺序与权威性）

| # | 数据源 | 位置 | 读到的内容 | 权威性 |
|---|--------|------|-----------|--------|
| 1 | 事件注册表 | `pilotstd/core/notification/events.py:94-142` | `ALL_EVENTS` = **44** 个 `EventDef`；`ALL_EVENT_KEYS`/`BYPASS_EVENTS` 派生（`:146-148`） | **SSOT** |
| 2 | 事件规格 | `pilotstd/core/notification/event_spec_data.py:20-549` | 44 条 `EventSpec`（触发文件/构建器/默认渠道/级别/类别/载荷键/是否可订阅） | **SSOT**；`event_spec.py:126` 断言与注册表一一对应 |
| 3 | 通知类别（10 类） | `pilotstd/core/notification/mapping.py:61-72` | `task_progress`/`task_result`/`task_failure`/`user_activity`/`batch_summary`/`anomaly_alert`/`security_alert`/`schedule_reminder`/`system_health`/`manual_test` | 派生自规格（`mapping.py:163-165`） |
| 4 | 构建器注册 | `pilotstd/core/notification/manager.py:412-416` + `_message_builders.py` | `{事件: 构建器}` 由规格派生，构建器实际实现见 `_builders_validity.py` / `_builders_batch.py` / `_builders_batch_download.py` / `_builders_task_results.py` / `_builders_system.py` / `_builders_system_security.py` | 运行时唯一入口 |
| 5 | 桌面主题映射 | `pilotstd/core/topic_index_data.json:3-44`（`topic_by_event`，44 条）+ `_topic_index.py:28` | 事件→桌面聚合主题（done/error/validity/…） | 桌面链路专用，**不是事件清单**（只是恰好也是 44 条） |
| 6 | 生产实发 | 只读 `GET /api/notification/logs`、`GET /api/notification/policy`、`GET /api/notification/channels`、`GET /api/notification/config`、只读 `SELECT … FROM notification_log` | 2608 行日志；当前订阅/渠道形态 | 生产证据（只读） |
| 7 | 文档（对照用） | 见页首"已查阅" | 文档数量与结构（部分滞后） | **非权威**，只用于发现漂移 |

**文档漂移清单（本次实测）**：

| 文档 | 写的 | 实际 | 影响 |
|------|------|------|------|
| `docs/governance/notification_coverage.md:31`、`:83` | 41 事件（正文另有"41 事件 × 4 维度"、L-22 已改 42） | **44** | 新增 `task_progress`/`desktop_toast`/`auto_pipeline_summary` 未进基线 |
| `docs/notification_event_dictionary.md` | 32 事件（Q20 Final） | 44，且含**不存在**的 `standard_expired`、`trust_ip_update` 归错分组（用户交互） | 字典整体过期 |
| `docs/reference/notification-user-guide.md:11`、`:274`、`:384` | 41 事件、12 类 | 44 | 用户文档过期 |
| `docs/reference/notification-user-guide.md:271` | Telegram 用"HTML 方言" | 实际 **MarkdownV2**（`channels/telegram.py:109`） | 文档错误 |
| `docs/reference/notification-user-guide.md:267` | "系统只产出内容…各渠道只是翻译员" | 企微卡片**不是**等价翻译：级别/链接/列表计数被丢（见 §2） | 文档结论不成立 |

### 1.2 事件清单（44 条，代码为准）

> 默认渠道 `-` = 出厂无默认订阅（`event_spec_data.py` 中 `default_channels=()`，`defaults.py:101` 不为它生成 `notification.rules.*`）；生产订阅见 §1.3。

| # | 事件 | 模块 | 触发点（`trigger_file`） | 构建器 | 出厂默认渠道 | 可能级别 | 通知类别 |
|---|------|------|------------------------|--------|:---:|:---:|---------|
| 1 | `standard_status_changed` | validity | `pilotstd/core/validity_checker.py` | `_build_standard_status_changed_message` | wechat | info/warning/error | schedule_reminder |
| 2 | `standard_first_registered` | validity | `pilotstd/core/validity_checker.py` | `_build_standard_first_registered_message` | – | info | task_result |
| 3 | `validity_batch_report` | validity | `pilotstd/core/_validity_pipeline.py` | `_build_validity_batch_report_message` | wechat | info/warning | batch_summary |
| 4 | `validity_round_summary` | validity | `pilotstd/core/_validity_pipeline.py` | `_build_validity_round_summary_message` | wechat | info | batch_summary |
| 5 | `validity_standard_failed` | validity | `pilotstd/core/_validity_pipeline.py` | `_build_validity_standard_failed_message` | wechat | error | anomaly_alert |
| 6 | `validity_system_failed` | validity | `pilotstd/core/_validity_pipeline.py` | `_build_validity_system_failed_message` | wechat | error | anomaly_alert |
| 7 | `date_reminder` | interaction | `pilotstd/tasks/date_reminder.py` | `_build_date_reminder_message` | wechat | info | schedule_reminder |
| 8 | `scan_complete` | scan | `pilotstd/manager/facade/_scan.py` | `_build_scan_complete_message` | – | info/warning | task_result |
| 9 | `scan_empty` | scan | `pilotstd/manager/facade/_scan.py` | `_build_scan_empty_message` | – | info | task_result |
| 10 | `auto_scan_failed` | scan | `pilotstd/manager/facade/_scan.py` | `_build_auto_scan_failed_message` | wechat | error | batch_summary |
| 11 | `batch_query_summary` | query | `pilotstd/manager/facade/_query_subsystem.py` | `_build_batch_query_summary_message` | – | info/warning | batch_summary |
| 12 | `query_failed` | query | `pilotstd/manager/facade/_query_subsystem.py` | `_build_query_failed_message` | – | error | task_failure |
| 13 | `query_empty` | query | `pilotstd/manager/facade/_query_subsystem.py` | `_build_query_empty_message` | – | warning | batch_summary |
| 14 | `batch_download_complete` | download | `pilotstd/download/engine.py` | `_build_batch_download_complete_message` | wechat | info/warning | batch_summary |
| 15 | `download_failed` | download | `pilotstd/tasks/favorite_download.py` | `_build_download_failed_message` | – | error | task_failure |
| 16 | `normalize_complete` | normalize | `pilotstd/manager/facade/_organize.py` | `_build_normalize_complete_message` | – | info | batch_summary |
| 17 | `normalize_failed` | normalize | `pilotstd/manager/facade/_organize.py` | `_build_normalize_failed_message` | – | error | task_failure |
| 18 | `archive_complete` | archive | `pilotstd/manager/facade/_organize.py` | `_build_archive_complete_message` | wechat | info | batch_summary |
| 19 | `archive_failed` | archive | `pilotstd/manager/organize/organizer.py` | `_build_archive_failed_message` | – | error | task_failure |
| 20 | `archive_abandoned` | archive | `pilotstd/services/favorite_chain_processor.py` | `_build_archive_abandoned_message` | – | error | task_result |
| 21 | `expire_standard_moved` | expire | `pilotstd/manager/facade/_organize.py` | `_build_expire_standard_moved_message` | – | info | task_result |
| 22 | `replacement_not_found` | expire | `pilotstd/manager/classifier.py` | `_build_replacement_not_found_message` | – | warning | task_failure |
| 23 | `announcement_fetch_complete` | announce | `docker/api/announce.py` | `_build_announcement_fetch_complete_message` | wechat | info | user_activity |
| 24 | `announcement_check_complete` | announce | `pilotstd/announce/notifier.py` | `_build_announcement_check_complete_message` | wechat | info/warning/error | user_activity |
| 25 | `announcement_fetch_failed` | announce | `pilotstd/announce/notifier.py` | `_build_announcement_fetch_failed_message` | – | error | user_activity |
| 26 | `announce_fetch_summary` | announce | `pilotstd/announce/notifier.py` | `_build_announce_fetch_summary_message` | – | info/warning | user_activity |
| 27 | `auto_backup` | system | `docker/scheduler.py` | `_build_auto_backup_message` | wechat | info/error | anomaly_alert |
| 28 | `image_update_available` | system | `docker/api/system.py` | `_build_image_update_available_message` | – | info/error | anomaly_alert |
| 29 | `trust_ip_update` | system | `pilotstd/manager/wechat_ip_service.py` | `_build_trust_ip_update_message` | – | info/warning | security_alert |
| 30 | `worker_error` | system | `pilotstd/ui/pending_query_dialog.py` | `_build_worker_error_message` | – | error | anomaly_alert |
| 31 | `task_execution_failed` | system | `docker/scheduler.py` | `_build_task_execution_failed_message` | – | error | anomaly_alert |
| 32 | `quota_exhausted` | system | `pilotstd/query/daily_quota.py` | `_build_quota_exhausted_message` | – | warning | anomaly_alert |
| 33 | `notification_delivery_failed` | system | `pilotstd/core/notification/manager.py` | `_build_notification_delivery_failed_message` | wechat | error | system_health |
| 34 | `desktop_toast` | system | `pilotstd/core/notification_aggregator.py` | `_build_desktop_toast_message` | – | info/warning/error | system_health |
| 35 | `favorite_created` | favorite | `docker/api/favorites.py` | `_build_favorite_created_message` | – | info | user_activity |
| 36 | `task_progress` | system | `pilotstd/core/notification/progress_reporter.py` | `_build_task_progress_message` | wechat,dingtalk,feishu,telegram | info | task_progress |
| 37 | `download_started` | favorite | `pilotstd/tasks/favorite_download.py` | `_build_download_started_message` | – | info | task_progress |
| 38 | `download_complete` | favorite | `pilotstd/tasks/favorite_download.py` | `_build_download_complete_message` | – | info | task_result |
| 39 | `favorite_abandoned_summary` | favorite | `pilotstd/services/favorite_chain_processor.py` | `_build_favorite_abandoned_summary_message` | wechat | warning | user_activity |
| 40 | `notification_credential_changed` | security | `docker/api/notification_config.py` | `_build_notification_credential_changed_message` | – | warning | security_alert |
| 41 | `security_password_changed` | security | `docker/api/users.py` | `_build_security_password_changed_message` | – | warning | security_alert |
| 42 | `security_token_refreshed` | security | `docker/api/settings.py` | `_build_security_token_refreshed_message` | – | warning | security_alert |
| 43 | `security_login_failed` | security | `docker/auth.py` | `_build_security_login_failed_message` | wechat | warning | security_alert |
| 44 | `auto_pipeline_summary` | system | `pilotstd/manager/facade/_auto.py` | `_build_auto_pipeline_summary_message` | – | info | batch_summary |

**不在事件全集里的"幽灵事件"**：`standard_expired` —— `events.py:30` 仍定义 `EVENT_EXPIRED`，但 `ALL_EVENTS` 中**没有**它；`pilotstd/core/notification/__init__.py:74-83` 只做废弃转发；语义已合并进 `standard_status_changed(is_expired=True)`（`_builders_validity.py:22-27`）。⇒ **系统没这个事件，渠道对齐不适用**。

### 1.3 是否已配置（出厂默认 vs 生产订阅）

- **出厂默认**：由 `event_spec_data.py` 的 `default_channels` 派生 `notification.rules.<event>`（`defaults.py:101`）。实测：**44 个事件中 16 个出厂有默认渠道——15 个仅 wechat（含 `notification_delivery_failed`/`favorite_abandoned_summary`/`security_login_failed`）、1 个（`task_progress`）四渠道全开；其余 28 个出厂无任何默认渠道**（`default_channels=()`）⇒ 新装用户默认收不到这 28 个事件（需手动订阅）。
- **生产订阅**（`GET /api/notification/policy`，2026-11-24 只读）：`wechat` 用**类别层 10 类全开**、`telegram` 用**逐事件显式 36 个**（`event_classes=[]`）。**TG 未订阅的 8 个**：`notification_delivery_failed`、`desktop_toast`、`favorite_abandoned_summary`、`notification_credential_changed`、`security_password_changed`、`security_token_refreshed`、`security_login_failed`、`auto_pipeline_summary`。
  ⇒ **生产上"事件覆盖面"是企微 > TG**（7 个安全/告警类只到企微；`desktop_toast` 两侧都不适用），但**单条消息的信息字段**是企微 < TG（见 §2、§3）。
- 注：每渠道策略行存在时**优先于** config 的 `notification.rules`（`_policy.py:73-139`）；本次 `GET /api/notification/config` 返回的 `rules` 多为 `["telegram"]`，是"策略表为空时的回退值"，**不是当前实际路由**。

---

## 2. 渠道渲染路径（文件:行）

### 2.1 主链路（四渠道共用，内容层统一）

```
业务代码 send_event(event, data)
  → manager.send_event                       manager.py:236-278
  → _dispatcher.send_event                   _dispatcher.py:70-151
      ├ host._build_message(event, data)     manager.py:418-426   （构建器 → NotificationMessage）
      ├ host.ops.apply_mapping(...)          _manager_ops.py:361-384
      └ host._do_send(msg, channels)         _dispatcher.py:225-248
  → 聚合器 enqueue / flush                    aggregate_buffer.py:172-266
  → _send_merged → 合成 NotificationMessage   aggregate_buffer.py:388-486
  → send_now(msg, channels)                  _dispatcher.py:251-324
      ├ 先落库占位 + 铸 callback token        _dispatcher.py:280-299
      ├ attach_web_actions(msg, cfg)         _dispatcher.py:300-303 → _links.py:74-108
      └ channel.send(msg)                    _dispatcher.py:304-318
```

**内容层**：`NotificationMessage`（`channel.py:33-108`）＝ 标题 + 4 种 Block（`blocks.py:20-59`：Text / KeyValue / StatusChange / List）+ 级别 + `link` + `failed_items` + `actions`。四渠道**拿同一个消息对象**，各自翻译。

**"动作"的唯一来源**：`attach_web_actions()` 在发送前给消息挂 `view_detail`（+ 有失败明细时 `open_logs`）链接型动作，URL = `{notification.web_base_url}/notification-logs`（`_links.py:36-71`）。**未配置/回环地址时降级**：不挂动作、改为追加一段纯文本提示（`_links.py:85-94`，文案 `notification.link.web_hint`）。`notification.web_base_url` 默认空（`defaults.py:68`）⇒ **生产是否有点击入口取决于该配置项，本次未取到其生产取值**（诊断端点 `actions` 列在占位落库时已写死为空，无法据此判定，见 §6.4）。

### 2.2 各渠道渲染路径

| 渠道 | 形态 | 渲染器（文件:行） | 发送入口 | 消息格式 | 单条上限 |
|------|------|------------------|---------|---------|---------|
| **Telegram** | 单一形态 | `renderer_telegram.py:25-147`（`TelegramRenderer`，继承 `BlockRenderer` 骨架） | `channels/telegram.py:61-94` | MarkdownV2，18 个保留字符转义 | 4096 字符（`renderer_base.py:26-31`） |
| **企业微信** | 群机器人 Webhook | `renderer.py:124-180`（`MarkdownRenderer`） | `channels/wechat.py:72-96` | `msgtype=markdown` | 2048 **字节**（按字节分段） |
| **企业微信** | 自建应用（生产在用） | `renderer_wecom_card.py:38-93`（`WeChatCardRenderer.render_card`） | `channels/wechat.py:172-175` | `msgtype=template_card`（`news_notice`） | 无分段；平台拒收→降级文本（`:79-84`、`:177-180`） |
| 飞书 | 卡片 | `renderer.py:195-320`（`FeishuCardRenderer`） | `channels/feishu.py:221-326` | 交互式卡片（标题颜色=级别、表格=列表、URL 按钮=动作） | 按元素切卡 |
| 钉钉 | 互动卡片 / 群机器人 | `renderer.py:328-370` / `MarkdownRenderer` | `channels/dingtalk.py:113-119`、`:244` | `cardParamMap{title,content,level}` / markdown | 4000 字符（未取证） |
| 桌面 | Toast | `renderer.py:373-402`（`DesktopRenderer`） | `notification_aggregator.py`（L2 本地信号） | 压一行、列表只取首条 | Windows Toast |

### 2.3 字段消费矩阵（"谁渲染了什么"——核心差异来源）

图例：✅=渲染；➖=该渠道无此字段/不适用；⚠️=有条件；**"级别前缀"= `level_prefix()`（`renderer_base.py:145-154`，仅 warning/error 产出 `⚠️ 警告`/`❌ 错误`）**。

| 字段 | TG | 企微 Webhook(markdown) | **企微应用(template_card)** | 飞书卡片 | 钉钉卡片 | 桌面 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| 标题 `title` | ✅ `*…*`（`renderer_telegram.py:75-78`） | ✅ `## …`（`renderer.py:145-148`） | ✅ `main_title`+`source`（`renderer_wecom_card.py:69-70`） | ✅ header（`renderer.py:235-243`） | ✅ `title`（`renderer.py:365-369`） | ✅ |
| **级别前缀** | ✅（`renderer_base.py:204-209`） | ✅（同上，`MarkdownRenderer` 未覆盖） | ❌ **不渲染**（`render_card` 直接走 `_render_block`，不经过 `render()` 的 204-209 行） | ✅ 标题颜色（`renderer.py:187-192`、`:239`） | ✅ 正文前缀（`renderer.py:357-363`） | ✅ |
| 正文块 Text/KeyValue/StatusChange | ✅ | ✅ | ✅（逐行塞 `vertical_content_list`，`renderer_wecom_card.py:44-53`） | ✅ | ✅ | ✅ |
| ListBlock 列表 | ✅ `•`/`📋`/`（共 N 条）`/原始 detail_url（`renderer_telegram.py:91-116`） | ✅ `-`/`（共 N 条）`/`[查看完整列表](url)`（`renderer.py:161-180`） | ⚠️ 逐行 `- …`，**丢「共 N 条」、丢 `detail_url`、丢字段标签**（`renderer_wecom_card.py:89-93`） | ✅ 表格+按钮（`renderer.py:264-317`） | ✅ 文本 | ✅ 仅首条首字段 |
| `message.link` 详情行 | ✅ `详情：<url>`（`renderer_base.py:157-162`、`:210-211`） | ✅ 同左 | ❌ **不渲染**（`render_card` 无 `detail_link_line`） | ✅ `renderer.py:232-234` | ✅ `renderer.py:359-363` | ✅ |
| 链接型动作 `view_detail` | ✅ inline URL 按钮（`renderer_telegram.py:49-52`） | ✅ markdown 链接（`renderer.py:134-140`） | ✅ `jump_list`+`card_action`（`renderer_wecom_card.py:57-75`） | ✅ URL 按钮（`renderer.py:217-229`） | ✅ 写进正文 markdown（`renderer.py:348-356`） | ❌（无动作概念） |
| 回调型按钮（retry 等） | ⚠️ 仅当消息带 `actions`+token（`renderer_telegram.py:53-71`） | ➖（markdown 无按钮） | ➖（`supports_buttons=False`，`test_notification_channel_capabilities.py:17-20`；且全库无业务动作生产者） | ✅ 能力存在 | ➖ | ➖ |
| 分段策略 | 4096 字符，段间"续 N/M"（`renderer_base.py:80-116`） | 2048 **字节**，段间"续 N/M"（`channels/wechat.py:88-96`） | **无分段**；卡片拒收→文本降级（**截断 2000 字符**，见 §4.1-P1-2） | 按元素切卡（`feishu.py:275-326`） | 4000 字符分段 | 单行 120 字符预览 |

> **注（推翻旧分析）**：`docs/analysis/2026-11-21-notification-channel-analysis.md:29-31` 称"企微 markdown、Telegram、桌面看不到级别；`message.link` 四渠道一个都不渲染"。该结论对应**修复前**代码；2026-11-21 提交 `3d4fbc09`（D-2 阶段1 三缺口）已在 `renderer_base.py:204-212` 统一补上"级别前缀 + 详情链接行"，本报告以当前代码为准。**该修复没有覆盖企微卡片路径**——这正是本任务最主要的缺口。

### 2.4 企微三条路径分别带了哪些字段

| 企微路径 | 代码位置 | 标题 | 级别 | 正文 | 详情链接 `message.link` | 动作 `view_detail` | ListBlock 计数/明细链接 |
|---------|---------|:--:|:--:|:--:|:--:|:--:|:--:|
| ① 模板卡片（生产在用） | `renderer_wecom_card.py:38-93` | ✅ | ❌ | ✅（140 字折行拆 desc） | ❌ | ✅ `jump_list` | ❌ |
| ② webhook markdown | `renderer.py:124-180` | ✅ | ✅ | ✅ | ✅ | ✅ markdown 链接 | ✅ |
| ③ 卡片拒收→文本降级 | `channels/wechat.py:177-180` | ⚠️（随 `MarkdownRenderer.render`，body-only 消息无标题） | ✅ | ⚠️ **`text[:2000]` 字符硬截断、不分段** | ✅ | ✅ | ✅ |

---

## 3. 通知模板对照表（核心产出）

### 3.1 图例

| 记号 | 含义 |
|------|------|
| `T` | 标题 |
| `LV` | 级别前缀（仅 warning/error 事件有） |
| `B` | 正文块（Text/KeyValue/StatusChange/List 的渲染结果） |
| `L` | `message.link` 详情行（仅 7 个事件带 `link`） |
| `A` | 链接型动作 `view_detail`（TG=按钮 / 企微卡片=jump_list / 企微 webhook=markdown 链接）。**仅当 `notification.web_base_url` 已配置**；否则降级为纯文本提示块 |
| `LC` / `DU` | ListBlock 的「共 N 条」计数 / `detail_url`（查看完整列表） |
| **判据列** | ✅=动作+对象+结果齐全；⚠️=缺其一（写明缺什么）；N/A=不适用 |
| **已配置列** | `出厂：<渠道>` 来自 `default_channels`；`生产：w=✔/✘, t=✔/✘` 来自生产 policy（w=企微、t=TG） |

> 表中"企微字段"按**生产在用的应用形态（模板卡片）** 列出，并在括号内标注 Webhook 形态差异（若无差异则写"同 TG"）。

| # | 事件 | 触发场景 | 已配置（出厂 / 生产） | TG 字段 | 企微字段（卡片） | 动作+对象+结果 | 差距 | 建议 |
|---|------|---------|----------------------|---------|------------------|:---:|------|------|
| 1 | `standard_status_changed` | 标准状态变更（废止时 error） | 出厂 wechat / w✔ t✔ | T+LV+B+L+A | T+B+A；**缺 LV、L** | ✅ 变更→标准号+名称→旧→新 | 企微卡片看不到 error 级别与标准详情链接 | 卡片补 LV+L（§5-P0-2/P0-3） |
| 2 | `standard_first_registered` | 新标准首次登记（批量） | 出厂 – / w✔ t✔ | T+B+LC+DU+L+A | T+B+A；**缺 LC、DU、L**（列表头"共 2 条"与"查看完整列表"被丢） | ✅ 登记→清单标准号/名称→共 2 条+耗时 | 企微卡片列表丢计数/完整列表链接/标准详情链接 | 卡片 `_render_list` 补 LC/DU；补 L |
| 3 | `validity_batch_report` | 批量有效性检查进度/完成 | 出厂 wechat / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 检查→变更/失败明细标准号→总数/变更/失败计数 | 企微卡片看不到 warning | 卡片补 LV |
| 4 | `validity_round_summary` | 单轮有效性检查汇总 | 出厂 wechat / w✔ t✔ | T+B+LC+A | T+B+A；**缺 LC** | ✅ 汇总→变更明细→轮次/检查/变更/失败计数 | 卡片列表丢"共 N 条"（N 仍在正文统计行，信息未全丢） | 卡片补 LC |
| 5 | `validity_standard_failed` | 单条标准有效性检查失败 | 出厂 wechat / w✔ t✔ | T+LV+B+L+A | T+B+A；**缺 LV、L** | ✅ 检查失败→标准号+名称→错误 | 级别/详情链接不可见 | 卡片补 LV+L |
| 6 | `validity_system_failed` | 有效性检查系统级失败 | 出厂 wechat / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ⚠️ 弱对象（只有"有效性检查"抽象，无标准/站点） | 级别不可见；对象过弱 | 卡片补 LV；构建器补异常上下文（站点/阶段） |
| 7 | `date_reminder` | 标准实施日期到期提醒 | 出厂 wechat / w✔ t✔ | T+B+A | T+B+A | ✅ 提醒→标准号+名称→还有 7 天 | 无（两侧同） | — |
| 8 | `scan_complete` | 扫描完成（有失败明细） | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 扫描→文件/失败路径→12/10/2 | 企微卡片看不到 warning | 卡片补 LV |
| 9 | `scan_empty` | 扫描完成但无新增文件 | 出厂 – / w✔ t✔ | T+B+A | T+B+A | ⚠️ **缺对象**（未写扫描哪个目录） | 两渠道都只说"未发现新文件" | 构建器补路径/根目录（§5-P1-5） |
| 10 | `auto_scan_failed` | 定时扫描异常 | 出厂 wechat / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 扫描失败→路径→错误 | 级别不可见 | 卡片补 LV |
| 11 | `batch_query_summary` | 批量查询完成（有命中） | 出厂 – / w✔ t✔ | T+B+LC+A | T+B+A；**缺 LC** | ✅ 查询→结果清单→共 N 条结果 | 列表计数丢失（正文另有总数） | 卡片补 LC |
| 12 | `query_failed` | 单条标准查询异常 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 查询失败→标准号+名称→错误 | 级别不可见 | 卡片补 LV |
| 13 | `query_empty` | 批量查询全部未命中 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ⚠️ **缺对象**（只有"共 3 条标准"，没有标准号清单） | 用户不知道"哪 3 条没查到"；级别不可见 | 构建器补 standards 列表（§5-P1-5）；卡片补 LV |
| 14 | `batch_download_complete` | 批量下载完成（含失败） | 出厂 wechat / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 下载→失败明细前 5 条→成功/失败/跳过 | 级别不可见（明细已在前 5 条截断，两侧一致） | 卡片补 LV |
| 15 | `download_failed` | 收藏下载单文件失败 | 出厂 – / w✔ t✔ | T+LV+B+L+A | T+B+A；**缺 LV、L** | ✅ 下载失败→标准号+名称→错误 | 级别/详情链接不可见 | 卡片补 LV+L |
| 16 | `normalize_complete` | 批量规范化完成 | 出厂 – / w✔ t✔ | T+B+LC+A | T+B+A；**缺 LC** | ✅ 规范化→失败明细（4 列）→总数/成功/失败 | 列表计数丢失 | 卡片补 LC |
| 17 | `normalize_failed` | 规范化流程异常 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ⚠️ **缺对象**（payload 只有 total+error） | 用户不知道"哪 2 条"；级别不可见 | 构建器补 `failed_items`（§5-P1-5）；卡片补 LV |
| 18 | `archive_complete` | 归档完成（含 count=0） | 出厂 wechat / w✔ t✔ | T+B+A | T+B+A | ✅ 归档→目录/分类→已归档 3 个 | 无字段级差（卡片列表为 TextBlock，不受 ListBlock 缺陷影响） | — |
| 19 | `archive_failed` | 部分文件归档失败 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ⚠️ **缺对象**（只有 count+error，无标准号） | 用户不知道"哪条归档失败" | 构建器补 standard_number/明细；卡片补 LV |
| 20 | `archive_abandoned` | 重试上限/业务终态放弃 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 放弃→standard_info→错误原因 | 级别不可见 | 卡片补 LV |
| 21 | `expire_standard_moved` | 废止标准移入过期作废目录 | 出厂 – / w✔ t✔ | T+B+A | T+B+A | ✅ 移入→标准号+名称→目标路径 | 无 | — |
| 22 | `replacement_not_found` | 替代标准查找全部失败 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 查找失败→标准号+名称→未找到+已搜索源 | 级别不可见 | 卡片补 LV |
| 23 | `announcement_fetch_complete` | 公告拉取完成（手动路径） | 出厂 wechat / w✔ t✔ | T+B+A | T+B+A | ✅ 拉取→来源+公告标题→新增计数 | 无 | — |
| 24 | `announcement_check_complete` | 公告检查完成（定时） | 出厂 wechat / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 检查→来源→公告/国标/行标/地标/涉及标准计数 | 级别不可见 | 卡片补 LV |
| 25 | `announcement_fetch_failed` | 公告抓取全站失败 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 抓取失败→来源→错误 | 级别不可见 | 卡片补 LV |
| 26 | `announce_fetch_summary` | 公告抓取逐站汇总 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 汇总→适配器名→总计+各站成功/失败 | 级别不可见 | 卡片补 LV |
| 27 | `auto_backup` | 每周自动备份数据库 | 出厂 wechat / w✔ t✔ | **渲染异常（TG 收不到）** | T+B+A（正常） | ✅ 备份→备份路径→文件大小 | **TG 渲染期 TypeError → 整条丢失**（生产实证） | 构建器 `size_mb` 转 str（§5-P0-1） |
| 28 | `image_update_available` | 镜像新版本可用 | 出厂 – / w✔ t✔ | T+B+A | T+B+A | ✅ 更新→镜像版本→新版本+更新内容 | 无 | — |
| 29 | `trust_ip_update` | 企微可信 IP 更新 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 更新→IP→状态 | 级别不可见 | 卡片补 LV |
| 30 | `worker_error` | 后台 Worker 线程异常 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 异常→worker 名→错误(+traceback) | 级别不可见 | 卡片补 LV |
| 31 | `task_execution_failed` | APScheduler 定时任务异常 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 任务失败→任务名→错误+将自动重试 | 级别不可见 | 卡片补 LV |
| 32 | `quota_exhausted` | 适配器日配额首次耗尽 | 出厂 – / w✔ t✔ | T+LV+B+A | T+B+A；**缺 LV** | ✅ 配额耗尽→站点→限额+重置时间 | 级别不可见 | 卡片补 LV |
| 33 | `notification_delivery_failed` | 通知系统自身投递失败 | 出厂 wechat / **t✘** | T+LV+B+A | T+B+A；**缺 LV** | ✅ 投递失败→渠道→连败次数/失败率+建议 | 级别不可见；TG 生产未订阅 | 卡片补 LV；如需 TG 也收需改策略 |
| 34 | `desktop_toast` | 桌面托盘回显（平台层） | 出厂 – / w✔(类别) t✘ | —（不经 `send_event`） | — | **N/A** | 平台层事件，渠道对齐不适用 | 不修（§4.3） |
| 35 | `favorite_created` | 收藏建立并进入下载队列 | 出厂 – / w✔ t✔ | T+B+L+A | T+B+A；**缺 L** | ✅ 收藏→标准号+名称→预计下载日期 | 标准详情链接不可见 | 卡片补 L |
| 36 | `task_progress` | 长任务周期进度汇报 | 出厂 4 渠道 / w✔ t✔ | T+B+A | T+B+A（卡片）；**Webhook 形态缺 T**（body-only 消息，基类 `_render_plain_text` 不补标题） | ✅ 进行中→任务名→30/100+步骤 | 生产用卡片形态 ⇒ 标题在；若切 Webhook 形态则丢标题 | 基类/MarkdownRenderer 补 body-only 标题（§5-P1-3） |
| 37 | `download_started` | 收藏下载开始执行 | 出厂 – / w✔ t✔ | T+B+L+A | T+B+A；**缺 L** | ⚠️ **缺结果**（只有"开始下载"，无结果；结果由 complete/failed 事件承载） | 两渠道都缺结果；详情链接在卡片不可见 | 构建器补预期/排队信息或合并入 complete；卡片补 L |
| 38 | `download_complete` | 单文件下载并归档完成 | 出厂 – / w✔ t✔ | T+B+L+A | T+B+A；**缺 L** | ✅ 下载归档→标准号+名称→文件位置 | 标准详情链接不可见 | 卡片补 L |
| 39 | `favorite_abandoned_summary` | 收藏终态放弃汇总（仅实际放弃时） | 出厂 wechat / **t✘** | T+LV+B+LC+A | T+B+A；**缺 LV、LC** | ✅ 放弃→示例标准号→总数+原因分类+建议 | 级别/列表计数不可见；TG 生产未订阅 | 卡片补 LV/LC |
| 40 | `notification_credential_changed` | 通知渠道凭证变更 | 出厂 – / **t✘**（w 类别层✔） | T+LV+B+A | T+B+A；**缺 LV** | ✅ 变更→渠道+字段→来源 IP+处理建议 | 级别不可见；TG 未订阅；且直连投递只认 webhook 形态（§4.1-P1-4） | 卡片补 LV；直连补应用形态（§5-P1-4） |
| 41 | `security_password_changed` | 账号密码变更 | 出厂 – / **t✘**（w 类别层✔） | T+LV+B+A | T+B+A；**缺 LV** | ⚠️ 弱结果（`sessions_revoked=True` 时不显示"已撤销 N 会话"，仅在 0 时显示异常提示） | 级别不可见；结果不完整 | 构建器在 True 分支补"已撤销会话"行；卡片补 LV |
| 42 | `security_token_refreshed` | API 静态令牌轮换 | 出厂 – / **t✘**（w 类别层✔） | T+LV+B+A | T+B+A；**缺 LV** | ✅（弱对象：对象=API 静态令牌，系统级可接受） 轮换→令牌→时间+旧令牌失效 | 级别不可见；TG 未订阅 | 卡片补 LV |
| 43 | `security_login_failed` | 登录失败达阈值 | 出厂 wechat / **t✘** | T+LV+B+A | T+B+A；**缺 LV** | ✅ 登录失败→目标账号→次数+来源 IP | 级别/告警语义不可见；TG 未订阅 | 卡片补 LV |
| 44 | `auto_pipeline_summary` | 一键处理（扫描→查询→下载→归档）终局汇总 | 出厂 – / **t✘**（w 类别层✔） | T+B+A | T+B+A | ⚠️ **缺对象**（无批次/无范围，四阶段计数） | 只有"什么结果"没有"处理了哪个对象/哪一批" | 构建器补 task_id/触发范围（§5-P1-5）；卡片补 A |

**对照表统计**：
- 事件 44；判据适用 43（`desktop_toast` N/A）；✅ 37 / ⚠️ 6 / 弱项 3（其中 2 个"弱对象"、1 个"弱结果"，均计入 ✅ 但需修补）；**无"缺动作"事件**。
- 企微卡片字段缺口并集 **34/44**：缺级别 27、缺详情链接 7、缺列表计数/完整列表链接 5（交集 3：`download_failed`/`standard_status_changed`/`validity_standard_failed`），另有 `task_progress` 在 Webhook 形态缺标题。

---

## 4. 差距清单（按严重度排序）

> 排序原则：**渠道级"整条丢失" > 模板级"缺结果" > "缺对象" > "缺动作" > 字段级丢失**；同档内按影响事件数排序。

### 4.0 P0-1：TG 渲染崩溃导致整条通知丢失（渠道级，最严重）

| 项 | 内容 |
|---|---|
| 现象 | `auto_backup`（自动备份成功）在 **Telegram 渲染阶段抛 `TypeError: expected string or bytes-like object, got 'float'`**，`_dispatcher.send_now` 捕获后该渠道标记 failed，**TG 用户整条收不到**；企微（markdown/卡片）正常显示 |
| 根因（代码级） | `docker/scheduler.py:166-177` 传 `size_mb = os.path.getsize(...) / (1024*1024)`（**float**）→ `_builders_system.py:128-132` 原样塞进 `KeyValueBlock(value=size)`（dataclass 声明 `value: str` 但无运行时校验，`blocks.py:29-33`）→ `renderer_telegram.py:85-86` 调 `_escape(block.value)` → `:120-128` `re.sub` 收到 float 抛异常 |
| 实测证据（本地） | `C:\Temp\p1_autobackup_check.py` 实跑：`telegram EXC -> TypeError: expected string or bytes-like object, got 'float'`；`wecom_markdown OK`、`wecom_card OK` |
| 实测证据（生产） | 只读 SQL：`notification_log` id=**2034**（telegram，title「自动备份成功」，status=**failed**，error_msg=`expected string or bytes-like object, got 'float'`，2026-10-26T03:00:32）——**生产上真的丢过这条** |
| 影响面 | 目前 1 个事件（`auto_backup`）整条丢失；同类隐患：任何"非 str 值进 Block"都会在 TG 崩溃而在企微正常工作（`tests/test_notification_e2e.py:590` 已把 `size_mb/elapsed_ms` 标为 float 字段，但 e2e 不跑渠道渲染，未拦住） |
| 修复 | §5-P0-1 |

### 4.1 渠道级字段丢失（企微应用形态，影响 34/44 事件）

| 编号 | 差距 | 影响 | 证据（文件:行） | 严重度 |
|------|------|------|----------------|:---:|
| **P0-2** | 企微模板卡片**不渲染级别前缀**：warning/error 在企微与 info 无法区分（TG/企微 webhook/飞书/钉钉都有） | **27** 个事件（全部 warning/error） | `renderer_wecom_card.py:41-76`（`render_card` 逐块调 `_render_block`，不经过 `renderer_base.py:204-209` 的前缀逻辑） | **高** |
| **P0-3** | 企微模板卡片**不渲染 `message.link` 详情行**：7 个带标准详情链接的事件在企微卡片点不到/看不到 | **7** 个事件（`standard_status_changed`/`standard_first_registered`/`validity_standard_failed`/`download_failed`/`favorite_created`/`download_started`/`download_complete`） | 构建器设 `link`：`_builders_validity.py:17-19,62,102,235`；`_builders_batch_download.py:83,108,141`；渲染：`renderer_base.py:157-162` 只被 `render()` 调用，`render_card` 无此调用 | **高** |
| **P1-1** | 企微模板卡片 `ListBlock` **丢「共 N 条」、丢 `detail_url`、丢字段标签** | **5** 个事件（`standard_first_registered`/`validity_round_summary`/`batch_query_summary`/`normalize_complete`/`favorite_abandoned_summary`） | `renderer_wecom_card.py:89-93` vs TG `renderer_telegram.py:91-116`、webhook `renderer.py:161-180` | 中 |
| **P1-2** | 企微**卡片拒收→文本降级**路径 `text[:2000]` 按**字符**硬截断且不分段：长消息丢尾部，且 2000 个汉字 ≈ 6000 字节 > 企微文本 2048 **字节**上限 ⇒ 降级消息本身可能再被拒收 | 任何长通知（聚合消息/多失败明细），一旦卡片被平台拒收即触发 | `channels/wechat.py:177-180`（未用已声明的 `CHANNEL_TEXT_LIMITS["wecom"]=(2048,"bytes")`，`renderer_base.py:26-31`） | **高（潜在）** |
| **P1-3** | 企微 **Webhook 形态**对**无 blocks 的 body-only 消息丢标题**（生产用应用形态不受影响，但 Webhook 是官方支持形态） | 目前 1 个事件（`task_progress`，`_builders_task_results.py:274-299` 只设 `body`）；测试消息同理 | 基类 `renderer_base.py:214-219` `_render_plain_text` 原样返回 body；TG 已覆盖（`renderer_telegram.py:130-137`），`MarkdownRenderer` 未覆盖 | 中（形态相关） |
| **P1-4** | 三类**安全告警直连投递只认 webhook 形态**：`security_notifier._channel_instance` 对 wechat 只读 `webhook_url`；生产企微是应用形态（`webhook_url` 为空）⇒ 直连路径直接 `continue` 跳过，只剩 `manager.send_event` 一条路 | 3 个事件（`notification_credential_changed`/`security_password_changed`/`security_token_refreshed`） | `security_notifier.py:89-104`；生产配置 `GET /api/notification/config`（wechat：`webhook_url=""`、`corpid/agentid/corpsecret` 已配） | 中 |
| **P2-4** | **能力自述两处口径冲突**：`channels/wechat.py:230-242` 写 `supports_callback=False`，而 `interaction.py:52-57` 写 `wechat.supports_callback=True`；`tests/test_channel_capabilities.py:80` 以后者为准 | 影响"企微能不能回调"的判断，进而影响交互按钮是否该对齐 | 见左 | 低（文档/自述一致性） |

### 4.2 模板级缺口（用户判据：缺结果 > 缺对象 > 缺动作）

**A. 缺「结果」（1 个事件）**

| 事件 | 现状 | 影响 | 证据 |
|------|------|------|------|
| `download_started` | 正文仅"标准号：…"（动作=开始下载、对象=标准，**无结果**；结果由后续 `download_complete`/`download_failed` 承载） | 单看这条通知无法回答"下载成功了吗"；与判据"必须动作+对象+结果"不符 | `_builders_batch_download.py:89-110`；TG/企微渲染一致 |
| （弱）`security_password_changed` | `sessions_revoked=True` 时**不显示**"已撤销会话数"，仅在 `False` 时提示"会话未失效" | 用户不知道"改密后其它登录是否已踢掉"——安全结果不完整 | `_builders_system_security.py:91-95` |

**B. 缺「对象」（5 个事件 + 2 个弱项）**

| 事件 | 现状 | 影响 | 证据 |
|------|------|------|------|
| `scan_empty` | 只发"未发现新文件"，**不写扫描了哪个目录/路径** | 无法判断"没扫到"是不是因为路径配错 | `_builders_task_results.py:95-103`（payload 无 path，`event_spec_data.py:123-131` `payload_keys=frozenset()`） |
| `query_empty` | 只发"共 3 条标准，均未查询到结果"，**不列标准号** | 用户不知道该重新查哪几条 | `_builders_task_results.py:128-137`（payload 仅 `total`，`event_spec_data.py:166-175`） |
| `archive_failed` | "1 条标准归档失败：<error>"，**无标准号** | 不知道哪条失败 | `_builders_task_results.py:141-152`（payload `count`+`error`，`event_spec_data.py:245-254`） |
| `normalize_failed` | "2 条标准规范化失败：<error>"，**无标准号/明细** | 同上 | `_builders_task_results.py:155-172`（payload `total`+`error`，`event_spec_data.py:219-228`） |
| `auto_pipeline_summary` | 四阶段计数（扫描 12/查询 8/下载 6/归档 5），**无批次/无处理对象范围** | 不知道"这 12 个文件是哪一批、哪次一键处理" | `_builders_task_results.py:302-326`（payload 4 个计数，`event_spec_data.py:537-548`） |
| （弱）`validity_system_failed` | 对象只有"有效性检查"这个抽象任务 | 排障时无站点/阶段上下文 | `_builders_validity.py:240-257` |
| （弱）`security_token_refreshed` | 对象=API 静态令牌（系统级单例），可接受 | 低 | `_builders_system_security.py:107-132` |

**C. 缺「动作」：0 个事件**（44 个事件的标题或正文都表达了动作；`query_empty`/`scan_empty` 等的问题在对象而非动作）。

### 4.3 横切问题（两渠道同受影响，非"对齐"但会让"信息量"整体退化）

| 项 | 现象 | 证据 | 影响 |
|---|---|---|---|
| **聚合后 `event_type` 被改成"类别名"** | `_send_merged(event_type, …)` 的 `event_type` 来自 `aggregate_keys.events_in_group()`；日常桶键是 `2␟daily␟u0` ⇒ 落库 `event_type="daily"`；同理 `security_alert`/`task_result`/`task_failure`/`batch_summary`/`anomaly_alert`/`schedule_reminder` | `aggregate_buffer.py:427,442-486` + `aggregate_keys.py:92-108,111-127`；**生产实证**：`notification_log` 的 `event_type` 分布里 `batch_summary` 1499、`security_alert` 297、`task_result` 209、`daily` 92… 而业务事件名另有一批 | 日志/统计按事件过滤失真；"某事件是否发出"无法从日志直接查（见 §6.2） |
| **多条目聚合摘要预览取到"级别前缀"行** | `_build_summary` 多条时取 `render(msg).split("\n")[0]`，而渲染首行是级别前缀 ⇒ 预览退化为重复的"⚠️ 警告" | `aggregate_buffer.py:503-511`；**生产实证**：id=**4619** body=`📦 聚合通知（2 条）\n• ⚠️ 警告\n• ⚠️ 警告` | 聚合通知的日志正文/降级文本信息量严重退化（动作/对象/结果均丢失） |
| **`notification_log` 不存各渠道最终文本** | 日志只存构建器/聚合摘要的 `body` 与 `title`（`_manager_ops.py:58-119`），**不含渠道渲染后的实际文本** | 只读抽样：同事件 wechat/telegram 两行 `title`/`body` 完全一致 | 无法从日志直接证明"某渠道实际收到了什么"；本报告渠道差异结论 = 构建器 + 渲染器实跑（§6.5 说明） |
| **日志接口 `level` 口径失真** | `_business_level(event_type)` 拿**业务事件名**与 `security_alert`/`task_failure`（类别名）比较 ⇒ 非聚合行恒 `info` | `docker/api/notification_logs.py:133-139,196` | Web 铃铛/日志页对"错误级别"着色仍不可靠（与渠道无关，但同属"严重度信息丢失"） |

### 4.4 不适用 / 隐藏（按用户判据：系统没做或没配置项 ⇒ 不要求对齐）

| # | 场景 | 为什么"隐藏/不适用" | 证据 |
|---|------|-------------------|------|
| 1 | 企微**回调型交互按钮**（`retry`/`ignore`/`snooze`/`mark_done`） | ① 全库**无生产者**（仅 `view_detail`/`open_logs` 链接型有生产者，`_links.py:100-106`）；② 企微卡片能力自述 `supports_buttons=False`（`test_notification_channel_capabilities.py:17-20`），`interaction.py:52-57` 亦无 buttons | `renderer_telegram.py:53-71`（TG 才有回调按钮）；构建器无 `actions` 业务动作 |
| 2 | 企微 Webhook 形态的按钮 | 企微群机器人 webhook 只支持 markdown，无按钮能力 | `renderer.py:127-141`（注释明说"只支持 markdown，无法带按钮"） |
| 3 | 图片 / 附件 | 四渠道**均未实现发送**（`attachments` 只承载不发送；企微卡片 `card_image` 仅"有图才输出"但无图片路径） | `channel.py:104`；`renderer_wecom_card.py:19-22`；渠道实现无图片分支 |
| 4 | `desktop_toast` | 平台层事件：L2 桌面协调层直构消息投本地信号，**不经 `send_event`**；`subscribable=False`、`default_channels=()` | `event_spec_data.py:412-425`；`events.py:83-90`；`notification_coverage.md:286-296` |
| 5 | `standard_expired` | 事件已合并进 `standard_status_changed(is_expired=True)`，仅剩废弃常量 + 废弃转发 | `events.py:30`（不在 `ALL_EVENTS`）；`__init__.py:74-83`；`_builders_validity.py:22-27` |
| 6 | 企微/飞书/钉钉的「表格」表达 | 只有飞书把 ListBlock 渲染成表格；这是渠道格式能力差异，不是信息缺失（企微卡片是逐行 desc） | `renderer.py:264-317` |
| 7 | 各渠道分片条数不同 | 企微按 2048 **字节**分段、TG 按 4096 字符分段 ⇒ 同一条长消息渠道条数不同，但**内容不丢**（段间有"续 N/M"） | `renderer_base.py:26-31,80-116`；`channels/wechat.py:88-96` |

---

## 5. 修复建议（改哪个构建器 / 渲染器的哪个字段）

> 原则：**先修"整条丢失/看不出严重度"，再修"缺字段"，最后修"缺对象"**；全部为最小 diff，不动声明体系。

### 5.1 最小修复集（建议按此顺序落地）

| ID | 改哪里（文件:行） | 怎么改 | 解决 | 验证方式 |
|----|------------------|--------|------|---------|
| **P0-1** | `pilotstd/core/notification/_builders_system.py:128-132` | `size` 转字符串：`value=str(size)`（或 `_builders_system.py:124-140` 内对 `path/size` 统一 `str()`） | TG `auto_backup` 渲染崩溃（整条丢失） | 本地 `TelegramRenderer().render(msg)` 不抛异常；生产复部署后 `/api/notification/logs` 出现 `auto_backup` telegram success |
| **P0-2** | `pilotstd/core/notification/renderer_wecom_card.py:67-76` | 在 `source.desc` 或 `main_title.desc` 补 `renderer_base.level_prefix(message.level)`（如 `source.desc=f"{prefix} {title}"`）；同时把 `_render_block` 的前缀逻辑与 `render()` 对齐（避免二次前缀） | 企微卡片看不出 warning/error（27 事件） | 用 warning/error 事件（如 `security_login_failed`）实跑，断言卡片 JSON 含 `⚠️ 警告` |
| **P0-3** | `pilotstd/core/notification/renderer_wecom_card.py:57-75` | 把 `message.link`（`str(message.link)` 非空时）作为 `jump_list` 的**首项**（title 用 `notification.renderer.detail`），`card_action.url` 指向它；现有 `view_detail` 动作保留为后续项 | 企微卡片丢标准详情链接（7 事件） | 实跑 7 个带 link 事件，断言卡片 `jump_list` 含标准详情 URL |
| **P1-1** | `pilotstd/core/notification/renderer_wecom_card.py:89-93` | `_render_list` 补 `renderer.list_count` 文案与 `block.detail_url`（同 `MarkdownRenderer` 的 `renderer.py:161-180` 口径） | 卡片列表丢「共 N 条」/完整列表链接（5 事件） | 实跑 `standard_first_registered`/`validity_round_summary` 等，断言 desc 含"共 N 条"或 jump_list 含 `detail_url` |
| **P1-2** | `pilotstd/core/notification/channels/wechat.py:177-180` | `_send_app_text` 改为 `for seg in split_for_channel(text, "wecom")` 逐段发送（复用 `renderer_base.split_for_channel`，字节口径），去掉 `text[:2000]` 字符截断 | 卡片拒收降级时企微丢尾部/再次被拒 | 构造超 2048 字节消息，mock 平台返回拒收 → 断言多段发送且末段含尾部内容 |
| **P1-3** | `pilotstd/core/notification/renderer.py:124-141`（`MarkdownRenderer`）或 `renderer_base.py:214-219`（基类 `_render_plain_text`） | 无 blocks 时补标题（与 `renderer_telegram.py:130-137` 同款）：`f"## {title}\n\n{body}"`；注意只为 markdown 渲染器加，避免影响桌面/其它渠道 | 企微 Webhook 形态丢标题（`task_progress` 等 body-only） | 实跑 `task_progress`，断言 markdown 首行含标题 |
| **P1-4** | `pilotstd/core/notification/security_notifier.py:89-104` | 为 wechat 增加应用形态构造分支（按 `corpid/agentid/corpsecret` 构造 `WechatChannel`），与 `channels/wechat.py:26-38` 的形态选择保持一致；或改为复用渠道注册表构造 | 应用形态企微收不到直连安全告警 | 单测：应用形态凭据下 `_channel_instance("wechat", creds)` 非 None |
| **P1-5** | 构建器补对象（各文件单点） | ① `scan_empty`：payload 增 `path`（`_scan.py` 传扫描根）→ `_builders_task_results.py:95-103` 渲染路径；② `query_empty`：payload 增 `standards` 列表 → `:128-137` 列前 N 条；③ `archive_failed`：payload 增 `standard_number`/`failed_items`；④ `normalize_failed`：payload 增 `failed_items`（复用 `build_failed_items_block`，`_builders_batch.py:374-417`）；⑤ `auto_pipeline_summary`：payload 增 `task_id`/触发范围 | 5 个"缺对象"事件 | 各事件新 payload 的 e2e/单测 + 渲染输出含对象 |
| **P2-1** | `pilotstd/core/notification/aggregate_buffer.py:442-486` | `merged.event_type` 改用 `first_msg.event_type`（保留业务事件名），聚合类别另存字段 | 日志 `event_type` 被类别名污染、按事件查询失真 | 单测：聚合后 `event_type` 仍为业务事件名 |
| **P2-2** | `pilotstd/core/notification/aggregate_buffer.py:503-511` | 多条摘要预览去掉级别前缀行（`render(msg).split("\n")` 中跳过 `level_prefix` 行） | 聚合摘要退化成"• ⚠️ 警告" | 单测：warning 级别 2 条聚合，摘要含各自正文关键信息 |
| **P2-3** | `docker/api/notification_logs.py:133-139` | `_business_level` 改用 `notify_event`（类别名）或从 `notification_log` 取真实 level（需加列，代价较大；最低成本：按 `notify_event` 映射） | 日志接口级别恒 info | 单测：`security_alert` 行返回 warning、`task_failure` 返回 error |
| **P2-4** | 文案/自述一致性 | 修 `channels/wechat.py:230-242` 与 `interaction.py:52-57` 的 `supports_callback` 冲突；修 `notification-user-guide.md:271` 的"HTML 方言"；更新事件数量 41→44 | 文档/能力口径漂移 | 文档评审 |

### 5.2 **不需要改**的部分（避免过度设计）

1. **TG 与企微 Webhook 的内容层已对齐**：两者共用 `BlockRenderer.render()` 骨架（标题/级别/详情/块），无需为"对齐"重写渲染器。
2. **飞书/钉钉**：不在本任务对齐范围（用户只要求"企微不能少于 TG"）；且飞书卡片已具备级别颜色/表格/按钮，字段最全。
3. **交互按钮 / 图片 / 附件**：见 §4.4，属"系统没做" ⇒ 不要求对齐。
4. **列表符号 `•` vs `-`、TG 特殊字符转义反斜杠**：纯排版差异，不是信息量差异。
5. **分片条数差异**：属渠道上限差异，内容不丢，不做统一（用户判据是"信息量"）。

### 5.3 验证建议（落地时按此验收）

- 单元/契约：新增/扩展 `tests/test_notification_renderer.py`（已有跨渠道渲染基础设施）——对 27 个 warning/error 事件断言"企微卡片含级别前缀"；对 7 个带 link 事件断言"企微卡片含 link"；对 5 个 ListBlock 事件断言"卡片含 共 N 条"。
- 回归：`python -m pytest tests/test_notification_e2e.py tests/test_notification_renderer.py tests/test_notification_wechat_card.py tests/test_notification_link_level_render.py -q`。
- 门禁：`bash scripts/check_all.sh --fast --guards --local`（涉及 `pilotstd/core/`，注意 G-045/G-046/G-047；`scripts/generate_capabilities.py` 是否需同批按其触发条件判断）。
- 部署后：只读复核 `/api/notification/logs` 的 `auto_backup` telegram 行 status、以及一条 warning 事件在企微侧的实际呈现（需人工确认，脚本无法读渠道侧最终文本）。

---

## 6. 实发样本（生产，只读；已脱敏）

> 取数方式：`GET /api/notification/logs?page=1&page_size=100` + 只读 `SELECT`（经 `/query` 只读闸门）+ `GET /api/notification/{policy,channels,config}`。**未做任何写操作**；IP 末段已掩码、标准号已泛化。

### 6.1 事件覆盖面（生产 `notification_log` 全量 `event_type` 分布，23 种）

`batch_summary 1499`、`security_alert 297`、`task_result 209`、`expire_standard_moved 100`、`daily 92`、`announce_fetch_summary 50`、`announcement_fetch_complete 50`、`scan_empty 46`、`standard_status_changed 44`、`task_failure 34`、`scan_complete 32`、`notification_delivery_failed 28`、`archive_complete 24`、`standard_first_registered 24`、`announcement_check_complete 20`、`anomaly_alert 16`、`schedule_reminder 14`、`auto_backup 8`、`notification_credential_changed 7`、`test 7`、`batch_download_complete 4`、`task_progress 2`、`auto_pipeline_summary 1`。

⚠️ **注意**：前 7 个是**通知类别名**而非业务事件名（见 §4.3 横切问题 1）——**不能用日志 `event_type` 反推"某事件没发过"**。

### 6.2 同事件双渠道对照（wechat vs telegram）——日志层内容一致

| 事件 | 渠道 | sent_at | 标题 | body（节选，原样） |
|------|------|---------|------|--------------------|
| 公告检查完成 | telegram | 2026-11-24T01:00:45 | 公告检查完成 | `⚠️ 警告 / 公告检查完成 / 来源：定时 / 公告总数：0，国标：0，行标：0，地标：0，涉及标准：0 / 距上次成功抓取已约 519 小时，本次已开启回看补抓。` |
| 公告检查完成 | wechat | 2026-11-24T01:00:35 | 公告检查完成 | **与上一行逐字相同** |

⇒ **日志记录的"消息源内容"两渠道一致**；渠道差异只发生在渲染层（日志不存渠道最终文本，见 §6.5）。

### 6.3 实际内容片段（脱敏）

**样本 A（业务事件，id=4632/4631，2026-11-24）**
```
标题：公告检查完成
body：⚠️ 警告
      公告检查完成

      来源：定时

      公告总数：0，国标：0，行标：0，地标：0，涉及标准：0

      距上次成功抓取已约 519 小时，本次已开启回看补抓。
```
（动作=公告检查；对象=来源（定时）；结果=计数 + "距上次抓取 519 小时"，**满足动作+对象+结果**）

**样本 B（聚合摘要退化，id=4619，wechat，2026-11-22 —— 负样本）**
```
标题：登录失败告警
body：📦 聚合通知（2 条）
      • ⚠️ 警告
      • ⚠️ 警告
```
（两条安全告警被聚合后，**日志正文只剩级别前缀**，动作/对象/结果全部丢失 —— 对应 §4.3 横切问题 2）

**样本 C（TG 整条丢失，id=2034，telegram，2026-10-26 —— 负样本）**
```
标题：自动备份成功
status：failed
error_msg：expected string or bytes-like object, got 'float'
```
（对应 §4.0 P0-1；同一时刻的 wechat 行是 success）

### 6.4 生产渠道/配置现状（只读）

| 项 | 值 | 说明 |
|---|---|---|
| 企微 | `enabled=true`，`webhook_url=""`，`corpid/agentid/corpsecret` 已配置（密钥掩码） | ⇒ **应用形态，走 `template_card`**（`channels/wechat.py:76-84`） |
| Telegram | `enabled=true`，`bot_token` 已配置、`chat_id` 已配置（不回显） | 单一形态 |
| 钉钉/飞书 | `enabled=false`、字段全空 | 生产未启用（与本任务无关） |
| 策略 | 企微=**类别层 10 类全开**；TG=**逐事件 36 个** | 事件覆盖 企微 ≥ TG；但单条信息量 企微 < TG |
| `notification.web_base_url` | **未取证**（`GET /api/notification/config` 不返回该键；默认空，`defaults.py:68`；诊断端点 `actions` 列在占位落库时写死为空，不能据此判定，见 §6.5） | 若未配置：两渠道都**没有**[查看详情]按钮/链接，只有一段"请前往 Web 端…"文本提示（`_links.py:85-94`） |

### 6.5 证据局限（必须明说）

1. **未取到"渠道侧最终收到的原文"**：`notification_log` 只存 `title`/`body`（构建器/聚合摘要产物），**不存各渠道渲染后的文本**（`_manager_ops.py:58-119`）。因此 §2/§3 的渠道差异结论 = **真实构建器 + 真实渲染器实跑**（`C:\Temp\p1_render_probe.py`，44 事件全量），不是从生产消息里截出来的。
2. **未截屏企微/TG 客户端**：生产写操作/发测试消息均属红线，本次不做；如需截图验收，需维护窗口发一条测试通知。
3. **生产日志的 `body` 有 55% 为空**（最近 100 行：empty 55 / 1-200 字 43 / >200 字 2）：与聚合/历史版本路径混用有关；不影响"无 blocks 事件"的模板判断（本报告以代码路径为准）。
4. **`auto_backup` 生产历史既有 failed（id=2034，float TypeError）也有 success 行**：success 行（id=4628/4381/3987/2473，`event_type=auto_backup`）的载荷形态与当前 scheduler 的 float 传参**未能解释一致**（可能来自手动/不同路径），已在 §4.0 标注为"生产实证 1 条失败 + 代码路径必然失败"；**建议修复后以新日志复核**。
5. `notification.web_base_url` 生产取值未取证 ⇒ 表内 `A`（链接型动作）标注"仅当已配置"，两种情形都已给出。

---

## 7. 附：复现方式与未取证项

### 7.1 复现命令（均为只读，产物在仓库外 `C:\Temp\`）

```powershell
cd D:\PilotStd
python C:\Temp\p1_render_probe.py      # 44 事件 × 四渠道真实渲染 → p1_render_samples.{json,md}
python C:\Temp\p1_autobackup_check.py  # auto_backup 的 TG TypeError 最小复现
python C:\Temp\p1_notify_prod_probe3.py  # 生产只读日志 → p1_notify_prod.json
python C:\Temp\p1_prod_sql2.py         # 生产只读 SQL（TypeError 行 / 事件分布）→ p1_prod_sql2.json
python C:\Temp\p1_prod_channels.py     # 生产渠道/配置（只读）
python C:\Temp\p1_prod_policy.py       # 生产策略（只读）
```

### 7.2 未取证项（明确留白，不作结论）

| # | 项 | 原因 |
|---|----|------|
| 1 | 企微模板卡片 `vertical_content_list` 的**平台条数/长度上限** | 官方文档未取到；代码未做条数上限，仅"卡片拒收→文本降级"兜底（`channels/wechat.py:79-84`） |
| 2 | `notification.web_base_url` 的生产取值 | 配置接口不暴露；诊断端点 `actions` 列不可靠（占位落库早于 `attach_web_actions`） |
| 3 | 生产渠道侧**最终文本** | 日志不存渲染后文本（§6.5-1） |
| 4 | 企微是否真的支持回调（能力自述冲突） | `channels/wechat.py:241` False vs `interaction.py:53` True；本任务只结论"出站按钮不适用"，入站回调未核实 |
| 5 | `auto_backup` 生产 success 行的载荷来源 | 与当前 scheduler float 传参矛盾，未取到当时镜像/载荷（§6.5-4） |

---

*本报告只写本文件；未修改任何代码/配置/其他文档，未 commit/push。*
