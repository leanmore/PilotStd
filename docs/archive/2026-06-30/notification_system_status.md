# 通知系统实现状态报告

> 调查日期：2026-06-29 / 纯调查，未修改代码

---

## 1. 渠道发送层

### 1.1 目录结构

✅ 存在 [pilotstd/core/notification/channels/](pilotstd/core/notification/channels/)，含 5 个文件：

| 文件 | 大小 |
|------|------|
| `__init__.py` | 空 |
| `wechat.py` | 企业微信机器人 |
| `dingtalk.py` | 钉钉群机器人（支持 HMAC-SHA256 签名） |
| `feishu.py` | 飞书机器人（交互式卡片消息） |
| `telegram.py` | Telegram Bot API |

❌ 无 `email.py`、`web.py`、`sms.py`。

### 1.2 渠道实现

**全部 4 个渠道均为生产级实现**，均通过 `urllib.request.urlopen` 发起真实 HTTP API 调用，非占位桩。

| 渠道 | 状态 | 实现方式 | 关键代码 |
|------|------|---------|---------|
| WechatChannel | ✅ 完整 | POST markdown 消息到企业微信 webhook | [wechat.py:19-41](pilotstd/core/notification/channels/wechat.py#L19-L41) |
| DingTalkChannel | ✅ 完整 | POST markdown 消息 + 可选 HMAC-SHA256 签名验证 | [dingtalk.py:39-73](pilotstd/core/notification/channels/dingtalk.py#L39-L73) |
| FeishuChannel | ✅ 完整 | POST 交互式卡片消息，按级别分色（info/warning/error） | [feishu.py:19-57](pilotstd/core/notification/channels/feishu.py#L19-L57) |
| TelegramChannel | ✅ 完整 | POST 到 Bot API，`parse_mode=Markdown` | [telegram.py:20-46](pilotstd/core/notification/channels/telegram.py#L20-L46) |

### 1.3 注册状态

✅ 在 [manager.py:17-22](pilotstd/core/notification/manager.py#L17-L22) 中完整注册：

```python
_CHANNEL_CLASSES = {
    "wechat": WechatChannel,
    "telegram": TelegramChannel,
    "feishu": FeishuChannel,
    "dingtalk": DingTalkChannel,
}
```

`_init_channels()` 按 `notification.channels.{name}.enabled` 配置条件初始化，配置不可用时静默跳过（不阻断启动）。

---

## 2. 消息持久化

### 2.1 数据库表

✅ 存在 `notification_log` 表，通过迁移 v17 创建 [db.py:592-609](pilotstd/core/db.py#L592-L609)：

```sql
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    title TEXT,
    body TEXT,
    standard_number TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    error_msg TEXT,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

含两个索引：`idx_notif_sent_at`（按时间查询）、`idx_notif_event_type`（按事件类型筛选）。

❌ 无 `read`/`unread` 状态列——未设计已读/未读跟踪。

### 2.2 写入逻辑

✅ `send_event()` 在每次发送尝试后写入数据库 [manager.py:64-88](pilotstd/core/notification/manager.py#L64-L88)：

- 渠道未启用 → 记录 `status="failed"`, `error_msg="渠道未启用"`
- `channel.send()` 返回 True → 记录 `status="success"`
- `channel.send()` 返回 False → 记录 `status="failed"`, `error_msg="发送失败"`
- 发送过程抛异常 → 记录 `status="failed"`, `error_msg=str(e)`

`_log()` 方法 [manager.py:214-222](pilotstd/core/notification/manager.py#L214-L222) 统一执行 `INSERT INTO notification_log`。

---

## 3. 前端消费机制

### 3.1 前端组件

| 组件 | 路径 | 用途 |
|------|------|------|
| 通知配置组件 | [NotificationConfig.vue](web/src/components/NotificationConfig.vue) | 4 渠道卡片（webhook/密钥配置）+ 事件订阅 + 测试发送 |
| 通知日志查看器 | [NotificationLogsView.vue](web/src/views/NotificationLogsView.vue) | 分页日志列表 + 渠道/状态/日期筛选 + 详情弹窗 |

### 3.2 路由与导航

✅ 路由注册 [router.ts:12](web/src/router.ts#L12)，导航链接 [AppLayout.vue:19](web/src/components/AppLayout.vue#L19)

### 3.3 缺失的前端能力

| 功能 | 状态 | 说明 |
|------|------|------|
| 通知中心（铃铛图标 + 下拉列表） | ❌ 不存在 | grep `NotificationCenter`/`NotificationBell`/`*Bell*` → 零命中 |
| Toast 弹窗通知 | ❌ 不存在 | 无实时弹窗通知组件 |
| WebSocket/SSE 实时推送 | ❌ 不存在 | grep `websocket`/`EventSource`/`sse` → 零命中 |
| 未读计数轮询 | ❌ 不存在 | 无 `unread`/`poll` 机制 |
| 已读标记 | ❌ 不存在 | 无 `POST /api/notification/read` 端点 |

---

## 4. API 接口支持

全部端点位于 [docker/api/notification.py](docker/api/notification.py)：

| 方法 | 路径 | 行号 | 描述 | 状态 |
|------|------|------|------|------|
| GET | `/api/notification/config` | 19-64 | 读取配置（已屏蔽密码/令牌值） | ✅ |
| PUT | `/api/notification/config` | 67-82 | 更新配置并重新加载渠道 | ✅ |
| POST | `/api/notification/test` | 85-108 | 测试发送（支持参数覆盖） | ✅ |
| GET | `/api/notification/logs` | 111-156 | 查询日志（分页 + 渠道/状态/日期筛选） | ✅ |
| POST | `/api/notification/read` | — | 标记已读 | ❌ 不存在 |

---

## 5. 事件注册表

在 [events.py](pilotstd/core/notification/events.py) 中定义了 **14 个事件**，`_build_message()` 在 manager.py 中为每个事件提供了定制消息构造：

| # | 事件类型 | 触发场景 |
|---|---------|---------|
| 1 | `archive_complete` | 归档完成 |
| 2 | `standard_status_changed` | 标准状态变更 |
| 3 | `standard_expired` | 标准已废止 |
| 4 | `standard_first_registered` | 新标准首次登记 |
| 5 | `check_batch_complete` | 时效性检查批次完成 |
| 6 | `announcement_fetch_complete` | 公告抓取完成 |
| 7 | `auto_backup` | 自动备份完成/失败 |
| 8 | `announcement_check_complete` | 定时公告检查完成 |
| 9 | `batch_download_complete` | 批量下载完成 |
| 10 | `auto_scan_failed` | 定时扫描异常 |
| 11 | `validity_batch_report` | 时效性检查每次汇总（A2 新增） |
| 12 | `validity_round_summary` | 周期总结汇报（A2 新增） |
| 13 | `validity_standard_failed` | 单条标准检查失败（A2 新增） |
| 14 | `validity_system_failed` | 系统级异常（A2 新增） |

---

## 6. 集成点（`send_event` 实际调用位置）

| 文件 | 行号 | 事件 |
|------|------|------|
| `validity_checker.py` | 62, 98 | `standard_first_registered`, `standard_expired`, `standard_status_changed` |
| `download/engine.py` | 200 | `batch_download_complete` |
| `docker/scheduler.py` | 87 | `auto_backup` |
| `docker/api/announce.py` | 72 | `announcement_check_complete` |
| `docker/api/announcements.py` | — | `announcement_fetch_complete` |
| `docker/api/validity.py`（通过 run_validity_check） | — | `check_batch_complete`, `validity_batch_report`, `validity_round_summary`, `validity_system_failed`, `validity_standard_failed` |

`NotificationManager` 在 [facade.py:152](pilotstd/manager/facade.py#L152) 注入：`self.notification_mgr = NotificationManager(self.cfg, self.db)`

---

## 7. 测试覆盖

❌ 通知模块**完全无测试**。`tests/` 目录中搜索 `*notif*` / `notification` → 零命中。

---

## 8. 总体评估

### 成熟度矩阵

| 维度 | 状态 | 评估 |
|------|------|------|
| 渠道发送 | ✅ 完整 | 4 渠道全部生产级实现 |
| 消息持久化 | ✅ 完整 | SQLite 表 + 迁移 + 索引 + 每次发送都写日志 |
| 配置管理 | ✅ 完整 | GET/PUT API + 前端 UI + 参数掩码 |
| 测试发送 | ✅ 完整 | 支持参数覆盖的测试接口 |
| 日志查询 | ✅ 完整 | API 分页筛选 + 前端日志查看器 |
| 前端配置 UI | ✅ 完整 | 渠道卡片 + 事件订阅 + 测试按钮 |
| 事件体系 | ✅ 完整 | 14 个预定义事件 + 定制消息构造 |
| 集成接入 | ⚠️ 部分 | 已连接 5 个子系统；归档/扫描尚未接入通知 |
| 实时交付 | ❌ 缺失 | 无 WebSocket/SSE |
| 通知中心 | ❌ 缺失 | 无铃铛图标/下拉列表/toast |
| 已读/未读 | ❌ 缺失 | 数据库无 `read` 列，无标记已读 API |
| 邮件渠道 | ❌ 缺失 | 未实现 |
| 测试覆盖 | ❌ 缺失 | 零测试 |

### 完整度评分

**后端核心：85%**（发送 + 持久化 + 事件 + 配置全部完成）
**前端显示：55%**（配置和日志查看器完成，缺通知中心和实时推送）
**整体：70%**

### 关键缺口排序

| 优先级 | 缺口 | 影响 |
|--------|------|------|
| P1 | `POST /api/notification/read` + `notification_log` 增加 `is_read` 列 | 用户无法标记已读 |
| P2 | WebSocket/SSE 实时推送 | 通知无法实时到达浏览器 |
| P2 | 通知中心（铃铛 + 下拉 + toast） | 用户被动等待查看日志页面 |
| P3 | 邮件渠道 | 仅支持 IM 渠道，缺传统邮件通知 |
| P3 | 归档/扫描完成事件的 send_event 接入 | 已有事件定义但未接入 |
