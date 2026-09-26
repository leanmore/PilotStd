# 模块文档：核心引擎（Core）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/core/` |
| G-031 映射 | `pilotstd/core/`（2026-09-25 落地：`DOC_SYNC_MAP` 已含该条，改任何 core 文件都会要求同步本文件） |
| 核心类 | `Database` / `ConfigManager` / `CacheManager` / `NotificationManager` |
| 子模块数 | 73 个 `.py`（config / db / notification / 安全 / 工具） |
| Schema 版本 | `CURRENT_SCHEMA_VERSION = 60`（`db/_constants.py`） |
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
- **配置**：点分隔键（如 `network.timeout`）持久化到 JSON，写时原子替换；frozen 环境下目录回退到 `%APPDATA%/PilotStd`。**下载节奏参数** `download.batch_size / long_rest / max_workers / max_retries / min_delay / max_delay` 由 facade 构造 `DownloadEngine`/`SessionManager` 时读取，手动批量下载与收藏下载链共用同一口径（暂不暴露 Web/Win 界面）。**定时任务键** `tasks.*_enabled` + `tasks.*_cron` 是三方一致契约：`settings_schema.py`（登记）↔ `docker/api/settings.py::_SCHEDULED_JOBS`（读写成对 + 保存时重排）↔ `docker/scheduler.py::start_scheduler()`（启动时注册），任一环漏项都会表现为"设置页改了不生效"（TD-20）。
- **通知**：事件驱动 → 渠道独立适配（企业微信/飞书/钉钉/Telegram），支持聚合缓冲与桌面格式化。模板文案统一走 i18n 层级键且**在调用期取 `t()`**（模块级求值会把语言固化在 import 时刻，运行时切换语言失效）；状态类判定使用数据口径（`_format_utils.is_abolished_status`），**禁止拿展示文案参与逻辑比较**（en/zh_TW 下 `t(...)` 与数据中的中文状态永不相等）；渲染层 / 聚合层 / 桌面层 / 渠道层的用户可见文案亦已外置为 `notification.renderer.*`、`notification.aggregated.body.*`、`notification.desktop.level.*`、`notification.channel.*`、`notification.channel_test.*`、`notification.manager.*` 键族；发送层不再追加标准号（与 telegram 同口径 `57f58a6c`，避免与构建器渲染重复）。构建器按「语义阶段」分文件（2026-09-26 G-010 治理）：`_builders_batch.py` 只留下载/收藏/批次类，`_builders_task_results.py` 承接扫描/查询/归档/规范化/状态迁移/公告抓取类——两者**无共享模块级符号**（AST 实测），故拆分不产生反向依赖；调用方一律经 `_message_builders.py` 重导出，增删构建器文件不需要改管理器。管理器本体同轮拆出 `_manager_ops.py`（写发送日志 / 日志分页查询 / 已读标记 / 未读计数 / 过期清理 / WebSocket 广播）：这 6 个方法只依赖数据库连接与 WS 回调，与「事件 → 渠道分发」主流程无共享局部状态。**采用组合而非继承**——`tests/test_architecture_mixin_guard.py` 明令除 `_WindowLifecycleMixin`（Qt 硬约束）外禁止新增 Mixin，并指定 Composition（ADR-010）；第一版为换取“调用点零改动”用了 Mixin，被该守护测试拦下后改为 `self.ops = NotificationOps(self)`，对外接口相应改为 `mgr.ops.get_logs(...)` 等（`docker/api/notification.py`、`docker/scheduler.py`、测试已同步）。ops 持有宿主引用而不是拷贝属性：`_ws_broadcast` 可被重绑，只有调用期读取才与拆分前语义一致。
