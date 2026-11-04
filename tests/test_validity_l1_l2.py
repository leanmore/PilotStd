"""有效性 L1：只信“否定”，不得短路 L2 适配器（D3-2）。

背景（2026-11-04 实测）：`announcement_record` 只要有该标准号，旧实现就按名称
关键词直接判“现行”并 return，适配器（L2）调用次数恒为 0。
"""

import json

from pilotstd.core.db import Database
from pilotstd.core.validity_checker import ValidityChecker


class _Result:
    def __init__(self, status):
        self.status = status

    def is_found(self):
        return True


class _Engine:
    def __init__(self, status="废止"):
        self.status = status
        self.calls = 0

    def query_standards(self, items):
        self.calls += 1
        return [_Result(self.status)]


def _db(tmp_path):
    return Database(str(tmp_path / "v.db"))


def _add_announcement(db, number, name):
    db.execute(
        "INSERT INTO announcement_record (source_site, pid, announce_no, standard_number,"
        " std_name, fetched_at) VALUES ('announcement_gb','p1','2026年第1号',?,?,'2026-01-01')",
        (number, name),
    )


def test_record_alone_does_not_block_adapter(tmp_path):
    db = _db(tmp_path)
    _add_announcement(db, "GB/T 9999-2020", "某推荐性国家标准")
    engine = _Engine("废止")
    res = ValidityChecker(db).check_standard("GB/T 9999-2020", query_engine=engine)

    assert engine.calls == 1, "L1 命中公告记录时不得短路 L2"
    assert res["evidence"] == "L2"
    assert res["status"] == "废止"


def test_structured_superseded_is_authoritative(tmp_path):
    db = _db(tmp_path)
    _add_announcement(db, "GB/T 9999-2020", "某推荐性国家标准")
    db.execute(
        "INSERT INTO announcement_match (standard_number, source_site, result_json, cached_at)"
        " VALUES ('GB/T 9999-2020','announcement_gb',?, '2026-01-01')",
        (json.dumps({"status": "被代替"}, ensure_ascii=False),),
    )
    engine = _Engine("现行")
    res = ValidityChecker(db).check_standard("GB/T 9999-2020", query_engine=engine)

    assert res["status"] == "被代替"
    assert res["evidence"] == "L1"
    assert engine.calls == 0, "结构化“被代替”应直接采信，不必再查适配器"


def test_name_keyword_is_negative_evidence(tmp_path):
    db = _db(tmp_path)
    _add_announcement(db, "GB/T 9999-2020", "某标准（废止）")
    engine = _Engine("现行")
    res = ValidityChecker(db).check_standard("GB/T 9999-2020", query_engine=engine)

    assert res["status"] == "已废止"
    assert res["evidence"] == "L1"
    assert engine.calls == 0


def test_amendment_name_does_not_pollute_base(tmp_path):
    """修改单名称不得让本体被判“废止”。"""
    db = _db(tmp_path)
    _add_announcement(db, "GB/T 9999-2020", "除湿机 第1号修改单（废止）")
    engine = _Engine("现行")
    res = ValidityChecker(db).check_standard("GB/T 9999-2020", query_engine=engine)

    assert res["status"] == "现行"
    assert res["evidence"] == "L2"
    assert engine.calls == 1


def test_no_query_engine_falls_back_to_l3(tmp_path):
    db = _db(tmp_path)
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at,"
        " next_check_at, created_at, updated_at) VALUES ('GB 1-2020','废止','2026-01-01',"
        " '2026-01-01','2026-01-01','2026-01-01')"
    )
    res = ValidityChecker(db).check_standard("GB 1-2020")
    assert res["evidence"] == "L3"
    assert res["status"] == "废止"
