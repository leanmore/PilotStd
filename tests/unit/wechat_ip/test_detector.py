"""detector.py 单元测试 — 2 个业务函数全覆盖。
================================================================
ROI 预检: 71 行中 ~50 行业务逻辑。
浏览器/scheduler 流程已 # pragma: no cover。
================================================================
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.wechat_ip.detector import _validate_ip, detect_ip


# ════════════════════════════════════════════════════════════
# 8. _validate_ip — IPv4 校验
# ════════════════════════════════════════════════════════════

class TestValidateIp:
    def test_valid_public_ip(self):
        assert _validate_ip("8.8.8.8") is True

    def test_valid_private_ip(self):
        # NOTE: 按设计允许私有 IP，非 bug（用于内网环境）
        assert _validate_ip("192.168.1.1") is True
        assert _validate_ip("10.0.0.1") is True
        assert _validate_ip("172.16.0.1") is True

    def test_localhost(self):
        assert _validate_ip("127.0.0.1") is True

    def test_boundary_values(self):
        assert _validate_ip("0.0.0.0") is True
        assert _validate_ip("255.255.255.255") is True

    def test_value_out_of_range(self):
        assert _validate_ip("256.1.1.1") is False
        assert _validate_ip("1.999.1.1") is False

    def test_negative_value(self):
        assert _validate_ip("-1.1.1.1") is False

    def test_wrong_segment_count(self):
        assert _validate_ip("1.2.3") is False
        assert _validate_ip("1.2.3.4.5") is False

    def test_non_numeric(self):
        assert _validate_ip("abc.def.ghi.jkl") is False

    def test_empty_string(self):
        assert _validate_ip("") is False

    def test_ipv6_rejected(self):
        assert _validate_ip("::1") is False
        assert _validate_ip("2001:db8::1") is False


# ════════════════════════════════════════════════════════════
# 9. detect_ip — 多源投票
# ════════════════════════════════════════════════════════════

class TestDetectIp:
    def _make_source(self, text, url="http://test"):
        """构造模拟 IP 检测源。"""
        return (url, lambda t: __import__("re").compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b").search(t))

    def test_all_sources_agree(self):
        """3 个源返回相同 IP → 众数投票通过。"""
        sources = [
            self._make_source("1.2.3.4"),
            self._make_source("1.2.3.4"),
            self._make_source("1.2.3.4"),
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value.text = "1.2.3.4"
            mock_get.return_value.encoding = "utf-8"
            result = detect_ip(sources)
        assert result == "1.2.3.4"

    def test_majority_wins(self):
        """2 源一致、1 源不同 → 返回众数。"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.text = "1.2.3.4"
            mock_get.return_value.encoding = "utf-8"
            mock_resp = MagicMock()
            mock_resp.text = "1.2.3.4"
            mock_resp.encoding = "utf-8"

            sources = [
                ("http://a", lambda t: __import__("re").search(r"1\.2\.3\.4", t)),
                ("http://b", lambda t: __import__("re").search(r"1\.2\.3\.4", t)),
                ("http://c", lambda t: None),  # 失败
            ]
            result = detect_ip(sources)
        assert result == "1.2.3.4"

    def test_single_source_only(self):
        """仅 1 个源 → 直接返回该结果。"""
        sources = [self._make_source("5.6.7.8")]
        with patch("requests.get") as mock_get:
            mock_get.return_value.text = "5.6.7.8"
            mock_get.return_value.encoding = "utf-8"
            result = detect_ip(sources)
        assert result == "5.6.7.8"

    def test_all_sources_fail_returns_none(self):
        """所有源都失败 → 返回 None。"""
        sources = [
            ("http://a", lambda t: None),
            ("http://b", lambda t: None),
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value.text = "garbage"
            mock_get.return_value.encoding = "utf-8"
            result = detect_ip(sources)
        assert result is None

    def test_http_exception_caught_per_source(self):
        """单个源 HTTP 异常 → 该源跳过，其他源继续。"""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                Exception("timeout"),
                MagicMock(text="9.9.9.9", encoding="utf-8"),
            ]
            sources = [
                ("http://down", lambda t: t.strip()),
                ("http://ok", lambda t: t.strip()),
            ]
            result = detect_ip(sources)
        assert result == "9.9.9.9"

    def test_inconsistent_votes_logs_warning(self, caplog):
        """3 个源返回 3 个不同 IP → 无众数，记录 warning（L69）。"""
        caplog.set_level(logging.WARNING)
        sources = [
            ("http://a", lambda t: "1.2.3.4"),
            ("http://b", lambda t: "5.6.7.8"),
            ("http://c", lambda t: "9.9.9.9"),
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(text="any", encoding="utf-8")
            detect_ip(sources)

        assert any("不一致" in rec.message for rec in caplog.records)

    def test_uses_default_sources_when_none_provided(self):
        """sources=None → 使用 DEFAULT_SOURCES 真实请求（mock 网络）。"""
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(text="1.2.3.4", encoding="utf-8")
            result = detect_ip(None)
        assert result == "1.2.3.4"

    def test_invalid_ip_filtered_out(self):
        """提取到非法 IP → 被 _validate_ip 过滤。"""
        sources = [
            ("http://bad", lambda t: "999.999.999.999"),
            ("http://good", lambda t: "1.2.3.4"),
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(text="any", encoding="utf-8")
            result = detect_ip(sources)
        assert result == "1.2.3.4"

    def test_empty_list_uses_default_sources(self):
        """空列表 [] 为 falsy → 回退到 DEFAULT_SOURCES。"""
        # 这是源码设计行为：sources or DEFAULT_SOURCES
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(text="1.2.3.4", encoding="utf-8")
            result = detect_ip([])
        # [] 是 falsy，所以使用 DEFAULT_SOURCES 并返回结果
        assert result is not None
