# tests/test_announcement_base_full.py
# BaseAnnounceCrawler 完整单元测试

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.announcement.base import AdapterFrozenError, BaseAnnounceCrawler


# ── 具体子类（实现抽象属性）──────────────────────────────────────
class ConcreteCrawler(BaseAnnounceCrawler):
    """用于测试的具体子类。"""

    @property
    def site_name(self) -> str:
        return "test_site"

    @property
    def standard_type(self) -> str:
        return "gb"

    @property
    def _list_url(self) -> str:
        return "https://example.com/api/list"

    @property
    def _detail_url(self) -> str:
        return "https://example.com/detail"


# ── 动态创建子类（验证 ABC 行为）──────────────────────────────────
def _make_dynamic_crawler(site_name="dyn_site", standard_type="hb",
                          list_url="http://dyn/list", detail_url="http://dyn/detail"):
    """用 type() 动态创建 BaseAnnounceCrawler 子类并返回实例。"""
    DynCrawler = type(
        "DynCrawler",
        (BaseAnnounceCrawler,),
        {
            "site_name": property(lambda s: site_name),
            "standard_type": property(lambda s: standard_type),
            "_list_url": property(lambda s: list_url),
            "_detail_url": property(lambda s: detail_url),
        },
    )
    return DynCrawler()


class TestBaseAnnounceCrawlerInit(unittest.TestCase):
    """构造函数和基本属性测试。"""

    def test_initial_state_defaults(self):
        c = ConcreteCrawler()
        self.assertEqual(c._cb_freeze_count, 0)
        self.assertIsNone(c._cb_first_freeze_time)
        self.assertIsNone(c._cb_frozen_until)
        self.assertEqual(c._cb_fail_streak, 0)
        self.assertFalse(c._cb_loaded)
        self.assertIsNone(c._http)

    def test_di_http_session(self):
        mock_session = MagicMock()
        c = ConcreteCrawler(_http=mock_session)
        self.assertIs(c._http, mock_session)

    def test_source_site_property(self):
        c = ConcreteCrawler()
        self.assertEqual(c.source_site, "announcement_gb")

    def test_dynamic_subclass_with_type(self):
        c = _make_dynamic_crawler(site_name="dyn", standard_type="db",
                                  list_url="http://a", detail_url="http://b")
        self.assertEqual(c.site_name, "dyn")
        self.assertEqual(c.standard_type, "db")
        self.assertEqual(c._list_url, "http://a")
        self.assertEqual(c._detail_url, "http://b")
        self.assertEqual(c.source_site, "announcement_db")


class TestAdapterFrozenError(unittest.TestCase):
    """AdapterFrozenError 异常测试。"""

    def test_message_and_attrs(self):
        err = AdapterFrozenError("my_adapter", 600)
        self.assertIn("my_adapter", str(err))
        self.assertIn("600", str(err))
        self.assertEqual(err.adapter_name, "my_adapter")
        self.assertEqual(err.remaining_seconds, 600)


class TestFinalizeItems(unittest.TestCase):
    """_finalize_items 静态方法测试。"""

    def test_adds_default_fields(self):
        items = [{"std_code": "GB/T 1.1-2020"}]
        result = BaseAnnounceCrawler._finalize_items(items, "https://example.com/doc.pdf")
        self.assertEqual(result[0]["attachment_url"], "https://example.com/doc.pdf")
        self.assertEqual(result[0]["attachment_path"], "")

    def test_does_not_overwrite_existing(self):
        items = [{"std_code": "GB/T 1.1", "attachment_url": "old_url", "attachment_path": "/tmp/old"}]
        result = BaseAnnounceCrawler._finalize_items(items, "new_url")
        self.assertEqual(result[0]["attachment_url"], "old_url")
        self.assertEqual(result[0]["attachment_path"], "/tmp/old")

    def test_empty_items(self):
        result = BaseAnnounceCrawler._finalize_items([], "")
        self.assertEqual(result, [])


class TestCircuitBreakerLoadHealth(unittest.TestCase):
    """_cb_load_health 测试 —— 从 DB 加载健康状态。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def tearDown(self):
        patch.stopall()

    @patch("pilotstd.core.config.paths.get_db_path")
    @patch("pilotstd.core.db.Database")
    def test_load_health_existing_row_restores_state(self, mock_db_cls, mock_get_db_path):
        """已有记录：应恢复 freeze_count/fail_streak 等字段。"""
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.fetchone.return_value = {
            "freeze_count": 2,
            "fail_streak": 1,
            "first_freeze_time": "2025-01-01T00:00:00+00:00",
            "frozen_until": "2025-01-01T06:00:00+00:00",
        }

        self.crawler._cb_load_health()

        self.assertEqual(self.crawler._cb_freeze_count, 2)
        self.assertEqual(self.crawler._cb_fail_streak, 1)
        self.assertIsNotNone(self.crawler._cb_first_freeze_time)
        self.assertIsNotNone(self.crawler._cb_frozen_until)
        self.assertTrue(self.crawler._cb_loaded)
        mock_db.close.assert_called_once()

    @patch("pilotstd.core.config.paths.get_db_path")
    @patch("pilotstd.core.db.Database")
    def test_load_health_no_existing_row_inserts(self, mock_db_cls, mock_get_db_path):
        """无记录：应插入一行初始记录。"""
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.fetchone.return_value = None

        self.crawler._cb_load_health()

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        self.assertIn("INSERT INTO adapter_state", call_args[0])
        self.assertTrue(self.crawler._cb_loaded)

    @patch("pilotstd.core.config.paths.get_db_path")
    @patch("pilotstd.core.db.Database")
    def test_load_health_already_loaded_skips(self, mock_db_cls, mock_get_db_path):
        """_cb_loaded=True 时直接跳过。"""
        self.crawler._cb_loaded = True
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db

        self.crawler._cb_load_health()

        mock_db.fetchone.assert_not_called()

    @patch("pilotstd.core.config.paths.get_db_path")
    @patch("pilotstd.core.db.Database")
    def test_load_health_db_error_swallowed(self, mock_db_cls, mock_get_db_path):
        """DB 异常不应抛出，仅保持 _cb_loaded=False。"""
        mock_db_cls.side_effect = RuntimeError("DB 挂了")

        self.crawler._cb_load_health()

        self.assertFalse(self.crawler._cb_loaded)


class TestCircuitBreakerSaveHealth(unittest.TestCase):
    """_cb_save_health 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def tearDown(self):
        patch.stopall()

    @patch("pilotstd.core.config.paths.get_db_path")
    @patch("pilotstd.core.db.Database")
    def test_save_health_persists_state(self, mock_db_cls, mock_get_db_path):
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.crawler._cb_freeze_count = 1
        self.crawler._cb_fail_streak = 3
        self.crawler._cb_frozen_until = now + timedelta(hours=1)

        self.crawler._cb_save_health()

        mock_db.execute.assert_called_once()
        mock_db.close.assert_called_once()
        sql = mock_db.execute.call_args[0][0]
        self.assertIn("INSERT OR REPLACE", sql)

    @patch("pilotstd.core.config.paths.get_db_path")
    @patch("pilotstd.core.db.Database")
    def test_save_health_error_swallowed(self, mock_db_cls, mock_get_db_path):
        mock_db_cls.side_effect = RuntimeError("写入失败")

        # 不应抛出异常
        self.crawler._cb_save_health()


class TestCircuitBreakerCheckFrozen(unittest.TestCase):
    """_cb_check_frozen 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def tearDown(self):
        patch.stopall()

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_load_health")
    def test_not_frozen_passes(self, mock_load):
        """未冻结：正常通过，不抛异常。"""
        self.crawler._cb_frozen_until = None
        self.crawler._cb_check_frozen()

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_load_health")
    def test_frozen_raises_error(self, mock_load):
        """冻结中：抛 AdapterFrozenError，含剩余秒数。"""
        future = datetime.now(timezone.utc) + timedelta(seconds=500)
        self.crawler._cb_frozen_until = future

        with self.assertRaises(AdapterFrozenError) as ctx:
            self.crawler._cb_check_frozen()
        self.assertEqual(ctx.exception.adapter_name, self.crawler.site_name)
        self.assertGreater(ctx.exception.remaining_seconds, 0)

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_load_health")
    def test_thaw_with_24h_window_reset(self, mock_load, mock_save):
        """冻结到期 + 首次冻结超过24h窗口：计数归零。"""
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.crawler._cb_frozen_until = past
        self.crawler._cb_first_freeze_time = datetime.now(timezone.utc) - timedelta(hours=25)
        self.crawler._cb_freeze_count = 3

        self.crawler._cb_check_frozen()

        self.assertIsNone(self.crawler._cb_frozen_until)
        self.assertEqual(self.crawler._cb_freeze_count, 0)
        self.assertIsNone(self.crawler._cb_first_freeze_time)
        mock_save.assert_called_once()

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_load_health")
    def test_thaw_within_24h_window_keeps_count(self, mock_load, mock_save):
        """冻结到期但首次冻结在24h内：不归零。"""
        past = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.crawler._cb_frozen_until = past
        self.crawler._cb_first_freeze_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.crawler._cb_freeze_count = 2

        self.crawler._cb_check_frozen()

        self.assertIsNone(self.crawler._cb_frozen_until)
        self.assertEqual(self.crawler._cb_freeze_count, 2)
        self.assertIsNotNone(self.crawler._cb_first_freeze_time)


class TestCircuitBreakerRecordSuccess(unittest.TestCase):
    """_cb_record_success 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def tearDown(self):
        patch.stopall()

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    def test_resets_fail_streak(self, mock_save):
        self.crawler._cb_fail_streak = 5
        self.crawler._cb_record_success()
        self.assertEqual(self.crawler._cb_fail_streak, 0)
        mock_save.assert_called_once()

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    def test_keeps_freeze_count_unchanged(self, mock_save):
        self.crawler._cb_freeze_count = 2
        self.crawler._cb_record_success()
        self.assertEqual(self.crawler._cb_freeze_count, 2)


class TestCircuitBreakerRecordFailure(unittest.TestCase):
    """_cb_record_failure 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def tearDown(self):
        patch.stopall()

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch.object(ConcreteCrawler, "_cb_threshold", new_callable=PropertyMock)
    def test_below_threshold_no_freeze(self, mock_threshold, mock_save):
        """失败次数低于阈值：不触发冻结，返回 False。"""
        mock_threshold.return_value = 5
        self.crawler._cb_fail_streak = 2

        result = self.crawler._cb_record_failure()

        self.assertEqual(self.crawler._cb_fail_streak, 3)
        self.assertFalse(result)
        self.assertIsNone(self.crawler._cb_frozen_until)

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch.object(ConcreteCrawler, "_cb_threshold", new_callable=PropertyMock)
    def test_reaches_threshold_triggers_freeze(self, mock_threshold, mock_save):
        """失败次数达到阈值：触发冻结，返回 True。"""
        mock_threshold.return_value = 3
        self.crawler._cb_fail_streak = 2  # 累加后=3 等于阈值

        result = self.crawler._cb_record_failure()

        self.assertTrue(result)
        self.assertIsNotNone(self.crawler._cb_frozen_until)
        self.assertEqual(self.crawler._cb_freeze_count, 1)
        self.assertEqual(self.crawler._cb_fail_streak, 0)  # 冻结后重置

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch.object(ConcreteCrawler, "_cb_threshold", new_callable=PropertyMock)
    def test_duration_index_capped(self, mock_threshold, mock_save):
        """冻结次数超过 duration 数组长度时，使用最大时长。"""
        mock_threshold.return_value = 1
        self.crawler._cb_freeze_count = 10  # 远超数组长度
        before_freeze = datetime.now(timezone.utc)

        self.crawler._cb_record_failure()

        expected_duration = self.crawler._cb_durations[-1]  # 最大时长
        actual_duration = (self.crawler._cb_frozen_until - before_freeze).total_seconds()
        # 允许 5 秒误差
        self.assertAlmostEqual(actual_duration, expected_duration, delta=5)

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch.object(ConcreteCrawler, "_cb_threshold", new_callable=PropertyMock)
    @patch.object(ConcreteCrawler, "_cb_reset_hours", new_callable=PropertyMock)
    def test_24h_window_reset_before_freeze(self, mock_reset, mock_threshold, mock_save):
        """触发冻结前检查 24h 窗口，超期则归零计数后冻结。"""
        mock_threshold.return_value = 1
        mock_reset.return_value = 24
        self.crawler._cb_freeze_count = 3
        self.crawler._cb_first_freeze_time = datetime.now(timezone.utc) - timedelta(hours=25)

        result = self.crawler._cb_record_failure()

        self.assertTrue(result)
        self.assertEqual(self.crawler._cb_freeze_count, 1)  # 归零后累加到 1
        # _cb_first_freeze_time 在归零后立刻被冻结逻辑重新设为 now
        self.assertIsNotNone(self.crawler._cb_first_freeze_time)

    @patch("pilotstd.announcement.base.BaseAnnounceCrawler._cb_save_health")
    @patch.object(ConcreteCrawler, "_cb_threshold", new_callable=PropertyMock)
    def test_first_freeze_time_set_once(self, mock_threshold, mock_save):
        """首次冻结时设置 _cb_first_freeze_time。后续冻结不重置。"""
        mock_threshold.return_value = 1
        self.crawler._cb_first_freeze_time = None

        self.crawler._cb_record_failure()
        first_time = self.crawler._cb_first_freeze_time
        self.assertIsNotNone(first_time)

        # 模拟解冻后再次触发
        self.crawler._cb_frozen_until = None
        self.crawler._cb_fail_streak = 0
        self.crawler._cb_record_failure()
        self.assertEqual(self.crawler._cb_first_freeze_time, first_time)


class TestFetchList(unittest.TestCase):
    """_fetch_list 测试 —— 分页拉取公告列表。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    @patch("pilotstd.announcement.base.safe_request")
    def test_single_page_returns_all_rows(self, mock_safe_request):
        """单页结果全部返回。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "rows": [
                {"PID": "p1", "CODE": "C1", "TITLE": "公告1", "NOTICE_DATE": "2024-01-15", "STD_COUNT": "3"},
                {"PID": "p2", "CODE": "C2", "TITLE": "公告2", "NOTICE_DATE": "2024-01-10", "STD_COUNT": "1"},
            ],
            "total": 2,
        }
        mock_safe_request.return_value = mock_resp

        result = self.crawler._fetch_list("2024-01-01", 20)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["pid"], "p1")
        self.assertEqual(result[0]["code"], "C1")
        self.assertEqual(result[1]["pid"], "p2")

    @patch("pilotstd.announcement.base.safe_request")
    def test_pagination_multiple_pages(self, mock_safe_request):
        """多页数据：模拟 page1 返回 page_size 条，page2 返回 0 条。"""
        def make_resp(session, method, url, site_name, timeout, params):
            resp = MagicMock()
            page = params.get("pageNumber", 1)
            if page == 1:
                resp.json.return_value = {
                    "rows": [{"PID": f"p{i}", "CODE": f"C{i}", "TITLE": f"T{i}", "NOTICE_DATE": "2024-01-15", "STD_COUNT": "1"} for i in range(1, 21)],
                    "total": 30,
                }
            elif page == 2:
                resp.json.return_value = {
                    "rows": [{"PID": f"p{i}", "CODE": f"C{i}", "TITLE": f"T{i}", "NOTICE_DATE": "2024-01-14", "STD_COUNT": "1"} for i in range(21, 31)],
                    "total": 30,
                }
            return resp
        mock_safe_request.side_effect = make_resp

        result = self.crawler._fetch_list("2024-01-01", 20)

        self.assertEqual(len(result), 30)
        self.assertEqual(mock_safe_request.call_count, 2)

    @patch("pilotstd.announcement.base.safe_request")
    def test_date_filtering_stops_early(self, mock_safe_request):
        """遇到早于 since_date 的记录时提前终止。"""
        def make_resp(session, method, url, site_name, timeout, params):
            resp = MagicMock()
            resp.json.return_value = {
                "rows": [
                    {"PID": "p1", "CODE": "C1", "TITLE": "新公告", "NOTICE_DATE": "2024-02-01", "STD_COUNT": "1"},
                    {"PID": "p2", "CODE": "C2", "TITLE": "旧公告", "NOTICE_DATE": "2024-01-01", "STD_COUNT": "1"},
                ],
                "total": 2,
            }
            return resp
        mock_safe_request.side_effect = make_resp

        result = self.crawler._fetch_list("2024-01-15", 20)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pid"], "p1")

    @patch("pilotstd.announcement.base.safe_request")
    def test_no_since_date_returns_all(self, mock_safe_request):
        """since_date 为空时不触发提前终止。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "rows": [
                {"PID": "p1", "CODE": "C1", "TITLE": "无日期限制", "NOTICE_DATE": "2020-01-01", "STD_COUNT": "1"},
            ],
            "total": 1,
        }
        mock_safe_request.return_value = mock_resp

        result = self.crawler._fetch_list("", 20)

        self.assertEqual(len(result), 1)

    @patch("pilotstd.announcement.base.safe_request")
    def test_request_failure_returns_empty(self, mock_safe_request):
        """请求失败（safe_request 返回 None）时返回空列表。"""
        mock_safe_request.return_value = None

        result = self.crawler._fetch_list("2024-01-01", 20)

        self.assertEqual(result, [])

    @patch("pilotstd.announcement.base.safe_request")
    def test_json_parse_error_returns_empty(self, mock_safe_request):
        """响应 JSON 解析失败时返回空列表。"""
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("bad JSON")
        mock_safe_request.return_value = mock_resp

        result = self.crawler._fetch_list("2024-01-01", 20)

        self.assertEqual(result, [])

    @patch("pilotstd.announcement.base.safe_request")
    def test_empty_rows_returns_empty(self, mock_safe_request):
        """响应 rows 为空时返回空列表。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rows": [], "total": 0}
        mock_safe_request.return_value = mock_resp

        result = self.crawler._fetch_list("2024-01-01", 20)

        self.assertEqual(result, [])

    @patch("pilotstd.announcement.base.safe_request")
    def test_response_with_c_title_fallback(self, mock_safe_request):
        """无 TITLE 字段时回退到 C_TITLE。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "rows": [
                {"PID": "p1", "CODE": "C1", "C_TITLE": "中文标题", "NOTICE_DATE": "2024-01-15", "STD_COUNT": "1"},
            ],
            "total": 1,
        }
        mock_safe_request.return_value = mock_resp

        result = self.crawler._fetch_list("2024-01-01", 20)

        self.assertEqual(result[0]["title"], "中文标题")


class TestFetchDetail(unittest.TestCase):
    """_fetch_detail 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    @patch("pilotstd.announcement.base.safe_raw_get")
    def test_success_returns_html(self, mock_safe_raw_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>公告详情</body></html>"
        mock_safe_raw_get.return_value = mock_resp

        result = self.crawler._fetch_detail("pid001")

        self.assertIn("公告详情", result)
        mock_safe_raw_get.assert_called_once()

    @patch("pilotstd.announcement.base.safe_raw_get")
    def test_request_failure_returns_none(self, mock_safe_raw_get):
        mock_safe_raw_get.return_value = None

        result = self.crawler._fetch_detail("pid001")

        self.assertIsNone(result)

    @patch("pilotstd.announcement.base.safe_raw_get")
    def test_non_200_status_returns_none(self, mock_safe_raw_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_safe_raw_get.return_value = mock_resp

        result = self.crawler._fetch_detail("pid001")

        self.assertIsNone(result)


class TestParseItems(unittest.TestCase):
    """_parse_items 测试 —— 页面结构路由。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    @patch("pilotstd.announcement.parser.parse_announcement_detail")
    @patch("pilotstd.announcement.parser.find_attachment_url")
    def test_html_only_no_attachment(self, mock_find_url, mock_parse):
        """纯网页，HTML 有数据无附件。"""
        mock_find_url.return_value = ""
        mock_parse.return_value = (
            [{"std_code": "GB/T 1.1-2020", "std_name": "测试"}],
            {"title": "公告标题"},
        )

        result = self.crawler._parse_items("<html>data</html>")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["std_code"], "GB/T 1.1-2020")

    @patch.object(ConcreteCrawler, "_download_attachment")
    @patch("pilotstd.announcement.parser.parse_announcement_detail")
    @patch("pilotstd.announcement.parser.find_attachment_url")
    def test_attachment_only_downloads_and_parses(self, mock_find_url, mock_parse, mock_download):
        """纯附件：HTML 无表格但有附件链接。"""
        mock_find_url.return_value = "https://example.com/doc.pdf"

        def parse_side_effect(html, att_bytes, att_url, ocr_provider=None):
            if att_bytes is None:
                return ([], {"title": ""})
            return (
                [{"std_code": "GB/T 2.2-2020", "std_name": "附件标准"}],
                {"title": ""},
            )
        mock_parse.side_effect = parse_side_effect
        mock_download.return_value = b"fake pdf bytes"

        result = self.crawler._parse_items("<html>no table</html>")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["std_code"], "GB/T 2.2-2020")

    @patch("pilotstd.announcement.parser.parse_announcement_detail")
    @patch("pilotstd.announcement.parser.find_attachment_url")
    def test_empty_returns_empty(self, mock_find_url, mock_parse):
        """HTML 无表格也无附件：返回空列表。"""
        mock_find_url.return_value = ""
        mock_parse.return_value = ([], {"title": ""})

        result = self.crawler._parse_items("<html>empty</html>")

        self.assertEqual(result, [])


class TestProcessOneDetail(unittest.TestCase):
    """_process_one_detail 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def _bump(self, pid):
        pass

    @patch.object(ConcreteCrawler, "_parse_items")
    @patch.object(ConcreteCrawler, "_fetch_detail")
    def test_success_returns_parsed_items(self, mock_fetch, mock_parse):
        """成功获取详情并解析。"""
        mock_fetch.return_value = "<html>detail</html>"
        mock_parse.return_value = [{"std_code": "GB/T 1.1-2020", "std_name": "测试"}]

        ann = {"pid": "p001", "code": "C001", "title": "公告标题", "notice_date": "2024-01-15", "std_count": "1"}
        result = self.crawler._process_one_detail(ann, None, self._bump)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["std_code"], "GB/T 1.1-2020")
        self.assertEqual(result[0]["announcement_title"], "公告标题")
        self.assertEqual(result[0]["_pid"], "p001")
        self.assertEqual(result[0]["announce_no"], "C001")
        self.assertEqual(result[0]["publish_date"], "2024-01-15")

    @patch.object(ConcreteCrawler, "_fetch_detail")
    def test_fetch_failure_returns_empty(self, mock_fetch):
        """获取详情失败返回空列表。"""
        mock_fetch.return_value = None

        ann = {"pid": "p001", "code": "C001", "title": "公告", "notice_date": "2024-01-15", "std_count": "1"}
        result = self.crawler._process_one_detail(ann, None, self._bump)

        self.assertEqual(result, [])

    @patch.object(ConcreteCrawler, "_parse_items")
    @patch.object(ConcreteCrawler, "_fetch_detail")
    def test_std_count_from_count_field(self, mock_fetch, mock_parse):
        """std_count 字段优先于解析条目数。"""
        mock_fetch.return_value = "<html>detail</html>"
        mock_parse.return_value = [{"std_code": "GB/T 1.1-2020"}]

        ann = {"pid": "p001", "code": "C001", "title": "公告", "notice_date": "2024-01-15", "std_count": "5"}
        result = self.crawler._process_one_detail(ann, None, self._bump)

        self.assertEqual(result[0]["standard_count"], 5)

    @patch.object(ConcreteCrawler, "_parse_items")
    @patch.object(ConcreteCrawler, "_fetch_detail")
    def test_std_count_fallback_from_parsed_len(self, mock_fetch, mock_parse):
        """std_count 为空时用解析条目数。"""
        mock_fetch.return_value = "<html>detail</html>"
        mock_parse.return_value = [
            {"std_code": "GB/T 1.1-2020"},
            {"std_code": "GB/T 2.2-2020"},
        ]

        ann = {"pid": "p001", "code": "C001", "title": "公告", "notice_date": "2024-01-15", "std_count": ""}
        result = self.crawler._process_one_detail(ann, None, self._bump)

        self.assertEqual(result[0]["standard_count"], 2)


class TestFetchDetailsParallel(unittest.TestCase):
    """_fetch_details_parallel 测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    @patch.object(ConcreteCrawler, "_process_one_detail")
    def test_parallel_processing_aggregates_results(self, mock_process):
        """多公告并行处理，结果汇总。"""
        mock_process.side_effect = lambda ann, ocr, bump: (
            [{"std_code": f"{ann['code']}-item1"}]
        )

        ann_list = [
            {"pid": "p1", "code": "C1"},
            {"pid": "p2", "code": "C2"},
            {"pid": "p3", "code": "C3"},
        ]
        result = self.crawler._fetch_details_parallel(ann_list, None, None)

        self.assertEqual(len(result), 3)

    @patch.object(ConcreteCrawler, "_process_one_detail")
    def test_empty_list_returns_empty(self, mock_process):
        result = self.crawler._fetch_details_parallel([], None, None)
        self.assertEqual(result, [])


class TestFetchAnnouncements(unittest.TestCase):
    """fetch_announcements 一站式方法测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    @patch.object(ConcreteCrawler, "_fetch_details_parallel")
    @patch.object(ConcreteCrawler, "_fetch_list")
    @patch.object(ConcreteCrawler, "_cb_check_frozen")
    @patch.object(ConcreteCrawler, "_cb_record_success")
    def test_success_flow(self, mock_success, mock_check, mock_list, mock_parallel):
        """完整成功流程：列表 -> 详情 -> 返回条目。"""
        mock_list.return_value = [{"pid": "p1", "code": "C1"}]
        mock_parallel.return_value = [{"std_code": "GB/T 1.1-2020"}]

        result = self.crawler.fetch_announcements("2024-01-01", 20)

        mock_check.assert_called_once()
        mock_list.assert_called_once()
        mock_parallel.assert_called_once()
        mock_success.assert_called_once()
        self.assertEqual(len(result), 1)

    @patch.object(ConcreteCrawler, "_cb_check_frozen")
    def test_frozen_raises_and_stops(self, mock_check):
        """冻结中：抛 AdapterFrozenError，不执行后续。"""
        mock_check.side_effect = AdapterFrozenError("test", 300)

        with self.assertRaises(AdapterFrozenError):
            self.crawler.fetch_announcements("2024-01-01")

    @patch.object(ConcreteCrawler, "_fetch_list")
    @patch.object(ConcreteCrawler, "_cb_check_frozen")
    @patch.object(ConcreteCrawler, "_cb_record_success")
    def test_empty_list_returns_empty(self, mock_success, mock_check, mock_list):
        """列表为空时直接返回空。"""
        mock_list.return_value = []

        result = self.crawler.fetch_announcements("2024-01-01")

        self.assertEqual(result, [])
        mock_success.assert_called_once()

    @patch.object(ConcreteCrawler, "_fetch_details_parallel")
    @patch.object(ConcreteCrawler, "_fetch_list")
    @patch.object(ConcreteCrawler, "_cb_check_frozen")
    @patch.object(ConcreteCrawler, "_cb_record_success")
    def test_filter_complete_pids(self, mock_success, mock_check, mock_list, mock_parallel):
        """complete_pids 过滤已完全解析的公告。"""
        mock_list.return_value = [
            {"pid": "p1", "code": "C1"},
            {"pid": "p2", "code": "C2"},
            {"pid": "p3", "code": "C3"},
        ]
        mock_parallel.return_value = [{"std_code": "X"}]
        complete_pids = {"p1", "p3"}

        self.crawler.fetch_announcements("2024-01-01", 20, complete_pids=complete_pids)

        # 只剩 p2 传给 parallel
        call_args = mock_parallel.call_args[0][0]
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["pid"], "p2")

    @patch.object(ConcreteCrawler, "_fetch_details_parallel")
    @patch.object(ConcreteCrawler, "_fetch_list")
    @patch.object(ConcreteCrawler, "_cb_check_frozen")
    @patch.object(ConcreteCrawler, "_cb_record_success")
    def test_all_pids_complete_returns_empty(self, mock_success, mock_check, mock_list, mock_parallel):
        """所有 PID 都已完全解析时，跳过全部。"""
        mock_list.return_value = [
            {"pid": "p1", "code": "C1"},
        ]
        complete_pids = {"p1"}

        result = self.crawler.fetch_announcements("2024-01-01", 20, complete_pids=complete_pids)

        self.assertEqual(result, [])
        mock_parallel.assert_not_called()

    @patch.object(ConcreteCrawler, "_fetch_details_parallel")
    @patch.object(ConcreteCrawler, "_fetch_list")
    @patch.object(ConcreteCrawler, "_cb_check_frozen")
    @patch.object(ConcreteCrawler, "_cb_record_failure")
    def test_parallel_returns_empty_records_failure(self, mock_fail, mock_check, mock_list, mock_parallel):
        """详情解析返回空时记录失败。"""
        mock_list.return_value = [{"pid": "p1", "code": "C1"}]
        mock_parallel.return_value = []

        result = self.crawler.fetch_announcements("2024-01-01")

        self.assertEqual(result, [])
        mock_fail.assert_called_once()


class TestCircuitBreakerConfigProperties(unittest.TestCase):
    """熔断配置属性测试。"""

    def setUp(self):
        self.crawler = ConcreteCrawler()

    def test_cb_threshold_has_default(self):
        self.assertIsInstance(self.crawler._cb_threshold, int)
        self.assertGreater(self.crawler._cb_threshold, 0)

    def test_cb_durations_has_default(self):
        durations = self.crawler._cb_durations
        self.assertIsInstance(durations, list)
        self.assertGreater(len(durations), 0)
        for d in durations:
            self.assertIsInstance(d, int)

    def test_cb_reset_hours_has_default(self):
        self.assertIsInstance(self.crawler._cb_reset_hours, int)
        self.assertGreater(self.crawler._cb_reset_hours, 0)


if __name__ == "__main__":
    unittest.main()
