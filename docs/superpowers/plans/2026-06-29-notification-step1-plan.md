# 通知系统第一步补全 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 补全 P1 已读标记（DB+API）、P2 WebSocket 后端推送、P3 测试覆盖。

**Architecture:** DB 迁移 v18 加 is_read 列 → API 新增 POST /read + GET /logs?is_read → WebSocket 端点 `/api/notification/ws` → send_event 独立线程广播 → 4 个测试文件。

**Tech Stack:** Python 3.12, FastAPI, WebSocket, SQLite, pytest, asyncio

**执行顺序：** P1 → P2 → P3

---

### Task 1.1: 数据库迁移 v18

**文件：** `pilotstd/core/db.py`

在当前最后一条迁移之后添加：

```python
@migration(18)
def _migrate_v18_notification_is_read(db: Database) -> None:
    """v18: 通知日志增加 is_read 字段，支持已读标记。"""
    db.execute("ALTER TABLE notification_log ADD COLUMN is_read INTEGER DEFAULT 0")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_is_read ON notification_log(is_read)")
```

- [ ] Commit: `git add pilotstd/core/db.py && git commit -m "feat: 迁移v18—notification_log新增is_read列"`

---

### Task 1.2: POST /api/notification/read 端点

**文件：** `docker/api/notification.py`

在文件顶部添加导入：
```python
from pydantic import BaseModel

class MarkReadRequest(BaseModel):
    id: int | None = None
```

在 `get_logs` 之后添加：
```python
@router.post("/api/notification/read")
def mark_notification_read(request: MarkReadRequest, nmgr=Depends(_get_notification_mgr)):
    try:
        db = nmgr._db
        if request.id is not None:
            existing = db.fetchone("SELECT id FROM notification_log WHERE id=?", (request.id,))
            if not existing:
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": f"通知 ID {request.id} 不存在"}, status_code=404)
            db.execute("UPDATE notification_log SET is_read=1 WHERE id=?", (request.id,))
        else:
            db.execute("UPDATE notification_log SET is_read=1")
        db.commit()
        return {"ok": True, "message": "已标记为已读"}
    except Exception as e:
        logger.exception("标记已读失败")
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": str(e)}, status_code=500)
```

- [ ] Commit: `git add docker/api/notification.py && git commit -m "feat: POST /api/notification/read 标记已读端点"`

---

### Task 1.3: GET /logs 增强 is_read

**文件：** `docker/api/notification.py`

在 `get_logs` 函数签名中添加 `is_read` 参数。修改后：

```python
@router.get("/api/notification/logs")
def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    is_read: bool | None = Query(None),  # 新增
    nmgr=Depends(_get_notification_mgr),
):
    # ... 在 where_clauses 构建中增加:
    if is_read is not None:
        where_clauses.append("is_read = ?")
        params.append(1 if is_read else 0)
    # 返回中 items 改为含 is_read 的 dict
```

- [ ] Commit: `git add docker/api/notification.py && git commit -m "feat: GET /logs 支持 is_read 筛选"`

---

### Task 2.1: 新建 websocket.py

**文件：** `docker/websocket.py`（新建）

完整代码见用户指令中 Task 2.1。

- [ ] Commit: `git add docker/websocket.py && git commit -m "feat: WebSocket 通知推送服务"`

---

### Task 2.2: 注册 WebSocket 路由

**文件：** `docker/app.py`

添加 import 和路由注册。按照 FastAPI `add_websocket_route` 方式。

- [ ] Commit: `git add docker/app.py && git commit -m "feat: 注册 /api/notification/ws WebSocket 路由"`

---

### Task 2.3: send_event WebSocket 广播

**文件：** `pilotstd/core/notification/manager.py`

在 `send_event()` 末尾添加独立线程广播（修正版，使用 `asyncio.new_event_loop()`）。

- [ ] Commit: `git add pilotstd/core/notification/manager.py && git commit -m "feat: send_event 增加 WebSocket 广播（独立线程）"`

---

### Task 3.1-3.4: 测试覆盖

**新建 4 个测试文件**，覆盖 manager、API、WebSocket、DB。

- [ ] Commit: `git add tests/ && git commit -m "test: 通知系统测试覆盖（manager+API+WebSocket+DB）"`

---

### 验证

```bash
pytest tests/test_notification_*.py -v   # 全部 PASS
ruff check pilotstd docker --fix && ruff format pilotstd docker && mypy pilotstd docker --follow-imports=skip  # 零错误
```
