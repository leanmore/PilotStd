"""tests/test_migration_checksum_guard.py — 技术债 #28：迁移 checksum 守卫的三种结果。

修正前：判定条件是「当前源码 raw != norm」，而 `norm_source` 会去缩进，
任何带缩进的函数恒有 raw != norm（实测 59/59）→ **任何**不匹配都走自愈，
`DatabaseError` 抛错分支不可达 → P-106（已执行迁移源码不可变）名义生效、实际失效。

修正后：先比标准化值（注释/空行变化不影响它），再比「存储值 == 当前 raw」（历史 raw 口径才自愈），
其余即真实变更 → 抛错。本文件用**合成迁移**（不碰真实迁移脚本）固定这三种结果。
"""

import inspect

import pytest

from pilotstd.core.db import _migration_checksum as mc
from pilotstd.core.db._constants import MIGRATIONS, DatabaseError


def _old_logic(db):
    """合成迁移（旧逻辑）。"""
    db.execute("CREATE TABLE a (id INTEGER)")


def _new_logic(db):
    """合成迁移（逻辑已变更：建的是另一张表）。"""
    db.execute("CREATE TABLE b (id INTEGER)")


class _FakeDb:
    """最小化 Database 替身：只提供校验用到的三个成员。"""

    def __init__(self, stored_checksum: str | None) -> None:
        self.schema_version = 1
        self._stored = stored_checksum
        self.updates: list[tuple] = []

    def fetchone(self, sql: str, params: tuple = ()):
        """返回库内 checksum（无值则返回 None）。"""
        if self._stored is None:
            return None
        return {"checksum": self._stored}

    def execute(self, sql: str, params: tuple = ()):
        """记录自愈写入。"""
        self.updates.append(params)


@pytest.fixture()
def one_migration(monkeypatch):
    """把 MIGRATIONS 换成单个合成迁移，避免依赖真实迁移脚本。"""

    def _use(fn):
        monkeypatch.setattr(mc, "MIGRATIONS", {1: fn})

    return _use


@pytest.fixture()
def norm():
    """标准化哈希函数（与门禁实现同口径）。"""
    return mc.norm_checksum


def test_unchanged_source_passes(one_migration, norm):
    """场景 1：存储值 == 标准化值 → 通过，且不做任何写入。"""
    one_migration(_old_logic)
    db = _FakeDb(norm(_old_logic))
    mc.verify_migration_checksums(db)
    assert db.updates == []


def test_comment_only_change_is_allowed(one_migration, norm, monkeypatch):
    """场景 2：只改注释 → 标准化值不变 → 视为源码未变，不报错、不写入。

    做法：先取改动前的标准化值当"库内存储值"，再让 `inspect.getsource` 返回**多一行注释**
    的同名函数源码（同名是必须的——源码含 `def` 行，换名字本身就改变了标准化值）。
    """
    one_migration(_old_logic)
    original = inspect.getsource(_old_logic)
    stored = norm(_old_logic)  # 改动前（= 库内存储值）

    changed = original.replace("    db.execute(", "    # 新增一条注释\n    db.execute(", 1)
    assert changed != original, "注入注释失败"

    class _Shim:
        """只替换 getsource 的 inspect 替身，避免污染真实 inspect 模块。"""

        @staticmethod
        def getsource(fn):
            """返回"多一行注释"的源码。"""
            return changed if fn is _old_logic else inspect.getsource(fn)

    monkeypatch.setattr(mc, "inspect", _Shim)
    assert mc.norm_checksum(_old_logic) == stored, "注释变化不应影响标准化值"

    db = _FakeDb(stored)
    mc.verify_migration_checksums(db)
    assert db.updates == [], "注释变化既不该报错、也不该写库"


def test_legacy_raw_hash_self_heals(one_migration, norm, caplog):
    """场景 3：库内是历史 raw 风格哈希、源码未变 → WARNING + 自愈为标准化值。"""
    one_migration(_old_logic)
    db = _FakeDb(mc.compute_checksum(_old_logic))
    with caplog.at_level("WARNING", logger="pilotstd.db"):
        mc.verify_migration_checksums(db)
    assert db.updates and db.updates[0][0] == norm(_old_logic), db.updates
    assert any("已自动修复" in r.getMessage() for r in caplog.records)


def test_logic_change_raises_database_error(one_migration, norm):
    """场景 4（#28 的**可达性证据**）：库内是旧逻辑的标准化哈希、当前源码逻辑已变 → 抛 DatabaseError。

    修正前本场景会走自愈分支（判定条件 `raw != norm` 恒真），断言必然失败；
    修正后它是抛错分支的永久回归用例——删掉它就意味着 #28 复发。
    """
    one_migration(_new_logic)
    db = _FakeDb(norm(_old_logic))  # 库内记录的是「旧逻辑」的哈希
    with pytest.raises(DatabaseError) as exc:
        mc.verify_migration_checksums(db)
    assert "脚本逻辑已变更" in str(exc.value)
    assert db.updates == [], "真实变更不应写库"


def test_real_migrations_all_have_raw_not_equal_norm():
    """事实基线：真实迁移函数恒有 raw != norm（59/59）——这正是旧判定恒真的根因。"""
    diff = sum(1 for fn in MIGRATIONS.values() if mc.compute_checksum(fn) != mc.norm_checksum(fn))
    assert diff == len(MIGRATIONS) > 0, f"{diff}/{len(MIGRATIONS)}"


def test_norm_source_strips_comments_and_indent():
    """口径固定：norm_source 去缩进、去 # 注释（含行内），但保留 docstring（字符串字面量）。"""
    src = 'def f():\n    """文档。"""\n    # 注释\n    x = 1  # 行内\n'
    assert mc.norm_source(src) == 'def f():\n"""文档。"""\nx = 1'
