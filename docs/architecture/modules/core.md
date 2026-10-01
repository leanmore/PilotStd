# 模块文档：核心引擎（Core）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/core/` |
| G-031 映射 | `pilotstd/core/`（2026-09-25 落地：`DOC_SYNC_MAP` 已含该条，改任何 core 文件都会要求同步本文件） |
| 核心类 | `Database` / `ConfigManager` / `CacheManager` / `NotificationManager` |
| 子模块数 | 74 个 `.py`（新增 `status.py`：状态值权威字典，#32-A）（config / db / notification / 安全 / 工具） |
| Schema 版本 | `CURRENT_SCHEMA_VERSION = 61`（`db/_constants.py`） |
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
│   └── _migrate_*.py          # v2~v60 各版本迁移实现（大版本拆分独立文件，控 G-010）
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
│   ├── manager.py             # NotificationManager：事件 → 渠道分发 + 聚合装配
│   ├── _manager_ops.py        # 日志/查询/清理/WS 广播（组合式 NotificationOps，2026-09-26 拆出）
│   ├── channels/              # wechat / feishu / dingtalk / telegram 渠道适配
│   ├── aggregate_buffer.py    # 聚合缓冲（窗口内合并同类事件）
│   ├── channel.py / events.py / _policy.py / _credentials.py
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
│   ├── file_index.py / _file_index_query.py
│   ├── file_utils.py / download_utils.py / export_utils.py
│   ├── std_utils.py           # 标准号分类（classify_std_code → "gb" 等）
│   ├── context.py / logger.py / project.py / settings_utils.py
│   └── notification_aggregator.py
```

## 关键机制

- **数据库迁移**：`Database.__init__` → `_run_migrations()` 按 `CURRENT_SCHEMA_VERSION`（当前 **60**）顺序执行未完成迁移；迁移函数注册于 `MIGRATIONS` 字典，执行结果（版本 + 校验和）写入 `_schema_version`；每次新增迁移需 `_constants.py` 版本号 +1 并同步本文件——**该同步自 2026-09-25 起由 G-031 强制**（`scripts/check_g_031_docs_sync.py` 的 `DOC_SYNC_MAP` 含 `pilotstd/core/` → 本文件；此前只有文档里的口头约定，没有门禁拦截）。新增迁移涉及 `CREATE INDEX` / `ALTER TABLE` 等结构操作时，先查 `sqlite_master` 确认表存在再执行（防御从旧版本跳跃升级场景，参考 v53/v59 实现）。**迁移校验和的三级语义**（2026-09-26 修正，技术债 #28）：`_schema_version.checksum` 存的是**标准化哈希**（`norm_checksum`，剥离注释/空行/行首缩进）；校验时 ① 存储值 == 标准化值 → **通过**（注释/空行变化不改变标准化值，故「只改注释」同样放行）；② 存储值 == **当前 raw 哈希**（历史 raw 口径、源码未变）→ WARNING + 自愈为标准值；③ 其余 → **抛 `DatabaseError` 阻断启动**（P-106「已执行迁移源码不可变」由此真正生效）。**不要**改回「当前源码 raw != norm 就自愈」：`norm_source()` 去缩进使任何带缩进函数恒有 raw != norm（实测 59/59），那会让第 ③ 条永不可达。**v60**（`_migrate_v60_drop_favorite_retry_columns.py`）是首个 `DROP COLUMN` 迁移：删 `user_favorites.archive_retry_count`/`last_archive_attempt` 两列死列（技术债 #16 残留，唯一读取方随 #16 旧响应键一并删除）。依赖 `DROP COLUMN` 需 SQLite ≥ 3.35（本地 3.50.4、容器基础镜像 `python:3.12-slim` 的 Debian 自带 libsqlite3 ≥ 3.40）；为防旧库无法删列时**阻断启动**，删列失败降级为告警日志（两列零读取方，留下只是 schema 未收敛）。
- **配置**：点分隔键（如 `network.timeout`）持久化到 JSON，写时原子替换；frozen 环境下目录回退到 `%APPDATA%/PilotStd`。**写盘语义（#31-P2 / R14-3a，2026-10-01）**：`ConfigManager.__init__ → _load()` **仅在①文件不存在（首次运行）②补默认值/迁移旧键实际改动了内存态** 时写盘；已存在且内容完整的配置**构造后零写盘**；`set()` 只改内存，需显式 `save()` 才落盘；损坏文件仍先备份 `config.json.corrupted.<ts>` 再以默认值初始化并写盘。**动机与量化**：原实现无条件 `save()`＝“每构造一次 = 读一次 + 写一次”，而热路径 `query/routing/scorer.py::get_profile()` 每次新建实例 → 单批查询实测 **save() 135 次／get_profile 577 ms**（≈519 KiB 无谓覆盖写）；修复后 **save() 2 次／153 ms**，同时大幅收窄“多实例 last-writer-wins 覆盖用户刚改配置”的窗口。契约由 `tests/unit/core/config/test_manager_dirty.py`（7 例：首建写盘／完整则零写盘／补默认值写一次／旧键迁移写一次／set+save 持久化／损坏备份／reload 零写盘）锁定。**下载节奏参数** `download.batch_size / long_rest / max_workers / max_retries / min_delay / max_delay` 由 facade 构造 `DownloadEngine`/`SessionManager` 时读取，手动批量下载与收藏下载链共用同一口径（暂不暴露 Web/Win 界面）。**定时任务键** `tasks.*_enabled` + `tasks.*_cron` 是三方一致契约：`settings_schema.py`（登记）↔ `docker/api/settings.py::_SCHEDULED_JOBS`（读写成对 + 保存时重排）↔ `docker/scheduler.py::start_scheduler()`（启动时注册），任一环漏项都会表现为"设置页改了不生效"（TD-20）。 **共享实例与失效通知数据流（#31-P1 / R14-3b，2026-10-01）**：`manager.get_shared_config(path=None)` 按**绝对路径**缓存 ConfigManager 实例（`_SHARED_INSTANCES`），热路径 `query/routing/scorer.py::get_profile()`、站点配置 `query/site_config/_loader.py`、统一访问层 `ConfigService` 均从它取实例（原先各自新建）。**失效链**：`ConfigManager.save()` 原子写盘成功后 → `_publish_config_written(self)` → ① 若缓存中的实例**不是写入者**（GUI 设置页 `ui/core/handlers/_settings*.py`／Web `docker/api/settings.py` 各持独立实例）→ 从缓存移除（陈旧）；② 无论哪种情况都同步回调 `_INVALIDATION_LISTENERS`（参数＝配置绝对路径）→ 站点配置模块的清缓存回调把 `_site_config_cache` 置 None → 下次读取重建即拿到新值。`invalidate_shared_config(path)` 供“外部改动配置文件”的场景显式失效。**明确不用基于时间的静默 TTL**（会掩盖“配置已改但读不到”的 bug）；`_SHARED_LOCK` 为**可重入锁**——首次运行会在 `_load()` 内写盘并发布通知（同线程重入），重入锁同时保证同一路径并发首次获取只产生一个实例。契约由 `tests/unit/core/config/test_manager_shared.py`（8 例）与 `tests/unit/query/routing/test_scorer_hot_path_config.py`（4 例：热路径构造 ≤2／稳态 0 构造／GUI 写盘后热路径读到新值／站点缓存被清）锁定。 **状态值字典（#32-A / R14-4a，2026-10-01）**：`core/status.py` 是状态值的**权威字典**——`Status` 枚举的 value 与现网中文字符串**逐字一致**（零行为变化，API/DB/前端比较全部兼容）；`STATUS_I18N_KEYS` / `STATUS_EN_KEYS` 为 B/C 阶段「后端英文枚举 + 前端 enum→i18n key」预留映射脚手架；`normalize_status()` 提供 `废止` → `已废止` 别名归一；命名集合（`ABOLISHED_STATUSES` / `ABOLISHED_STATUSES_WITH_EXPIRED` / `EXPIRED_STATUSES` / `NON_OVERRIDABLE_STATUSES` / `API_VALID_STATUSES`）收敛了原先散落在 9 处的容器定义（`manager/classifier.py`、`manager/facade/_organize.py|_query.py|_query_subsystem.py`、`organizer/mover.py`、`core/notification/_format_utils.py`、`ui/core/handlers/auto_flow_engine.py|query_flow_engine.py`、`docker/api/standards.py`），**取值集合与重构前逐一等价**（`tests/unit/core/test_status.py` 断言 4/5/3/含待确认/API-tuple 五种口径）。**本阶段不替换业务字面量**（B 阶段）、不改 DB 迁移脚本、不改 API 返回字符串。**R15 再保险（2026-10-01，随 T-35 观察项）**：`ConfigManager.save()` 在 `os.replace` **之前**把现有文件复制为 `config.json.bak`（失败不阻断写盘），`_load()` 解析失败时**优先**从该备份回滚（成功即 `save()` 回写并告警；备份不可用才退化为原有的「备份 `.corrupted.<ts>` + 默认值初始化」路径）——即在**不引入跨进程文件锁**的前提下，把"并发写丢一次配置"的恢复成本压到接近 0。**R15 补记（2026-10-01）**：`validity_checker.py::register_new_standard` 的 `INSERT` 原把状态写成 SQL 文本里的 `'未知'` （AST 口径的收敛覆盖不到），已改为占位符参数 `Status.UNKNOWN.value` —— 至此 `pilotstd/` 内**再无内嵌状态字面量**。**B 阶段（R14-4b，2026-10-01）起**：`pilotstd/core/**`（`validity_checker.py`／`file_index.py`／`_file_index_query.py`／`_validity_pipeline.py`）内的状态字面量已改引 `Status.*.value`（零行为变化、逐处等价）；同一收敛按域分批推进（query → manager → ui → docker）。**C 阶段（R14-4c，2026-10-01）**：状态字典成为**API 契约来源**——`status_key(value)` 把数据值映射为稳定英文键（active/upcoming/withdrawn/superseded/voided/expired/pending/unknown，未知回退 `unknown`），`resolve_status_filter(raw)` 让过滤入参**同时接受英文键与历史中文值**（老书签/旧前端不受影响）；`/api/standards/status`、`/api/query/results`、`/api/pending/requery` 的每条记录在原有中文 `status` 之外新增 `status_key`（**向后兼容**），前端据此做与界面语言无关的比较（原 13 处中文比较的 `i18n-allow` 豁免全部消除）。**v61 迁移（同批）**：`_migrate_v61_enum_status_defaults.py` 把 `file_index.status` / `standard_validity.status` 的**列默认值**收敛到字典（`Status.ACTIVE.value` / `Status.UNKNOWN.value`）——默认值已等于枚举值时**不重建表**（现网库全部命中，零数据搬动）；仅当出现漂移才走 SQLite 12 步重建修复并保留数据与索引；`CURRENT_SCHEMA_VERSION` 随之 60 → **61**。遵守 P-106：不改动 v2/v3/v16 等历史迁移源码。
- **通知渠道异常处理（2026-09-26）**：`notification/channels/{dingtalk,feishu,wechat}.py` 的错误响应体读取分支（`except Exception: pass`）统一为「记录 `read_exc` + 以 `<body 读取失败: ...>` 标记回填 `body` + `logger.debug`」，三个渠道的外层 `logger.warning` 统一补 `exc_info=True`。**动机**：原 `pass` 使"服务端未返回 body"与"body 读取失败"两种情形在日志里不可区分（都表现为 `body=`），且外层告警丢异常栈。捕获本身**不是**吞错——外层已设置 `last_error`、记录告警并 `return False`，故内层只影响诊断文本丰富度。全链路审计脚本的吞错计数由此从 3 归零（`scripts/audit_notification_chain.py --scope notification`）。
- **安全告警投递（2026-09-26，第 2 批安全审计闭环）**：新增 `notification/security_notifier.py`。**它绝不调用 `NotificationManager.send_event`**——凭证类告警必须在"新凭证落库之前"送达**旧**渠道，而 manager 路径的三重延迟会让告警流向攻击者控制的新地址：① 聚合缓冲（`notification.aggregate_enabled` 默认 True）只入队，实际发送推迟到窗口到期；② 静音时段命中时写入 `notification_queue` 表延后补发；③ `send_event` 首行受 `notification.enabled`（默认 False）门控。故该模块按"指定用户"读旧凭证 → 构造**临时渠道实例** → `concurrent.futures` 并发同步 `send()`（总超时 5s 封顶）→ 才允许调用方落库。三个新事件（`notification_credential_changed` / `security_password_changed` / `security_token_refreshed`）仍登记于 `events.py` 并配 `_builders_system.py` 构建器，但**有意豁免** `tests/test_notification_e2e.py` 的"必须有 send_event 触发点"契约（见该文件 `SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED`），投递正确性由 `tests/test_p0_security_endpoints.py` 锁定（含"send 必须先于 set_channel"的顺序断言）。紧急降级开关是**环境变量** `PILOTSTD_SECURITY_NOTIFY_ENABLED` 而非配置文件——凭证变更端点自身能写配置，放配置里等于给攻击者一个关闭告警的把手。`client_ip(request)` 对测试替身做类型校验（`MagicMock` 的任意属性都返回 Mock，直接入审计 detail 会让 `json.dumps` 崩溃）。
- **通知**：事件驱动 → 渠道独立适配（企业微信/飞书/钉钉/Telegram），支持聚合缓冲与桌面格式化。模板文案统一走 i18n 层级键且**在调用期取 `t()`**（模块级求值会把语言固化在 import 时刻，运行时切换语言失效）；状态类判定使用数据口径（`_format_utils.is_abolished_status`），**禁止拿展示文案参与逻辑比较**（en/zh_TW 下 `t(...)` 与数据中的中文状态永不相等）；渲染层 / 聚合层 / 桌面层 / 渠道层的用户可见文案亦已外置为 `notification.renderer.*`、`notification.aggregated.body.*`、`notification.desktop.level.*`、`notification.channel.*`、`notification.channel_test.*`、`notification.manager.*` 键族；发送层不再追加标准号（与 telegram 同口径 `57f58a6c`，避免与构建器渲染重复）。构建器按「语义阶段」分文件（2026-09-26 G-010 治理）：`_builders_batch.py` 只留下载/收藏/批次类，`_builders_task_results.py` 承接扫描/查询/归档/规范化/状态迁移/公告抓取类——两者**无共享模块级符号**（AST 实测），故拆分不产生反向依赖；调用方一律经 `_message_builders.py` 重导出，增删构建器文件不需要改管理器。管理器本体同轮拆出 `_manager_ops.py`（写发送日志 / 日志分页查询 / 已读标记 / 未读计数 / 过期清理 / WebSocket 广播）：这 6 个方法只依赖数据库连接与 WS 回调，与「事件 → 渠道分发」主流程无共享局部状态。**采用组合而非继承**——`tests/test_architecture_mixin_guard.py` 明令除 `_WindowLifecycleMixin`（Qt 硬约束）外禁止新增 Mixin，并指定 Composition（ADR-010）；第一版为换取“调用点零改动”用了 Mixin，被该守护测试拦下后改为 `self.ops = NotificationOps(self)`，对外接口相应改为 `mgr.ops.get_logs(...)` 等（`docker/api/notification.py`、`docker/scheduler.py`、测试已同步）。ops 持有宿主引用而不是拷贝属性：`_ws_broadcast` 可被重绑，只有调用期读取才与拆分前语义一致。
