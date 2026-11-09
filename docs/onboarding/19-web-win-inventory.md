# 19 · Web / Win / CLI 功能与分支清单

> 目的：把“三端到底有哪些入口、哪些分支已读、哪些还只是路由级”列清楚。  
> 图例：✅ 已读主流程；◐ 只读入口/路由；○ 仅知道存在。  
> 132 个 API 路由的逐条清单见 [`20-api-route-inventory.md`](20-api-route-inventory.md)。

---

## 一、Web

### 1. 规模

- `docker/api/`：**41 个 router 模块、132 个路由**；
- `web/src/views/`：**21 个视图**；
- `web/src/api/`：15 个 API 模块。

### 2. 视图清单

| 视图 | 覆盖 | 说明 |
|---|---|---|
| `TaskView.vue` | ✅ | 五段式：scan→query→download→normalize→archive；轮询 `pipeline_runs` |
| `HomeView.vue` | ◐ | 首页/概览 |
| `OrganizeView.vue` | ◐ | 归档/整理 |
| `PendingView.vue` | ◐ | 待确认 |
| `FavoritesView.vue` | ◐ | 收藏 |
| `AnnounceView.vue` / `AnnounceDetail.vue` | ◐ | 公告列表/详情 |
| `NotificationLogsView.vue` | ◐ | 通知日志/未读 |
| `StandardsStatusView.vue` | ◐ | 标准状态 |
| `SettingsView.vue` | ◐ | 设置 |
| `SchedulerStatus.vue` | ◐ | 调度器 |
| `QualityView.vue` | ◐ | 质量检查 |
| `BackupView.vue` | ◐ | 备份 |
| `SystemResources.vue` | ◐ | 系统资源 |
| `QueryHistory.vue` | ◐ | 查询历史 |
| `DownloadQueue.vue` | ◐ | 下载队列 |
| `DownloadImport.vue` | ◐ | 导入下载 |
| `LoginView.vue` / `RegisterView.vue` / `ForbiddenView.vue` | ◐ | 登录/注册/403 |
| `LegacyRedirect.vue` | ○ | 旧路由兼容 |

### 3. Web 分支

| 分支 | 现状 |
|---|---|
| 开始 | `runPipeline()` 清空上一步结果，scan 生成 `run_id` |
| 轮询 | 2 秒一次；连续 3 次失败停止，不自动重连 |
| 离开页面 | `onBeforeUnmount` 只停轮询；后端任务继续 |
| 恢复 | `resolveActiveRun()` 只恢复 `running/pending`；终态清掉 |
| 重跑 | 重新从 scan 开始；无显式 `if (running) return` |
| 停止 | **已实现**（Web B：`/task` 停止按钮 + 阶段边界协作式停止） |
| 下载 | 只取 `exact`、非采标；2026-11-09 起不再截断为 10 条 |
| 归档 | 入参来自 scan.files + normalize 结果 + 下载成功项（2026-11-07 起） |

---

## 二、Win

### 1. Worker（8 个）

| Worker | 覆盖 | 职责 |
|---|---|---|
| `ScanWorker` | ✅ | 扫描/解析 |
| `QueryWorker` | ✅ | 查询/分类 |
| `DownloadWorker` | ✅ | 下载 |
| `NormalizeWorker` | ✅ | 规范化预览 |
| `ArchiveWorker` | ✅ | 归档 |
| `AutoWorker` | ✅ | 一键 `auto_run_stream` |
| `AnnounceWorker` | ◐ | 公告抓取/解析/对账 |
| `UpdateDownloadWorker` | ○ | 更新包下载/脚本 |

### 2. FlowEngine（12 个）

| FlowEngine | 覆盖 | 说明 |
|---|---|---|
| `scan_flow_engine` | ✅ | 扫描 |
| `query_flow_engine` | ✅ | 查询 |
| `download_flow_engine` | ✅ | 下载 |
| `archive_flow_engine` | ✅ | 归档/规范化 |
| `auto_flow_engine` | ✅ | 一键 |
| `announce_flow_engine` | ◐ | 公告 |
| `query_summary_flow_engine` | ◐ | 查询汇总 |
| `cleanup_flow_engine` | ◐ | 清理 |
| `project_flow_engine` | ◐ | 项目保存/恢复 |
| `persistence_flow_engine` | ◐ | 窗口/表格状态 |
| `settings_io_flow_engine` | ◐ | 设置导入导出 |
| `actions_flow_engine` | ◐ | 通用动作 |

### 3. Win 分支

- 手动：每个 Worker 只跑一段；
- 一键：`AutoWorker` 串完整链；
- 停止：`stop_worker_gracefully()` 协作式，不 `terminate()`；
- 持久化：窗口/分割器/排序/列宽/项目，**不保存 Worker 运行态**；
- 重启：未完成任务不自动续跑。

---

## 三、CLI（12 个命令）

```text
scan / query / download / organize / auto / pending /
normalize / announce / task / move / expire / validity
```

- `auto` 串主链；
- `normalize` 只预览；
- `organize` 才归档；
- 其余为单点操作/查询。

---

## 四、外围功能覆盖

| 功能 | 覆盖 | 缺口 |
|---|---|---|
| 收藏下载 | ◐ | `favorite_downloads` 状态机、重试、解耦未逐行读 |
| 待确认 | ◐ | `pending_lookup` 全流程未读 |
| 任务中心 | ◐ | `task_queue` 展示有，真实消费方未穷尽 |
| 下载导入 | ◐ | `DownloadImport.vue` / `/api/download/import` 只到路由 |
| 上传/导出 | ○ | 上传校验、导出字段/权限未读 |
| 备份 | ◐ | 创建/下载已读；恢复无 API、未演练 |
| 用户/权限/多用户 | ○ | 角色矩阵、用户隔离、通知归属未读 |
| 设置/缓存/审计/质量/微信 IP | ○ | 只到路由级 |

---

## 五、结论

- **Web**：主链和 TaskView 已读；21 个视图里大部分只到入口级。
- **Win**：8 个 Worker + 核心 FlowEngine 已读；公告/项目/设置/清理等分支只到入口级。
- **CLI**：12 个命令已列，主链命令已读。
- **外围**：收藏、待确认、上传/导出、用户/权限、设置/缓存/审计/质量/微信 IP 仍未逐条读。
- “全部分支”目前**没有**做到；本清单是后续补齐的底稿。
