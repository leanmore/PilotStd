# tests/integration/test_monitor_catchup_e2e.py
"""P3-16 / 08#23：monitor 启动补扫端到端（先写失败用例）。

口径：
- 「启动前放入的文件」= 无 watchdog 事件 ⇒ 只能靠启动补扫发现；
- 补扫按**有文件的目录**分批（递归时祖先目录折叠子目录），每批调用一次 `auto_run`；
- 真实搬文件 + 真实写 `file_index`，不是 mock 返回值；
- watermark 只放行比上次补扫开始时间更新的文件；首次（watermark=0）必须全处理。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pilotstd.core.db import Database  # noqa: E402
from pilotstd.core.file_index import FileIndexRepository  # noqa: E402
from pilotstd.core.status import Status  # noqa: E402
from pilotstd.monitor import scheduler as scheduler_mod  # noqa: E402
from pilotstd.monitor.handler import StandardFileHandler  # noqa: E402
from pilotstd.monitor.scheduler import FileMonitorScheduler  # noqa: E402
from pilotstd.organizer.industry_lookup import build_code_mapping  # noqa: E402
from pilotstd.scan.parser import StandardParser  # noqa: E402

_PDF = b"%PDF-1.4 fake standard full text"


class _RecursiveArchiveMgr:
    """真递归扫目录 + 真解析 + 真搬文件 + 真写索引的管理器替身。"""

    def __init__(self, db, dst_dir: Path):
        self._parser = StandardParser(build_code_mapping())
        self._repo = FileIndexRepository(db)
        self._dst = dst_dir
        self.auto_run_roots: list[str] = []
        self.moved: list[Path] = []
        self.delay = 0.0

    def scan_directory(self, root_path: str):
        parsed = []
        for f in sorted(Path(root_path).rglob("*.pdf")):
            info = self._parser.parse(f.name)
            if info:
                info.source_path = str(f)
                parsed.append(info)
        return parsed

    def auto_run(self, root_path: str):
        self.auto_run_roots.append(str(root_path))
        if self.delay:
            time.sleep(self.delay)
        parsed = self.scan_directory(root_path)
        self._dst.mkdir(parents=True, exist_ok=True)
        for item in parsed:
            dst = self._dst / Path(item.source_path).name
            os.replace(item.source_path, dst)
            self.moved.append(dst)
            self._repo.upsert(
                file_path=str(dst),
                logical_code=item.logical_code,
                number=item.number,
                year=item.year,
                std_name="测试标准",
                status=Status.ACTIVE.value,
            )
        return {
            "scan": len(parsed),
            "query_found": len(parsed),
            "download_success": 0,
            "organize_moved": len(parsed),
            "organize_failed": 0,
        }


def _cfg(watch_path: Path, **overrides) -> dict:
    cfg = {
        "enabled": True,
        "watch_path": str(watch_path),
        "delay_seconds": 1,
        "recursive": True,
        "auto_archive": True,
        "scan_existing_on_start": True,
        "file_patterns": [".pdf", ".docx", ".doc"],
        "ignore_patterns": ["~$", ".tmp", ".swp"],
    }
    cfg.update(overrides)
    return cfg


def _increments(stats: MagicMock) -> dict[str, int]:
    out: dict[str, int] = {}
    for call in stats.increment.call_args_list:
        out[call.args[0]] = out.get(call.args[0], 0) + 1
    return out


def _wait_until(predicate, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def env(tmp_path, monkeypatch):
    """真实 DB + 真实管理器替身 + 补扫相关 DB 读写替换为内存实现。"""
    monkeypatch.delenv("PILOTSTD_STORAGE_INBOX_DIR", raising=False)
    db_path = str(tmp_path / "monitor.db")
    Database(db_path).close()
    db = Database(db_path)
    mgr = _RecursiveArchiveMgr(db, tmp_path / "library")
    stats = MagicMock()
    state: dict[str, object] = {"watermark": 0.0, "saved": [], "last": "", "last_saved": []}

    monkeypatch.setattr(scheduler_mod, "get_monitor_stats", lambda: stats)
    monkeypatch.setattr(
        scheduler_mod, "get_catchup_watermark", lambda: float(state["watermark"])
    )
    monkeypatch.setattr(
        scheduler_mod,
        "set_catchup_watermark",
        lambda ts: (state["saved"].append(ts), state.__setitem__("watermark", ts)),
    )
    monkeypatch.setattr(scheduler_mod, "get_last_processed", lambda: str(state["last"]))
    monkeypatch.setattr(
        scheduler_mod,
        "set_last_processed",
        lambda path: (state["last_saved"].append(path), state.__setitem__("last", path)),
    )
    yield {
        "tmp": tmp_path,
        "db": db,
        "mgr": mgr,
        "stats": stats,
        "state": state,
        "monkeypatch": monkeypatch,
    }
    db.close()


@pytest.mark.integration
class TestMonitorCatchupEndToEnd:
    def test_start_processes_preexisting_files_and_archives(self, env):
        """启动前放 3 个文件（2 个目录）→ 启动后全部搬走并写索引；2 批。"""
        inbox = env["tmp"] / "inbox"
        (inbox / "GB 国家标准").mkdir(parents=True)
        (inbox / "SH 石油化工").mkdir(parents=True)
        (inbox / "GB 国家标准" / "GB 19001-2020 质量管理体系.pdf").write_bytes(_PDF)
        (inbox / "GB 国家标准" / "GB 19002-2020 环境管理体系.pdf").write_bytes(_PDF)
        (inbox / "SH 石油化工" / "SH 3001-2019 石油化工设计.pdf").write_bytes(_PDF)

        env["monkeypatch"].setattr(scheduler_mod, "get_config", lambda: _cfg(inbox))
        scheduler = FileMonitorScheduler(manager=env["mgr"])
        scheduler.start()
        try:
            assert _wait_until(lambda: len(env["mgr"].auto_run_roots) == 2), env["mgr"].auto_run_roots
            assert _wait_until(lambda: len(env["mgr"].moved) == 3)
        finally:
            scheduler.stop()

        assert sorted(Path(p).name for p in env["mgr"].auto_run_roots) == [
            "GB 国家标准",
            "SH 石油化工",
        ]
        assert not list(inbox.rglob("*.pdf")), "补扫后 inbox 不应再有文件"
        assert len(list((env["tmp"] / "library").glob("*.pdf"))) == 3
        inc = _increments(env["stats"])
        assert inc.get("processed") == 2, inc
        assert inc.get("success") == 2, inc
        assert env["state"]["saved"], "补扫完成必须推进 watermark"
        assert env["state"]["last_saved"], "last_processed 必须落库"

    def test_nested_dirs_collapse_to_ancestor_batch(self, env):
        """递归时祖先目录折叠：GB 根与其 2020 子目录只算 1 批，文件仍全部搬走。"""
        inbox = env["tmp"] / "inbox"
        (inbox / "GB 国家标准" / "2020").mkdir(parents=True)
        (inbox / "SH 石油化工").mkdir(parents=True)
        (inbox / "GB 国家标准" / "GB 1-2020 A.pdf").write_bytes(_PDF)
        (inbox / "GB 国家标准" / "2020" / "GB 2-2020 B.pdf").write_bytes(_PDF)
        (inbox / "SH 石油化工" / "SH 3-2019 C.pdf").write_bytes(_PDF)

        env["monkeypatch"].setattr(scheduler_mod, "get_config", lambda: _cfg(inbox))
        env["mgr"].auto_run_roots.clear()
        scheduler = FileMonitorScheduler(manager=env["mgr"])
        scheduler.handler = StandardFileHandler(callback=lambda p: None, delay_seconds=0)
        scheduler._catch_up_existing(threading.Event())

        assert sorted(Path(p).name for p in env["mgr"].auto_run_roots) == [
            "GB 国家标准",
            "SH 石油化工",
        ]
        assert len(env["mgr"].moved) == 3

    def test_watermark_skips_older_files(self, env):
        """watermark 语义是**目录级**：整目录都旧 → 跳过；目录里有新文件 → 整批处理。"""
        inbox = env["tmp"] / "inbox"
        old_dir = inbox / "GB 国家标准"
        new_dir = inbox / "SH 石油化工"
        old_dir.mkdir(parents=True)
        new_dir.mkdir(parents=True)
        old = old_dir / "GB 1-2020 旧文件.pdf"
        new = new_dir / "SH 2-2020 新文件.pdf"
        old.write_bytes(_PDF)
        new.write_bytes(_PDF)
        os.utime(old, (1000.0, 1000.0))
        env["state"]["watermark"] = 2000.0

        env["monkeypatch"].setattr(scheduler_mod, "get_config", lambda: _cfg(inbox))
        scheduler = FileMonitorScheduler(manager=env["mgr"])
        scheduler.handler = StandardFileHandler(callback=lambda p: None, delay_seconds=0)
        scheduler._catch_up_existing(threading.Event())

        assert env["mgr"].auto_run_roots == [str(new_dir)], env["mgr"].auto_run_roots
        assert old.exists(), "只有旧文件的目录必须整目录跳过"
        assert not new.exists()
        assert env["state"]["saved"] and env["state"]["saved"][0] > 2000.0

    def test_disabled_config_does_not_scan(self, env):
        """scan_existing_on_start=false：启动不补扫（存量留给手动）。"""
        inbox = env["tmp"] / "inbox"
        inbox.mkdir()
        (inbox / "GB 1-2020 A.pdf").write_bytes(_PDF)
        env["monkeypatch"].setattr(
            scheduler_mod, "get_config", lambda: _cfg(inbox, scan_existing_on_start=False)
        )
        scheduler = FileMonitorScheduler(manager=env["mgr"])
        scheduler.start()
        time.sleep(1.0)
        try:
            assert env["mgr"].auto_run_roots == []
        finally:
            scheduler.stop()

    def test_stop_interrupts_long_catchup(self, env):
        """补扫可被 stop 打断（不再继续跑剩余目录）。"""
        inbox = env["tmp"] / "inbox"
        for i in range(5):
            d = inbox / f"D{i}"
            d.mkdir(parents=True)
            (d / f"GB {i + 1}-2020 A.pdf").write_bytes(_PDF)
        env["monkeypatch"].setattr(scheduler_mod, "get_config", lambda: _cfg(inbox))
        env["mgr"].delay = 0.4
        scheduler = FileMonitorScheduler(manager=env["mgr"])
        scheduler.start()
        try:
            assert _wait_until(lambda: len(env["mgr"].auto_run_roots) >= 1, timeout=5)
        finally:
            scheduler.stop()
        assert len(env["mgr"].auto_run_roots) < 5, env["mgr"].auto_run_roots

    def test_on_file_records_last_processed(self, env):
        """事件路径同样刷新 last_processed（状态页可看到最后处理文件）。"""
        inbox = env["tmp"] / "inbox"
        inbox.mkdir()
        f = inbox / "GB 19001-2020 质量管理体系.pdf"
        f.write_bytes(_PDF)
        env["monkeypatch"].setattr(scheduler_mod, "get_config", lambda: _cfg(inbox))
        scheduler = FileMonitorScheduler(manager=env["mgr"])
        scheduler._on_file(str(f))
        assert env["state"]["last_saved"] == [str(f)]
