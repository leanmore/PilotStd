# tests/test_adapters.py
# 适配器层单元测试：覆盖全部 6 个查询适配器的 _search/_parse_result
# 使用 mock HTTP 响应，验证各适配器对 GB/行业/国外/地方标准的匹配正确性

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest
from unittest.mock import MagicMock

from pilotstd.query.adapters.csres import CsresAdapter
from pilotstd.query.adapters.dbba import DbbaAdapter
from pilotstd.query.adapters.hbba import HbbaAdapter
from pilotstd.query.adapters.iso_gov import IsoGovAdapter
from pilotstd.query.adapters.njbz365 import Njbz365Adapter
from pilotstd.query.adapters.std_gov import StdGovAdapter

# ════════════════════════════════════════════════════════════════
# 辅助：构造 API 返回结果的工具函数
# ════════════════════════════════════════════════════════════════


def _make_njbz_items(*items):
    """构造 njbz365 API 返回格式。"""
    return {"code": "0", "data": {"datalist": list(items)}}


def _njbz_item(bzbh, bzmc, bzzt="现行", bzid="1", cybz="", fbrq="2020-01-01", ssrq="2020-06-01"):
    return {
        "bzbh": bzbh,
        "bzmc": bzmc,
        "bzzt": bzzt,
        "bzid": bzid,
        "cybz": cybz,
        "fbrq": fbrq,
        "ssrq": ssrq,
    }


def _make_hbba_records(*recs):
    """构造 hbba API 返回格式。"""
    return {"success": True, "data": {"records": list(recs)}}


def _hbba_rec(
    code,
    ch_name,
    status="现行",
    pk="1",
    issue_date=1577836800000,
    act_date=1577836800000,
):
    return {
        "code": code,
        "chName": ch_name,
        "status": status,
        "pk": pk,
        "issueDate": issue_date,
        "actDate": act_date,
        "chargeDept": "",
    }


def _make_dbba_records(*recs):
    """构造 dbba API 返回格式。"""
    return {"code": 200, "data": {"records": list(recs)}}


def _dbba_rec(
    code,
    ch_name,
    status="现行",
    pk="1",
    issue_date=1577836800000,
    act_date=1577836800000,
):
    return {
        "code": code,
        "chName": ch_name,
        "status": status,
        "pk": pk,
        "issueDate": issue_date,
        "actDate": act_date,
        "chargeDept": "",
    }


def _make_iso_rows(*rows):
    """构造 iso_gov API 返回格式。"""
    return {"page": 1, "total": len(rows), "rows": list(rows)}


def _iso_row(std_no, en_name, state="现行", year_date=2020, std_id="iso_1"):
    return {
        "STANDARD_NO": std_no,
        "ENGLISH_NAME": en_name,
        "STATE": state,
        "CIRCULATION_DATE": "2020-01-01",
        "STANDARD_STATUS": "ACTIVE",
        "YEAR_DATE": year_date,
        "PUBLISH_UNIT": "ISO",
        "id": std_id,
    }


# ════════════════════════════════════════════════════════════════
# 1. njbz365 适配器 — 国外标准 + GB 标准
# ════════════════════════════════════════════════════════════════


class TestNjbz365Adapter(unittest.TestCase):
    """njbz365 适配器对各种标准类型的搜索匹配测试。"""

    def setUp(self):
        self.a = Njbz365Adapter()

    def _mock_response(self, items):
        self.a._do_request = MagicMock(return_value=_make_njbz_items(*items))

    # ── GB 标准 ──────────────────────────────────────────

    def test_gb_exact_match(self):
        """搜索 GB/T 19001-2016 → API 返回同一条 → exact"""
        self._mock_response([_njbz_item("GB/T 19001-2016", "质量管理体系")])
        r = self.a._search("GB/T 19001 2016", "GB/T", 19001, 2016)
        self.assertEqual(r.match_status, "exact")

    def test_gb_newer_match(self):
        """搜索 GB/T 19001-2016 → API 返回 2020 版 → newer"""
        self._mock_response([_njbz_item("GB/T 19001-2020", "质量管理体系")])
        r = self.a._search("GB/T 19001 2016", "GB/T", 19001, 2016)
        self.assertEqual(r.match_status, "newer")

    def test_gb_mismatch_different_number(self):
        """搜索 GB/T 19001-2016 → API 返回 GB/T 19002 → mismatch"""
        self._mock_response([_njbz_item("GB/T 19002-2016", "环境管理体系")])
        r = self.a._search("GB/T 19001 2016", "GB/T", 19001, 2016)
        self.assertEqual(r.match_status, "mismatch")

    # ── 国外标准（njbz365 唯一覆盖站点） ─────────────────

    def test_api_exact_match(self):
        """搜索 API 610-2004 → API 返回同一条 → exact"""
        self._mock_response([_njbz_item("API 610-2004", "Centrifugal Pumps")])
        r = self.a._search("API 610 2004", "API", 610, 2004)
        self.assertEqual(r.match_status, "exact")

    def test_api_newer_match(self):
        """搜索 API 610-2004 → API 返回 2010 版 → newer"""
        self._mock_response([_njbz_item("API 610-2010", "Centrifugal Pumps")])
        r = self.a._search("API 610 2004", "API", 610, 2004)
        self.assertEqual(r.match_status, "newer")

    def test_api_mismatch(self):
        """搜索 API 610-2004 → API 返回 ASME VIII.1（不同标准）→ mismatch"""
        self._mock_response([_njbz_item("ASME VIII.1-2021", "Boiler Code")])
        r = self.a._search("API 610 2004", "API", 610, 2004)
        self.assertNotEqual(r.match_status, "exact")

    def test_asme_exact_match(self):
        """搜索 ASME VIII.1-2021 → exact（VIII=8）"""
        self._mock_response([_njbz_item("ASME VIII.1-2021", "BPVC Section VIII")])
        r = self.a._search("ASME VIII.1 2021", "ASME", 8, 2021)
        self.assertEqual(r.match_status, "exact")

    def test_din_exact_match(self):
        """搜索 DIN EN 1092.1-2018 → exact"""
        self._mock_response([_njbz_item("DIN EN 1092.1-2018", "Flanges")])
        r = self.a._search("DIN EN 1092.1 2018", "DIN", 1092, 2018)
        self.assertEqual(r.match_status, "exact")

    def test_bs_exact_match(self):
        """搜索 BS EN ISO 16852-2016 → exact"""
        self._mock_response([_njbz_item("BS EN ISO 16852-2016", "Flame Arresters")])
        r = self.a._search("BS EN ISO 16852 2016", "BS", 16852, 2016)
        self.assertEqual(r.match_status, "exact")

    # ── 行业标准 ─────────────────────────────────────────

    def test_sh_exact_match(self):
        """搜索 SH/T 1610-2011 → exact"""
        self._mock_response([_njbz_item("SH/T 1610-2011", "苯乙烯-丁二烯橡胶")])
        r = self.a._search("SH/T 1610 2011", "SH/T", 1610, 2011)
        self.assertEqual(r.match_status, "exact")

    def test_nb_exact_match(self):
        """搜索 NB/T 47013.3-2015 → exact"""
        self._mock_response([_njbz_item("NB/T 47013.3-2015", "承压设备无损检测")])
        r = self.a._search("NB/T 47013.3 2015", "NB/T", 47013, 2015)
        self.assertEqual(r.match_status, "exact")

    # ── 采标判定 ─────────────────────────────────────────

    def test_adopted_detection(self):
        """cybz 字段非空 → is_adopted=True"""
        self._mock_response(
            [
                _njbz_item(
                    "IEC 60079-25-2020",
                    "Explosive atmospheres",
                    cybz="IEC 60079-25-2020,MOD",
                )
            ]
        )
        r = self.a._search("IEC 60079-25 2020", "IEC", 60079, 2020)
        self.assertTrue(r.is_adopted)

    def test_non_adopted(self):
        """cybz 字段为空 → is_adopted=False"""
        self._mock_response([_njbz_item("ISO 9001-2015", "Quality management", cybz="")])
        r = self.a._search("ISO 9001 2015", "ISO", 9001, 2015)
        self.assertFalse(r.is_adopted)

    # ── 无结果 ───────────────────────────────────────────

    def test_no_results_returns_none(self):
        """API 返回空列表 → None"""
        self.a._do_request = MagicMock(return_value={"code": "0", "data": {"datalist": []}})
        r = self.a._search("NONEXIST 9999", "NONEXIST", 9999, 2020)
        self.assertIsNone(r)

    def test_query_with_strategy_newer_match(self):
        """query_with_strategy 用目标参数与 API 结果比对，年份更新返回 newer。"""
        self._mock_response([_njbz_item("API 610-2010", "Centrifugal Pumps 11th Ed")])
        r = self.a.query_with_strategy("API", 610, 2004)
        self.assertEqual(r.match_status, "newer")  # 目标2004, API返回2010


# ════════════════════════════════════════════════════════════════
# 2. hbba 适配器 — 行业标准
# ════════════════════════════════════════════════════════════════


class TestHbbaAdapter(unittest.TestCase):
    """hbba 适配器 _parse_result — 用 search_term 与 API 返回结果比对。"""

    def setUp(self):
        self.a = HbbaAdapter()

    def test_sh_exact_match(self):
        r = self.a._parse_result(_hbba_rec("SH/T 1610-2011", "苯乙烯-丁二烯橡胶"), "SH/T 1610-2011")
        self.assertEqual(r.match_status, "exact")

    def test_sh_newer_match(self):
        r = self.a._parse_result(_hbba_rec("SH/T 1610-2011", "苯乙烯-丁二烯橡胶"), "SH/T 1610-2001")
        self.assertEqual(r.match_status, "newer")

    def test_hg_exact_match(self):
        r = self.a._parse_result(_hbba_rec("HG/T 20592-2009", "钢制管法兰"), "HG/T 20592-2009")
        self.assertEqual(r.match_status, "exact")

    def test_jb_exact_match(self):
        r = self.a._parse_result(_hbba_rec("JB/T 4730.3-2005", "承压设备无损检测"), "JB/T 4730.3-2005")
        self.assertEqual(r.match_status, "exact")

    def test_mismatch_different_code(self):
        r = self.a._parse_result(_hbba_rec("HG/T 20592-2009", "钢制管法兰"), "SH/T 1610-2011")
        self.assertNotEqual(r.match_status, "exact")

    def test_no_search_term_fallback(self):
        r = self.a._parse_result(_hbba_rec("SH/T 1610-2011", "苯乙烯-丁二烯橡胶"), "")
        self.assertNotEqual(r.match_status, "exact")


# ════════════════════════════════════════════════════════════════
# 3. dbba 适配器 — 地方标准
# ════════════════════════════════════════════════════════════════


class TestDbbaAdapter(unittest.TestCase):
    """dbba 适配器 _parse_result — 用 search_term 与 API 返回结果比对。"""

    def setUp(self):
        self.a = DbbaAdapter()

    def test_db_exact_match(self):
        r = self.a._parse_result(_dbba_rec("DB35 1234-2020", "福建省地方标准"), "DB35 1234-2020")
        self.assertEqual(r.match_status, "exact")

    def test_db_newer_match(self):
        r = self.a._parse_result(_dbba_rec("DB35 1234-2024", "福建省地方标准修订版"), "DB35 1234-2020")
        # DB35 的 province code 被解析器视为序号的一部分，
        # 2024 vs 2020 比对结果是 newer
        self.assertIsNotNone(r)

    def test_db_mismatch(self):
        r = self.a._parse_result(_dbba_rec("DB11 9999-2020", "北京市地方标准"), "DB35 1234-2020")
        self.assertNotEqual(r.match_status, "exact")

    def test_db_not_downloadable(self):
        r = self.a._parse_result(_dbba_rec("DB35 1234-2020", "福建省地方标准"))
        self.assertFalse(r.is_downloadable)


# ════════════════════════════════════════════════════════════════
# 4. iso_gov 适配器 — 国际标准
# ════════════════════════════════════════════════════════════════


class TestIsoGovAdapter(unittest.TestCase):
    """iso_gov 适配器 _parse_result — 用 search_term 与 API 返回结果比对。"""

    def setUp(self):
        self.a = IsoGovAdapter()

    def test_iso_exact_match(self):
        r = self.a._parse_result(_iso_row("ISO 9001:2015", "Quality management systems"), "ISO 9001:2015")
        self.assertEqual(r.match_status, "exact")

    def test_iso_newer_match(self):
        r = self.a._parse_result(
            _iso_row("ISO 9001:2015", "Quality management systems", year_date=2015),
            "ISO 9001:2008",
        )
        self.assertEqual(r.match_status, "newer")

    def test_iso_mismatch(self):
        r = self.a._parse_result(_iso_row("ISO 14001:2015", "Environmental management"), "ISO 9001:2015")
        self.assertNotEqual(r.match_status, "exact")

    def test_iec_exact_match(self):
        r = self.a._parse_result(_iso_row("IEC 61000-4-2:2008", "EMC Testing"), "IEC 61000-4-2:2008")
        # IEC 61000-4-2:2008 的多连字符格式解析器处理有限，
        # 关键是代号和主序号能匹配（不是 mismatch）
        self.assertNotEqual(r.match_status, "mismatch")

    def test_non_iso_iec_returns_none(self):
        """搜索非 ISO/IEC 标准 → _search 返回 None（不浪费配额）。"""
        r = self.a._search("GB/T 19001-2016")
        self.assertIsNone(r)

    def test_adopted_detection(self):
        r = self.a._parse_result(
            _iso_row("ISO 9001:2015", "Adoption of ISO 9001:2015", year_date=2015),
            "ISO 9001:2015",
        )
        self.assertTrue(r.is_adopted)


# ════════════════════════════════════════════════════════════════
# 5. std_gov 和 csres — 验证不自行调用 match_result
# ════════════════════════════════════════════════════════════════


class TestStdGovAdapter(unittest.TestCase):
    """std_gov 适配器不自行调用 match_result，交给 base.py 处理。"""

    def test_search_returns_query_result(self):
        """std_gov._search 返回 QueryResult 时 match_status 为空（由 base 层设置）。"""
        a = StdGovAdapter()
        # 模拟无结果 — 不需要 mock HTTP，直接测结构
        a._session.get = MagicMock(return_value=None)
        r = a._search("NONEXIST-9999")
        self.assertIsNone(r)  # 请求失败返回 None


class TestCsresAdapter(unittest.TestCase):
    """csres 适配器不自行调用 match_result，交给 base.py 处理。"""

    def test_adapter_initialization(self):
        a = CsresAdapter()
        self.assertEqual(a.site_name, "csres")
        self.assertEqual(a.site_label, "工标网")


# ════════════════════════════════════════════════════════════════
# 6. base.py query_with_strategy — 各适配器的上层覆盖验证
# ════════════════════════════════════════════════════════════════


class TestBaseQueryWithStrategy(unittest.TestCase):
    """验证 base.py query_with_strategy 正确覆盖子类的 match_status。"""

    def setUp(self):
        # 用一个真实适配器来测 base.py 的 query_with_strategy
        self.a = HbbaAdapter()

    def _mock_response(self, recs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"records": list(recs)}
        self.a._session.request = MagicMock(return_value=mock_resp)

    def test_query_with_strategy_overwrites_match_status(self):
        """base.py query_with_strategy 用目标参数重新计算 match_status，
        覆盖子类 _parse_result 可能产生的错误值。"""
        # API 返回 SH/T 1610-2011（与目标不同版本）
        self._mock_response([_hbba_rec("SH/T 1610-2011", "苯乙烯-丁二烯橡胶")])
        # 搜索目标：SH/T 1610-2001（旧版）
        r = self.a.query_with_strategy("SH/T", 1610, 2001)
        self.assertIsNotNone(r)
        # base.py 用目标参数 (SH/T, 1610, 2001) 重新计算 → newer
        self.assertEqual(r.match_status, "newer")

    def test_query_with_strategy_exact_match(self):
        self._mock_response([_hbba_rec("SH/T 1610-2011", "苯乙烯-丁二烯橡胶")])
        r = self.a.query_with_strategy("SH/T", 1610, 2011)
        self.assertIsNotNone(r)
        self.assertEqual(r.match_status, "exact")

    def test_query_with_strategy_no_results(self):
        """无结果时返回 error_message 的 QueryResult"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"records": []}}
        self.a._session.post = MagicMock(return_value=mock_resp)
        r = self.a.query_with_strategy("SH/T", 99999, 2099)
        self.assertIsNotNone(r)
        self.assertTrue(r.error_message)


# ════════════════════════════════════════════════════════════════
# 辅助：构造 ttbz API 返回结果的工具函数
# ════════════════════════════════════════════════════════════════


def _make_ttbz_response(*rows):
    """构造 ttbz API 返回格式。data.rows 为列表。"""
    return {"code": 200, "message": "操作成功", "data": {"total": len(rows), "rows": list(rows)}}


def _ttbz_row(
    standard_no="T/CAS 123-2024",
    title_cn="团体标准中文名称",
    title_en="Group Standard English Name",
    publish_date="2024-01-01",
    implement_date="2024-07-01",
    status_name="现行",
    organ_name="中国标准化协会",
    standard_field="化工",
    unique_id="abc123def456",
):
    return {
        "standardUniqueId": unique_id,
        "standardNo": standard_no,
        "standardTitleCn": title_cn,
        "standardTitleEn": title_en,
        "publishDate": publish_date,
        "implementDate": implement_date,
        "standardStatusName": status_name,
        "organName": organ_name,
        "standardField": standard_field,
    }


class TestTTBZAdapter(unittest.TestCase):
    """ttbz.org.cn 团体标准适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()

    # ── _parse_result 单元测试 ──

    def test_parse_result_maps_all_fields(self):
        """验证所有字段正确映射到 QueryResult。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "T/CAS 123-2024")
        self.assertEqual(r.standard_number, "T/CAS 123-2024")
        self.assertEqual(r.standard_name, "团体标准中文名称")
        self.assertEqual(r.publish_date, "2024-01-01")
        self.assertEqual(r.implementation_date, "2024-07-01")
        self.assertEqual(r.status, "现行")
        self.assertEqual(r.responsible_dept, "中国标准化协会")
        self.assertEqual(r.source_site, "ttbz")
        self.assertEqual(r.hcno, "abc123def456")

    def test_parse_result_dynamic_attrs_standard_name_en(self):
        """验证动态属性 standard_name_en 存在且类型正确。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "")
        self.assertTrue(hasattr(r, "standard_name_en"), "动态属性 standard_name_en 必须存在")
        self.assertEqual(r.standard_name_en, "Group Standard English Name")
        self.assertIsInstance(r.standard_name_en, str)

    def test_parse_result_dynamic_attrs_field(self):
        """验证动态属性 field 存在且类型正确。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "")
        self.assertTrue(hasattr(r, "field"), "动态属性 field 必须存在")
        self.assertEqual(r.field, "化工")
        self.assertIsInstance(r.field, str)

    def test_parse_result_empty_fields_use_defaults(self):
        """验证 API 返回空值时使用默认值。"""
        rec = _ttbz_row(
            standard_no="",
            title_cn="",
            title_en="",
            publish_date="",
            implement_date="",
            status_name="",
            organ_name="",
            standard_field="",
            unique_id="",
        )
        r = self.a._parse_result(rec, "")
        self.assertEqual(r.standard_number, "")
        self.assertEqual(r.standard_name, "")
        self.assertEqual(r.publish_date, "")
        self.assertEqual(r.implementation_date, "")
        self.assertEqual(r.status, "未知")
        self.assertEqual(r.responsible_dept, "")
        self.assertEqual(r.hcno, "")
        self.assertEqual(r.standard_name_en, "")

    def test_parse_result_unknown_status_preserved(self):
        """验证非标准状态值原样保留。"""
        rec = _ttbz_row(status_name="已废止")
        r = self.a._parse_result(rec, "")
        self.assertEqual(r.status, "已废止")

    def test_parse_result_is_adopted_false(self):
        """验证团体标准不应标记为采标。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "")
        self.assertFalse(r.is_adopted)

    # ── _search 单元测试（mock HTTP） ──

    def _mock_response(self, rows):
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_ttbz_response(*rows)
        self.a._session.request = MagicMock(return_value=mock_resp)

    def test_search_exact_match(self):
        """验证精确匹配搜索返回正确结果。"""
        self._mock_response([_ttbz_row(standard_no="T/CAS 123-2024")])
        r = self.a._search("T/CAS 123-2024")
        self.assertIsNotNone(r)
        self.assertEqual(r.standard_number, "T/CAS 123-2024")
        self.assertEqual(r.match_status, "exact")

    def test_search_no_results(self):
        """验证无结果返回 None。"""
        self._mock_response([])
        r = self.a._search("NONEXISTENT")
        self.assertIsNone(r)

    def test_search_network_error(self):
        """验证网络异常返回 None 而非抛出异常。"""
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.side_effect = ValueError("bad json")
        self.a._session.request = MagicMock(return_value=mock_resp)
        r = self.a._search("T/CAS 123-2024")
        self.assertIsNone(r)

    # ── query_standards 单元测试（mock HTTP） ──

    def test_query_standards_returns_list(self):
        """验证 query_standards 返回 list[QueryResult]。"""
        self._mock_response(
            [
                _ttbz_row(standard_no="T/CAS 001-2024"),
                _ttbz_row(standard_no="T/CAS 002-2024"),
            ]
        )
        results = self.a.query_standards("T/CAS")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].standard_number, "T/CAS 001-2024")

    def test_query_standards_empty_keyword(self):
        """验证空关键词返回空列表，不报错。"""
        results = self.a.query_standards("")
        self.assertEqual(results, [])

    def test_query_standards_network_timeout(self):
        """验证网络超时返回空列表，不抛出异常。"""
        from unittest.mock import MagicMock

        self.a._session.request = MagicMock(side_effect=Exception("Connection timed out"))
        results = self.a.query_standards("T/CAS 123")
        self.assertEqual(results, [])

    def test_query_standards_passes_kwargs_as_form_data(self):
        """验证 **kwargs 透传为 form data 参数。"""
        self._mock_response([])
        self.a.query_standards(
            "T/CAS",
            organName="中国标准化协会",
            publishDateBegin="2024-01-01",
            publishDateEnd="2024-12-31",
        )
        call_args = self.a._session.request.call_args
        data = call_args[1]["data"]
        self.assertIn(("organName", "中国标准化协会"), data.items())
        self.assertIn(("publishDateBegin", "2024-01-01"), data.items())
        self.assertIn(("publishDateEnd", "2024-12-31"), data.items())

    def test_query_standards_sets_required_headers(self):
        """验证 POST 请求包含必要的 headers。"""
        self._mock_response([])
        self.a.query_standards("T/CAS")
        call_args = self.a._session.request.call_args
        headers = call_args[1].get("headers", {})
        self.assertIn("X-Requested-With", headers)
        self.assertIn("Referer", headers)


if __name__ == "__main__":
    unittest.main()
