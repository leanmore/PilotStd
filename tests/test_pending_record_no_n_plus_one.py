"""tests/test_pending_record_no_n_plus_one.py — record_pending 的 N+1 消除（NEW-04，2026-11-23）。

背景：`record_pending` 原对每条 item 单独 `SELECT id ... WHERE standard_number=?`
再决定是否 INSERT。批量 500 条 = 500 次 SELECT + 最多 500 次 INSERT。

修法：先分批 `SELECT ... WHERE status='pending' AND standard_number IN (...)`
拿到已存在集合，再只对不在集合里的 INSERT。

本测试锁住：
  1. 批量 N 条时 SELECT 次数与批次相关（不是 N 次）—— 这是 N+1 的核心判据
  2. 已存在的标准号不被重复 INSERT
  3. 新标准号全部被 INSERT
  4. 空列表不产生任何查询
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.manager.pending_service import PendingService  # noqa: E402


class FakeParsed:
    """最小可用的 parsed item 替身（只提供 record_pending 用到的字段）。"""

    def __init__(self, num: str):
        self._num = num
        self.std_name = f"name-{num}"
        self.found_name = f"found-{num}"
        self.match_status = "matched"
        self.effect_status = "active"
        self.source_path = f"/tmp/{num}"
        self.found_number = num
        self.found_source_site = "site"
        self.source_name = "src"
        self.stage_status = "ok"

    def get_full_number(self) -> str:
        return self._num


def make_service(existing: set[str]) -> tuple[PendingService, MagicMock]:
    db = MagicMock()
    # fetchall 返回已存在的行（dict 形式，与 Database.fetchall 契约一致）
    db.fetchall.return_value = [{"standard_number": n} for n in existing]
    svc = PendingService(db=db, file_index=MagicMock())
    return svc, db


def test_select_count_is_not_proportional_to_items():
    """N 条 item 时 SELECT 次数应为「批次数」，不是 N（N+1 的核心判据）。"""
    items = [FakeParsed(f"GB/T {i}") for i in range(100)]
    svc, db = make_service(existing=set())
    svc.record_pending(items)

    # 100 条 < 500 一批 ⇒ 只应有 1 次 fetchall（旧实现是 100 次 fetchone）
    assert db.fetchall.call_count == 1, f"预期 1 次批量查询，实际 {db.fetchall.call_count}"
    assert db.fetchone.call_count == 0, "不应再有逐条 fetchone"
    # 100 条都要 INSERT
    assert db.execute.call_count == 100


def test_existing_numbers_are_skipped():
    """已处于 pending 的标准号不应重复 INSERT。"""
    items = [FakeParsed("A"), FakeParsed("B"), FakeParsed("C")]
    svc, db = make_service(existing={"B"})
    svc.record_pending(items)

    inserted = [c.args[1][0] for c in db.execute.call_args_list]
    assert sorted(inserted) == ["A", "C"]
    assert "B" not in inserted


def test_empty_list_makes_no_query():
    """空列表不应产生任何查询（避免无意义的 IN () 语法错误）。"""
    svc, db = make_service(existing=set())
    svc.record_pending([])
    assert db.fetchall.call_count == 0
    assert db.execute.call_count == 0


def test_large_batch_splits_into_multiple_queries():
    """超过 500 条时应分批查询（SQLite 变量上限 999）。"""
    items = [FakeParsed(f"N{i}") for i in range(1200)]
    svc, db = make_service(existing=set())
    svc.record_pending(items)
    # 1200 条 / 500 一批 = 3 批
    assert db.fetchall.call_count == 3
    assert db.execute.call_count == 1200


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
