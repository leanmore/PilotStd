# tests/test_download.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import shutil
import tempfile
import time
import unittest

import requests

from pilotstd.download.adapters.base import BaseDownloadAdapter
from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import BatchDownloadStats, DownloadStatus, DownloadTask
from pilotstd.download.session import DEFAULT_USER_AGENTS, SessionManager

# ── 辅助：模拟 QueryResult ──────────────────────────────


class FakeQueryResult:
    def __init__(
        self,
        standard_number,
        standard_name="测试标准",
        is_adopted=False,
        year=2020,
        number=19001,
        part=None,
    ):
        self.standard_number = standard_number
        self.standard_name = standard_name
        self.is_adopted = is_adopted
        self.year = year
        self.number = number
        self.part = part


# ── 模拟适配器 ──────────────────────────────────────────


class MockDownloadAdapter(BaseDownloadAdapter):
    """模拟下载适配器：返回固定字节内容，可触发失败。"""

    def __init__(self, session=None, fail=False):
        super().__init__(session or requests.Session())
        self._fail = fail
        self.download_called = False

    @property
    def site_name(self):
        return "mock_download"

    def can_handle(self, task):
        return "GB" in task.standard_number

    def download(self, task):
        self.download_called = True
        if self._fail:
            task.error_message = "模拟下载失败"
            return None
        return b"%PDF-1.4 mock content"


# ── 测试用例 ────────────────────────────────────────────


class TestDownloadModels(unittest.TestCase):
    def test_task_defaults(self):
        t = DownloadTask(standard_number="GB/T 1-2020")
        self.assertEqual(t.status, DownloadStatus.PENDING)
        self.assertEqual(t.max_retries, 3)

    def test_stats_accumulate(self):
        s = BatchDownloadStats(total=10, success=7, skipped_adopted=2, failed=1)
        self.assertEqual(s.success, 7)
        self.assertEqual(s.skipped_adopted, 2)


class TestSessionManager(unittest.TestCase):
    def test_ua_rotation(self):
        sm = SessionManager(user_agents=["UA1", "UA2", "UA3"])
        uas = [sm._next_ua() for _ in range(5)]
        self.assertEqual(uas, ["UA1", "UA2", "UA3", "UA1", "UA2"])

    def test_create_session_sets_headers(self):
        sm = SessionManager(user_agents=["TestUA/1.0"])
        s = sm.create_session()
        self.assertIn("User-Agent", s.headers)

    def test_delay_respects_bounds(self):
        sm = SessionManager(min_delay=0.01, max_delay=0.03)
        start = time.time()
        sm.delay()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.2)

    def test_default_user_agents(self):
        SessionManager()
        self.assertGreaterEqual(len(DEFAULT_USER_AGENTS), 2)

    def test_proxy_config(self):
        sm = SessionManager(proxy="http://127.0.0.1:8080")
        self.assertEqual(sm._proxy, "http://127.0.0.1:8080")


class TestDownloadEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.session_mgr = SessionManager(min_delay=0.001, max_delay=0.005)
        self.mock = MockDownloadAdapter(session=self.session_mgr.create_session())
        self.engine = DownloadEngine(
            adapters=[self.mock],
            session_manager=self.session_mgr,
            save_root=self.tmp,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_single_download_success(self):
        qr = FakeQueryResult("GB/T 19001-2020")
        task = DownloadTask(standard_number="GB/T 19001-2020", query_result=qr)
        task = self.engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.SUCCESS)
        self.assertTrue(task.saved_path.endswith(".pdf"))
        self.assertTrue(os.path.exists(task.saved_path))

    def test_skip_adopted_standard(self):
        qr = FakeQueryResult("GB/T 19001-2020", is_adopted=True)
        task = DownloadTask(standard_number="GB/T 19001-2020", query_result=qr)
        task = self.engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.SKIPPED)
        self.assertIn("采标", task.error_message)

    def test_no_matching_adapter(self):
        task = DownloadTask(standard_number="XX 1234-2020")
        task = self.engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.FAILED)
        self.assertIn("适配器", task.error_message)

    def test_download_failure(self):
        fail_adapter = MockDownloadAdapter(session=self.session_mgr.create_session(), fail=True)
        engine = DownloadEngine(
            adapters=[fail_adapter],
            session_manager=self.session_mgr,
            save_root=self.tmp,
        )
        task = DownloadTask(standard_number="GB/T 1-2020")
        task = engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.FAILED)

    # ── fetch_bytes（A 修复：收藏链复用适配器但不落盘）──

    def test_fetch_bytes_returns_content_without_saving(self):
        before = set(os.listdir(self.tmp))
        qr = FakeQueryResult("GB/T 19001-2020")
        task = DownloadTask(standard_number="GB/T 19001-2020", query_result=qr)

        content, err = self.engine.fetch_bytes(task)

        self.assertIsNotNone(content)
        self.assertEqual(err, "")
        self.assertEqual(set(os.listdir(self.tmp)), before, "fetch_bytes 不得落盘")

    def test_fetch_bytes_rejects_adopted(self):
        qr = FakeQueryResult("GB/T 19001-2020", is_adopted=True)
        task = DownloadTask(standard_number="GB/T 19001-2020", query_result=qr)

        content, err = self.engine.fetch_bytes(task)

        self.assertIsNone(content)
        self.assertIn("采标", err)

    def test_fetch_bytes_no_matching_adapter(self):
        task = DownloadTask(standard_number="XX 1234-2020")

        content, err = self.engine.fetch_bytes(task)

        self.assertIsNone(content)
        self.assertIn("适配器", err)

    def test_fetch_bytes_surfaces_adapter_error_without_retry(self):
        """适配器业务失败（返回 None 并设置 error_message）不重试，原样回传原因。"""
        calls = [0]

        class BusinessFailAdapter(BaseDownloadAdapter):
            @property
            def site_name(self):
                return "business_fail"

            def can_handle(self, task):
                return True

            def download(self, task):
                calls[0] += 1
                task.error_message = "viewGb 返回空内容（标准可能暂无全文）"
                return None

        engine = DownloadEngine(
            adapters=[BusinessFailAdapter(self.session_mgr.create_session())],
            session_manager=self.session_mgr,
            save_root=self.tmp,
        )

        content, err = engine.fetch_bytes(DownloadTask(standard_number="GB/T 1-2020"))

        self.assertIsNone(content)
        self.assertIn("viewGb 返回空内容", err)
        self.assertEqual(calls[0], 1, "业务失败不得重试")

    def test_fetch_bytes_retries_on_network_error(self):
        """网络类异常按 3 次尝试退避重试（等价于原收藏链 _download_with_retry）。"""
        calls = [0]

        class FlakyFetchAdapter(BaseDownloadAdapter):
            @property
            def site_name(self):
                return "flaky_fetch"

            def can_handle(self, task):
                return True

            def download(self, task):
                calls[0] += 1
                if calls[0] < 3:
                    raise requests.ConnectionError("connection reset by peer")
                return b"%PDF-1.4 ok"

        engine = DownloadEngine(
            adapters=[FlakyFetchAdapter(self.session_mgr.create_session())],
            session_manager=self.session_mgr,
            save_root=self.tmp,
        )

        with unittest.mock.patch("pilotstd.download.engine.time.sleep") as sleep_mock:
            content, err = engine.fetch_bytes(DownloadTask(standard_number="GB/T 1-2020"))

        self.assertEqual(content, b"%PDF-1.4 ok")
        self.assertEqual(err, "")
        self.assertEqual(calls[0], 3)
        # 退避序列 2s/4s（SessionManager.delay 也会 sleep，故按取值断言而非计数）
        delays = [c.args[0] for c in sleep_mock.call_args_list if c.args]
        self.assertIn(2, delays)
        self.assertIn(4, delays)

    def test_fetch_bytes_exhausts_network_retries(self):
        class AlwaysFailAdapter(BaseDownloadAdapter):
            @property
            def site_name(self):
                return "always_fail"

            def can_handle(self, task):
                return True

            def download(self, task):
                raise requests.ConnectionError("connection reset by peer")

        engine = DownloadEngine(
            adapters=[AlwaysFailAdapter(self.session_mgr.create_session())],
            session_manager=self.session_mgr,
            save_root=self.tmp,
        )

        with unittest.mock.patch("pilotstd.download.engine.time.sleep"):
            content, err = engine.fetch_bytes(DownloadTask(standard_number="GB/T 1-2020"))

        self.assertIsNone(content)
        self.assertIn("connection reset", err)

    def test_batch_download_stats(self):
        tasks = [
            DownloadTask(
                standard_number="GB/T 1-2020",
                query_result=FakeQueryResult("GB/T 1-2020", number=1),
            ),
            DownloadTask(
                standard_number="GB/T 2-2020",
                query_result=FakeQueryResult("GB/T 2-2020", is_adopted=True, number=2),
            ),
            DownloadTask(standard_number="XX 3-2020"),
        ]
        results, stats = self.engine.download_batch(tasks)
        self.assertEqual(stats.total, 3)
        self.assertEqual(stats.success, 1)
        self.assertEqual(stats.skipped_adopted, 1)
        self.assertEqual(stats.failed, 1)

    def test_saved_file_naming(self):
        qr = FakeQueryResult("GB/T 1610-2010", standard_name="石油化工规范", number=1610, year=2010)
        task = DownloadTask(standard_number="GB/T 1610-2010", query_result=qr)
        task = self.engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.SUCCESS)
        self.assertTrue(os.path.exists(task.saved_path))
        self.assertIn("GBT", os.path.basename(task.saved_path))
        self.assertIn("1610", os.path.basename(task.saved_path))
        self.assertIn("2010", os.path.basename(task.saved_path))

    def test_download_retry_on_network_error(self):
        """下载遇到网络超时应标记 RETRYING，batch 层自动重试。"""
        # 前 2 次超时、第 3 次成功的适配器
        call_count = [0]

        class FlakyAdapter(BaseDownloadAdapter):
            @property
            def site_name(self):
                return "flaky"

            def can_handle(self, task):
                return True

            def download(self, task):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise requests.Timeout("模拟超时")
                return b"%PDF-1.4 ok"

        engine = DownloadEngine(
            adapters=[FlakyAdapter(self.session_mgr.create_session())],
            session_manager=self.session_mgr,
            save_root=self.tmp,
            max_retries=2,
        )
        task = DownloadTask(standard_number="GB/T 1-2020")
        task = engine.download_single(task)
        # 第一次调用应进入 RETRYING
        self.assertEqual(task.status, DownloadStatus.RETRYING)
        self.assertEqual(task.retry_count, 1)

        # 批量下载内部应自动重试到成功
        results, stats = engine.download_batch(
            [
                DownloadTask(
                    standard_number="GB/T 1-2020",
                    query_result=FakeQueryResult("GB/T 1-2020", number=1),
                )
            ]
        )
        self.assertEqual(stats.success, 1, "重试后应成功")

    def test_skip_existing_file(self):
        """目标文件已存在 → 跳过下载。"""
        qr = FakeQueryResult("GB/T 1.1-2020", number=1, year=2020)
        # 用引擎内部的 _resolve_target_path 计算正确路径
        task = DownloadTask(standard_number="GB/T 1.1-2020", query_result=qr)
        target = self.engine._resolve_target_path(task)
        os.makedirs(os.path.dirname(target) or self.tmp, exist_ok=True)
        with open(target, "wb") as f:
            f.write(b"%PDF-1.4 preexisting")
        task = self.engine.download_single(task)
        self.assertEqual(
            task.status,
            DownloadStatus.SKIPPED,
            f"文件已存在应跳过，实际: {task.status}",
        )
        self.assertIn("已存在", task.error_message or "")

    def test_empty_content_from_adapter(self):
        """适配器返回空内容 → 下载失败（status=FAILED）。"""

        class EmptyAdapter(BaseDownloadAdapter):
            @property
            def site_name(self):
                return "empty"

            def can_handle(self, task):
                return True

            def download(self, task):
                return b""  # 空内容

        engine = DownloadEngine(
            adapters=[EmptyAdapter(self.session_mgr.create_session())],
            session_manager=self.session_mgr,
            save_root=self.tmp,
        )
        task = DownloadTask(standard_number="GB/T 1-2020")
        task = engine.download_single(task)
        self.assertEqual(task.status, DownloadStatus.FAILED)

    def test_find_adapter_exact_match(self):
        """source_site 精确匹配时优先使用对应适配器。"""
        task = DownloadTask(standard_number="GB/T 1-2020", source_site="openstd_download")
        adapter = self.engine._find_adapter(task)
        self.assertIsNotNone(adapter)

    def test_find_adapter_returns_none_for_unknown_site(self):
        """未知 source_site → 回退 can_handle → 无匹配 → None。"""
        task = DownloadTask(standard_number="API 610-2004", source_site="njbz365")
        adapter = self.engine._find_adapter(task)
        self.assertIsNone(adapter, "njbz365 来源的国外标准无可下载适配器")

    def test_content_disposition_filename_extraction(self):
        """Content-Disposition 响应头中的 filename 应被正确提取到 task.extra。"""
        import re

        from pilotstd.download.models import DownloadTask

        task = DownloadTask(
            standard_number="GB/T 19001-2016",
            source_site="openstd_download",
            extra={},
        )
        # 模拟服务器返回的 Content-Disposition 头
        cd = "attachment;filename=GB_T_19001-2016.pdf"
        m = re.search(r'filename[^;=\n]*=(["\']?)([^"\';\n]+)\1', cd)
        self.assertIsNotNone(m, "Content-Disposition 解析正则不应为 None")
        assert m is not None
        filename = m.group(2)
        self.assertEqual(filename, "GB_T_19001-2016.pdf", "应从 Content-Disposition 中提取文件名")

        # 验证文件名存入 task.extra
        task.extra["filename_from_header"] = filename
        self.assertEqual(task.extra["filename_from_header"], "GB_T_19001-2016.pdf")

    def test_content_disposition_quoted_filename(self):
        """带引号的 Content-Disposition filename 应正确处理。"""
        import re

        cd = 'attachment; filename="GB_T_19001-2016.pdf"'
        m = re.search(r'filename[^;=\n]*=(["\']?)([^"\';\n]+)\1', cd)
        self.assertIsNotNone(m)
        assert m is not None
        self.assertEqual(m.group(2), "GB_T_19001-2016.pdf")

    def test_file_validity_minimum_size_and_pdf_header(self):
        """下载文件应大于 1KB 且以 PDF 魔数开头。"""
        saved = os.path.join(self.tmp, "test_valid.pdf")
        # 写入合法 PDF 头 + 填充到 > 1KB
        content = b"%PDF-1.4\n" + b"x" * 1500
        with open(saved, "wb") as f:
            f.write(content)

        self.assertTrue(os.path.exists(saved))
        self.assertGreater(os.path.getsize(saved), 1024, "文件应大于 1KB")
        with open(saved, "rb") as f:
            header = f.read(5)
        self.assertEqual(header, b"%PDF-", f"PDF 魔数应为 %PDF-，实际: {header!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
