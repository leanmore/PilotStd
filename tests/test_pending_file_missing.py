"""A-46 本地回归：pending 记录路径不存在 → file_missing（构造临时目录，不依赖生产）。"""

from __future__ import annotations

from pathlib import Path

from pilotstd.manager.pending_service import mark_missing_files, resolve_reason


def test_resolve_reason_rules():
    assert resolve_reason({"file_path": "", "reason": "pending"}, exists=False) == "no_file"
    assert resolve_reason({"file_path": "/x/a.pdf", "reason": "pending"}, exists=False) == "file_missing"
    assert resolve_reason({"file_path": "/x/a.pdf", "reason": "archive_conflict"}, exists=True) == "archive_conflict"


class _DB:
    """最小 DB 替身：只实现 fetchall / execute。"""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = [dict(r) for r in rows]
        self.updated: list[tuple[int, str]] = []

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.rows]

    def execute(self, sql: str, params: tuple = ()) -> None:
        if sql.startswith("UPDATE pending_lookup SET reason"):
            self.updated.append((params[0], params[1] if len(params) > 1 else ""))


def test_mark_missing_files_with_temp_dir(tmp_path: Path):
    """真实存在的文件不动；不存在的标 file_missing；空路径不算 missing。"""
    existing = tmp_path / "exists.pdf"
    existing.write_bytes(b"%PDF")

    db = _DB(
        [
            {"id": 1, "file_path": str(existing), "reason": "pending", "status": "pending"},
            {"id": 2, "file_path": str(tmp_path / "gone.pdf"), "reason": "pending", "status": "pending"},
            {"id": 3, "file_path": "", "reason": "no_file", "status": "pending"},
        ]
    )
    stats = mark_missing_files(db)
    assert stats["checked"] == 3
    assert stats["missing"] == 1          # 只有 id=2
    assert stats["updated"] == 1
    assert [u[0] for u in db.updated] == [2]
