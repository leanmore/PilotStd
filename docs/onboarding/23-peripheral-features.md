# 23 · 外围功能细分清单

> 目的：把主链之外的收藏、待确认、任务、上传/导出、备份、用户/权限、设置/缓存/审计/质量/微信 IP 逐项列清。  
> 状态：✅ 主流程已读；◐ 只读入口/关键分支；○ 仅清单。

---

## 一、收藏下载

| 项 | 事实 |
|---|---|
| API | `POST /api/favorites`、`GET /api/favorites`、`POST /api/favorites/batch-status`、`GET /api/favorites/export` |
| 表 | `user_favorites`（收藏记录）、`favorite_downloads`（下载状态机） |
| 链路 | `favorite_download.download_to_inbox()`：类别闸/版权闸 → 下载到 Inbox → 扫描/归档 → `file_index` 确认 |
| 状态 | `pending` → `downloading` → `archiving` → `done`；失败 `failed`；业务终态 `abandoned` |
| 业务终态 | `FavoriteSkip`：非国标、采标版权限制 → `abandoned`，不按失败重试 |
| 通知 | `download_started` / `download_complete` / `download_failed` / `favorite_abandoned_summary` |
| 注意 | `FavoriteSkip` 不是失败；不要把它计入重试窗口 |

---

## 二、待确认

| 项 | 事实 |
|---|---|
| API | `GET /api/pending`、`POST /api/pending/requery` |
| 表 | `pending_lookup`、`download_queue` |
| 状态 | `pending` / `resolved` / `manual_required` |
| 重查 | `requery_count`；达到上限转 `manual_required` |
| 下载等待 | `download_queue`：`waiting` → `done`；`expected_available` 公开期 |
| 注意 | `download_queue` 是“等待公开期队列”，不是下载执行队列 |

---

## 三、任务中心

| 项 | 事实 |
|---|---|
| API | `GET /api/tasks`、`GET /api/tasks/runs`、`GET /api/tasks/{task_id}`、`POST /api/tasks`、`POST /api/tasks/{id}/retry`、`POST /api/tasks/{id}/cancel` |
| 表 | `task_queue`、`pipeline_runs` |
| 状态 | `pending` / `running` / `paused` / `completed` / `failed` / `cancelled` |
| 原子认领 | `TaskQueue.start()`：只有 pending→running 成功者执行 |
| 未实现 handler | 默认 `_unimplemented` → FAILED，不永久 pending |
| 注意 | `task_queue` 有表，但真实下载 handler 仍不完整；与 Web 五段式 `pipeline_runs` 不是同一套 |

---

## 四、上传 / 导出

| 功能 | 事实 |
|---|---|
| 上传 | `POST /api/upload`，主要给登录背景/图片；`_validate_image` 校验扩展名 + 内容 |
| 静态背景 | `GET /api/backgrounds/{filename}`、`GET /api/login-background` |
| 导出 | `GET /api/export/standards?format=json|csv` |
| 注意 | 上传不是“标准文件上传入口”；标准文件仍走 Inbox/扫描 |

---

## 五、备份

| 项 | 事实 |
|---|---|
| API | `GET /api/backup/list`、`POST /api/backup/create`、`GET /api/backup/download/{name}` |
| 权限 | admin-only；写操作有审计 |
| 目录 | `data/backups/` |
| 恢复 | **无恢复 API**；停服务手工替换 |
| 注意 | 列表/创建/下载都可审计；恢复必须另走维护流程 |

---

## 六、用户 / 权限 / 多用户

| 项 | 事实 |
|---|---|
| API | `POST /api/login`、`POST /api/auth/register`、`GET/POST/DELETE /api/users`、`PUT /api/users/password` |
| 表 | `users`、`api_keys`、`user_credentials`、`user_preferences`、`user_settings`、`user_layouts` |
| 角色 | `admin` / `user`；`require_role` 控制写端点 |
| 鉴权 | session cookie + CSRF；静态 token 不是当前主路径 |
| 多用户 | 通知/收藏/偏好按 `user_id`；但部分旧通知仍按 system/默认用户 |
| 注意 | 角色矩阵/用户隔离尚未逐端点核完 |

---

## 七、设置 / 缓存 / 审计 / 质量 / 微信 IP

| 功能 | 入口 | 事实 |
|---|---|---|
| 设置 | `GET/PUT /api/settings`、`/api/settings/sites`、`/api/settings/schema`、`/api/settings/token` | 点分隔 JSON；站点覆盖；静态 token 刷新 |
| 缓存 | `GET/PUT /api/cache/config`、`GET /api/cache/stats`、`POST /api/cache/cleanup` | `CacheManager`：版本 + LRU；`standard_info_cache` / `announcement_record` / `validity` |
| 审计 | `GET /api/admin/audit` | `audit_logs`；管理员操作 |
| 质量 | `POST /api/quality/run` | 质量检查/违规项；只读检查 |
| 微信 IP | `GET/PUT /api/wechat-ip/config`、`POST /api/wechat-ip/check`、`GET /api/wechat-ip/status` | 企微可信 IP 配置/检查 |
| 调度器 | `GET /api/scheduler/status`、`/history`、`/history/stats` | APScheduler 状态/历史 |
| 系统资源 | `GET /api/system/resources`、`/api/system/version` | 磁盘/版本 |

---

## 八、结论

- 收藏/待确认/任务/备份/设置/缓存/审计/质量/微信 IP **入口和关键表已清**；
- 但收藏重试、待确认重查上限、任务真实消费方、用户多租户隔离、上传/导出边界仍未逐行读；
- 这些属于“功能地图已建、实现细节未穷尽”，不是完全未知。
