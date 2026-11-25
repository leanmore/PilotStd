"""写入端 `effect_status` 归一测试（批次 11 / N3，P2 代码侧）。

背景（`docs/plans/2026-11-25-p1-unknown-refresh.md` §5.4）：`organizer.py` 原样把
`effect_status` 写进 `file_index.status`；`map_status('未生效')` 仍原样透传
（`pilotstd/query/search_strategy.py` 的 `STATUS_MAP` 无该条目）→ 即便批次 12 清洗了存量，
后续归档仍会再生 `未生效` 脏值。

修法：写入前走统一归一 `normalize_status_for_write()`（与读取侧 `normalize_status()` 同源），
`未生效` → `即将实施`；批次 12 存量清洗后行为自然收敛。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.core.status import Status
from pilotstd.manager.organize.organizer import OrganizerCore


def _make_item(effect_status: str, src: str = "/src/doc.pdf"):
    p = MagicMock()
    p.source_path = src
    p.logical_code = "GB"
    p.number = 1234
    p.year = 2020
    p.part = None
    p.std_name = "测试标准"
    p.effect_status = effect_status
    p.raw_number = "GB 1234-2020"
    p.get_full_number.return_value = "GB 1234-2020"
    return p


@pytest.fixture
def organizer(tmp_path):
    cfg = MagicMock()
    cfg.get.return_value = {}
    file_index = MagicMock()
    file_index.upsert.return_value = None
    dir_builder = MagicMock()
    mover = MagicMock()
    mover.normalize_filename.return_value = str(tmp_path / "lib" / "GB" / "GB_1234-2020.pdf")
    mover.move_to_code_dir.return_value = str(tmp_path / "lib" / "GB" / "GB_1234-2020.pdf")
    with patch("pilotstd.manager.organize.organizer.StandardParser"):
        org = OrganizerCore(cfg, file_index, dir_builder, mover)
    org._dedup_standard = MagicMock()
    return org, file_index, mover


def _run(organizer, effect_status: str) -> dict:
    org, file_index, mover = organizer
    item = _make_item(effect_status)
    result = {"moved": 0, "failed": 0, "skipped_exists": 0, "skipped_source": 0,
              "dedup_skipped": 0, "details": []}
    with (
        patch("pilotstd.manager.organize.organizer.hash_file_content") as mock_hash,
        patch("pilotstd.manager.organize.organizer.os.path.getsize", return_value=1024),
    ):
        mock_hash.return_value = "hash123"
        org._organize_nonword_item(item, mover, result, {}, "skip")
    assert result["moved"] == 1
    return file_index.upsert.call_args.kwargs


class TestEffectStatusNormalizationOnWrite:
    def test_legacy_not_effective_written_as_upcoming(self, organizer):
        """**验收**：`effect_status='未生效'` 写入 `file_index.status` 时必须归一为 `即将实施`。"""
        kwargs = _run(organizer, "未生效")
        assert kwargs["status"] == Status.UPCOMING.value
        assert kwargs["status"] != "未生效", "不得再向 file_index 透传历史脏值"

    def test_upcoming_unchanged(self, organizer):
        kwargs = _run(organizer, Status.UPCOMING.value)
        assert kwargs["status"] == Status.UPCOMING.value

    def test_withdrawn_spelling_keeps_existing_data_value(self, organizer):
        """`废止` 落库保持既有数据值 `废止`（不回写 `已废止`，否则筛选口径会错位）。"""
        kwargs = _run(organizer, Status.WITHDRAWN.value)
        assert kwargs["status"] == Status.WITHDRAWN.value

    def test_normalized_spelling_written_back_to_existing_data_value(self, organizer):
        """若上游给的是规范拼写 `已废止`，落库统一回既有数据值 `废止`。"""
        kwargs = _run(organizer, Status.WITHDRAWN_NORMALIZED.value)
        assert kwargs["status"] == Status.WITHDRAWN.value

    def test_empty_effect_status_defaults_to_active(self, organizer):
        kwargs = _run(organizer, "")
        assert kwargs["status"] == Status.ACTIVE.value

    def test_unknown_enum_external_value_not_silently_rewritten(self, organizer):
        """枚举外且无别名的值原样落库（不猜测语义；存量数据治理属批次 12）。"""
        kwargs = _run(organizer, "未实施")
        assert kwargs["status"] == "未实施"


class TestNormalizeStatusForWrite:
    """`normalize_status_for_write()` 纯函数口径（与读取侧 `normalize_status()` 同源）。"""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("未生效", Status.UPCOMING.value),
            (f" {Status.UPCOMING.value} ", Status.UPCOMING.value),
            (Status.WITHDRAWN.value, Status.WITHDRAWN.value),
            (Status.WITHDRAWN_NORMALIZED.value, Status.WITHDRAWN.value),
            (Status.VOIDED.value, Status.VOIDED.value),
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalize_status_for_write(self, raw, expected):
        from pilotstd.core.status import normalize_status_for_write

        assert normalize_status_for_write(raw) == expected
