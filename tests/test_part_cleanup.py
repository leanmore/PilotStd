"""C-3：启动清理超过 1 小时的 .part 半成品。"""

import os
import time

from pilotstd.download.part_cleanup import cleanup_stale_parts


def _write(path, mtime: float) -> None:
    path.write_bytes(b"partial")
    os.utime(path, (mtime, mtime))


def test_removes_only_stale_parts(tmp_path) -> None:
    now = time.time()
    old_part = tmp_path / "a.pdf.part"
    new_part = tmp_path / "b.pdf.part"
    old_pdf = tmp_path / "c.pdf"
    _write(old_part, now - 7200)
    _write(new_part, now - 60)
    _write(old_pdf, now - 7200)

    removed = cleanup_stale_parts(str(tmp_path), now=now)
    assert removed == 1
    assert not old_part.exists()
    assert new_part.exists()
    assert old_pdf.exists()


def test_missing_dir_is_noop(tmp_path) -> None:
    assert cleanup_stale_parts(str(tmp_path / "nope")) == 0
