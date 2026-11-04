"""第三批边缘修复（D1-1/D1-3/D3-5/D3-6/D4-4/D6-3）与归档 unparsed 计数。"""

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pilotstd.announcement._circuit_breaker import CircuitBreaker
from pilotstd.core._validity_pipeline import _finalize_validity_round, _process_validity_batch
from pilotstd.core.db import Database
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.scan.parser import StandardParser

# ── D1-1 / D1-3：解析边界 ──────────────────────────────────────────


@pytest.fixture(scope="module")
def parser():
    return StandardParser(build_code_mapping())


@pytest.mark.parametrize(
    ("name", "year", "code"),
    [
        ("GB1234-20.pdf", 2020, "GB"),
        ("GB1234-86.pdf", 1986, "GB"),
        ("GB/T 1234-20.pdf", 2020, "GB/T"),
    ],
)
def test_short_year_expanded(parser, name, year, code):
    info = parser.parse(name)
    assert info is not None
    assert info.year == year
    assert info.logical_code == code


def test_language_preserved_for_domestic(parser):
    zh = parser.parse("GB/T 1234-2020 中文版.pdf")
    en = parser.parse("GB/T 1234-2020(英文版).pdf")
    assert zh is not None and zh.language == "中文版"
    assert en is not None and en.language == "英文版"


def test_amendment_kind(parser):
    info = parser.parse("GB/T 19411-2024 第1号修改单.pdf")
    assert info is not None
    assert "第1号修改单" in info.file_kind


# ── D3-5：checked_count 排除失败样本 + 合法号分母 ─────────────────


class _Cfg:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.saved = False

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.saved = True


def test_checked_count_excludes_failures():
    cfg = _Cfg({"validity.checked_count": 10})
    db = MagicMock()
    db.fetchone.return_value = {"cnt": 6}

    _finalize_validity_round(
        cfg, db, ["GB 1-2020", "GB 2-2020", "GB 3-2020"],
        [], [{"standard": "GB 2-2020", "error": "timeout"}], None, None, True,
    )

    assert cfg.values["validity.checked_count"] == 12, "只应累加成功 2 条（10+2）"
    assert cfg.values.get("validity.round_completed") is True
    assert cfg.saved is True


def test_round_total_ignores_malformed_numbers():
    cfg = _Cfg({"validity.checked_count": 0})
    db = MagicMock()
    db.fetchone.return_value = {"cnt": 2}
    _finalize_validity_round(cfg, db, ["GB 1-2020", "GB 2-2020"], [], [], None, None, True)
    sql = db.fetchone.call_args[0][0]
    assert "GLOB '[A-Z]*'" in sql


# ── D3-6：L2 受控并发 ────────────────────────────────────────────


def test_l2_runs_concurrently_with_bound():
    state = {"active": 0, "max": 0}
    lock = threading.Lock()

    class _Checker:
        def check_standard(self, std_no, query_engine=None):
            with lock:
                state["active"] += 1
                state["max"] = max(state["max"], state["active"])
            time.sleep(0.05)
            with lock:
                state["active"] -= 1
            return {"status": "现行"}

        def update_status(self, *a, **k):
            return None

        def should_apply_side_effects(self, evidence):
            return False

    db = MagicMock()
    db.fetchone.return_value = {"status": "现行"}
    candidates = [f"GB {i}-2020" for i in range(6)]

    _process_validity_batch(candidates, _Checker(), db, None, 50, 0, query_engine=object(), l2_workers=3)

    assert state["max"] >= 2, f"应发生并发，实际峰值 {state['max']}"
    assert state["max"] <= 3, "并发不得超过配置上限"


def test_l2_failure_isolated():
    class _Checker:
        def check_standard(self, std_no, query_engine=None):
            if std_no == "GB 2-2020":
                raise RuntimeError("adapter timeout")
            return {"status": "现行"}

        def update_status(self, *a, **k):
            return None

        def should_apply_side_effects(self, evidence):
            return False

    db = MagicMock()
    db.fetchone.return_value = {"status": "现行"}
    changed, changed_list, failed, detail = _process_validity_batch(
        ["GB 1-2020", "GB 2-2020", "GB 3-2020"], _Checker(), db, None, 50, 0, l2_workers=2
    )
    assert [f["standard"] for f in failed] == ["GB 2-2020"]
    assert changed == 0


# ── D4-4：熔断通知 ───────────────────────────────────────────────


def test_freeze_emits_system_notification(monkeypatch):
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "pilotstd.core.notification.notify_system", lambda event, data: sent.append((event, data))
    )
    cb = CircuitBreaker(lambda: "gb")
    monkeypatch.setattr(cb, "save_health", lambda: None)
    monkeypatch.setattr(cb, "load_health", lambda: None)
    monkeypatch.setattr(type(cb), "_threshold", property(lambda self: 1))
    monkeypatch.setattr(type(cb), "_durations", property(lambda self: [60]))

    assert cb.record_failure() is True
    assert sent, "触发熔断必须发系统通知"
    event, data = sent[0]
    assert event == "task_execution_failed"
    assert "熔断" in data["error"]


# ── D6-3：保留期清理 ─────────────────────────────────────────────


def test_retention_cleanup_deletes_old_rows(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "r.db"))
    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource, detail, timestamp)"
        " VALUES (1,'X','r','{}', datetime('now','localtime','-400 days'))"
    )
    db.execute(
        "INSERT INTO audit_logs (user_id, action, resource, detail, timestamp)"
        " VALUES (1,'Y','r','{}', datetime('now','localtime'))"
    )
    db.execute(
        "INSERT INTO pipeline_runs (run_id, current_step, status, progress, created_at, updated_at)"
        " VALUES ('old','scan','completed',100, datetime('now','localtime','-400 days'),"
        " datetime('now','localtime','-400 days'))"
    )
    db.execute(
        "INSERT INTO pipeline_runs (run_id, current_step, status, progress, created_at, updated_at)"
        " VALUES ('new','scan','completed',100, datetime('now','localtime'), datetime('now','localtime'))"
    )

    import docker.scheduler as sched

    monkeypatch.setattr(sched, "_get_db", lambda: db)
    sched._cleanup_retention()

    assert db.fetchone("SELECT COUNT(*) AS c FROM audit_logs")["c"] == 1
    assert db.fetchone("SELECT COUNT(*) AS c FROM pipeline_runs")["c"] == 1


# ── D1-1：归档 unparsed 计数 ────────────────────────────────────


def test_organize_counts_unparsed(tmp_path):
    from pilotstd.manager.facade._organize import OrganizeHandler

    class _Parser:
        def parse(self, name):
            return None if "bad" in name else SimpleNamespace(source_path="", effect_status="")

    mgr = OrganizeHandler.__new__(OrganizeHandler)
    mgr._core = SimpleNamespace(parser=_Parser())
    mgr.archive_standards = lambda parsed: {"moved": len(parsed), "failed": 0, "skipped_exists": 0}
    good = tmp_path / "GB 1-2020.pdf"
    bad = tmp_path / "bad-name.pdf"
    good.write_bytes(b"x")
    bad.write_bytes(b"x")

    result = mgr.organize_files([str(good), str(bad)])

    assert result["moved"] == 1
    assert result["unparsed"] == 1
