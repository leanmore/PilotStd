"""v67-a 解耦契约测试：待确认链路的名称来源与写入面。

锁三件事：
1) **停写**：`PendingService.record_pending()` 的 INSERT **不再包含** `final_name` 列，
   也不再传入该值（③ 的权威落点是 `announcement_record.final_name`）；
2) **改读**：`GET /api/pending` 的③改为经 `fetch_resolved_names()`（**一次批量**，严禁 N+1）
   取自公告表；行内遗留的 `final_name` 值**被忽略**（证明已解耦，而非"顺手还能读到"）；
3) **稳健降级**：批量映射未命中时回退行内 ②查询名 → ①解析名，**绝不返回 None/空串**。
"""

from types import SimpleNamespace
from unittest.mock import patch

from docker.api.pending import get_pending
from pilotstd.manager.pending_service import PendingService


class _Mgr:
    """假管理器：只实现 `get_pending_items()`。"""

    def __init__(self, items):
        self._items = items

    def get_pending_items(self):
        return self._items


def _item(**over):
    """构造一条待确认行（含**已废弃**的 final_name，用于证明它被忽略）。"""
    row = {
        "id": 1,
        "standard_number": "GB/T 1-2020",
        "std_name": "解析名",
        "found_name": "查询名",
        "final_name": "行内遗留决策名（应被忽略）",
        "source_site": "std_gov",
    }
    row.update(over)
    return row


class TestRecordPendingStopsWritingFinalName:
    def test_insert_no_longer_mentions_final_name(self):
        captured = []

        def _fetchone(sql, params=()):  # noqa: ARG001 - 契约签名
            return None  # 不存在 ⇒ 走 INSERT 分支

        def _execute(sql, params=()):
            captured.append((sql, params))
            return None

        db = SimpleNamespace(fetchone=_fetchone, execute=_execute)
        parsed = SimpleNamespace(
            std_name="解析名",
            found_name="查询名",
            match_status="exact",
            effect_status="现行",
            source_path="D:/lib/a.pdf",
            source_name="公告名",
            final_name="决策名（不应被写入）",
            stage_status="pending",
            get_full_number=lambda: "GB/T 1-2020",
        )

        PendingService(db, None).record_pending([parsed])

        assert captured, "应发生一次 INSERT"
        sql, params = captured[0]
        assert "final_name" not in sql, "v67-a：INSERT 不得再写 final_name 列"
        assert "决策名（不应被写入）" not in params, "v67-a：也不得再传该值"
        assert "std_name" in sql and "found_name" in sql, "①②过程字段仍需保留"


class TestGetPendingNameSource:
    def test_authoritative_name_comes_from_batch_mapping(self):
        """③ 取自公告表（批量映射）；行内遗留 final_name 必须被忽略。"""
        with patch(
            "docker.api.pending.fetch_resolved_names",
            return_value={"GB/T 1-2020": "决策名（公告表）"},
        ) as mocked:
            out = get_pending(db=SimpleNamespace(), mgr=_Mgr([_item()]))["items"][0]

        assert out["standard_name"] == "决策名（公告表）"
        assert out["standard_name"] != "行内遗留决策名（应被忽略）", "v67-a：不得再以行内列为③"
        assert "std_name" not in out, "D8：对外不再暴露旧键"
        assert mocked.call_count == 1, "一次批量（严禁 N+1）"

    def test_batch_mapping_called_once_for_many_items(self):
        items = [_item(id=i, standard_number=f"GB/T {i}-2020") for i in range(1, 6)]
        with patch("docker.api.pending.fetch_resolved_names", return_value={}) as mocked:
            get_pending(db=SimpleNamespace(), mgr=_Mgr(items))
        assert mocked.call_count == 1, "5 条也必须只调一次批量映射"

    def test_falls_back_to_found_then_std(self):
        """未命中批量映射 ⇒ 行内 ②查询名 → ①解析名；全空 ⇒ 空串（不抛错、不返回 None）。"""
        rows = [
            _item(standard_number="A"),
            _item(standard_number="B", found_name=""),
            _item(standard_number="C", found_name="", std_name=""),
        ]
        with patch("docker.api.pending.fetch_resolved_names", return_value={}):
            items = get_pending(db=SimpleNamespace(), mgr=_Mgr(rows))["items"]
        assert [i["standard_name"] for i in items] == ["查询名", "解析名", ""]

    def test_stage_fields_are_preserved(self):
        """②查询名等阶段字段必须保留（待确认页要并列展示供人工判断）。"""
        with patch("docker.api.pending.fetch_resolved_names", return_value={}):
            out = get_pending(db=SimpleNamespace(), mgr=_Mgr([_item()]))["items"][0]
        assert out["found_name"] == "查询名"
        assert out["source_site"] == "std_gov"
        assert out["standard_number"] == "GB/T 1-2020"

    def test_empty_list_passthrough(self):
        with patch("docker.api.pending.fetch_resolved_names", return_value={}) as mocked:
            out = get_pending(db=SimpleNamespace(), mgr=_Mgr([]))
        assert out == {"items": []}
        assert mocked.call_count == 1  # 空列表也走同一条批量路径（内部立即返回 {}）
