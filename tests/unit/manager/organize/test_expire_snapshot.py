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
