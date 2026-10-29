# 多用户支持度盘点（2026-10-29，只读）

> 目的：为 A-21（按用户静音）与未来多用户改造提供结构依据。不改代码。

## 一、七维度

| 维度 | 现状 | 代码位置 | 缺口 |
|---|---|---|---|
| **用户体系** | **部分支持** | `users` 表（`pilotstd/core/db/_migrate_v16_v49.py:63`）：`id/username/password_hash/salt/role/must_change_password/created_at`；用户 CRUD `docker/api/users.py:45/52/98`；注册 `auth_register.py` | 业务层（通知、扫描、下载）默认"一个活跃用户"，没有"当前用户"上下文贯穿 |
| **认证授权** | **部分支持** | 登录 `/api/login` → `pilotstd_token` + CSRF；`AuthMiddleware`；`role` 字段默认 `user`；`ADMIN_ROLE` + `require_role`（`docker/auth.py:74`），覆盖审计/DB 管理/用户管理 | 只有 admin/user 两档；无细粒度权限；前端无用户管理入口 |
| **数据隔离** | **部分支持** | per-user：`user_preferences`、`user_settings`、`user_layouts`、`notification_policy`、`user_favorites`、`date_reminder_log`、`audit_logs`、`user_credentials`；**全局**：`notification_log`、`notification_queue`、`standards`/`file_index` 等 | 通知历史/队列无 `user_id`；`get_logs`（`_manager_ops.py`）无用户过滤 ⇒ 任何登录用户可看全部日志 |
| **用户偏好** | **部分支持** | `user_preferences` KV（per-user）；默认值在 `settings_manager.py`；静音时段 UI 写偏好 | 静音时段服务端读全局 `config.json`（A-20/A-21）；偏好与通知策略是两套 |
| **通知链路** | **部分支持 / 关键处不支持** | 渠道凭证 per-user（`user_credentials`，`_credentials.py:51`）；策略 per-user（`notification_policy`）；**manager 持有单一 `_user_id`**（`manager.py:78,194`）；`notification_queue`/`notification_log` 全局；静音全局配置 | 多用户并发时：队列、历史、静音、投递路由共享一个 manager 状态 |
| **并发/多会话** | **不支持** | 单 `NotificationManager` 绑定 `_user_id`；无 per-user manager/上下文；队列无租约 | 两个用户同时触发通知会共用队列与日志；无互斥/隔离 |
| **UI** | **部分支持** | 登录/注册页；`web/src/api/auth.ts` 有 `/users` CRUD；路由 `permission` 元数据 | 无用户管理/切换界面；管理 CRUD 未接线到视图 |

## 二、总结：真正支持多用户要改哪几层

| 层 | 要改什么 | 范围/难点 |
|---|---|---|
| **数据模型** | `notification_log`、`notification_queue` 加 `user_id`；迁移存量行（默认 1）；查询按 user_id 过滤 | 中等：迁移 + 所有读写点；但结构清晰 |
| **通知路由/队列** | manager 不能只有单一 `_user_id`：改为 per-user 实例或每次调用带 `user_context`；队列 release 按用户；聚合按用户 | **最难**：`manager` 是长生命周期单例，静音/聚合/补发都绑在它上面 |
| **配置** | 静音时段从全局 config 改为 per-user（A-21）；渠道凭证已 per-user | 中等；A-21 即此层 |
| **权限** | 细粒度（谁能改谁的凭证/策略）；admin 管理用户 | 中等；现有 role 可扩展 |
| **UI** | 用户管理页、用户切换/当前用户指示 | 低—中：纯前端 + 少量 API |

**最难的层：通知路由/队列**——不是表加列，而是"单例 manager + 全局队列 + 全局静音"三件事同时要拆；数据模型是它的前置。
