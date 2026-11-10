"""U38 measurements: C20-C23 user-path checks + D24-D26 effect measurements.

These tests only measure current behavior; they do not change production code.
"""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.core.db import Database
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.core.status import Status
from pilotstd.core.validity_checker import ValidityChecker


def test_c20_expired_move_creates_expire_dir(tmp_path, monkeypatch):
    """C20 用户路径：废止件归档后，过期作废目录/文件是否真的出现。"""
    library = tmp_path / "library"
    monkeypatch.setenv("STANDARD_ROOT", str(library))
    db = Database(str(tmp_path / "c20.db"))
    try:
        src = tmp_path / "GB 1-2020 测试.pdf"
        src.write_bytes(b"%PDF-1.4 fake")
        FileIndexRepository(db).upsert(
            file_path=str(src),
            logical_code="GB",
            number=1,
            year=2020,
            std_name="测试",
            status=Status.ACTIVE.value,
        )
        moved = ValidityChecker(db)._move_expired_file(
            "GB 1-2020", Status.WITHDRAWN_NORMALIZED.value
        )
        assert moved, "应返回 [(旧路径, 新路径)]"
        dst = Path(moved[0][1])
        assert dst.exists()
        assert "过期作废" in dst.parts
    finally:
        db.close()


class _RealArchiveMgr:
    """真扫 + 真归档 + 真写 file_index 的 monitor 管理器替身（同 e2e）。"""

    def __init__(self, db, dst_dir: Path):
        self._repo = FileIndexRepository(db)
        self._dst_dir = dst_dir
        self.moved: list[str] = []

    def auto_run(self, root_path: str):
        parsed = []
        for f in sorted(Path(root_path).glob("*.pdf")):
            info = SimpleNamespace(
                source_path=str(f),
                logical_code="GB",
                number=19001,
                year=2020,
                std_name="测试",
            )
            parsed.append(info)
        for item in parsed:
            self._dst_dir.mkdir(parents=True, exist_ok=True)
            dst = str(self._dst_dir / Path(item.source_path).name)
            shutil.move(item.source_path, dst)
            self.moved.append(item.source_path)
            self._repo.upsert(
                file_path=dst,
                logical_code="GB",
                number=19001,
                year=2020,
                std_name="测试",
                status=Status.ACTIVE.value,
            )
        return {"scan": len(parsed), "organize_moved": len(self.moved)}


def _run_on_file_with_watch(mgr, path: str, watch_path: Path, tmp_path: Path):
    from pilotstd.monitor.scheduler import FileMonitorScheduler

    db = Database(str(tmp_path / "monitor.db"))
    scheduler = FileMonitorScheduler(manager=mgr)
    stats = MagicMock()
    with patch(
        "pilotstd.monitor.scheduler.get_config",
        return_value={"auto_archive": True, "watch_path": str(watch_path)},
    ), patch(
        "pilotstd.monitor.scheduler.resolve_monitor_config",
        return_value={"watch_path": str(watch_path)},
    ), patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=stats):
        scheduler._on_file(path)
    db.close()
    return stats


@pytest.mark.xfail(
    strict=True,
    reason="C21 确认缺陷：_cleanup_empty_dirs 在 start_dir==watch_root 时直接 return 0",
)
def test_c21_on_file_cleans_empty_child_dir(tmp_path):
    """C21 用户路径：归档后空子目录消失（必须走 _on_file，不是单测函数）。"""
    inbox = tmp_path / "inbox"
    empty = inbox / "empty_child"
    empty.mkdir(parents=True)
    src = inbox / "GB 19001-2020 测试.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    mgr = _RealArchiveMgr(None, tmp_path / "library")
    db = Database(str(tmp_path / "c21.db"))
    try:
        mgr._repo = FileIndexRepository(db)
        _run_on_file_with_watch(mgr, str(src), inbox, tmp_path)
        assert not src.exists()
        assert not empty.exists(), "归档后空子目录应被清理"
    finally:
        db.close()


def test_c22_on_file_triggers_fallback(tmp_path):
    """C22 用户路径：无标准号文件走 auto_run 的 fallback（生产编排 + monitor 链）。"""
    from pilotstd.manager.facade._auto import AutoPipeline

    calls: list[str] = []

    class _Scan:
        def scan_directory(self, root):
            return []

    class _Query:
        def query(self, parsed):
            return [], SimpleNamespace(found=0)

    class _Download:
        def download(self):
            return [], SimpleNamespace(success=0)

    class _Organize:
        def archive_standards(self, parsed):
            return {"moved": 0, "failed": 0}

        def organize_fallback(self, root):
            calls.append(root)
            return {"moved": 1}

    core = SimpleNamespace(
        cfg=SimpleNamespace(
            get=lambda key, default=None: {
                "storage.mirror_skipped_dirs": False,
                "storage.mirror_fallback": True,
            }.get(key, default)
        ),
        notification_mgr=None,
        last_skipped_dirs=[],
    )
    pipeline = AutoPipeline(core, _Scan(), _Query(), _Download(), _Organize())
    mgr = SimpleNamespace(auto_run=pipeline.auto_run)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "scan_0001.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    db = Database(str(tmp_path / "c22.db"))
    try:
        _run_on_file_with_watch(mgr, str(src), inbox, tmp_path)
        assert calls == [str(inbox)]
    finally:
        db.close()


def test_c23_pipeline_writes_effect_status(tmp_path):
    """C23 用户路径：_on_file -> auto_run -> query 后 effect_status 写回。"""
    from pilotstd.manager.classifier import QueryClassifier
    from pilotstd.manager.facade._auto import AutoPipeline
    from pilotstd.models import ParsedStdInfo
    from pilotstd.query.models import QueryResult

    seen: list[str] = []

    class _Scan:
        def scan_directory(self, root):
            return [
                ParsedStdInfo(
                    source_path="x",
                    raw_filename="HB 1-2020.pdf",
                    logical_code="HB",
                    number=1,
                    year=2020,
                    std_name="测试",
                )
            ]

    class _Query:
        def query(self, parsed):
            result = QueryResult(
                standard_number="HB 1-2020",
                standard_name="测试",
                status=Status.WITHDRAWN_NORMALIZED.value,
                match_status="newer",
            )
            qc = QueryClassifier(
                router=SimpleNamespace(apply_actions=lambda *a, **k: {}),
                query_adapters=[],
                quota_tracker=None,
                query_engine=None,
            )
            qc.classify([result], parsed, [], [], [])
            return [result], SimpleNamespace(found=1)

    class _Download:
        def download(self):
            return [], SimpleNamespace(success=0)

    class _Organize:
        def archive_standards(self, parsed):
            seen.extend(str(getattr(p, "effect_status", "")) for p in parsed)
            return {"moved": 0, "failed": 0}

        def organize_fallback(self, root):
            return {"moved": 0}

    core = SimpleNamespace(
        cfg=SimpleNamespace(get=lambda key, default=None: {
            "storage.mirror_skipped_dirs": False,
            "storage.mirror_fallback": False,
        }.get(key, default)),
        notification_mgr=None,
        last_skipped_dirs=[],
    )
    pipeline = AutoPipeline(core, _Scan(), _Query(), _Download(), _Organize())
    mgr = SimpleNamespace(auto_run=pipeline.auto_run)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "HB 1-2020.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    db = Database(str(tmp_path / "c23.db"))
    try:
        _run_on_file_with_watch(mgr, str(src), inbox, tmp_path)
        assert seen == [Status.WITHDRAWN_NORMALIZED.value]
    finally:
        db.close()


def test_d24_register_694_concurrently_has_no_unique_errors(tmp_path):
    """D24 效果：694 个不同标准并发登记，UNIQUE 错误应为 0、行数=694。"""
    db = Database(str(tmp_path / "d24.db"))
    checker = ValidityChecker(db)
    errors: list[str] = []

    def _reg(i: int) -> None:
        try:
            checker.register_new_standard(f"GB {i}-2020")
        except Exception as exc:  # noqa: BLE001 — 测量并收集
            errors.append(str(exc))

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(_reg, range(694)))
        rows = db.fetchone("SELECT COUNT(*) AS c FROM standard_validity")["c"]
        assert errors == []
        assert rows == 694
    finally:
        db.close()


def test_d25_batch_keys_for_598_import_scopes():
    """D25 效果：598 次独立导入作用域 -> 598 个批次键（不是 1 个）。"""
    from pilotstd.core.notification.batch import batch_scope, ensure_batch_key

    keys = set()
    for _ in range(598):
        with batch_scope("imp"):
            keys.add(ensure_batch_key("arch"))
    assert len(keys) == 598


def test_d25_one_batch_reuses_one_key():
    """D25 对照：同一个 batch_scope 内 598 次 archive 调用应只有 1 个键。"""
    from pilotstd.core.notification.batch import batch_scope, ensure_batch_key

    with batch_scope("imp"):
        keys = {ensure_batch_key("arch") for _ in range(598)}
    assert len(keys) == 1


def test_d26_scheduler_reuses_one_manager_across_concurrent_files(tmp_path):
    """D26 效果：同一 scheduler 并发处理 34 个目录，StandardManager 只建 1 个。"""
    import pilotstd.monitor.scheduler as scheduler_mod

    created: list[int] = []

    class _Mgr:
        def auto_run(self, root):
            return {"scan": 0, "organize_moved": 0}

    def _factory():
        created.append(1)
        return _Mgr()

    dirs = []
    for i in range(34):
        d = tmp_path / f"inbox_{i}"
        d.mkdir()
        (d / f"GB {i}-2020.pdf").write_bytes(b"%PDF-1.4 fake")
        dirs.append(d)

    sched = scheduler_mod.FileMonitorScheduler()
    with patch("pilotstd.manager.facade.StandardManager", side_effect=_factory), patch(
        "pilotstd.monitor.scheduler.get_config",
        return_value={"auto_archive": True},
    ), patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=MagicMock()):
        with ThreadPoolExecutor(max_workers=34) as pool:
            list(
                pool.map(
                    lambda pair: sched._on_file(str(pair[0] / f"GB {pair[1]}-2020.pdf")),
                    [(d, i) for i, d in enumerate(dirs)],
                )
            )
    assert len(created) == 1
