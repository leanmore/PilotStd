# tests/test_ui_self_check.py
"""_self_check.py 单元测试 — 启动自检函数全覆盖。"""

import os
import unittest
from unittest.mock import MagicMock, patch

from pilotstd.ui.core._self_check import (
    _is_enabled,
    run_self_check,
    _check_parsed_results_consistency,
    _check_core_attributes,
    _check_mgr_proxy,
)


class TestIsEnabled(unittest.TestCase):
    """_is_enabled — 环境变量检查"""

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "1"}, clear=True)
    def test_enabled_when_set_to_1(self):
        self.assertTrue(_is_enabled())

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "0"}, clear=True)
    def test_disabled_when_set_to_0(self):
        self.assertFalse(_is_enabled())

    @patch.dict(os.environ, {}, clear=True)
    def test_disabled_when_not_set(self):
        self.assertFalse(_is_enabled())

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "true"}, clear=True)
    def test_disabled_for_non_1_value(self):
        self.assertFalse(_is_enabled())


class TestRunSelfCheck(unittest.TestCase):
    """run_self_check — 顶层调度"""

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "0"}, clear=True)
    def test_disabled_returns_true_immediately(self):
        window = MagicMock()
        result = run_self_check(window)
        self.assertTrue(result)

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "1"}, clear=True)
    @patch("pilotstd.ui.core._self_check._check_parsed_results_consistency")
    @patch("pilotstd.ui.core._self_check._check_core_attributes")
    @patch("pilotstd.ui.core._self_check._check_mgr_proxy")
    def test_all_pass_returns_true(self, mock_proxy, mock_attrs, mock_parsed):
        mock_parsed.return_value = True
        mock_attrs.return_value = True
        mock_proxy.return_value = True
        window = MagicMock()
        result = run_self_check(window)
        self.assertTrue(result)

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "1"}, clear=True)
    @patch("pilotstd.ui.core._self_check._check_parsed_results_consistency")
    @patch("pilotstd.ui.core._self_check._check_core_attributes")
    @patch("pilotstd.ui.core._self_check._check_mgr_proxy")
    def test_one_fail_returns_false(self, mock_proxy, mock_attrs, mock_parsed):
        mock_parsed.return_value = True
        mock_attrs.return_value = False
        mock_proxy.return_value = True
        window = MagicMock()
        result = run_self_check(window)
        self.assertFalse(result)

    @patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "1"}, clear=True)
    @patch("pilotstd.ui.core._self_check._check_parsed_results_consistency")
    @patch("pilotstd.ui.core._self_check._check_core_attributes")
    @patch("pilotstd.ui.core._self_check._check_mgr_proxy")
    def test_all_fail_returns_false(self, mock_proxy, mock_attrs, mock_parsed):
        mock_parsed.return_value = False
        mock_attrs.return_value = False
        mock_proxy.return_value = False
        window = MagicMock()
        result = run_self_check(window)
        self.assertFalse(result)


class TestCheckParsedResultsConsistency(unittest.TestCase):
    """_check_parsed_results_consistency — Handler 间 parsed_results 一致性"""

    def test_no_core_skips(self):
        window = MagicMock(spec=[])
        result = _check_parsed_results_consistency(window)
        self.assertTrue(result)

    def test_all_handlers_same_id(self):
        shared = [1, 2, 3]
        core = MagicMock()
        core.scan = MagicMock(_parsed_results=shared)
        core.query = MagicMock(_parsed_results=shared)
        core.archive = MagicMock(_parsed_results=shared)
        core.auto = MagicMock(_parsed_results=shared)
        core.actions = MagicMock(_parsed_results=shared)
        window = MagicMock(_core=core)
        result = _check_parsed_results_consistency(window)
        self.assertTrue(result)

    def test_different_id_returns_false(self):
        core = MagicMock()
        core.scan = MagicMock(_parsed_results=[1])
        core.query = MagicMock(_parsed_results=[2])  # 不同对象
        core.archive = MagicMock(_parsed_results=[1])
        core.auto = MagicMock(_parsed_results=[1])
        core.actions = MagicMock(_parsed_results=[1])
        window = MagicMock(_core=core)
        result = _check_parsed_results_consistency(window)
        self.assertFalse(result)

    def test_missing_handler_skipped(self):
        shared = [1]
        core = MagicMock()
        core.scan = MagicMock(_parsed_results=shared)
        core.query = None  # 未初始化
        core.archive = MagicMock(_parsed_results=shared)
        core.auto = MagicMock(_parsed_results=shared)
        core.actions = MagicMock(_parsed_results=shared)
        window = MagicMock(_core=core)
        result = _check_parsed_results_consistency(window)
        self.assertTrue(result)

    def test_handler_without_parsed_results_skipped(self):
        shared = [1]
        core = MagicMock()
        core.scan = MagicMock(_parsed_results=shared)
        core.query = MagicMock(spec=[])  # 无 _parsed_results
        core.archive = MagicMock(_parsed_results=shared)
        core.auto = MagicMock(_parsed_results=shared)
        core.actions = MagicMock(_parsed_results=shared)
        window = MagicMock(_core=core)
        result = _check_parsed_results_consistency(window)
        self.assertTrue(result)


class TestCheckCoreAttributes(unittest.TestCase):
    """_check_core_attributes — Handler 初始化检查"""

    def test_no_core_skips(self):
        window = MagicMock(spec=[])
        result = _check_core_attributes(window)
        self.assertTrue(result)

    def test_all_handlers_present(self):
        core = MagicMock()
        for attr in ["scan", "query", "download", "archive", "auto", "announce", "cleanup", "export", "actions"]:
            setattr(core, attr, MagicMock())
        window = MagicMock(_core=core)
        result = _check_core_attributes(window)
        self.assertTrue(result)

    def test_missing_handler_returns_false(self):
        core = MagicMock()
        for attr in ["scan", "query", "download", "archive", "auto", "announce", "cleanup", "export", "actions"]:
            setattr(core, attr, MagicMock())
        core.query = None
        window = MagicMock(_core=core)
        result = _check_core_attributes(window)
        self.assertFalse(result)

    def test_all_missing_returns_false(self):
        core = MagicMock()
        for attr in ["scan", "query", "download", "archive", "auto", "announce", "cleanup", "export", "actions"]:
            setattr(core, attr, None)
        window = MagicMock(_core=core)
        result = _check_core_attributes(window)
        self.assertFalse(result)


class TestCheckMgrProxy(unittest.TestCase):
    """_check_mgr_proxy — StandardManager 属性代理检查"""

    def test_no_mgr_skips(self):
        window = MagicMock(spec=[])
        result = _check_mgr_proxy(window)
        self.assertTrue(result)

    def test_all_key_attrs_present(self):
        mgr = MagicMock()
        mgr.task_queue = 1
        mgr.query_engine = 1
        mgr.file_index = 1
        mgr.download_engine = 1
        mgr.router = 1
        window = MagicMock(_mgr=mgr)
        result = _check_mgr_proxy(window)
        self.assertTrue(result)

    def test_missing_attr_returns_false(self):
        # spec=[] 确保非显式设置的属性访问抛出 AttributeError
        mgr = MagicMock(spec=[])
        mgr.task_queue = 1
        mgr.query_engine = 1
        mgr.file_index = 1
        mgr.download_engine = 1
        # router 未设置 → getattr 抛 AttributeError
        window = MagicMock(_mgr=mgr)
        result = _check_mgr_proxy(window)
        self.assertFalse(result)

    def test_multiple_missing_returns_false(self):
        mgr = MagicMock(spec=[])  # spec=[] 确保未知属性抛出 AttributeError
        window = MagicMock(_mgr=mgr)
        result = _check_mgr_proxy(window)
        self.assertFalse(result)
