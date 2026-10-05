"""B3-d 接线专项测试：本地索引「展示名」对齐回退链的**集成点**。

为什么需要这些用例：`resolve_name` 本身已由 `tests/test_name_resolution.py`（21 例）锁定语义，
但**接线**（缓存命中后把回退链结果写进 `std_name`、未命中时保持索引表内原值、`found_name` 仍为②语义）
一旦被未来重构改坏，纯函数用例是发现不了的 ⇒ 此处锁住接线。

覆盖：
1) 缓存命中（`match_status == "exact"`）⇒ `std_name` = 回退链结果（③ 若有则优先），`found_name` 仍为②查询名；
2) 缓存未命中/JSON 损坏 ⇒ `std_name` **保持索引表内原值**（不被清空）；
3) 批量路径 `get_full_info()` ⇒ 命中缓存的行取回退链结果，无缓存的行保持表内原值。
"""

import json
from types import SimpleNamespace

from pilotstd.core._file_index_query import FileIndexQuery


class _Db:
    """最小 DB 替身：`get_full_info` 只用到 `fetchall`。"""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self, sql, params=()):  # noqa: ARG002 - 契约签名
        return self._rows


def _row(**over):
    """构造一条 `fi.* + 缓存列` 形状的行（与 get_full_info 的 SELECT 对齐）。"""
    row = {
        "file_path": "D:/lib/GB_T 1-2020.pdf",
        "logical_code": "GB/T",
        "number": 1,
        "year": 2020,
        "part": -1,
        "std_name": "解析名（索引表内）",
        "nc_result_json": None,
        "nc_cached_at": None,
        "ac_result_json": None,
        "ac_cached_at": None,
    }
    row.update(over)
    return row


class TestApplyCacheResult:
    def test_hit_sets_display_name_to_cache_name(self):
        """缓存命中且无③ ⇒ 展示名＝②查询名；`found_name` 仍是②语义（D5）。"""
        info = SimpleNamespace(std_name="解析名", found_name="", final_name="")
        FileIndexQuery._apply_cache_result(
            json.dumps({"match_status": "exact", "status": "现行", "standard_name": "查询名"}), info
        )
        assert info.found_name == "查询名", "②语义字段必须保持'查询名'"
        assert info.std_name == "查询名", "展示名应取回退链结果"

    def test_hit_prefers_final_name_over_cache_name(self):
        """③决策名已在对象上 ⇒ 展示名取③（最高可得阶段名），而非②。"""
        info = SimpleNamespace(std_name="解析名", found_name="", final_name="决策名")
        FileIndexQuery._apply_cache_result(
            json.dumps({"match_status": "exact", "status": "现行", "standard_name": "查询名"}), info
        )
        assert info.std_name == "决策名"
        assert info.found_name == "查询名"

    def test_non_exact_or_broken_keeps_index_name(self):
        """非 exact 命中 / JSON 损坏 ⇒ 不得改动展示名（保持索引表内原值）。"""
        for payload in ('{"match_status": "fuzzy", "standard_name": "别的名"}', "{坏 JSON"):
            info = SimpleNamespace(std_name="解析名（索引表内）", found_name="", final_name="")
            FileIndexQuery._apply_cache_result(payload, info)
            assert info.std_name == "解析名（索引表内）"
            assert info.found_name == ""


class TestGetFullInfoBatchPath:
    def test_cache_hit_row_takes_chain_result(self):
        rows = [_row(nc_result_json=json.dumps({"standard_name": "查询名", "status": "现行"}))]
        items = FileIndexQuery(_Db(rows)).get_full_info("GB/T", 1)
        assert items[0]["found_name"] == "查询名"
        assert items[0]["std_name"] == "查询名", "命中缓存 ⇒ 展示名取回退链结果"

    def test_row_without_cache_keeps_index_name(self):
        """无任何缓存 ⇒ 展示名保持索引表内原值（不得清空）。"""
        items = FileIndexQuery(_Db([_row()])).get_full_info("GB/T", 1)
        assert items[0]["found_name"] == ""
        assert items[0]["std_name"] == "解析名（索引表内）"

    def test_final_name_on_row_wins(self):
        """行内若存在 `final_name`（未来加列）⇒ 展示名自动取③，无需改代码。"""
        rows = [_row(final_name="决策名", nc_result_json=json.dumps({"standard_name": "查询名"}))]
        items = FileIndexQuery(_Db(rows)).get_full_info("GB/T", 1)
        assert items[0]["std_name"] == "决策名"
