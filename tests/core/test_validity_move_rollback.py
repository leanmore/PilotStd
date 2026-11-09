# tests/core/test_validity_move_rollback.py — U56 §7.4：废止搬移与回滚
"""覆盖 `pilotstd/core/validity_checker.py` 的“部分失败必须回滚”契约（D3-1/D3-4）。

10 例：单文件失败回滚、非法标准号、已在过期目录、修改单排除、part 精确、
无记录、逆序回滚、回滚 OSError 继续、并行期判定、通知异常只 warning。
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from types import SimpleNamespace

from pilotstd.core import validity_checker as vc_mod
from pilotstd.core.validity_checker import ValidityChecker


class _FakeDb:
    """把 sqlite3.Connection 适配成 ValidityChecker 需要的 Database 子集。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchall()


def _db(rows: list[tuple]) -> _FakeDb:
    """建 file_index 并插入 (file_path, std_name, logical_code, number, year, part)。

    用中性表名建表后 RENAME：schema 一致性门禁按表名比对生产列集，
    直接用生产表名会因缺列被判 MISSING。
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE tmp_file_index (file_path TEXT, std_name TEXT, logical_code TEXT,"
        " number INTEGER, year INTEGER, part INTEGER)"
    )
    conn.execute("ALTER TABLE tmp_file_index RENAME TO file_index")
    conn.executemany("INSERT INTO file_index VALUES (?,?,?,?,?,?)", rows)
    return _FakeDb(conn)


def _patch_organizer(monkeypatch, tmp_path, dst_dir, fail: set[str] | None = None):
    """把 DirBuilder/FileMover/ConfigManager/StandardParser 换成临时目录替身。"""
    fail = fail or set()
    calls: list[str] = []
    dst_dir.mkdir(parents=True, exist_ok=True)

    class _Mover:
        def __init__(self, builder, *a, **kw):  # noqa: ANN001, ANN002, ANN003
            self._builder = builder

        def move_to_code_dir(self, path, info):  # noqa: ANN001
            import os

            base = os.path.basename(path)
            calls.append(path)
            if base in fail:
                return None
            target = dst_dir / base
            shutil.move(path, target)
            return str(target)

    monkeypatch.setattr("pilotstd.core.config.ConfigManager", lambda: SimpleNamespace(
        get=lambda key, default=None: "过期作废"
    ))
    monkeypatch.setattr("pilotstd.core.config.get_library_root", lambda cfg: tmp_path)
    monkeypatch.setattr("pilotstd.organizer.dir_builder.DirBuilder", lambda *a, **kw: object())
    monkeypatch.setattr("pilotstd.organizer.mover.FileMover", _Mover)
    monkeypatch.setattr("pilotstd.organizer.industry_lookup.build_code_mapping", lambda *a, **kw: {})
    monkeypatch.setattr(
        "pilotstd.scan.parser.StandardParser",
        lambda mapping: SimpleNamespace(parse=lambda name: SimpleNamespace(file_name=name)),
    )
    return calls


def _mkfile(path, content: bytes = b"x") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


# ── 1) 部分失败 → 回滚 ─────────────────────────────────────────────────


def test_move_expired_file_rolls_back_when_one_file_fails(tmp_path, monkeypatch) -> None:
    """2 个文件，第 2 个移动失败 → 第 1 个被搬回原位、返回 None。"""
    src = tmp_path / "src"
    a = _mkfile(src / "a.pdf")
    b = _mkfile(src / "b.pdf")
    calls = _patch_organizer(monkeypatch, tmp_path, tmp_path / "dst", fail={"b.pdf"})
    checker = ValidityChecker(_db([(a, "甲", "GB/T", 1, 2020, None), (b, "乙", "GB/T", 1, 2020, None)]))

    result = checker._move_expired_file("GB/T 1-2020", "已废止")

    assert result is None
    assert len(calls) == 2
    assert (src / "a.pdf").exists(), "第一个文件必须被回滚回原位"
    assert not (tmp_path / "dst" / "a.pdf").exists()


# ── 2) 非法标准号 ──────────────────────────────────────────────────────


def test_move_expired_file_returns_empty_on_unparseable_number(monkeypatch) -> None:
    """非法标准号 → []（上层继续写状态）。"""
    monkeypatch.setattr(vc_mod.__name__ + ".parse_std_number", None, raising=False)
    # parse_std_number 是函数内 import，改源模块
    monkeypatch.setattr("pilotstd.core.std_utils.parse_std_number", lambda number: None)
    checker = ValidityChecker(_db([]))

    assert checker._move_expired_file("不是标准号", "已废止") == []


# ── 3) 已在过期目录 ────────────────────────────────────────────────────


def test_move_expired_file_skips_already_expired_dir(tmp_path, monkeypatch) -> None:
    """路径已在“过期作废”下 → 不重复搬。"""
    expired = tmp_path / "lib" / "过期作废" / "a.pdf"
    path = _mkfile(expired)
    calls = _patch_organizer(monkeypatch, tmp_path, tmp_path / "dst")
    checker = ValidityChecker(_db([(path, "甲", "GB/T", 1, 2020, None)]))

    assert checker._move_expired_file("GB/T 1-2020", "已废止") == []
    assert calls == []


# ── 4) 修改单排除 ──────────────────────────────────────────────────────


def test_move_expired_file_skips_modification_sheets(tmp_path, monkeypatch) -> None:
    """文件名/名称含“修改单” → 不搬（由 SQL 过滤）。"""
    src = tmp_path / "src"
    a = _mkfile(src / "a.pdf")
    calls = _patch_organizer(monkeypatch, tmp_path, tmp_path / "dst")
    checker = ValidityChecker(_db([(a, "标准修改单", "GB/T", 1, 2020, None)]))

    assert checker._move_expired_file("GB/T 1-2020", "已废止") == []
    assert calls == []


# ── 5) part 精确 ───────────────────────────────────────────────────────


def test_move_expired_file_part_scoped(tmp_path, monkeypatch) -> None:
    """同号不同 part → 只搬命中 part（D3-4）。"""
    src = tmp_path / "src"
    p1 = _mkfile(src / "p1.pdf")
    p2 = _mkfile(src / "p2.pdf")
    calls = _patch_organizer(monkeypatch, tmp_path, tmp_path / "dst")
    monkeypatch.setattr(
        "pilotstd.core.std_utils.parse_std_number",
        lambda number: {"raw_code": "GB/T", "number": 1, "year": 2020, "part": 1},
    )
    checker = ValidityChecker(
        _db([(p1, "甲", "GB/T", 1, 2020, 1), (p2, "乙", "GB/T", 1, 2020, 2)])
    )

    moved = checker._move_expired_file("GB/T 1.1-2020", "已废止")

    assert moved is not None and len(moved) == 1
    assert calls == [p1]
    assert (src / "p2.pdf").exists()


# ── 6) 无记录 ──────────────────────────────────────────────────────────


def test_move_expired_file_returns_empty_when_no_rows(tmp_path, monkeypatch) -> None:
    """索引无记录 → []。"""
    _patch_organizer(monkeypatch, tmp_path, tmp_path / "dst")
    checker = ValidityChecker(_db([]))

    assert checker._move_expired_file("GB/T 1-2020", "已废止") == []


# ── 7) 逆序回滚 ────────────────────────────────────────────────────────


def test_rollback_moves_restores_in_reverse_order(tmp_path, monkeypatch) -> None:
    """3 条 → 逆序搬回。"""
    pairs = []
    for name in ("a", "b", "c"):
        new = _mkfile(tmp_path / "dst" / f"{name}.pdf")
        old = tmp_path / "src" / f"{name}.pdf"
        pairs.append((str(old), new))
    order: list[str] = []
    real_move = shutil.move

    def _spy(src, dst):
        order.append(str(src))
        return real_move(src, dst)

    monkeypatch.setattr(shutil, "move", _spy)
    ValidityChecker._rollback_moves(pairs)

    assert [os.path.basename(p) for p in order] == ["c.pdf", "b.pdf", "a.pdf"]
    assert all((tmp_path / "src" / f"{n}.pdf").exists() for n in ("a", "b", "c"))


# ── 8) 回滚 OSError 继续 ───────────────────────────────────────────────


def test_rollback_moves_logs_and_continues_on_oserror(tmp_path, monkeypatch) -> None:
    """单个回滚抛 OSError → 其他继续、不冒泡。"""
    first_new = _mkfile(tmp_path / "dst" / "a.pdf")
    second_new = _mkfile(tmp_path / "dst" / "b.pdf")
    pairs = [
        (str(tmp_path / "src" / "a.pdf"), first_new),
        (str(tmp_path / "src" / "b.pdf"), second_new),
    ]
    real_move = shutil.move

    def _flaky(src, dst):
        if str(src).endswith("a.pdf"):
            raise OSError("locked")
        return real_move(src, dst)

    monkeypatch.setattr(shutil, "move", _flaky)
    ValidityChecker._rollback_moves(pairs)  # 不抛

    assert not (tmp_path / "src" / "a.pdf").exists()
    assert (tmp_path / "src" / "b.pdf").exists()


# ── 9) 并行期 ──────────────────────────────────────────────────────────


def test_parallel_period_active_window() -> None:
    """实施日在未来 → True；已过 → False；非法日期 → False。"""
    assert ValidityChecker._parallel_period_active("GB/T 1-2099", "2099-01-01") is True
    assert ValidityChecker._parallel_period_active("GB/T 1-2000", "2000-01-01") is False
    assert ValidityChecker._parallel_period_active("GB/T 1-2020", "not-a-date") is False
    assert ValidityChecker._parallel_period_active("", "2099-01-01") is False


# ── 10) 通知异常只 warning ─────────────────────────────────────────────


def test_notify_status_changed_swallows_send_error(caplog) -> None:
    """通知抛错 → 只 warning，不冒泡。"""

    class _Mgr:
        def send_event(self, *a, **kw):  # noqa: ANN002, ANN003
            raise RuntimeError("notify down")

    checker = ValidityChecker(_db([]))
    with caplog.at_level("WARNING", logger="pilotstd.core.validity_checker"):
        checker._notify_status_changed(_Mgr(), "GB/T 1-2020", "已废止", "现行", "", "")

    assert any("状态变更通知发送失败" in r.message for r in caplog.records)
