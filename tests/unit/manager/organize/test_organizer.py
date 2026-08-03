"""organizer.py 覆盖率补齐 — 目标: 49% → 95%+"""

import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from pilotstd.manager.organize.organizer import OrganizerCore


# ── 辅助：构造 ParsedStdInfo 风格的 mock 对象 ──


def _make_item(
    source_path: str,
    logical_code: str = "GB",
    number: int = 1234,
    year: int = 2020,
    std_name: str = "Test Standard",
    next_action: str = "",
    part: int | None = None,
    effect_status: str = "现行",
    raw_number: str = "",
    **kwargs,
):
    """构造模拟 parsed item 对象（getattr 兼容）。"""
    p = MagicMock()
    p.source_path = source_path
    p.logical_code = logical_code
    p.number = number
    p.year = year
    p.std_name = std_name
    p.next_action = next_action
    p.part = part
    p.effect_status = effect_status
    p.raw_number = raw_number
    for k, v in kwargs.items():
        setattr(p, k, v)
    p.get_full_number.return_value = f"{logical_code} {number}-{year}"
    return p


# ── Fixtures ──


@pytest.fixture
def mock_cfg():
    cfg = MagicMock()
    cfg.get.return_value = {}
    return cfg


@pytest.fixture
def mock_file_index():
    fi = MagicMock()
    fi.upsert.return_value = None
    fi.find_by_standard.return_value = []
    fi.remove.return_value = None
    fi.db = MagicMock()
    return fi


@pytest.fixture
def mock_dir_builder():
    return MagicMock()


@pytest.fixture
def mock_file_mover():
    fm = MagicMock()
    fm.normalize_filename.return_value = "/lib/GB/GB_T_1234-2020.pdf"
    fm.move_to_code_dir.return_value = "/lib/GB/GB_T_1234-2020.pdf"
    return fm


@pytest.fixture
def organizer(mock_cfg, mock_file_index, mock_dir_builder, mock_file_mover):
    with patch("pilotstd.manager.organize.organizer.StandardParser") as mock_parser_cls:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = None
        mock_parser_cls.return_value = mock_parser
        org = OrganizerCore(mock_cfg, mock_file_index, mock_dir_builder, mock_file_mover)
        org._std_parser = mock_parser
        return org


# ════════════════════════════════════════════════════════════
# T1: organize() 主入口
# ════════════════════════════════════════════════════════════


class TestOrganize:
    def test_empty_list_returns_zero_results(self, organizer):
        """空列表 → result 全零 + 汇总日志"""
        with patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root:
            mock_root.return_value = "/fake/lib"
            result = organizer.organize([])
            assert result["moved"] == 0
            assert result["failed"] == 0
            assert result["details"] == []

    def test_skips_pending_items(self, organizer, tmp_path):
        """next_action == 'pending' → 跳过"""
        src = tmp_path / "test.pdf"
        src.write_bytes(b"pdf content")
        item = _make_item(str(src), next_action="pending")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
        ):
            mock_root.return_value = str(tmp_path / "lib")
            mock_isfile.return_value = True
            result = organizer.organize([item])
            assert result["moved"] == 0

    def test_skips_missing_source_file(self, organizer):
        """source_path 不存在 → details 记录跳过"""
        item = _make_item("/nonexistent/file.pdf")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
        ):
            mock_root.return_value = "/fake/lib"
            mock_isfile.return_value = False
            result = organizer.organize([item])
            assert result["moved"] == 0
            assert any("无源文件" in d for d in result["details"])

    def test_dedup_logs_when_duplicates_removed(self, organizer, tmp_path, caplog):
        """同标准号多条 → 去重 + 日志"""
        src = tmp_path / "a.pdf"
        src.write_bytes(b"a")
        item1 = _make_item(str(src), logical_code="GB", number=1, year=2020)
        item2 = _make_item(str(src), logical_code="GB", number=1, year=2020)

        import logging

        caplog.set_level(logging.INFO, logger="pilotstd.manager.organize.organizer")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
        ):
            mock_root.return_value = str(tmp_path / "lib")
            mock_isfile.return_value = False
            organizer.organize([item1, item2])
            assert any("去重" in rec.message for rec in caplog.records)

    def test_progress_log_every_50_items(self, organizer, tmp_path, caplog):
        """≥50 条时触发进度日志"""
        src = tmp_path / "x.pdf"
        src.write_bytes(b"x")
        items = [
            _make_item(str(src), logical_code="GB", number=i, year=2020)
            for i in range(50)
        ]

        import logging

        caplog.set_level(logging.INFO, logger="pilotstd.manager.organize.organizer")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
        ):
            mock_root.return_value = str(tmp_path / "lib")
            mock_isfile.return_value = False
            organizer.organize(items)
            assert any("归档进度" in rec.message for rec in caplog.records)

    def test_word_item_routed_to_word_handler(self, organizer, tmp_path):
        """Word 文件 → _organize_word_item"""
        src = tmp_path / "report.docx"
        src.write_bytes(b"docx")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
            patch("pilotstd.manager.organize.organizer._is_word_or_template") as mock_is_word,
            patch.object(organizer, "_organize_word_item") as mock_word,
        ):
            mock_root.return_value = str(tmp_path / "lib")
            mock_isfile.return_value = True
            mock_is_word.return_value = True
            organizer.organize([_make_item(str(src))])
            mock_word.assert_called_once()

    def test_nonword_item_routed_to_nonword_handler(self, organizer, tmp_path):
        """PDF 文件 → _organize_nonword_item"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
            patch("pilotstd.manager.organize.organizer._is_word_or_template") as mock_is_word,
            patch.object(organizer, "_organize_nonword_item") as mock_nonword,
        ):
            mock_root.return_value = str(tmp_path / "lib")
            mock_isfile.return_value = True
            mock_is_word.return_value = False
            organizer.organize([_make_item(str(src))])
            mock_nonword.assert_called_once()

    def test_overwrite_mode_sets_on_exists(self, organizer, tmp_path):
        """overwrite=True → on_exists='overwrite'"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")

        with (
            patch("pilotstd.manager.organize.organizer.get_library_root") as mock_root,
            patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile,
            patch("pilotstd.manager.organize.organizer._is_word_or_template") as mock_is_word,
            patch.object(organizer, "_organize_nonword_item") as mock_nonword,
        ):
            mock_root.return_value = str(tmp_path / "lib")
            mock_isfile.return_value = True
            mock_is_word.return_value = False
            organizer.organize([_make_item(str(src))], overwrite=True)
            # _organize_nonword_item(p, mover, result, content_hashes, on_exists)
            # on_exists 是第5个位置参数
            on_exists_arg = mock_nonword.call_args[0][4]
            assert on_exists_arg == "overwrite"


# ════════════════════════════════════════════════════════════
# T2: _organize_nonword_item（最大缺口，47行）
# ════════════════════════════════════════════════════════════


class TestOrganizeNonWordItem:
    def test_happy_path_move_and_index(self, organizer, mock_file_mover, mock_file_index, tmp_path):
        """正常 PDF 归档：hash → move → upsert → register"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"%PDF-1.4 real pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {}

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.getsize") as mock_size,
        ):
            mock_hash.return_value = "abc123"
            mock_size.return_value = 1024
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        assert result["moved"] == 1
        assert "abc123" in hashes
        mock_file_mover.move_to_code_dir.assert_called_once()
        mock_file_index.upsert.assert_called_once()

    def test_content_hash_duplicate_skipped(self, organizer, mock_file_mover, tmp_path):
        """内容哈希重复 → dedup_skipped++"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"same content")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {"abc123": "/existing/path.pdf"}

        with patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash:
            mock_hash.return_value = "abc123"
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        assert result["dedup_skipped"] == 1
        mock_file_mover.move_to_code_dir.assert_not_called()

    def test_hash_os_error_skips(self, organizer, mock_file_mover, tmp_path):
        """hash_file_content 抛 OSError → 仍尝试移动"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"corrupt")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {}

        with patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash:
            mock_hash.side_effect = OSError("read error")
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        mock_file_mover.move_to_code_dir.assert_called_once()

    def test_move_returns_none_file_exists(self, organizer, mock_file_mover, mock_file_index, tmp_path):
        """move_to_code_dir 返回 None + 目标已存在 → skipped_exists++"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "skipped_source": 0, "dedup_skipped": 0, "details": []}
        hashes = {}
        mock_file_mover.move_to_code_dir.return_value = None
        mock_file_mover.normalize_filename.return_value = "/lib/exists.pdf"

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_hash.return_value = "abc123"
            mock_exists.return_value = True
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        assert result["skipped_exists"] == 1

    def test_move_returns_none_file_not_exists(self, organizer, mock_file_mover, tmp_path):
        """move_to_code_dir 返回 None + 目标不存在 → failed++"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {}
        mock_file_mover.move_to_code_dir.return_value = None
        mock_file_mover.normalize_filename.return_value = "/lib/nonexist.pdf"

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_hash.return_value = "abc123"
            mock_exists.return_value = False
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        assert result["failed"] == 1

    def test_auto_clean_source_removes_file(self, organizer, mock_file_mover, mock_cfg, tmp_path):
        """auto_clean_source=True + 目标已存在 → os.remove 源文件"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "skipped_source": 0, "dedup_skipped": 0, "details": []}
        hashes = {}
        mock_file_mover.move_to_code_dir.return_value = None
        mock_file_mover.normalize_filename.return_value = "/lib/exists.pdf"
        mock_cfg.get.return_value = True

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
            patch("pilotstd.manager.organize.organizer.os.remove") as mock_remove,
        ):
            mock_hash.return_value = "abc123"
            mock_exists.return_value = True
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        mock_remove.assert_called_once_with(str(src))

    def test_register_standard_called_on_success(self, organizer, mock_file_mover, tmp_path):
        """move 成功后调用 _register_standard"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {}

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.getsize") as mock_size,
            patch.object(organizer, "_register_standard") as mock_register,
        ):
            mock_hash.return_value = "abc123"
            mock_size.return_value = 2048
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        mock_register.assert_called_once_with(item, "abc123", 2048)

    def test_dedup_standard_called_on_success(self, organizer, mock_file_mover, tmp_path):
        """move 成功后调用 _dedup_standard"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {}

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.getsize") as mock_size,
            patch.object(organizer, "_dedup_standard") as mock_dedup,
        ):
            mock_hash.return_value = "abc123"
            mock_size.return_value = 2048
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        mock_dedup.assert_called_once_with(item, "/lib/GB/GB_T_1234-2020.pdf")

    def test_getsize_os_error_returns_zero(self, organizer, mock_file_mover, tmp_path):
        """os.path.getsize 抛 OSError → file_size=0（覆盖 L205-206）"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "dedup_skipped": 0, "details": []}
        hashes = {}

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.getsize") as mock_size,
            patch.object(organizer, "_register_standard") as mock_register,
        ):
            mock_hash.return_value = "abc123"
            mock_size.side_effect = OSError("file vanished")
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        mock_register.assert_called_once_with(item, "abc123", 0)

    def test_auto_clean_remove_os_error_silent(self, organizer, mock_file_mover, mock_cfg, tmp_path):
        """auto_clean os.remove 抛 OSError → 静默忽略（覆盖 L215-216）"""
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"pdf")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "skipped_source": 0, "dedup_skipped": 0, "details": []}
        hashes = {}
        mock_file_mover.move_to_code_dir.return_value = None
        mock_file_mover.normalize_filename.return_value = "/lib/exists.pdf"
        mock_cfg.get.return_value = True

        with (
            patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
            patch("pilotstd.manager.organize.organizer.os.remove") as mock_remove,
        ):
            mock_hash.return_value = "abc123"
            mock_exists.return_value = True
            mock_remove.side_effect = OSError("permission denied")
            # 不应抛异常
            organizer._organize_nonword_item(item, mock_file_mover, result, hashes, "skip")

        assert result["skipped_exists"] == 1


# ════════════════════════════════════════════════════════════
# T3: _organize_word_item
# ════════════════════════════════════════════════════════════


class TestOrganizeWordItem:
    def test_word_with_standard_number_moves_to_code_dir(self, organizer, mock_file_mover, mock_file_index, tmp_path):
        """Word 有标准号 → 走分类归档路径"""
        src = tmp_path / "report.docx"
        src.write_bytes(b"word content")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        # std_parser 返回有效解析结果
        parsed_mock = MagicMock()
        parsed_mock.logical_code = "GB"
        parsed_mock.number = 1234
        parsed_mock.year = 2020
        parsed_mock.std_name = "Test Word"
        organizer._std_parser.parse.return_value = parsed_mock

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_exists.return_value = False
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        assert result["moved"] == 1
        assert result["word_mirrored"] == 1
        mock_move.assert_called_once()
        mock_file_index.upsert.assert_called_once()

    def test_word_without_standard_number_mirrors_source(self, organizer, tmp_path):
        """Word 无标准号 → 镜像源目录路径"""
        src = tmp_path / "notes.docx"
        src.write_bytes(b"notes")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        # std_parser 返回无效结果
        organizer._std_parser.parse.return_value = None

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer._resolve_industry_in_path") as mock_resolve,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_resolve.side_effect = lambda x: x
            mock_exists.return_value = False
            organizer._organize_word_item(item, "/lib", "/src_root", result, "skip")

        assert result["moved"] == 1
        assert result["word_mirrored"] == 1
        call_args = mock_move.call_args
        assert call_args[0][1].startswith("/lib")

    def test_word_target_exists_skip(self, organizer, tmp_path):
        """目标已存在 + on_exists='skip' → 跳过"""
        src = tmp_path / "exists.docx"
        src.write_bytes(b"word")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        parsed_mock = MagicMock()
        parsed_mock.logical_code = "GB"
        parsed_mock.number = 1234
        parsed_mock.year = 2020
        parsed_mock.std_name = "Exists"
        organizer._std_parser.parse.return_value = parsed_mock

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_exists.return_value = True
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        assert result["skipped_exists"] == 1
        mock_move.assert_not_called()

    def test_word_no_dst_path_fails(self, organizer, tmp_path):
        """dst 路径计算结果为空 → failed++（覆盖 L136-140）"""
        src = tmp_path / "badfile"
        src.write_bytes(b"word")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        # parser 返回有效结果，但 normalize_filename 返回 None
        # os.path.splitext(None) 会抛 TypeError，从源码看这是极端边界情况
        # 改用：让 strip 无效化文件名为空扩展名，normalize 也返回空
        parsed_mock = MagicMock()
        parsed_mock.logical_code = "GB"
        parsed_mock.number = 1234
        parsed_mock.year = 2020
        parsed_mock.std_name = "Bad"
        organizer._std_parser.parse.return_value = parsed_mock
        organizer._file_mover.normalize_filename.return_value = ""

        with patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip:
            # strip 返回无扩展名文件，使 ext=""，dst=""+""=""
            mock_strip.return_value = "badfile_noext"
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        assert result["failed"] == 1

    def test_word_permission_error_handled(self, organizer, tmp_path):
        """safe_move 抛 PermissionError → failed++"""
        src = tmp_path / "locked.docx"
        src.write_bytes(b"word")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        parsed_mock = MagicMock()
        parsed_mock.logical_code = "GB"
        parsed_mock.number = 1234
        parsed_mock.year = 2020
        parsed_mock.std_name = "Locked"
        organizer._std_parser.parse.return_value = parsed_mock

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_exists.return_value = False
            mock_move.side_effect = PermissionError("locked")
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        assert result["failed"] == 1

    def test_word_os_error_handled(self, organizer, tmp_path):
        """safe_move 抛 OSError → failed++"""
        src = tmp_path / "bad.docx"
        src.write_bytes(b"word")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        parsed_mock = MagicMock()
        parsed_mock.logical_code = "GB"
        parsed_mock.number = 1234
        parsed_mock.year = 2020
        parsed_mock.std_name = "Bad"
        organizer._std_parser.parse.return_value = parsed_mock

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_exists.return_value = False
            mock_move.side_effect = OSError("disk full")
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        assert result["failed"] == 1

    def test_word_no_parser_goes_to_mirror(self, organizer, tmp_path):
        """std_parser 为 None → 走镜像路径"""
        organizer._std_parser = None
        src = tmp_path / "notes.docx"
        src.write_bytes(b"notes")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer._resolve_industry_in_path") as mock_resolve,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_resolve.side_effect = lambda x: x
            mock_exists.return_value = False
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        assert result["moved"] == 1
        assert result["word_mirrored"] == 1

    def test_word_updates_index_with_word_label(self, organizer, mock_file_index, tmp_path):
        """Word 无标号镜像 → index upsert 写入 logical_code='WORD'"""
        organizer._std_parser.parse.return_value = None
        src = tmp_path / "notes.docx"
        src.write_bytes(b"notes")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer._resolve_industry_in_path") as mock_resolve,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_resolve.side_effect = lambda x: x
            mock_exists.return_value = False
            organizer._organize_word_item(item, "/lib", None, result, "skip")

        upsert_call = mock_file_index.upsert.call_args
        assert upsert_call[1]["logical_code"] == "WORD"
        assert upsert_call[1]["number"] == 0
        assert upsert_call[1]["year"] == 0

    def test_word_source_root_relpath(self, organizer, tmp_path):
        """word_source_root 匹配 → os.path.relpath（覆盖 L124）"""
        src_root = tmp_path / "src"
        src_root.mkdir()
        src = src_root / "sub" / "notes.docx"
        src.parent.mkdir()
        src.write_bytes(b"notes")
        item = _make_item(str(src))
        result = {"moved": 0, "failed": 0, "skipped_exists": 0, "word_mirrored": 0, "details": []}

        organizer._std_parser.parse.return_value = None

        with (
            patch("pilotstd.manager.organize.organizer.safe_move") as mock_move,
            patch("pilotstd.manager.organize.organizer.strip_long_path") as mock_strip,
            patch("pilotstd.manager.organize.organizer._resolve_industry_in_path") as mock_resolve,
            patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_makedirs,
            patch("pilotstd.manager.organize.organizer.os.path.exists") as mock_exists,
        ):
            mock_strip.side_effect = lambda x: x
            mock_resolve.side_effect = lambda x: x
            mock_exists.return_value = False
            organizer._organize_word_item(item, "/lib", str(src_root), result, "skip")

        assert result["moved"] == 1


# ════════════════════════════════════════════════════════════
# T4: _register_standard
# ════════════════════════════════════════════════════════════


class TestRegisterStandard:
    def test_insert_executes_sql(self, organizer, mock_file_index):
        item = _make_item("/fake/path.pdf")
        organizer._register_standard(item, "abc123", 4096)
        mock_file_index.db.execute.assert_called_once()

    def test_db_exception_is_caught(self, organizer, mock_file_index):
        mock_file_index.db.execute.side_effect = Exception("DB locked")
        item = _make_item("/fake/path.pdf")
        # 不应向上抛异常
        organizer._register_standard(item, "abc123", 4096)


# ════════════════════════════════════════════════════════════
# T5: _dedup_standard
# ════════════════════════════════════════════════════════════


class TestDedupStandard:
    def test_no_file_index_returns_early(self, organizer):
        organizer._file_index = None
        item = _make_item("/fake/path.pdf")
        # 不应抛异常
        organizer._dedup_standard(item, "/new/path.pdf")

    def test_find_duplicates_and_cleanup(self, organizer, mock_file_index, tmp_path):
        """找到旧路径 → os.remove + file_index.remove"""
        old_file = tmp_path / "old.pdf"
        old_file.write_bytes(b"old")
        mock_file_index.find_by_standard.return_value = [
            {"file_path": str(old_file)},
            {"file_path": "/new/path.pdf"},  # 同路径跳过
        ]

        with patch("pilotstd.manager.organize.organizer.os.remove") as mock_remove:
            item = _make_item("/new/path.pdf")
            organizer._dedup_standard(item, "/new/path.pdf")

        mock_remove.assert_called_once_with(str(old_file))
        # 旧路径被 remove
        mock_file_index.remove.assert_called_once_with(str(old_file))

    def test_duplicate_path_not_on_disk_skips_remove(self, organizer, mock_file_index):
        """旧路径在 DB 中但文件不存在 → 仅调 file_index.remove"""
        mock_file_index.find_by_standard.return_value = [
            {"file_path": "/nonexistent/old.pdf"}
        ]

        with patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile:
            mock_isfile.return_value = False
            item = _make_item("/new/path.pdf")
            organizer._dedup_standard(item, "/new/path.pdf")

        mock_file_index.remove.assert_called_once_with("/nonexistent/old.pdf")

    def test_os_remove_error_is_silent(self, organizer, mock_file_index, tmp_path):
        """os.remove 失败 → 静默忽略，仍调 file_index.remove"""
        old_file = tmp_path / "old.pdf"
        old_file.write_bytes(b"old")
        mock_file_index.find_by_standard.return_value = [
            {"file_path": str(old_file)}
        ]

        with patch("pilotstd.manager.organize.organizer.os.path.isfile") as mock_isfile:
            with patch("pilotstd.manager.organize.organizer.os.remove") as mock_remove:
                mock_isfile.return_value = True
                mock_remove.side_effect = OSError("permission denied")
                item = _make_item("/new/path.pdf")
                organizer._dedup_standard(item, "/new/path.pdf")

        mock_file_index.remove.assert_called_once_with(str(old_file))


# ════════════════════════════════════════════════════════════
# T6: _log_organize_summary + _ensure_target_dir
# ════════════════════════════════════════════════════════════


class TestLogSummary:
    def test_summary_logs_all_counters(self, organizer, caplog):
        import logging

        caplog.set_level(logging.INFO, logger="pilotstd.manager.organize.organizer")
        result = {
            "moved": 5, "word_mirrored": 2, "skipped_exists": 1,
            "skipped_source": 0, "dedup_skipped": 3, "failed": 1, "details": [],
        }
        organizer._log_organize_summary(result)
        assert "5" in caplog.text
        assert "2" in caplog.text
        assert "3" in caplog.text
        assert "1" in caplog.text

    def test_notification_triggered_on_failure(self, organizer, caplog):
        """failed > 0 且有 notification_mgr → 发送通知"""
        organizer._core = MagicMock()
        organizer._core.notification_mgr = MagicMock()
        result = {"moved": 0, "word_mirrored": 0, "skipped_exists": 0,
                  "skipped_source": 0, "dedup_skipped": 0, "failed": 2, "details": []}
        organizer._log_organize_summary(result)
        organizer._core.notification_mgr.send_event.assert_called_once()

    def test_notification_exception_silent(self, organizer):
        """通知发送异常 → 静默忽略"""
        organizer._core = MagicMock()
        organizer._core.notification_mgr.send_event.side_effect = RuntimeError("boom")
        result = {"moved": 0, "word_mirrored": 0, "skipped_exists": 0,
                  "skipped_source": 0, "dedup_skipped": 0, "failed": 1, "details": []}
        # 不应抛异常
        organizer._log_organize_summary(result)


class TestEnsureTargetDir:
    def test_creates_directory(self, organizer, tmp_path):
        target = str(tmp_path / "new_dir")
        with patch("pilotstd.manager.organize.organizer.os.makedirs") as mock_mkdir:
            organizer._ensure_target_dir(target)
            mock_mkdir.assert_called_once_with(target, exist_ok=True)
