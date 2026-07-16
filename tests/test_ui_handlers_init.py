# tests/test_ui_handlers_init.py
"""handlers/__init__.py 测试 — 导入正确性、__all__ 完整性。"""

import unittest

from pilotstd.ui.core.handlers import (
    ActionsHandler,
    CleanupHandler,
    DialogHandler,
    ExportHandler,
    FileDialogHandler,
    FileTreeHandler,
    PersistenceHandler,
    ProjectHandler,
    SettingsHandler,
    TableHandler,
    TableHelperHandler,
    ThemeHandler,
    UISetupHandler,
)


class TestHandlersInit(unittest.TestCase):
    """handlers/__init__.py — 公开导入验证"""

    def test_all_classes_importable(self):
        """__all__ 中列出的所有类都能成功导入"""
        classes = [
            ActionsHandler, CleanupHandler, DialogHandler, ExportHandler,
            FileDialogHandler, FileTreeHandler, PersistenceHandler,
            ProjectHandler, SettingsHandler, TableHandler,
            TableHelperHandler, ThemeHandler, UISetupHandler,
        ]
        for cls in classes:
            self.assertIsNotNone(cls, f"{cls.__name__} 不应为 None")

    def test_all_list_matches_imports(self):
        """验证 __all__ 与导出的类一致"""
        from pilotstd.ui.core.handlers import __all__
        expected = [
            "ActionsHandler", "CleanupHandler", "DialogHandler",
            "ExportHandler", "FileDialogHandler", "FileTreeHandler",
            "PersistenceHandler", "ProjectHandler", "SettingsHandler",
            "TableHandler", "TableHelperHandler", "ThemeHandler",
            "UISetupHandler",
        ]
        self.assertEqual(sorted(__all__), sorted(expected))

    def test_actions_handler_is_class(self):
        self.assertTrue(isinstance(ActionsHandler, type))

    def test_settings_handler_is_class(self):
        self.assertTrue(isinstance(SettingsHandler, type))

    def test_theme_handler_is_class(self):
        self.assertTrue(isinstance(ThemeHandler, type))
