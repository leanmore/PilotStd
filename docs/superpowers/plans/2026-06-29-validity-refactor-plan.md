# Validity 重构 + 调度接入 + auto_query 删除 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 auto_query 死代码全链路，将 validity 核心逻辑迁移到 `pilotstd/core/validity_checker.py`，通过 APScheduler 间隔唤醒实现调度化自动执行。

**Architecture:** APScheduler 每 5 分钟唤醒 `_check_validity_schedule()`，内部读取 `next_run` 配置判断是否到执行时间，满足条件时调用底层的 `run_validity_check()`。API `/validity/run` 也直接调用同一个 `run_validity_check()`，仅不更新轮次计数器。

**Tech Stack:** Python 3.12, FastAPI, APScheduler, SQLite, threading

---

## 第一部分：删除 auto_query

### Task 1.1: 移除 docker/scheduler.py 中 auto_query 的 cron 注册

**文件：** `docker/scheduler.py:168-183`

- [ ] **Step 1: 从 start_scheduler() 中移除 auto_query 行**

在 `start_scheduler()` 函数中，移除 for 循环中的 `auto_query` 元组：

```python
# 修改前（第 174-178 行）：
    for job_id, cron_key, enabled_key in [
        ("auto_scan", "tasks.auto_scan_cron", "tasks.auto_scan_enabled"),
        ("auto_query", "tasks.auto_query_cron", "tasks.auto_query_enabled"),
        ("auto_announce", "tasks.auto_announce_cron", "tasks.auto_announce_enabled"),
        ("auto_backup", "tasks.auto_backup_cron", "tasks.auto_backup_enabled"),
    ]:

# 修改后：
    for job_id, cron_key, enabled_key in [
        ("auto_scan", "tasks.auto_scan_cron", "tasks.auto_scan_enabled"),
        ("auto_announce", "tasks.auto_announce_cron", "tasks.auto_announce_enabled"),
        ("auto_backup", "tasks.auto_backup_cron", "tasks.auto_backup_enabled"),
    ]:
```

- [ ] **Step 2: Commit**

```bash
git add docker/scheduler.py
git commit -m "fix: 移除 auto_query 的调度 cron 注册"
```

---

### Task 1.2: 移除 docker/app.py 中 auto_query 的注册

**文件：** `docker/app.py:80`

- [ ] **Step 1: 删除 register_job_func("auto_query", ...) 行**

```python
# 修改前（第 79-81 行）：
    register_job_func("auto_scan", lambda: _cron_mgr.scan_and_index())
    register_job_func("auto_query", lambda: _cron_mgr.recheck_updates())
    from .api.announce import check_announce

# 修改后：
    register_job_func("auto_scan", lambda: _cron_mgr.scan_and_index())
    from .api.announce import check_announce
```

- [ ] **Step 2: Commit**

```bash
git add docker/app.py
git commit -m "fix: 移除 auto_query 的 app 注册"
```

---

### Task 1.3: 删除 scheduled_service.py 的 recheck_updates()

**文件：** `pilotstd/manager/scheduled_service.py:79-109`

- [ ] **Step 1: 删除 recheck_updates() 方法完整定义**

删除第 79-109 行（从 `# 更新检测` 注释到方法结束的 `return {"checked": checked, "updated": updated}` 行后）：

```python
# 删除此整个代码块（第 79-109 行）：
    # ════════════════════════════════════════════════════════════════
    # 更新检测
    # ════════════════════════════════════════════════════════════════

    def recheck_updates(self) -> dict[str, int]:
        """定时任务专用：重新查询 file_index 中的现行标准，检测是否有更新/废止。"""
        rows = self._file_index.get_recheck_candidates(limit=500)
        if not rows:
            return {"checked": 0, "updated": 0}
        updated = 0
        checked = 0
        for row in rows:
            lc = row.get("logical_code", "")
            num = row.get("number", 0)
            yr = row.get("year", 0)
            if not lc or not num:
                continue
            r_list = self._query_engine.query_standards([(lc, num, yr, "", None, row.get("num_prefix", ""))])
            checked += 1
            r = r_list[0] if r_list else None
            if r and r.is_found() and r.status != row.get("status"):
                self._file_index.upsert(
                    row["file_path"],
                    logical_code=lc,
                    number=num,
                    year=yr,
                    std_name=r.standard_name,
                    status=r.status,
                )
                updated += 1
        return {"checked": checked, "updated": updated}
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/manager/scheduled_service.py
git commit -m "fix: 删除 recheck_updates() 方法"
```

---

### Task 1.4: 删除 facade.py 的 recheck_updates() 透传

**文件：** `pilotstd/manager/facade.py:1210-1212`

- [ ] **Step 1: 删除 recheck_updates() 透传方法**

删除第 1210-1212 行：

```python
# 删除以下代码：
    def recheck_updates(self) -> dict[str, int]:
        """定时任务专用：重新查询 file_index 中的现行标准，检测是否有更新/废止。"""
        return self._scheduled_svc.recheck_updates()  # type: ignore[no-any-return]
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/manager/facade.py
git commit -m "fix: 删除 facade 层 recheck_updates() 透传"
```

---

### Task 1.5: 删除 file_index.py 的 get_recheck_candidates()

**文件：** `pilotstd/core/file_index.py:157-164`

- [ ] **Step 1: 删除 get_recheck_candidates() 方法**

删除第 157-164 行：

```python
# 删除以下代码：
    def get_recheck_candidates(self, limit: int = 500) -> list[dict[str, Any]]:
        """返回需重新查询的标准（7天未检查的现行标准）。"""
        return self._db.fetchall(
            "SELECT * FROM file_index WHERE status='现行' AND "
            "(last_checked IS NULL OR last_checked < date('now', '-7 days')) "
            "ORDER BY last_checked ASC LIMIT ?",
            (limit,),
        )
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/core/file_index.py
git commit -m "fix: 删除 get_recheck_candidates() 方法"
```

---

### Task 1.6: 移除 docker/api/settings.py 中 auto_query 的读/写引用

**文件：** `docker/api/settings.py:53-54, 105`

- [ ] **Step 1: GET 接口移除 auto_query 字段**

在 `get_settings()` 函数中，删除 tasks 字典里的两行（第 53-54 行）：

```python
# 修改前（第 50-57 行）：
        "tasks": {
            "auto_scan_enabled": cfg.get("tasks.auto_scan_enabled", False),
            "auto_scan_cron": cfg.get("tasks.auto_scan_cron", "0 3 * * *"),
            "auto_query_enabled": cfg.get("tasks.auto_query_enabled", False),
            "auto_query_cron": cfg.get("tasks.auto_query_cron", "0 5 * * *"),
            "auto_announce_enabled": cfg.get("tasks.auto_announce_enabled", False),
            "auto_announce_cron": cfg.get("tasks.auto_announce_cron", "0 1 * * *"),
        },

# 修改后：
        "tasks": {
            "auto_scan_enabled": cfg.get("tasks.auto_scan_enabled", False),
            "auto_scan_cron": cfg.get("tasks.auto_scan_cron", "0 3 * * *"),
            "auto_announce_enabled": cfg.get("tasks.auto_announce_enabled", False),
            "auto_announce_cron": cfg.get("tasks.auto_announce_cron", "0 1 * * *"),
        },
```

- [ ] **Step 2: PUT 接口移除 auto_query 同步逻辑**

在 `put_settings()` 函数中，从任务同步循环移除 auto_query：

```python
# 修改前（第 103-107 行）：
    for job_id, cron_key in [
        ("auto_scan", "auto_scan_cron"),
        ("auto_query", "auto_query_cron"),
        ("auto_announce", "auto_announce_cron"),
    ]:

# 修改后：
    for job_id, cron_key in [
        ("auto_scan", "auto_scan_cron"),
        ("auto_announce", "auto_announce_cron"),
    ]:
```

- [ ] **Step 3: Commit**

```bash
git add docker/api/settings.py
git commit -m "fix: 移除前端设置接口中的 auto_query 配置项"
```

---

### Task 1.7: 移除测试文件中的 auto_query 引用

**文件：** `tests/test_docker_scheduler.py:63-64, 74-75`

- [ ] **Step 1: 从 mock 数据中移除 auto_query 配置**

在 `test_start_scheduler_adds_enabled_jobs` 测试方法中：

```python
# 修改前（第 60-67 行）：
        mock_cfg.return_value.get.side_effect = lambda key, default: {
            "tasks.auto_scan_enabled": True,
            "tasks.auto_scan_cron": "0 3 * * *",
            "tasks.auto_query_enabled": False,
            "tasks.auto_query_cron": "0 5 * * *",
            "tasks.auto_announce_enabled": False,
            "tasks.auto_announce_cron": "0 1 * * *",
        }.get(key, default)

# 修改后：
        mock_cfg.return_value.get.side_effect = lambda key, default: {
            "tasks.auto_scan_enabled": True,
            "tasks.auto_scan_cron": "0 3 * * *",
            "tasks.auto_announce_enabled": False,
            "tasks.auto_announce_cron": "0 1 * * *",
        }.get(key, default)
```

- [ ] **Step 2: 移除 auto_query 断言**

在同一测试方法中：

```python
# 修改前（第 74-75 行）：
        self.assertTrue(any(j.id == "auto_scan" for j in scheduler.get_jobs()))
        self.assertFalse(any(j.id == "auto_query" for j in scheduler.get_jobs()))

# 修改后：
        self.assertTrue(any(j.id == "auto_scan" for j in scheduler.get_jobs()))
```

- [ ] **Step 3: 运行测试确认通过**

```bash
python -m pytest tests/test_docker_scheduler.py -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_docker_scheduler.py
git commit -m "test: 移除 auto_query 测试引用"
```

---

## 第二部分：配置项调整

### Task 2.1: 更新 pilotstd/core/config.py 默认配置

**文件：** `pilotstd/core/config.py:173-179`

- [ ] **Step 1: 新增 5 项配置，废弃 3 项旧配置**

在 `_DEFAULTS` 字典中，将第 173-179 行替换为：

```python
# 修改前（第 173-179 行）：
    # 时效性检查配置
    "validity.frequency": "weekly",
    "validity.execute_time": "03:00",
    "validity.batch_size": 50,
    "validity.batch_interval": 5,
    "validity.check_ratio": 25,
    "validity.update_interval": 28,

# 修改后：
    # 时效性检查配置
    "validity.first_execution": None,       # datetime 或 None，用户首次设置
    "validity.total_weeks": 4,              # int，范围 4~52
    "validity.next_run": None,              # datetime 或 None，系统计算的下次执行
    "validity.checked_count": 0,            # int，当前轮次已检查标准数
    "validity.round_completed": False,      # bool，当前轮次是否完成
    "validity.batch_size": 50,
    "validity.batch_interval": 5,
    "validity.check_ratio": 25,
    # 以下已废弃，保留键名兼容旧数据但不再读取
    "validity.frequency": "weekly",         # @deprecated
    "validity.execute_time": "03:00",       # @deprecated
    "validity.update_interval": 28,         # @deprecated
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/core/config.py
git commit -m "feat: validity 配置新增5项（first_execution/total_weeks等），废弃3项旧配置"
```

---

### Task 2.2: 更新 docker/api/validity.py GET/PUT 配置接口

**文件：** `docker/api/validity.py:21-106`

- [ ] **Step 1: 修改默认配置字典**

```python
# 修改前（第 21-31 行）：
_VALID_FREQUENCIES = ("daily", "weekly", "monthly")
_FREQUENCY_MAP = {"每日": "daily", "每周": "weekly", "每月": "monthly"}

_DEFAULT_CONFIG = {
    "frequency": "weekly",
    "execute_time": "03:00",
    "batch_size": 50,
    "batch_interval": 5,
    "check_ratio": 25,
    "update_interval": 28,
}

# 修改后：
_DEFAULT_CONFIG = {
    "batch_size": 50,
    "batch_interval": 5,
    "check_ratio": 25,
    "total_weeks": 4,
}
```

- [ ] **Step 2: 修改 GET /validity/config 接口**

```python
# 修改前（第 34-45 行）：
@router.get("/api/validity/config")
def get_validity_config(mgr=Depends(get_manager_dep)):
    """读取时效性检查配置，未设置时返回默认值。"""
    cfg = mgr.cfg
    return {
        "frequency": cfg.get("validity.frequency") or _DEFAULT_CONFIG["frequency"],
        "execute_time": cfg.get("validity.execute_time") or _DEFAULT_CONFIG["execute_time"],
        "batch_size": cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"],
        "batch_interval": cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"],
        "check_ratio": cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"],
        "update_interval": cfg.get("validity.update_interval") or _DEFAULT_CONFIG["update_interval"],
    }

# 修改后：
@router.get("/api/validity/config")
def get_validity_config(mgr=Depends(get_manager_dep)):
    """读取时效性检查配置，未设置时返回默认值。"""
    cfg = mgr.cfg
    return {
        "batch_size": cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"],
        "batch_interval": cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"],
        "check_ratio": cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"],
        "total_weeks": cfg.get("validity.total_weeks") or _DEFAULT_CONFIG["total_weeks"],
        "first_execution": cfg.get("validity.first_execution"),
        "next_run": cfg.get("validity.next_run"),
        "checked_count": cfg.get("validity.checked_count", 0),
        "round_completed": cfg.get("validity.round_completed", False),
        # 已废弃字段（兼容旧前端）
        "frequency": cfg.get("validity.frequency") or "weekly",
        "execute_time": cfg.get("validity.execute_time") or "03:00",
        "update_interval": cfg.get("validity.update_interval") or 28,
    }
```

- [ ] **Step 3: 修改 PUT /validity/config 接口**

```python
# 修改前（第 48-106 行完整替换为以下）：
@router.put("/api/validity/config")
def update_validity_config(body: dict, mgr=Depends(get_manager_dep)):
    """更新时效性检查配置，校验后写入 ConfigManager。"""
    errors: list[str] = []

    first_execution = body.get("first_execution")
    if first_execution is not None:
        try:
            from datetime import datetime
            datetime.fromisoformat(str(first_execution))
        except (ValueError, TypeError):
            errors.append("first_execution 格式必须为 ISO datetime（如 2026-07-01T03:00:00）")

    total_weeks = body.get("total_weeks")
    if total_weeks is not None and (not isinstance(total_weeks, int) or total_weeks < 4 or total_weeks > 52):
        errors.append("total_weeks 必须为 4-52 之间的整数")

    batch_size = body.get("batch_size")
    if batch_size is not None and (not isinstance(batch_size, int) or batch_size < 1):
        errors.append("batch_size 必须为 >=1 的整数")

    batch_interval = body.get("batch_interval")
    if batch_interval is not None and (not isinstance(batch_interval, int) or batch_interval < 1):
        errors.append("batch_interval 必须为 >=1 的整数")

    check_ratio = body.get("check_ratio")
    if check_ratio is not None and (not isinstance(check_ratio, int) or check_ratio < 1 or check_ratio > 100):
        errors.append("check_ratio 必须为 1-100 之间的整数")

    if errors:
        return JSONResponse({"error": "参数校验失败", "details": errors}, status_code=400)

    field_map = {
        "first_execution": "validity.first_execution",
        "total_weeks": "validity.total_weeks",
        "batch_size": "validity.batch_size",
        "batch_interval": "validity.batch_interval",
        "check_ratio": "validity.check_ratio",
    }
    # 已废弃字段：接受但不写入（frequency, execute_time, update_interval 被忽略）
    try:
        for json_key, cfg_key in field_map.items():
            val = body.get(json_key)
            if val is not None:
                mgr.cfg.set(cfg_key, val)
        mgr.cfg.save()
        logger.info("时效性检查配置已更新")
    except Exception as e:
        logger.exception("时效性检查配置写入失败")
        return JSONResponse({"error": f"配置写入失败: {e}"}, status_code=500)

    return {"ok": True, "message": "配置已更新"}
```

- [ ] **Step 4: Commit**

```bash
git add docker/api/validity.py
git commit -m "feat: validity 配置接口更新—新增字段/废弃旧字段/忽略写入"
```

---

## 第三部分：validity 迁移到底层

### Task 3.1: 修复 update_status() 硬编码 bug

**文件：** `pilotstd/core/validity_checker.py:58-104`

- [ ] **Step 1: 将 timedelta(days=28) 改为读取 total_weeks 配置**

```python
# 修改前（第 63-64 行）：
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        next_check = (now + timedelta(days=28)).isoformat()

# 修改后：
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        from .config import ConfigManager
        total_weeks = ConfigManager().get("validity.total_weeks", 4)
        next_check = (now + timedelta(days=total_weeks * 7)).isoformat()
```

- [ ] **Step 2: Commit**

```bash
git add pilotstd/core/validity_checker.py
git commit -m "fix: update_status() 硬编码28天改为读取 total_weeks 配置"
```

---

### Task 3.2: 新增 run_validity_check() 纯执行函数

**文件：** `pilotstd/core/validity_checker.py`（在文件末尾，`get_status_summary()` 之后添加）

- [ ] **Step 1: 在文件顶部添加 import**

在现有 imports 后添加：

```python
import threading
```

- [ ] **Step 2: 在 ValidityChecker 类定义之后、文件末尾添加模块级锁 + 函数**

```python
# ── 模块级并发锁 ──────────────────────────────────────────
_VALIDITY_LOCK = threading.Lock()


# ── 纯执行函数（API + 调度器共用）───────────────────────────

def run_validity_check(notification_mgr: Any = None, db: Any = None, update_counters: bool = False) -> dict:
    """执行时效性检查，供 API 和调度器共同调用。

    Args:
        notification_mgr: 通知管理器实例，可选
        db: 数据库连接，可选（默认从 Database 获取）
        update_counters: 是否更新 checked_count/round_completed（仅调度器为 True）

    Returns:
        {"ok": bool, "checked": int, "changed": int, "error": str|None}
    """
    if not _VALIDITY_LOCK.acquire(blocking=False):
        return {"ok": False, "checked": 0, "changed": 0, "error": "检查正在执行中"}
    try:
        import time as _time

        if db is None:
            from .db import Database
            from .config import get_db_path
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

        changed = 0
        for i, std_no in enumerate(candidates):
            try:
                result = checker.check_standard(std_no)
                if result:
                    checker.update_status(std_no, result["status"], notification_mgr)
                    if result.get("previous") and result["previous"] != result["status"]:
                        changed += 1
            except Exception as e:
                logger.warning("检查标准 %s 失败: %s", std_no, e)
            if i > 0 and i % batch_size == 0 and batch_interval > 0:
                _time.sleep(batch_interval)

        if update_counters:
            current_count = config.get("validity.checked_count", 0)
            new_count = current_count + len(candidates)
            config.set("validity.checked_count", new_count)
            try:
                total_row = db.fetchone("SELECT COUNT(*) AS cnt FROM standard_validity")
                total = total_row["cnt"] if total_row else 0
                if total > 0 and new_count >= total:
                    config.set("validity.round_completed", True)
            except Exception:
                pass
            config.save()

        if notification_mgr:
            try:
                notification_mgr.send_event("check_batch_complete", {
                    "count": len(candidates),
                    "changed": changed,
                })
            except Exception:
                pass

        logger.info("时效性检查完成: checked=%d changed=%d", len(candidates), changed)
        return {"ok": True, "checked": len(candidates), "changed": changed}
    except Exception as e:
        logger.exception("时效性检查执行失败")
        return {"ok": False, "checked": 0, "changed": 0, "error": str(e)}
    finally:
        _VALIDITY_LOCK.release()
```

- [ ] **Step 3: Commit**

```bash
git add pilotstd/core/validity_checker.py
git commit -m "feat: 新增 run_validity_check() 纯执行函数，供API和调度器共用"
```

---

### Task 3.3: API POST /validity/run 改为调用底层函数

**文件：** `docker/api/validity.py:109-173`

- [ ] **Step 1: 替换 run_validity_check 端点实现**

```python
# 修改前（第 109-173 行完整替换为以下）：
@router.post("/api/validity/run")
def run_validity_check(mgr=Depends(get_manager_dep)):
    """立即触发时效性检查——对到期标准执行三级检查。"""
    try:
        checker = mgr.validity_checker
        due = checker.get_due_standards()
        if not due:
            return {"ok": True, "message": "无到期标准需检查", "checked": 0, "changed": 0}

        # 按配置的 batch_size 和 check_ratio 取切片
        batch_size = mgr.cfg.get("validity.batch_size") or _DEFAULT_CONFIG["batch_size"]
        ratio = mgr.cfg.get("validity.check_ratio") or _DEFAULT_CONFIG["check_ratio"]
        # 随机切片
        import random
        import time as _time

        rng = random.Random(int(_time.time()))
        shuffled = list(due)
        rng.shuffle(shuffled)
        sample_size = max(1, int(len(shuffled) * ratio / 100))
        candidates = shuffled[:sample_size]

        changed = 0
        engine = mgr.query_engine if hasattr(mgr, "query_engine") else None
        interval = mgr.cfg.get("validity.batch_interval") or _DEFAULT_CONFIG["batch_interval"]

        for i, std_no in enumerate(candidates):
            try:
                result = checker.check_standard(std_no, query_engine=engine)
                if result:
                    checker.update_status(std_no, result["status"], mgr.notification_mgr)
                    if result.get("previous") and result["previous"] != result["status"]:
                        changed += 1
            except Exception as e:
                logger.warning("检查标准 %s 失败: %s", std_no, e)
            # 批次间隔
            if i > 0 and i % batch_size == 0 and interval > 0:
                _time.sleep(interval)

        logger.info("时效性检查完成: checked=%d changed=%d", len(candidates), changed)

        if mgr.notification_mgr:
            try:
                mgr.notification_mgr.send_event(
                    "check_batch_complete",
                    {
                        "count": len(candidates),
                        "changed": changed,
                    },
                )
            except Exception:
                pass

        # 时效性检查完成后标记缓存失效
        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(mgr.db).invalidate_by_source(DataSource.VALIDITY)
        except Exception:
            pass

        return {"ok": True, "checked": len(candidates), "changed": changed}
    except Exception as e:
        logger.exception("时效性检查执行失败")
        return JSONResponse({"error": f"执行失败: {e}"}, status_code=500)


# 修改后：
@router.post("/api/validity/run")
def run_validity_check_api(mgr=Depends(get_manager_dep)):
    """立即触发时效性检查——调用底层 run_validity_check()。"""
    from pilotstd.core.validity_checker import run_validity_check as do_check

    result = do_check(notification_mgr=mgr.notification_mgr, db=mgr.db, update_counters=False)
    if result["ok"]:
        # 时效性检查完成后标记缓存失效
        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(mgr.db).invalidate_by_source(DataSource.VALIDITY)
        except Exception:
            pass
        return {"ok": True, "checked": result["checked"], "changed": result["changed"]}
    else:
        return JSONResponse({"error": result.get("error", "执行失败")}, status_code=500)
```

- [ ] **Step 2: Commit**

```bash
git add docker/api/validity.py
git commit -m "feat: API /validity/run 改为调用底层 run_validity_check()"
```

---

## 第四部分：调度器接入

### Task 4.1: scheduler.py 新增 _check_validity_schedule() + _add_interval_job()

**文件：** `docker/scheduler.py`

- [ ] **Step 1: 在 _add_cron_job() 之后添加 _add_interval_job() 辅助函数**

在第 56 行之后（`_add_cron_job` 函数之后）添加：

```python
def _add_interval_job(job_id: str, interval_seconds: int):
    """向调度器添加 interval 定时任务（唤醒模式）。"""
    from apscheduler.triggers.interval import IntervalTrigger

    func = _job_funcs.get(job_id)
    if func:
        scheduler.add_job(func, IntervalTrigger(seconds=interval_seconds), id=job_id, replace_existing=True)
```

- [ ] **Step 2: 在文件末尾 stop_scheduler() 之前添加 _check_validity_schedule()**

```python
def _check_validity_schedule(notification_mgr=None):
    """APScheduler 唤醒函数：检查是否到了 validity 执行时间。"""
    import math
    from datetime import datetime, timedelta

    config = ConfigManager()
    first_execution_str = config.get("validity.first_execution")
    next_run_str = config.get("validity.next_run")
    round_completed = config.get("validity.round_completed", False)

    if first_execution_str is None:
        return

    if round_completed:
        config.set("validity.round_completed", False)
        config.set("validity.checked_count", 0)
        now = datetime.now()
        config.set("validity.next_run", (now + timedelta(minutes=1)).isoformat())
        config.save()
        logger.info("validity 轮次完成，自动重置，下一轮将于 1 分钟后开始")
        return

    now = datetime.now()

    if next_run_str is None:
        try:
            first_execution = datetime.fromisoformat(first_execution_str)
        except (ValueError, TypeError):
            logger.warning("validity.first_execution 格式无效: %s", first_execution_str)
            return
        if now < first_execution:
            return
    else:
        try:
            next_run = datetime.fromisoformat(next_run_str)
        except (ValueError, TypeError):
            logger.warning("validity.next_run 格式无效: %s", next_run_str)
            return
        if now < next_run:
            return

    # 执行检查
    from pilotstd.core.validity_checker import run_validity_check

    run_validity_check(notification_mgr=notification_mgr, update_counters=True)

    # 计算下次执行时间
    check_ratio = config.get("validity.check_ratio", 25)
    total_weeks = config.get("validity.total_weeks", 4)
    total_runs = math.ceil(100 / check_ratio)
    total_days = total_weeks * 7
    interval_days = math.ceil(total_days / total_runs)

    next_dt = now + timedelta(days=interval_days)
    config.set("validity.next_run", next_dt.isoformat())
    config.save()
    logger.info("validity 下次执行时间: %s（间隔 %d 天）", next_dt.isoformat(), interval_days)
```

- [ ] **Step 3: 在 start_scheduler() 末尾添加 validity_wake 注册**

在 `start_scheduler()` 函数中，`scheduler.start()` 之前添加：

```python
# 在 scheduler.start() 之前添加 validity_wake 间隔任务
_add_interval_job("validity_wake", 300)
```

完整上下文：

```python
def start_scheduler():
    """启动调度器：获取互斥锁 → 注册定时任务 → 启动心跳线程。"""
    if not _acquire_scheduler_lock():
        return

    cfg = ConfigManager()
    for job_id, cron_key, enabled_key in [
        ("auto_scan", "tasks.auto_scan_cron", "tasks.auto_scan_enabled"),
        ("auto_announce", "tasks.auto_announce_cron", "tasks.auto_announce_enabled"),
        ("auto_backup", "tasks.auto_backup_cron", "tasks.auto_backup_enabled"),
    ]:
        default_enabled = (job_id == "auto_backup") or cfg.get(enabled_key, False)
        if cfg.get(enabled_key, default_enabled):
            default_cron = "0 3 * * 0" if job_id == "auto_backup" else "0 0 * * *"
            _add_cron_job(job_id, cfg.get(cron_key, default_cron))
    _add_interval_job("validity_wake", 300)
    scheduler.start()
    _heartbeat_stop.clear()
    threading.Thread(target=_heartbeat_loop, daemon=True, name="scheduler-heartbeat").start()
    logger.info("APScheduler 已启动")
```

- [ ] **Step 4: Commit**

```bash
git add docker/scheduler.py
git commit -m "feat: 新增 validity 唤醒调度（每5分钟检查，内部判断执行时机）"
```

---

### Task 4.2: 在 app.py 中注册 validity_wake

**文件：** `docker/app.py:45, 80-85`

- [ ] **Step 1: 添加 _check_validity_schedule 到 import**

```python
# 修改前（第 45 行）：
from .scheduler import _backup_database, register_job_func, start_scheduler, stop_scheduler

# 修改后：
from .scheduler import _backup_database, _check_validity_schedule, register_job_func, start_scheduler, stop_scheduler
```

- [ ] **Step 2: 注册 validity_wake**

在 `start_scheduler()` 调用之前添加：

```python
# 修改前（第 79-85 行）：
    _cron_mgr = _get_mgr()
    register_job_func("auto_scan", lambda: _cron_mgr.scan_and_index())
    from .api.announce import check_announce

    register_job_func("auto_announce", check_announce)
    register_job_func("auto_backup", lambda: _backup_database(notification_mgr=_cron_mgr.notification_mgr))
    start_scheduler()

# 修改后：
    _cron_mgr = _get_mgr()
    register_job_func("auto_scan", lambda: _cron_mgr.scan_and_index())
    from .api.announce import check_announce

    register_job_func("auto_announce", check_announce)
    register_job_func("auto_backup", lambda: _backup_database(notification_mgr=_cron_mgr.notification_mgr))
    register_job_func("validity_wake", lambda: _check_validity_schedule(notification_mgr=_cron_mgr.notification_mgr))
    start_scheduler()
```

- [ ] **Step 3: Commit**

```bash
git add docker/app.py
git commit -m "feat: 注册 validity_wake 调度任务"
```

---

## 第五部分：验证

### Task 5.1: 残留引用检查

- [ ] **Step 1: grep 确认 auto_query 无残留**

```bash
grep -rn "recheck_updates\|auto_query" --include="*.py" pilotstd/ docker/ tests/
```
预期结果：**零命中**。

- [ ] **Step 2: grep 确认 get_recheck_candidates 无残留**

```bash
grep -rn "get_recheck_candidates" --include="*.py" pilotstd/ docker/ tests/
```
预期结果：**零命中**。

- [ ] **Step 3: grep 确认旧配置键未在代码中被消费**

```bash
grep -rn "validity\.frequency\|validity\.execute_time\|validity\.update_interval" --include="*.py" pilotstd/ docker/
```
预期结果：仅命中 `config.py` 中标记 `@deprecated` 的默认值行和 `validity.py` 中 GET 接口返回的废弃字段（兼容旧前端）。

---

### Task 5.2: 运行门禁

- [ ] **Step 1: 运行 run-gates**

```bash
python scripts/run-gates
```
预期：全 PASS（特别注意 GATE-07a Python 死代码检测）。

- [ ] **Step 2: 运行 ruff + mypy**

```bash
ruff check pilotstd docker --fix
ruff format pilotstd docker
mypy pilotstd docker --follow-imports=skip
```
预期：零错误。

---

### Task 5.3: 运行相关测试

- [ ] **Step 1: 运行 scheduler 测试**

```bash
python -m pytest tests/test_docker_scheduler.py -v
```
预期：全 PASS。

- [ ] **Step 2: 前端类型检查**

```bash
cd web && npm run type-check
```
预期：通过（本次仅改后端，无前端变更）。

---

## 文件变更总览

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `docker/scheduler.py` | 修改 | 移除 auto_query cron；新增 `_add_interval_job()`、`_check_validity_schedule()` |
| 2 | `docker/app.py` | 修改 | 移除 auto_query 注册行；新增 validity_wake 注册行；导入 `_check_validity_schedule` |
| 3 | `pilotstd/manager/scheduled_service.py` | 修改 | 删除 `recheck_updates()` |
| 4 | `pilotstd/manager/facade.py` | 修改 | 删除 `recheck_updates()` 透传 |
| 5 | `pilotstd/core/file_index.py` | 修改 | 删除 `get_recheck_candidates()` |
| 6 | `docker/api/settings.py` | 修改 | GET/PUT 移除 auto_query 相关字段 |
| 7 | `tests/test_docker_scheduler.py` | 修改 | 移除 auto_query mock 和断言 |
| 8 | `pilotstd/core/config.py` | 修改 | 新增 5 项配置，废弃 3 项 |
| 9 | `docker/api/validity.py` | 修改 | GET/PUT 配置接口更新；POST run 改为调用底层 |
| 10 | `pilotstd/core/validity_checker.py` | 修改 | 修复 update_status 硬编码；新增 `run_validity_check()` |

---

## 前端修改汇总（本次不实施，供前端团队后续参考）

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `web/src/api/validity.ts` | `ValidityConfig` 接口：新增 `first_execution`、`total_weeks`、`next_run`、`checked_count`、`round_completed`；旧字段标记 `@deprecated` | 高 |
| `web/src/components/ValidityConfig.vue` | 表单新增"首次执行时间"日期时间选择器 + "总检查周期"输入框 + "下次执行时间(只读)" + "轮次进度(只读)"；旧字段 UI 加"（即将废弃）"标签 | 高 |
| `web/src/views/SettingsView.vue` | 如有引用旧配置字段，同步更新 | 中 |

### API 契约变化

**GET /validity/config 返回：**
- 新字段：`first_execution`、`total_weeks`、`next_run`、`checked_count`、`round_completed`
- 保留字段：`batch_size`、`batch_interval`、`check_ratio`
- 废弃字段（兼容过渡）：`frequency`、`execute_time`、`update_interval`

**PUT /validity/config 接受：**
- 可写：`first_execution`、`total_weeks`、`batch_size`、`batch_interval`、`check_ratio`
- 忽略（兼容）：`frequency`、`execute_time`、`update_interval`

### 迁移建议
1. 旧配置在 UI 上只读展示，新配置可编辑
2. 过渡期（2 周）后前端可移除旧字段 UI
3. `next_run`、`checked_count`、`round_completed` 为只读显示字段，不可编辑
