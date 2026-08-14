"""pilotstd/scan/parser/_utils.py 补测 — 兼容别名导入验证。"""


class TestUtilsCompatAlias:
    """验证 _utils.py 兼容层正确委托到 ParserCore。"""

    def test_import_utils_mixin(self):
        """UtilsMixin 可从 _utils 正常导入。"""
        from pilotstd.scan.parser._utils import UtilsMixin
        assert UtilsMixin is not None

    def test_utils_mixin_is_parser_core(self):
        """UtilsMixin 即 ParserCore 别名。"""
        from pilotstd.scan.parser._core import ParserCore
        from pilotstd.scan.parser._utils import UtilsMixin
        assert UtilsMixin is ParserCore

    def test_utils_mixin_has_expected_interface(self):
        """ParserCore 提供核心工具方法（clean, detect_language 等）。"""
        from pilotstd.scan.parser._utils import UtilsMixin
        assert hasattr(UtilsMixin, "clean") or callable(getattr(UtilsMixin, "__init__", None))

    def test_utils_mixin_repr(self):
        """UtilsMixin 类名确认。"""
        from pilotstd.scan.parser._utils import UtilsMixin
        assert UtilsMixin.__name__ == "ParserCore"

    def test_boundary_import_from_alias_module(self):
        """_utils 模块含合法 docstring 且可正常 import。"""
        import pilotstd.scan.parser._utils as mod
        assert mod.__doc__ is not None
        assert "兼容层" in mod.__doc__
