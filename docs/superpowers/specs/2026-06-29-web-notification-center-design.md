# Web 端通知中心 — 设计文档 (PrimeVue)

日期：2026-06-29

## 目标

为 Web 端实现通知中心：铃铛图标 + 未读红点 + 下拉列表 + Toast 弹窗 + 日志页增强。

## 架构

```
useNotification (WebSocket + 状态管理)
    ├── NotificationBell.vue (铃铛 + Popover 下拉列表)
    ├── NotificationToastContainer.vue (PrimeVue Toast 容器)
    ├── NotificationLogsView.vue (DataTable + 已读标记 + 高亮)
    └── NotificationConfig.vue (Toast 开关 + 事件选择)

WebSocket → /api/notification/ws
    ├── 收到消息 → messages[] + toast.add()
    ├── 断开 → 自动重连 (5s, 最多10次)
    └── onMounted → connect(), onUnmounted → disconnect()
```

## 技术栈

PrimeVue 4 + Vue 3 + TypeScript + Vite + WebSocket

## 文件变更

| # | 文件 | 操作 |
|---|------|------|
| 1 | `web/src/composables/useNotification.ts` | 新建 |
| 2 | `web/src/components/NotificationBell.vue` | 新建 |
| 3 | `web/src/components/NotificationToastContainer.vue` | 新建 |
| 4 | `web/src/views/NotificationLogsView.vue` | 修改 |
| 5 | `web/src/components/NotificationConfig.vue` | 修改 |
| 6 | `web/src/api/notification.ts` | 修改 |
| 7 | `web/src/App.vue` | 修改 |
| 8 | `web/src/components/AppLayout.vue` | 修改 |
