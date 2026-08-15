"""docker/health_check_service.py 单元测试。"""

from unittest.mock import MagicMock, patch

from docker.health_check_service import _probe, _write_health, run_health_check


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
    def test_run_health_check_all_up(self, mock_sites, mock_probe, mock_write):
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
    def test_run_health_check_counts_down(self, mock_sites, mock_probe, mock_write):
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
