# tests/download/test_engine_save_guard.py — U56 §7.3：_save_file 安全拒绝与统计分类
"""覆盖 `pilotstd/download/engine.py` 落盘前最后一道防线（D2-1/D2-2）与批量统计/通知。

10 例：路径越界、非 PDF、文档过小、原子写、replace 失败清理、
五类失败分类、error 状态计数、通知载荷、通知异常不冒泡、重试后放弃。
"""

from __future__ import annotations

from types import SimpleNamespace

import requests

from pilotstd.download import engine as engine_mod
from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import BatchDownloadStats, DownloadStatus, DownloadTask


class _Session:
    def delay(self) -> None:
        return None


class _Adapter:
    site_name = "fake"

    def __init__(self, content: bytes | None = None, exc: Exception | None = None) -> None:
        self._content = content
        self._exc = exc

    def download(self, task):  # noqa: ANN001
        if self._exc is not None:
            raise self._exc
        return self._content


def _engine(tmp_path, max_retries: int = 2) -> DownloadEngine:
    return DownloadEngine(
        adapters=[],
        session_manager=_Session(),
        save_root=str(tmp_path),
        max_retries=max_retries,
        max_workers=1,
        min_delay=0,
        max_delay=0,
        long_rest=0,
    )


def _task(number: str = "GB/T 1-2020") -> DownloadTask:
    return DownloadTask(standard_number=number)


# ── 1) 路径越界 ────────────────────────────────────────────────────────


def test_save_file_rejects_path_outside_root(tmp_path, monkeypatch) -> None:
    """validate_path_in_root 抛 ValueError → False + “路径校验失败”。"""
    eng = _engine(tmp_path)
    monkeypatch.setattr(eng, "_resolve_target_path", lambda task: str(tmp_path / "x.pdf"))

    def _boom(path, root):
        raise ValueError("outside root")

    monkeypatch.setattr(engine_mod, "validate_path_in_root", _boom)
    task = _task()

    assert eng._save_file(task, b"%PDF-1.4 ok", _Adapter()) is False
    assert task.error_message == "路径校验失败"


# ── 2) 非 PDF 魔数 ─────────────────────────────────────────────────────


def test_save_file_rejects_non_pdf_magic(tmp_path, monkeypatch) -> None:
    """.pdf + HTML → 拒绝，错误信息含“非 PDF”。"""
    eng = _engine(tmp_path)
    monkeypatch.setattr(eng, "_resolve_target_path", lambda task: str(tmp_path / "x.pdf"))
    task = _task()

    assert eng._save_file(task, b"<html>error page</html>", _Adapter()) is False
    assert "非 PDF" in task.error_message
    assert not (tmp_path / "x.pdf").exists()


# ── 3) 文档过小 ────────────────────────────────────────────────────────


def test_save_file_rejects_too_small_docx(tmp_path, monkeypatch) -> None:
    """.docx + 100 字节 → 拒绝。"""
    eng = _engine(tmp_path)
    monkeypatch.setattr(eng, "_resolve_target_path", lambda task: str(tmp_path / "x.docx"))
    task = _task()

    assert eng._save_file(task, b"x" * 100, _Adapter()) is False
    assert "过小" in task.error_message


# ── 4) 原子写 ──────────────────────────────────────────────────────────


def test_save_file_writes_atomically(tmp_path, monkeypatch) -> None:
    """成功 → 无 .part 残留、saved_path 正确。"""
    eng = _engine(tmp_path)
    target = tmp_path / "ok.pdf"
    monkeypatch.setattr(eng, "_resolve_target_path", lambda task: str(target))
    task = _task()

    assert eng._save_file(task, b"%PDF-1.7\nbody", _Adapter()) is True
    assert task.saved_path == str(target)
    assert target.read_bytes().startswith(b"%PDF-")
    assert not list(tmp_path.glob("*.part"))


# ── 5) os.replace 失败清理 .part ───────────────────────────────────────


def test_save_file_cleans_part_when_replace_fails(tmp_path, monkeypatch) -> None:
    """mock os.replace 抛 OSError → .part 被清理、返回 False。"""
    eng = _engine(tmp_path)
    target = tmp_path / "bad.pdf"
    monkeypatch.setattr(eng, "_resolve_target_path", lambda task: str(target))

    def _boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(engine_mod.os, "replace", _boom)
    task = _task()

    assert eng._save_file(task, b"%PDF-1.7\nbody", _Adapter()) is False
    assert task.error_message == "disk full"
    assert not (tmp_path / "bad.pdf.part").exists()
    assert not target.exists()


# ── 6) 五类失败分类 ────────────────────────────────────────────────────


def test_collect_batch_stats_classifies_error_types() -> None:
    """timeout / network / parse / not_found / unknown 五类映射正确。"""
    msgs = [
        "request timeout",
        "connection refused by peer",
        "parse error: invalid json",
        "404 not found",
        "something odd happened",
    ]
    ids = ["GB 1", "GB 2", "GB 3", "GB 4", "GB 5"]
    tasks = []
    for number, msg in zip(ids, msgs):
        t = DownloadTask(standard_number=number, status=DownloadStatus.FAILED, error_message=msg)
        t.query_result = SimpleNamespace(std_name=f"name-{number}")
        tasks.append(t)
    stats = BatchDownloadStats(total=len(tasks))

    DownloadEngine._collect_batch_stats(tasks, stats)

    assert [item["error_type"] for item in stats.failed_items] == [
        "timeout",
        "network",
        "parse",
        "not_found",
        "unknown",
    ]
    assert stats.failed == 5
    assert stats.failed_items[0]["standard_name"] == "name-GB 1"


# ── 7) error 状态计数 ──────────────────────────────────────────────────


def test_collect_batch_stats_counts_error_status() -> None:
    """非 success/skipped/failed 状态 → stats.errors += 1。"""
    task = DownloadTask(standard_number="GB 9", status=DownloadStatus.RUNNING)
    stats = BatchDownloadStats(total=1)

    DownloadEngine._collect_batch_stats([task], stats)

    assert stats.errors == 1
    assert stats.failed_items == []


# ── 8) 通知载荷 ────────────────────────────────────────────────────────


def test_notify_download_complete_payload_has_failed_items() -> None:
    """载荷含 failed_items、correlation_id，且 failed = failed + errors。"""
    sent: list[tuple] = []

    class _Mgr:
        def send_event(self, event, payload, context=None):  # noqa: ANN001
            sent.append((event, payload, context))

    stats = BatchDownloadStats(total=3, success=1, failed=1, errors=1, skipped_adopted=0)
    stats.failed_items = [{"standard_number": "GB 1", "standard_name": "-", "error_type": "network"}]

    DownloadEngine._notify_download_complete(_Mgr(), stats, correlation_id="cid-1")

    event, payload, _ctx = sent[0]
    assert event == "batch_download_complete"
    assert payload["correlation_id"] == "cid-1"
    assert payload["failed_items"] == stats.failed_items
    assert payload["failed"] == 2


# ── 9) 通知异常不冒泡 ──────────────────────────────────────────────────


def test_notify_download_complete_swallows_exception() -> None:
    """通知抛错 → 不冒泡。"""

    class _Mgr:
        def send_event(self, *a, **kw):  # noqa: ANN002, ANN003
            raise RuntimeError("notify down")

    DownloadEngine._notify_download_complete(_Mgr(), BatchDownloadStats(total=0))


# ── 10) 重试后放弃 ─────────────────────────────────────────────────────


def test_download_batch_retries_then_gives_up(tmp_path, monkeypatch) -> None:
    """首次网络失败 → RETRYING；第二次失败 → FAILED，统计为 network 失败。"""
    eng = _engine(tmp_path, max_retries=1)
    monkeypatch.setattr(eng, "_resolve_target_path", lambda task: str(tmp_path / "none.pdf"))
    adapter = _Adapter(exc=requests.ConnectionError("connection reset"))
    monkeypatch.setattr(eng, "_find_adapter", lambda task: adapter)
    task = _task()

    eng.download_single(task)
    assert task.status == DownloadStatus.RETRYING
    assert task.retry_count == 1

    eng.download_single(task)
    assert task.status == DownloadStatus.FAILED

    stats = BatchDownloadStats(total=1)
    DownloadEngine._collect_batch_stats([task], stats)
    assert stats.failed == 1
    assert stats.failed_items[0]["error_type"] == "network"
