# tests/gui/test_archive_flow_engine.py
"""ArchiveFlowEngine 纯逻辑单元测试 — 不依赖 Qt，纯 pytest。

覆盖所有 9 个静态方法，目标覆盖率 ≥ 90%。
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.models import ParsedStdInfo
from pilotstd.ui.core.handlers.archive_flow_engine import ArchiveFlowEngine


# ── 测试辅助 ─────────────────────────────────────────────────


def _make_parsed(
    logical_code: str = "GB/T",
    number: int = 1,
    year: int = 2020,
    source_path: str = "",
    std_name: str = "测试标准",
    found_name: str = "",
    next_action: str = "",
) -> ParsedStdInfo:
    return ParsedStdInfo(
        raw_filename=f"{logical_code} {number}-{year}.pdf",
        logical_code=logical_code,
        number=number,
        year=year,
        source_path=source_path,
        std_name=std_name,
        found_name=found_name,
        next_action=next_action,
    )


def _make_mock_parsed(**kwargs: object) -> MagicMock:
    """创建带任意属性的 mock 对象，模拟 ParsedStdInfo。"""
    m = MagicMock()
    m.get_full_number.return_value = "GB/T 1-2020"
    m.source_path = ""
    m.source_name = ""
    m.found_name = ""
    m.std_name = ""
    m.raw_filename = ""
    m.next_action = ""
    m.effect_status = ""
    m.stage_status = ""
    m.final_name = ""
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


@pytest.fixture
def engine():
    return ArchiveFlowEngine()


# ════════════════════════════════════════════════════════════════
# determine_status_label
# ════════════════════════════════════════════════════════════════


class TestDetermineStatusLabel:
    def test_replaced(self, engine):
        assert engine.determine_status_label("被代替") == "被代替"

    def test_abolished(self, engine):
        assert engine.determine_status_label("废止") == "废止"

    def test_abolished_variant(self, engine):
        assert engine.determine_status_label("已废止") == "废止"

    def test_cancelled(self, engine):
        assert engine.determine_status_label("作废") == "废止"

    def test_current(self, engine):
        assert engine.determine_status_label("现行") == "现行"

    def test_about_to_implement(self, engine):
        assert engine.determine_status_label("即将实施") == "现行"

    def test_empty_string(self, engine):
        assert engine.determine_status_label("") == "现行"


# ════════════════════════════════════════════════════════════════
# detect_file_conflicts
# ════════════════════════════════════════════════════════════════


class TestDetectFileConflicts:
    def test_empty_list(self, engine):
        result = engine.detect_file_conflicts([], "/lib", {}, lambda p, r, c: "")
        assert result == []

    def test_no_source_path(self, engine):
        p = _make_mock_parsed(source_path="")
        result = engine.detect_file_conflicts([p], "/lib", {}, lambda p, r, c: "/lib/f.pdf")
        assert result == []

    def test_source_file_not_exist(self, engine, tmp_path):
        nonexistent = str(tmp_path / "nonexistent.pdf")
        p = _make_mock_parsed(source_path=nonexistent)
        result = engine.detect_file_conflicts([p], "/lib", {}, lambda p, r, c: "/lib/f.pdf")
        assert result == []

    def test_target_is_none(self, engine):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            p = _make_mock_parsed(source_path=tmp_path)
            result = engine.detect_file_conflicts(
                [p], "/lib", {}, lambda p, r, c: None
            )
            assert result == []
        finally:
            os.unlink(tmp_path)

    def test_target_not_exist(self, engine):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            p = _make_mock_parsed(source_path=tmp_path)
            result = engine.detect_file_conflicts(
                [p], "/lib", {}, lambda p, r, c: "/lib/nonexistent.pdf"
            )
            assert result == []
        finally:
            os.unlink(tmp_path)

    def test_detects_conflict(self, engine):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            src_path = f.name
        try:
            p = _make_mock_parsed(source_path=src_path)
            # target_path_fn 返回源文件自身路径 → 肯定存在
            result = engine.detect_file_conflicts(
                [p], "/lib", {}, lambda p, r, c: src_path
            )
            assert len(result) == 1
            assert result[0][0] == os.path.basename(src_path)
            assert result[0][1] == src_path
        finally:
            os.unlink(src_path)

    def test_mixed(self, engine):
        """混合场景：有冲突 + 无冲突 + 无源文件。"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            conflict_path = f.name
        try:
            p_conflict = _make_mock_parsed(source_path=conflict_path)
            p_no_conflict = _make_mock_parsed(source_path=conflict_path)
            p_no_source = _make_mock_parsed(source_path="")

            result = engine.detect_file_conflicts(
                [p_conflict, p_no_conflict, p_no_source],
                "/lib",
                {},
                lambda p, r, c: conflict_path if p is p_conflict else "/lib/other.pdf",
            )
            assert len(result) == 1
        finally:
            os.unlink(conflict_path)


# ════════════════════════════════════════════════════════════════
# format_conflict_message
# ════════════════════════════════════════════════════════════════


class TestFormatConflictMessage:
    def test_empty(self, engine):
        msg = engine.format_conflict_message([])
        assert "0" in msg

    def test_under_5(self, engine):
        conflicts = [("a.pdf", "/lib/a.pdf"), ("b.pdf", "/lib/b.pdf")]
        msg = engine.format_conflict_message(conflicts)
        assert "2" in msg
        assert "a.pdf" in msg

    def test_over_5(self, engine):
        conflicts = [(f"{i}.pdf", f"/lib/{i}.pdf") for i in range(10)]
        msg = engine.format_conflict_message(conflicts)
        assert "10" in msg
        assert "... 等共 10 个" in msg


# ════════════════════════════════════════════════════════════════
# filter_by_action
# ════════════════════════════════════════════════════════════════


class TestFilterByAction:
    def test_empty(self, engine):
        assert engine.filter_by_action([], "expire") == []

    def test_exact_match(self, engine):
        expired = _make_mock_parsed(next_action="expire")
        archive = _make_mock_parsed(next_action="archive")
        result = engine.filter_by_action([expired, archive], "expire")
        assert len(result) == 1

    def test_no_match(self, engine):
        items = [_make_mock_parsed(next_action="download") for _ in range(3)]
        assert engine.filter_by_action(items, "expire") == []

    def test_default_empty_string(self, engine):
        """next_action 不存在时 getattr 默认返回 ''。"""
        m = _make_mock_parsed()
        m.next_action = ""
        assert engine.filter_by_action([m], "expire") == []


# ════════════════════════════════════════════════════════════════
# count_archive_results
# ════════════════════════════════════════════════════════════════


class TestCountArchiveResults:
    def test_empty(self, engine):
        saved, skipped = engine.count_archive_results([])
        assert saved == 0
        assert skipped == 0

    def test_all_saved(self, engine):
        results = [(0, "已归档"), (1, "已归档"), (2, "已归档")]
        saved, skipped = engine.count_archive_results(results)
        assert saved == 3
        assert skipped == 0

    def test_all_skipped(self, engine):
        results = [(0, "已存在"), (1, "跳过")]
        saved, skipped = engine.count_archive_results(results)
        assert saved == 0
        assert skipped == 2

    def test_mixed(self, engine):
        results = [(0, "已归档"), (1, "已归档"), (2, "已存在"), (3, "失败")]
        saved, skipped = engine.count_archive_results(results)
        assert saved == 2
        assert skipped == 2


# ════════════════════════════════════════════════════════════════
# find_missing_names
# ════════════════════════════════════════════════════════════════


class TestFindMissingNames:
    def test_empty(self, engine):
        assert engine.find_missing_names([]) == []

    def test_all_have_names(self, engine):
        items = [_make_parsed(std_name="标准A"), _make_parsed(found_name="标准B")]
        assert engine.find_missing_names(items) == []

    def test_some_missing(self, engine):
        items = [
            _make_parsed(std_name="标准A"),
            _make_parsed(std_name="", found_name=""),
            _make_parsed(number=2, std_name="", found_name=""),
        ]
        result = engine.find_missing_names(items)
        assert len(result) == 2

    def test_all_missing(self, engine):
        items = [_make_parsed(std_name="", found_name="") for _ in range(3)]
        assert len(engine.find_missing_names(items)) == 3


# ════════════════════════════════════════════════════════════════
# format_skip_details
# ════════════════════════════════════════════════════════════════


class TestFormatSkipDetails:
    def test_empty_results(self, engine):
        assert engine.format_skip_details([], []) == []

    def test_all_archived(self, engine):
        results = [(0, "已归档"), (1, "已归档")]
        parsed = [_make_mock_parsed(source_path="/tmp/a.pdf") for _ in range(2)]
        assert engine.format_skip_details(results, parsed) == []

    def test_skipped_items(self, engine):
        results = [(0, "已归档"), (1, "已存在"), (2, "失败")]
        parsed = [
            _make_mock_parsed(source_path="/tmp/a.pdf"),
            _make_mock_parsed(source_path="/tmp/b.pdf"),
            _make_mock_parsed(raw_filename="c.pdf"),
        ]
        details = engine.format_skip_details(results, parsed)
        assert len(details) == 2

    def test_idx_out_of_range(self, engine):
        """idx >= len(parsed_results) 时应跳过。"""
        results = [(0, "已存在"), (99, "失败")]  # idx 99 越界
        parsed = [_make_mock_parsed(source_path="/tmp/a.pdf")]
        details = engine.format_skip_details(results, parsed)
        assert len(details) == 1

    def test_no_source_or_raw(self, engine):
        """source_path 和 raw_filename 均为空时用空字符串。"""
        results = [(0, "跳过")]
        m = _make_mock_parsed()
        m.source_path = ""
        m.raw_filename = ""
        details = engine.format_skip_details(results, [m])
        assert len(details) == 1


# ════════════════════════════════════════════════════════════════
# get_library_root_from_config
# ════════════════════════════════════════════════════════════════


class TestGetLibraryRoot:
    def test_returns_string(self, engine):
        cfg = MagicMock()
        cfg.get.return_value = "/test/lib"
        # get_library_root 内部调用 config.get，然后 os.path.abspath
        # Mock 整个 get_library_root 调用路径
        with patch(
            "pilotstd.ui.core.handlers.archive_flow_engine.get_library_root",
            return_value="/mock/lib",
        ):
            result = engine.get_library_root_from_config(cfg)
            assert result == "/mock/lib"
