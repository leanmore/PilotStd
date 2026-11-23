# tests/gui/test_base_table.py
# 测试 BaseTable —— 表头/斑马纹/hover/选中/边框/圆角的令牌取值、四主题、非法参数、缺令牌

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QTableWidget  # noqa: E402

from pilotstd.ui import tokens_generated as T  # noqa: E402
from pilotstd.ui.widgets.base_table import BaseTable, _alpha, _composite, _rgb  # noqa: E402

THEMES = ("light", "dark", "green", "blue")


@pytest.fixture(scope="module")
def app():
    """Qt 需要 QApplication 实例（offscreen 下可无窗口）。"""
    inst = QApplication.instance() or QApplication([])
    yield inst


class TestBaseTableIdentity:
    """BaseTable 必须是 QTableWidget 子类，业务侧的既有用法零改动。"""

    def test_is_qtablewidget_subclass(self, app) -> None:
        assert issubclass(BaseTable, QTableWidget)
        assert isinstance(BaseTable(), QTableWidget)

    def test_constructor_keeps_rows_columns(self, app) -> None:
        """构造参数与 QTableWidget(rows, columns) 同序同义。"""
        table = BaseTable(3, 5)
        assert table.rowCount() == 3
        assert table.columnCount() == 5

    def test_default_theme_and_striped(self, app) -> None:
        table = BaseTable()
        assert table.theme_name == "light"
        assert table.striped is True
        assert table.alternatingRowColors() is True


class TestBaseTableHeader:
    """表头：背景 surfaceRaised、文字 text（**不是** textSecondary）、11px / 600。"""

    def test_header_background_uses_surface_raised(self, app) -> None:
        for theme in THEMES:
            qss = BaseTable(theme=theme).styleSheet()
            raised = T.color(theme, "surfaceRaised")
            assert raised, f"主题 {theme} 缺 surfaceRaised"
            assert f"background: {raised};" in qss, f"{theme} 表头背景不是 surfaceRaised"

    def test_header_text_uses_text_not_text_secondary(self, app) -> None:
        """§12.1 + Tech-Debt #8：表头字色必须是 --text（textSecondary/textDim 对比度不达标）。"""
        for theme in THEMES:
            qss = BaseTable(theme=theme).styleSheet()
            text = T.color(theme, "text")
            secondary = T.color(theme, "textSecondary")
            dim = T.color(theme, "textDim")
            assert text and secondary and dim
            # 表头段单独断言：只取 QHeaderView::section 那一段
            head = qss.split("QHeaderView::section")[1].split("}")[0]
            assert f"color: {text};" in head, f"{theme} 表头字色不是 text"
            assert f"color: {secondary};" not in head, f"{theme} 表头仍在用 textSecondary"
            assert f"color: {dim};" not in head, f"{theme} 表头仍在用 textDim"

    def test_header_font_size_and_weight_from_tokens(self, app) -> None:
        """字号 11px、字重 600，都从令牌取（对应 Web 的 --font-size-11 / semibold）。"""
        qss = BaseTable(theme="light").styleSheet()
        head = qss.split("QHeaderView::section")[1].split("}")[0]
        assert f"font-size: {T.token('font_size_11')};" in head
        assert f"font-weight: {T.token('font_weight_semibold')};" in head

    def test_header_height_matches_token_math(self, app) -> None:
        """表头高 = 2×space_10 + 11px×line-height-normal（QSS padding 不改 header 高，须显式设）。"""
        table = BaseTable()
        pad = int(T.token("space_10").removesuffix("px"))
        font = int(T.token("font_size_11").removesuffix("px"))
        ratio = float(T.token("line_height_normal"))
        expected = 2 * pad + int(font * ratio + 0.5)
        assert table.horizontalHeader().height() == expected


class TestBaseTableRows:
    """行：斑马纹 surfaceRaised、hover/选中 selected、行分隔 borderLight、外框 border。"""

    def test_striped_rows_use_surface_raised(self, app) -> None:
        for theme in THEMES:
            qss = BaseTable(theme=theme).styleSheet()
            raised = T.color(theme, "surfaceRaised")
            assert f"alternate-background-color: {raised};" in qss, f"{theme} 斑马纹不是 surfaceRaised"

    def test_hover_and_selected_use_selected_token(self, app) -> None:
        """hover 与选中都用 --selected，且必须已合成成不透明色（见模块 docstring 的实测）。"""
        for theme in THEMES:
            qss = BaseTable(theme=theme).styleSheet()
            surface = T.color(theme, "surface")
            expected = _composite(T.color(theme, "selected"), surface)
            assert f"QTableWidget::item:hover {{ background: {expected}; }}" in qss, f"{theme} hover 不是 selected"
            assert f"background: {expected}; color: {T.color(theme, 'text')};" in qss, f"{theme} 选中态取色不对"

    def test_selected_color_is_opaque(self, app) -> None:
        """Qt 的 item 委托不合成半透明 ::item 背景，故交给 QSS 的必须是 #rrggbb。"""
        for theme in THEMES:
            surface = T.color(theme, "surface")
            composed = _composite(T.color(theme, "selected"), surface)
            assert composed.startswith("#") and len(composed) == 7, f"{theme} 合成结果不是 #rrggbb：{composed}"
            assert "rgba" not in composed

    def test_row_borders_use_border_and_border_light(self, app) -> None:
        """外框 --border；行分隔 --borderLight（避免整表被线条切碎）。"""
        for theme in THEMES:
            qss = BaseTable(theme=theme).styleSheet()
            border = T.color(theme, "border")
            light = T.color(theme, "borderLight")
            assert f"border: 1px solid {border};" in qss, f"{theme} 外框不是 border"
            assert f"border-bottom: 1px solid {light};" in qss, f"{theme} 行分隔不是 borderLight"

    def test_row_height_matches_token_math(self, app) -> None:
        """行高 = 2×space_9 + 13px×line-height-normal。"""
        table = BaseTable()
        pad = int(T.token("space_9").removesuffix("px"))
        font = int(T.token("font_size_13").removesuffix("px"))
        ratio = float(T.token("line_height_normal"))
        expected = 2 * pad + int(font * ratio + 0.5)
        # 0 行时 rowHeight(0) 返回 0，故看 verticalHeader 的默认段高（这才是 QSS 外要显式设的值）
        assert table.verticalHeader().defaultSectionSize() == expected
        table.setRowCount(1)
        assert table.rowHeight(0) == expected

    def test_grid_disabled(self, app) -> None:
        """DS 只要行分隔线、不要竖线：默认网格必须关掉。"""
        assert BaseTable().showGrid() is False

    def test_striped_can_be_disabled(self, app) -> None:
        table = BaseTable(striped=False)
        assert table.striped is False
        assert table.alternatingRowColors() is False


class TestBaseTableRadius:
    """圆角统一 --ds-radius-md（§12.1：旧 --radius 10px 冻结，收敛到 8px）。"""

    def test_radius_uses_ds_radius_md(self, app) -> None:
        radius = T.token("ds_radius_md")
        assert radius
        for theme in THEMES:
            assert f"border-radius: {radius};" in BaseTable(theme=theme).styleSheet()


class TestBaseTableErrors:
    """非法参数/缺令牌必须显式抛错，不静默降级。"""

    def test_unknown_theme_raises(self, app) -> None:
        with pytest.raises(ValueError, match="unknown theme"):
            BaseTable(theme="solarized")

    def test_missing_scale_token_raises(self, app, monkeypatch) -> None:
        monkeypatch.setattr(T, "token", lambda name, default="": "")
        with pytest.raises(KeyError, match="missing scale token"):
            BaseTable()

    def test_missing_color_token_raises(self, app, monkeypatch) -> None:
        monkeypatch.setattr(T, "color", lambda theme, key, default="": "")
        with pytest.raises(KeyError, match="has no color key"):
            BaseTable()

    def test_non_px_scale_token_raises(self, app, monkeypatch) -> None:
        """像素换算令牌必须是 px 长度，否则抛 ValueError（不猜单位）。"""
        original = T.token

        def fake(name: str, default: str = "") -> str:
            if name == "space_9":
                return "1rem"
            return original(name, default)

        monkeypatch.setattr(T, "token", fake)
        with pytest.raises(ValueError, match="is not a px length"):
            BaseTable()


class TestBaseTableThemes:
    """四主题都能构造、渲染尺寸一致（不崩、不串色）。"""

    def test_all_themes_construct_and_render(self, app) -> None:
        for theme in THEMES:
            table = BaseTable(theme=theme, striped=True)
            table.setRowCount(2)
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["A", "B"])
            table.show()
            app.processEvents()
            assert table.rowHeight(0) == table.rowHeight(1)
            assert table.theme_name == theme
            table.hide()
            table.deleteLater()

    def test_themes_do_not_share_colors(self, app) -> None:
        """light 与 dark 的表头背景必须不同（否则说明取色没按主题走）。"""
        light_qss = BaseTable(theme="light").styleSheet()
        dark_qss = BaseTable(theme="dark").styleSheet()
        assert light_qss != dark_qss
        assert T.color("light", "surfaceRaised") != T.color("dark", "surfaceRaised")


class TestCompositeHelpers:
    """`--selected` 是 rgba，必须先合成成不透明色（Qt item 委托不会自己合成）。"""

    def test_rgb_parses_hex_and_rgb(self) -> None:
        assert _rgb("#ffffff") == (255, 255, 255)
        assert _rgb("#fff") == (255, 255, 255)
        assert _rgb("rgb(1, 2, 3)") == (1, 2, 3)
        assert _rgb("rgba(1, 2, 3, 0.5)") == (1, 2, 3)
        assert _rgb("not-a-color") is None

    def test_alpha_parses_float_percent_and_int(self) -> None:
        assert _alpha("rgba(0, 0, 0, 0.08)") == pytest.approx(0.08)
        assert _alpha("rgba(0, 0, 0, 8%)") == pytest.approx(0.08)
        assert _alpha("rgba(0, 0, 0, 20)") == pytest.approx(20 / 255)
        assert _alpha("#000000") == 1.0

    def test_composite_matches_manual_math(self) -> None:
        """8% 主色叠在白底上 = 各通道按 0.92/0.08 混合（手算校验）。"""
        composed = _composite("rgba(99, 102, 241, 0.08)", "#ffffff")
        expected = "#{:02x}{:02x}{:02x}".format(
            round(99 * 0.08 + 255 * 0.92),
            round(102 * 0.08 + 255 * 0.92),
            round(241 * 0.08 + 255 * 0.92),
        )
        assert composed == expected

    def test_composite_passthrough_when_unparsable(self) -> None:
        """解析不了就原样返回，让取色断言先红，而不是静默换成别的颜色。"""
        assert _composite("var(--selected)", "#ffffff") == "var(--selected)"


def test_no_hardcoded_colors_in_widget_source() -> None:
    """控件源码里不得出现字面色值（G-055）：色值只能来自令牌产物。

    注意：本模块带 `_rgb()`/`_alpha()` 两个**解析器**，它们内部会出现 `"rgb("` 这类
    字符串前缀比较（不是色值）。故正则要求 `rgb(` 后紧跟数字，`#` 后紧跟十六进制，
    只命中真正的色值字面量。
    """
    import re
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "pilotstd" / "ui" / "widgets" / "base_table.py"
    source = path.read_text(encoding="utf-8")
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", source)
    assert not literals, f"BaseTable 出现字面色值：{literals}"


def test_no_hardcoded_color_values_in_qss(app) -> None:
    """运行期 QSS 里所有色值都必须能在令牌表里找到（防止写死 #fff）。"""
    import re

    for theme in THEMES:
        qss = BaseTable(theme=theme).styleSheet()
        allowed = set(T.THEME_COLORS[theme].values())
        # 合成后的 `selected` 不在令牌表里，单独放行
        allowed.add(_composite(T.color(theme, "selected"), T.color(theme, "surface")))
        found = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", qss)
        unknown = [value for value in found if value not in allowed]
        assert not unknown, f"{theme} QSS 出现非令牌色值：{unknown}"
