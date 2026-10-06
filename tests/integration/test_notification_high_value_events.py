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


class _RealMoveMover(FileMover):
    """对照组：**真实执行**文件移动（真 OS 操作），用于验证成功路径**不**发 `archive_failed`。"""

    def move_to_code_dir(self, src_path: str, parsed: Any, on_exists: str = "skip") -> str:
        """在库根目录下真实创建目标文件并移动（真 OS 操作），返回目标路径。"""
        target_dir = Path(self._library_root) / "GB"
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / self.normalize_filename(parsed)
        self.archive(src_path, str(dst), on_exists=on_exists)
        return str(dst) if Path(dst).exists() else ""


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
        organizer, notifier = _build_organizer(_RealMoveMover(_DirBuilderStub(os.environ["STANDARD_ROOT"])))

        result = organizer.organize([_make_parsed(source)])

        assert result["failed"] == 0, f"成功路径不应有失败计数：{result}"
        assert "archive_failed" not in notifier.events(), f"成功路径误发事件：{notifier.events()}"

    def test_missing_source_is_not_a_failure(self, tmp_path: Path, library_root: Path) -> None:
        """无源文件 ⇒ 跳过（不计失败、不发事件），与"归档失败"语义区分。"""
        organizer, notifier = _build_organizer(_FailingMover(_DirBuilderStub(os.environ["STANDARD_ROOT"])))
        parsed = _make_parsed(tmp_path / "not-exists.pdf")

        result = organizer.organize([parsed])

        assert result["failed"] == 0
        assert "archive_failed" not in notifier.events()
