# tests/test_remaining_batch3_logs.py — U-3/U-4 批 3：查询/UI 5 条日志升级
"""锁定批 3 的代表点：轮转/标题/搜索解析/下载 CSV/导出目录树失败必须 WARNING。"""

import logging
from types import SimpleNamespace

from pilotstd.announce.notifier import AnnounceNotifier
from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.rotator import SiteRotator
from pilotstd.ui.core.handlers.download_flow_engine import DownloadFlowEngine
from pilotstd.ui.main_window.parts import _export_ops


class _BadDB:
    def fetchall(self, *a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("db down")

    def execute(self, *a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("db down")


class _FakeAdapter(BaseAdapter):
    site_name = "fake-site"
    site_label = "Fake"

    def _build_search_data(self, search_term: str) -> dict:
        return {"q": search_term}


def test_rotator_reset_failure_warns(caplog) -> None:
    """清空 adapter_state 冷却记录失败 → WARNING（日志不再谎报"已重置"）。"""
    rotator = SiteRotator(sites=[], db=_BadDB())
    with caplog.at_level(logging.WARNING, logger="pilotstd.query.rotator"):
        rotator.reset_all_cooldowns()

    assert any("站点轮转状态更新失败" in r.message for r in caplog.records)


def test_notifier_title_fetch_failure_warns(caplog) -> None:
    """公告标题拉取失败 → WARNING + []。"""
    notifier = AnnounceNotifier(notification_mgr=None, mgr_db=_BadDB())
    with caplog.at_level(logging.WARNING, logger="pilotstd.announce.notifier"):
        assert notifier._fetch_announcement_titles("2026-11-09T00:00:00+08:00") == []

    assert any("公告标题拉取失败" in r.message for r in caplog.records)


def test_adapter_search_json_failure_warns(monkeypatch, caplog) -> None:
    """搜索响应 JSON 解析失败 → WARNING（带适配器名）+ []。"""
    import pilotstd.query.network as network

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            raise ValueError("bad json")

    monkeypatch.setattr(network, "safe_post", lambda *a, **k: _Resp())
    adapter = object.__new__(_FakeAdapter)
    adapter._session = SimpleNamespace(headers={})

    with caplog.at_level(logging.WARNING, logger="pilotstd.query.adapters.base"):
        assert adapter._post_search_candidates("GB/T 1") == []

    assert any("搜索响应解析失败" in r.message for r in caplog.records)


def test_download_csv_parse_failure_warns(monkeypatch, caplog) -> None:
    """下载 CSV 解析失败 → WARNING + []。"""
    import csv as csv_mod

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("bad csv")

    # 该函数在体内 `import csv`，故 patch 全局 csv.DictReader（同一模块对象）
    monkeypatch.setattr(csv_mod, "DictReader", _boom)
    with caplog.at_level(logging.WARNING, logger="pilotstd.ui.core.handlers.download_flow_engine"):
        assert DownloadFlowEngine.parse_download_csv("standard_number\nGB 1\n") == []

    assert any("下载 CSV 解析失败" in r.message for r in caplog.records)


def test_export_folder_tree_scan_failure_warns(tmp_path, monkeypatch, caplog) -> None:
    """导出目录树 scandir 无权限 → WARNING（导出内容被截断可见）。"""

    def _boom(path):
        raise PermissionError("denied")

    monkeypatch.setattr(_export_ops.os, "scandir", _boom)
    lines: list = []
    with caplog.at_level(logging.WARNING, logger="pilotstd.ui"):
        _export_ops._collect_folder_tree(None, str(tmp_path), lines, "", 0)

    assert any("导出失败" in r.message for r in caplog.records)
