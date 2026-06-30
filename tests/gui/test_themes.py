# tests/gui/test_themes.py
# 测试 themes 模块 — 配色方案、QSS 生成、主题切换、默认主题

from unittest.mock import MagicMock, patch

from pilotstd.ui.themes import (
    COLOR_SCHEMES,
    COMMON_QSS,
    DARK_THEMES,
    apply_theme,
    generate_qss,
)


class TestColorSchemes:
    """配色方案字典测试。"""

    REQUIRED_KEYS = [
        "bg",
        "surface",
        "surface_alt",
        "text",
        "text_bright",
        "text_dim",
        "text_heading",
        "border",
        "border_light",
        "primary",
        "primary_light",
        "primary_dark",
        "primary_darker",
        "primary_bg",
        "primary_text",
        "disabled_bg",
        "disabled_text",
        "gridline",
        "hover_bg",
        "log_bg",
    ]

    def test_all_four_themes_exist(self) -> None:
        """四套主题全部存在。"""
        assert "经典白" in COLOR_SCHEMES
        assert "暗夜黑" in COLOR_SCHEMES
        assert "护眼绿" in COLOR_SCHEMES
        assert "科技蓝" in COLOR_SCHEMES

    def test_each_theme_has_all_required_keys(self) -> None:
        """每个主题包含所有必需的配色键。"""
        for name, colors in COLOR_SCHEMES.items():
            missing = [k for k in self.REQUIRED_KEYS if k not in colors]
            assert not missing, f"主题 {name} 缺少键: {missing}"

    def test_dark_themes_set_correct(self) -> None:
        """暗色主题集合包含暗夜黑和科技蓝。"""
        assert "暗夜黑" in DARK_THEMES
        assert "科技蓝" in DARK_THEMES
        assert "经典白" not in DARK_THEMES
        assert "护眼绿" not in DARK_THEMES


class TestGenerateQss:
    """QSS 生成测试。"""

    def test_generate_qss_valid_theme_returns_non_empty(self) -> None:
        """有效主题名生成非空 QSS。"""
        qss = generate_qss("经典白")
        assert len(qss) > 0
        assert "QMainWindow" in qss

    def test_generate_qss_all_themes_succeed(self) -> None:
        """四套主题均能生成有效 QSS 且包含基本选择器。"""
        for name in COLOR_SCHEMES:
            qss = generate_qss(name)
            assert len(qss) > 0, f"主题 {name} 生成的 QSS 为空"
            assert "QPushButton" in qss
            assert "QLineEdit" in qss

    def test_generate_qss_invalid_theme_returns_empty(self) -> None:
        """无效主题名返回空字符串。"""
        qss = generate_qss("不存在的主题")
        assert qss == ""

    def test_generate_qss_substitutes_colors(self) -> None:
        """生成的 QSS 中不含模板占位符（如 {bg}）。"""
        qss = generate_qss("暗夜黑")
        assert "{bg}" not in qss
        assert "{surface}" not in qss

    def test_common_qss_template_has_all_placeholders(self) -> None:
        """COMMON_QSS 模板中的占位符与 COLOR_SCHEMES 键匹配。"""
        import re

        placeholders = set(re.findall(r"\{(\w+)\}", COMMON_QSS))
        sample = COLOR_SCHEMES["经典白"]
        for ph in placeholders:
            assert ph in sample, f"占位符 {ph} 在配色方案中找不到"


class TestApplyTheme:
    """apply_theme 函数测试（mock Qt app）。"""

    def test_apply_theme_sets_stylesheet_for_valid_theme(self) -> None:
        """有效主题名设置非空样式表。"""
        app = MagicMock()
        apply_theme(app, "经典白")
        app.setStyle.assert_called_once()
        app.setStyleSheet.assert_called_once()
        qss = app.setStyleSheet.call_args[0][0]
        assert len(qss) > 0

    def test_apply_theme_with_invalid_theme_name(self) -> None:
        """无效主题名清空样式表。"""
        app = MagicMock()
        apply_theme(app, "未知主题")
        app.setStyleSheet.assert_called_once_with("")

    def test_apply_dark_theme_calls_titlebar(self) -> None:
        """暗色主题自动设置标题栏为深色模式。"""
        app = MagicMock()
        mock_widget = MagicMock()
        mock_widget.isWindow.return_value = True
        mock_widget.winId.return_value = 12345
        app.topLevelWidgets.return_value = [mock_widget]

        with patch("pilotstd.ui.themes._set_titlebar_dark_mode") as mock_set:
            apply_theme(app, "暗夜黑")
            mock_set.assert_called_once()

    def test_apply_light_theme_calls_light_titlebar(self) -> None:
        """浅色主题设置标题栏为浅色模式。"""
        app = MagicMock()
        mock_widget = MagicMock()
        mock_widget.isWindow.return_value = True
        mock_widget.winId.return_value = 12345
        app.topLevelWidgets.return_value = [mock_widget]

        with patch("pilotstd.ui.themes._set_titlebar_dark_mode") as mock_set:
            apply_theme(app, "经典白")
            mock_set.assert_called_once_with(12345, False)
