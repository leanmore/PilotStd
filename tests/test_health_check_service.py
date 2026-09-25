"""docker/health_check_service.py 单元测试。"""

import logging
from unittest.mock import MagicMock, patch

import requests

from docker.health_check_service import (
    _ANNOUNCE_ADAPTERS,
    _log_health_transition,
    _probe,
    _write_health,
    run_health_check,
)
from pilotstd.query.network import safe_request
from pilotstd.query.site_config import create_default_sites

HEALTH_LOGGER = "docker.health_check_service"
NETWORK_LOGGER = "pilotstd.query.network"


class TestProbe:
    @patch("docker.health_check_service.safe_raw_get")
    def test_probe_up(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        mock_get.return_value = resp
        assert _probe("http://example.com", "test") == "up"

    @patch("docker.health_check_service.safe_raw_get")
    def test_probe_down_on_none(self, mock_get):
        mock_get.return_value = None
        assert _probe("http://example.com", "test") == "down"

    @patch("docker.health_check_service.safe_raw_get")
    def test_probe_down_on_5xx(self, mock_get):
        resp = MagicMock()
        resp.status_code = 500
        mock_get.return_value = resp
        assert _probe("http://example.com", "test") == "down"


class TestWriteHealth:
    @patch("docker.health_check_service.Database")
    def test_write_health_upsert(self, mock_db_cls):
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        _write_health("ahbz", "up")
        sql = mock_db.execute.call_args[0][0]
        assert "INSERT INTO adapter_state" in sql
        assert "ON CONFLICT(adapter_name) DO UPDATE SET" in sql
        assert "last_health_check = excluded.last_health_check" in sql
        assert "health_status = excluded.health_status" in sql
        mock_db.close.assert_called_once()


class TestRunHealthCheck:
    @patch("docker.health_check_service._write_health")
    @patch("docker.health_check_service._probe")
    @patch("docker.health_check_service.create_default_sites")
    def test_run_health_check_all_up(self, mock_sites, mock_probe, _mock_write):
        site1 = MagicMock()
        site1.name = "ahbz"
        site1.base_url = "https://ahbz.example.com"
        site2 = MagicMock()
        site2.name = "std_gov"
        site2.base_url = "https://std.example.com"
        mock_sites.return_value = [site1, site2]
        mock_probe.return_value = "up"

        stats = run_health_check()

        # 2 个查询适配器 + 3 个公告适配器（gb/hb/db）= 5
        assert stats["total"] == 5
        assert stats["up"] == 5
        assert stats["down"] == 0

    @patch("docker.health_check_service._write_health")
    @patch("docker.health_check_service._probe")
    @patch("docker.health_check_service.create_default_sites")
    def test_run_health_check_counts_down(self, mock_sites, mock_probe, _mock_write):
        site = MagicMock()
        site.name = "ahbz"
        site.base_url = "https://ahbz.example.com"
        mock_sites.return_value = [site]
        mock_probe.return_value = "down"

        stats = run_health_check()

        # 1 个查询适配器 + 3 个公告适配器 = 4，全部 down
        assert stats["total"] == 4
        assert stats["down"] == 4
        assert stats["up"] == 0


class TestAnnounceAdapters:
    def test_announce_urls_are_distinct(self):
        """公告三站探活地址应为各自搜索端点，而非共用首页。"""
        assert "/noc/search/nocGBPage" in _ANNOUNCE_ADAPTERS["gb"]
        assert "/noc/search/nocHBPage" in _ANNOUNCE_ADAPTERS["hb"]
        assert "/noc/search/nocDBPage" in _ANNOUNCE_ADAPTERS["db"]
        assert len(set(_ANNOUNCE_ADAPTERS.values())) == 3

    @patch("docker.health_check_service._write_health")
    @patch("docker.health_check_service._probe")
    @patch("docker.health_check_service.create_default_sites")
    def test_announce_probe_uses_distinct_urls(self, mock_sites, mock_probe, _mock_write):
        """公告三站探活应分别发往各自端点 URL。"""
        mock_sites.return_value = []
        mock_probe.return_value = "up"

        run_health_check()

        announce_calls = [c for c in mock_probe.call_args_list if c[0][1] in ("gb", "hb", "db")]
        urls = [c[0][0] for c in announce_calls]
        assert len(urls) == 3
        assert len(set(urls)) == 3
        for url in urls:
            assert "/noc/search/noc" in url


# ════════════════════════════════════════════════════════════════
# 第三轮 P2：energy 误判修复 + 健康状态变化才告警
# 现场实测（2026-09-25）：energy 的 stdPage 裸 GET 返回 400、带参数返回 200；
# adapter_state.health_status 因此长期为 down，并每小时刷一条 WARNING。
# jtst 则是外部不可达（本机与 NAS 均 ConnectionError），判决正确、只是重复告警。
# ════════════════════════════════════════════════════════════════


class TestProbeLoggingAndParams:
    """探活必须按站点真实请求形态发参数，并把失败日志交给调用方按状态变化处理。"""

    @patch("docker.health_check_service.safe_raw_get")
    def test_energy_probe_passes_params_and_skips_ssl_verify(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        mock_get.return_value = resp

        result = _probe(
            "https://114.251.111.103:18080/zxd/portal/stdPage",
            "energy",
            "GET",
            {"keyword": "GB", "limit": 15},
        )

        assert result == "up"
        kwargs = mock_get.call_args[1]
        assert kwargs["params"] == {"keyword": "GB", "limit": 15}, "缺参数时站点返回 400 → 误判 down"
        assert kwargs["verify"] is False, "energy 为纯 IP + 自签名证书站点"
        assert kwargs["log_failures"] is False, "探活失败改由调用方按状态变化告警"

    @patch("docker.health_check_service.safe_raw_get")
    def test_probe_without_params_still_works(self, mock_get):
        """未配置 probe_params 的站点保持原行为（params=None）。"""
        resp = MagicMock()
        resp.status_code = 200
        mock_get.return_value = resp

        assert _probe("https://std.example.com", "std_gov") == "up"
        assert mock_get.call_args[1]["params"] is None

    @patch("docker.health_check_service.safe_raw_post")
    def test_post_probe_passes_params(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp

        assert _probe("https://x.example.com", "some_site", "POST", {"q": "1"}) == "up"
        assert mock_post.call_args[1]["params"] == {"q": "1"}


class TestTransitionLogging:
    """健康状态只在变化时告警：重复 down 不刷屏，但状态变化必须留痕。"""

    def test_unchanged_down_is_debug_not_warning(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=HEALTH_LOGGER):
            _log_health_transition("jtst", "down", "down")

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING], "重复 down 不应再打 WARNING"
        assert any(r.levelno == logging.DEBUG for r in caplog.records)

    def test_transition_to_down_warns(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=HEALTH_LOGGER):
            _log_health_transition("jtst", "up", "down")

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "状态变化为 down 必须告警（不掩盖真实错误）"
        assert "转为不可用" in warnings[0].getMessage()

    def test_first_down_warns(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=HEALTH_LOGGER):
            _log_health_transition("energy", None, "down")

        assert [r for r in caplog.records if r.levelno == logging.WARNING], "首次判定 down 要告警"

    def test_recovery_is_info(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=HEALTH_LOGGER):
            _log_health_transition("jtst", "down", "up")

        infos = [r for r in caplog.records if r.levelno == logging.INFO]
        assert infos and "已恢复" in infos[0].getMessage()

    def test_unchanged_up_is_debug(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=HEALTH_LOGGER):
            _log_health_transition("csres", "up", "up")

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestSiteConfigProbeParams:
    """站点配置回归守卫：energy 探活必须声明参数。"""

    def test_energy_site_declares_probe_params(self):
        sites = {s.name: s for s in create_default_sites()}

        assert "energy" in sites
        params = sites["energy"].probe_params
        assert params.get("keyword"), "energy 探活需要 keyword，否则 stdPage 返回 400"
        assert {"tid", "limit", "offset"} <= set(params), "缺少 Bootstrap-table 必需的分页参数"


class TestSafeRequestLogLevel:
    """safe_request(log_failures=False)：失败降到 DEBUG，返回值语义不变。"""

    @staticmethod
    def _failing_session() -> MagicMock:
        session = MagicMock()
        session.request.side_effect = requests.ConnectionError("boom")
        return session

    @patch("pilotstd.query.network.time.sleep", lambda _s: None)
    def test_log_failures_false_downgrades_warning(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=NETWORK_LOGGER):
            result = safe_request(self._failing_session(), "GET", "https://x.invalid", "jtst", log_failures=False)

        assert result is None, "返回值语义不变（仍返回 None）"
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING], "探活失败不应刷 WARNING"
        assert any("请求异常(已重试)" in r.getMessage() for r in caplog.records), "失败事实仍留在 DEBUG"

    @patch("pilotstd.query.network.time.sleep", lambda _s: None)
    def test_log_failures_true_keeps_warning(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=NETWORK_LOGGER):
            safe_request(self._failing_session(), "GET", "https://x.invalid", "jtst")

        assert [r for r in caplog.records if r.levelno == logging.WARNING], "业务请求失败必须保持 WARNING"
