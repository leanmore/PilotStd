"""OrganizerExpireMixin Phase 0/1 行为快照测试。

merge_expire_from_source 的 6 个路径 + 正常路径。
Phase 1 改为直接调用模块级函数，cfg 显式传入。
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.manager.organize.expire import merge_expire_from_source
from pilotstd.models import ParsedStdInfo


class TestMergeExpireFromSource:

    @pytest.fixture
    def cfg(self):
        cfg = MagicMock()
        cfg.get.return_value = "过期作废"
        return cfg

    @pytest.fixture
    def parsed_item(self):
        p = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB",
            number=1234,
            year=2020,
        )
        p.source_path = "/fake/src/test.pdf"
        return p

    # -- 边界：root_dir 无效 --

    def test_root_dir_none_returns_zero(self, cfg):
        p = ParsedStdInfo(raw_filename="x.pdf", logical_code="GB", number=1, year=2020)
        p.source_path = "/f/x.pdf"
        result = merge_expire_from_source(cfg, None, [p])
        assert result == 0

    def test_root_dir_empty_string_returns_zero(self, cfg):
        p = ParsedStdInfo(raw_filename="x.pdf", logical_code="GB", number=1, year=2020)
        p.source_path = "/f/x.pdf"
        result = merge_expire_from_source(cfg, "", [p])
        assert result == 0

    # -- 边界：parsed_list 为空 --

    def test_parsed_list_empty_returns_zero(self, cfg, tmp_path):
        result = merge_expire_from_source(cfg, str(tmp_path), [])
        assert result == 0

    # -- 正常路径：有过期文件夹，合并成功 --

    @pytest.mark.serial
    def test_normal_merge_moves_files(self, cfg, tmp_path):
        root = tmp_path / "library"
        root.mkdir()
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=1234, year=2020)
        p.source_path = str(src_dir / "test.pdf")
        (src_dir / "test.pdf").touch()

        expire_dir = src_dir / "过期作废"
        expire_dir.mkdir()
        (expire_dir / "old_std.pdf").touch()
        (expire_dir / "old_std.doc").touch()

        cfg.get.return_value = "过期作废"

        with patch("pilotstd.organizer.industry_lookup.get_folder_name", return_value="GB"):
            result = merge_expire_from_source(cfg, str(root), [p])

        assert result == 2
        tgt = root / "GB" / "过期作废"
        assert tgt.exists()
        assert len(list(tgt.iterdir())) == 2

    def test_normal_merge_with_custom_expire_folder(self, cfg, tmp_path):
        root = tmp_path / "library"
        root.mkdir()
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="SH", number=56, year=2021)
        p.source_path = str(src_dir / "test.pdf")
        (src_dir / "test.pdf").touch()

        expire_dir = src_dir / "已废止"
        expire_dir.mkdir()
        (expire_dir / "old.pdf").touch()

        cfg.get.return_value = "已废止"

        with patch("pilotstd.organizer.industry_lookup.get_folder_name", return_value="SH"):
            result = merge_expire_from_source(cfg, str(root), [p])

        assert result == 1

    # -- 边界：无过期文件夹 --

    def test_no_expire_dir_returns_zero(self, cfg, tmp_path):
        root = tmp_path / "library"
        root.mkdir()
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=1, year=2020)
        p.source_path = str(src_dir / "test.pdf")
        (src_dir / "test.pdf").touch()

        result = merge_expire_from_source(cfg, str(root), [p])
        assert result == 0

    # -- 边界：parsed 的 source_path 不属于当前 src_dir（L40） --

    def test_parsed_source_not_in_src_dir_skipped(self, cfg, tmp_path):
        """source_path 不在当前 src_dir 下 → continue 跳过。"""
        root = tmp_path / "library"
        root.mkdir()
        src_dir_a = tmp_path / "source_a"
        src_dir_a.mkdir()
        src_dir_b = tmp_path / "source_b"
        src_dir_b.mkdir()

        # p_a 属于 src_dir_a，p_b 属于 src_dir_b
        p_a = ParsedStdInfo(raw_filename="a.pdf", logical_code="GB", number=1, year=2020)
        p_a.source_path = str(src_dir_a / "a.pdf")
        (src_dir_a / "a.pdf").touch()
        p_b = ParsedStdInfo(raw_filename="b.pdf", logical_code="GB", number=2, year=2020)
        p_b.source_path = str(src_dir_b / "b.pdf")
        (src_dir_b / "b.pdf").touch()

        # src_dir_a 有过期文件夹，src_dir_b 也有
        expire_a = src_dir_a / "过期作废"
        expire_a.mkdir()
        (expire_a / "old_a.pdf").touch()
        expire_b = src_dir_b / "过期作废"
        expire_b.mkdir()
        (expire_b / "old_b.pdf").touch()

        with patch(
            "pilotstd.organizer.industry_lookup.get_folder_name", return_value="GB"
        ):
            result = merge_expire_from_source(cfg, str(root), [p_a, p_b])

        # 每个 src_dir 各自的过期文件被合并
        assert result == 2

    # -- 边界：safe_move 抛 OSError（L51-52） --

    def test_safe_move_oserror_caught(self, cfg, tmp_path):
        """safe_move 抛 OSError → 捕获继续，不中断合并。"""
        root = tmp_path / "library"
        root.mkdir()
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=1, year=2020)
        p.source_path = str(src_dir / "test.pdf")
        (src_dir / "test.pdf").touch()

        expire_dir = src_dir / "过期作废"
        expire_dir.mkdir()
        (expire_dir / "good.pdf").touch()
        (expire_dir / "bad.pdf").touch()

        real_safe_move = __import__(
            "pilotstd.core.file_utils", fromlist=["safe_move"]
        ).safe_move

        def move_side_effect(src, dst, **kw):
            if "bad.pdf" in src:
                raise OSError("permission denied")
            return real_safe_move(src, dst, **kw)

        with patch(
            "pilotstd.core.file_utils.safe_move",
            side_effect=move_side_effect,
        ), patch(
            "pilotstd.organizer.industry_lookup.get_folder_name", return_value="GB"
        ):
            result = merge_expire_from_source(cfg, str(root), [p])

        # good.pdf 被移动，bad.pdf 因 OSError 跳过
        assert result == 1

    # -- 边界：os.rmdir 抛 OSError（L56-57） --

    def test_rmdir_oserror_caught(self, cfg, tmp_path):
        """os.rmdir 失败 → 捕获继续（L56-57）。"""
        root = tmp_path / "library"
        root.mkdir()
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=1, year=2020)
        p.source_path = str(src_dir / "test.pdf")
        (src_dir / "test.pdf").touch()

        expire_dir = src_dir / "过期作废"
        expire_dir.mkdir()
        (expire_dir / "old.pdf").touch()

        with patch(
            "pilotstd.core.file_utils.safe_move",
            return_value=True,
        ), patch(
            "pilotstd.organizer.industry_lookup.get_folder_name", return_value="GB"
        ), patch(
            # 第一次返回文件列表供循环遍历，第二次返回空触发 rmdir
            "os.listdir", side_effect=[["old.pdf"], []]
        ), patch(
            "os.rmdir", side_effect=OSError("directory not empty")
        ):
            result = merge_expire_from_source(cfg, str(root), [p])

        assert result == 1
