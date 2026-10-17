"""收藏下载的 file_index 查询：区分"没查到"与"查不了"（体检 D-11）。

原实现 `except Exception: pass` 把数据库错误吞成 None，调用方据此认为"库里没有"，
于是对已归档的标准**重复下载**。修复后：解析失败 → None；数据库错误 → 抛出，
由任务外层标记失败（宁可报错，也不重复下载）；归档轮询期的瞬时错误则记警告后重试。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilotstd.core.db._constants import DatabaseError
from pilotstd.tasks.favorite_download import _find_in_file_index, _reuse_existing_file


def test_db_error_propagates_instead_of_looking_like_missing() -> None:
    db = MagicMock()
    db.execute.side_effect = DatabaseError("database is locked")

    with pytest.raises(DatabaseError):
        _find_in_file_index("GB/T 1-2020", db)


def test_returns_path_when_index_has_row() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = {"file_path": "/library/GB-T 1-2020.pdf"}
    db = MagicMock()
    db.execute.return_value = cursor

    assert _find_in_file_index("GB/T 1-2020", db) == "/library/GB-T 1-2020.pdf"
    args = db.execute.call_args.args
    assert "file_index" in args[0]


def test_unparseable_number_returns_none_without_query() -> None:
    db = MagicMock()
    assert _find_in_file_index("not_a_standard", db) is None
    db.execute.assert_not_called()


def test_reuse_existing_file_propagates_db_error() -> None:
    """复用判断遇到数据库错误时不得静默返回 False（那会继续走下载）。"""
    db = MagicMock()
    db.execute.side_effect = DatabaseError("disk I/O error")

    with pytest.raises(DatabaseError):
        _reuse_existing_file(db, favorite_id=1, standard_number="GB/T 1-2020", user_id=1, notify=False)


def test_reuse_existing_file_returns_false_when_absent() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    db = MagicMock()
    db.execute.return_value = cursor

    assert _reuse_existing_file(db, 1, "GB/T 1-2020", 1, notify=False) is False
