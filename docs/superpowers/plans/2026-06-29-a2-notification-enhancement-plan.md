# A2 通知增强 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 validity_checker 新增 4 类通知（每次汇总、周期汇总、执行中异常、系统级异常），新建 AdapterManager（Manager 层）聚合适配器状态。

**Architecture:** AdapterManager（Manager 层）聚合 SiteRotator + DailyQuotaTracker + adapter_health 表；run_validity_check() 接收 adapter_mgr 参数收集适配器状态并触发 4 类新通知；standard_validity 表新增 last_changed_at 字段支持周期汇总统计。

**Tech Stack:** Python 3.12, SQLite, threading

**执行顺序：** A2.0 → A2.1 → A2.2 → A2.3 → A2.4 → A2.5 → A2.6

---

### Task A2.0: 新增 AdapterManager（Manager 层）

**文件：**
- Create: `pilotstd/manager/adapter_manager.py`

- [ ] **Step 1: 创建 AdapterManager 类**

```python
# pilotstd/manager/adapter_manager.py
"""适配器状态管理器 — 聚合 SiteRotator + DailyQuotaTracker + adapter_health 表。"""

import time
from typing import Any


class AdapterManager:
    """适配器状态管理——聚合查询引擎的站点状态和数据库熔断状态。"""

    def __init__(self, db: Any, rotator: Any, quota_tracker: Any):
        self._db = db
        self._rotator = rotator
        self._quota = quota_tracker

    def list_adapters(self) -> list[str]:
        """返回所有已配置适配器名称。"""
        return list(self._rotator._sites.keys()) if self._rotator else []

    def get_adapter_status(self, name: str) -> dict[str, Any]:
        """返回单个适配器的综合状态。"""
        site_state = self._rotator._sites.get(name) if self._rotator else None
        daily_used = self._quota.get_used(name) if self._quota else 0
        daily_limit = self._quota._limits.get(name, 500) if self._quota else 500

        health = None
        if self._db:
            try:
                health = self._db.fetchone(
                    "SELECT status, frozen_until, freeze_count, fail_streak FROM adapter_health WHERE name = ?",
                    (name,),
                )
            except Exception:
                pass

        remaining = 0
        if site_state and site_state.cooldown_until > 0:
            remaining = max(0, site_state.cooldown_until - time.time())

        return {
            "name": name,
            "status": health["status"] if health else "normal",
            "frozen_until": health["frozen_until"] if health else None,
            "remaining_seconds": int(remaining),
            "freeze_count": health["freeze_count"] if health else 0,
            "fail_streak": health["fail_streak"] if health else 0,
            "daily_used": daily_used,
            "daily_limit": daily_limit,
        }

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """返回所有适配器状态。"""
        return {name: self.get_adapter_status(name) for name in self.list_adapters()}
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/manager/adapter_manager.py
git commit -m "feat: 新增 AdapterManager（Manager层聚合SiteRotator+QuotaTracker+adapter_health）"
```

---

### Task A2.1: 在 StandardManager 中集成 AdapterManager

**文件：**
- Modify: `pilotstd/manager/facade.py`

- [ ] **Step 1: 在 StandardManager.__init__() 中实例化**

找到 `self.quota_tracker = ...` 行之后，添加：

```python
        # AdapterManager — 聚合适配器状态查询
        from .adapter_manager import AdapterManager

        self.adapter_manager = AdapterManager(
            db=self.db,
            rotator=self.rotator,
            quota_tracker=self.quota_tracker,
        )
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/manager/facade.py
git commit -m "feat: StandardManager 集成 AdapterManager"
```

---

### Task A2.2: 数据库迁移 last_changed_at

**文件：**
- Modify: `pilotstd/core/validity_checker.py`

- [ ] **Step 1: 修改 ValidityChecker.__init__() 添加自动迁移**

```python
# 修改前：
    def __init__(self, db: Database):
        self._db = db

# 修改后：
    def __init__(self, db: Any, config: Any = None):
        self._db = db
        self._ensure_last_changed_at_column()

    def _ensure_last_changed_at_column(self) -> None:
        """确保 standard_validity 表存在 last_changed_at 字段。"""
        try:
            cols = self._db.fetchall("PRAGMA table_info(standard_validity)")
            col_names = [c["name"] for c in cols]
            if "last_changed_at" not in col_names:
                self._db.execute("ALTER TABLE standard_validity ADD COLUMN last_changed_at TEXT")
                self._db.execute("UPDATE standard_validity SET last_changed_at = updated_at")
                self._db.commit()
                logger.info("standard_validity 表已添加 last_changed_at 字段并回填")
        except Exception as e:
            logger.warning("last_changed_at 迁移跳过: %s", e)
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/core/validity_checker.py
git commit -m "feat: standard_validity 新增 last_changed_at 字段（自动迁移+回填）"
```

---

### Task A2.3: update_status() 增加 last_changed_at 逻辑

**文件：**
- Modify: `pilotstd/core/validity_checker.py`

- [ ] **Step 1: 修改 update_status() 方法**

将 `update_status()` 方法完整替换为：

```python
    def update_status(self, standard_number: str, new_status: str, notification_mgr: Any = None) -> None:
        """更新标准时效性状态，设置下次检查时间=now + total_weeks*7 天。
        状态变更时同步更新 last_changed_at，未变化时仅更新 updated_at。
        """
        old_row = self._db.fetchone(
            f"SELECT status FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        old_status = old_row["status"] if old_row else None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        from .config import ConfigManager

        total_weeks = ConfigManager().get("validity.total_weeks", 4)
        next_check = (now + timedelta(days=total_weeks * 7)).isoformat()

        if old_status is None:
            self._db.execute(
                f"INSERT INTO {_TABLE} (standard_number, status, last_checked_at, "
                "next_check_at, last_changed_at, check_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (standard_number, new_status, now_iso, next_check, now_iso, now_iso, now_iso),
            )
        elif old_status != new_status:
            self._db.execute(
                f"UPDATE {_TABLE} SET status=?, last_checked_at=?, next_check_at=?, "
                "last_status=?, last_status_updated_at=?, last_changed_at=?, "
                "check_count=check_count+1, updated_at=? WHERE standard_number=?",
                (new_status, now_iso, next_check, old_status, now_iso, now_iso, now_iso, standard_number),
            )
            if notification_mgr:
                try:
                    event_type = "standard_expired" if new_status == "已废止" else "standard_status_changed"
                    notification_mgr.send_event(
                        event_type,
                        {
                            "standard_number": standard_number,
                            "old_status": old_status,
                            "new_status": new_status,
                        },
                    )
                except Exception:
                    pass
        else:
            self._db.execute(
                f"UPDATE {_TABLE} SET last_checked_at=?, next_check_at=?, "
                "check_count=check_count+1, updated_at=? WHERE standard_number=?",
                (now_iso, next_check, now_iso, standard_number),
            )
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/core/validity_checker.py
git commit -m "feat: update_status() 增加 last_changed_at 逻辑（状态变化时更新）"
```

---

### Task A2.4: 通知模块新增 4 个事件

**文件：**
- Modify: `pilotstd/core/notification/events.py`
- Modify: `pilotstd/core/notification/manager.py`
- Modify: `pilotstd/core/config.py`

- [ ] **Step 1: events.py 新增常量**

在 `EVENT_AUTO_SCAN_FAILED` 之后追加 4 个常量，并追加到 `ALL_EVENTS`：

```python
EVENT_VALIDITY_BATCH_REPORT = "validity_batch_report"
EVENT_VALIDITY_ROUND_SUMMARY = "validity_round_summary"
EVENT_VALIDITY_STANDARD_FAILED = "validity_standard_failed"
EVENT_VALIDITY_SYSTEM_FAILED = "validity_system_failed"

ALL_EVENTS = [
    EVENT_ARCHIVE_COMPLETE,
    EVENT_STATUS_CHANGED,
    EVENT_EXPIRED,
    EVENT_FIRST_REGISTERED,
    EVENT_CHECK_BATCH_COMPLETE,
    EVENT_ANNOUNCEMENT_FETCH,
    EVENT_AUTO_BACKUP,
    EVENT_ANNOUNCEMENT_CHECK,
    EVENT_BATCH_DOWNLOAD,
    EVENT_AUTO_SCAN_FAILED,
    EVENT_VALIDITY_BATCH_REPORT,
    EVENT_VALIDITY_ROUND_SUMMARY,
    EVENT_VALIDITY_STANDARD_FAILED,
    EVENT_VALIDITY_SYSTEM_FAILED,
]
```

- [ ] **Step 2: manager.py 新增 4 个消息模板**

在 `_build_message()` 方法中，`auto_scan_failed` 分支之后、`else` 之前插入：

```python
        elif event_type == "validity_batch_report":
            count = data.get("count", 0)
            changed = data.get("changed", 0)
            failed = data.get("failed", 0)
            adapters = data.get("adapters", {})
            adapter_summary = ", ".join(
                [f"{k}:{v.get('status','unknown')}" for k, v in adapters.items()]
            )[:100]
            return NotificationMessage(
                title="时效性检查完成",
                body=f"本次检查 {count} 条，变更 {changed} 条，失败 {failed} 条 | 适配器: {adapter_summary}",
                level="info" if failed == 0 else "warning",
                event_type=event_type,
            )

        elif event_type == "validity_round_summary":
            total_checks = data.get("total_checks", 0)
            total_changes = data.get("total_changes", 0)
            total_failures = data.get("total_failures", 0)
            change_list = data.get("change_list", [])
            change_preview = ", ".join(change_list[:5])
            if len(change_list) > 5:
                change_preview += f" 等 {len(change_list)} 项"
            return NotificationMessage(
                title="周期总结汇报",
                body=f"总检查 {total_checks} 条，总变更 {total_changes} 条，总失败 {total_failures} 条 | 变更: {change_preview}",
                level="info",
                event_type=event_type,
            )

        elif event_type == "validity_standard_failed":
            standard_number = data.get("standard_number", "未知")
            error = data.get("error", "未知错误")
            return NotificationMessage(
                title="标准检查失败",
                body=f"标准 {standard_number} 检查失败: {error}",
                level="error",
                event_type=event_type,
            )

        elif event_type == "validity_system_failed":
            error = data.get("error", "未知错误")
            return NotificationMessage(
                title="时效性检查系统异常",
                body=f"系统执行异常: {error}",
                level="error",
                event_type=event_type,
            )
```

- [ ] **Step 3: config.py FACTORY_DEFAULTS 新增 4 个默认规则**

在 `"notification.rules.auto_scan_failed"` 之后添加：

```python
    "notification.rules.validity_batch_report": ["wechat"],
    "notification.rules.validity_round_summary": ["wechat"],
    "notification.rules.validity_standard_failed": ["wechat"],
    "notification.rules.validity_system_failed": ["wechat"],
```

- [ ] **Step 4: Commit**

```bash
git add pilotstd/core/notification/events.py pilotstd/core/notification/manager.py pilotstd/core/config.py
git commit -m "feat: 新增4个validity通知事件（batch_report/round_summary/standard_failed/system_failed）"
```

---

### Task A2.5: run_validity_check() 增强

**文件：**
- Modify: `pilotstd/core/validity_checker.py`

- [ ] **Step 1: 函数签名新增 adapter_mgr 参数 + 收集器初始化**

将函数签名和开头部分修改为：

```python
def run_validity_check(notification_mgr: Any = None, db: Any = None, adapter_mgr: Any = None, update_counters: bool = False) -> dict:
    """执行时效性检查，供 API 和调度器共同调用。

    Args:
        notification_mgr: 通知管理器实例，可选
        db: 数据库连接，可选
        adapter_mgr: AdapterManager 实例，可选（聚合适配器状态）
        update_counters: 是否更新 checked_count/round_completed（仅调度器为 True）

    Returns:
        {"ok": bool, "checked": int, "changed": int, "error": str|None}
    """
    if not _VALIDITY_LOCK.acquire(blocking=False):
        return {"ok": False, "checked": 0, "changed": 0, "error": "检查正在执行中"}
    try:
        import time as _time

        if db is None:
            from .config import get_db_path
            from .db import Database

            db = Database(get_db_path())

        from .config import ConfigManager

        config = ConfigManager()
        checker = ValidityChecker(db)

        check_ratio = config.get("validity.check_ratio", 25)
        batch_size = config.get("validity.batch_size", 50)
        batch_interval = config.get("validity.batch_interval", 5)

        due = checker.get_due_standards()
        if not due:
            return {"ok": True, "checked": 0, "changed": 0}

        rng = random.Random(int(_time.time()))
        shuffled = list(due)
        rng.shuffle(shuffled)
        sample_size = max(1, int(len(shuffled) * check_ratio / 100))
        candidates = shuffled[:sample_size]

        changed_list: list[str] = []
        failed_list: list[dict] = []
        changed = 0
```

- [ ] **Step 2: 修改检查循环，收集变更和失败**

```python
        for i, std_no in enumerate(candidates):
            try:
                result = checker.check_standard(std_no)
                if result:
                    old_row = db.fetchone(
                        f"SELECT status FROM {_TABLE} WHERE standard_number=?",
                        (std_no,),
                    )
                    old_status = old_row["status"] if old_row else None
                    new_status = result["status"] or "现行"
                    checker.update_status(std_no, new_status, notification_mgr)
                    if old_status and old_status != new_status:
                        changed_list.append(std_no)
                        changed += 1
                        # 每 10 条变更发一条分条通知
                        if len(changed_list) % 10 == 0 and notification_mgr:
                            try:
                                notification_mgr.send_event("validity_batch_report", {
                                    "count": 0,
                                    "changed": 10,
                                    "failed": 0,
                                    "adapters": {},
                                    "change_detail": changed_list[-10:],
                                })
                            except Exception:
                                pass
            except Exception as e:
                failed_list.append({"standard": std_no, "error": str(e)})
                if notification_mgr:
                    try:
                        notification_mgr.send_event("validity_standard_failed", {
                            "standard_number": std_no,
                            "error": str(e),
                        })
                    except Exception:
                        pass
            if i > 0 and i % batch_size == 0 and batch_interval > 0:
                _time.sleep(batch_interval)
```

- [ ] **Step 3: 获取适配器状态**

```python
        # 获取适配器状态
        adapters_status: dict = {}
        if adapter_mgr:
            try:
                adapters_status = adapter_mgr.get_all_status()
            except Exception as e:
                logger.warning("获取适配器状态失败: %s", e)
```

- [ ] **Step 4: 发送每次汇总 + 周期汇总 + 更新计数器**

替换现有的 `update_counters` 和 `notification_mgr` 代码块：

```python
        if update_counters:
            current_count = config.get("validity.checked_count", 0)
            new_count = current_count + len(candidates)
            config.set("validity.checked_count", new_count)
            try:
                total_row = db.fetchone("SELECT COUNT(*) AS cnt FROM standard_validity")
                total = total_row["cnt"] if total_row else 0
                if total > 0 and new_count >= total:
                    config.set("validity.round_completed", True)
                    # 发送周期汇总
                    if notification_mgr:
                        try:
                            changes = db.fetchall(
                                "SELECT standard_number FROM standard_validity "
                                "WHERE last_changed_at IS NOT NULL "
                                "ORDER BY last_changed_at DESC LIMIT 200"
                            )
                            cycle_change_list = [r["standard_number"] for r in changes]
                            notification_mgr.send_event("validity_round_summary", {
                                "total_checks": new_count,
                                "total_changes": len(cycle_change_list),
                                "total_failures": len(failed_list),
                                "change_list": cycle_change_list,
                                "adapter_summary": adapters_status,
                            })
                        except Exception:
                            pass
            except Exception:
                pass
            config.save()

        # 发送每次汇总报告
        if notification_mgr:
            try:
                notification_mgr.send_event("validity_batch_report", {
                    "count": len(candidates),
                    "changed": len(changed_list),
                    "failed": len(failed_list),
                    "adapters": adapters_status,
                })
            except Exception:
                pass

        logger.info("时效性检查完成: checked=%d changed=%d failed=%d", len(candidates), len(changed_list), len(failed_list))
        return {"ok": True, "checked": len(candidates), "changed": len(changed_list)}
```

- [ ] **Step 5: 系统级异常通知**

修改 except 块：

```python
    except Exception as e:
        logger.exception("时效性检查执行失败")
        if notification_mgr:
            try:
                import traceback
                notification_mgr.send_event("validity_system_failed", {
                    "error": str(e),
                    "traceback": traceback.format_exc()[:500],
                })
            except Exception:
                pass
        return {"ok": False, "checked": 0, "changed": 0, "error": str(e)}
    finally:
        _VALIDITY_LOCK.release()
```

- [ ] **Step 6: Commit**

```bash
git add pilotstd/core/validity_checker.py
git commit -m "feat: run_validity_check() 增强——收集变更/失败/适配器状态，触发4类新通知"
```

---

### Task A2.6: 调用方传入 adapter_mgr

**文件：**
- Modify: `docker/api/validity.py`
- Modify: `docker/scheduler.py`
- Modify: `docker/app.py`

- [ ] **Step 1: docker/api/validity.py — 传入 adapter_mgr**

将调用行改为：

```python
    result = do_check(
        notification_mgr=mgr.notification_mgr,
        db=mgr.db,
        adapter_mgr=mgr.adapter_manager,
        update_counters=False,
    )
```

- [ ] **Step 2: docker/scheduler.py — _check_validity_schedule() 传参**

修改 `_check_validity_schedule()` 函数签名，并在调用 run_validity_check 时传入：

```python
def _check_validity_schedule(notification_mgr=None, adapter_mgr=None):
    # ... 现有逻辑不变 ...
    run_validity_check(
        notification_mgr=notification_mgr,
        update_counters=True,
        adapter_mgr=adapter_mgr,
    )
    # ...
```

- [ ] **Step 3: docker/app.py — 注册时传入 adapter_mgr**

修改 validity_wake 注册行：

```python
    register_job_func("validity_wake", lambda: _check_validity_schedule(
        notification_mgr=_cron_mgr.notification_mgr,
        adapter_mgr=_cron_mgr.adapter_manager,
    ))
```

- [ ] **Step 4: Commit**

```bash
git add docker/api/validity.py docker/scheduler.py docker/app.py
git commit -m "feat: 调用方传入 adapter_mgr 到 run_validity_check()"
```

---

### 验证

- [ ] **Step 1: ruff + mypy**

```bash
ruff check pilotstd docker --fix && ruff format pilotstd docker && mypy pilotstd docker --follow-imports=skip
```

- [ ] **Step 2: 前端类型检查**

```bash
cd web && npm run type-check
```

- [ ] **Step 3: 运行相关测试**

```bash
python -m pytest tests/test_docker_scheduler.py -v
```

---

## 文件变更总览

| # | 文件 | 操作 | 层 |
|---|------|------|-----|
| 1 | `pilotstd/manager/adapter_manager.py` | **新建** | Manager |
| 2 | `pilotstd/manager/facade.py` | 修改 | Manager |
| 3 | `pilotstd/core/notification/manager.py` | 修改 | Core |
| 4 | `pilotstd/core/notification/events.py` | 修改 | Core |
| 5 | `pilotstd/core/config.py` | 修改 | Core |
| 6 | `pilotstd/core/validity_checker.py` | 修改 | Core |
| 7 | `docker/api/validity.py` | 修改 | API |
| 8 | `docker/scheduler.py` | 修改 | API |
| 9 | `docker/app.py` | 修改 | API |

## 前端修改汇总（本次不实施）

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `web/src/components/NotificationConfig.vue` | 新增 4 个事件勾选项 | 高 |
| `web/src/components/NotificationLogsView.vue` | 新增 4 个事件标签映射 | 高 |
