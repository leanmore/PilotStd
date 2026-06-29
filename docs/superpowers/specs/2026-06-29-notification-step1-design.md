# 通知系统第一步补全 — 设计文档

日期：2026-06-29

## 目标

补全通知系统的 P1 已读标记（数据库+API）、P2 WebSocket 后端推送、P3 测试覆盖。

## 架构

```
notification_log 表 (v18 迁移新增 is_read 列)
      ↑
      │ 写入
      ▼
NotificationManager.send_event()
      │
      ├── 渠道发送（微信/钉钉/飞书/Telegram）
      ├── 写入 notification_log（含 is_read=0）
      └── WebSocket 广播（独立线程 + 新 event loop）
            │
            ▼
   NotificationConnectionManager
      │
      ├── /api/notification/ws (WebSocket 端点)
      └── broadcast() → 所有活跃连接

API 层:
  POST /api/notification/read  → 标记已读
  GET  /api/notification/logs  → 支持 is_read 筛选
```

## 关键技术决策

| # | 决策 | 理由 |
|---|------|------|
| 1 | WebSocket 广播用独立线程 + `asyncio.new_event_loop()` | `send_event()` 是同步方法，调度器调用时无运行中 event loop |
| 2 | 每次广播新建 daemon 线程 | 不阻塞主流程，广播失败静默降级 |
| 3 | 连接数为 0 时跳过广播 | 避免无意义开销 |
| 4 | 迁移 v18 ALTER TABLE ADD COLUMN | 遵循现有迁移框架（decorator 模式） |

## 文件变更

| # | 文件 | 操作 | 阶段 |
|---|------|------|------|
| 1 | `pilotstd/core/db.py` | 修改 — 迁移 v18 | P1 |
| 2 | `docker/api/notification.py` | 修改 — POST /read + GET /logs 增强 | P1 |
| 3 | `docker/websocket.py` | 新建 | P2 |
| 4 | `docker/app.py` | 修改 — 注册 WebSocket 路由 | P2 |
| 5 | `pilotstd/core/notification/manager.py` | 修改 — send_event 广播 | P2 |
| 6 | `tests/test_notification_manager.py` | 新建 | P3 |
| 7 | `tests/test_notification_api.py` | 新建 | P3 |
| 8 | `tests/test_notification_websocket.py` | 新建 | P3 |
| 9 | `tests/test_notification_db.py` | 新建 | P3 |
