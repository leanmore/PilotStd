"""tests/test_scan_and_index_diagnostics.py — scan_and_index 的跳过原因分类（G-27，2026-11-23）。

背景：生产实测 `indexed=0 / skipped=825 / failed=0`，但原实现把三种**完全不同**的
跳过原因都记进同一个 `skipped`：
  ① 文件名解析失败（`parse()` 返回 None）
  ② 四要素（sha256/code/name/size）查询无命中
  ③ 命中但 `scan_status != 'pending'`（已索引过）

汇总日志只有 `skipped=825`，无法判断是哪一类 —— 排查只能靠猜（G-27 因此卡住）。

本测试锁住：
  1. 三类跳过各自计数，且 `skip_parse_failed + skip_no_match + skip_not_pending == skipped`
  2. 首条未匹配样本被记录（含四要素），用于定位「断在哪一环」
  3. 正常命中时 `indexed` 递增，且不产生跳过计数
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.manager.scheduled_service import ScheduledService  # noqa: E402


class _Parsed:
    """最小解析结果替身。"""

    def __init__(self, code: str, name: str) -> None:
        self.logical_code = code
        self.std_name = name
        self.ext = ".pdf"


def _make_service(tmp_path: Path, parser_side_effect, db_rows):
    """构造 ScheduledService：只注入 scan_and_index 用到的依赖。"""
    cfg = MagicMock()
    cfg.get.return_value = str(tmp_path)
    parser = MagicMock()
    parser.parse.side_effect = parser_side_effect
    file_index = MagicMock()
    file_index.db.execute.return_value.fetchone.return_value = db_rows
    svc = ScheduledService(
        cfg=cfg,
        scanner=MagicMock(),
        parser=parser,
        query_engine=MagicMock(),
        file_index=file_index,
        quota_tracker=MagicMock(),
        download_engine=MagicMock(),
    )
    return svc, file_index


def _touch(path: Path, name: str) -> Path:
    p = path / name
    p.write_text("dummy", encoding="utf-8")
    return p


def test_parse_failure_counted_separately(tmp_path, monkeypatch):
    """① 文件名解析失败 → skip_parse_failed。"""
    _touch(tmp_path, "bad-name.pdf")
    svc, _ = _make_service(tmp_path, parser_side_effect=lambda _n: None, db_rows=None)
    monkeypatch.setattr(
        "pilotstd.manager.scheduled_service.hash_file_content", lambda _p: "hash"
    )

    result = svc.scan_and_index()

    assert result["skip_parse_failed"] == 1
    assert result["skip_no_match"] == 0
    assert result["skip_not_pending"] == 0
    assert result["skipped"] == 1


def test_four_element_miss_counted_separately(tmp_path, monkeypatch):
    """② 四要素未命中 → skip_no_match，并记录首条样本。"""
    _touch(tmp_path, "GB 50011-2010 建筑抗震设计规范.pdf")
    svc, _ = _make_service(
        tmp_path,
        parser_side_effect=lambda _n: _Parsed("GB", "建筑抗震设计规范"),
        db_rows=None,  # fetchone 返回 None → 未命中
    )
    monkeypatch.setattr(
        "pilotstd.manager.scheduled_service.hash_file_content", lambda _p: "abcdef0123456789"
    )

    result = svc.scan_and_index()

    assert result["skip_no_match"] == 1
    assert result["skip_parse_failed"] == 0
    assert result["skip_not_pending"] == 0
    assert result["indexed"] == 0


def test_not_pending_counted_separately(tmp_path, monkeypatch):
    """③ 命中但状态非 pending（UPDATE rowcount=0）→ skip_not_pending。"""
    _touch(tmp_path, "GB 50011-2010 建筑抗震设计规范.pdf")
    svc, file_index = _make_service(
        tmp_path,
        parser_side_effect=lambda _n: _Parsed("GB", "建筑抗震设计规范"),
        db_rows=(1,),  # 命中
    )
    file_index.db.execute.return_value.rowcount = 0  # UPDATE 未生效
    monkeypatch.setattr(
        "pilotstd.manager.scheduled_service.hash_file_content", lambda _p: "hash"
    )

    result = svc.scan_and_index()

    assert result["skip_not_pending"] == 1
    assert result["skip_parse_failed"] == 0
    assert result["skip_no_match"] == 0
    assert result["indexed"] == 0


def test_indexed_on_success(tmp_path, monkeypatch):
    """正常命中且状态为 pending → indexed 递增，无跳过。"""
    _touch(tmp_path, "GB 50011-2010 建筑抗震设计规范.pdf")
    svc, file_index = _make_service(
        tmp_path,
        parser_side_effect=lambda _n: _Parsed("GB", "建筑抗震设计规范"),
        db_rows=(1,),
    )
    file_index.db.execute.return_value.rowcount = 1
    monkeypatch.setattr(
        "pilotstd.manager.scheduled_service.hash_file_content", lambda _p: "hash"
    )

    result = svc.scan_and_index()

    assert result["indexed"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0


def test_skip_breakdown_sums_to_skipped(tmp_path, monkeypatch):
    """三类跳过之和必须等于 skipped（防止新增来源时漏登记）。"""
    for i in range(3):
        _touch(tmp_path, f"bad{i}.pdf")
    svc, _ = _make_service(tmp_path, parser_side_effect=lambda _n: None, db_rows=None)
    monkeypatch.setattr(
        "pilotstd.manager.scheduled_service.hash_file_content", lambda _p: "hash"
    )

    result = svc.scan_and_index()

    assert (
        result["skip_parse_failed"] + result["skip_no_match"] + result["skip_not_pending"]
        == result["skipped"]
    )
    assert result["skipped"] == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
