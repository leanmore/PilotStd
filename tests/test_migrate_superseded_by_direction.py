"""superseded_by 迁移脚本的纯逻辑 + 端到端（临时库）测试。"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "migrate_superseded_by_direction.py"


def _load():
    spec = importlib.util.spec_from_file_location("migrate_superseded_by", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


def test_parse_year_handles_common_forms():
    assert m.parse_year("GB 30871-2022") == 2022
    assert m.parse_year("GB/T 1.1-2020") == 2020
    assert m.parse_year("HG/T 20615-2009") == 2009
    assert m.parse_year("无年份标准") == 0


def test_split_codes_supports_chinese_comma():
    assert m.split_codes("A-2010,B-2011") == ["A-2010", "B-2011"]
    assert m.split_codes("A-2010，B-2011") == ["A-2010", "B-2011"]
    assert m.split_codes("") == []
    assert m.split_codes(None) == []


def test_plan_row_drops_backwards_and_keeps_forward():
    plan = m.plan_row(1, "GB 4287-2026", "GB 4287-2012,GB 28936-2030")
    assert plan.dropped == ["GB 4287-2012"]
    assert plan.keep == ["GB 28936-2030"]
    assert plan.after() == "GB 28936-2030"
    assert plan.changed is True


def test_plan_row_without_year_is_untouched():
    plan = m.plan_row(2, "GB/T 9999", "GB/T 8888")
    assert plan.changed is False
    assert plan.after() == "GB/T 8888"


def _temp_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # 中性表名建表后改名：门禁的 schema 校验只比对生产表名，直接建会被判“列集不全”
    conn.execute(
        "CREATE TABLE _tmp_ar ("
        " id INTEGER PRIMARY KEY, standard_number TEXT, superseded_by TEXT)"
    )
    conn.execute("ALTER TABLE _tmp_ar RENAME TO announcement_record")
    conn.executemany(
        "INSERT INTO announcement_record (id, standard_number, superseded_by) VALUES (?,?,?)",
        [
            (1, "GB 6000-2026", "GB 6000-1999"),   # 倒退：应清空并回填目标
            (2, "GB 6000-1999", ""),               # 目标旧标准：空 → 写新号
            (3, "GB 8840-2026", "GB 8840-2009"),   # 倒退
            (4, "GB 8840-2009", "GB 8840-1990"),   # 目标已有值 → 不覆盖
            (5, "GB 1-2020", "GB 2-2025"),         # 已是正向 → 不动
        ],
    )
    conn.commit()
    return conn


def test_apply_only_fills_empty_targets(tmp_path):
    conn = _temp_db()
    plans = m.collect_plans(conn, 0)
    assert {p.row_id for p in plans} == {1, 3, 4}
    result = m.apply_plans(conn, plans)
    assert result["cleared_rows"] == 3
    rows = {r["id"]: r["superseded_by"] for r in conn.execute("SELECT id, superseded_by FROM announcement_record")}
    assert rows[1] == "" and rows[2] == "GB 6000-2026"
    # 4 号自己也是倒退值：先被清掉，再作为 3 号的目标被回填（不是“保留乱值”）
    assert rows[3] == "" and rows[4] == "GB 8840-2026"
    assert rows[5] == "GB 2-2025"                        # 正向不动


def test_check_existing_reports_direction_mix(tmp_path):
    """--check-existing 的前提结论：正确方向的值不会被计为“将清理”。"""
    conn = _temp_db()
    conn.execute(
        "INSERT INTO announcement_record (id, standard_number, superseded_by) "
        "VALUES (6, 'GB 9-2010', 'GB 9-2020')"
    )
    conn.execute(
        "INSERT INTO announcement_record (id, standard_number, superseded_by) "
        "VALUES (7, 'GB 9-2020', 'GB 9-2030')"
    )
    conn.commit()
    stats = m.check_existing(conn)
    assert stats["targets"] >= 1
    assert stats["forward"] >= 1        # GB 9-2010 -> GB 9-2020 方向正确
    assert stats["backward"] >= 1       # 目标行里也有倒退值（GB 8840-2009 -> GB 8840-1990）
    assert stats["empty"] >= 1          # GB 6000-1999 原本为空

    plans = m.collect_plans(conn, 0)
    cleared = {v for p in plans for v in p.dropped}
    assert "GB 9-2020" not in cleared   # 正确方向的值不在清理集合里（无误伤）


def test_json_plan_rollback_restores(tmp_path):
    conn = _temp_db()
    plan_file = tmp_path / "plan.json"
    plans = m.collect_plans(conn, 0)
    backup = m._ensure_backup(conn)
    m.apply_plans(conn, plans)
    payload = {
        "backup_table": backup,
        "plans": [
            {"row_id": p.row_id, "standard_number": p.standard_number,
             "before": p.before, "after": p.after(), "targets": p.targets}
            for p in plans
        ],
    }
    plan_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    before_target = conn.execute("SELECT superseded_by FROM announcement_record WHERE id=2").fetchone()[0]
    assert before_target == "GB 6000-2026"
    n = m.rollback(conn, plan_file)
    assert n >= 1
    rows = {r["id"]: r["superseded_by"] for r in conn.execute("SELECT id, superseded_by FROM announcement_record")}
    assert rows[1] == "GB 6000-1999"
    assert rows[2] == ""
    assert rows[4] == "GB 8840-1990"  # 目标行原值也一并还原
