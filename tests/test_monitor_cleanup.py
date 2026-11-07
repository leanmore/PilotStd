"""monitor 归档后空目录清理：只删空目录，不删 watch_root。"""

from pilotstd.monitor.scheduler import _cleanup_empty_dirs


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
