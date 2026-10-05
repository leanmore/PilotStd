"""名称决策（阶段③）结果落库的单测（批次二）。

为什么单独测这一层：`_persist_final_names` 是「决策 → 落库」闭环的唯一写入点，
其三条硬约束必须被测试锁定：
  1) **批量**：一次 `executemany`，严禁循环逐条 UPDATE（性能）；
  2) **best-effort**：DB 异常只记 debug，**不得外抛**（否则会打断查询/归档主流程）；
  3) **精确作用域**：只写"决策确实产出 final_name"的条目，且缺 `get_full_number` 的条目跳过。
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.manager.classifier import QueryClassifier


def _make_classifier() -> QueryClassifier:
    """用最小替身构造分类器（本用例只测落库，不触路由器/适配器）。"""
    return QueryClassifier(
        router=MagicMock(),
        query_adapters=[],
        quota_tracker=None,
        query_engine=MagicMock(),
    )


def _item(number: str, final_name: str, *, with_number: bool = True) -> SimpleNamespace:
    """构造一条"已决策"的解析条目。"""
    obj = SimpleNamespace(final_name=final_name)
    if with_number:
        obj.get_full_number = lambda n=number: n
    return obj


class TestPersistFinalNames:
    def test_batch_writes_once_with_decided_rows(self):
        """两条已决策条目 ⇒ 一次 executemany，参数为 [(名称, 标准号)]，且连接被关闭。"""
        clf = _make_classifier()
        db = MagicMock()
        with patch("pilotstd.core.config.get_db_path", return_value=":memory:"), patch(
            "pilotstd.core.db.database.Database", return_value=db
        ):
            clf._persist_final_names([_item("GB/T 1-2020", "决策名甲"), _item("GB/T 2-2020", "决策名乙")])

        assert db.executemany.call_count == 1, "必须是单次批量提交，不得逐条 UPDATE"
        sql, rows = db.executemany.call_args.args
        assert "UPDATE announcement_record SET final_name = ?" in sql
        assert rows == [("决策名甲", "GB/T 1-2020"), ("决策名乙", "GB/T 2-2020")]
        assert db.close.called, "独立短连接必须关闭"

    def test_skips_items_without_final_name(self):
        """未产出 final_name（如未参与决策/无 ①②）的条目不写库；全空则完全不碰 DB。"""
        clf = _make_classifier()
        with patch("pilotstd.core.db.database.Database") as db_cls:
            clf._persist_final_names([_item("GB/T 1-2020", ""), SimpleNamespace()])
        assert not db_cls.called, "无决策结果时不得建立连接"

    def test_skips_items_without_get_full_number(self):
        """缺 `get_full_number` 的条目（异常构造/替身）跳过，不抛错。"""
        clf = _make_classifier()
        db = MagicMock()
        with patch("pilotstd.core.config.get_db_path", return_value=":memory:"), patch(
            "pilotstd.core.db.database.Database", return_value=db
        ):
            clf._persist_final_names([_item("GB/T 1-2020", "决策名", with_number=False)])
        assert not db.executemany.called

    def test_db_failure_is_swallowed(self):
        """落库异常不得外抛（best-effort：不影响分类结果与后续归档）。"""
        clf = _make_classifier()
        with patch("pilotstd.core.config.get_db_path", return_value=":memory:"), patch(
            "pilotstd.core.db.database.Database", side_effect=RuntimeError("db down")
        ):
            clf._persist_final_names([_item("GB/T 1-2020", "决策名")])  # 不应抛异常

    def test_executemany_failure_still_closes_connection(self):
        """executemany 抛错时仍走 finally 关闭连接。"""
        clf = _make_classifier()
        db = MagicMock()
        db.executemany.side_effect = RuntimeError("disk full")
        with patch("pilotstd.core.config.get_db_path", return_value=":memory:"), patch(
            "pilotstd.core.db.database.Database", return_value=db
        ):
            clf._persist_final_names([_item("GB/T 1-2020", "决策名")])
        assert db.close.called


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
