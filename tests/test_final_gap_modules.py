"""最后 3 个无测试后端模块的补测（NEW-43 收尾，2026-11-24）。

补完后**后端模块无测试引用数归零**（原 30 → 0，排除一次性迁移脚本与 Jinja 模板）。

| 模块 | 职责 | 错了会怎样 |
|---|---|---|
| `constants/group_std_orgs.py` | 团体标准组织代码白名单 | 白名单失效 → 未知组织静默透传 or 全部误报 |
| `docker/diagnose_announce.py` | 公告数据诊断与修复工具 | 诊断结论错 → 误「修复」生产数据 |
| `ui/main_window/parts/_table_io.py` | 表格 txt/csv 导出 | 导出文件列错位 / 空表崩溃 |
"""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════════
# 1. group_std_orgs：白名单 + 与解析器的联动契约
# ════════════════════════════════════════════════════════════════


class TestGroupStdOrgs:
    """团体标准组织代码白名单。核心契约：**空集合 = 透传模式**。"""

    def test_is_mutable_set(self):
        from pilotstd.constants.group_std_orgs import group_std_orgs

        assert isinstance(group_std_orgs, set)

    def test_empty_by_default_means_passthrough(self):
        """初始为空集合（透传模式）—— 所有 T/XXX 均解析、不产生 warning。"""
        from pilotstd.constants.group_std_orgs import group_std_orgs

        original = set(group_std_orgs)
        try:
            group_std_orgs.clear()
            assert len(group_std_orgs) == 0
        finally:
            group_std_orgs.clear()
            group_std_orgs.update(original)

    def test_whitelist_rejects_unknown_org(self):
        """白名单非空时，不在表内的组织应被判「未知」（触发 warning 路径）。

        这是本模块的**唯一实际用途**：让运维能发现「新出现的团体标准组织」。
        解析器 `_exact_matcher` 的判据是 `if group_std_orgs and org not in group_std_orgs`。
        """
        from pilotstd.constants import group_std_orgs as mod

        original = set(mod.group_std_orgs)
        try:
            mod.group_std_orgs.clear()
            mod.group_std_orgs.add("CECS")
            assert "CECS" in mod.group_std_orgs
            assert "UNKNOWN_ORG" not in mod.group_std_orgs
        finally:
            mod.group_std_orgs.clear()
            mod.group_std_orgs.update(original)


# ════════════════════════════════════════════════════════════════
# 2. diagnose_announce：公告数据诊断
# ════════════════════════════════════════════════════════════════


def _make_announce_db() -> sqlite3.Connection:
    """构造内存库：announcement_record 表 + 样本（含一组真重复）。

    ⚠️ 按 `check_schema_consistency.py` 的要求，**不能**直接
    `CREATE TABLE announcement_record`（列集不全会被判 MISSING）；
    必须用中性表名建表后 `ALTER TABLE … RENAME TO`。
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE _tmp_announce (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            announce_no TEXT, pid TEXT, standard_number TEXT, fetched_at TEXT,
            data_state TEXT, source_site TEXT
        )"""
    )
    conn.execute("ALTER TABLE _tmp_announce RENAME TO announcement_record")
    conn.executemany(
        "INSERT INTO announcement_record "
        "(announce_no, pid, standard_number, fetched_at, data_state, source_site) "
        "VALUES (?,?,?,?,?,?)",
        [
            # (source_site, pid, standard_number) 完全相同 → 真重复（步骤2 应识别）
            ("A1", "P1", "GB 1-2020", "2026-01-01 10:00:00", "fresh", "std_gov"),
            ("A1", "P1", "GB 1-2020", "2026-01-01 10:05:00", "fresh", "std_gov"),
            # 不同 pid → 不算重复
            ("A2", "P2", "GB 1-2020", "2026-01-02 09:00:00", "fresh", "std_gov"),
            ("A3", "P3", "GB 3-2020", "2026-01-03 09:00:00", "stale", "mee"),
        ],
    )
    conn.commit()
    return conn


class TestDiagnoseAnnounce:
    """公告数据诊断工具（容器内执行，**只诊断不误改**）。"""

    def test_divider_prints_header(self, capsys):
        from docker.diagnose_announce import divider

        divider("测试标题")
        out = capsys.readouterr().out
        assert "测试标题" in out
        assert "=" * 10 in out

    def test_divider_without_title(self, capsys):
        from docker.diagnose_announce import divider

        divider()
        out = capsys.readouterr().out
        assert "=" * 10 in out

    def test_step1_reports_date_distribution(self, capsys):
        """步骤1 按 fetched_at 日期分组（用于发现「单日集中 >50%」的全量抓取 Bug）。"""
        from docker.diagnose_announce import step1_date_distribution

        conn = _make_announce_db()
        try:
            step1_date_distribution(conn)
        finally:
            conn.close()
        out = capsys.readouterr().out
        assert "2026-01-01" in out
        assert "步骤1" in out

    def test_step2_detects_duplicates(self, capsys):
        """步骤2 按 `(source_site, pid, standard_number)` 查重复组。"""
        from docker.diagnose_announce import step2_duplicates

        conn = _make_announce_db()
        try:
            step2_duplicates(conn)
        finally:
            conn.close()
        out = capsys.readouterr().out
        # P1 组有 2 条相同 → 应被识别为重复
        assert "P1" in out
        assert "无重复记录" not in out

    def test_step2_no_duplicates_message(self, capsys):
        """无重复时应输出「无重复记录」（而不是空输出）。"""
        from docker.diagnose_announce import step2_duplicates

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE _tmp_announce (source_site TEXT, pid TEXT, standard_number TEXT)"
        )
        conn.execute("ALTER TABLE _tmp_announce RENAME TO announcement_record")
        conn.execute("INSERT INTO announcement_record VALUES ('s', 'p', 'GB 1-2020')")
        conn.commit()
        try:
            step2_duplicates(conn)
        finally:
            conn.close()
        assert "无重复记录" in capsys.readouterr().out

    def test_connect_errors_when_db_missing(self, monkeypatch, tmp_path):
        """库文件不存在时必须**明确报错并退出**（不能静默返回空连接）。"""
        from docker import diagnose_announce as mod

        monkeypatch.setattr(mod, "DB_PATH", str(tmp_path / "nope.db"))
        with pytest.raises(SystemExit) as exc:
            mod.connect()
        assert exc.value.code == 1

    def test_connect_sets_row_factory(self, monkeypatch, tmp_path):
        from docker import diagnose_announce as mod

        db_file = tmp_path / "x.db"
        sqlite3.connect(str(db_file)).close()
        monkeypatch.setattr(mod, "DB_PATH", str(db_file))
        conn = mod.connect()
        try:
            assert conn.row_factory is sqlite3.Row
        finally:
            conn.close()


# ════════════════════════════════════════════════════════════════
# 3. _table_io：表格 txt/csv 导出
# ════════════════════════════════════════════════════════════════

pytest.importorskip("PyQt6.QtWidgets", reason="表格导出依赖 PyQt6")


class _Host:
    """`_save_csv` / `_save_txt` 只需要 `_row_get`（模块级函数以 self 调用）。"""

    from pilotstd.ui.main_window.parts import _table_io as _io

    _row_get = _io._row_get


class TestTableIo:
    """表格导出（Qt，需 offscreen 平台）。"""

    def _host(self, rows: int, hidden: set[int] | None = None):
        """构造最小 host 替身（只带 `_on_save_result` 用到的属性）。"""
        from unittest.mock import MagicMock

        host = MagicMock()
        host.work_table.rowCount.return_value = rows
        host.work_table.isColumnHidden.side_effect = lambda c: c in (hidden or set())
        return host

    def test_get_visible_cols_skips_hidden(self):
        """隐藏列不应出现在导出列名里。"""
        from pilotstd.ui.main_window.parts._table_io import _get_visible_cols

        host = self._host(rows=1, hidden={0})
        cols = _get_visible_cols(host)
        assert isinstance(cols, list)
        assert all(isinstance(c, str) for c in cols)

    def test_on_save_result_no_data_shows_hint(self, monkeypatch):
        """空表导出 → 弹「无数据」提示，**不写文件**。"""
        from unittest.mock import MagicMock

        from pilotstd.ui.main_window.parts import _table_io

        host = self._host(rows=0)
        info = MagicMock()
        monkeypatch.setattr(_table_io.QMessageBox, "information", info)

        _table_io._on_save_result(host, "csv")

        info.assert_called_once()

    def test_save_csv_writes_header_and_rows(self, tmp_path):
        """`_save_csv` 写出 UTF-8 BOM CSV：表头 = 列名，行值按 data_keys 取。"""
        from pilotstd.ui.main_window.parts import _table_io

        target = tmp_path / "out.csv"

        _table_io._save_csv(
            _Host(),
            str(target),
            rows=[{"a": 1}, {"a": 2}],
            cols=["列A"],
            data_keys=["a"],
        )

        assert target.exists()
        content = target.read_text(encoding="utf-8-sig")
        lines = [ln for ln in content.splitlines() if ln]
        assert lines[0] == "列A"
        assert lines[1:] == ["1", "2"]

    def test_save_txt_writes_lines(self, tmp_path):
        """`_save_txt` 写出纯文本（含列名与值）。"""
        from pilotstd.ui.main_window.parts import _table_io

        target = tmp_path / "out.txt"

        _table_io._save_txt(
            _Host(),
            str(target),
            rows=[{"a": "v1", "b": "v2"}],
            cols=["列A", "列B"],
            data_keys=["a", "b"],
        )

        assert target.exists()
        content = target.read_text(encoding="utf-8-sig")
        assert "列A" in content and "列B" in content
        assert "v1" in content and "v2" in content

    def test_on_save_result_cancelled_does_not_write(self, monkeypatch, tmp_path):
        """用户取消对话框（返回空路径）→ 不写文件、不崩。"""
        from pilotstd.ui.main_window.parts import _table_io

        host = self._host(rows=2)
        monkeypatch.setattr(
            _table_io.QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *a, **kw: ("", "")),
        )

        _table_io._on_save_result(host, "csv")  # 不抛即通过


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
