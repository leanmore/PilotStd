"""ConfigManager.update()：单键写入不得整文件覆盖他方已写入的键（2026-11-20）。

背景：`save()` 写的是整个内存快照。`docker/scheduler._check_validity_schedule` 在任务开始处
构造实例、任务结束处 `save()`，用旧快照覆盖文件 ⇒ `wechat_ip.last_fail_key` 被冲掉，
同一 IP 的 Cookie 失败每个周期重复通知（生产实证：每 5~6 小时一条，且从无“已更新”通知）。

本文件锁定 `update()` 的两条契约：
1. 写前重读磁盘：他方在我构造之后写入的键必须保留；
2. 语义仍等价于 set+save：本实例写完后，新构造的实例能读回该值。
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from pilotstd.core.config.manager import ConfigManager


def _make(filepath: str) -> ConfigManager:
    """在隔离空库下构造（构造期会做防呆查库，避免读到真实开发库）。"""
    db = str(Path(tempfile.mkdtemp(prefix="pilotstd_cfg_db_")) / "empty.db")
    sqlite3.connect(db).close()
    with patch("pilotstd.core.config.paths.get_db_path", return_value=db):
        return ConfigManager(filepath=filepath)


def _new_file() -> str:
    p = Path(tempfile.mkdtemp(prefix="pilotstd_cfg_upd_")) / "config.json"
    p.write_text(json.dumps({}), encoding="utf-8")
    return str(p)


def test_update_keeps_other_instance_writes():
    """A 构造后、写盘前，B 写了别的键 —— A 的 update 不得把 B 的键冲掉。"""
    path = _new_file()
    a = _make(path)
    b = _make(path)

    b.set("wechat_ip.last_fail_key", "cookie|1.2.3.4")
    b.save()

    a.update("validity.next_run", "2026-11-21T00:00:00")

    fresh = _make(path)
    assert fresh.get("wechat_ip.last_fail_key") == "cookie|1.2.3.4"
    assert fresh.get("validity.next_run") == "2026-11-21T00:00:00"


def test_update_value_is_persisted():
    path = _new_file()
    cfg = _make(path)
    cfg.update("validity.first_execution", "2026-11-20T00:00:00")

    fresh = _make(path)
    assert fresh.get("validity.first_execution") == "2026-11-20T00:00:00"


def test_update_overwrites_same_key():
    """同一键再次 update 以最后一次为准。"""
    path = _new_file()
    cfg = _make(path)
    cfg.update("a.b", 1)
    cfg.update("a.b", 2)
    assert _make(path).get("a.b") == 2


def test_update_many_keeps_other_instance_writes():
    """批量记账（时效轮次收尾）同样不得覆盖他方在任务期间写入的键。"""
    path = _new_file()
    a = _make(path)
    b = _make(path)

    b.set("wechat_ip.last_fail_key", "cookie|5.6.7.8")
    b.save()

    a.update_many({"validity.round_completed": True, "validity.round_count": 3})

    fresh = _make(path)
    assert fresh.get("wechat_ip.last_fail_key") == "cookie|5.6.7.8"
    assert fresh.get("validity.round_completed") is True
    assert fresh.get("validity.round_count") == 3
