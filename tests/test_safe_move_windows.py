"""B3：safe_move 的 Windows 特例（长路径 / 文件占用 / 跨盘符）。"""

import os
import sys

import pytest

from pilotstd.core.file_utils import _win_long_path, safe_move


def _make_long_path(base, depth=8, width=45):
    path = base
    for i in range(depth):
        path = os.path.join(path, f"d{i:02d}" + "x" * width)
    return path


def test_safe_move_long_path(tmp_path):
    root = _make_long_path(str(tmp_path))
    os.makedirs(_win_long_path(root), exist_ok=True)
    src = os.path.join(root, "source.pdf")
    dst = os.path.join(root, "sub", "target.pdf")
    with open(_win_long_path(src), "wb") as fh:
        fh.write(b"%PDF-1.7 long path")
    assert len(os.path.abspath(src)) > 260

    assert safe_move(src, dst) is True
    assert os.path.exists(_win_long_path(dst))
    assert not os.path.exists(_win_long_path(src))


def test_safe_move_retries_locked_source(tmp_path, monkeypatch):
    src = tmp_path / "locked.pdf"
    dst = tmp_path / "out" / "locked.pdf"
    src.write_bytes(b"%PDF-1.7")
    real_remove = os.remove
    calls = {"n": 0}

    def flaky_remove(path):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("file in use")
        return real_remove(path)

    monkeypatch.setattr("pilotstd.core.file_utils.os.remove", flaky_remove)
    assert safe_move(str(src), str(dst)) is True
    assert dst.exists()
    assert not src.exists()


def test_safe_move_keeps_source_when_forever_locked(tmp_path, monkeypatch):
    src = tmp_path / "locked.pdf"
    dst = tmp_path / "out" / "locked.pdf"
    src.write_bytes(b"%PDF-1.7")

    real_remove = os.remove

    def locked_only_source(path):
        if os.path.abspath(path) == os.path.abspath(str(src)):
            raise PermissionError("file in use")
        return real_remove(path)

    monkeypatch.setattr("pilotstd.core.file_utils.os.remove", locked_only_source)
    assert safe_move(str(src), str(dst)) is False
    assert not dst.exists(), "失败时回滚目标副本，避免留下重复文件"
    assert src.exists(), "源文件被占用时必须保留，绝不丢数据"


@pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 跨盘符场景")
def test_safe_move_cross_drive(tmp_path):
    drives = [d for d in ("D:\\", "E:\\", "F:\\") if os.path.isdir(d)]
    target = None
    for d in drives:
        try:
            probe = os.path.join(d, ".pilotstd_write_test")
            with open(probe, "w") as fh:
                fh.write("")
            os.remove(probe)
            target = d
            break
        except OSError:
            continue
    if not target:
        pytest.skip("没有可写的第二块盘符")
    src = tmp_path / "cross.pdf"
    src.write_bytes(b"%PDF-1.7 cross")
    dst = os.path.join(target, "pilotstd_cross_test.pdf")
    try:
        assert safe_move(str(src), dst) is True
        assert os.path.exists(dst)
        assert not src.exists()
    finally:
        if os.path.exists(dst):
            os.remove(dst)
