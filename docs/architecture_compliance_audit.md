# 架构合规性审计报告

> 审计日期：2026-06-29
> 基于：四层架构定义 v2.0 + 三端定位 (`docs/architecture_layers.md`)

---

## 1. 导入关系违规

| # | 严重度 | 文件 | 行号 | 违规导入 | 违反规则 | 说明 |
|---|--------|------|------|---------|---------|------|
| 1 | 中 | `pilotstd/core/notification/manager.py` | 289 | `from docker.websocket import get_ws_manager` | 规则 2 — Core→端层 | 惰性导入（函数内），A2 WebSocket 广播的已知设计权衡。修复：通过回调注入而非直接导入 |
| 2 | 中 | `pilotstd/monitor/scheduler.py` | 88 | `from pilotstd.manager.facade import StandardManager` | 业务层→Manager（反向依赖） | Monitor 业务包调用 `StandardManager().scan_directory()`。修复：通过依赖注入传入 Manager 实例 |

**合规项（零违规）：**
- ✅ Core → Manager：零命中
- ✅ Core → Business：零命中
- ✅ Core → `import *`：零命中
- ✅ Manager → Platform：零命中
- ✅ Business → Platform：零命中
- ✅ Platform 互导：零命中

---

## 2. 目录结构合规

| # | 严重度 | 发现 | 说明 |
|---|--------|------|------|
| — | — | ✅ 结构良好 | `pilotstd/` 下仅 `__init__.py` 和 `models.py`，无杂项文件 |
| — | — | ✅ Core 层干净 | `pilotstd/core/` 14 个文件，职责清晰 |
| — | — | ✅ Manager 层干净 | `pilotstd/manager/` 9 个文件（含新建的 `adapter_manager.py`） |

---

## 3. API 层直接 DB 访问 + 业务逻辑（规则 5 违规）

| # | 文件 | 违规次数 | 典型代码 |
|---|------|---------|---------|
| 3 | `docker/api/validity.py` | 4 | `get_validity_history()` 直接创建 `Database(get_db_path())` 跑聚合 SQL；`enqueue_validity_check()` 直接 INSERT |
| 4 | `docker/api/announce.py` | 3 | `check_announce()` 含结果汇总+通知发送；`_sync_wait_check()` 创建 DB 轮询 |
| 5 | `docker/api/announcements.py` | 4 | `_run_fetch_task()`、`trigger_fetch()`、`get_task_status()`、`get_task_results()` 全含独立 DB 操作 |
| 6 | `docker/api/standards.py` | 2 | `get_status_stats()` — 直接 GROUP BY；`get_standards_status()` — 构建动态 SQL + 分页 |
| 7 | `docker/api/adapter.py` | 1 | `get_adapter_status()` 直接查 `adapter_health` 表 |
| 8 | `docker/api/user.py` | 10+ | 每个 CRUD 端点都创建独立 `Database()` 实例 |
| 9 | `docker/api/tasks.py` | 1 | `list_tasks()` 穿透 `mgr.task_queue._db` 执行内联 SQL |

**合规 API 端点（无违规，正确委派到 Manager）：**
✅ `scan.py`, `download.py`, `query.py`, `archive.py`, `normalize.py`, `pending.py`, `stats.py`, `settings.py`, `cache.py`, `monitor.py`, `notification.py`, `api_keys.py`, `wechat_ip.py`

---

## 4. 端侧重复实现（规则 6 违规）

| # | 严重度 | 发现 | 说明 |
|---|--------|------|------|
| 10 | 低 | `ArchiveWorker.target_path()` | `pilotstd/ui/workers.py:375-392` 复制了 `OrganizerService` 的路径构建逻辑。Manager 层路径方案变更时不同步 |

**已验证无重复的端侧实现：**
- ✅ 查询：CLI/UI/API 全部委派到 Manager（`StandardManager.query()` / `query_by_numbers()`）
- ✅ 扫描：CLI/UI 全部委派到 Manager（`scan_directory_stream()`）
- ✅ 下载：CLI/UI 全部委派到 Manager（`download_by_numbers()`）
- ✅ 归档：CLI/UI 全部委派到 Manager（`archive_standards()`）

---

## 5. 前端合规（GATE-12）

| 合规 | 数量 |
|------|------|
| ✅ 有 defineOptions | 29 |
| ❌ 缺 defineOptions | 1 (`web/src/App.vue`) |

30 个 `<script setup>` Vue 组件中，29 个正确声明 `defineOptions({ name: '...' })`。唯一缺失是根组件 `App.vue`。

---

## 6. 合规性评分

| 维度 | 检查项 | 合规/总计 | 合规率 |
|------|--------|----------|--------|
| 导入关系 | 7 项检查 | 5/7 零违规，2 项含 1 违规 | **71%** |
| 目录结构 | 3 项检查 | 3/3 合规 | **100%** |
| API 纯净度 | 20 个 API 文件 | 13/20 合规，7 含业务逻辑 | **65%** |
| 端侧去重 | 4 组功能检查 | 3/4 无重复，1 有轻微重复 | **75%** |
| 前端合规 | 30 个 Vue 组件 | 29/30 合规 | **97%** |
| **综合** | | | **~82%** |

---

## 7. 整改优先级

| 优先级 | 类别 | 数量 | 影响范围 | 建议 |
|--------|------|------|---------|------|
| P0 | 导入违规 | 2 | 架构退化风险 | 第一批：`manager.py` 改为回调注入；`monitor/scheduler.py` 改为依赖注入 |
| P1 | API 直连 DB | ~21 | API 层与 DB 耦合 | 第二批：全部改为 `mgr.db` 或新建 Manager 方法 |
| P1 | API 含业务逻辑 | 7 文件 | 业务逻辑散落 | 随 P1 同步迁移到 Manager |
| P2 | 端侧重复实现 | 1 | 低风险 | 第三批：UI 归档路径改用 Manager 方法 |
| P3 | 前端 GATE-12 | 1 | 极低风险 | `App.vue` 加 `defineOptions({ name: 'App' })` |

---

## 8. 整改计划草案

### 第一批（P0）：修复导入违规

1. **`pilotstd/core/notification/manager.py:289`** — 将 `_broadcast_to_ws()` 改为通过回调/接口注入，移除 `from docker.websocket`：
   ```python
   # 当前（违规）
   from docker.websocket import get_ws_manager
   ws_manager = get_ws_manager()

   # 修复方案：send_event 增加 ws_broadcast 回调参数
   def send_event(self, event_type, event_data, ws_broadcast=None):
       ...
       if ws_broadcast:
           self._broadcast_to_ws(event_type, msg, ws_broadcast)
   ```

2. **`pilotstd/monitor/scheduler.py:88`** — 将 `StandardManager()` 实例从外部传入，而非 Monitor 内部导入：
   ```python
   # 当前（违规）
   from pilotstd.manager.facade import StandardManager
   mgr = StandardManager()

   # 修复方案：构造函数接收 manager
   def __init__(self, manager=None):
       self._mgr = manager
   ```

### 第二批（P1）：API 层业务逻辑迁移

按文件逐一处理，每个文件将业务逻辑提取到 Manager 方法：

| 文件 | 需迁移内容 | 目标 Manager 方法 |
|------|-----------|-----------------|
| `validity.py` | history 查询、enqueue 逻辑 | `ValidityService.get_history()` / `enqueue_files()` |
| `announce.py` | 同步等待检查、通知发送 | 现有 `check_announcements_filtered()` 已覆盖大部分 |
| `announcements.py` | 抓取任务状态管理 | `AnnounceService` 新增方法 |
| `standards.py` | 状态统计、列表查询 | `StandardStatusService.get_stats()` / `get_list()` |
| `adapter.py` | 适配器状态查询 | 已有 `AdapterManager.get_all_status()`，直接调 |
| `user.py` | 用户 CRUD | `UserService` 或保持现状（跨领域） |
| `tasks.py` | 任务列表查询 | 改为 `mgr.task_queue` 公开方法 |

### 第三批（P3）：轻微修复

- `web/src/App.vue`：加 `defineOptions({ name: 'App' })`
- `pilotstd/ui/workers.py`：`target_path()` 改为调用 Manager 方法
