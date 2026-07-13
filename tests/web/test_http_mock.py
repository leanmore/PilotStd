"""验证 Adapter 发起网络请求时能被 mock 拦截，以及超时/错误处理"""

from unittest import mock

import requests

from pilotstd.query.adapters.std_gov import StdGovAdapter

# ── 模拟全国标准平台搜索结果页 HTML ──

_MOCK_SEARCH_HTML = """<html><body>
<div class="nums"><span>1</span></div>
<div class="panel post">
  <a tid="detail" pid="ABC123">
    <span class="en-code">GB/T 12345-2020</span>
    测试标准名称
  </a>
  <div class="panel-footer">
    <time class="post-date">2020-06-01</time>
    <time class="post-date">2021-01-01</time>
  </div>
  <span class="s-status label-success">现行</span>
</div>
</body></html>"""

_MOCK_EMPTY_HTML = """<html><body>
<div class="nums"><span>0</span></div>
</body></html>"""


def _mock_response(html: str, status_code: int = 200) -> mock.MagicMock:
    """构建一个模拟的 requests.Response 对象。"""
    resp = mock.MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = html
    resp.encoding = "utf-8"
    return resp


# ═══════════════════════════════════════════
# StdGovAdapter（标准查询 — HTML 解析）
# ═══════════════════════════════════════════


class TestStdGovAdapterMock:
    """使用 mock 拦截 safe_get 验证 StdGovAdapter 搜索逻辑。"""

    def test_search_returns_result(self):
        adapter = StdGovAdapter()
        with mock.patch(
            "pilotstd.query.adapters.std_gov.safe_get",
            return_value=_mock_response(_MOCK_SEARCH_HTML),
        ) as mock_get:
            results = adapter._search_multi("GB/T 12345")
            assert len(results) == 1
            assert results[0].standard_number == "GB/T 12345-2020"
            assert results[0].standard_name == "测试标准名称"
            assert results[0].source_site == "std_gov"
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "std.samr.gov.cn/search/stdPage" in str(call_args)

    def test_search_empty_results(self):
        adapter = StdGovAdapter()
        with mock.patch(
            "pilotstd.query.adapters.std_gov.safe_get",
            return_value=_mock_response(_MOCK_EMPTY_HTML),
        ):
            results = adapter._search_multi("GB/T 99999")
            assert results == []

    def test_search_network_error_returns_empty(self):
        adapter = StdGovAdapter()
        with mock.patch(
            "pilotstd.query.adapters.std_gov.safe_get",
            return_value=None,
        ):
            results = adapter._search_multi("GB/T 12345")
            assert results == []

    def test_search_non_200_status(self):
        adapter = StdGovAdapter()
        with mock.patch(
            "pilotstd.query.adapters.std_gov.safe_get",
            return_value=_mock_response("", status_code=500),
        ):
            results = adapter._search_multi("GB/T 12345")
            assert results == []

    def test_single_search_returns_first_candidate(self):
        adapter = StdGovAdapter()
        with mock.patch(
            "pilotstd.query.adapters.std_gov.safe_get",
            return_value=_mock_response(_MOCK_SEARCH_HTML),
        ):
            result = adapter._search("GB/T 12345")
            assert result is not None
            assert result.standard_number == "GB/T 12345-2020"


class TestStdGovAdapterProperties:
    """验证 StdGovAdapter 的基本属性。"""

    def test_site_name(self):
        adapter = StdGovAdapter()
        assert adapter.site_name == "std_gov"

    def test_site_label(self):
        adapter = StdGovAdapter()
        assert adapter.site_label == "国家标准公开"

    def test_search_url_constant(self):
        assert StdGovAdapter.SEARCH_URL == "https://std.samr.gov.cn/search/stdPage"


# ═══════════════════════════════════════════
# IsoGovAdapter（国际标准）
# ═══════════════════════════════════════════


class TestIsoGovAdapter:
    def test_site_properties(self):
        from pilotstd.query.adapters.iso_gov import IsoGovAdapter

        a = IsoGovAdapter()
        assert a.site_name == "iso_gov"
        assert a.site_label == "国际标准平台"

    def test_search_url_is_correct(self):
        from pilotstd.query.adapters.iso_gov import IsoGovAdapter

        a = IsoGovAdapter()
        mock_resp = mock.MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "rows": [
                {
                    "STANDARD_NO": "ISO 9001:2015",
                    "ENGLISH_NAME": "Quality management systems",
                    "STATE": "现行",
                    "CIRCULATION_DATE": "2015-09-01",
                    "STANDARD_STATUS": "ACTIVE",
                }
            ],
        }
        with mock.patch(
            "pilotstd.query.adapters.iso_gov.safe_get",
            return_value=mock_resp,
        ):
            results = a._search_candidates("ISO 9001")
            assert len(results) > 0


# ═══════════════════════════════════════════
# HbbaAdapter（行业标准）
# ═══════════════════════════════════════════


class TestHbbaAdapter:
    def test_site_properties(self):
        from pilotstd.query.adapters.hbba import HbbaAdapter

        a = HbbaAdapter()
        assert a.site_name == "hbba"
        assert a.site_label == "行业标准平台"

    def test_search_url_is_correct(self):
        from pilotstd.query.adapters.hbba import HbbaAdapter

        assert HbbaAdapter.API_URL == "https://hbba.sacinfo.org.cn/stdQueryList"


# ═══════════════════════════════════════════
# AhbzAdapter（安徽地方标准）
# ═══════════════════════════════════════════


class TestAhbzAdapter:
    def test_site_properties(self):
        from pilotstd.query.adapters.ahbz import AhbzAdapter

        a = AhbzAdapter()
        assert a.site_name == "ahbz"
        assert a.site_label == "安徽标准平台"

    def test_search_url_constant(self):
        from pilotstd.query.adapters.ahbz import SEARCH_URL

        assert SEARCH_URL == "https://bzxx.ahbz.org.cn/standard/query"


# ═══════════════════════════════════════════
# OpenstdDownloadAdapter（下载）
# ═══════════════════════════════════════════


class TestOpenstdDownloadAdapter:
    def test_site_properties(self):
        from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter

        a = OpenstdDownloadAdapter()
        assert a.site_name == "openstd_download"

    def test_can_handle_openstd_task(self):
        from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
        from pilotstd.download.models import DownloadTask

        a = OpenstdDownloadAdapter()
        task = DownloadTask(
            standard_number="GB/T 12345-2020",
            source_site="openstd_download",
            extra={"hcno": "ABC123"},
        )
        assert a.can_handle(task)


# ═══════════════════════════════════════════
# SamrGbCrawler（公告爬虫）
# ═══════════════════════════════════════════


class TestAnnouncementCrawler:
    def test_samr_gb_properties(self):
        from pilotstd.announcement.adapters.samr_gb import SamrGbCrawler

        c = SamrGbCrawler()
        assert c.site_name == "samr_gb"
        assert c.standard_type == "gb"

    def test_samr_gb_has_urls(self):
        from pilotstd.announcement.adapters.samr_gb import SamrGbCrawler

        c = SamrGbCrawler()
        assert c._list_url.startswith("https://")
        assert c._detail_url.startswith("https://")

    def test_fetch_list_mocked(self):
        from pilotstd.announcement.adapters.samr_gb import SamrGbCrawler

        c = SamrGbCrawler()
        with mock.patch.object(c, "_fetch_list", return_value=[]):
            with mock.patch.object(c, "_fetch_details_parallel", return_value=[]):
                results = c.fetch_announcements(since_date="2026-01-01")
                assert results == []


# ═══════════════════════════════════════════
# Updater（更新检查）
# ═══════════════════════════════════════════


class TestUpdater:
    def test_github_api_url(self):
        from pilotstd.platform.updater import GITHUB_API_URL

        assert "api.github.com" in GITHUB_API_URL

    def test_is_newer_version(self):
        from pilotstd.platform.updater import is_newer_version

        assert is_newer_version("v2.0.0", "1.0.0") is True
        assert is_newer_version("1.0.0", "2.0.0") is False
        assert is_newer_version("1.0.0", "1.0.0") is False

    def test_check_latest_version_mocked(self):
        from pilotstd.platform.updater import check_latest_version

        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = (
            b'{"tag_name":"v2.0.0","body":"test",'
            b'"assets":[{"browser_download_url":"https://example.com/PilotStd.zip",'
            b'"name":"PilotStd.zip"}]}'
        )
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            result = check_latest_version()
            assert result is not None
            assert result["tag_name"] == "v2.0.0"

    def test_check_latest_version_network_error(self):
        import urllib.error

        from pilotstd.platform.updater import check_latest_version

        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network error"),
        ):
            result = check_latest_version()
            assert result is None


# ═══════════════════════════════════════════
# 通知渠道（企业微信 Webhook）
# ═══════════════════════════════════════════


class TestNotificationChannels:
    def test_wechat_webhook_format(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel

        ch = WechatChannel(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
        assert ch._url.startswith("https://qyapi.weixin.qq.com")

    def test_dingtalk_webhook_format(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        ch = DingTalkChannel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=test")
        assert "dingtalk" in ch._url

    def test_feishu_webhook_format(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel

        ch = FeishuChannel(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test")
        assert "feishu" in ch._url
