# 通知系统现状调查报告

> 调查日期：2026-07-01
> 调查范围：Web 端 (web/src/) + WinUI 端 (pilotstd/ui/)
> 状态：**只读调查，未修改任何代码**

---

## 1. Web 端

### 通知入口文件

| 入口 | 文件 | 类型 | 说明 |
|------|------|------|------|
| A | `web/src/composables/useNotification.ts` | **核心管道** | WebSocket 接收 + PrimeVue Toast 触发，含 localStorage 配置门控 |
| B | `web/src/views/SettingsView.vue` | 行内 Toast | 直接 `useToast()` 用于表单验证反馈 |
| C | `web/src/components/NotificationBell.vue` | 铃铛图标 | 消费 `useNotification()`，仅展示未读计数+下拉菜单 |
| D | `web/src/views/NotificationLogsView.vue` | 历史记录 | REST API 只读视图，无 Toast |

### 调用方式（核心流程）

```ts
// useNotification.ts — WebSocket 收到消息时触发 Toast
ws.value.onmessage = (event) => {
  const data = JSON.parse(event.data)
  const toastConfig = getToastConfig()  // 从 localStorage 读取
  if (toastConfig.enabled && toastConfig.events.includes(data.event_type)) {
    toast.add({
      severity: severityMap[data.level] || 'info',
      summary: data.title,
      detail: data.body,
      life: 5000,
      closable: true,
    })
  }
}
```

**技术栈**：PrimeVue `useToast()` + `ToastService` 插件，全局 `<Toast position="bottom-right" />`

### 设置页路径

`web/src/views/SettingsView.vue` — 14 个 Tab 的 SFC，含 "通知" Tab → 嵌入 `NotificationConfig.vue` 组件

### 存储机制现状

| 机制 | 用途 | 文件 |
|------|------|------|
| **localStorage** | Toast 弹窗配置（`notification_toast_config` 键） | `NotificationConfig.vue`, `useNotification.ts` |
| Pinia `useAppStore` | 主题/语言偏好 | `stores/app.ts` |
| Pinia `usePreferencesStore` | 通用键值偏好（3 层回退） | `stores/preferences.ts` |
| REST API | 通知渠道配置（webhook URL 等） | `api/notification.ts` → `PUT /api/notification/config` |

**关键发现**：Toast 配置绕过 Pinia，仅用 localStorage，不跨设备同步。

---

## 2. WinUI 端

### 通知入口文件

| 入口 | 文件 | 类型 | 说明 |
|------|------|------|------|
| A | `pilotstd/ui/controllers/*` (15+ 文件) | **模态弹窗** | `QMessageBox` 阻塞式对话框，遍布所有控制器 |
| B | `pilotstd/platform/notify.py` | **系统托盘 Toast** | `NotifyService` 单例，`QSystemTrayIcon.showMessage()` 非阻塞气泡 |
| C | `pilotstd/ui/widgets/notification_bell_widget.py` | **铃铛组件** | WebSocket 客户端 + 下拉菜单，显示最近 10 条通知 |

### 调用方式

```python
# 模态弹窗（阻塞）
QMessageBox.warning(self, "标题", "内容")
QMessageBox.information(self, "标题", "内容")

# 系统托盘 Toast（非阻塞）
NotifyService.get().show("标题", "消息", duration=5000)
NotifyService.get().show_warning("标题", "警告消息")

# 铃铛组件（被动查看）
self.notification_bell = NotificationBellWidget(self)
self.toolbar.addWidget(self.notification_bell)
```

### 设置页路径

`pilotstd/ui/pages/settings_page.py` — 左侧导航 + 右侧 `QStackedWidget` 多 Tab

**关键发现**：设置页**无通知 Tab**。通知渠道配置（webhook URL、启停开关）仅在 `config.json` 中存在，需通过 Web API 或手动编辑 JSON 配置。

### 存储机制现状

| 机制 | 用途 | 文件 |
|------|------|------|
| `ConfigManager` | 唯一配置存储（JSON 文件，Fernet 加密敏感字段） | `core/config/manager.py` |
| `notification.*` 键 | 渠道启停/URL/事件路由 | `core/config/defaults.py:53-74` |
| `appearance.*` 键 | UI 状态持久化 | 各处 |

---

## 3. 两端差异对比

| 维度 | Web 端 | WinUI 端 |
|------|--------|---------|
| **实时推送** | ✅ PrimeVue Toast（WebSocket → `toast.add()`） | ✅ 系统托盘气泡 (`NotifyService`) |
| **历史查看** | ✅ `NotificationLogsView` 表格 | ✅ `NotificationBellWidget` 下拉菜单 |
| **配置界面** | ✅ SettingsView "通知" Tab | ❌ 无通知设置页 |
| **配置存储** | localStorage (Toast) + Pinia + REST API | `ConfigManager` JSON 文件 |
| **非阻塞通知** | ✅ Toast（5s 自动消失） | ✅ 系统托盘气泡 |
| **阻塞对话框** | ❌ 无（Web 特性） | ✅ QMessageBox（15+ 控制器使用） |
| **去重机制** | ❌ 无 | ✅ `NotifyService._DEDUP_WINDOW = 3.0s` |
| **事件订阅过滤** | ✅ `notification_toast_config.events[]` | ❌ 铃铛显示全部事件 |

---

## 4. 实施建议

### Web 端 — 聚合器最佳插入点

**推荐位置**：`web/src/composables/useNotification.ts` 的 `ws.onmessage` 回调

现有代码已经在此处读取 localStorage 配置并过滤事件。聚合逻辑（频率限制、智能合并同类通知、暂停模式）直接在此处添加：

```ts
// 伪代码：在现有 ws.onmessage 之前插入聚合层
const aggregator = new NotificationAggregator(getToastConfig())
ws.value.onmessage = (event) => {
  const data = JSON.parse(event.data)
  const shouldShow = aggregator.shouldShow(data)
  if (shouldShow) {
    toast.add({ ... })
  }
}
```

聚合器需新增文件 `web/src/composables/useNotificationAggregator.ts`。

### WinUI 端 — 聚合器最佳插入点

**推荐位置**：`pilotstd/platform/notify.py` 的 `NotifyService.show()` 方法

现有代码已在此处做 3s 去重。扩展该方法为智能聚合器：

```python
class NotifyService:
    def show(self, title, msg, duration=5000):
        if self._aggregator and not self._aggregator.should_show(title, msg):
            return
        self._tray.showMessage(title, msg, icon, duration)
```

聚合器需新增文件 `pilotstd/platform/notification_aggregator.py`，从 `config.json` 读取 `notification.aggregation.*` 配置。

### 共享配置键（建议）

```json
{
  "notification": {
    "aggregation": {
      "enabled": true,
      "window_seconds": 60,
      "max_per_window": 5,
      "pause_until": null
    }
  }
}
```

Web 端从 Pinia/localStorage 读取，WinUI 端从 `ConfigManager` 读取。

---

## 调查真实性声明

- 已全面搜索 `web/src/` 目录下所有与 toast/notification/settings 相关的文件 ✅
- 已全面搜索 `pilotstd/ui/` 目录下所有控制器、页面、组件和平台服务 ✅
- 已确认 Web 端使用 PrimeVue Toast + localStorage 组合 ✅
- 已确认 WinUI 端使用 QMessageBox + QSystemTrayIcon + NotificationBellWidget 三层机制 ✅
- 调查过程中未修改任何代码文件 ✅
