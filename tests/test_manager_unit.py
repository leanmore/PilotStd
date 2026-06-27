# tests/test_manager_unit.py
# 管理层单元测试：QueryClassifier 分类逻辑 + PendingService 待确认/下载队列
# 使用 mock 适配器构造已知查询结果，验证分类和待确认逻辑的正确性

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest

import pytest

from pilotstd.core.file_index import FileIndexRepository
from pilotstd.core.file_utils import make_standard_filename
from pilotstd.manager.classifier import QueryClassifier
from pilotstd.manager.pending_service import PendingService
from pilotstd.models import ParsedStdInfo
from pilotstd.pipeline.router import PipelineRouter
from pilotstd.query.models import QueryResult

# ════════════════════════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════════════════════════


def _make_parsed(code, number, year, std_name="测试标准", source_path=""):
    # 用规范文件名确保 router 正确识别 organize
    if not source_path:
        fname = make_standard_filename(code, number, year, std_name)
        source_path = f"/tmp/{fname}"
    return ParsedStdInfo(
        raw_filename=f"{code} {number}-{year}.pdf",
        logical_code=code,
        number=number,
        year=year,
        std_name=std_name,
        source_path=source_path,
    )


def _make_result(
    std_num,
    std_name,
    status="现行",
    match_status="exact",
    is_adopted=False,
    replaces="",
    source_site="std_gov",
):
    return QueryResult(
        standard_number=std_num,
        standard_name=std_name,
        status=status,
        match_status=match_status,
        is_adopted=is_adopted,
        replaces=replaces,
        source_site=source_site,
    )


# ════════════════════════════════════════════════════════════════
# 1. QueryClassifier — 查询后分类验证
# ════════════════════════════════════════════════════════════════


class TestQueryClassifier(unittest.TestCase):
    """验证 classifier.classify() 对各类标准的分类结果。"""

    def setUp(self):
        self.router = PipelineRouter()
        self.classifier = QueryClassifier(
            router=self.router,
            query_adapters=[],
            quota_tracker=None,
            query_engine=None,
        )

    def _classify(self, parsed_list, results):
        download: list = []
        expire: list = []
        pending: list = []
        self.classifier.classify(results, parsed_list, download, expire, pending)
        return download, expire, pending

    # ── GB 标准 — 现行 ────────────────────────────────────

    def test_gb_active_exact_goes_to_organize(self):
        """GB 现行 + exact → next_action=archive（文件名正确直接归档）"""
        p = _make_parsed("GB/T", 19001, 2016, "质量管理体系")  # 自动生成规范文件名
        r = _make_result("GB/T 19001-2016", "质量管理体系")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "archive")
        self.assertEqual(len(download), 0)
        self.assertEqual(len(pending), 0)

    def test_gb_active_normalized_filename(self):
        """GB 现行但文件名不规范 → next_action=normalize"""
        p = _make_parsed("GB/T", 19001, 2016, "质量管理体系", source_path="/tmp/wrong_name.pdf")
        r = _make_result("GB/T 19001-2016", "质量管理体系")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "normalize")

    # ── GB 标准 — newer（远程有更新版） ─────────────────

    def test_gb_newer_goes_to_download(self):
        """GB newer + 非采标 → pending（规则0: 非exact统一pending）"""
        p = _make_parsed("GB/T", 19001, 2016, "质量管理体系")
        r = _make_result("GB/T 19001-2020", "质量管理体系", match_status="newer")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "pending")
        self.assertIn(p, pending)

    def test_gb_newer_adopted_goes_to_pending(self):
        """GB newer + 采标 → pending（不可下载）"""
        p = _make_parsed("GB/T", 19001, 2016, "质量管理体系")
        r = _make_result("GB/T 19001-2020", "质量管理体系", match_status="newer", is_adopted=True)
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "pending")
        self.assertIn(p, pending)

    # ── GB 标准 — 废止 ───────────────────────────────────

    def test_gb_repealed_with_replaces_goes_to_download(self):
        """GB 废止 + 有替代 + 非采标 → download"""
        p = _make_parsed("GB", 150, 1998, "钢制压力容器")
        r = _make_result("GB 150-1998", "钢制压力容器", status="废止", replaces="GB/T 150.1-2011")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "download")
        self.assertIn(p, download)

    def test_gb_repealed_no_replaces_goes_to_expire(self):
        """GB 废止 + 无替代 → expire"""
        p = _make_parsed("GB", 12345, 1990, "旧标准")
        r = _make_result("GB 12345-1990", "旧标准", status="废止", replaces="")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "expire")
        self.assertIn(p, expire)

    # ── 非 GB 标准 — 不路由到 download ───────────────────

    def test_industry_active_goes_to_organize(self):
        """行业标准 现行 + exact → archive（可归档，不可下载）"""
        p = _make_parsed("SH/T", 1610, 2011, "苯乙烯-丁二烯橡胶")
        r = _make_result("SH/T 1610-2011", "苯乙烯-丁二烯橡胶", source_site="hbba")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "archive")
        self.assertEqual(len(download), 0)

    def test_foreign_not_found_goes_to_pending(self):
        """国外标准 未查到 → pending"""
        p = _make_parsed("API", 610, 2004, "Centrifugal Pumps")
        r = QueryResult(
            standard_number="API 610-2004",
            status="",
            match_status="",
            error_message="所有来源均未找到",
            source_site="njbz365",
        )
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "pending")

    def test_foreign_active_goes_to_organize(self):
        """国外标准 现行 + exact → archive（不可下载）"""
        p = _make_parsed("API", 610, 2004, "Centrifugal Pumps")
        r = _make_result("API 610-2004", "Centrifugal Pumps", source_site="njbz365")
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "archive")
        self.assertEqual(len(download), 0)

    # ── 待确认 ───────────────────────────────────────────

    def test_uncertain_status_goes_to_pending(self):
        """查询结果 status='待确认' → pending"""
        p = _make_parsed("SH/T", 9999, 2020, "未知标准")
        r = _make_result(
            "SH/T 9999-2020",
            "未知标准",
            status="待确认",
            match_status="related",
            source_site="hbba",
        )
        download, expire, pending = self._classify([p], [r])
        self.assertEqual(p.next_action, "pending")

    # ── found_source_site 回写 ────────────────────────────

    def test_found_source_site_is_populated(self):
        """分类后 parsed.found_source_site 被正确回写"""
        p = _make_parsed(
            "GB/T",
            19001,
            2016,
            "质量管理体系",
            source_path="/tmp/GB_T 19001-2016 质量管理体系.pdf",
        )
        r = _make_result("GB/T 19001-2016", "质量管理体系", source_site="std_gov")
        self._classify([p], [r])
        self.assertEqual(p.found_source_site, "std_gov")

    # ── 新标准本地已有 → 跳过下载 ────────────────────────

    def test_newer_exists_locally_skips_download(self):
        """同代号同序号 + 另一个 exact 项已存在 → newer 项走 pending（规则0）"""
        p_old = _make_parsed("GB/T", 19001, 2016, "质量管理体系")
        p_new = _make_parsed("GB/T", 19001, 2020, "质量管理体系")
        r_old = _make_result("GB/T 19001-2020", "质量管理体系", match_status="newer")
        r_new = _make_result("GB/T 19001-2020", "质量管理体系", match_status="exact")
        download, expire, pending = self._classify([p_old, p_new], [r_old, r_new])
        # p_old: newer → pending（规则0: 非exact统一pending）
        self.assertEqual(p_old.next_action, "pending")
        # p_new: exact → archive
        self.assertEqual(p_new.next_action, "archive")
        self.assertEqual(len(download), 0)


# ════════════════════════════════════════════════════════════════
# 2. PendingService — 待确认清单 + 下载等待队列 + 本地缓存查询
# ════════════════════════════════════════════════════════════════


class TestPendingService(unittest.TestCase):
    """验证 PendingService 的 CRUD 操作和本地缓存查询。"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        # standard_info_cache 由 CacheRepository 惰性创建，PendingService 间接使用
        shared_db.execute("""
            CREATE TABLE IF NOT EXISTS standard_info_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_number TEXT NOT NULL, source_site TEXT NOT NULL,
                result_json TEXT NOT NULL, cached_at TEXT,
                source TEXT NOT NULL DEFAULT 'network',
                status_history TEXT NOT NULL DEFAULT '')
        """)
        self.file_index = FileIndexRepository(shared_db)
        self.svc = PendingService(shared_db, self.file_index)

    # ── record_pending ────────────────────────────────────

    def test_record_pending_writes_to_db(self):
        p = _make_parsed("SH/T", 9999, 2020, "未知标准")
        p.effect_status = "待确认"
        p.match_status = "related"
        self.svc.record_pending([p])
        items = self.svc.get_pending_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["standard_number"], "SH/T 9999-2020")

    def test_record_pending_skips_duplicate(self):
        p = _make_parsed("SH/T", 9999, 2020)
        self.svc.record_pending([p])
        self.svc.record_pending([p])  # 重复写入
        items = self.svc.get_pending_items()
        self.assertEqual(len(items), 1)  # 不应重复

    # ── resolve_pending ───────────────────────────────────

    def test_resolve_pending_updates_status(self):
        p = _make_parsed("NB/T", 47013, 2015)
        self.svc.record_pending([p])
        self.svc.resolve_pending([p], "discarded")
        items = self.svc.get_pending_items()
        self.assertEqual(len(items), 0)  # 已处理的不在 pending 列表中

    def test_get_pending_returns_only_pending_status(self):
        p1 = _make_parsed("NB/T", 47013, 2015)
        p2 = _make_parsed("HG/T", 20592, 2009)
        self.svc.record_pending([p1, p2])
        self.svc.resolve_pending([p1], "confirmed")  # 只处理 p1
        items = self.svc.get_pending_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["standard_number"], "HG/T 20592-2009")

    # ── enqueue_download_wait ─────────────────────────────

    def test_enqueue_download_wait(self):
        p = _make_parsed("GB/T", 3836, 2024)
        p.found_publish_date = "2024-06-01"
        self.svc.enqueue_download_wait(p)
        due = self.svc.get_due_downloads()
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["standard_number"], "GB/T 3836-2024")

    def test_enqueue_download_wait_skips_no_publish_date(self):
        p = _make_parsed("GB/T", 3836, 2024)
        p.found_publish_date = ""  # 无发布日期
        self.svc.enqueue_download_wait(p)
        due = self.svc.get_due_downloads()
        self.assertEqual(len(due), 0)  # 未写入

    def test_enqueue_download_wait_skips_duplicate(self):
        p = _make_parsed("GB/T", 3836, 2024)
        p.found_publish_date = "2024-06-01"
        self.svc.enqueue_download_wait(p)
        self.svc.enqueue_download_wait(p)
        due = self.svc.get_due_downloads()
        self.assertEqual(len(due), 1)

    def test_get_due_downloads_filters_by_date(self):
        p = _make_parsed("GB/T", 99999, 2099)
        p.found_publish_date = "2099-01-01"  # 未来
        self.svc.enqueue_download_wait(p)
        due = self.svc.get_due_downloads()
        self.assertEqual(len(due), 0)  # 未到公开期

    def test_remove_download_queue(self):
        p = _make_parsed("GB/T", 3836, 2024)
        p.found_publish_date = "2024-06-01"
        self.svc.enqueue_download_wait(p)
        self.svc.remove_download_queue("GB/T 3836-2024")
        due = self.svc.get_due_downloads()
        self.assertEqual(len(due), 0)

    # ── query_local_cache ─────────────────────────────────

    def test_query_local_cache_returns_results(self):
        import json

        self.db.execute(
            "INSERT INTO standard_info_cache (standard_number, source_site, "
            "result_json, cached_at) VALUES (?, 'std_gov', ?, datetime('now'))",
            (
                "GB/T 19001-2016",
                json.dumps(
                    {
                        "standard_name": "质量管理体系",
                        "status": "现行",
                        "match_status": "exact",
                        "is_adopted": False,
                        "hcno": "12345",
                        "replaces": "",
                        "publish_date": "2016-12-30",
                        "implementation_date": "2017-07-01",
                    }
                ),
            ),
        )
        p = _make_parsed("GB/T", 19001, 2016)
        results = self.svc.query_local_cache([p])
        self.assertEqual(len(results), 1)
        _, result = results[0]
        self.assertEqual(result.standard_name, "质量管理体系")
        self.assertEqual(result.source_site, "local_db")

    def test_query_local_cache_not_found(self):
        p = _make_parsed("API", 610, 2004)
        results = self.svc.query_local_cache([p])
        self.assertEqual(len(results), 1)
        _, result = results[0]
        self.assertIn("未找到", result.error_message or "")

    def test_query_local_cache_falls_back_to_announcement(self):
        import json

        self.db.execute(
            "INSERT INTO announcement_match (standard_number, source_site, "
            "result_json, cached_at) VALUES (?, 'announcement', ?, datetime('now'))",
            (
                "SH/T 1610-2011",
                json.dumps(
                    {
                        "standard_name": "苯乙烯-丁二烯橡胶",
                        "status": "现行",
                        "match_status": "exact",
                        "is_adopted": False,
                    }
                ),
            ),
        )
        p = _make_parsed("SH/T", 1610, 2011)
        results = self.svc.query_local_cache([p])
        _, result = results[0]
        self.assertEqual(result.standard_name, "苯乙烯-丁二烯橡胶")
        self.assertIn("公告", result.source_site)


if __name__ == "__main__":
    unittest.main()
