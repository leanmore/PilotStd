# tests/gui/test_base_dialog.py
# 测试 BaseDialog —— 圆角/内边距/边框/标题/关闭按钮的令牌取值、四主题、非法参数、QDialog 语义保留

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout  # noqa: E402

from pilotstd.ui import tokens_generated as T  # noqa: E402
from pilotstd.ui.widgets.base_dialog import BaseDialog, build_title_row  # noqa: E402

THEMES = ("light", "dark", "green", "blue")


@pytest.fixture(scope="module")
def app():
    """Qt 需要 QApplication 实例（offscreen 下可无窗口）。"""
    inst = QApplication.instance() or QApplication([])
    yield inst


class TestBaseDialogIdentity:
    """BaseDialog 必须是 QDialog 子类，且**不覆盖**任何业务语义方法。"""

    def test_is_qdialog_subclass(self, app) -> None:
        assert issubclass(BaseDialog, QDialog)
        assert isinstance(BaseDialog(), QDialog)

    def test_dialog_code_is_same_enum(self, app) -> None:
        """替换 35 处 `dlg.exec() != QDialog.DialogCode.Accepted` 后判断必须照常成立。"""
        assert BaseDialog.DialogCode is QDialog.DialogCode
        assert BaseDialog.DialogCode.Accepted == QDialog.DialogCode.Accepted
        assert BaseDialog.DialogCode.Rejected == QDialog.DialogCode.Rejected

    def test_does_not_override_dialog_semantics(self, app) -> None:
        """exec/accept/reject/done/setWindowTitle/resize/closeEvent/result 一律不改语义。

        注意：PyQt6 的绑定方法每次访问都返回新的包装对象，`is` 比较必然为 False，
        故用「类 `__dict__` 里有没有这个名字」判断是否覆写 —— 这才是真正要守的东西。
        """
        own = set(BaseDialog.__dict__)
        # 允许覆写的只有这两个 Qt 钩子（且都必须调用 super()）
        assert own & {"showEvent", "resizeEvent"} == {"showEvent", "resizeEvent"}
        forbidden = {
            "exec",
            "accept",
            "reject",
            "done",
            "setWindowTitle",
            "resize",
            "setMinimumWidth",
            "setMinimumSize",
            "setSizeGripEnabled",
            "result",
            "closeEvent",
        }
        assert not (own & forbidden), f"BaseDialog 不得覆写：{sorted(own & forbidden)}"

    def test_accept_reject_keep_result(self, app) -> None:
        dialog = BaseDialog()
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        dialog.reject()
        assert dialog.result() == QDialog.DialogCode.Rejected

    def test_setwindowtitle_and_resize_unchanged(self, app) -> None:
        """子类在 super().__init__ 之后的 setWindowTitle / resize 调用照旧生效。"""
        dialog = BaseDialog()
        dialog.setWindowTitle("测试标题")
        dialog.resize(360, 240)
        assert dialog.windowTitle() == "测试标题"
        assert dialog.width() == 360
        assert dialog.height() == 240

    def test_default_theme_and_not_closable(self, app) -> None:
        """默认不显示右上角关闭按钮（不改变存量 35 处弹窗的关闭入口）。"""
        dialog = BaseDialog()
        assert dialog.theme_name == "light"
        assert dialog.closable is False


class TestBaseDialogChrome:
    """外观：圆角 ds_radius_lg、背景 surface、边框 border。"""

    def test_radius_uses_ds_radius_lg(self, app) -> None:
        radius = T.token("ds_radius_lg")
        assert radius
        for theme in THEMES:
            assert f"border-radius: {radius};" in BaseDialog(theme=theme).styleSheet()

    def test_radius_is_not_frozen_old_value(self, app) -> None:
        """§12.2：冻结的旧 --radius-lg（14px）不得再被引用。"""
        radius = T.token("ds_radius_lg")
        assert radius == "12px"
        assert radius != "14px"

    def test_background_and_border_from_tokens(self, app) -> None:
        for theme in THEMES:
            qss = BaseDialog(theme=theme).styleSheet()
            surface = T.color(theme, "surface")
            border = T.color(theme, "border")
            assert f"background: {surface};" in qss, f"{theme} 弹窗背景不是 surface"
            assert f"border: 1px solid {border};" in qss, f"{theme} 弹窗边框不是 border"

    def test_title_uses_text_heading_and_semibold(self, app) -> None:
        """§12.2：header 标题 --text-heading + --font-weight-semibold。"""
        for theme in THEMES:
            qss = BaseDialog(theme=theme).styleSheet()
            heading = T.color(theme, "textHeading")
            weight = T.token("font_weight_semibold")
            block = qss.split("QLabel#dsDialogTitle")[1].split("}")[0]
            assert f"color: {heading};" in block, f"{theme} 标题色不是 textHeading"
            assert f"font-weight: {weight};" in block, f"{theme} 标题字重不是 semibold"

    def test_close_button_icon_size_and_color_from_tokens(self, app) -> None:
        """关闭按钮只收敛图标字号到 --size-20、色 --text-secondary（§12.2）。"""
        for theme in THEMES:
            qss = BaseDialog(theme=theme).styleSheet()
            block = qss.split("QToolButton#dsDialogClose")[1].split("}")[0]
            assert f"font-size: {T.token('size_20')};" in block, f"{theme} 关闭图标字号不是 size_20"
            assert f"color: {T.color(theme, 'textSecondary')};" in block, f"{theme} 关闭图标色不对"


class TestBaseDialogPadding:
    """内边距：--space_18（上下）/ --space_20（左右），首次显示时套到 layout。"""

    def test_content_padding_uses_space_18_20(self, app) -> None:
        dialog = BaseDialog()
        horizontal = int(T.token("space_20").removesuffix("px"))
        vertical = int(T.token("space_18").removesuffix("px"))
        assert dialog.content_padding == (horizontal, vertical)

    def test_layout_margins_applied_on_show(self, app) -> None:
        """首次 show 后 layout margin 必须等于 (space_20, space_18)。"""
        dialog = BaseDialog()
        layout = QVBoxLayout(dialog)
        label = QLabel("内容")
        layout.addWidget(label)
        dialog.resize(400, 300)
        dialog.show()
        app.processEvents()
        margins = layout.contentsMargins()
        expected_h = int(T.token("space_20").removesuffix("px"))
        expected_v = int(T.token("space_18").removesuffix("px"))
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            expected_h,
            expected_v,
            expected_h,
            expected_v,
        )
        # 子控件真的被内缩了（不是只改了数字）
        assert label.x() == expected_h
        assert label.y() == expected_v
        dialog.hide()
        dialog.deleteLater()

    def test_padding_not_applied_twice(self, app) -> None:
        """二次 show 不得重复累加内边距（Qt 布局 margin 是绝对值，但仍守一次）。"""
        dialog = BaseDialog()
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("内容"))
        dialog.resize(400, 300)
        dialog.show()
        app.processEvents()
        first = layout.contentsMargins().left()
        dialog.hide()
        dialog.show()
        app.processEvents()
        assert layout.contentsMargins().left() == first
        dialog.hide()
        dialog.deleteLater()

    def test_padding_skipped_without_layout(self, app) -> None:
        """没有 layout 的弹窗不得崩（showEvent 必须能安全跳过）。"""
        dialog = BaseDialog()
        dialog.resize(200, 150)
        dialog.show()
        app.processEvents()
        assert dialog.isVisible()
        dialog.hide()
        dialog.deleteLater()


class TestBaseDialogCloseButton:
    """closable=True 时右上角有关闭按钮；默认 False 时不加（不改存量行为）。"""

    def test_no_close_button_by_default(self, app) -> None:
        dialog = BaseDialog()
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("内容"))
        dialog.resize(400, 300)
        dialog.show()
        app.processEvents()
        assert dialog.close_button is None
        dialog.hide()
        dialog.deleteLater()

    def test_close_button_positioned_top_right(self, app) -> None:
        """关闭按钮在右上角：x 靠右、y 等于 space_18。"""
        dialog = BaseDialog(closable=True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("内容"))
        dialog.resize(400, 300)
        dialog.show()
        app.processEvents()
        button = dialog.close_button
        assert button is not None
        assert button.parent() is dialog
        # 右边缘留 space_20 的呼吸位
        right_gap = dialog.width() - (button.x() + button.width())
        assert 0 <= right_gap <= int(T.token("space_20").removesuffix("px")) + 2
        assert button.y() == int(T.token("space_18").removesuffix("px"))
        # 不能是 20×20 的小热区（WCAG 2.5.8 要求 >=24px）
        assert button.height() >= 24
        dialog.hide()
        dialog.deleteLater()

    def test_close_button_rejects(self, app) -> None:
        """点关闭按钮走 reject（与页脚「取消」同语义，不触发 accept 的业务保存）。"""
        dialog = BaseDialog(closable=True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("内容"))
        dialog.resize(400, 300)
        dialog.show()
        app.processEvents()
        assert dialog.close_button is not None
        dialog.close_button.click()
        assert dialog.result() == QDialog.DialogCode.Rejected
        dialog.hide()
        dialog.deleteLater()


class TestBaseDialogErrors:
    """非法参数/缺令牌必须显式抛错，不静默降级。"""

    def test_unknown_theme_raises(self, app) -> None:
        with pytest.raises(ValueError, match="unknown theme"):
            BaseDialog(theme="solarized")

    def test_missing_scale_token_raises(self, app, monkeypatch) -> None:
        monkeypatch.setattr(T, "token", lambda name, default="": "")
        with pytest.raises(KeyError, match="missing scale token"):
            BaseDialog()

    def test_missing_color_token_raises(self, app, monkeypatch) -> None:
        monkeypatch.setattr(T, "color", lambda theme, key, default="": "")
        with pytest.raises(KeyError, match="has no color key"):
            BaseDialog()

    def test_no_overlay_backdrop_token_added(self) -> None:
        """本轮明确不新增 overlayBackdrop（Web 端也没加，见模块 docstring）。"""
        assert not any("overlay" in key.lower() for key in T.TOKENS)
        assert not any("backdrop" in key.lower() for key in T.TOKENS)
        for colors in T.THEME_COLORS.values():
            assert not any("overlay" in key.lower() or "backdrop" in key.lower() for key in colors)


class TestBaseDialogThemes:
    """四主题都能构造、显示、关闭（不崩、不串色）。"""

    def test_all_themes_construct_and_show(self, app) -> None:
        for theme in THEMES:
            dialog = BaseDialog(theme=theme)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("内容"))
            dialog.resize(360, 240)
            dialog.show()
            app.processEvents()
            assert dialog.isVisible()
            assert dialog.theme_name == theme
            dialog.accept()
            assert dialog.result() == QDialog.DialogCode.Accepted
            dialog.hide()
            dialog.deleteLater()

    def test_themes_do_not_share_colors(self, app) -> None:
        assert BaseDialog(theme="light").styleSheet() != BaseDialog(theme="dark").styleSheet()


class TestTitleRow:
    """`build_title_row()` 给标题标签挂上 dsDialogTitle，让 QSS 的标题口径生效。"""

    def test_title_row_sets_object_name(self, app) -> None:
        row, layout = build_title_row("汇总")
        labels = row.findChildren(QLabel)
        assert len(labels) == 1
        assert labels[0].text() == "汇总"
        assert labels[0].objectName() == "dsDialogTitle"
        assert layout.count() == 2  # 标题 + stretch


def test_no_hardcoded_colors_in_widget_source() -> None:
    """控件源码里不得出现字面色值（G-055）：色值只能来自令牌产物。"""
    import re
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "pilotstd" / "ui" / "widgets" / "base_dialog.py"
    source = path.read_text(encoding="utf-8")
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", source)
    assert not literals, f"BaseDialog 出现字面色值：{literals}"


def test_no_hardcoded_color_values_in_qss(app) -> None:
    """运行期 QSS 里所有色值都必须能在令牌表里找到（防止写死 #fff）。"""
    import re

    for theme in THEMES:
        qss = BaseDialog(theme=theme).styleSheet()
        allowed = set(T.THEME_COLORS[theme].values())
        found = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", qss)
        unknown = [value for value in found if value not in allowed]
        assert not unknown, f"{theme} QSS 出现非令牌色值：{unknown}"
