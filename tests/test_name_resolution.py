"""标准名称回退链测试（③ 决策名 → ② 查询名 → ① 解析名）。

为什么这些用例重要：
- 该回退链是"通知里的标准名"的唯一取值口径（2026-10-05 裁定 D1/D7）；
- **批次一必须容忍 `announcement_record.final_name` 列不存在**（该列由后续 v66 迁移引入），
  否则通知链路会在"刚上线、未迁移"的窗口里报错——故专门有用例锁定该边界。
"""

from pilotstd.core.name_resolution import (
    DEFAULT_PREFERRED_SITE,
    NAME_STAGE_ORDER,
    fetch_resolved_name,
    resolve_name,
)


class _Db:
    """最小 DB 替身：只实现本模块用到的两个方法，返回**字典行**（与生产 Database 一致）。"""

    def __init__(self, *, columns=("std_name", "standard_type", "final_name"), record=None, cache=None, boom=False):
        self._columns = list(columns)
        self._record = record
        self._cache = cache
        self._boom = boom
        self.sqls: list[str] = []

    def fetchall(self, sql, params=()):  # noqa: ARG002 - 契约签名
        """模拟 PRAGMA table_info：返回列名行。"""
        self.sqls.append(sql)
        if self._boom and "PRAGMA" in sql:
            raise RuntimeError("db down")
        return [{"name": c} for c in self._columns]

    def fetchone(self, sql, params=()):  # noqa: ARG002 - 契约签名
        """按 SQL 关键字分派：缓存表返回缓存行，公告表返回记录行。"""
        self.sqls.append(sql)
        if self._boom:
            raise RuntimeError("db down")
        if "standard_info_cache" in sql:
            return self._cache
        return self._record


class TestResolveName:
    def test_returns_first_non_empty(self):
        assert resolve_name(None, "", "   ", "名字B", "名字C") == "名字B"

    def test_all_empty_returns_empty_string(self):
        assert resolve_name(None, "", "   ") == ""

    def test_strips_whitespace(self):
        assert resolve_name("  标准名称  ") == "标准名称"

    def test_stage_order_constant_is_documented_order(self):
        """阶段降序常量即口径本身——顺序被改动时本用例会失败（防无声变更）。"""
        assert NAME_STAGE_ORDER == ("final_name", "found_name", "std_name")


class TestFetchResolvedName:
    def test_final_name_wins_over_cache_and_parsed(self):
        db = _Db(record={"std_name": "解析名", "standard_type": "GB", "final_name": "决策名"},
                 cache={"result_json": '{"standard_name": "查询名"}'})
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("决策名", "GB")

    def test_falls_back_to_cache_when_final_name_empty(self):
        """③ 为空 ⇒ 取 ②（且**不应**退到 ①，否则等于丢弃更高质量的名）。"""
        db = _Db(record={"std_name": "解析名", "standard_type": "GB", "final_name": ""},
                 cache={"result_json": '{"standard_name": "查询名"}'})
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("查询名", "GB")

    def test_falls_back_to_parsed_when_no_cache(self):
        db = _Db(record={"std_name": "解析名", "standard_type": "GB", "final_name": ""}, cache=None)
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("解析名", "GB")

    def test_column_absent_still_works(self):
        """**批次一边界**：`final_name` 列尚不存在时不得报错，且不得出现在 SQL 里。"""
        db = _Db(columns=("std_name", "standard_type"),
                 record={"std_name": "解析名", "standard_type": "GB"})
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("解析名", "GB")
        selects = [s for s in db.sqls if "SELECT" in s and "announcement_record" in s]
        assert selects and "final_name" not in selects[0]

    def test_all_sources_empty_returns_empty_pair(self):
        db = _Db(record={"std_name": "", "standard_type": "", "final_name": ""}, cache=None)
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("", "")

    def test_blank_standard_number_short_circuits(self):
        db = _Db(record={"std_name": "解析名", "standard_type": "GB", "final_name": ""})
        assert fetch_resolved_name(db, "") == ("", "")
        assert db.sqls == []

    def test_broken_cache_json_degrades_to_empty(self):
        """缓存是外部写入的 JSON：损坏时降级，不得抛错。"""
        db = _Db(record={"std_name": "", "standard_type": "", "final_name": ""},
                 cache={"result_json": "{不是合法 JSON"})
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("", "")

    def test_db_failure_degrades_to_empty(self):
        db = _Db(boom=True)
        assert fetch_resolved_name(db, "GB/T 1-2020") == ("", "")

    def test_preferred_site_is_passed_to_cache_query(self):
        """多站点缓存：以"优先站点 + cached_at 倒序"取行，站点可用参数覆盖。"""
        db = _Db(record=None, cache={"result_json": '{"standard_name": "查询名"}'})
        assert fetch_resolved_name(db, "GB/T 1-2020", preferred_site="csres") == ("查询名", "")
        cache_sql = next(s for s in db.sqls if "standard_info_cache" in s)
        assert "cached_at DESC" in cache_sql
        assert "source_site != ?" in cache_sql
        assert DEFAULT_PREFERRED_SITE == "std_gov"
