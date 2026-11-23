# tests/gui/test_base_input.py
# 测试 BaseInput / BaseSelect —— 尺寸令牌、四态取色、禁用态 A-53 接线、密码模式

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtGui import QPalette  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from pilotstd.ui import tokens_generated as T  # noqa: E402
from pilotstd.ui.widgets.base_input import BaseInput, BaseSelect  # noqa: E402


@pytest.fixture(scope="module")
def app():
    """Qt 需要 QApplication 实例（offscreen 下可无窗口）。"""
    inst = QApplication.instance() or QApplication([])
    yield inst


class TestBaseInputSize:
    """尺寸档必须吃 --input-height-*，且与按钮档位互不复用。"""

    def test_default_is_m(self, app) -> None:
        """默认档位是 m（与 Web AppInput 默认一致）。"""
        w = BaseInput()
        assert w.size_name == "m"

    def test_all_sizes_use_input_height_tokens(self, app) -> None:
        """l/m/s 分别落到 input_height_lg/md/sm，且高度值真的出现在 QSS 里。"""
        for size, token_name in (
            ("l", "input_height_lg"),
            ("m", "input_height_md"),
            ("s", "input_height_sm"),
        ):
            w = BaseInput(size=size)
            expected = T.token(token_name)
            assert expected, f"令牌 {token_name} 缺失"
            height_px = int(expected.removesuffix("px"))
            # QSS 里写的是内容盒高度（总高 = 内容盒 + 2×描边），换算回总高才是令牌值
            assert f"min-height: {height_px - 2}px" in w.styleSheet(), f"{size} 档未使用 {token_name}"

    def test_input_sizes_do_not_reuse_btn_height_tokens(self, app) -> None:
        """输入框高度必须来自 --input-height-*，不得复用 --btn-height-*（§11.1 禁止项）。"""
        # 两套令牌同值（40/34/28），靠字符串无法区分，改为守护控件源码的引用口径
        import inspect

        from pilotstd.ui.widgets import base_input

        assert T.token("btn_height_lg") == T.token("input_height_lg")  # 值同档、语义独立
        source = inspect.getsource(base_input)
        assert "btn_height" not in source, "BaseInput 不得引用按钮高度令牌"

    def test_radius_uses_ds_radius_md(self, app) -> None:
        """圆角统一 --ds-radius-md（§11.2），不区分尺寸档。"""
        radius = T.token("ds_radius_md")
        assert radius
        for size in ("l", "m", "s"):
            assert f"border-radius: {radius}" in BaseInput(size=size).styleSheet()

    def test_unknown_size_raises(self, app) -> None:
        """非法档位显式抛 ValueError，不静默降级。"""
        with pytest.raises(ValueError, match="unknown size"):
            BaseInput(size="xl")

    def test_missing_height_token_raises(self, app, monkeypatch) -> None:
        """令牌缺失必须抛 KeyError（与 BaseButton 同风格），不能静默用默认样式。"""
        monkeypatch.setattr(T, "token", lambda name, default="": "")
        with pytest.raises(KeyError, match="missing scale token"):
            BaseInput(size="m")


class TestBaseInputStates:
    """四态取色必须来自生成令牌，禁用态走 A-53 接线后的 disabled*。"""

    def test_default_colors_come_from_tokens(self, app) -> None:
        """默认态底色/文字/描边分别来自 surface/text/border。"""
        qss = BaseInput(theme="light").styleSheet()
        for key in ("surface", "text", "border"):
            value = T.color("light", key)
            assert value, f"主题 light 缺颜色键 {key}"
            assert value in qss, f"默认态未使用 {key}"

    def test_hover_border_uses_text_dim(self, app) -> None:
        """悬停只提描边到 text-dim，不改底色（§11.3 的理由：避免与行 hover 叠层）。"""
        qss = BaseInput(theme="light").styleSheet()
        hover_border = T.color("light", "textDim")
        assert f"QLineEdit:hover {{ border-color: {hover_border}; }}" in qss

    def test_focus_border_uses_primary(self, app) -> None:
        """聚焦描边换 primary（QSS 无 box-shadow，2px 主色描边即等效外发光）。"""
        qss = BaseInput(theme="light").styleSheet()
        focus = T.color("light", "primary")
        assert f"2px solid {focus}" in qss

    def test_focus_keeps_total_height(self, app) -> None:
        """聚焦加粗描边时内容盒让回 2px，四态外框总高恒等于高度令牌。"""
        qss = BaseInput(size="m").styleSheet()
        total = int(T.token("input_height_md").removesuffix("px"))
        assert f"min-height: {total - 2}px" in qss  # 默认 1px 描边
        assert f"min-height: {total - 4}px" in qss  # 聚焦 2px 描边

    def test_disabled_uses_a53_tokens(self, app) -> None:
        """禁用态必须用 disabledBg/disabledText（A-53 Win 侧接线），不是 borderLight/textDim。"""
        for theme in ("light", "dark", "green", "blue"):
            qss = BaseInput(theme=theme).styleSheet()
            disabled_bg = T.color(theme, "disabledBg")
            disabled_fg = T.color(theme, "disabledText")
            assert disabled_bg and disabled_fg, f"主题 {theme} 缺 disabled 令牌"
            assert f"background: {disabled_bg};" in qss, f"{theme} 禁用态底色不是 disabledBg"
            assert f"color: {disabled_fg};" in qss, f"{theme} 禁用态文字不是 disabledText"

    def test_placeholder_uses_text_dim(self, app) -> None:
        """placeholder 走调色板（Qt QSS 无 ::placeholder），色值取 textDim。"""
        w = BaseInput(theme="light")
        expected = T.color("light", "textDim")
        actual = w.palette().color(QPalette.ColorRole.PlaceholderText).name()
        assert actual.lower() == expected.lower()

    def test_missing_color_token_raises(self, app, monkeypatch) -> None:
        """颜色令牌缺失必须抛 KeyError。"""
        monkeypatch.setattr(T, "color", lambda theme, key, default="": "")
        with pytest.raises(KeyError, match="has no color key"):
            BaseInput(theme="light")


class TestBaseInputPassword:
    """password=True 走 QLineEdit.EchoMode.Password，文本内容不受影响。"""

    def test_password_mode_sets_echo_mode(self, app) -> None:
        w = BaseInput("s3cret", password=True)
        assert w.echoMode() == QLineEdit.EchoMode.Password
        assert w.is_password is True
        assert w.text() == "s3cret"

    def test_text_mode_is_normal_echo(self, app) -> None:
        w = BaseInput("plain")
        assert w.echoMode() == QLineEdit.EchoMode.Normal
        assert w.is_password is False


class TestBaseSelect:
    """BaseSelect 与 BaseInput 同尺寸/圆角/四态口径。"""

    def test_default_is_m_and_items_added(self, app) -> None:
        w = BaseSelect(["经典白", "暗夜黑"])
        assert w.size_name == "m"
        assert w.count() == 2
        assert w.itemText(0) == "经典白"

    def test_all_sizes_use_input_height_tokens(self, app) -> None:
        for size, token_name in (
            ("l", "input_height_lg"),
            ("m", "input_height_md"),
            ("s", "input_height_sm"),
        ):
            qss = BaseSelect(size=size).styleSheet()
            height_px = int(T.token(token_name).removesuffix("px"))
            assert f"min-height: {height_px - 2}px" in qss, f"{size} 档未使用 {token_name}"

    def test_radius_and_states_from_tokens(self, app) -> None:
        w = BaseSelect(theme="light")
        qss = w.styleSheet()
        assert f"border-radius: {T.token('ds_radius_md')}" in qss
        assert f"border-color: {T.color('light', 'textDim')}" in qss  # hover
        assert f"2px solid {T.color('light', 'primary')}" in qss  # focus
        assert f"background: {T.color('light', 'disabledBg')};" in qss
        assert f"color: {T.color('light', 'disabledText')};" in qss

    def test_unknown_size_raises(self, app) -> None:
        with pytest.raises(ValueError, match="unknown size"):
            BaseSelect(size="xl")

    def test_missing_token_raises(self, app, monkeypatch) -> None:
        monkeypatch.setattr(T, "token", lambda name, default="": "")
        with pytest.raises(KeyError, match="missing scale token"):
            BaseSelect(size="m")


class TestBaseButtonDisabledA53:
    """A-53 Win 侧收口：BaseButton 的禁用态也必须走 disabledBg/disabledText。"""

    def test_disabled_uses_a53_tokens(self, app) -> None:
        """四个主题的禁用态都取 disabled* 令牌，不再用 borderLight/textDim 顶替。"""
        from pilotstd.ui.widgets.base_button import BaseButton

        for theme in ("light", "dark", "green", "blue"):
            qss = BaseButton("x", theme=theme).styleSheet()
            disabled_bg = T.color(theme, "disabledBg")
            disabled_fg = T.color(theme, "disabledText")
            assert disabled_bg and disabled_fg, f"主题 {theme} 缺 disabled 令牌"
            assert f"background: {disabled_bg}; color: {disabled_fg};" in qss, f"{theme} 禁用态未接 A-53 令牌"

    def test_old_substitute_tokens_gone_from_disabled_state(self, app) -> None:
        """旧的替代口径（borderLight + textDim）不得再出现在 BaseButton 的禁用态。"""
        from pilotstd.ui.widgets.base_button import BaseButton

        for theme in ("light", "dark", "green", "blue"):
            qss = BaseButton("x", theme=theme).styleSheet()
            old = f"background: {T.color(theme, 'borderLight')}; color: {T.color(theme, 'textDim')};"
            assert old not in qss, f"{theme} 禁用态仍是旧的替代令牌"


class TestRenderedHeight:
    """四态换算后外框总高必须真的等于高度令牌（不是只写在 QSS 字符串里）。"""

    def test_rendered_height_matches_input_height_tokens(self, app) -> None:
        for size, token_name in (
            ("l", "input_height_lg"),
            ("m", "input_height_md"),
            ("s", "input_height_sm"),
        ):
            expected = int(T.token(token_name).removesuffix("px"))
            assert BaseInput(size=size).sizeHint().height() == expected, f"BaseInput {size} 档渲染高度不符"
            assert BaseSelect(["a"], size=size).sizeHint().height() == expected, f"BaseSelect {size} 档渲染高度不符"

    def test_rendered_height_under_app_stylesheet(self, app) -> None:
        """应用级 QSS 存在时（真实运行态）构造完即须拿到令牌高度。

        回归：Qt 在应用级样式表生效、控件尚未 polish 时，QComboBox 的 sizeHint 会返回
        未套控件 QSS 的高度（实测 22px），要等事件循环 polish 后才变回令牌高度 ——
        首帧布局会按 22px 排，表单控件看起来"矮了一截"。BaseInput/BaseSelect 在
        `_apply_style()` 末尾立即 ensurePolished 消除这个窗口。
        """
        app.setStyleSheet("QDialog, QWidget { background-color: #ffffff; color: #475569; font-size: 10pt; }")
        try:
            for size, token_name in (
                ("l", "input_height_lg"),
                ("m", "input_height_md"),
                ("s", "input_height_sm"),
            ):
                expected = int(T.token(token_name).removesuffix("px"))
                assert BaseInput(size=size).sizeHint().height() == expected
                assert BaseSelect(["a"], size=size).sizeHint().height() == expected
        finally:
            app.setStyleSheet("")


def test_no_hardcoded_colors_in_widget_source() -> None:
    """控件源码里不得出现字面色值（G-055）：色值只能来自令牌产物。"""
    import re
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "pilotstd" / "ui" / "widgets" / "base_input.py"
    source = path.read_text(encoding="utf-8")
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", source)
    assert not literals, f"BaseInput/BaseSelect 出现字面色值：{literals}"


class TestWinInputUnification:
    """Win 端输入控件统一守护：pilotstd/ui 内不得再构造原生 QLineEdit/QComboBox。"""

    @staticmethod
    def _ui_sources():
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "pilotstd" / "ui"
        return [p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts]

    def test_no_raw_qlineedit_or_qcombobox_instantiation(self) -> None:
        """统一走 BaseInput/BaseSelect；否则样式会脱离跨端令牌（与按钮守护同口径）。"""
        import re

        call = re.compile(r"(?<![\w.])(QLineEdit|QComboBox)\(")
        offenders = []
        for path in self._ui_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if call.search(line):
                    offenders.append(f"{path.name}:{lineno}: {line.strip()[:80]}")
        assert not offenders, "发现未替换的输入控件构造：\n" + "\n".join(offenders)

    def test_replaced_sites_keep_behavior(self) -> None:
        """替换后必须保留 placeholder / 密码模式 / 下拉选项，不能只换类名丢语义。"""
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        settings_src = (root / "pilotstd" / "ui" / "core" / "handlers" / "_settings.py").read_text(encoding="utf-8")
        rules_src = (root / "pilotstd" / "ui" / "pages" / "rules_page.py").read_text(encoding="utf-8")

        # 密码框：走 BaseInput(password=True)，不再手工 setEchoMode
        assert settings_src.count("BaseInput(password=True)") == 7
        assert "setEchoMode(QLineEdit.EchoMode.Password)" not in settings_src
        # `placeholder` 原样保留
        assert 'setPlaceholderText("http://127.0.0.1:8080")' in settings_src
        assert 'setPlaceholderText(_("placeholder_xpath"))' in rules_src
        # 下拉选项与 setCurrentText 逻辑保留
        assert 'self._theme_combo.addItems(["经典白", "暗夜黑", "护眼绿", "科技蓝"])' in settings_src
        assert 'self.type_combo.setCurrentText(self._rule["type"])' in rules_src
        # 信号连接保留
        assert "self._announce_url_edit.textChanged.connect(self._on_announce_url_changed)" in settings_src
        assert "self._announce_api_key_edit.textChanged.connect(self._on_announce_api_key_changed)" in settings_src
