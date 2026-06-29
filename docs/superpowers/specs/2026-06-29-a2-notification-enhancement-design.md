# A2 通知增强 — 设计文档

日期：2026-06-29

## 一、目标

为 validity_checker 增强 4 类通知能力：

| # | 通知事件 | 触发时机 | 级别 |
|---|---------|---------|------|
| 1 | `validity_batch_report` | 每次 `run_validity_check()` 执行完成后 | info/warning |
| 2 | `validity_round_summary` | 一轮全部标准检查完成后 | info |
| 3 | `validity_standard_failed` | 单条标准检查异常时 | error |
| 4 | `validity_system_failed` | 整体执行流程异常时 | error |

## 二、架构

### 2.1 新增组件

```
pilotstd/manager/adapter_manager.py  (AdapterManager — Manager 层)
    │
    ├── 聚合 SiteRotator (query 层)
    ├── 聚合 DailyQuotaTracker (query 层)
    └── 读取 adapter_health 表 (Core 层 DB)
    │
    ├── 被 StandardManager 持有 (self.adapter_manager)
    └── 被 run_validity_check() 通过参数接收
```

### 2.2 分层理由

`AdapterManager` 必须放在 Manager 层而非 Core 层，因为它依赖业务层类型（SiteRotator、DailyQuotaTracker）。Core 层禁止引用业务层。

### 2.3 数据流

```
run_validity_check(adapter_mgr=...)
    │
    ├── 初始化收集器: changed_list, failed_list
    │
    ├── 逐条检查循环:
    │   ├── 成功 + 状态变更 → changed_list.append()
    │   ├── 失败 → failed_list.append() + send_event("validity_standard_failed")
    │   └── 每 10 条变更 → 分条通知
    │
    ├── 获取适配器状态: adapter_mgr.get_all_status()
    │
    ├── send_event("validity_batch_report")  ← 每次执行完成
    │
    ├── run_validity_check() 整体异常:
    │   └── send_event("validity_system_failed")
    │
    └── round_completed → send_event("validity_round_summary")  ← 仅调度器触发
```

## 三、数据库变更

```sql
ALTER TABLE standard_validity ADD COLUMN last_changed_at TEXT;
UPDATE standard_validity SET last_changed_at = updated_at;
```

在 `ValidityChecker.__init__()` 中自动迁移，无需独立脚本。

## 四、文件变更清单

| # | 文件 | 操作 | 层 |
|---|------|------|-----|
| 1 | `pilotstd/manager/adapter_manager.py` | **新建** | Manager |
| 2 | `pilotstd/manager/facade.py` | 修改 — 集成 AdapterManager | Manager |
| 3 | `pilotstd/core/notification/manager.py` | 修改 — 新增 4 个消息模板 | Core |
| 4 | `pilotstd/core/notification/events.py` | 修改 — 新增 4 个常量 | Core |
| 5 | `pilotstd/core/config.py` | 修改 — 新增 4 个默认规则 | Core |
| 6 | `pilotstd/core/validity_checker.py` | 修改 — 迁移 + update_status + run 增强 | Core |
| 7 | `docker/api/validity.py` | 修改 — 传入 adapter_mgr | API |
| 8 | `docker/scheduler.py` | 修改 — 传入 adapter_mgr | API |
| 9 | `docker/app.py` | 修改 — 注册时传入 adapter_mgr | API |

## 五、关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| 1 | AdapterManager 放 Manager 层 | Core 不依赖业务层（SiteRotator/DailyQuotaTracker 在 query 层） |
| 2 | last_changed_at 自动迁移 | 避免独立迁移脚本的部署复杂度 |
| 3 | 每 10 条变更分条通知 | 防止单条通知过长 |
| 4 | 周期汇总仅调度器触发 | API 手动触发不应计入轮次统计 |
| 5 | 所有通知 try-except 包裹 | 通知失败不阻断主流程 |

## 六、执行顺序

A2.0 → A2.1 → A2.2 → A2.3 → A2.4 → A2.5 → A2.6 → 验证
