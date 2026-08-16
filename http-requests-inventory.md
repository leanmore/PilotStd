# HTTP 请求迁移清单

> 阶段 2.1 扫描产物 — 依据第 1 层 route-scoped 取消机制，列出所有需迁移的 HTTP 请求。
> 扫描范围：`web/src/` 下所有 `.vue` / `.ts`。触发分类：onMounted / watch immediate / script 顶层 / 点击事件。

## 分类标准

- **[需迁移]**：走共享 `@/api/http` 实例（含拦截器 + AbortController），在 onMounted / watch 中触发，需加 `routeTag`。
- **[低优先级]**：走 `http` 但由点击事件触发，不会被路由切换误杀，迁移后享受路由级取消。
- **[原生 axios]**：直接 `import axios from 'axios'`，**不走 http.ts 拦截器**，不受取消机制影响，无需迁移（见末尾说明）。

---

## 路由: `/`

**HomeView** + dashboard widgets（各自 onMounted）

- [ ] `src/composables/useDashboard.ts:110` → `http.get('/user/preferences/layout:dashboard')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/StatsCard.vue:13` → `getStats()` → `http.get('/stats')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/SystemInfoCard.vue:16` → `http.get('/system/version')` + `http.get('/adapter/status')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/AdapterStatusCard.vue:63` → `http.get('/adapter/status')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/AdapterStatusQueryCard.vue:62` → `http.get('/adapter/status')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/AdapterStatusAnnounceCard.vue:66` → `http.get('/adapter/status')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/RecentAnnounceCard.vue:56` → `getAnnounceResults()` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/PendingItemsCard.vue:12` → `http.get('/pending')` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/TaskTrendCard.vue:17` → `getStats()` → routeTag: `/`
- [ ] `src/components/dashboard/widgets/SystemLogCard.vue:53` → `http.get('/logs')` → routeTag: `/`

## 路由: `/organize`

- [ ] `src/views/OrganizeView.vue:89` → `browse()` → `getFiles()` → `http.get('/files')` → routeTag: `/organize`

## 路由: `/pending`

- [ ] `src/views/PendingView.vue:66` → `ensure()` → `useQueryAdapters` → `http.get('/adapter/status')` → routeTag: `/pending`

## 路由: `/announce`

- [ ] `src/views/AnnounceView.vue:91` → `load()` → `getAnnounceResults()` → `http.get('/announce/results')` → routeTag: `/announce`
- [ ] `src/views/AnnounceView.vue:69` → `loadStats()` → `http.get('/announce/stats')` → routeTag: `/announce`

## 路由: `/announce/:source/:announceNo`（公告详情）

- [ ] `src/views/AnnounceDetail.vue:224` → `loadDetail()` → `useDetailCache` → `getAnnouncement` 系列 → routeTag: `/announce`

## 路由: `/announce/:announceNo`（重定向）

- [ ] `src/views/LegacyRedirect.vue:22` → `getAnnouncementByNo()` → routeTag: `/announce`

## 路由: `/notification-logs`

- [ ] `src/views/NotificationLogsView.vue:228` → `loadLogs()` → `getNotificationLogs()` → routeTag: `/notification-logs`

## 路由: `/standards-status`

- [ ] `src/views/StandardsStatusView.vue:109` → `loadStats()` → `getStandardsStats()` → routeTag: `/standards-status`
- [ ] `src/views/StandardsStatusView.vue:109` → `loadList()` → `getStandardsStatus()` → routeTag: `/standards-status`

## 路由: `/settings`（含全部 Tab 子组件）

**SettingsView 编排层**（onMounted:325）

- [ ] `src/views/SettingsView.vue:325` → `loadCfg()` → `getSettings()` + `getSettingsSchema()` → routeTag: `/settings`
- [ ] `src/views/SettingsView.vue:325` → `loadTabMeta()` → `getSettingsMetadata()` → routeTag: `/settings`
- [ ] `src/views/SettingsView.vue:325` → `loadSystemSections()` → `prefsStore.getAll()` → routeTag: `/settings`

**各 Tab 子组件**（KeepAlive 动态挂载，各自 onMounted）

- [ ] `src/views/settings/SettingsTabSites.vue:194` → `loadSites()` → `http.get('/settings/sites')` → routeTag: `/settings`
- [ ] `src/views/settings/SettingsTabToken.vue:94` → `loadToken()` → `getToken()` → routeTag: `/settings`
- [ ] `src/views/settings/SettingsTabToken.vue:94` → `loadGhToken()` → `http.get('/settings')` → routeTag: `/settings`
- [ ] `src/views/settings/SettingsTabUsers.vue:89` → `loadUsers()` → `getUsers()` → `http.get('/users')` → routeTag: `/settings`
- [ ] `src/views/settings/SettingsTabSchedule.vue:71` → `loadTasks()` → `getSettings()` → routeTag: `/settings`
- [ ] `src/views/settings/SettingsTabCircuit.vue:68` → `loadCircuitConfig()` → `http.get('/adapter/config')` → routeTag: `/settings`
- [ ] `src/views/settings/SettingsTabValidity.vue:67` → `loadCircuitConfig()` → `http.get('/adapter/config')` → routeTag: `/settings`
- [ ] `src/components/ValidityConfig.vue:212` → `loadConfig()` + `loadHistory()` → `getValidityConfig()` / `getValidityHistory()` → routeTag: `/settings`
- [ ] `src/components/NotificationConfig.vue:228` → `getNotificationConfig()` → routeTag: `/settings`
- [ ] `src/components/WechatTrustIP.vue:140` → `loadConfig()` + `loadStatus()` → `http.get('/wechat-ip/*')` → routeTag: `/settings`
- [ ] `src/components/CacheManager.vue:71` → `loadStats()` → `http.get('/cache/stats')` → routeTag: `/settings`
- [ ] `src/components/TaskManager.vue:96` → `loadTasks()` → `http.get('/tasks')` → routeTag: `/settings`
- [ ] `src/components/FileMonitor.vue:116` → `loadConfig()` + `loadStatus()` + `loadStats()` → `http.get('/monitor/*')` → routeTag: `/settings`

## 路由: `/login`

- [ ] `src/views/LoginView.vue:26` → `getSettingsCached()` → `http.get('/settings')` → routeTag: `/login`

---

## 原生 axios（不走共享 http.ts，无需迁移）

以下组件直接 `import axios from 'axios'`，请求**不进 pendingPools/globalPool**，不受取消机制影响。它们也不会被误杀，但同样享受不到 CSRF / 401 降级 / 路由级取消。建议后续统一到 `@/api/http`（另立任务，非本次迁移范围）。

- `src/views/SchedulerStatus.vue:34` → `axios.get('/api/scheduler/status')`（onMounted）
- `src/views/BackupView.vue:25` → `axios.get('/api/backup/list')`（onMounted）
- `src/views/SystemResources.vue:17` → `axios.get('/api/system/resources')`（onMounted + setInterval 10s）
- `src/views/QueryHistory.vue:16` → `axios.get('/api/query/results')`（onMounted）
- `src/views/DownloadQueue.vue:16` → `axios.get('/api/tasks')`（onMounted）
- `src/views/QualityView.vue:22` → `axios.post('/api/quality/run')`（点击触发，无 onMounted）
- `src/views/DownloadImport.vue` → `axios`（点击触发，无 onMounted）

## 路由: `/task`（无初始化 HTTP）

`src/views/TaskView.vue:106` onMounted 仅读 localStorage（`pilotstd_tasks` + `loadPaths`），无 HTTP 请求。`getPipelineRun` 为点击启动任务后的 setInterval 轮询（低优先级）。

---

## 低优先级（点击事件触发，非路由切换误杀场景）

这些走 `http` 但由 `@click` 触发，迁移后享受路由级取消，非必须。

- `src/views/settings/SettingsTabSites.vue:136` → `saveSite()` → `http.put('/settings/sites/:name')`
- `src/views/settings/SettingsTabToken.vue:50` → `saveGhToken()` → `http.put('/settings')`
- `src/views/settings/SettingsTabToken.vue:83` → `doRefreshToken()` → `refreshToken()`
- `src/views/settings/SettingsTabCircuit.vue:53` → `saveCircuitConfig()` → `http.put('/adapter/config')`
- `src/views/settings/SettingsTabValidity.vue:55` → `saveCircuitConfig()` → `http.put('/adapter/config')`
- `src/views/AnnounceView.vue:73` → `check()` → `postAnnounceCheck()`
- `src/views/PendingView.vue:38` → `requery()` → `postRequery()`
- `src/views/OrganizeView.vue:74` → `doEnqueue()` → `enqueueValidityCheck()`
- `src/components/dashboard/widgets/QuickActionsCard.vue:48` → `http.post('/scan-and-index')`
- `src/components/TaskManager.vue:87,91` → retry/cancel → `http.post('/tasks/:id/...')`
- `src/components/CacheManager.vue:36,44` → `http.put('/cache/config')` / `http.post('/cache/cleanup')`

---

## 迁移统计

| 分类 | 数量 |
|------|------|
| 需迁移（走 http.ts，onMounted/watch） | 约 30 处 |
| 原生 axios（无需迁移） | 7 个 view |
| 低优先级（点击触发） | 约 11 处 |
| 无初始化 HTTP 的路由 | 1（`/task`） |
