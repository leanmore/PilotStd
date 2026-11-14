"""P2-10 批 4：UI 两处「用户主动操作失败、界面却看起来正常」的 WARNING 锁定。

对应决策（见 docs/debt/p2-10-silent-errors-triage.md §九）：
1. `CleanupHandler.scan_empty_dirs()`：扫描失败 → 界面只会显示"没有可清理目录"，
   看着像成功结果；
2. `RulesPage._get_rules()`：`sites.rules` JSON 损坏 → 静默按空表展示，用户再保存
   一次就把坏串覆盖成空表（配置静默丢失）。

两处都从 debug/return 升到 WARNING；控制流与返回值不变。放在 tests/gui/ 是因为
两个模块都 import PyQt6（backend 套件受 G-053 约束不得 import pilotstd.ui）。
"""

from __future__ import annotations

import logging

from pilotstd.ui.core.handlers._cleanup import CleanupHandler
from pilotstd.ui.pages.rules_page import RulesPage


class _Cfg:
    """最小配置替身：只实现被测代码用到的 get/set。"""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value


class _Engine:
    """最小引擎替身：扫描结果固定为空，用于把失败点隔离在 os.scandir。"""

    def scan_empty_dirs(self, dir_tree, expire_folder_name=""):
        return [], []


def test_cleanup_scan_failure_warns(tmp_path, caplog):
    """目录不可读/不存在 → WARNING，且仍返回空结果（不抛给 UI）。"""
    handler = object.__new__(CleanupHandler)
    handler._config = _Cfg()
    handler._engine = _Engine()

    with caplog.at_level(logging.WARNING, logger="pilotstd.ui.core.handlers._cleanup"):
        empty, expire, folder = handler.scan_empty_dirs(str(tmp_path / "missing"))

    assert (empty, expire) == ([], [])
    assert folder  # 过期目录名来自配置默认值
    assert any("scan cleanup dir tree failed" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]


def test_rules_json_corrupt_warns(caplog):
    """规则 JSON 损坏 → WARNING + 返回空列表（不静默吞掉损坏事实）。"""
    page = RulesPage.__new__(RulesPage)  # QWidget 子类必须走 sip 的 __new__
    page._config = _Cfg({"sites.rules": "{not json"})

    with caplog.at_level(logging.WARNING, logger="pilotstd.ui.pages.rules_page"):
        rules = page._get_rules()

    assert rules == []
    assert any("site rules JSON parse failed" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]
