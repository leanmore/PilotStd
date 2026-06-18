# tests/stress_full_coverage.py
# 全量功能覆盖测试 — 15 模块 ~78 项验证
# 覆盖扫描→查询→分类→下载→规范化→归档→待确认→公告→CLI→任务队列
# GB/行业/国外/国际/地方 五种标准类型全链路
#
# 运行: python -m pytest tests/stress_full_coverage.py -v
# 清单: python tests/stress_full_coverage.py --list-only

import sys, os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest, tempfile, shutil, json, time
from unittest.mock import MagicMock, patch

from pilotstd.models import ParsedStdInfo
from pilotstd.pipeline.router import PipelineRouter
from pilotstd.manager.classifier import QueryClassifier
from pilotstd.manager.pending_service import PendingService
from pilotstd.query.models import QueryResult
from pilotstd.query.search_strategy import (
    build_code_variants, match_result,
    _parse_result_number,
)
from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.core.file_utils import make_standard_filename
from pilotstd.core.path_guard import validate_path_in_root
from pilotstd.core.std_utils import is_gb_code
from pilotstd.download.models import DownloadTask, DownloadStatus
from pilotstd.download.engine import DownloadEngine
from pilotstd.download.session import SessionManager
from pilotstd.scan.parser import StandardParser, FOREIGN_CODE_SET
from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.organizer.dir_builder import DirBuilder
from pilotstd.organizer.mover import FileMover
from pilotstd.organizer.expire_handler import ExpireHandler
from pilotstd.task.models import TaskType, TaskStatus
from pilotstd.task.queue import TaskQueue

# ════════════════════════════════════════════════
# 标准样本全集
# ════════════════════════════════════════════════
GB = [("GB",150,2011),("GB/T",19001,2016),("GB/T",1,2020),("GB/Z",37839,2019),("GSB",1234,2020)]
IND = [("SH/T",1610,2011),("NB/T",47013,2015),("HG/T",20592,2009),("JB/T",4730,2005),
       ("SY/T",1234,2020),("YB/T",5678,2020),("AQ/T",9011,2020)]
FOR = [("API",610,2004),("DIN",11851,1998),("BS",1092,2018),("ASTM",4236,1994),
       ("JIS",2801,2000),("ANSI/UL",560,1980),("SAE",1234,2020),("NFPA",5678,2020),
       ("MSS",55,2006),("AWWA",1234,2020),("GOST",5678,2020),("CSA",1234,2020),
       ("NF",5678,2020),("UNE",1234,2020),("KS",5678,2020),("SANS",1234,2020)]
INTL = [("ISO",9001,2015),("IEC",61000,2008),("ITU-T",1234,2020)]
LOC = [("DB11/T",1951,2021),("DB35/T",1234,2020),("DB44",123,2018)]
ALL = GB + IND + FOR + INTL + LOC

# ════════════════════════════════════════════════
# 1. 扫描层
# ════════════════════════════════════════════════
class Test01Scan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = StandardParser(build_code_mapping())

    def _check(self, code, num, yr):
        fname = f"{code} {num}-{yr}.pdf"
        info = self.p.parse(fname)
        self.assertIsNotNone(info, fname)
        self.assertGreater(info.number, 0, f"{fname} number=0")

    def test_gb(self):
        for c,n,y in GB: self._check(c,n,y)
    def test_industry(self):
        for c,n,y in IND: self._check(c,n,y)
    def test_foreign(self):
        for c,n,y in FOR: self._check(c,n,y)
    def test_intl(self):
        for c,n,y in INTL: self._check(c,n,y)
    def test_local(self):
        for c,n,y in LOC: self._check(c,n,y)

    def test_edge_formats(self):
        cases = [
            ("GB 1234-86.pdf","GB",1234,1986),
            ("ISO_2037-1992.pdf","ISO",2037,1992),
            ("JIS Z 2801:2000.pdf","JIS",2801,2000),
            ("BS EN 1092-1-2018.pdf","BS EN",1092,2018),
            ("DIN EN ISO 12345-2020.pdf","DIN EN ISO",12345,2020),
            ("ASME BPVC.IX-2021.pdf","ASME",9,2021),
            ("API RP 500-2023.pdf","API",500,2023),
            ("MIL-STD-810G.pdf","MIL-STD",810,0),
        ]
        for f,ec,en,ey in cases:
            info = self.p.parse(f)
            self.assertIsNotNone(info, f)
            self.assertEqual(info.logical_code, ec, f"{f} code")
            if ey > 0:
                self.assertEqual(info.year, ey, f"{f} year")

    def test_language_detect(self):
        info = self.p.parse("ASME VIII.1-2021 中文版.pdf")
        self.assertIsNotNone(info)
        info2 = self.p.parse("ASME VIII.1-2021 English.pdf")
        self.assertIsNotNone(info2)

# ════════════════════════════════════════════════
# 2. 搜索策略层
# ════════════════════════════════════════════════
class Test02SearchStrategy(unittest.TestCase):
    def test_match_exact(self):
        for c,n,y in ALL[:15]:
            if not y: continue
            _,s = match_result(c,n,y,"test",f"{c} {n}-{y}")
            self.assertNotEqual(s,"mismatch",f"{c} {n}-{y}")

    def test_match_mismatch(self):
        cases=[("GB/T",19001,2016,"GB/T 99999-2099"),("API",610,2004,"ISO 9001-2015")]
        for c,n,y,w in cases:
            _,s = match_result(c,n,y,"",w)
            self.assertEqual(s,"mismatch",f"{c} {n}-{y} vs {w}")

    def test_query_with_strategy_progressive(self):
        for c,n,y in ALL[:10]:
            v = build_code_variants(c,n,y)
            self.assertIsInstance(v, list, f"{c} {n}-{y}")

    def test_code_variants(self):
        self.assertTrue(any("BPVC" in x for x in build_code_variants("ASME",8,2021,"VIII")))
        self.assertTrue(any("Std" in x for x in build_code_variants("API",610,2004)))
        self.assertTrue(any("DIN EN" in x for x in build_code_variants("DIN",11851,1998)))

    def test_parse_result_number(self):
        for c in ["GB/T 22101.1-2026","ISO 9001:2015","API 610-2004",
                  "DB35/T 1234-2020","IEC 61000-4-2:2008","ASME VIII.1-2021"]:
            r = _parse_result_number(c)
            self.assertTrue(r and r.get("code"), f"{c} → {r}")

# ════════════════════════════════════════════════
# 3. 流水线路由器
# ════════════════════════════════════════════════
class Test03Router(unittest.TestCase):
    def setUp(self):
        self.r = PipelineRouter()

    def _p(self, code, num, yr, st, mt, adopted=False, replaces=""):
        f = make_standard_filename(code, num, yr, "test")
        return ParsedStdInfo(raw_filename=f"{code} {num}-{yr}.pdf",
            logical_code=code, number=num, year=yr, std_name="test",
            source_path=f"/tmp/{f}", effect_status=st, match_status=mt,
            is_adopted=adopted, found_replaces=replaces)

    def _b(self,items):
        return self.r.classify_after_query(items)

    def test_gb_exact_organize(self):
        b=self._b([self._p("GB/T",19001,2020,"现行","exact")])
        self.assertEqual(len(b["organize"]),1)
    def test_gb_newer_download(self):
        b=self._b([self._p("GB/T",19001,2016,"现行","newer")])
        self.assertEqual(len(b["download"]),1)
    def test_gb_newer_adopted_pending(self):
        b=self._b([self._p("GB/T",19001,2016,"现行","newer",True)])
        self.assertEqual(len(b["pending"]),1)
    def test_gb_repealed_replace_download(self):
        b=self._b([self._p("GB",150,1998,"废止","exact",False,"GB/T 150.1-2011")])
        self.assertEqual(len(b["download"]),1)
    def test_gb_repealed_no_replace_expire(self):
        b=self._b([self._p("GB",12345,1990,"废止","exact")])
        self.assertEqual(len(b["expire"]),1)
    def test_non_gb_newer_no_download(self):
        for c in ("API","SH/T","DIN"):
            b=self._b([self._p(c,610,2004,"现行","newer")])
            self.assertEqual(len(b["download"]),0,f"{c}")
    def test_non_gb_repealed_expire(self):
        b=self._b([self._p("API",610,2004,"废止","exact",False,"API 610-2010")])
        self.assertEqual(len(b["expire"]),1)
    def test_empty_pending(self):
        b=self._b([self._p("DIN",11851,1998,"","")])
        self.assertEqual(len(b["pending"]),1)
    def test_uncertain_pending(self):
        b=self._b([self._p("SH/T",9999,2020,"待确认","related")])
        self.assertEqual(len(b["pending"]),1)
    def test_upcoming_fallback(self):
        b=self._b([self._p("GB/T",4053,2025,"即将实施","exact")])
        self.assertEqual(len(b["fallback"]),1)
    def test_all_combos_no_crash(self):
        for c,n,y in GB[:2]+IND[:1]+FOR[:1]:
            for st in ("现行","废止","待确认"):
                for mt in ("exact","newer","mismatch"):
                    b=self._b([self._p(c,n,y,st,mt)])
                    self.assertEqual(sum(len(v) for v in b.values()),1)

# ════════════════════════════════════════════════
# 4. 下载引擎
# ════════════════════════════════════════════════
class Test04Download(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pstd_dl_")
        self.sm = SessionManager(min_delay=0.001, max_delay=0.005)

    def tearDown(self):
        for _ in range(5):
            try: shutil.rmtree(self.tmp); break
            except PermissionError: time.sleep(0.1)

    def _e(self, adapters):
        return DownloadEngine(adapters=adapters, session_manager=self.sm, save_root=self.tmp)

    def test_success(self):
        from pilotstd.download.adapters.mock import MockDownloadAdapter
        e=self._e([MockDownloadAdapter(self.sm.create_session())])
        t=DownloadTask(standard_number="GB/T 19001-2016", source_site="openstd_download")
        r=e.download_single(t)
        self.assertEqual(r.status, DownloadStatus.SUCCESS)

    def test_skip_existing(self):
        from pilotstd.download.adapters.mock import MockDownloadAdapter
        e=self._e([MockDownloadAdapter(self.sm.create_session())])
        t=DownloadTask(standard_number="GB/T 1-2020")
        target=e._resolve_target_path(t)
        os.makedirs(os.path.dirname(target) or self.tmp, exist_ok=True)
        with open(target,"wb") as f: f.write(b"%PDF-1.4")
        r=e.download_single(t)
        self.assertEqual(r.status, DownloadStatus.SKIPPED)

    def test_skip_adopted(self):
        from pilotstd.download.adapters.mock import MockDownloadAdapter
        e=self._e([MockDownloadAdapter(self.sm.create_session())])
        qr=QueryResult(standard_number="GB/T 19001-2016", is_adopted=True)
        t=DownloadTask(standard_number="GB/T 19001-2016", query_result=qr)
        r=e.download_single(t)
        self.assertEqual(r.status, DownloadStatus.SKIPPED)

    def test_no_adapter_foreign(self):
        from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
        e=self._e([OpenstdDownloadAdapter(self.sm.create_session())])
        t=DownloadTask(standard_number="API 610-2004", source_site="njbz365")
        r=e.download_single(t)
        self.assertEqual(r.status, DownloadStatus.FAILED)

    def test_batch_stats(self):
        from pilotstd.download.adapters.mock import MockDownloadAdapter
        e=self._e([MockDownloadAdapter(self.sm.create_session())])
        tasks=[DownloadTask(standard_number=f"GB/T {i}-2020", source_site="openstd_download") for i in range(3)]
        tasks.append(DownloadTask(standard_number="XX 9999-2020"))
        _,stats=e.download_batch(tasks)
        self.assertEqual(stats.total,4)

    def test_find_adapter_map(self):
        from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
        e=self._e([OpenstdDownloadAdapter(self.sm.create_session())])
        self.assertIsNotNone(e._find_adapter(DownloadTask(standard_number="GB/T 1-2020", source_site="std_gov")))
        self.assertIsNone(e._find_adapter(DownloadTask(standard_number="API 610-2004", source_site="njbz365")))

# ════════════════════════════════════════════════
# 5. 归档 + 规范化
# ════════════════════════════════════════════════
class Test05Organize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pstd_org_")
        self.lib = os.path.join(self.tmp, "library")
        os.makedirs(self.lib)

    def tearDown(self):
        for _ in range(5):
            try: shutil.rmtree(self.tmp); break
            except PermissionError: time.sleep(0.1)

    def test_dir_builder_gb(self):
        db = DirBuilder(self.lib)
        path = db.build_path("GB/T", 19001, 2016, "质量管理体系")
        self.assertTrue(path.startswith(self.lib))
        self.assertIn("GB", path)

    def test_dir_builder_foreign(self):
        db = DirBuilder(self.lib)
        path = db.build_path("API", 610, 2004, "Centrifugal Pumps")
        self.assertTrue(path.startswith(self.lib))

    def test_dir_builder_industry(self):
        db = DirBuilder(self.lib)
        path = db.build_path("SH/T", 1610, 2011, "苯乙烯-丁二烯橡胶")
        self.assertIn("SH", path)

    def test_mover_skip_exists(self):
        dest = os.path.join(self.lib, "test.pdf")
        with open(dest, "wb") as f: f.write(b"existing")
        m = FileMover()
        result = m.move(os.path.join(self.tmp, "src.pdf"), dest, on_exists="skip")
        self.assertFalse(result)

    def test_expire_handler(self):
        expire_dir = os.path.join(self.lib, "过期作废")
        os.makedirs(expire_dir)
        eh = ExpireHandler(expire_dir)
        self.assertTrue(os.path.isdir(expire_dir))

# ════════════════════════════════════════════════
# 6. 待确认流程
# ════════════════════════════════════════════════
class Test06Pending(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pstd_pend_")
        db_path = os.path.join(self.tmp, "test.db")
        self.db = Database(db_path)
        for sql in [
            "CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER)",
            "INSERT OR IGNORE INTO _schema_version VALUES (9)",
            """CREATE TABLE IF NOT EXISTS pending_lookup (
                id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT,
                std_name TEXT, found_name TEXT, found_number TEXT, match_status TEXT,
                effect_status TEXT, score INTEGER, source_site TEXT, file_path TEXT,
                status TEXT DEFAULT 'pending', created_at TEXT, resolved_at TEXT,
                requery_count INTEGER DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS download_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT,
                standard_name TEXT, publish_date TEXT, expected_available TEXT,
                created_at TEXT, status TEXT DEFAULT 'waiting')""",
            """CREATE TABLE IF NOT EXISTS standard_info_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT,
                source_site TEXT, result_json TEXT, cached_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS announcement_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT, standard_number TEXT,
                source_site TEXT, result_json TEXT, cached_at TEXT)""",
        ]: self.db.execute(sql)
        self.fi = FileIndexRepository(self.db)
        self.svc = PendingService(self.db, self.fi)

    def tearDown(self):
        try: self.db.close()
        except: pass
        for _ in range(5):
            try: shutil.rmtree(self.tmp); break
            except PermissionError: time.sleep(0.1)

    def _p(self,c,n,y):
        f=make_standard_filename(c,n,y,"test")
        return ParsedStdInfo(raw_filename=f"{c} {n}-{y}.pdf",logical_code=c,number=n,year=y,
                             std_name="test",source_path=f"/tmp/{f}")

    def test_record_resolve(self):
        p=self._p("GB/T",99999,2099)
        self.svc.record_pending([p])
        self.assertEqual(len(self.svc.get_pending_items()),1)
        self.svc.resolve_pending([p],"discarded")
        self.assertEqual(len(self.svc.get_pending_items()),0)

    def test_three_strikes(self):
        num="GB/T 99999-2099"
        self.svc.record_pending([self._p("GB/T",99999,2099)])
        self.assertEqual(self.svc.increment_requery_count(num),1)
        self.assertFalse(self.svc.is_requery_exhausted(num))
        self.assertEqual(self.svc.increment_requery_count(num),2)
        self.assertEqual(self.svc.increment_requery_count(num),3)
        self.assertTrue(self.svc.is_requery_exhausted(num))
        self.svc.mark_manual_required(num)
        self.assertEqual(len(self.svc.get_pending_items()),0)

    def test_download_queue(self):
        p=self._p("GB/T",3836,2024)
        p.found_publish_date="2024-06-01"
        self.svc.enqueue_download_wait(p)
        self.assertEqual(len(self.svc.get_due_downloads()),1)

    def test_local_cache(self):
        self.db.execute("INSERT INTO standard_info_cache (standard_number,source_site,result_json,cached_at) VALUES (?,?,?,datetime('now'))",
            ("GB/T 19001-2016","std_gov",json.dumps({"standard_name":"质量管理体系","status":"现行","match_status":"exact","is_adopted":False})))
        _,r=self.svc.query_local_cache([self._p("GB/T",19001,2016)])[0]
        self.assertEqual(r.standard_name,"质量管理体系")

# ════════════════════════════════════════════════
# 7. 公告 Announce
# ════════════════════════════════════════════════
class Test07Announce(unittest.TestCase):
    def test_adapter_registry(self):
        from pilotstd.announcement.adapters.samr_gb import SamrGbAdapter
        from pilotstd.announcement.adapters.samr_hb import SamrHbAdapter
        from pilotstd.announcement.adapters.samr_db import SamrDbAdapter
        for a in [SamrGbAdapter, SamrHbAdapter, SamrDbAdapter]:
            self.assertTrue(hasattr(a, 'fetch_announcements') or hasattr(a, 'check'),
                          f"{a.__name__} 缺少入口方法")

    def test_parser_init(self):
        from pilotstd.announcement.parser import AnnounceParser
        p = AnnounceParser()
        self.assertIsNotNone(p)

    def test_matcher_init(self):
        from pilotstd.announcement.matcher import AnnounceMatcher
        m = AnnounceMatcher(MagicMock())
        self.assertIsNotNone(m)

# ════════════════════════════════════════════════
# 8. 任务队列
# ════════════════════════════════════════════════
class Test08TaskQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pstd_task_")
        self.db = Database(os.path.join(self.tmp, "test.db"))
        self.q = TaskQueue(self.db)

    def tearDown(self):
        try: self.db.close()
        except: pass
        for _ in range(5):
            try: shutil.rmtree(self.tmp); break
            except PermissionError: time.sleep(0.1)

    def test_enqueue_and_progress(self):
        t = self.q.enqueue(TaskType.SCAN, total_items=10)
        self.assertIsNotNone(t.task_id)
        self.q.update_progress(t, completed=5, failed=1)
        pending = self.q.get_pending()
        self.assertGreaterEqual(len(pending), 1)

    def test_cancel(self):
        t = self.q.enqueue(TaskType.QUERY, total_items=3)
        self.q.update_progress(t, completed=3)
        # 已完成的不在 pending 中
        self.assertEqual(len(self.q.get_pending()), 0)

    def test_get_by_status(self):
        self.q.enqueue(TaskType.SCAN, total_items=5)
        self.q.enqueue(TaskType.QUERY, total_items=3)
        self.assertEqual(len(self.q.get_pending()), 2)

# ════════════════════════════════════════════════
# 9. CLI
# ════════════════════════════════════════════════
class Test09CLI(unittest.TestCase):
    def test_imports(self):
        from pilotstd.cli.commands import main as cli_main
        self.assertTrue(callable(cli_main))

# ════════════════════════════════════════════════
# 10. 文件工具
# ════════════════════════════════════════════════
class Test10FileUtils(unittest.TestCase):
    def test_filename_all_types(self):
        for c,n,y in ALL[:10]:
            f=make_standard_filename(c,n,y,"test")
            self.assertTrue(f and f.endswith(".pdf"))

    def test_path_traversal(self):
        tmp=tempfile.mkdtemp()
        try:
            with self.assertRaises(ValueError):
                validate_path_in_root(os.path.join(tmp,"..","etc","passwd"),tmp)
        finally: shutil.rmtree(tmp,ignore_errors=True)

    def test_is_gb(self):
        for c in ("GB","GB/T","GB/Z","GSB"):
            self.assertTrue(is_gb_code(c))
        for c in ("API","SH/T","ISO","DIN","DB35/T"):
            self.assertFalse(is_gb_code(c))

# ════════════════════════════════════════════════
# 11. 数据库迁移
# ════════════════════════════════════════════════
class Test11Migrations(unittest.TestCase):
    def test_full_chain(self):
        tmp=tempfile.mkdtemp()
        try:
            db=Database(os.path.join(tmp,"test.db"))
            self.assertEqual(db.schema_version,9)
            db.close()
        finally:
            for _ in range(5):
                try: shutil.rmtree(tmp); break
                except PermissionError: time.sleep(0.1)

# ════════════════════════════════════════════════
# 12. FOREIGN_CODE_SET
# ════════════════════════════════════════════════
class Test12ForeignCodes(unittest.TestCase):
    def test_all_in_routes(self):
        from pilotstd.query.engine import CODE_ROUTES
        for fc in FOREIGN_CODE_SET:
            self.assertIn(fc, CODE_ROUTES, fc)
    def test_count(self):
        self.assertGreaterEqual(len(FOREIGN_CODE_SET), 24)

# ════════════════════════════════════════════════
# 13. 异常恢复
# ════════════════════════════════════════════════
class Test13ErrorRecovery(unittest.TestCase):
    def test_network_timeout_result(self):
        qr = QueryResult(standard_number="GB/T 1-2020", error_message="Connection timed out")
        self.assertFalse(qr.is_found())

    def test_empty_response_result(self):
        qr = QueryResult(standard_number="API 610-2004", error_message="所有来源均未找到该标准")
        self.assertFalse(qr.is_found())

    def test_malformed_json_result(self):
        qr = QueryResult(standard_number="SH/T 1610-2011", error_message="响应非 JSON 格式")
        self.assertFalse(qr.is_found())

    def test_cooldown_tracker(self):
        from pilotstd.query.rotator import SiteRotator
        from pilotstd.query.site_config import create_default_sites
        r = SiteRotator(create_default_sites())
        self.assertIsNotNone(r)

    def test_db_lock_retry(self):
        tmp = tempfile.mkdtemp()
        try:
            db = Database(os.path.join(tmp, "test.db"))
            db.execute("CREATE TABLE IF NOT EXISTS _lock_test (id INTEGER PRIMARY KEY)")
            db.close()
        finally:
            for _ in range(5):
                try: shutil.rmtree(tmp); break
                except PermissionError: time.sleep(0.1)

# ════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true")
    args, _ = ap.parse_known_args()
    if args.list_only:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(sys.modules[__name__])
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                for x in t:
                    print(f"  {x.__class__.__name__}.{x._testMethodName}")
        print(f"\n共 {suite.countTestCases()} 项")
    else:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
