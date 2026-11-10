"""批次三：有效性检查接通（L2 适配器 / JOIN 年份 / 副作用闸门）。"""

from unittest.mock import MagicMock

import pytest

from pilotstd.core._validity_pipeline import _process_validity_batch, run_validity_check
from pilotstd.core.db import Database
from pilotstd.core.validity_checker import ValidityChecker
from pilotstd.manager.standard_service import StandardService


@pytest.fixture()
def db(tmp_path):
    return Database(str(tmp_path / "t.db"))


def test_pipeline_passes_query_engine_to_check_standard(db):
    """L2 可达性：批处理必须把 query_engine 传给 check_standard。"""
    checker = MagicMock()
    checker.check_standard.return_value = {"status": "现行", "evidence": "L2"}
    checker.should_apply_side_effects.return_value = False

    sentinel = object()
    _process_validity_batch(["GB 1-2020"], checker, db, None, 50, 0, query_engine=sentinel)

    checker.check_standard.assert_called_once_with("GB 1-2020", query_engine=sentinel)


def test_factory_default_auto_move_enabled():
    """P1-07：auto_move_expired 的出厂默认是 true，文档/代码注释按此对齐。"""
    from pilotstd.core.config.defaults import FACTORY_DEFAULTS

    assert FACTORY_DEFAULTS["validity.auto_move_expired"] is True


def test_run_validity_check_accepts_query_engine(tmp_path):
    """入口签名必须接受 query_engine（API/调度器据此接线）。"""
    result = run_validity_check(
        notification_mgr=None,
        db=Database(str(tmp_path / "t.db")),
        adapter_mgr=None,
        update_counters=False,
        query_engine=object(),
    )
    assert result["ok"] is True
    assert result["checked"] == 0


def test_check_standard_marks_evidence_l2(db):
    checker = ValidityChecker(db)
    qe = MagicMock()
    qe.query_standards.return_value = [MagicMock(status="废止", is_found=lambda: True)]

    result = checker.check_standard("GB 1-2020", query_engine=qe)

    assert result["evidence"] == "L2"
    assert result["status"] == "废止"


def test_check_standard_marks_evidence_l1(db):
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, standard_number, std_name, fetched_at)"
        " VALUES ('announcement_gb','p','GB 1-2020','已废止 某标准','2026-01-01')"
    )
    checker = ValidityChecker(db)
    result = checker.check_standard("GB 1-2020")
    assert result["evidence"] == "L1"


def test_l1_abolished_does_not_move_file(db, monkeypatch):
    """L1 单独命中废止时不得搬文件（默认不自动搬）。"""
    db.execute(
        "INSERT INTO standard_validity (standard_number, status) VALUES ('GB 1-2020','现行')"
    )
    checker = ValidityChecker(db)
    moved = []
    monkeypatch.setattr(checker, "_move_expired_file", lambda n, s: (moved.append(n), [])[1])

    checker.update_status("GB 1-2020", "已废止", evidence="L1")

    assert moved == []


def test_l2_abolished_moves_only_when_switch_on(db, monkeypatch):
    db.execute(
        "INSERT INTO standard_validity (standard_number, status) VALUES ('GB 1-2020','现行')"
    )
    checker = ValidityChecker(db)
    moved = []
    monkeypatch.setattr(checker, "_move_expired_file", lambda n, s: (moved.append(n), [])[1])

    monkeypatch.setattr("pilotstd.core.config.ConfigManager.get", lambda self, k, d=None: False)
    checker.update_status("GB 1-2020", "已废止", evidence="L2")
    assert moved == []

    monkeypatch.setattr("pilotstd.core.config.ConfigManager.get", lambda self, k, d=None: True)
    checker.update_status("GB 1-2020", "现行", evidence="L2")
    checker.update_status("GB 1-2020", "已废止", evidence="L2")
    assert moved == ["GB 1-2020"]


def test_join_with_year_returns_last_checked(db):
    """file_index(带 year) 必须能 JOIN 上 standard_validity.standard_number。"""
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status)"
        " VALUES ('/standards/x.pdf','GB/T',1,2020,-1,'标准一','现行')"
    )
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at, check_count)"
        " VALUES ('GB/T 1-2020','现行','2026-10-01T00:00:00+00:00',3)"
    )

    mgr = MagicMock()
    mgr.db = db
    result = StandardService(mgr).get_list(page=1, size=10)

    assert result["total"] == 1
    assert result["items"][0]["last_checked_at"] == "2026-10-01T00:00:00+00:00"
    assert result["items"][0]["check_count"] == 3


def test_join_without_year_still_matches(db):
    """year=0 的行退回「代号+顺序号」口径，不因拼接 '-0' 失配。"""
    db.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status)"
        " VALUES ('/standards/y.pdf','ANSI',78,0,-1,'标准二','现行')"
    )
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at, check_count)"
        " VALUES ('ANSI 78','现行','2026-10-02T00:00:00+00:00',1)"
    )

    mgr = MagicMock()
    mgr.db = db
    result = StandardService(mgr).get_list(page=1, size=10)
    assert result["items"][0]["last_checked_at"] == "2026-10-02T00:00:00+00:00"
