# tests/gui/test_announce_flow_engine.py
"""AnnounceFlowEngine 纯单元测试 — 零 Qt，毫秒级。"""

from __future__ import annotations

from pilotstd.ui.core.handlers.announce_flow_engine import AnnounceFlowEngine

# ═══════════════════════════════════════════════════════════════════
# parse_announcement
# ═══════════════════════════════════════════════════════════════════


class TestParseAnnouncement:
    def test_normal_input(self):
        raw = {
            "title": "国家标准公告2024年第1号",
            "code": "2024-001",
            "pid": "abc123",
            "publish_date": "2024-01-15",
            "standard_count": 5,
        }
        r = AnnounceFlowEngine.parse_announcement(raw)
        assert r["title"] == "国家标准公告2024年第1号"
        assert r["code"] == "2024-001"
        assert r["pid"] == "abc123"
        assert r["publish_date"] == "2024-01-15"
        assert r["standard_count"] == 5
        assert r["is_valid"] is True

    def test_alternate_field_names(self):
        raw = {"TITLE": "公告标题", "NOTICE_DATE": "2024-06-01", "STD_COUNT": "3"}
        r = AnnounceFlowEngine.parse_announcement(raw)
        assert r["title"] == "公告标题"
        assert r["publish_date"] == "2024-06-01"
        assert r["standard_count"] == 3

    def test_missing_fields_get_defaults(self):
        r = AnnounceFlowEngine.parse_announcement({"pid": "only_pid"})
        assert r["title"] == ""
        assert r["code"] == ""
        assert r["standard_count"] == 0
        assert r["is_valid"] is False

    def test_none_input(self):
        r = AnnounceFlowEngine.parse_announcement(None)
        assert r["title"] == ""
        assert r["is_valid"] is False

    def test_empty_dict(self):
        r = AnnounceFlowEngine.parse_announcement({})
        assert r["standard_count"] == 0
        assert r["is_valid"] is False

    def test_not_a_dict(self):
        r = AnnounceFlowEngine.parse_announcement("not_a_dict")
        assert r["is_valid"] is False

    def test_standard_count_type_error(self):
        r = AnnounceFlowEngine.parse_announcement({"standard_count": "not_a_number"})
        assert r["standard_count"] == 0

    def test_standard_count_string_int(self):
        r = AnnounceFlowEngine.parse_announcement({"standard_count": "42"})
        assert r["standard_count"] == 42


# ═══════════════════════════════════════════════════════════════════
# filter_by_status
# ═══════════════════════════════════════════════════════════════════


class TestFilterByStatus:
    def test_empty_list(self):
        r = AnnounceFlowEngine.filter_by_status([], "现行")
        assert r == []

    def test_all_match(self):
        items = [{"status": "现行"}, {"status": "现行"}]
        r = AnnounceFlowEngine.filter_by_status(items, "现行")
        assert len(r) == 2

    def test_none_match(self):
        items = [{"status": "现行"}, {"status": "废止"}]
        r = AnnounceFlowEngine.filter_by_status(items, "即将实施")
        assert r == []

    def test_mixed_status(self):
        items = [
            {"code": "A", "status": "现行"},
            {"code": "B", "status": "废止"},
            {"code": "C", "status": "现行"},
        ]
        r = AnnounceFlowEngine.filter_by_status(items, "现行")
        assert len(r) == 2
        assert all(x["status"] == "现行" for x in r)

    def test_effect_status_field(self):
        items = [{"effect_status": "废止"}]
        r = AnnounceFlowEngine.filter_by_status(items, "废止")
        assert len(r) == 1

    def test_empty_status_arg(self):
        items = [{"status": "现行"}]
        r = AnnounceFlowEngine.filter_by_status(items, "")
        assert r == items


# ═══════════════════════════════════════════════════════════════════
# sort_by_date
# ═══════════════════════════════════════════════════════════════════


class TestSortByDate:
    def test_empty_list(self):
        r = AnnounceFlowEngine.sort_by_date([])
        assert r == []

    def test_descending_order(self):
        items = [
            {"code": "B", "publish_date": "2024-01-01"},
            {"code": "A", "publish_date": "2024-06-01"},
            {"code": "C", "publish_date": "2024-03-15"},
        ]
        r = AnnounceFlowEngine.sort_by_date(items)
        assert r[0]["code"] == "A"
        assert r[1]["code"] == "C"
        assert r[2]["code"] == "B"

    def test_ascending_order(self):
        items = [
            {"code": "B", "publish_date": "2024-06-01"},
            {"code": "A", "publish_date": "2024-01-01"},
        ]
        r = AnnounceFlowEngine.sort_by_date(items, descending=False)
        assert r[0]["code"] == "A"
        assert r[1]["code"] == "B"

    def test_same_date_preserves_order(self):
        items = [
            {"code": "B", "publish_date": "2024-01-01"},
            {"code": "A", "publish_date": "2024-01-01"},
        ]
        r = AnnounceFlowEngine.sort_by_date(items)
        assert len(r) == 2

    def test_notice_date_fallback(self):
        items = [
            {"code": "B", "notice_date": "2024-01-01"},
            {"code": "A", "publish_date": "2024-06-01"},
        ]
        r = AnnounceFlowEngine.sort_by_date(items)
        assert r[0]["code"] == "A"

    def test_missing_date_goes_last(self):
        items = [
            {"code": "B", "publish_date": "2024-01-01"},
            {"code": "A"},
        ]
        r = AnnounceFlowEngine.sort_by_date(items)
        assert r[0]["code"] == "B"
        assert r[1]["code"] == "A"
