"""monitor 归档后空目录清理：只删空目录（含仅系统垃圾的目录），不删 watch_root。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from pilotstd.monitor.scheduler import _cleanup_empty_dirs


def _junk_dir(path: Path, *names: str) -> Path:
    """建一个只含系统垃圾文件（Thumbs.db / ~$ 锁文件）的目录。"""
    path.mkdir(parents=True, exist_ok=True)
    for name in names or ("Thumbs.db",):
        (path / name).write_bytes(b"junk")
    return path


def test_cleanup_empty_child_dirs(tmp_path):
    root = tmp_path / "inbox"
    empty = root / "a" / "b"
    empty.mkdir(parents=True)
    keep = root / "keep"
    keep.mkdir()
    (keep / "file.pdf").write_bytes(b"%PDF-1.4")

    removed = _cleanup_empty_dirs(str(root), str(root / "a"))

    assert removed == 2
    assert not (root / "a").exists()
    assert keep.exists()
    assert (keep / "file.pdf").exists()


def test_cleanup_removes_deeply_nested_empty_dirs(tmp_path):
    """源目录下 3 层嵌套空目录必须一次递归清到底，而不是只清最内层。"""
    root = tmp_path / "inbox"
    (root / "a" / "b" / "c").mkdir(parents=True)

    removed = _cleanup_empty_dirs(str(root), str(root / "a"))

    assert removed == 3, "深层空目录必须递归清理"
    assert not (root / "a").exists()


def test_cleanup_removes_junk_only_dirs(tmp_path):
    """只有 Thumbs.db / ~$ 锁文件的目录也算空目录（与 remove_empty_dirs 同口径）。"""
    root = tmp_path / "inbox"
    batch = root / "batch"
    _junk_dir(batch / "nested", "Thumbs.db")
    _junk_dir(batch, "Thumbs.db", "~$GB 1-2020.docx")

    removed = _cleanup_empty_dirs(str(root), str(batch))

    assert removed == 2, "仅含系统垃圾文件的目录应按空目录清理"
    assert not batch.exists()
    assert root.exists()


def test_cleanup_keeps_non_empty_dir_and_its_junk(tmp_path):
    """非空目录（哪怕带 Thumbs.db）必须保留，且不删其中的垃圾文件。"""
    root = tmp_path / "inbox"
    keep = root / "keep"
    keep.mkdir(parents=True)
    (keep / "Thumbs.db").write_bytes(b"junk")
    (keep / "real.pdf").write_bytes(b"%PDF-1.4")

    removed = _cleanup_empty_dirs(str(root), str(keep))

    assert removed == 0
    assert (keep / "real.pdf").exists()
    assert (keep / "Thumbs.db").exists()


def test_cleanup_prunes_empty_ancestors(tmp_path):
    """文件在 inbox/a/b/c 时，归档后 a/b/c 三层都不应留下（watch_root 保留）。"""
    root = tmp_path / "inbox"
    leaf = root / "a" / "b" / "c"
    leaf.mkdir(parents=True)
    keep = root / "keep"
    keep.mkdir()
    (keep / "f.pdf").write_bytes(b"%PDF-1.4")

    removed = _cleanup_empty_dirs(str(root), str(leaf))

    assert removed == 3, "空祖先目录也要向上收掉"
    assert not (root / "a").exists()
    assert root.exists()
    assert keep.exists()


def test_cleanup_from_watch_root_removes_nested_empty_and_junk(tmp_path):
    """文件直接放在 Inbox 根时，根下多层空目录/垃圾目录仍要清理，根本身保留。"""
    root = tmp_path / "inbox"
    _junk_dir(root / "batch" / "junk", "Thumbs.db")
    (root / "empty" / "deep").mkdir(parents=True)

    removed = _cleanup_empty_dirs(str(root), str(root))

    assert removed == 4
    assert root.exists()
    assert not (root / "batch").exists()
    assert not (root / "empty").exists()


def test_cleanup_prune_stops_at_non_empty_ancestor(tmp_path):
    """向上收空祖先时遇到第一个非空目录必须停下，不能越级删。"""
    root = tmp_path / "inbox"
    leaf = root / "a" / "b" / "c"
    leaf.mkdir(parents=True)
    keep = root / "a" / "keep"
    keep.mkdir()
    (keep / "f.pdf").write_bytes(b"%PDF-1.4")

    removed = _cleanup_empty_dirs(str(root), str(leaf))

    assert removed == 2
    assert not (root / "a" / "b").exists()
    assert (root / "a").exists()
    assert keep.exists()


def test_cleanup_never_touches_watch_root_junk(tmp_path):
    """watch_root 本身连同其中的垃圾文件都不动。"""
    root = tmp_path / "inbox"
    root.mkdir()
    (root / "Thumbs.db").write_bytes(b"junk")

    assert _cleanup_empty_dirs(str(root), str(root)) == 0
    assert (root / "Thumbs.db").exists()


def test_cleanup_never_removes_watch_root(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()

    assert _cleanup_empty_dirs(str(root), str(root)) == 0
    assert root.exists()


def test_cleanup_outside_watch_root_is_noop(tmp_path):
    root = tmp_path / "inbox"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    assert _cleanup_empty_dirs(str(root), str(outside)) == 0
    assert outside.exists()


class _MovingManager:
    """把源目录里的 pdf 搬走的 manager 替身（模拟归档后源目录留下空目录）。"""

    def __init__(self, dst: Path):
        self.dst = dst
        self.moved: list[str] = []

    def auto_run(self, root_path: str) -> dict:
        self.dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(Path(root_path).rglob("*.pdf")):
            f.replace(self.dst / f.name)
            self.moved.append(str(f))
        return {"scan": len(self.moved), "organize_moved": len(self.moved), "organize_failed": 0}


def test_on_file_triggers_cleanup_of_nested_and_junk_dirs(tmp_path):
    """用户路径：`_on_file` 归档完一批后，源目录下多层空目录 + 仅垃圾目录都要被清掉。"""
    from pilotstd.monitor.scheduler import FileMonitorScheduler

    inbox = tmp_path / "inbox"
    batch = inbox / "batch"
    src = batch / "GB 1-2020.pdf"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"%PDF-1.4")
    _junk_dir(batch / "only-thumbs", "Thumbs.db")
    (batch / "level1" / "level2").mkdir(parents=True)

    library = tmp_path / "library"
    scheduler = FileMonitorScheduler(manager=_MovingManager(library))
    stats = MagicMock()
    with (
        patch(
            "pilotstd.monitor.scheduler.get_config",
            return_value={"auto_archive": True, "watch_path": str(inbox)},
        ),
        patch(
            "pilotstd.monitor.scheduler.resolve_monitor_config",
            return_value={"watch_path": str(inbox)},
        ),
        patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=stats),
        patch("pilotstd.monitor.scheduler.set_last_processed"),
    ):
        scheduler._on_file(str(src))

    assert not src.exists()
    assert (library / src.name).exists()
    assert not batch.exists(), "归档后源目录（含空子目录/垃圾目录）应整体清理"
    assert inbox.exists(), "watch_root 必须保留"
    stats.increment.assert_any_call("success")
