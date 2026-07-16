"""覆盖 pilotstd/ui/ 下 misc 模块：rules_page, self_check。"""
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QDialog, QMessageBox


# ═══ _core/_self_check.py ═══
class TestSelfCheck:
    def test_is_enabled(self):
        import os
        with patch.dict(os.environ, {"PILOTSTD_SELF_CHECK": "1"}):
            from pilotstd.ui.core._self_check import _is_enabled
            assert _is_enabled() is True

    def test_is_disabled_by_default(self):
        import os
        with patch.dict(os.environ, {}, clear=True):
            from pilotstd.ui.core._self_check import _is_enabled
            assert _is_enabled() is False

    def test_run_self_check_no_core(self):
        from pilotstd.ui.core._self_check import run_self_check
        fake_window = MagicMock()
        fake_window._mgr = MagicMock()
        run_self_check(fake_window)

    def test_check_parsed_results_consistency(self):
        from pilotstd.ui.core._self_check import _check_parsed_results_consistency
        _check_parsed_results_consistency(MagicMock())

    def test_check_core_attributes(self):
        from pilotstd.ui.core._self_check import _check_core_attributes
        fake_window = MagicMock()
        fake_window._core = MagicMock()
        _check_core_attributes(fake_window)

    def test_check_mgr_proxy(self):
        from pilotstd.ui.core._self_check import _check_mgr_proxy
        fake_window = MagicMock()
        fake_window._mgr = MagicMock()
        _check_mgr_proxy(fake_window)


# ═══ pages/rules_page.py — mock QFileDialog ═══
class TestRulesPage:
    def test_create_rules_page(self, qapp):
        from pilotstd.ui.pages.rules_page import RulesPage
        cfg = MagicMock()
        cfg.get.return_value = True
        page = RulesPage(cfg)
        assert page is not None

    def test_add_rule_creates_dialog(self, qapp):
        from pilotstd.ui.pages.rules_page import RulesPage
        cfg = MagicMock()
        cfg.get.return_value = True
        cfg.list_query_rules.return_value = []
        page = RulesPage(cfg)
        with patch("pilotstd.ui.pages.rules_page.RuleEditDialog") as mock_dlg:
            mock_dlg.return_value.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.return_value.get_rule.return_value = {"name": "test", "site_id": "std_gov", "type": "query"}
            page._on_add_rule()

    def test_import_json_cancelled(self, qapp):
        from pilotstd.ui.pages.rules_page import RulesPage
        cfg = MagicMock()
        cfg.get.return_value = True
        cfg.list_query_rules.return_value = []
        page = RulesPage(cfg)
        with patch("pilotstd.ui.pages.rules_page.QFileDialog.getOpenFileName", return_value=("", "")):
            page._on_import_json()

    def test_import_json_success(self, qapp):
        from pilotstd.ui.pages.rules_page import RulesPage
        cfg = MagicMock()
        cfg.get.return_value = True
        cfg.list_query_rules.return_value = []
        page = RulesPage(cfg)
        with patch("pilotstd.ui.pages.rules_page.QFileDialog.getOpenFileName", return_value=("/fake/r.json", "")):
            cfg.import_rules = MagicMock(return_value=3)
            page._on_import_json()

    def test_export_json_no_rules(self, qapp):
        from pilotstd.ui.pages.rules_page import RulesPage
        cfg = MagicMock()
        cfg.get.return_value = True
        cfg.list_query_rules.return_value = []
        page = RulesPage(cfg)
        page._on_export_json()

    def test_export_json_success(self, qapp):
        from pilotstd.ui.pages.rules_page import RulesPage
        cfg = MagicMock()
        cfg.get.return_value = True
        rule = {"name": "r1", "site_id": "std_gov", "type": "query", "captcha": "none"}
        cfg.list_query_rules.return_value = [rule]
        page = RulesPage(cfg)
        with patch("pilotstd.ui.pages.rules_page.QFileDialog.getSaveFileName", return_value=("/fake/out.json", "")):
            page._on_export_json()


# ═══ pending_query_dialog.py ═══
class TestPendingQueryGap:
    def test_dialog_creates(self, qapp):
        from pilotstd.ui.pending_query_dialog import PendingQueryDialog
        mgr = MagicMock()
        mgr.get_cooldown_info.return_value = {}
        items = [MagicMock()]
        items[0].get_full_number.return_value = "GB/T 1-2020"
        dlg = PendingQueryDialog(mgr, items, None)
        assert dlg is not None
        dlg.close()
