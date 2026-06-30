# tests/test_manager.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import shutil
import tempfile
import unittest

from pilotstd.manager import StandardManager


class TestStandardManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        # 创建测试用的标准文件
        self.test_file = os.path.join(self.tmp, "GB 19001-2020 质量管理.pdf")
        with open(self.test_file, "w") as f:
            f.write("dummy content")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_scan_directory(self):
        mgr = StandardManager()
        parsed = mgr.scan_directory(self.tmp)
        self.assertGreaterEqual(len(parsed), 1)
        info = parsed[0]
        self.assertEqual(info.logical_code, "GB")
        self.assertEqual(info.number, 19001)
        self.assertEqual(info.year, 2020)

    def test_scan_empty_directory(self):
        empty = tempfile.mkdtemp(prefix="pilotstd_empty_")
        try:
            mgr = StandardManager()
            parsed = mgr.scan_directory(empty)
            self.assertEqual(len(parsed), 0)
        finally:
            shutil.rmtree(empty)

    def test_query_with_mock(self):
        mgr = StandardManager()
        mgr._parsed_results = []  # 直接设置内部状态
        mgr.scan_directory(self.tmp)
        results, stats = mgr.query()
        self.assertEqual(len(results), len(mgr._parsed_results))

    def test_manager_init_defaults(self):
        mgr = StandardManager()
        self.assertIsNotNone(mgr.cfg)
        self.assertIsNotNone(mgr.scanner)
        self.assertIsNotNone(mgr.query_engine)
        self.assertIsNotNone(mgr.download_engine)

    def test_download_after_query(self):
        mgr = StandardManager()
        mgr.scan_directory(self.tmp)
        results, stats = mgr.query()
        tasks, dl_stats = mgr.download(results)
        self.assertIsNotNone(dl_stats)

    def test_organize_no_source_files(self):
        mgr = StandardManager()
        mgr.scan_directory(self.tmp)
        result = mgr.archive_standards()
        self.assertIn("moved", result)
        self.assertIn("failed", result)

    def test_full_pipeline_integration(self):
        """端到端集成测试：scan → query → download → organize 完整流程。"""
        # 在临时目录创建多个测试标准文件
        files = {
            "GB 1.1-2020 标准化工作导则.pdf": "dummy GB",
            "SH 1610-2011 热塑性弹性体.pdf": "dummy SH",
        }
        for fname, content in files.items():
            with open(os.path.join(self.tmp, fname), "w") as f:
                f.write(content)

        mgr = StandardManager()
        # 1. 扫描
        parsed = mgr.scan_directory(self.tmp)
        self.assertGreaterEqual(len(parsed), 2, "扫描至少识别 2 个文件")

        # 2. 查询（实际走网络 → 可能全部失败 → 但不应崩溃）
        results, stats = mgr.query(parsed, force_refresh=False)
        self.assertEqual(len(results), len(parsed))

        # 3. 下载（无网络时结果为 0 是正常行为，验证不崩溃即可）
        tasks, dl_stats = mgr.download(results)
        self.assertIsNotNone(dl_stats)
        self.assertIsNotNone(dl_stats)

        # 4. 归档（文件应被移动或跳过）
        org_result = mgr.archive_standards(parsed)
        self.assertIn("moved", org_result)
        self.assertIn("failed", org_result)

    def test_download_matches_subset_correctly(self):
        """download() 在查询子集场景下通过 _queried_items 正确匹配索引。

        模拟 stress_01 场景：扫描全部（PDF+Word混合），只查询 PDF 子集。
        验证 download() 中 _download_list 的项能通过 _queried_items 正确对应
        到 _query_results 中的结果，而非按 _parsed_results 的全局索引错位匹配。
        """
        from unittest.mock import MagicMock

        from pilotstd.download.models import BatchDownloadStats
        from pilotstd.models import ParsedStdInfo
        from pilotstd.query.models import QueryResult

        mgr = StandardManager()

        # 1. 模拟扫描结果：5个条目（混合 PDF 和 Word，只有部分参与查询）
        items = []
        for i in range(5):
            p = ParsedStdInfo(
                raw_filename=f"test{i}.pdf",
                logical_code="GB",
                number=1000 + i,
                year=2020,
                std_name=f"测试标准{i}",
                source_path=f"C:\\test\\test{i}.pdf",
            )
            items.append(p)
        mgr._parsed_results = items

        # 2. 模拟只查询了索引 0, 2, 4（PDF 子集，跳过 Word 条目）
        subset = [items[0], items[2], items[4]]
        mgr._queried_items = subset

        # 3. 模拟查询结果（与 subset 一一平行：3条结果对应3条查询）
        results = []
        for j, p in enumerate(subset):
            r = QueryResult(standard_number=p.get_full_number())
            if j == 1:  # subset[1] = items[2] 标记为新版本，需要下载
                r.status = "现行"
                r.match_status = "newer"
            else:
                r.status = "现行"
            results.append(r)
        mgr._query_results = results

        # 4. 模拟分类结果：仅 subset[1]（items[2]）需要下载
        mgr._download_list = [subset[1]]

        # _expire_list 须存在（download() 会检查其是否非空）
        mgr._expire_list = []
        mgr._pending_list = []

        # 5. Mock 下载引擎，拦截 download_batch 以验证传入的任务
        mock_engine = MagicMock()
        mock_stats = BatchDownloadStats(success=0, skipped_exists=0, failed=0, errors=0)
        mock_engine.download_batch = MagicMock(return_value=([], mock_stats))
        mgr.download_engine = mock_engine

        # 6. 执行下载
        completed, stats = mgr.download()

        # 7. 验证：下载引擎被调用
        assert mock_engine.download_batch.called, "download_batch 未被调用"

        # 8. 验证传入的任务数量
        tasks = mock_engine.download_batch.call_args[0][0]
        assert len(tasks) == 1, f"预期 1 个下载任务，实际 {len(tasks)}"

        # 9. 关键断言：standard_number 来自正确的 QueryResult
        #    subset[1] 在 _queried_items 中位于索引 1，应匹配 results[1]
        #    无 _queried_items 修复时，会按 _parsed_results 索引 2 错位匹配 results[2]
        assert tasks[0].standard_number == subset[1].get_full_number(), (
            f"索引错位：预期 standard_number = {subset[1].get_full_number()}，实际 {tasks[0].standard_number}"
        )

        # 10. 验证 query_result 是正确的结果对象（而非错位匹配的其他结果）
        assert tasks[0].query_result is results[1], "DownloadTask.query_result 未正确关联到对应的 QueryResult"

    def test_auto_run(self):
        mgr = StandardManager()
        report = mgr.auto_run(self.tmp)
        self.assertIn("scan", report)
        self.assertIn("query_found", report)
        self.assertGreaterEqual(report["scan"], 1)

    def test_mock_full_pipeline_e2e(self):
        """mock 网络层的全管线 E2E：扫描→查询→下载→归档，验证各段衔接无崩溃。"""
        import shutil
        import tempfile
        from unittest.mock import MagicMock

        from pilotstd.download.models import BatchDownloadStats
        from pilotstd.query.models import QueryResult

        tmp = tempfile.mkdtemp()
        try:
            # 创建测试文件，模拟真实 PDF
            pdf_path = os.path.join(tmp, "GB 19001-2020 质量管理体系.pdf")
            with open(pdf_path, "w") as f:
                f.write("%PDF-1.4 dummy pdf content for testing pipeline e2e")

            mgr = StandardManager()

            # Mock query_engine —— 模拟网络查询成功
            qr = QueryResult(standard_number="GB/T 19001-2020")
            qr.standard_name = "质量管理体系"
            qr.status = "现行"
            qr.source_site = "test"
            qr.match_status = "exact"
            qr.is_adopted = False
            mock_qstats = MagicMock()
            mock_qstats.total = 1
            mock_qstats.found = 1
            mock_qstats.downloadable = 1
            mock_qstats.not_found = 0
            mgr.query_engine = MagicMock()
            mgr.query_engine.query_standards.return_value = [qr]

            # Mock download_engine —— 模拟下载成功
            mock_task = MagicMock()
            mock_task.standard_number = "GB/T 19001-2020"
            mock_task.status = MagicMock(value="success")
            mock_task.saved_path = os.path.join(tmp, "GB_T_19001-2020.pdf")
            mock_task.error_message = ""
            mock_task.query_result = qr
            mock_dl = MagicMock()
            mock_dl.download_batch.return_value = (
                [mock_task],
                BatchDownloadStats(success=1, skipped_exists=0, failed=0, errors=0),
            )
            mgr.download_engine = mock_dl

            # 调用 auto_run —— 生产代码的唯一公共入口
            report = mgr.auto_run(tmp)

            # 验证各段均有输出（auto_run 返回的 report 使用描述性 key 名）
            self.assertIn("scan", report)
            self.assertGreaterEqual(report["scan"], 1, "扫描应至少识别 1 个文件")
            # 各段不应抛异常，report 应包含完整 pipeline 结果
            for key in ["scan", "query_found", "download_success", "organize_moved"]:
                self.assertIn(key, report, f"report 应包含 {key} 键（{list(report.keys())}）")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# === Item 2: organize_skipped_dirs 行业代号解析测试 ===

_SEP = os.sep


class TestResolveIndustryInPath:
    """organize_skipped_dirs 路径解析：API → API 美国石油学会 等。
    _resolve_industry_in_path 是静态方法，直接通过类调用，无需实例。"""

    def test_foreign_code_resolved(self):
        """国外标准代号 → 代号+组织名"""
        result = StandardManager._resolve_industry_in_path(f"API{_SEP}过期作废")
        assert result == f"API 美国石油学会{_SEP}过期作废"

    def test_domestic_code_resolved(self):
        """国内标准代号 → 代号+行业名（GB 在 NATIONAL_CODES，需守卫条件覆盖）"""
        result = StandardManager._resolve_industry_in_path(f"GB{_SEP}过期作废")
        assert result == f"GB 国家标准{_SEP}过期作废"

    def test_db_code_resolved(self):
        """地方标准代号 → DB 地方标准/省份"""
        result = StandardManager._resolve_industry_in_path(f"DB11{_SEP}过期作废")
        assert result == f"DB 地方标准{_SEP}北京{_SEP}过期作废"

    def test_already_resolved_unchanged(self):
        """已解析过的目录名原样返回"""
        result = StandardManager._resolve_industry_in_path(f"SH 石油化工{_SEP}过期作废")
        assert result == f"SH 石油化工{_SEP}过期作废"

    def test_non_code_unchanged(self):
        """非行业代号目录名原样返回"""
        result = StandardManager._resolve_industry_in_path(f"其他资料{_SEP}过期作废")
        assert result == f"其他资料{_SEP}过期作废"

    def test_empty_path(self):
        """空路径原样返回"""
        result = StandardManager._resolve_industry_in_path("")
        assert result == ""

    def test_single_component(self):
        """仅行业代号（无子目录）→ 代号+名称"""
        result = StandardManager._resolve_industry_in_path("API")
        assert result == "API 美国石油学会"


# === _auto.py 覆盖 ===


class TestAutoMixin(unittest.TestCase):
    """auto_run / auto_run_stream 管线测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        test_file = os.path.join(self.tmp, "GB 19001-2020.pdf")
        with open(test_file, "w") as f:
            f.write("dummy")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_auto_run_all_stages_complete(self):
        """auto_run 四阶段全走完，report 含全部键且无崩溃。"""
        mgr = StandardManager()
        report = mgr.auto_run(self.tmp)
        for key in ("scan", "query_found", "download_success", "organize_moved"):
            self.assertIn(key, report, f"缺少键 {key}")

    def test_auto_run_stream_short_circuit_empty(self):
        """空目录扫描返回 0 条时 auto_run_stream 提前退出，不崩溃。"""
        empty = tempfile.mkdtemp(prefix="pilotstd_empty_")
        try:
            mgr = StandardManager()
            report = mgr.auto_run_stream(empty)
            self.assertEqual(report["scan"], 0)
        finally:
            shutil.rmtree(empty)


# === _download.py 覆盖 ===


class TestDownloadMixin(unittest.TestCase):
    """download / enqueue_download_wait / download_by_numbers 测试。"""

    def test_download_enqueue_wait_delegates(self):
        """enqueue_download_wait 委托 _pending_svc，不抛异常。"""
        from unittest.mock import MagicMock

        mgr = StandardManager()
        mgr._pending_svc = MagicMock()
        mgr.enqueue_download_wait(MagicMock())
        mgr._pending_svc.enqueue_download_wait.assert_called_once()

    def test_download_by_numbers_delegates(self):
        """download_by_numbers 委托 _scheduled_svc，不抛异常。"""
        from unittest.mock import MagicMock

        mgr = StandardManager()
        mgr._scheduled_svc = MagicMock()
        mgr._scheduled_svc.download_by_numbers.return_value = ([], MagicMock())
        result = mgr.download_by_numbers(["GB/T 1-2020"])
        self.assertIsNotNone(result)


# === _organize.py 覆盖 ===


class TestOrganizeMixin(unittest.TestCase):
    """normalize_files / expire_files / _backfill_std_name 测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.test_file = os.path.join(self.tmp, "GB 19001-2020 质量管理.pdf")
        with open(self.test_file, "w") as f:
            f.write("dummy")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_normalize_files_returns_correct_keys(self):
        """normalize_files 返回列表，每项含 normalized/folder/logical_code。"""
        mgr = StandardManager()
        results = mgr.normalize_files([self.test_file])
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertIn("normalized", item)
        self.assertIn("folder", item)
        self.assertEqual(item["logical_code"], "GB")

    def test_expire_files_no_valid_input(self):
        """非标准文件路径时 expire_files 返回 details 含'无有效文件'。"""
        mgr = StandardManager()
        nonexistent = os.path.join(self.tmp, "no_such_file.pdf")
        result = mgr.expire_files([nonexistent])
        self.assertIn("details", result)
        self.assertIn("无有效文件", result["details"][0])


# === _scan.py 覆盖 ===


class TestScanMixin(unittest.TestCase):
    """scan_directory / scan_and_index / stop_watching 测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        test_file = os.path.join(self.tmp, "GB 19001-2020 质量管理.pdf")
        with open(test_file, "w") as f:
            f.write("dummy")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_scan_directory_skipped_dirs_set(self):
        """scan_directory 后 _last_skipped_dirs 被赋值。"""
        mgr = StandardManager()
        mgr.scan_directory(self.tmp)
        # _last_skipped_dirs 应为 list（即使空）
        self.assertIsNotNone(mgr._last_skipped_dirs)

    def test_stop_watching_noop_when_none(self):
        """_file_watcher 为 None 时 stop_watching 不抛异常。"""
        mgr = StandardManager()
        mgr._file_watcher = None
        try:
            mgr.stop_watching()
        except Exception as e:
            self.fail(f"stop_watching 不应抛异常: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
