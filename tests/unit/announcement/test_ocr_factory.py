"""ocr/__init__.py 单元测试 — create_ocr_provider 工厂函数全覆盖。"""

from unittest.mock import MagicMock, patch

from pilotstd.announcement.ocr import create_ocr_provider


class TestCreateOcrProvider:
    def test_explicit_baidu(self):
        config = {"provider": "baidu", "api_key": "k", "secret_key": "s"}
        with patch(
            "pilotstd.announcement.ocr._create_baidu", return_value=MagicMock()
        ) as mock_create:
            result = create_ocr_provider(config)
            assert result is not None
            mock_create.assert_called_once_with(config)

    def test_explicit_tencent(self):
        config = {"provider": "tencent", "secret_id": "id", "secret_key": "s"}
        with patch(
            "pilotstd.announcement.ocr._create_tencent", return_value=MagicMock()
        ) as mock_create:
            result = create_ocr_provider(config)
            assert result is not None
            mock_create.assert_called_once()

    def test_explicit_aliyun(self):
        config = {
            "provider": "aliyun",
            "access_key_id": "id",
            "access_key_secret": "s",
        }
        with patch(
            "pilotstd.announcement.ocr._create_aliyun", return_value=MagicMock()
        ) as mock_create:
            result = create_ocr_provider(config)
            assert result is not None
            mock_create.assert_called_once()

    def test_explicit_unknown_falls_to_aliyun(self):
        config = {
            "provider": "unknown",
            "access_key_id": "id",
            "access_key_secret": "s",
        }
        with patch(
            "pilotstd.announcement.ocr._create_aliyun", return_value=MagicMock()
        ) as mock_create:
            create_ocr_provider(config)
            mock_create.assert_called_once()

    def test_multi_provider_returns_scheduler(self):
        config = {"baidu_api_key": "k1", "baidu_secret_key": "s1"}
        mock_baidu = MagicMock()
        mock_scheduler = MagicMock()

        with patch(
            "pilotstd.announcement.ocr._create_baidu", return_value=mock_baidu
        ), patch(
            "pilotstd.announcement.ocr._create_tencent", return_value=None
        ), patch(
            "pilotstd.announcement.ocr._create_aliyun", return_value=None
        ), patch(
            "pilotstd.announcement.ocr.OcrSlot", return_value=MagicMock()
        ), patch(
            "pilotstd.announcement.ocr.OcrScheduler", return_value=mock_scheduler
        ), patch(
            "pilotstd.announcement.ocr.OcrCounters", return_value=MagicMock()
        ), patch(
            "pilotstd.announcement.ocr.ProviderCooling", return_value=MagicMock()
        ), patch(
            "pilotstd.announcement.ocr.os.path.join", return_value="/fake/counters.json"
        ), patch(
            "pilotstd.core.config.get_data_dir", return_value="/fake/data"
        ):
            result = create_ocr_provider(config, data_dir="/fake")
            assert result is mock_scheduler

    def test_no_providers_configured_returns_none(self):
        config = {}
        with patch(
            "pilotstd.announcement.ocr._create_baidu", return_value=None
        ), patch(
            "pilotstd.announcement.ocr._create_tencent", return_value=None
        ), patch(
            "pilotstd.announcement.ocr._create_aliyun", return_value=None
        ), patch(
            "pilotstd.announcement.ocr.os.path.join", return_value="/fake/counters.json"
        ), patch(
            "pilotstd.core.config.get_data_dir", return_value="/fake/data"
        ):
            result = create_ocr_provider(config, data_dir="/fake")
            assert result is None
