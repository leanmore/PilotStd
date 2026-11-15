"""P2-11 根因回归：空代号不得写出畸形 validity 键（2026-11-15）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pilotstd.core.db import Database
from pilotstd.core.std_utils import build_standard_number
from pilotstd.core.validity_checker import ValidityChecker
from pilotstd.manager.facade._organize import OrganizeHandler
from pilotstd.models import ParsedStdInfo


@pytest.mark.parametrize(
    ("code", "number", "part", "year", "expected"),
    [
        ("TSG", 11, None, 2020, "TSG 11-2020"),
        ("GB/T", 1, 1, 2020, "GB/T 1.1-2020"),
        ("TSG", 7, None, None, "TSG 7"),
        ("", 11, None, 2020, ""),
        ("  ", 11, None, 2020, ""),
        ("TSG", 0, None, 2020, ""),
    ],
)
def test_build_standard_number(code, number, part, year, expected):
    assert build_standard_number(code, number, part, year) == expected


@pytest.fixture
def checker(tmp_path):
    db = Database(str(tmp_path / "v.db"))
    yield ValidityChecker(db)
    db.close()


def _count(db, key):
    return db.fetchone("SELECT COUNT(*) AS c FROM standard_validity WHERE standard_number=?", (key,))["c"]


def test_register_rejects_malformed_key(checker, tmp_path):
    db = checker._db
    checker.register_new_standard(" 11-2020")
    assert _count(db, " 11-2020") == 0


def test_register_accepts_canonical_key(checker):
    checker.register_new_standard("TSG 11-2020")
    assert _count(checker._db, "TSG 11-2020") == 1


class _Organizer:
    def organize(self, items, word_source_root, overwrite=False):
        return {"moved": len(items)}


def test_archive_registration_recovers_code_from_filename(tmp_path):
    """代号为空但有文件名时，从文件名补解析出 TSG，而不是写 ' 11-2020'。"""
    db = Database(str(tmp_path / "a.db"))
    checker = ValidityChecker(db)
    core = SimpleNamespace(
        organizer_svc=_Organizer(),
        validity_checker=checker,
        notification_mgr=None,
        parsed_results=[],
        db=db,
    )
    handler = OrganizeHandler(core)
    item = ParsedStdInfo(
        raw_filename="TSG 11-2020 锅炉安全技术规程.pdf",
        source_path="/inbox/TSG 11-2020 锅炉安全技术规程.pdf",
        logical_code="",
        number=11,
        year=2020,
        std_name="锅炉安全技术规程",
        final_name="TSG 11-2020 锅炉安全技术规程.pdf",
    )
    handler.archive_standards([item])
    assert _count(db, " 11-2020") == 0
    assert _count(db, "TSG 11-2020") == 1
    db.close()


def test_archive_registration_skips_when_code_unknown(tmp_path):
    db = Database(str(tmp_path / "b.db"))
    checker = ValidityChecker(db)
    core = SimpleNamespace(
        organizer_svc=_Organizer(),
        validity_checker=checker,
        notification_mgr=None,
        parsed_results=[],
        db=db,
    )
    handler = OrganizeHandler(core)
    item = ParsedStdInfo(
        raw_filename="unknown-file.pdf",
        source_path="/inbox/unknown-file.pdf",
        logical_code="",
        number=0,
        year=0,
        std_name="",
        final_name="unknown-file.pdf",
    )
    handler.archive_standards([item])
    rows = db.fetchall("SELECT standard_number FROM standard_validity")
    assert rows == []
    db.close()


def test_parse_combined_range_uses_real_year():
    """合订本残片 "47008-1947 010-2010"：取起始编号 + 真实年份 2010，不是 1947。"""
    from pilotstd.core.std_utils import parse_std_number

    parsed = parse_std_number("NB/T 47008-1947 010-2010 合订本.pdf")
    assert parsed["code"] == "NBT"
    assert parsed["number"] == 47008
    assert parsed["year"] == 2010


def test_parse_tsg_letter_prefix():
    """TSG Z8002-2022：代号 TSG、编号 8002、前缀 Z（不是 code=TSGZ800）。"""
    from pilotstd.core.std_utils import parse_std_number

    parsed = parse_std_number("TSG Z8002-2022 特种设备检验人员考核规则 第2号修改单.docx")
    assert parsed["code"] == "TSG"
    assert parsed["number"] == 8002
    assert parsed["year"] == 2022
    assert parsed["num_prefix"] == "Z"

def test_archive_resolves_pending_by_canonical_key(tmp_path):
    """归档成功（源文件已不在）→ 同规范键的 pending 行置 resolved。"""
    from pilotstd.manager.pending_service import PendingService

    db = Database(str(tmp_path / "p.db"))
    db.execute(
        "INSERT INTO pending_lookup (standard_number, status) VALUES (?, ?)",
        ("GB/T 1-2020", "pending"),
    )
    core = SimpleNamespace(
        organizer_svc=_Organizer(),
        validity_checker=None,
        notification_mgr=None,
        parsed_results=[],
        db=db,
        pending_svc=PendingService(db, None),
    )
    handler = OrganizeHandler(core)
    item = ParsedStdInfo(
        raw_filename="GB/T 1-2020 测试.pdf",
        source_path=str(tmp_path / "not-exists.pdf"),
        logical_code="GB/T",
        number=1,
        year=2020,
        std_name="测试",
        final_name="GB/T 1-2020 测试.pdf",
    )
    handler.archive_standards([item])
    row = db.fetchone("SELECT status FROM pending_lookup WHERE standard_number='GB/T 1-2020'")
    assert row["status"] == "resolved"
    db.close()


def test_archive_keeps_pending_when_source_still_exists(tmp_path):
    """源文件仍在（未真正归档）→ 不核销 pending。"""
    from pilotstd.manager.pending_service import PendingService

    db = Database(str(tmp_path / "p2.db"))
    db.execute(
        "INSERT INTO pending_lookup (standard_number, status) VALUES (?, ?)",
        ("GB/T 2-2020", "pending"),
    )
    still_there = tmp_path / "still.pdf"
    still_there.write_text("x", encoding="utf-8")
    core = SimpleNamespace(
        organizer_svc=_Organizer(),
        validity_checker=None,
        notification_mgr=None,
        parsed_results=[],
        db=db,
        pending_svc=PendingService(db, None),
    )
    handler = OrganizeHandler(core)
    item = ParsedStdInfo(
        raw_filename="GB/T 2-2020 测试.pdf",
        source_path=str(still_there),
        logical_code="GB/T",
        number=2,
        year=2020,
        std_name="测试",
        final_name="GB/T 2-2020 测试.pdf",
    )
    handler.archive_standards([item])
    row = db.fetchone("SELECT status FROM pending_lookup WHERE standard_number='GB/T 2-2020'")
    assert row["status"] == "pending"
    db.close()


def test_build_standard_number_with_letter_prefix():
    """TSG Z8002-2022：带前缀时保留 Z，不丢成 TSG 8002-2022。"""
    from pilotstd.core.std_utils import build_standard_number

    assert build_standard_number("TSG", 8002, None, 2022, "Z") == "TSG Z8002-2022"
    assert build_standard_number("TSG", 8002, None, 2022, "") == "TSG 8002-2022"


def test_archive_resolves_z_prefixed_pending(tmp_path):
    """归档 Z 前缀标准时，同键与带前缀变体都要核销。"""
    from pilotstd.manager.pending_service import PendingService

    db = Database(str(tmp_path / "z.db"))
    db.execute(
        "INSERT INTO pending_lookup (standard_number, status) VALUES (?, ?)",
        ("TSG Z8002-2022", "pending"),
    )
    core = SimpleNamespace(
        organizer_svc=_Organizer(),
        validity_checker=None,
        notification_mgr=None,
        parsed_results=[],
        db=db,
        pending_svc=PendingService(db, None),
    )
    handler = OrganizeHandler(core)
    item = ParsedStdInfo(
        raw_filename="TSG Z8002-2022 特种设备检验人员考核规则.docx",
        source_path=str(tmp_path / "not-exists-z.docx"),
        logical_code="TSG",
        number=8002,
        year=2022,
        std_name="特种设备检验人员考核规则",
        final_name="TSG Z8002-2022 特种设备检验人员考核规则.docx",
        num_prefix="Z",
    )
    handler.archive_standards([item])
    row = db.fetchone("SELECT status FROM pending_lookup WHERE standard_number='TSG Z8002-2022'")
    assert row["status"] == "resolved"
    db.close()
