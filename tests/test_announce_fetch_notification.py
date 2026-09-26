# tests/test_announce_fetch_notification.py
# Per-adapter fetch summary + notification message — unit tests

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestBuildFetchSummary(unittest.TestCase):
    """build_fetch_summary() — payload construction tests."""

    def setUp(self):
        from pilotstd.announce.crawler_service import build_fetch_summary

        self._build = build_fetch_summary

    def test_all_zero(self):
        """全部适配器返回 0 条——count 均为 0，status 均为 success。"""
        adapter_results = [
            {"name": "samr_gb", "type": "national", "count": 0, "status": "success", "error_msg": ""},
            {"name": "samr_hb", "type": "industry", "count": 0, "status": "success", "error_msg": ""},
            {"name": "samr_db", "type": "local", "count": 0, "status": "success", "error_msg": ""},
        ]
        summary = self._build(adapter_results)
        self.assertEqual(summary["total_count"], 0)
        self.assertFalse(summary["has_error"])
        self.assertEqual(len(summary["adapters"]), 3)
        for a in summary["adapters"]:
            self.assertEqual(a["count"], 0)
            self.assertEqual(a["status"], "success")

    def test_partial_zero(self):
        """国标 3 条、行标 0、地标 5 条——明细各自独立。"""
        adapter_results = [
            {"name": "samr_gb", "type": "national", "count": 3, "status": "success", "error_msg": ""},
            {"name": "samr_hb", "type": "industry", "count": 0, "status": "success", "error_msg": ""},
            {"name": "samr_db", "type": "local", "count": 5, "status": "success", "error_msg": ""},
        ]
        summary = self._build(adapter_results)
        self.assertEqual(summary["total_count"], 8)
        self.assertFalse(summary["has_error"])
        self.assertEqual(summary["adapters"][0]["count"], 3)
        self.assertEqual(summary["adapters"][1]["count"], 0)
        self.assertEqual(summary["adapters"][2]["count"], 5)

    def test_all_with_data(self):
        """全部适配器非零——total_count 等于各 count 之和。"""
        adapter_results = [
            {"name": "samr_gb", "type": "national", "count": 10, "status": "success", "error_msg": ""},
            {"name": "samr_hb", "type": "industry", "count": 7, "status": "success", "error_msg": ""},
        ]
        summary = self._build(adapter_results)
        self.assertEqual(summary["total_count"], 17)
        self.assertFalse(summary["has_error"])

    def test_adapter_error(self):
        """行标适配器抛异常——status=error, error_msg 非空, has_error=True。"""
        adapter_results = [
            {"name": "samr_gb", "type": "national", "count": 2, "status": "success", "error_msg": ""},
            {"name": "samr_hb", "type": "industry", "count": 0, "status": "error", "error_msg": "连接超时"},
            {"name": "samr_db", "type": "local", "count": 1, "status": "success", "error_msg": ""},
        ]
        summary = self._build(adapter_results)
        self.assertEqual(summary["total_count"], 3)
        self.assertTrue(summary["has_error"])
        err_adapter = summary["adapters"][1]
        self.assertEqual(err_adapter["status"], "error")
        self.assertEqual(err_adapter["error_msg"], "连接超时")
        self.assertEqual(err_adapter["count"], 0)

    def test_fetch_time_is_iso_utc(self):
        """fetch_time 为 UTC ISO 8601 格式。"""
        adapter_results = [
            {"name": "samr_gb", "type": "national", "count": 1, "status": "success", "error_msg": ""},
        ]
        summary = self._build(adapter_results)
        ft = summary["fetch_time"]
        self.assertIn("T", ft)
        self.assertIn("+00:00", ft)


class TestBuildAnnounceFetchSummaryMessage(unittest.TestCase):
    """_build_announce_fetch_summary_message() — 通知消息构建测试。"""

    def setUp(self):
        from pilotstd.core.notification._builders_task_results import _build_announce_fetch_summary_message

        class _BuilderNS:
            pass
        self.mixin = _BuilderNS()
        self.mixin._build_announce_fetch_summary_message = _build_announce_fetch_summary_message

    def _make_data(self, adapters=None):

        if adapters is None:
            adapters = []
        return {
            "fetch_time": "2026-07-29T10:00:00+00:00",
            "adapters": adapters,
            "total_count": sum(a["count"] for a in adapters),
            "has_error": any(a["status"] == "error" for a in adapters),
        }

    def test_level_info_when_no_error(self):
        data = self._make_data(
            [
                {"name": "samr_gb", "type": "national", "count": 3, "status": "success", "error_msg": ""},
            ]
        )
        msg = self.mixin._build_announce_fetch_summary_message(data)
        self.assertEqual(msg.level, "info")
        self.assertEqual(msg.event_type, "announce_fetch_summary")

    def test_level_warning_when_has_error(self):
        data = self._make_data(
            [
                {"name": "samr_gb", "type": "national", "count": 1, "status": "success", "error_msg": ""},
                {"name": "samr_hb", "type": "industry", "count": 0, "status": "error", "error_msg": "DNS 解析失败"},
            ]
        )
        msg = self.mixin._build_announce_fetch_summary_message(data)
        self.assertEqual(msg.level, "warning")

    def test_error_adapter_shows_error_msg(self):
        data = self._make_data(
            [
                {"name": "samr_gb", "type": "national", "count": 0, "status": "error", "error_msg": "TLS 握手超时"},
            ]
        )
        msg = self.mixin._build_announce_fetch_summary_message(data)
        # 至少有一个 block 的 value 包含错误信息
        error_blocks = [b for b in msg.blocks if hasattr(b, "value") and "TLS" in str(b.value)]
        self.assertTrue(len(error_blocks) > 0)

    def test_truncation_when_exceeds_max_display(self):
        """超过 MAX_ADAPTER_DISPLAY 时截断并显示汇总提示。"""
        adapters = []
        for i in range(15):
            adapters.append(
                {
                    "name": f"adapter_{i}",
                    "type": "other",
                    "count": 1,
                    "status": "success",
                    "error_msg": "",
                }
            )
        data = self._make_data(adapters)
        msg = self.mixin._build_announce_fetch_summary_message(data)
        # 总计 + 10 个明细 + 1 个截断提示 = 12 个 KeyValueBlock（不计入 TextBlock）
        kv_blocks = [b for b in msg.blocks if hasattr(b, "key")]
        self.assertLessEqual(len(kv_blocks), 13, "超出预期的 KeyValueBlock 数量")


if __name__ == "__main__":
    unittest.main()
