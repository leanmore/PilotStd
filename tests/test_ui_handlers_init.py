# tests/test_ui_handlers_init.py
"""handlers/__init__.py 测试 — 导入正确性、__all__ 完整性。"""

import unittest

from pilotstd.ui.core.handlers import (
    CleanupHandler,
    PersistenceHandler,
    ProjectHandler,
    SettingsHandler,
)


class TestHandlersInit(unittest.TestCase):
    """handlers/__init__.py — 公开导入验证"""

    def test_all_classes_importable(self):
        """__all__ 中列出的所有类都能成功导入"""
        classes = [
            CleanupHandler,
            PersistenceHandler,
            ProjectHandler,
            SettingsHandler,
        ]
        for cls in classes:
            self.assertIsNotNone(cls, f"{cls.__name__} 不应为 None")

    def test_all_list_matches_imports(self):
        """验证 __all__ 与导出的类一致"""
        from pilotstd.ui.core.handlers import __all__

        expected = [
            "CleanupHandler",
            "PersistenceHandler",
            "ProjectHandler",
            "SettingsHandler",
        ]
        self.assertEqual(sorted(__all__), sorted(expected))

    def test_settings_handler_is_class(self):
        self.assertTrue(isinstance(SettingsHandler, type))

    def test_cleanup_handler_is_class(self):
        self.assertTrue(isinstance(CleanupHandler, type))
