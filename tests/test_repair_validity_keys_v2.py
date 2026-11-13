"""P2-11 一次性修复脚本（dry-run/apply/备份）的受控测试。"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from pilotstd.core.db import Database

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "repair_validity_keys_v2.py"

TSG_CASES = [
    ("11", "2020", "TSG 11-2020", "锅炉安全技术规程", "锅炉安全技术规程 第1号修改单"),
    ("23", "2021", "TSG 23-2021", "气瓶安全技术规程", "气瓶安全技术规程 第1号修改单"),
    ("7", "2019", "TSG 7-2019", "特种设备生产和充装单位许可规则", "特种设备生产和充装单位许可规则 第2号修改单"),
    ("8001", "2019", "TSG 8001-2019", "特种设备无损检测人员考核规则", "特种设备无损检测人员考核规则 第1号修改单"),
    ("8002", "2022", "TSG 8002-2022", "特种设备检验人员考核规则", "特种设备检验人员考核规则 第1号修改单"),
]


def _load():
    spec = importlib.util.spec_from_file_location("repair_validity_keys_v2", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 注解解析需要模块已注册
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "pilotstd.db")
    Database(path).close()
    conn = sqlite3.connect(path)
    for i, (num, year, _canonical, main_name, amendment) in enumerate(TSG_CASES):
        conn.execute(
            "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status) "
            "VALUES (?,?,?,?,?,?,?)",
            (f"/standards/TSG/main-{i}.pdf", "TSG", int(num), int(year), -1, main_name, "现行"),
        )
        conn.execute(
            "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status) "
            "VALUES (?,?,?,?,?,?,?)",
            (f"/standards/T/amend-{i}.docx", "T/SG", int(num), int(year), -1, amendment, "现行"),
        )
    # 唯一主代号、且规范键不存在 → rename
    conn.execute(
        "INSERT INTO file_index (file_path, logical_code, number, year, part, std_name, status) "
        "VALUES (?,?,?,?,?,?,?)",
        ("/standards/GB/only-1.pdf", "GB", 9999, 2020, -1, "测试标准", "现行"),
    )
    for i, (num, year, canonical, _m, _a) in enumerate(TSG_CASES):
        conn.execute(
            "INSERT INTO standard_validity (standard_number, status, check_count, last_checked_at) "
            "VALUES (?,?,?,?)",
            (canonical, "未知", 0, None),
        )
        conn.execute(
            "INSERT INTO standard_validity (standard_number, status, check_count, last_checked_at) "
            "VALUES (?,?,?,?)",
            (f" {num}-{year}", "现行" if i == 0 else "未知", i + 2, f"2026-11-0{i + 1}T03:00:00+00:00"),
        )
    # 2 条无证据 + 1 条可改名
    conn.execute(
        "INSERT INTO standard_validity (standard_number, status, check_count) VALUES (?,?,?)",
        (" 19001-2020", "未知", 2),
    )
    conn.execute(
        "INSERT INTO standard_validity (standard_number, status, check_count) VALUES (?,?,?)",
        (" 47008-1947", "未知", 2),
    )
    conn.execute(
        "INSERT INTO standard_validity (standard_number, status, check_count) VALUES (?,?,?)",
        (" 9999-2020", "未知", 2),
    )
    conn.commit()
    conn.close()
    return path


def test_plan_merges_five_marks_two_manual_and_one_rename(db_path):
    mod = _load()
    conn = sqlite3.connect(db_path)
    try:
        repairs = mod.plan_repairs(conn)
    finally:
        conn.close()
    by_key = {r.malformed: r for r in repairs}
    assert len(repairs) == 8
    for num, year, canonical, _m, _a in TSG_CASES:
        assert by_key[f" {num}-{year}"].action == "merge"
        assert by_key[f" {num}-{year}"].canonical == canonical
    assert by_key[" 19001-2020"].action == "manual_required"
    assert by_key[" 47008-1947"].action == "manual_required"
    assert by_key[" 9999-2020"].action == "rename"


def test_dry_run_does_not_write(db_path, capsys):
    mod = _load()
    assert mod.main(["--db", db_path]) == 0
    out = capsys.readouterr().out
    assert "dry-run only" in out
    conn = sqlite3.connect(db_path)
    try:
        kept = conn.execute(
            "SELECT COUNT(*) FROM standard_validity WHERE standard_number=' 11-2020'"
        ).fetchone()[0]
        assert kept == 1
        assert not list(Path(db_path).parent.glob("*.bak-*"))
    finally:
        conn.close()


def test_apply_merges_backs_up_and_is_idempotent(db_path, capsys):
    mod = _load()
    assert mod.main(["--db", db_path, "--apply"]) == 0
    out = capsys.readouterr().out
    assert "backup:" in out and "applied:" in out
    backups = list(Path(db_path).parent.glob("*.bak-*"))
    assert len(backups) == 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # 5 条畸形键已消失，规范键保留了更"好"的状态/计数
        for num, year, canonical, _m, _a in TSG_CASES:
            assert conn.execute(
                "SELECT COUNT(*) FROM standard_validity WHERE standard_number=?", (f" {num}-{year}",)
            ).fetchone()[0] == 0
            row = conn.execute(
                "SELECT status, check_count FROM standard_validity WHERE standard_number=?", (canonical,)
            ).fetchone()
            assert row is not None
        first = conn.execute(
            "SELECT status, check_count FROM standard_validity WHERE standard_number='TSG 11-2020'"
        ).fetchone()
        assert first["status"] == "现行"
        assert first["check_count"] == 2
        # manual_required 保持原样
        assert conn.execute(
            "SELECT COUNT(*) FROM standard_validity WHERE standard_number IN (' 19001-2020',' 47008-1947')"
        ).fetchone()[0] == 2
        # rename 生效
        assert conn.execute(
            "SELECT COUNT(*) FROM standard_validity WHERE standard_number='GB 9999-2020'"
        ).fetchone()[0] == 1
    finally:
        conn.close()

    # 第二次运行：不再有可修项
    repairs = []
    conn = sqlite3.connect(db_path)
    try:
        repairs = mod.plan_repairs(conn)
    finally:
        conn.close()
    assert {r.action for r in repairs} == {"manual_required"}
    assert len(repairs) == 2
