# Validity 重构 + 调度接入 + auto_query 删除 — 设计文档

日期：2026-06-29

## 一、背景与动机

### 1.1 问题

1. **auto_query 是死功能**：`auto_query` 通过 `recheck_updates()` 对 `file_index` 中的现行标准做重查，本质上是低频低价值的轮询查询。该功能一直未被调度器真正消费（frequency 配置与实际调度逻辑脱节）。
2. **validity 逻辑散落**：时效性检查的核心执行逻辑全部写在 `docker/api/validity.py` 的 API 端点内，无法被调度器复用。
3. **硬编码 bug**：`ValidityChecker.update_status()` 中 `next_check_at` 固定为 `+28天`，无视配置中的 `update_interval` 参数。
4. **调度器未接 validity**：`std_gov` 负载超 150%，validity 没有调度触发机制。

### 1.2 目标

| # | 目标 | 效果 |
|---|------|------|
| 1 | 删除 auto_query 全链路 | 消除死代码 |
| 2 | validity 核心逻辑迁移到 `pilotstd/core/` | API 和调度器共用 |
| 3 | 调度器接入 validity（唤醒模式） | 自动化执行，从数据库读取 `next_run` 判断时机 |
| 4 | 修复硬编码 bug | `total_weeks` 配置真正生效 |
| 5 | 废弃无用配置 | `frequency`/`execute_time`/`update_interval` 标记废弃 |

---

## 二、架构设计

### 2.1 调度模型：唤醒触发器

```
┌──────────────┐   每5分钟唤醒    ┌──────────────────────┐
│ APScheduler  │ ───────────────→ │ _check_validity_schedule() │
│              │                  │                      │
│ (Background  │                  │ first_execution=None? → 跳过  │
│  Scheduler)  │                  │ round_completed? → 重置     │
│              │                  │ now < next_run? → 跳过      │
│              │                  │ 否则 → run_validity_check() │
└──────────────┘                  └──────┬───────────────┘
                                         │
                                         ▼
                               ┌──────────────────────┐
                               │ run_validity_check() │
                               │ (pilotstd/core)      │
                               │                      │
                               │ 1. 获取到期标准       │
                               │ 2. 随机切片 (check_ratio) │
                               │ 3. 逐批检查 (batch_size) │
                               │ 4. 更新状态+通知      │
                               └──────────────────────┘
```

**为什么不用传统的 cron 定时触发？**
- 每次执行的时间间隔是动态的：`total_days / ceil(100/check_ratio)` 天
- 用户可能随时通过 API 手动触发，影响下次执行时间
- 唤醒模式更灵活：5 分钟粒度足够，判断逻辑简单

### 2.2 层次划分

```
┌─────────────────────────────────┐
│  调度器 (docker/scheduler.py)   │  ← 唤醒 + 判断是否到时间
├─────────────────────────────────┤
│  API 层 (docker/api/validity.py)│  ← 直接调用底层函数
├─────────────────────────────────┤
│  核心层 (pilotstd/core/)        │  ← 纯执行逻辑 + ValidityChecker
└─────────────────────────────────┘
```

### 2.3 数据流

```
用户设 first_execution → 存储到 config.json
         │
         ▼
调度器唤醒 (每5分钟) → _check_validity_schedule()
         │
    ┌────┴────┐
    │ 条件判断 │ → 不满足 → return
    └────┬────┘
         │ 满足
         ▼
run_validity_check() → standard_validity 表
         │
    ┌────┴────┐
    │批次循环  │ → sleep(batch_interval)
    └────┬────┘
         │
         ▼
    ┌──────────────┐
    │ update_status │ → 写入数据库 + next_check_at = now + total_weeks*7
    └──────┬───────┘
           │
           ▼
    send_event("check_batch_complete")
           │
           ▼
    checked_count += len(checked_this_run)
    若 checked_count >= 总标准数 → round_completed = True
           │
           ▼
    计算 next_run = now + interval_days
```

---

## 三、文件变更清单

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `docker/scheduler.py` | 修改 | 移除 auto_query 注册；新增 `_check_validity_schedule()` + 唤醒注册 |
| 2 | `docker/app.py` | 修改 | 移除 `register_job_func("auto_query", ...)` |
| 3 | `pilotstd/manager/scheduled_service.py` | 修改 | 删除 `recheck_updates()` |
| 4 | `pilotstd/manager/facade.py` | 修改 | 删除 `recheck_updates()` 透传 |
| 5 | `pilotstd/core/file_index.py` | 修改 | 删除 `get_recheck_candidates()` |
| 6 | `tests/test_docker_scheduler.py` | 修改 | 移除 auto_query 测试引用 |
| 7 | `pilotstd/core/config.py` | 修改 | 新增 5 项配置 + 废弃 3 项旧配置 |
| 8 | `docker/api/validity.py` | 修改 | API 改为调用底层 `run_validity_check()`；GET/PUT config 接口调整 |
| 9 | `pilotstd/core/validity_checker.py` | 修改 | 新增 `run_validity_check()`；修复 `update_status()` 硬编码 bug |

---

## 四、关键设计决策

### 4.1 配置项设计

**新增**：
| 键名 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `validity.first_execution` | `str\|None` | `None` | ISO datetime，用户首次设置 |
| `validity.total_weeks` | `int` | `4` | 总检查周期（周），范围 4~52 |
| `validity.next_run` | `str\|None` | `None` | ISO datetime，系统计算的下次执行 |
| `validity.checked_count` | `int` | `0` | 当前轮次已检查标准数 |
| `validity.round_completed` | `bool` | `False` | 当前轮次是否完成 |

**保留的已有配置**：
| `validity.batch_size` | `int` | `50` | 每批检查条数 |
| `validity.batch_interval` | `int` | `5` | 批次间隔秒数 |
| `validity.check_ratio` | `int` | `25` | 每轮检查比例（%） |

**废弃**（保留键名不删，兼容旧 config.json，但代码不再读取）：
- `validity.frequency`
- `validity.execute_time`
- `validity.update_interval`

### 4.2 时间间隔计算公式

```
total_runs = ceil(100 / check_ratio)
total_days = total_weeks * 7
interval_days = ceil(total_days / total_runs)
```

例如：check_ratio=25（每轮 4 次执行）, total_weeks=4（28 天）→ interval_days = ceil(28/4) = 7 天

### 4.3 API 兼容策略

- GET `/validity/config`：返回旧字段 + 新字段，旧字段值从 config 读取（可能是已保存的旧值），每个旧字段附带 `deprecated: true`
- PUT `/validity/config`：接受 `first_execution`、`total_weeks`，忽略 `frequency`/`execute_time`/`update_interval`

### 4.4 通知事件

- `check_batch_complete`：每次 run 完成时发送，含 `count`、`changed`
- 通知调用全部用 `try-except` 包裹，通知失败不影响主流程

### 4.5 时间状态机

```
first_execution=None  →  调度器跳过（安全初始态）
        │
        ▼ 用户设置
first_execution=T0
        │
        ▼ 调度器唤醒：now >= T0
首次执行 run_validity_check()
  计算 next_run = now + interval_days
        │
        ▼
后续唤醒：now >= next_run?  →  执行 + 重算 next_run
        │
        ▼ 累计 checked_count >= 总数
round_completed = True
        │
        ▼ 调度器唤醒
重置：round_completed=False, checked_count=0, next_run=None
  → 回到等待 first_execution 状态（用户重新设置后开始下一轮）
```

**关键规则**：
- `first_execution` 仅在首次进入（`next_run is None` 且未完成过任何一轮）时使用
- 后续完全由 `next_run` 驱动
- `round_completed` 重置时**同时清除 `next_run`**，强制用户重新设置 `first_execution` 来启动新轮次，防止在用户未确认的情况下自动开始下一轮

### 4.6 并发保护

`run_validity_check()` 内部使用模块级 `threading.Lock`，确保同一时刻只有一个执行实例。

- 调度器唤醒时若锁已被持有（用户正手动触发），则跳过本次唤醒
- 手动触发时若锁已被持有（调度器正在执行），则返回 `{"ok": False, "error": "检查正在执行中"}`

手动触发的 API 直接调用 `run_validity_check()`，不更新 `checked_count`（不参与轮次计数）。轮次计数仅限于调度器触发的执行。

- `check_batch_complete`：每次 run 完成时发送，含 `count`、`changed`
- 通知调用全部用 `try-except` 包裹，通知失败不影响主流程

---

## 五、安全与边界

- `first_execution` 为 None 时调度器不启动检查（安全默认值）
- `ConfigManager` 在调度函数内部每次读取（不缓存），确保读取到最新配置
- 数据库连接复用已有的 `_get_db()` 模式
- 所有通知调用包裹 `try-except`

---

## 六、前端汇总（本次不实施）

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `web/src/api/validity.ts` | `ValidityConfig` 接口新增 5 个字段，旧 3 字段标记 `@deprecated` | 高 |
| `web/src/components/ValidityConfig.vue` | 表单新增 `first_execution` 日期时间选择器 + `total_weeks` 输入框；旧字段 UI 加标签 | 高 |
| `web/src/views/SettingsView.vue` | 如有引用旧字段，同步更新 | 中 |
