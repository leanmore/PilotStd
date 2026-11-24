"""Win 端 BaseDialog：样式全部取自 tokens_generated（跨端令牌产物）。

与 Web 的 `<AppDialog>` 一一对应（docs/reference/ui-system.md §12.2）：
  圆角 `--ds-radius-lg`、背景 `--surface` + `1px solid --border`
  header / content 内边距 `--space-18`（上下）/ `--space-20`（左右）
  header 下沿一条 `--border` 分隔线、标题 `--text-heading` + 600
  关闭按钮在右上角，图标字号 `--size-20`、色 `--text-secondary`（hover 转 `--text`）

样式来自 `pilotstd/ui/tokens_generated.py`（由 `scripts/gen_win_tokens.py` 从 Web 的
design-tokens.css / themes.ts 生成），因此两端色值与尺度永远一致；缺令牌即抛错，
禁止在控件里手写色值或尺寸字面量（G-055）。

── 为什么**不新增** `overlayBackdrop` 令牌 ──
Web 端也没加（AppDialog.vue 的「遮罩层为什么不要 --overlay-backdrop」注释 + ui-system.md §12.2）：
新增颜色键要同时改四套主题、`applyThemeToDom`、`style.css :root`、`design-tokens.test.ts`
的映射覆盖断言，还要重生成 Win 产物（会连带触发令牌同步链），而本轮没有明确视觉诉求。
Qt 侧的模态遮罩由平台窗口管理器绘制，本来也不吃 QSS 颜色，加令牌在 Win 端无处可消费。

── 内边距为什么是 `--space-20` 而不是 22px ──
Web 迁移前写的是 `18px 22px`；间距档位表里**没有 22**（1/2/3/4/6/7/8/9/10/12/14/16/18/20/24/
30/32/40/44），按 §12.2 收敛到最近的 `--space-20`（视觉差 2px 不可辨），竖直保留精确的
`--space-18`。

── 为什么内边距在 `showEvent` 里套到 layout，而不是构造时 ──
Qt 的 `QLayout::contentsMargins` 与 `QWidget::contentsMargins` 是两套东西：给 QDialog
`setContentsMargins()` 只是把窗口内容区整体内缩（实测 label 从 (11,11) 移到 (31,29)），
**不会**改布局自己的 margin；而 `QLayout.setContentsMargins()` 在 `show()` 之前会被
QDialog 的默认布局重排覆盖回 11px。两者叠加还会翻倍（实测 (40,36)）。
故本类在 `showEvent` 里对 layout 设一次 margin（Qt 的布局在 show 时已经定型），
且只在「调用方没自己改过 margin」时才动手，避免覆盖业务自定义布局。

── 为什么不在 `setLayout()` 里套 ──
`QDialog.setLayout()` 在 Python 侧可以被覆写，但 `QVBoxLayout(self)` 这种「把父对象直接
传给布局构造函数」的写法走的是 C++ 侧的 setLayout，**不会**经过 Python 覆写（实测覆写未被调用）。
`showEvent` 对两种写法都生效。

── 关闭按钮：为什么 `closable` 默认 False（与 Web 的默认 true 有意不同）──
Web 的 `<AppDialog closable>` 默认 true，由 PrimeVue 的 header-actions 在右上角渲染。
Win 端存量 35 处 QDialog **全部**自带页脚「关闭 / 确定 / 取消」按钮，再加一个浮动关闭按钮
= 同一弹窗两个关闭入口，属业务行为变更（本任务明确禁止）。
故 `closable=False` 为默认（不改变任何既有弹窗），需要右上角关闭按钮的新弹窗显式传
`closable=True`。这是 Win 端为「不破坏存量」付的局部代价，已登记在
`docs/architecture/modules/ui.md` 的模块二小节。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QResizeEvent, QShowEvent
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLayout, QToolButton, QWidget

from pilotstd.i18n import _
from pilotstd.ui import tokens_generated as T

# 四主题白名单：未知主题必须显式报错，不能静默回退 `light`（否则配色错误无人发现）
_THEMES = ("light", "dark", "green", "blue")


# ── 令牌读取（缺令牌即抛错，不静默降级）────────────────────
def _color(theme: str, key: str) -> str:
    """取当前主题的颜色；缺失时抛 KeyError。"""
    value = T.color(theme, key)
    if not value:
        raise KeyError(f"theme {theme} has no color key {key}; run scripts/gen_win_tokens.py")
    return value


def _size(key: str) -> str:
    """取尺度令牌；缺失时抛 KeyError。"""
    value = T.token(key)
    if not value:
        raise KeyError(f"missing scale token {key}; run scripts/gen_win_tokens.py")
    return value


def _px(key: str) -> int:
    """取像素尺度令牌并转成整数（内边距要用数值设给 layout）。"""
    value = _size(key)
    if not value.endswith("px"):
        raise ValueError(f"scale token {key} is not a px length: {value!r}")
    return int(float(value[: -len("px")]))


class BaseDialog(QDialog):
    """跨端统一弹窗（Win 端）。

    与 Web 的 `<AppDialog>` 对应；业务侧只负责「标题 + 内容 + 按钮」，
    圆角/内边距/边框/标题层级一律由本控件承担（§12.2、§12.3 禁止项）。

    ── 与 QDialog 的兼容性（替换 35 处继承/构造点时最关心的事）──
    本类是 `QDialog` 的直接子类，**不覆盖** `exec()` / `accept()` / `reject()` / `done()` /
    `setWindowTitle()` / `resize()` / `closeEvent()` / `result()` / 任何信号，
    全部原样继承。因此：
      * `dlg.exec() != QDialog.DialogCode.Accepted` 这类判断照常成立
        （`BaseDialog.DialogCode` 与 `QDialog.DialogCode` 是同一个枚举）；
      * 子类自己的 `closeEvent` 覆写仍然生效（本类不定义 closeEvent）；
      * 子类在 `super().__init__(parent)` 之后调用的 `setWindowTitle` / `resize` /
        `setMinimumWidth` / `setSizeGripEnabled` / `setAttribute` 全部照旧。
    本类只做三件事：套 QSS、首次 `showEvent` 时给 layout 设内边距、按需加右上角关闭按钮。

    ── 参数 ──
      theme    : 四主题之一（light/dark/green/blue），未知值抛 ValueError
      closable : 是否在右上角加关闭按钮（默认 False，见模块 docstring 的理由）
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        theme: str = "light",
        closable: bool = False,
    ) -> None:
        super().__init__(parent)
        if theme not in _THEMES:
            raise ValueError(f"unknown theme: {theme!r}; expected one of {_THEMES}")
        self._theme = theme
        self._closable = bool(closable)
        # 调用方显式改过 `layout` `margin` 后就不再覆盖（尊重业务自定义布局）
        self._margin_applied = False
        self._close_button: QToolButton | None = None
        self._apply_style()

    # ── 样式 ─────────────────────────────────────────────────
    def _apply_style(self) -> None:
        """按主题组装 QSS；所有色值/尺寸都来自生成令牌，缺令牌即抛错。"""
        theme = self._theme
        surface = _color(theme, "surface")
        text = _color(theme, "text")
        border = _color(theme, "border")
        radius = _size("ds_radius_lg")
        heading = _color(theme, "textHeading")
        weight_heading = _size("font_weight_semibold")

        self.setStyleSheet(
            f"QDialog {{"
            f" background: {surface};"
            f" border: 1px solid {border};"
            f" border-radius: {radius};"
            f" color: {text};"
            f" }}"
            # 标题：比正文高一档亮度 + 600（对应 Web 的 .p-dialog-title）
            f" QLabel#dsDialogTitle {{"
            f" color: {heading};"
            f" font-weight: {weight_heading};"
            f" }}"
            # 关闭按钮：只收敛图标字号到 --size-20 与色阶，**不**设按钮本体宽高
            # （与 Aura 同款取舍：硬设 20×20 会把点击热区压到 `20px`，低于 WCAG 2.5.8 的 `24px`）
            f" QToolButton#dsDialogClose {{"
            f" color: {_color(theme, 'textSecondary')};"
            f" font-size: {_size('size_20')};"
            f" border: none;"
            f" background: transparent;"
            f" }}"
            f" QToolButton#dsDialogClose:hover {{ color: {text}; }}"
        )

    # ── 右上角关闭按钮（可选）────────────────────────────────
    def _build_close_button(self) -> QToolButton:
        """构造右上角关闭按钮；只改图标字号与色阶，不改点击热区（§12.2）。

        刻意**不**给按钮设固定宽高（Web 端 AppDialog.vue 同款取舍）：硬设成图标尺寸
        会把点击热区压到 20px，低于 WCAG 2.5.8 的 24px 最小目标。这里只设**最小**尺寸
        `--size-24`，既保住热区，又让按钮随字体自然撑开。
        """
        button = QToolButton(self)
        button.setObjectName("dsDialogClose")
        button.setText("\u2715")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRaise(True)
        button.setToolTip(_("btn_close"))
        min_side = _px("size_24")
        button.setMinimumSize(min_side, min_side)
        button.clicked.connect(self.reject)
        return button

    def _place_close_button(self) -> None:
        """把关闭按钮放到内容区右上角（不动业务自己的 layout 结构）。"""
        if self._close_button is None:
            self._close_button = self._build_close_button()
        pad_h = _px("space_20")
        button = self._close_button
        button.adjustSize()
        button.move(max(0, self.width() - button.width() - pad_h), _px("space_18"))
        button.raise_()

    # ── 内边距（首次显示时套到 `layout`）────────────────────────
    def showEvent(self, event: QShowEvent | None) -> None:
        """首次显示时把 DS 内边距套到布局，并按需摆好关闭按钮。"""
        super().showEvent(event)
        if not self._margin_applied:
            layout = self.layout()
            if isinstance(layout, QLayout):
                pad_v = _px("space_18")
                pad_h = _px("space_20")
                layout.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
            self._margin_applied = True
        if self._closable:
            self._place_close_button()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        """窗口尺寸变化时把关闭按钮重新贴到右上角。"""
        super().resizeEvent(event)
        if self._closable and self._close_button is not None:
            self._place_close_button()

    # ── 便于测试/调试 ─────────────────────────────────────────
    @property
    def theme_name(self) -> str:
        return self._theme

    @property
    def closable(self) -> bool:
        return self._closable

    @property
    def close_button(self) -> QToolButton | None:
        return self._close_button

    @property
    def content_padding(self) -> tuple[int, int]:
        """当前主题下的 (左右, 上下) 内边距，单位 px。"""
        return _px("space_20"), _px("space_18")


def build_title_row(title: str, parent: QWidget | None = None) -> tuple[QWidget, QHBoxLayout]:
    """构造 §12.2 口径的标题行（标题标签 + 弹性空白），供弹窗内容区复用。

    BaseDialog 的 QSS 用 `QLabel#dsDialogTitle` 承担「--text-heading + 600」，
    本函数负责把 objectName 挂上并把标题行做成可直接 addWidget 的容器。
    """
    from PyQt6.QtWidgets import QLabel

    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(title, row)
    label.setObjectName("dsDialogTitle")
    layout.addWidget(label)
    layout.addStretch()
    return row, layout


__all__ = ["BaseDialog", "build_title_row"]
