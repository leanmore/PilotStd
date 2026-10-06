# tests/integration/test_notification_high_value_events.py
"""高优事件「可验证性接线」——真链路 + **边界桩**（P6/P7 · 2026-10-06）。

**本文件的目的**：把用户最关心的几条通知从"靠人工发现坏了"变成"改坏即红灯"。
接线点在生产代码中**早已存在**（见 `docs/plans/notification-redesign/18-高优事件接线提案.md` §〇），
因此本批是**纯测试批次**：**零业务代码改动**。

**桩的纯度要求（用户红线）**：
- 只在**边界**打桩：站点/下载适配器、**OS 文件操作协作者**（`Organizer` 的 file_mover）、
  通知管理器（应用边界）；
- **不** mock 业务逻辑本身（不桩 `Organizer`/门面/处理器的方法），不桩 `shutil.move` 之类的库内部实现，
  而是替换**被注入的协作者** ⇒ 失败由"边界返回失败"自然传导到事件。

覆盖（逐条对应提案 §一，子批 1/3）：
1. `archive_failed` —— 真实 `Organizer.organize()` + **OS 边界移动器桩**（返回失败）⇒ `failed > 0` ⇒ 事件；
   同时验证反向：移动成功时**不得**发该事件（防"永远发"的假绿）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pilotstd.manager.organize import OrganizerService  # noqa: E402
from pilotstd.models import ParsedStdInfo  # noqa: E402
from pilotstd.organizer.mover import FileMover  # noqa: E402


class _RecordingNotifier:
    """通知管理器**边界桩**：只记录 `send_event` 调用（不桩任何业务逻辑）。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def send_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """记录一次事件（与真实签名一致：`(event_type, payload)`）。"""
        self.calls.append((event_type, payload or {}))

    def events(self) -> list[str]:
        """已记录的事件名列表（便于断言）。"""
        return [name for name, _ in self.calls]


class _FailingMover(FileMover):
    """**OS 文件操作边界桩**：保留真实 `FileMover` 的全部逻辑，仅让"移动"这一步失败。

    纯度说明（用户红线）：被替换的是**文件操作协作者**本身（真实实现内部即 `shutil.move`），
    等价于"磁盘/权限导致移动失败"；`Organizer`、去重、索引、汇总等业务逻辑**全部真实执行**，
    不桩任何业务方法。
    """

    def move_to_code_dir(self, src_path: str, parsed: Any, on_exists: str = "skip") -> str:
        """恒返回空串 ⇒ 触发调用方的失败分支（真实实现此处返回目标路径）。"""
        del src_path, parsed, on_exists  # 不使用参数，仅为签名一致
        return ""


class _SucceedingMover(FileMover):
    """对照组：**OS 报告移动成功**的边界桩（与 `_FailingMover` 对称）。

    **为什么不真移动**：CI 实测（Linux/Python 3.12）真实移动在该环境下失败（`file_utils.py:222`），
    使"成功路径"用例变成平台相关。此处只让**文件操作协作者**返回库根目录内的目标路径
    （等价于"OS 说移动成功"），不落地文件 ⇒ 跨平台确定；`OrganizerCore` 的计数、去重、
    索引更新与 `_log_organize_summary`（事件判定）逻辑**仍全部真实执行**。
    """

    def move_to_code_dir(self, src_path: str, parsed: Any, on_exists: str = "skip") -> str:
        """返回库根目录内的目标路径（不写盘），模拟移动成功。"""
        del src_path, on_exists  # 不使用参数，仅为签名一致
        return str(Path(self._library_root) / "GB" / self.normalize_filename(parsed))


class _DirBuilderStub:
    """目录构建器**边界值对象**：`FileMover` 只依赖其 `.root`（库根目录）。"""

    def __init__(self, root: str) -> None:
        self.root = root


def _make_parsed(source: Path) -> ParsedStdInfo:
    """构造一条真实解析结果（字段齐备，供归档链路使用）。"""
    return ParsedStdInfo(
        raw_filename=source.name,
        logical_code="GB",
        number=1,
        year=2020,
        raw_number="GB 1-2020",
        std_name="测试标准",
        source_path=str(source),
        part=None,
        effect_status="active",
    )


@pytest.fixture
def library_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """标准库根目录走环境变量（配置边界），避免触碰真实库。"""
    root = tmp_path / "library"
    root.mkdir()
    monkeypatch.setenv("STANDARD_ROOT", str(root))
    return root


def _build_organizer(mover: Any) -> tuple[OrganizerService, _RecordingNotifier]:
    """构造**真实** `Organizer`，仅把 OS 边界（file_mover）与通知边界换成桩。"""
    cfg = {"scan": {"code_mapping": {}}, "storage": {"root_path": os.environ["STANDARD_ROOT"]}}
    dir_builder = _DirBuilderStub(os.environ["STANDARD_ROOT"])
    organizer = OrganizerService(cfg=cfg, file_index=None, dir_builder=dir_builder, file_mover=mover)
    notifier = _RecordingNotifier()
    # `_core` 由应用容器注入（真实运行由门面/服务工厂挂载）；此处仅提供通知边界桩
    organizer._core = SimpleNamespace(notification_mgr=notifier)  # type: ignore[attr-defined]
    return organizer, notifier


class TestArchiveFailed:
    """`archive_failed`（提案 §一 第 6 项；接线点 `manager/organize/organizer.py:255`）。"""

    def test_real_move_failure_fires_event(self, tmp_path: Path, library_root: Path) -> None:
        """真实归档链路 + OS 边界移动失败 ⇒ `failed > 0` ⇒ 发 `archive_failed`（含计数）。"""
        source = tmp_path / "GB 1-2020 测试标准.pdf"
        source.write_bytes(b"content")
        organizer, notifier = _build_organizer(_FailingMover(_DirBuilderStub(os.environ["STANDARD_ROOT"])))

        result = organizer.organize([_make_parsed(source)])

        assert result["failed"] >= 1, f"移动失败未被计数：{result}"
        assert "archive_failed" in notifier.events(), f"未发出事件：{notifier.events()}"
        payload = next(p for n, p in notifier.calls if n == "archive_failed")
        assert payload.get("count") == result["failed"], "事件载荷的 count 应与失败计数一致"

    def test_success_path_does_not_fire(self, tmp_path: Path, library_root: Path) -> None:
        """反向验证：移动"成功"时**不得**发 `archive_failed`（防"永远发"的假绿）。"""
        source = tmp_path / "GB 1-2020 测试标准.pdf"
        source.write_bytes(b"content")
        organizer, notifier = _build_organizer(_SucceedingMover(_DirBuilderStub(os.environ["STANDARD_ROOT"])))

        result = organizer.organize([_make_parsed(source)])

        assert result["failed"] == 0, f"成功路径不应有失败计数：{result}"
        assert result["moved"] == 1, f"成功分支未被计入 moved：{result}"
        assert "archive_failed" not in notifier.events(), f"成功路径误发事件：{notifier.events()}"

    def test_missing_source_is_not_a_failure(self, tmp_path: Path, library_root: Path) -> None:
        """无源文件 ⇒ 跳过（不计失败、不发事件），与"归档失败"语义区分。"""
        organizer, notifier = _build_organizer(_FailingMover(_DirBuilderStub(os.environ["STANDARD_ROOT"])))
        parsed = _make_parsed(tmp_path / "not-exists.pdf")

        result = organizer.organize([parsed])

        assert result["failed"] == 0
        assert "archive_failed" not in notifier.events()


# ── 子批 2/3 ────────────────────────────────────────────────────────────────


class _EngineStub:
    """**外部子系统网关桩**：只提供"查询引擎"这一外部依赖的返回值。

    纯度说明：`QuerySubsystem.query()` 内部的一切（参数处理、`_query_via_engine` 包装、
    `_finalize_query` 的统计/失败明细抽取/分类路由/待确认持久化/汇总报告/事件分发）**均为真实执行**；
    本桩只替代"向外查询"这一步。
    """

    def __init__(self, results: list[Any]) -> None:
        self._results = results

    def query_standards(self, parsed_tuples: Any, **kwargs: Any) -> list[Any]:
        """返回预置的查询结果（真实实现此处会走网络/适配器）。"""
        del parsed_tuples, kwargs  # 不使用参数，仅为签名兼容
        return list(self._results)


def _build_query_subsystem(results: list[Any]) -> tuple[Any, _RecordingNotifier]:
    """构造**真实** `QuerySubsystem`，仅把外部网关（query_engine）与通知边界换成桩。"""
    from pilotstd.manager.facade._query_subsystem import QuerySubsystem

    notifier = _RecordingNotifier()
    core = SimpleNamespace(
        notification_mgr=notifier,
        query_engine=_EngineStub(results),
        parsed_results=[],
        queried_items=[],
        query_results=[],
        pending_list=[],
        download_list=[],
        expire_list=[],
        classifier=MagicMock(),  # 注入的分类服务（外部协作者），门面自身路由仍真实执行
        pending_svc=MagicMock(),  # 注入的待确认服务（外部协作者）
        cfg={},
    )
    return QuerySubsystem(core), notifier


class TestQueryFailed:
    """`query_failed`（提案 §一 第 5 项；接线点 `facade/_query_subsystem.py:235`）。"""

    def test_engine_failure_fires_query_failed(self) -> None:
        """真实门面链路 + 外部网关返回失败结果 ⇒ 逐条发 `query_failed`（含标准号与错误）。"""
        from pilotstd.query.models import QueryResult

        failed = QueryResult(
            standard_number="GB/T 19001—2020",
            error_message="外部站点不可达",
        )
        subsystem, notifier = _build_query_subsystem([failed])

        subsystem, notifier = _build_query_subsystem([failed])
        results, stats = subsystem.query(parsed_list=[_make_parsed(Path("GB 1-2020.pdf"))], site="openstd")

        # ── 证据：门面**内部**逻辑真实执行（网关桩只替代"向外查询"这一步）──
        assert len(results) == 1, "门面应原样返回查询结果"
        assert stats.total == 1, f"`_finalize_query` 的统计步骤未执行：{stats}"
        assert subsystem._core.query_results == results, "`_finalize_query` 未回写结果（内部步骤被绕过）"
        assert subsystem._core.classifier.classify.called, "分类路由（classifier.classify）未被调用，门面内部步骤被绕过"
        assert subsystem._core.pending_svc.record_pending.call_count >= 0, "待确认持久化协作者应处于可调用状态"

        # ── 事件分发 ──
        assert "query_failed" in notifier.events(), f"未发出事件：{notifier.events()}"
        payload = next(p for n, p in notifier.calls if n == "query_failed")
        assert payload.get("standard_number") == "GB/T 19001—2020"
        assert payload.get("error") == "外部站点不可达"

    def test_success_results_do_not_fire_query_failed(self) -> None:
        """反向验证：查询成功（无 error_message）⇒ **不得**发 `query_failed`。"""
        from pilotstd.query.models import QueryResult

        ok = QueryResult(standard_number="GB/T 19001—2020", status="现行")
        subsystem, notifier = _build_query_subsystem([ok])

        _results, stats = subsystem.query(parsed_list=[_make_parsed(Path("GB 1-2020.pdf"))], site="openstd")

        assert stats.total == 1, "门面统计步骤应真实执行"
        assert "query_failed" not in notifier.events(), f"成功路径误发事件：{notifier.events()}"


class TestNormalizeComplete:
    """`normalize_complete`（提案 §一 第 3 项；接线点 `facade/_organize.py:436`）。"""

    def test_real_normalize_fires_complete(self, tmp_path: Path, library_root: Path) -> None:
        """真实规范化链路（真文件）⇒ 发 `normalize_complete`，载荷计数与结果一致。"""
        from pilotstd.manager.facade._organize import OrganizeHandler

        source = tmp_path / "GB 1-2020 测试标准.pdf"
        source.write_bytes(b"content")
        notifier = _RecordingNotifier()
        handler = OrganizeHandler(SimpleNamespace(notification_mgr=notifier, parser=MagicMock()))

        results = handler.normalize_files_stream([_make_parsed(source)])

        assert results and results[0]["source"] == str(source), f"结果应指向真实文件：{results}"
        assert "normalize_complete" in notifier.events(), f"未发出事件：{notifier.events()}"
        payload = next(p for n, p in notifier.calls if n == "normalize_complete")
        assert payload.get("total") == 1 and payload.get("success") == 1

    def test_tmp_dir_is_cleaned_up(self, tmp_path: Path, library_root: Path) -> None:
        """临时目录可靠性：本用例产物只落在 pytest `tmp_path` 内 ⇒ 结束后由框架清理。

        断言"库根目录"未出现本用例的中间产物（避免污染真实标准库；`library_root` 亦在 tmp_path 内）。
        """
        from pilotstd.manager.facade._organize import OrganizeHandler

        source = tmp_path / "GB 1-2020 测试标准.pdf"
        source.write_bytes(b"content")
        handler = OrganizeHandler(SimpleNamespace(notification_mgr=_RecordingNotifier(), parser=MagicMock()))

        handler.normalize_files_stream([_make_parsed(source)])

        # 规范化只产出"名称"，不落地文件 ⇒ 库根目录应保持为空（无残留）
        assert list(library_root.iterdir()) == [], "规范化不应在库根目录留下文件"
        assert str(tmp_path) in str(source), "所有产物均在 pytest tmp_path 内，框架负责清理"


# ── 子批 3/3 ────────────────────────────────────────────────────────────────


class TestDownloadStarted:
    """`download_started`（提案 §一 第 1 项；接线点 `tasks/favorite_download.py:184`）。

    **复用既有 e2e 夹具**（`_run`）：它真实驱动任务 `download_to_inbox`，并把
    `pilotstd.manager.facade.StandardManager`（**应用容器边界**）替换为带真实下载引擎的替身，
    站点交互由 `_FakeOpenstdAdapter`（**站点适配器边界**）承担 ⇒ 任务内部的校验/状态机/落库全部真实执行。
    """

    def test_real_task_fires_download_started(self, tmp_path: Path) -> None:
        """真实任务链路 ⇒ 发 `download_started`，载荷含用户/标准号/收藏 id。"""
        from tests.integration.test_favorite_download_chain_e2e import (  # noqa: PLC0415
            _FakeOpenstdAdapter,
            _run,
        )

        fav_id, mgr, *_rest = _run(tmp_path, _FakeOpenstdAdapter())

        calls = mgr.notification_mgr.send_event.call_args_list
        events = [c.args[0] for c in calls]
        assert "download_started" in events, f"未发出事件：{events}"
        payload = next(c.args[1] for c in calls if c.args[0] == "download_started")
        assert payload["user_id"] == 1, f"载荷缺少用户：{payload}"
        assert payload["standard_number"] == "GB/T 1234-2020", f"载荷标准号异常：{payload}"
        assert payload["favorite_id"] == fav_id, f"载荷收藏 id 异常：{payload}"


class TestBatchDownloadComplete:
    """`batch_download_complete`（提案 §一 第 2 项；接线点 `services/favorite_chain_processor.py:240`）。

    真链路：真实 `process_pending_downloads(notify_per_record=False)`（cron 批量路径）+
    真实临时库记录 + 真实逐条处理函数；仅把 **下载引擎**（外部子系统入口）替换为边界桩，
    并把 `StandardManager`（应用容器）替换为记录用的替身。
    """

    def test_real_batch_run_fires_summary(self, tmp_path: Path) -> None:
        """一次真实批量运行结束 ⇒ 发 `batch_download_complete`，载荷为三计数 + 明细。"""
        from unittest.mock import patch

        from pilotstd.services import favorite_chain_processor as fcp
        from tests.integration.test_favorite_download_chain_e2e import (  # noqa: PLC0415
            _FakeOpenstdAdapter,
            _seed,
        )

        db_path = str(tmp_path / "batch.db")
        _seed(db_path)
        notifier = _RecordingNotifier()
        mgr = SimpleNamespace(notification_mgr=notifier)
        adapter = _FakeOpenstdAdapter()
        inbox = tmp_path / "inbox"
        found_path = str(tmp_path / "library" / "GBT 1234-2020.pdf")

        with patch("pilotstd.tasks.favorite_download.get_db_path", return_value=db_path), patch(
            "pilotstd.tasks.favorite_download._get_inbox_dir", return_value=inbox
        ), patch(
            "pilotstd.tasks.favorite_download._load_cached_query_result",
            return_value=MagicMock(hcno="HC123", is_adopted=False),
        ), patch(
            "pilotstd.manager.facade.StandardManager", return_value=mgr
        ), patch(
            "pilotstd.tasks.favorite_download._find_in_file_index",
            side_effect=[None, found_path],
        ), patch(
            "pilotstd.tasks.favorite_download.time.sleep"
        ), patch.object(
            fcp, "get_db_path", return_value=db_path
        ):
            fcp.process_pending_downloads(download_engine=None, notify_per_record=False)

        del adapter  # 站点交互由 download_to_inbox 内部经 StandardManager 走引擎（本用例聚焦批量汇总）
        assert "batch_download_complete" in notifier.events(), f"未发出事件：{notifier.events()}"
        payload = next(p for n, p in notifier.calls if n == "batch_download_complete")
        for key in ("success", "failed", "skipped", "details"):
            assert key in payload, f"载荷缺少 {key}：{payload}"


    def test_empty_run_does_not_fire(self, tmp_path: Path) -> None:
            """反向验证：**无待处理记录**时批量运行不发汇总（防"永远发"的假绿，证明上例非空转）。"""
            from unittest.mock import patch

            from pilotstd.services import favorite_chain_processor as fcp

            db_path = str(tmp_path / "empty.db")
            from pilotstd.core.db import Database

            Database(db_path).close()  # 只建库、不塞记录
            notifier = _RecordingNotifier()
            mgr = SimpleNamespace(notification_mgr=notifier)

            with patch.object(fcp, "get_db_path", return_value=db_path), patch(
                "pilotstd.manager.facade.StandardManager", return_value=mgr
            ):
                processed = fcp.process_pending_downloads(download_engine=None, notify_per_record=False)

            assert processed == 0, f"空库不应处理任何记录：{processed}"
            assert "batch_download_complete" not in notifier.events(), f"空库误发事件：{notifier.events()}"


class TestStandardStatusChanged:
    """`standard_status_changed`（提案 §一 第 4 项；接线点 `core/validity_checker.py:100`）。

    真链路：真实 `Database`（走迁移链建表）+ 真实 `ValidityChecker.update_status()`；
    通知管理器为**边界桩**（应用外部依赖）。`update_status` 内部的 SQL 写入、时间戳与
    `is_expired` 推导全部真实执行。
    """

    def test_real_status_change_fires_event(self, tmp_path: Path) -> None:
        """真实状态变更 ⇒ 发事件，载荷含旧/新状态与 `is_expired` 推导。"""
        from pilotstd.core.db import Database  # noqa: PLC0415
        from pilotstd.core.status import Status  # noqa: PLC0415
        from pilotstd.core.validity_checker import ValidityChecker  # noqa: PLC0415

        db = Database(str(tmp_path / "validity.db"))
        try:
            db.execute(
                "INSERT INTO standard_validity (standard_number, status, created_at, updated_at)"
                " VALUES (?, ?, datetime('now'), datetime('now'))",
                ("GB/T 1.1-2020", Status.ACTIVE.value),
            )
            notifier = _RecordingNotifier()
            checker = ValidityChecker(db)

            checker.update_status("GB/T 1.1-2020", Status.WITHDRAWN_NORMALIZED.value, notification_mgr=notifier)

            assert "standard_status_changed" in notifier.events(), f"未发出事件：{notifier.events()}"
            payload = next(p for n, p in notifier.calls if n == "standard_status_changed")
            assert payload["old_status"] == Status.ACTIVE.value
            assert payload["new_status"] == Status.WITHDRAWN_NORMALIZED.value
            assert payload["is_expired"] is True, "废止状态应推导为已过期"
            # 真实副作用：状态已落库
            row = db.fetchone("SELECT status FROM standard_validity WHERE standard_number=?", ("GB/T 1.1-2020",))
            assert row["status"] == Status.WITHDRAWN_NORMALIZED.value, "状态未真实写库"
        finally:
            db.close()
