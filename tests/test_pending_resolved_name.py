"""B3-c：待确认接口（`GET /api/pending`）名称统一的契约测试。

锁三条保证（裁定 (A) + D8）：
1) **值＝回退链结果**：③`final_name` → ②`found_name` → ①`std_name`（取第一个非空，全空为空串）；
2) **键名只能是 `standard_name`** ⇒ 必须 `pop` 掉旧键 `std_name`；
3) **保留阶段字段**：`found_name`/`final_name`/`source_name` 是**不同语义**的字段（待确认页要并列展示
   "解析名 vs 查询名"供人工判断），不得因为统一展示名而删除它们。
另锁性能约束：名称由**行内字段**直接算出 ⇒ 不得发生任何额外查询（本用例的假 mgr 只有取列表一个方法）。
"""

from docker.api.pending import get_pending


class _Mgr:
    """假管理器：只实现 `get_pending_items()` ⇒ 若接口内部另做查询，本用例会立即报错。"""

    def __init__(self, items):
        self._items = items

    def get_pending_items(self):
        return self._items


def _one(**over):
    """构造一条待确认行（默认三阶段名齐全）。"""
    item = {
        "id": 1,
        "standard_number": "GB/T 1-2020",
        "std_name": "解析名",
        "found_name": "查询名",
        "final_name": "决策名",
        "source_site": "std_gov",
    }
    item.update(over)
    return item


def test_final_name_wins_and_old_key_removed():
    out = get_pending(mgr=_Mgr([_one()]))["items"][0]
    assert out["standard_name"] == "决策名"
    assert "std_name" not in out, "D8：对外不得保留旧键 std_name"


def test_falls_back_to_found_then_std():
    rows = [
        _one(final_name=""),
        _one(final_name="", found_name=""),
        _one(final_name="", found_name="", std_name=""),
    ]
    items = get_pending(mgr=_Mgr(rows))["items"]
    assert [i["standard_name"] for i in items] == ["查询名", "解析名", ""]


def test_stage_fields_are_preserved():
    """阶段字段（②查询名/③决策名）必须保留：待确认页需要并列展示供人工判断。"""
    out = get_pending(mgr=_Mgr([_one()]))["items"][0]
    assert out["found_name"] == "查询名"
    assert out["final_name"] == "决策名"
    assert out["source_site"] == "std_gov"
    assert out["standard_number"] == "GB/T 1-2020"


def test_empty_list_passthrough():
    assert get_pending(mgr=_Mgr([])) == {"items": []}
