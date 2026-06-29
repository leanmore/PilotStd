# 业务功能与管理功能现状调查

> 调查日期：2026-06-29 / 基于：全项目代码扫描（78 API + 9 视图 + 11 CLI + 45 Manager 方法）

---

## 1. 业务功能清单

| 功能分类 | 功能项 | Web | CLI | WinUI | API | 成熟度 | 说明 |
|----------|--------|-----|-----|-------|-----|--------|------|
| **标准查询** | 单号/批量查询 | ✅ TaskView | ✅ cmd_query | ✅ btn_query | ✅ 3 端点 | **完整** | 核心功能，三端齐备 |
| **标准查询** | 查询历史/缓存 | ✅ SettingsView cache | ❌ | ❌ | ✅ 4 端点 | 部分 | 缓存管理仅设置页可配 |
| **标准下载** | 单条/批量下载 | ✅ TaskView | ✅ cmd_download | ✅ btn_download | ✅ 1 端点 | **完整** | 含采标跳过 |
| **标准扫描** | 目录扫描/解析 | ✅ TaskView | ✅ cmd_scan | ✅ btn_select | ✅ 1 端点 | **完整** | FileScanner + StandardParser |
| **标准归档** | 文件归档/分类 | ✅ TaskView/OrganizeView | ✅ cmd_organize | ✅ btn_save+btn_normalize | ✅ 3 端点 | **完整** | 含规范化+过期处理 |
| **公告管理** | 公告抓取 | ✅ AnnounceView | ✅ cmd_announce | ✅ btn_announce | ✅ 7 端点 | **完整** | 同步+异步双模式 |
| **公告管理** | 公告匹配/记录 | ✅ AnnounceView | ❌ | ❌ | ✅ | 部分 | API 有记录查询 |
| **时效性检查** | 配置与执行 | ✅ SettingsView | ❌ | ❌ | ✅ 5 端点 | 部分 | Web 配置页完整，CLI/WinUI 缺 |
| **时效性检查** | 定时调度 | ✅ (APScheduler) | ❌ | ❌ | ✅ | 部分 | 仅 Docker 端有 |
| **任务管理** | 查看/取消/重试 | ✅ TaskView | ✅ cmd_task | ❌ | ✅ 5 端点 | 部分 | WinUI 缺独立任务页 |
| **任务管理** | 一键自动 | ❌ | ✅ cmd_auto | ✅ btn_auto | ❌ | 部分 | 无 API 端点 |
| **文件监控** | 实时监控 | ✅ SettingsView | ❌ | ❌ | ✅ 5 端点 | 部分 | 仅 Web 端可配 |
| **待确认管理** | 查看/重查询 | ✅ PendingView | ✅ cmd_pending | ❌ | ✅ 2 端点 | 部分 | 核心功能完整 |
| **数据质量** | 质量检查 | ❌ | ❌ | ❌ | ❌ | **缺失** | `quality/` 模块有骨架但不对外暴露 |
| **下载等待队列** | 到期下载 | ❌ | ❌ | ❌ | ✅ Manager | 部分 | 逻辑在 Manager，无前端入口 |
| **文件浏览** | 文件管理 | ✅ OrganizeView | ❌ | ✅ 文件树 | ✅ 2 端点 | 部分 | 各端独立实现 |

---

## 2. 管理功能清单

| 功能分类 | 功能项 | Web | CLI | WinUI | API | 成熟度 | 说明 |
|----------|--------|-----|-----|-------|-----|--------|------|
| **用户管理** | 用户 CRUD | ✅ SettingsView | ❌ | ❌ | ✅ 4 端点 | 部分 | Web 设置页完整 |
| **用户管理** | 密码修改 | ✅ SettingsView | ❌ | ❌ | ✅ | 部分 | |
| **配置管理** | 存储/网络/扫描 | ✅ SettingsView | ❌ | ❌ | ✅ 4 端点 | 部分 | 13 个设置标签页 |
| **配置管理** | 站点限流配置 | ✅ SettingsView(sites) | ❌ | ❌ | ✅ | 部分 | 只读展示 |
| **配置管理** | OCR 配置 | ✅ SettingsView(ocr) | ❌ | ❌ | ✅ | 部分 | 三云调度 |
| **配置管理** | 主题/语言/UI | ✅ SettingsView(ui) | ❌ | ✅ themes.py | ❌ | 部分 | 仅 Web 有配置页 |
| **适配器管理** | 状态查看 | ✅ 仪表板 Widget | ❌ | ❌ | ✅ 3 端点 | 部分 | 含倒计时刷新 |
| **适配器管理** | 熔断配置 | ✅ SettingsView(circuit) | ❌ | ❌ | ✅ | 部分 | |
| **适配器管理** | 测试适配器 | ❌ | ❌ | ❌ | ❌ | **缺失** | 无单站点测试端点 |
| **通知管理** | 四渠道配置 | ✅ SettingsView | ❌ | ❌ | ✅ 5 端点 | **完整** | 微信/Telegram/飞书/钉钉 |
| **通知管理** | 事件订阅 | ✅ NotificationConfig | ❌ | ❌ | ✅ | **完整** | 14 个事件可选 |
| **通知管理** | 通知日志 | ✅ NotificationLogsView | ❌ | ❌ | ✅ | **完整** | 分页+筛选+已读标记 |
| **通知管理** | 测试发送 | ✅ NotificationConfig | ❌ | ❌ | ✅ | **完整** | |
| **通知管理** | WebSocket 推送 | ✅ NotificationBell | ❌ | ✅ 铃铛 | ✅ WebSocket | **完整** | 双端铃铛 |
| **调度管理** | 查看调度状态 | ❌ | ❌ | ❌ | ❌ | **缺失** | 无 API |
| **调度管理** | 手动触发任务 | ✅ (各页面按钮) | ✅ | ✅ | ⚠️ | 部分 | 无统一调度面板 |
| **缓存管理** | 查看状态 | ✅ CacheManager | ❌ | ❌ | ✅ 4 端点 | **完整** | |
| **缓存管理** | 手动清理 | ✅ SettingsView | ❌ | ❌ | ✅ | **完整** | |
| **日志管理** | 实时日志 | ✅ LogBar | ❌ | ✅ 日志面板 | ✅ 2 端点 | **完整** | 含原始文本下载 |
| **系统状态** | 版本/运行信息 | ✅ SystemInfoCard | ❌ | ❌ | ✅ 1 端点 | 部分 | |
| **系统状态** | 健康检查 | ❌ | ❌ | ❌ | ❌ | **缺失** | |
| **系统状态** | 资源使用 | ❌ | ❌ | ❌ | ❌ | **缺失** | |
| **数据导出** | 标准列表导出 | ❌ | ❌ | ✅ export_mixin | ❌ | 部分 | 仅 WinUI |
| **备份管理** | 自动备份(定时) | ❌ | ❌ | ❌ | ✅ scheduler | 部分 | `auto_backup` cron |
| **备份管理** | 手动备份 | ❌ | ❌ | ❌ | ❌ | **缺失** | |
| **备份管理** | 备份列表/恢复 | ❌ | ❌ | ❌ | ❌ | **缺失** | |
| **企业微信 IP** | IP 检测配置 | ✅ WechatTrustIP | ❌ | ❌ | ✅ 4 端点 | **完整** | |
| **API 令牌** | 查看/刷新 | ✅ SettingsView(token) | ❌ | ❌ | ✅ | **完整** | |

---

## 3. 功能缺口分析

### 3.1 业务功能缺口

| 优先级 | 缺口 | 说明 | 建议 |
|--------|------|------|------|
| P1 | 数据质量检查 | `pilotstd/quality/` 有 `QualityRunner` + 规则定义，但无 API 暴露、无前端页面、无 CLI 命令 | 新增 `/api/quality/run` + Web 质量检查页面 |
| P1 | 时效性检查 WinUI/CLI 入口 | WinUI 工具栏和 CLI 均无时效性检查按钮 | CLI 增加 `pilotstd validity` 命令；WinUI 增加检查按钮 |
| P2 | 一键自动 API | `cmd_auto`/`btn_auto` 存在，但无对应 HTTP API | 新增 `POST /api/auto` 端点 |
| P2 | 下载队列管理页面 | Manager 层有完整的下载等待队列逻辑，前端无入口 | 新增 `/download-queue` 页面 |
| P3 | 查询历史页面 | API 有查询缓存和结果存储，前端无历史记录浏览 | 新增 `/query-history` 页面 |

### 3.2 管理功能缺口

| 优先级 | 缺口 | 说明 | 建议 |
|--------|------|------|------|
| P1 | 系统健康检查 | 无 `/api/health` 端点检查 DB/缓存/适配器状态 | 新增 `GET /api/system/health` |
| P1 | 调度器状态面板 | 无 API 查看当前调度任务列表和状态 | 新增 `GET /api/scheduler/status` |
| P2 | 备份管理 Web 页面 | 自动备份在后台运行，无手动备份入口和备份列表 | 新增备份管理页面（列表/创建/恢复） |
| P2 | 适配器测试端点 | 站点无单独测试端点（仅通知有 test endpoint） | 新增 `POST /api/adapter/test` 单站点连通性测试 |
| P3 | 手动备份 API | 无 `POST /api/backup` 端点 | 新增备份触发端点 |
| P3 | 系统资源监控 | 无 CPU/内存/磁盘使用 API | 新增 `GET /api/system/resources` |
| P3 | 数据导出 Web 入口 | 仅 WinUI 有导出，Web+CLI 缺 | 新增 `GET /api/export` + Web 导出按钮 |

---

## 4. 功能重叠分析

| 重叠项 | 涉及模块 | 说明 | 建议 |
|--------|---------|------|------|
| 文件浏览 | `OrganizeView`(Web) + `file_tree_mixin`(WinUI) | 两端各自实现文件树，非共享逻辑 | 均为端侧 UI，接受现状 |
| 日志查看 | `LogBar`(Web) + `workers.py`(WinUI) | 两端独立实现日志展示 | 均为端侧 UI，接受现状 |
| 归档操作 | `archive_mixin`(WinUI) + `TaskView`(Web) | 均调用同一 Manager 方法，正确 | ✅ 架构正确 |
| one-click run | `cmd_auto`(CLI) + `btn_auto`(WinUI) | 均调用 `mgr.auto_run()`，但 Web 无对应 | 新增 API 端点统一 |

---

## 5. 建议新增功能清单（方向5）

| 优先级 | 功能名称 | 类型 | 复杂度 | 预期收益 |
|--------|---------|------|--------|---------|
| P0 | `GET /api/system/health` | 管理 | 低（~30 行） | 运维监控基础 |
| P1 | 数据质量检查（API + Web 页面） | 业务 | 中（~200 行） | 激活已有 quality 模块 |
| P1 | 调度器状态 API + 面板 | 管理 | 中（~150 行） | 运维可见性 |
| P1 | CLI `pilotstd validity` 命令 | 业务 | 低（~50 行） | 补齐 CLI 端 |
| P2 | `POST /api/auto` 一键处理 | 业务 | 低（~30 行） | 补齐 Web API |
| P2 | 备份管理 Web 页面 | 管理 | 中（~200 行） | 运维操作便利 |
| P2 | 适配器连通性测试端点 | 管理 | 低（~50 行） | 排障工具 |
| P3 | 查询历史页面 | 业务 | 中（~150 行） | 用户回溯 |
| P3 | 下载队列管理页面 | 业务 | 中（~150 行） | 用户可见性 |
| P3 | 系统资源监控 | 管理 | 低（~50 行） | 运维监控 |
| P3 | Web 端数据导出 | 管理 | 中（~100 行） | 补齐 Web 端 |

---

## 6. 功能开发路线图建议

**阶段 1（运维基础）**：`GET /api/system/health` + 调度器状态 API + 适配器测试端点
**阶段 2（业务补齐）**：数据质量检查 + CLI validity 命令 + `POST /api/auto`
**阶段 3（管理增强）**：备份管理页面 + 系统资源监控 + Web 数据导出
**阶段 4（体验优化）**：查询历史页面 + 下载队列管理页面

---

## 证据附录

### 证据1：API 端点统计
78 个活跃端点，24 个功能分组。详见 Agent 1 完整报告。

### 证据2：Web 前端
9 个视图全部完整，21 个组件全部完整，13 个设置标签页。

### 证据3：CLI
11 个命令：scan / query / download / organize / auto / normalize / move / expire / announce / pending / task

### 证据4：WinUI
9 个工具栏按钮 + 16 个 mixin 控制器 + 3 个页面

### 证据5：Manager 方法
~45 个公开方法，覆盖扫描/查询/下载/归档/公告/待确认/文件索引/监控/配额等全业务域
