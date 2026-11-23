"""tests/test_db_conn_reclaim.py — DB 线程连接回收（NEW-41，2026-11-23）。

背景：`Database._all_conns` 累积所有线程的连接；`threading.local` 的连接在线程结束后
**不会自动关闭**，线程 churn 场景（`_batch_dispatcher` / worker 线程）会持续累积。

修法：给「当前线程的 `threading.local` 对象」挂 `weakref.finalize` ——
线程退出后 `_local` 条目被回收，回调关闭该线程的连接并从 `_all_conns` 移除。

⚠️ 关键实测约束：**`sqlite3.Connection` 不支持弱引用**，
故锚点必须是 `threading.local`（支持弱引用），不能是 conn 本身。
本测试锁住这个约束，防止有人"优化"成 `weakref.finalize(conn, ...)` 后静默退化。
"""

import sqlite3
import sys
import threading
import weakref
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.core.db.database import Database  # noqa: E402


def test_sqlite_connection_is_not_weakrefable():
    """固化实测约束：sqlite3.Connection 不可弱引用（决定 finalize 锚点必须是 local）。"""
    conn = sqlite3.connect(":memory:")
    try:
        with pytest.raises(TypeError):
            weakref.ref(conn)
    finally:
        conn.close()


def test_thread_local_is_weakrefable():
    """threading.local 可弱引用（NEW-41 的 finalize 锚点）。"""
    loc = threading.local()
    r = weakref.ref(loc)  # 不抛异常即通过
    assert r() is loc


def test_conns_tracked_and_close_all_clears(tmp_path):
    """正常路径：连接被登记，close_all 后清空。"""
    db = Database(str(tmp_path / "t.db"))
    conn = db._get_conn()
    assert conn is not None
    assert len(db._all_conns) >= 1
    db.close_all()
    assert db._all_conns == []


def test_conns_lock_is_lazy_for_bypassed_init(tmp_path):
    """用 __new__ 绕过 __init__ 构造的实例也能拿到锁（兼容既有测试替身）。"""
    db = Database.__new__(Database)
    db._db_path = str(tmp_path / "t2.db")
    db._local = threading.local()
    db._all_conns = []
    lock = db._get_conns_lock()
    assert lock is not None
    # 幂等：再次获取返回同一把锁
    assert db._get_conns_lock() is lock


def test_per_thread_connections_are_distinct(tmp_path):
    """不同线程各自持有独立连接（threading.local 语义），且都被登记。"""
    db = Database(str(tmp_path / "t3.db"))
    seen: list[int] = []

    def worker() -> None:
        conn = db._get_conn()
        seen.append(id(conn))
        db.close_all()  # 该线程自己清理

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 3
    # 三个线程应拿到三个不同连接（threading.local）
    assert len(set(seen)) == 3


def test_finalizer_registered_on_thread_local(tmp_path):
    """源码必须把 finalize 锚在 _local 上（不是 conn）—— 防静默退化。"""
    src = (ROOT / "pilotstd" / "core" / "db" / "database.py").read_text(encoding="utf-8")
    assert "weakref.finalize(self._local" in src, "finalize 必须锚在 threading.local 上"
    assert "weakref.finalize(conn" not in src, "conn 不可弱引用，锚在 conn 上会 TypeError"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
