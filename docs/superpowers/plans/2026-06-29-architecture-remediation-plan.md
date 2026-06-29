# 架构合规性整改 — 实施计划

> **Goal:** 修复审计报告全部违规项，目标 100% 合规。

**Architecture:** P0 修复 2 处导入违规 → P1 新建 3 个 Service + 迁移 7 个 API 文件 → P2/P3 端侧去重 + 前端 defineOptions。

**执行顺序：** P0 → P1 → P2/P3

---

## P0: 导入违规修复

### Task 1.1: manager.py 回调注入

`pilotstd/core/notification/manager.py` — `__init__` 增加 `ws_broadcast` 参数，替换 `from docker.websocket`。

### Task 1.2: monitor/scheduler.py 依赖注入

`pilotstd/monitor/scheduler.py` — 构造函数增加 `manager` 参数，替换直接 import `StandardManager`。

## P1: API 业务逻辑迁移

### Task 2.1: 新建 ValidityService → 改 validity.py
### Task 2.2: 新建 UserService → 改 user.py
### Task 2.3: 新建 StandardStatsService → 改 standards.py
### Task 2.4: 扩展 AnnounceService → 改 announce.py + announcements.py
### Task 2.5: adapter.py 改为调用 AdapterManager
### Task 2.6: tasks.py 改为调用 TaskQueue 公开方法

## P2/P3: 端侧 + 前端

### Task 3.1: ui/workers.py target_path 改用 Manager
### Task 3.2: App.vue 添加 defineOptions
