"""safe_move 权限回归：只读源文件也必须能搬走且目标可读（2026-11-04 CI 缺陷）。"""

import os

from pilotstd.core.file_utils import safe_move


def test_safe_move_readonly_source(tmp_path):
    src = tmp_path / "src.pdf"
    dst = tmp_path / "out" / "dst.pdf"
    src.write_bytes(b"%PDF-1.4 body")
    os.chmod(src, 0o444)
    dst.parent.mkdir()

    assert safe_move(str(src), str(dst)) is True
    assert not src.exists()
    assert dst.read_bytes() == b"%PDF-1.4 body"
    # 目标必须可读（POSIX 上旧实现会把源改成 0o200 导致 copy2 失败）
    assert os.access(dst, os.R_OK)


def test_safe_move_same_content_skip(tmp_path):
    src = tmp_path / "a.pdf"
    dst = tmp_path / "b.pdf"
    src.write_bytes(b"same")
    dst.write_bytes(b"same")

    assert safe_move(str(src), str(dst)) is False
    assert src.exists() and dst.exists()
