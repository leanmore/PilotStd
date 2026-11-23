"""Win 端 BaseInput / BaseSelect：样式全部取自 tokens_generated（跨端令牌产物）。

与 Web 的 `<AppInput>` / `<AppSelect>` 一一对应：
  size ↔ size（l/m/s，单行外框高度取 --input-height-*，语义独立于 --btn-height-*）
  四态 ↔ 四态（docs/reference/ui-system.md §11.3）

样式来自 `pilotstd/ui/tokens_generated.py`（由 `scripts/gen_win_tokens.py`
从 Web 的 design-tokens.css / themes.ts 生成），因此两端色值与尺度永远一致；
缺令牌即抛错，禁止在控件里手写色值或尺寸字面量（G-055）。
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QComboBox, QLineEdit, QWidget

from pilotstd.ui import tokens_generated as T

# 尺寸档 → (高度令牌, 水平内边距令牌, 字号令牌)
# 取值口径与 web/src/components/ui/AppInput.vue 的 `.app-input--*` 一致：
#   L 40px / space-16 / font-15、M 34px / space-12 / font-13、S 28px / space-10 / font-12
_SIZE_TOKENS: dict[str, tuple[str, str, str]] = {
    "l": ("input_height_lg", "space_16", "font_size_15"),
    "m": ("input_height_md", "space_12", "font_size_13"),
    "s": ("input_height_sm", "space_10", "font_size_12"),
}

# 下拉的尺寸档：高度/字号同上，但左右内边距按 AppSelect.vue 的 label 口径
# （L space-16 / M space-14 / S space-12）——下拉的左右内边距由 label 承担，
# 与单行输入框不是同一组取值，这里照搬 Web 实现，避免两端看起来"缩进不同"。
_SELECT_SIZE_TOKENS: dict[str, tuple[str, str, str]] = {
    "l": ("input_height_lg", "space_16", "font_size_15"),
    "m": ("input_height_md", "space_14", "font_size_13"),
    "s": ("input_height_sm", "space_12", "font_size_12"),
}

# 四态里描边的粗细：默认/悬停/禁用 1px，聚焦 2px（等效 Web 的 box-shadow 外发光）
_BORDER_WIDTH = 1
_FOCUS_BORDER_WIDTH = 2


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
    """取像素尺度令牌并转成整数（QSS 里要做四态等值换算，必须先有数值）。"""
    value = _size(key)
    if not value.endswith("px"):
        raise ValueError(f"scale token {key} is not a px length: {value!r}")
    return int(float(value[: -len("px")]))


class BaseInput(QLineEdit):
    """跨端统一单行输入框（Win 端）。

    与 Web 的 `<AppInput>` 对应（本阶段只覆盖单行文本/密码形态；多行与数字分叉
    等 Web 端契约稳定后再补，避免 Win 端先行造出与 Web 不一致的形态）。

    ── 四态（ui-system.md §11.3）──
      Default  : --surface 底 + 1px --border 描边 + --text 文字
      Hover    : 只把描边提到 --text-dim（**不改底色**，否则与表格行 hover 叠成双层高亮）
      Focus    : 描边换 --primary + 加粗到 2px（QSS 无 box-shadow，2px 主色描边即等效外发光）
      Disabled : --disabled-bg / --disabled-text（A-53 接线后的唯一口径）

    ── 为什么聚焦要把 min-height / padding 各让回 1px ──
    Qt 的 `min-height` 是内容盒高度，外框总高 = min-height + 2×描边；聚焦把描边从
    1px 加到 2px 会让总高多 2px，同一表单里的控件会在获得焦点时"跳高"并把下面
    的元素顶下去。故聚焦态按 `高度-4` / `内边距-1` 换算，四态外框总高恒等于高度令牌。
    """

    def __init__(
        self,
        text: str = "",
        *,
        size: str = "m",
        theme: str = "light",
        password: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if size not in _SIZE_TOKENS:
            raise ValueError(f"unknown size: {size!r}; expected l/m/s")
        self._size_name = size
        self._theme = theme
        self._password = password
        if password:
            self.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_style()

    # ── 样式 ─────────────────────────────────────────────────
    def _apply_style(self) -> None:
        """按尺寸与主题组装 QSS；所有色值/尺寸都来自生成令牌，缺令牌即抛错。"""
        height_key, pad_key, font_key = _SIZE_TOKENS[self._size_name]
        height = _px(height_key)
        pad = _px(pad_key)
        font = _size(font_key)
        radius = _size("ds_radius_md")

        surface = _color(self._theme, "surface")
        text = _color(self._theme, "text")
        border = _color(self._theme, "border")
        hover_border = _color(self._theme, "textDim")
        focus_border = _color(self._theme, "primary")
        disabled_bg = _color(self._theme, "disabledBg")
        disabled_fg = _color(self._theme, "disabledText")

        self.setStyleSheet(
            f"QLineEdit {{"
            f" background: {surface};"
            f" color: {text};"
            f" border: {_BORDER_WIDTH}px solid {border};"
            f" border-radius: {radius};"
            f" min-height: {height - 2 * _BORDER_WIDTH}px;"
            f" padding: 0 {pad}px;"
            f" font-size: {font};"
            f" }}"
            f" QLineEdit:hover {{ border-color: {hover_border}; }}"
            f" QLineEdit:focus {{"
            f" border: {_FOCUS_BORDER_WIDTH}px solid {focus_border};"
            f" min-height: {height - 2 * _FOCUS_BORDER_WIDTH}px;"
            f" padding: 0 {pad - (_FOCUS_BORDER_WIDTH - _BORDER_WIDTH)}px;"
            f" }}"
            f" QLineEdit:disabled {{"
            f" background: {disabled_bg};"
            f" color: {disabled_fg};"
            f" border-color: {border};"
            f" }}"
        )
        # 应用级样式表存在时，QComboBox/QLineEdit 的 sizeHint 在首次 polish 前返回的是
        # **未套控件 QSS** 的高度（实测 22px），要等事件循环 polish 后才变回令牌高度。
        # 这里立即 ensurePolished，让构造完成即拿到正确高度，避免布局在首帧按 22px 排版。
        self.ensurePolished()
        # placeholder 只能走调色板：Qt QSS 不支持 `::placeholder` 伪元素。
        # 必须放在 ensurePolished 之后 —— polish 会用 QSS 的 `color` 重建调色板，
        # 先设会被覆盖回正文色（实测 placeholder 变成 text 的颜色）。
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(_color(self._theme, "textDim")))
        self.setPalette(palette)
        self.updateGeometry()

    # ── 便于测试/调试 ─────────────────────────────────────────
    @property
    def size_name(self) -> str:
        return self._size_name

    @property
    def theme_name(self) -> str:
        return self._theme

    @property
    def is_password(self) -> bool:
        return self._password


class BaseSelect(QComboBox):
    """跨端统一下拉选择（Win 端）。

    与 Web 的 `<AppSelect>` 对应：尺寸档 / 圆角 / 四态与 `BaseInput` 同口径，
    区别只有两点（都照搬 Web 实现，不另立标准）：
      * 左右内边距由 label 承担，档位取值见 `_SELECT_SIZE_TOKENS`；
      * 需要额外给下拉面板与箭头子控件上色（QComboBox 的弹出列表是独立 QAbstractItemView）。
    """

    def __init__(
        self,
        items: list[str] | None = None,
        *,
        size: str = "m",
        theme: str = "light",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if size not in _SELECT_SIZE_TOKENS:
            raise ValueError(f"unknown size: {size!r}; expected l/m/s")
        self._size_name = size
        self._theme = theme
        if items:
            self.addItems(items)
        self._apply_style()

    # ── 样式 ─────────────────────────────────────────────────
    def _apply_style(self) -> None:
        """按尺寸与主题组装 QSS；所有色值/尺寸都来自生成令牌，缺令牌即抛错。"""
        height_key, pad_key, font_key = _SELECT_SIZE_TOKENS[self._size_name]
        height = _px(height_key)
        pad = _px(pad_key)
        font = _size(font_key)
        radius = _size("ds_radius_md")
        arrow_width = _px("space_20")

        surface = _color(self._theme, "surface")
        text = _color(self._theme, "text")
        border = _color(self._theme, "border")
        hover_border = _color(self._theme, "textDim")
        focus_border = _color(self._theme, "primary")
        disabled_bg = _color(self._theme, "disabledBg")
        disabled_fg = _color(self._theme, "disabledText")
        selected = _color(self._theme, "selected")

        self.setStyleSheet(
            f"QComboBox {{"
            f" background: {surface};"
            f" color: {text};"
            f" border: {_BORDER_WIDTH}px solid {border};"
            f" border-radius: {radius};"
            f" min-height: {height - 2 * _BORDER_WIDTH}px;"
            f" padding: 0 {pad}px;"
            f" font-size: {font};"
            f" }}"
            f" QComboBox:hover {{ border-color: {hover_border}; }}"
            f" QComboBox:focus {{"
            f" border: {_FOCUS_BORDER_WIDTH}px solid {focus_border};"
            f" min-height: {height - 2 * _FOCUS_BORDER_WIDTH}px;"
            f" padding: 0 {pad - (_FOCUS_BORDER_WIDTH - _BORDER_WIDTH)}px;"
            f" }}"
            f" QComboBox:disabled {{"
            f" background: {disabled_bg};"
            f" color: {disabled_fg};"
            f" border-color: {border};"
            f" }}"
            # 箭头区域只清描边/底色，宽度取 --space-20，保留 Fusion 自绘箭头
            f" QComboBox::drop-down {{"
            f" border: none;"
            f" background: transparent;"
            f" width: {arrow_width}px;"
            f" }}"
            # 弹出列表是独立视图，不吃上面的根选择器，需单独上色
            f" QComboBox QAbstractItemView {{"
            f" background: {surface};"
            f" color: {text};"
            f" border: 1px solid {border};"
            f" selection-background-color: {selected};"
            f" selection-color: {text};"
            f" }}"
        )
        # 同 BaseInput：应用级样式表下首次 polish 前 sizeHint 会退回 22px，立即 polish 修正
        self.ensurePolished()
        self.updateGeometry()

    # ── 便于测试/调试 ─────────────────────────────────────────
    @property
    def size_name(self) -> str:
        return self._size_name

    @property
    def theme_name(self) -> str:
        return self._theme
