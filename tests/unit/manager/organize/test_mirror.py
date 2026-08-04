"""mirror.py 覆盖率补齐 — 目标: 28% → 95%+"""

import os
import stat
import pytest
from unittest.mock import MagicMock, patch

from pilotstd.manager.organize.mirror import OrganizerMirror


@pytest.fixture
def mock_cfg():
    cfg = MagicMock()
    cfg.get.return_value = True
    return cfg


@pytest.fixture
def mirror(mock_cfg):
    return OrganizerMirror(mock_cfg)


@pytest.fixture(autouse=True)
def _patch_common(monkeypatch, tmp_path):
    """自动 patch get_library_root 等，指向临时目录。"""
    library_root = str(tmp_path / "library")
    os.makedirs(library_root, exist_ok=True)

    monkeypatch.setattr(
        "pilotstd.manager.organize.mirror.get_library_root",
        lambda _: library_root,
    )
    monkeypatch.setattr(
        "pilotstd.manager.organize.mirror._resolve_industry_in_path",
        lambda x: x,
    )
    monkeypatch.setattr(
        "pilotstd.manager.organize.mirror.ensure_long_path",
        lambda x: x,
    )
    monkeypatch.setattr(
        "pilotstd.manager.organize.mirror.strip_long_path",
        lambda x: x,
    )


def _make_src_dir(tmp_path, name: str = "source") -> str:
    src = tmp_path / name
    src.mkdir(exist_ok=True)
    return str(src)


def _touch(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x")


# ════════════════════════════════════════════════════════════
# P0: organize_skipped_dirs
# ════════════════════════════════════════════════════════════

class TestOrganizeSkippedDirs:
    def test_whole_dir_moved_when_dst_not_exists(self, mirror, tmp_path):
        """目标不存在 → shutil.move 整体移动目录。"""
        src_root = _make_src_dir(tmp_path)
        src_dir = os.path.join(src_root, "skipped_industry")
        os.makedirs(src_dir)
        _touch(os.path.join(src_dir, "file.pdf"))

        with patch("shutil.move") as mock_shutil_move:
            result = mirror.organize_skipped_dirs([src_dir], source_root=src_root)

        assert result["moved"] == 1
        mock_shutil_move.assert_called_once()

    def test_into_existing_dst_files_moved(self, mirror, tmp_path):
        """目标已存在 → safe_move 逐文件移动。"""
        library = str(tmp_path / "library")
        dst_dir = os.path.join(library, "skipped_industry")
        os.makedirs(dst_dir, exist_ok=True)

        src_root = _make_src_dir(tmp_path)
        src_dir = os.path.join(src_root, "skipped_industry")
        os.makedirs(src_dir)
        _touch(os.path.join(src_dir, "a.pdf"))
        _touch(os.path.join(src_dir, "b.pdf"))

        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ) as mock_sm:
            result = mirror.organize_skipped_dirs([src_dir], source_root=src_root)

        assert result["moved"] == 2
        assert mock_sm.call_count == 2

    def test_src_dir_not_exist_skipped(self, mirror):
        """源目录不存在 → _resolve_skipped_relative 返回 None → 跳过。"""
        result = mirror.organize_skipped_dirs(
            ["/nonexistent_dir_xyz"], source_root="/src"
        )
        assert result["moved"] == 0
        assert result["failed"] == 0

    def test_path_traversal_rejected(self, mirror, tmp_path):
        """路径越界 → _check_path_traversal 返回 False → failed += 1。"""
        src_root = _make_src_dir(tmp_path)
        src_dir = os.path.join(src_root, "ok_dir")
        os.makedirs(src_dir)

        with patch(
            "pilotstd.manager.organize.mirror._resolve_industry_in_path",
            return_value="../../escape",
        ):
            result = mirror.organize_skipped_dirs([src_dir], source_root=src_root)

        assert result["failed"] == 1
        assert "路径越界" in result["details"][0]

    def test_oserror_caught_as_failed(self, mirror, tmp_path):
        """OSError → failed += 1，details 记录。"""
        src_root = _make_src_dir(tmp_path)
        src_dir = os.path.join(src_root, "will_fail")
        os.makedirs(src_dir)

        with patch("shutil.move", side_effect=OSError("Permission denied")):
            result = mirror.organize_skipped_dirs([src_dir], source_root=src_root)

        assert result["failed"] == 1
        assert "移动失败" in result["details"][0]

    def test_empty_skipped_dirs_list(self, mirror):
        """空列表 → 直接返回零计数。"""
        result = mirror.organize_skipped_dirs([], source_root="/src")
        assert result["moved"] == 0
        assert result["failed"] == 0


# ════════════════════════════════════════════════════════════
# P1: _resolve_skipped_relative
# ════════════════════════════════════════════════════════════

class TestResolveSkippedRelative:
    def test_normal_relpath(self, mirror, tmp_path):
        """正常路径 → relpath 计算正确。"""
        root = str(tmp_path / "library")
        src_root = str(tmp_path / "source")
        src_dir = os.path.join(src_root, "industry", "sub")
        os.makedirs(src_dir)

        rel, dst = mirror._resolve_skipped_relative(src_dir, root, src_root)
        assert rel == os.path.join("industry", "sub")
        assert dst == os.path.join(root, "industry", "sub")

    def test_source_root_none_uses_basename(self, mirror, tmp_path):
        """source_root=None → 回退到 basename。"""
        root = str(tmp_path / "library")
        src_dir = os.path.join(str(tmp_path), "source", "mydir")
        os.makedirs(src_dir)

        rel, dst = mirror._resolve_skipped_relative(src_dir, root, None)
        assert rel == "mydir"

    def test_long_path_prefix_stripped(self, mirror, tmp_path):
        r"""\\?\ 前缀 → 被剥离后正常计算。"""
        root = str(tmp_path / "library")
        src_root = str(tmp_path / "source")
        src_dir = os.path.join(src_root, "sub")
        os.makedirs(src_dir)

        long_src_dir = "\\\\?\\" + src_dir
        long_src_root = "\\\\?\\" + src_root

        result = mirror._resolve_skipped_relative(long_src_dir, root, long_src_root)
        assert result[0] is not None, f"_resolve_skipped_relative returned skip: {result}"
        rel, dst = result
        assert "sub" in rel

    def test_nonexistent_dir_returns_skip(self, mirror, tmp_path):
        """目录不存在 → 返回 (None, reason)。"""
        result = mirror._resolve_skipped_relative("/no/such/dir", "/root", "/src")
        assert result[0] is None
        assert "skipped" in result[1]

    def test_value_error_falls_back_to_basename(self, mirror, tmp_path):
        """relpath 抛 ValueError → 回退到 basename。"""
        root = str(tmp_path / "library")
        src_dir = os.path.join(str(tmp_path), "source", "mydir")
        os.makedirs(src_dir)

        with patch("os.path.relpath", side_effect=ValueError("different drives")):
            rel, dst = mirror._resolve_skipped_relative(
                src_dir, root, "Z:\\other_drive"
            )
        assert rel == "mydir"


# ════════════════════════════════════════════════════════════
# P1: _check_path_traversal
# ════════════════════════════════════════════════════════════

class TestCheckPathTraversal:
    def test_safe_path(self, mirror, tmp_path):
        root = str(tmp_path / "library")
        dst = os.path.join(root, "sub", "file.pdf")
        os.makedirs(root, exist_ok=True)
        assert mirror._check_path_traversal(dst, root, "/src") is True

    def test_unsafe_path(self, mirror, tmp_path):
        root = str(tmp_path / "library")
        dst = str(tmp_path / "outside" / "file.pdf")
        os.makedirs(root, exist_ok=True)
        assert mirror._check_path_traversal(dst, root, "/src") is False


# ════════════════════════════════════════════════════════════
# P1: _mirror_into_existing_dst
# ════════════════════════════════════════════════════════════

class TestMirrorIntoExistingDst:
    def test_files_moved_via_safe_move(self, mirror, tmp_path):
        """文件 → safe_move 逐个移动。"""
        dst = str(tmp_path / "dst")
        src_dir = str(tmp_path / "src")
        os.makedirs(dst)
        os.makedirs(src_dir)
        _touch(os.path.join(src_dir, "a.pdf"))
        _touch(os.path.join(src_dir, "b.pdf"))

        result = {"moved": 0, "details": []}
        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ) as mock_sm:
            mirror._mirror_into_existing_dst(dst, src_dir, result)

        assert result["moved"] == 2
        assert mock_sm.call_count == 2

    def test_safe_move_returns_false_skips(self, mirror, tmp_path):
        """safe_move 返回 False → 不计数，记录 details。"""
        dst = str(tmp_path / "dst")
        src_dir = str(tmp_path / "src")
        os.makedirs(dst)
        os.makedirs(src_dir)
        _touch(os.path.join(src_dir, "dup.pdf"))

        result = {"moved": 0, "details": []}
        with patch("pilotstd.manager.organize.mirror.safe_move", return_value=False):
            mirror._mirror_into_existing_dst(dst, src_dir, result)

        assert result["moved"] == 0
        assert len(result["details"]) == 1

    def test_subdir_moved_via_shutil(self, mirror, tmp_path):
        """嵌套子目录 → shutil.move 整体移动（覆盖 L107-117）。"""
        dst = str(tmp_path / "dst")
        src_dir = str(tmp_path / "src")
        os.makedirs(dst)
        os.makedirs(src_dir)
        # 需要 3 层深度：src_dir/subdir/nested/ 才能触发 shutil.move
        sub = os.path.join(src_dir, "subdir")
        nested = os.path.join(sub, "nested")
        os.makedirs(nested)
        _touch(os.path.join(nested, "c.pdf"))

        result = {"moved": 0, "details": []}
        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ), patch("shutil.move") as mock_shutil_move:
            mirror._mirror_into_existing_dst(dst, src_dir, result)

        mock_shutil_move.assert_called_once()

    def test_subdir_clear_readonly(self, mirror, mock_cfg, tmp_path):
        """clear_readonly=True → os.chmod 被调用。"""
        dst = str(tmp_path / "dst")
        src_dir = str(tmp_path / "src")
        os.makedirs(dst)
        os.makedirs(src_dir)
        sub = os.path.join(src_dir, "subdir")
        os.makedirs(sub)
        _touch(os.path.join(sub, "ro.pdf"))

        result = {"moved": 0, "details": []}
        with patch("shutil.move"), patch("os.chmod") as mock_chmod:
            mirror._mirror_into_existing_dst(dst, src_dir, result)

        chmod_calls = [
            c for c in mock_chmod.call_args_list if c.args[1] == stat.S_IWRITE
        ]
        assert len(chmod_calls) >= 1

    def test_subdir_oserror_recorded(self, mirror, tmp_path):
        """子目录操作 OSError → details 记录。"""
        dst = str(tmp_path / "dst")
        src_dir = str(tmp_path / "src")
        os.makedirs(dst)
        os.makedirs(src_dir)
        sub = os.path.join(src_dir, "bad_sub")
        os.makedirs(sub)
        _touch(os.path.join(sub, "x.pdf"))

        result = {"moved": 0, "details": []}
        with patch(
            "pilotstd.manager.organize.mirror.os.makedirs",
            side_effect=OSError("fail"),
        ):
            mirror._mirror_into_existing_dst(dst, src_dir, result)

        assert any("失败" in d for d in result["details"])


# ════════════════════════════════════════════════════════════
# P2: _mirror_whole_directory
# ════════════════════════════════════════════════════════════

class TestMirrorWholeDirectory:
    def test_whole_dir_moved(self, mirror, tmp_path):
        """整体移动 → shutil.move 被调用。"""
        dst = str(tmp_path / "dst" / "target")
        src_dir = str(tmp_path / "src")
        os.makedirs(src_dir)
        _touch(os.path.join(src_dir, "file.pdf"))

        result = {"moved": 0, "details": []}
        with patch("shutil.move") as mock_shutil_move:
            mirror._mirror_whole_directory(dst, src_dir, result)

        assert result["moved"] == 1
        mock_shutil_move.assert_called_once_with(src_dir, dst)

    def test_clear_readonly_before_move(self, mirror, tmp_path):
        """clear_readonly=True → os.chmod 移除只读。"""
        dst = str(tmp_path / "dst" / "target")
        src_dir = str(tmp_path / "src")
        os.makedirs(src_dir)
        _touch(os.path.join(src_dir, "ro.pdf"))

        result = {"moved": 0, "details": []}
        with patch("shutil.move"), patch("os.chmod") as mock_chmod:
            mirror._mirror_whole_directory(dst, src_dir, result)

        chmod_calls = [
            c for c in mock_chmod.call_args_list if c.args[1] == stat.S_IWRITE
        ]
        assert len(chmod_calls) >= 1


# ════════════════════════════════════════════════════════════
# P3: organize_fallback
# ════════════════════════════════════════════════════════════

class TestOrganizeFallback:
    def test_residual_files_moved(self, mirror, tmp_path):
        """残留文件 → safe_move 移动到 library。"""
        src_root = _make_src_dir(tmp_path, "source")
        _touch(os.path.join(src_root, "residual.pdf"))
        sub = os.path.join(src_root, "sub")
        os.makedirs(sub)
        _touch(os.path.join(sub, "more.pdf"))

        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ) as mock_sm:
            result = mirror.organize_fallback(source_root=src_root)

        assert result["moved"] == 2
        assert mock_sm.call_count == 2

    def test_skip_system_files(self, mirror, tmp_path):
        """.DS_Store / Thumbs.db / ~ 前缀 → 跳过。"""
        src_root = _make_src_dir(tmp_path, "source")
        _touch(os.path.join(src_root, ".DS_Store"))
        _touch(os.path.join(src_root, "Thumbs.db"))
        _touch(os.path.join(src_root, "~$temp.docx"))
        _touch(os.path.join(src_root, "valid.pdf"))

        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ) as mock_sm:
            result = mirror.organize_fallback(source_root=src_root)

        assert result["skipped"] == 3
        assert result["moved"] == 1
        assert mock_sm.call_count == 1

    def test_skip_pending_paths(self, mirror, tmp_path):
        """pending_paths 中的文件 → skipped_pending += 1。"""
        src_root = _make_src_dir(tmp_path, "source")
        pending_file = os.path.join(src_root, "pending.pdf")
        _touch(pending_file)
        _touch(os.path.join(src_root, "other.pdf"))

        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ) as mock_sm:
            result = mirror.organize_fallback(
                source_root=src_root, pending_paths=frozenset([pending_file])
            )

        assert result["skipped_pending"] == 1
        assert result["moved"] == 1

    def test_skip_already_processed(self, mirror, tmp_path):
        """_skipped_source_files 中的文件 → skipped_by_organize += 1。"""
        src_root = _make_src_dir(tmp_path, "source")
        processed = os.path.join(src_root, "processed.pdf")
        _touch(processed)
        _touch(os.path.join(src_root, "other.pdf"))
        mirror._skipped_source_files.add(processed)

        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=True
        ) as mock_sm:
            result = mirror.organize_fallback(source_root=src_root)

        assert result["skipped_by_organize"] == 1
        assert result["moved"] == 1

    def test_safe_move_oserror_counted(self, mirror, tmp_path):
        """safe_move 抛 OSError → failed += 1。"""
        src_root = _make_src_dir(tmp_path, "source")
        _touch(os.path.join(src_root, "bad.pdf"))

        with patch(
            "pilotstd.manager.organize.mirror.safe_move",
            side_effect=OSError("disk full"),
        ):
            result = mirror.organize_fallback(source_root=src_root)

        assert result["failed"] == 1
        assert "兜底镜像失败" in result["details"][0]

    def test_safe_move_returns_false_skipped(self, mirror, tmp_path):
        """safe_move 返回 False → skipped += 1。"""
        src_root = _make_src_dir(tmp_path, "source")
        _touch(os.path.join(src_root, "exists.pdf"))

        with patch(
            "pilotstd.manager.organize.mirror.safe_move", return_value=False
        ):
            result = mirror.organize_fallback(source_root=src_root)

        assert result["skipped"] == 1
        assert result["moved"] == 0
