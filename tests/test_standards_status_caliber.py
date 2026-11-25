"""标准状态口径集成测试（P0：`未生效` 过滤静默失效，P1-5 批次 11）。

背景（`docs/plans/2026-11-25-p1-unknown-refresh.md` §5.1）：
生产 `file_index` 776 条中 `status='未生效'` 有 10 条，`resolve_status_filter('未生效')`
返回 `None` → `/api/standards/status?status=未生效` **静默忽略过滤、返回全表 776**。

本文件用**真实 SQLite + 生产分布夹具**（现行 572 / 废止 95 / 作废 58 / 被代替 21 /
即将实施 20 / 未生效 10 = 776）锁定验收口径：

- `未生效` = `即将实施` 的历史兼容别名（公告口径 10/10 佐证同义）→ 与 `?status=upcoming`
  **结果集完全一致**（20 条），且 `status_key` 统一为 `upcoming`；
- 条数必须 **< 全表**（防「静默忽略过滤」复发），且每条 `status` 与解析后的取值匹配。
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from pilotstd.core.status import Status
from pilotstd.manager.standard_service import StandardService

#: 生产实测状态分布（docs/plans/2026-11-25-p1-unknown-refresh.md §2.3 SQL ①）
PRODUCTION_DISTRIBUTION = {
    Status.ACTIVE.value: 572,
    Status.WITHDRAWN.value: 95,
    Status.VOIDED.value: 58,
    Status.SUPERSEDED.value: 21,
    Status.UPCOMING.value: 20,
    "未生效": 10,
}


class _FakeDB:
    """模拟 `Database` 接口（fetchone/fetchall/execute），底层 sqlite3 :memory:。"""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    def fetchone(self, sql: str, params=()):
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params=()):
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def execute(self, sql: str, params=()):
        self._conn.execute(sql, params)
        self._conn.commit()


@pytest.fixture
def db() -> _FakeDB:
    d = _FakeDB()
    # 表结构必须与迁移链产出的生产 Schema 一致（check_schema_consistency.py 会比对 tests/ 的
    # CREATE TABLE；此处只填测试需要的列，其余列保留默认值）。
    d.execute(
        """
        CREATE TABLE file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            logical_code TEXT,
            number INTEGER,
            year INTEGER,
            part INTEGER DEFAULT -1,
            std_name TEXT DEFAULT '',
            file_hash TEXT DEFAULT '',
            status TEXT DEFAULT '现行',
            scanned_at TEXT,
            last_checked TEXT,
            raw_number TEXT DEFAULT '',
            source_version TEXT,
            data_state TEXT,
            last_accessed_at TEXT
        )
        """
    )
    d.execute(
        """
        CREATE TABLE standard_validity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            status TEXT DEFAULT '未知',
            last_checked_at TEXT,
            next_check_at TEXT,
            last_status TEXT,
            last_status_updated_at TEXT,
            check_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            source_version TEXT,
            data_state TEXT,
            last_accessed_at TEXT,
            last_changed_at TEXT
        )
        """
    )
    seq = 0
    for status, count in PRODUCTION_DISTRIBUTION.items():
        for _ in range(count):
            seq += 1
            d.execute(
                "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status, raw_number) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"/lib/{seq}.pdf", "GB", seq, 2020, -1, f"标准{seq}", status, str(seq)),
            )
    return d


@pytest.fixture
def mgr(db: _FakeDB):
    manager = SimpleNamespace(db=db)
    manager.standard_service = StandardService(manager)
    return manager


def _list(mgr, **kwargs) -> dict:
    from docker.api.standards import get_standards_status

    return get_standards_status(
        standard_no=None,
        name=None,
        page=1,
        page_size=100,
        mgr=mgr,
        **kwargs,
    )


class TestNotEffectiveFilter:
    def test_not_effective_filter_returns_upcoming_subset_not_full_table(self, db, mgr):
        """**P0 验收**：`?status=未生效` 返回 20 条子集而非全表 776，且每条状态匹配。"""
        resp = _list(mgr, status="未生效")
        total_all = db.fetchone("SELECT COUNT(*) AS cnt FROM file_index")["cnt"]

        assert total_all == 776
        assert resp["total"] == 20, "必须等于「即将实施」条数（别名归一），不得是全表"
        assert resp["total"] < total_all, "过滤必须真实生效（不能静默忽略）"
        assert len(resp["items"]) == 20
        assert all(item["status"] == Status.UPCOMING.value for item in resp["items"])
        assert all(item["status_key"] == "upcoming" for item in resp["items"])

    def test_not_effective_and_upcoming_filters_return_identical_result_sets(self, mgr):
        """`未生效` / `即将实施` / `upcoming` 三种写法结果集必须完全一致（历史兼容别名）。"""
        results = {
            raw: [item["id"] for item in _list(mgr, status=raw)["items"]]
            for raw in ("未生效", Status.UPCOMING.value, "upcoming")
        }
        assert results["未生效"] == results[Status.UPCOMING.value] == results["upcoming"]
        assert len(results["未生效"]) == 20

    def test_other_legacy_filters_still_work(self, mgr):
        """回归：既有分类筛选不受本次改动影响（作废仍可单筛、废止族口径不变）。"""
        assert _list(mgr, status="作废")["total"] == 58
        assert _list(mgr, status=Status.UPCOMING.value)["total"] == 20
        assert _list(mgr, status="withdrawn")["total"] == 174  # 废止 95 + 作废 58 + 被代替 21
        # 未知 = 四值之外：即将实施 20 + 未生效 10（`未生效` 仍进未知统计桶，见 get_stats）
        assert _list(mgr, status="unknown")["total"] == 30


class TestStatsCaliber:
    def test_stats_on_production_distribution(self, mgr):
        """统计口径不变：572 / 174 / 30（总数守恒 776）；`未生效` 仍属未知桶。"""
        stats = mgr.standard_service.get_stats()
        assert stats["total"] == 776
        assert stats["by_status"][Status.ACTIVE.value] == 572
        assert stats["by_status"][Status.WITHDRAWN_NORMALIZED.value] == 174
        assert stats["by_status"][Status.UNKNOWN.value] == 30
