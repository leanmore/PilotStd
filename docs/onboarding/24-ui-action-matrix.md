# 24 · Web/Win UI 动作矩阵

> 来源：`web/src/views/*.vue` 的 `@click` / API 导入、`pilotstd/ui/core/handlers/*_flow_engine.py`，2026-11-07。  
> 只列“页面/FlowEngine → 主要动作”；不是逐行 UI 规格。

---

## 一、Web 21 个视图

| 视图 | 主要动作 | API 模块 |
|---|---|---|
| `TaskView.vue` | `runPipeline`：scan→query→download→normalize→archive | `tasks` |
| `HomeView.vue` | 概览展示 | — |
| `OrganizeView.vue` | `cleanEmpty`、`doEnqueue`（有效性入队） | `validity` |
| `PendingView.vue` | `loadPending`、`requery`、`refreshAdapters` | — |
| `FavoritesView.vue` | 收藏列表/状态 | `http` |
| `AnnounceView.vue` | `check`（公告检查） | `http` |
| `AnnounceDetail.vue` | `startParse`、`handleBatchApprove` | — |
| `NotificationLogsView.vue` | `loadLogs`、`onSearch`、`onReset`、`doCleanup` | — |
| `StandardsStatusView.vue` | `onSearch` | `standards` |
| `SettingsView.vue` | `saveCfg`、`applyCurrentTab` | `settings`、`http` |
| `SchedulerStatus.vue` | 调度器状态 | `scheduler` |
| `QualityView.vue` | `runCheck` | `quality` |
| `BackupView.vue` | `createBackup` | `backup` |
| `SystemResources.vue` | 系统资源 | `system` |
| `QueryHistory.vue` | 查询历史 | — |
| `DownloadQueue.vue` | 下载队列 | `tasks` |
| `DownloadImport.vue` | `handleSubmit`（导入下载） | `download` |
| `LoginView.vue` | `submit` | `http` |
| `RegisterView.vue` | `submit` | `auth` |
| `ForbiddenView.vue` | 403 | — |
| `LegacyRedirect.vue` | 旧公告路由兼容 | `announce` |

### TaskView 分支（重点）

| 分支 | 行为 |
|---|---|
| 开始 | 清空结果 → scan → 拿 `run_id` → 启动轮询 |
| 查询 | `scan.files[].standard_number` |
| 下载 | 只 `exact`、非采标，最多 10 条 |
| 规范化 | scan.files 预览 |
| 归档 | scan.files + normalize 结果；不含 `downloadResult` |
| 失败 | 当前 step fail；保存 partial/fail |
| 恢复 | 只恢复 `running/pending` |
| 停止 | 无停止按钮 |

---

## 二、Win 12 个 FlowEngine

| FlowEngine | 主要职责 |
|---|---|
| `scan_flow_engine` | 扫描/解析/表格回填 |
| `query_flow_engine` | 查询/分类/结果回填 |
| `download_flow_engine` | 下载/进度/重试 |
| `archive_flow_engine` | 归档/规范化/移动 |
| `auto_flow_engine` | 一键编排 |
| `announce_flow_engine` | 公告抓取/解析/对账 |
| `query_summary_flow_engine` | 查询汇总 |
| `cleanup_flow_engine` | 清空目录/清理 |
| `project_flow_engine` | 查询/下载项目保存/恢复 |
| `persistence_flow_engine` | 窗口/分割器/排序/列宽 |
| `settings_io_flow_engine` | 设置导入/导出 |
| `actions_flow_engine` | 通用动作 |

### Win 分支

- 手动：每个 Worker 只跑一段；
- 一键：`AutoWorker` 串完整链；
- 停止：`stop_worker_gracefully()`，协作式；
- 持久化：窗口/项目，不保存 Worker 运行态；
- 重启：未完成任务不自动续跑。

---

## 三、结论

- Web 21 个视图的“主要动作 + API 模块”已列；
- Win 12 个 FlowEngine 的职责已列；
- 但各视图的表格列/弹窗/权限/错误提示、各 FlowEngine 的异常分支仍未逐行读；
- 这是“动作地图”，不是“逐控件规格”。
