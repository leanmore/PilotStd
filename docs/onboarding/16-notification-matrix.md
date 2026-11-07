# 16 · 通知事件 × 渠道矩阵（44 事件）

> 来源：`event_spec_data.py` 的 44 个 `EventSpec`；渠道默认值取自 `default_channels`。
> **实际发送还受 `notification_policy` / 用户订阅 / 静音 / 聚合影响**；本表不是“线上一定发到这些渠道”。

| # | 事件 | 分类 | 微信 | Telegram | 钉钉 | 飞书 | 级别 |
|---|---|---|---|---|---|---|---|
| 1 | `standard_status_changed` | schedule_reminder | ✓ |  |  |  | info,warning,error |
| 2 | `standard_first_registered` | task_result |  |  |  |  | info |
| 3 | `validity_batch_report` | batch_summary | ✓ |  |  |  | info,warning |
| 4 | `validity_round_summary` | batch_summary | ✓ |  |  |  | info |
| 5 | `validity_standard_failed` | anomaly_alert | ✓ |  |  |  | error |
| 6 | `validity_system_failed` | anomaly_alert | ✓ |  |  |  | error |
| 7 | `date_reminder` | schedule_reminder | ✓ |  |  |  | info |
| 8 | `scan_complete` | task_result |  |  |  |  | info,warning |
| 9 | `scan_empty` | task_result |  |  |  |  | info |
| 10 | `auto_scan_failed` | batch_summary | ✓ |  |  |  | error |
| 11 | `batch_query_summary` | batch_summary |  |  |  |  | info,warning |
| 12 | `query_failed` | task_failure |  |  |  |  | error |
| 13 | `query_empty` | batch_summary |  |  |  |  | warning |
| 14 | `batch_download_complete` | batch_summary | ✓ |  |  |  | info,warning |
| 15 | `download_failed` | task_failure |  |  |  |  | error |
| 16 | `normalize_complete` | batch_summary |  |  |  |  | info |
| 17 | `normalize_failed` | task_failure |  |  |  |  | error |
| 18 | `archive_complete` | batch_summary | ✓ |  |  |  | info |
| 19 | `archive_failed` | task_failure |  |  |  |  | error |
| 20 | `archive_abandoned` | task_result |  |  |  |  | error |
| 21 | `expire_standard_moved` | task_result |  |  |  |  | info |
| 22 | `replacement_not_found` | task_failure |  |  |  |  | warning |
| 23 | `announcement_fetch_complete` | user_activity | ✓ |  |  |  | info |
| 24 | `announcement_check_complete` | user_activity | ✓ |  |  |  | info,warning,error |
| 25 | `announcement_fetch_failed` | user_activity |  |  |  |  | error |
| 26 | `announce_fetch_summary` | user_activity |  |  |  |  | info,warning |
| 27 | `auto_backup` | anomaly_alert | ✓ |  |  |  | info,error |
| 28 | `image_update_available` | anomaly_alert |  |  |  |  | info,error |
| 29 | `trust_ip_update` | security_alert |  |  |  |  | info,warning |
| 30 | `worker_error` | anomaly_alert |  |  |  |  | error |
| 31 | `task_execution_failed` | anomaly_alert |  |  |  |  | error |
| 32 | `quota_exhausted` | anomaly_alert |  |  |  |  | warning |
| 33 | `notification_delivery_failed` | system_health | ✓ |  |  |  | error |
| 34 | `desktop_toast` | system_health |  |  |  |  | info,warning,error |
| 35 | `favorite_created` | user_activity |  |  |  |  | info |
| 36 | `task_progress` | task_progress | ✓ | ✓ | ✓ | ✓ | info |
| 37 | `download_started` | task_progress |  |  |  |  | info |
| 38 | `download_complete` | task_result |  |  |  |  | info |
| 39 | `favorite_abandoned_summary` | user_activity | ✓ |  |  |  | warning |
| 40 | `notification_credential_changed` | security_alert |  |  |  |  | warning |
| 41 | `security_password_changed` | security_alert |  |  |  |  | warning |
| 42 | `security_token_refreshed` | security_alert |  |  |  |  | warning |
| 43 | `security_login_failed` | security_alert | ✓ |  |  |  | warning |
| 44 | `auto_pipeline_summary` | batch_summary |  |  |  |  | info |

## 关键事实

- **44 个事件**；`task_progress` 默认四渠道全开，其余大多默认空/仅微信。
- “默认空”不等于“不能发”：用户策略/`notification_policy` 可以显式订阅；线上规则以 `/api/notification/config` 为准。
- 线上规则当前以 Telegram 为主（`archive_complete`/`standard_status_changed` 等），这是用户策略覆盖，不是 EventSpec 默认值。
- 聚合：`aggregate` 走聚合器；`task_progress` 默认四渠道但受分档节流/静音影响。
- 重试：Webhook/文本路径走基座 `_with_retry`；钉钉企业卡片、飞书应用消息目前单次（Q5）。

## 待补

- 逐事件 builder 的 payload/正文/动作；
- `notification_policy` 的按用户/按事件订阅矩阵；
- 静音/聚合/分档节流的端到端实测。
