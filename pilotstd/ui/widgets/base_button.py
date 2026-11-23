"""Win 端 BaseButton：样式全部取自 tokens_generated（跨端令牌产物）。"""

from __future__ import annotations

from PyQt6.QtWidgets import QPushButton, QWidget

from pilotstd.ui import tokens_generated as T

# 层级 → (背景, 文字, 边框) 的三元组；值为 CSS 变量名，运行时从令牌解析
_KIND_TOKENS: dict[str, tuple[str, str, str]] = {
    "primary": ("primaryFill", "textOnPrimary", ""),
    "secondary": ("surface", "text", "border"),
    "danger": ("danger", "textOnPrimary", ""),
    "ghost": ("transparent", "textSecondary", ""),
}

_SIZE_TOKENS: dict[str, tuple[str, str, str]] = {
    # (高度令牌, 水平内边距令牌, 字号令牌)
    "l": ("btn_height_lg", "space_20", "font_size_15"),
    "m": ("btn_height_md", "space_16", "font_size_13"),
    "s": ("btn_height_sm", "space_12", "font_size_12"),
}


class BaseButton(QPushButton):
    """跨端统一按钮（Win 端）。

    与 Web 的 `<AppButton>` 一一对应：
      kind ↔ type（primary/secondary/danger/ghost）
      size ↔ size（l/m/s）

    样式来自 `pilotstd/ui/tokens_generated.py`（由 `scripts/gen_win_tokens.py`
    从 Web 的 design-tokens.css / themes.ts 生成），因此两端色值与尺度永远一致。
    """

    def __init__(
        self,
        text: str = "",
        *,
        kind: str = "secondary",
        size: str = "m",
        theme: str = "light",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if kind not in _KIND_TOKENS:
            raise ValueError(f"unknown kind: {kind!r}; expected primary/secondary/danger/ghost")
        if size not in _SIZE_TOKENS:
            raise ValueError(f"unknown size: {size!r}; expected l/m/s")
        self._kind = kind
        self._size_name = size
        self._theme = theme
        self.setProperty("variant", kind)
        self._apply_style()

    # ── 令牌读取 ─────────────────────────────────────────────
    def _color(self, key: str) -> str:
        """取当前主题的颜色；`transparent` 原样返回（QSS 支持该关键字）。"""
        if key == "transparent":
            return "transparent"
        value = T.color(self._theme, key)
        if not value:
            raise KeyError(f"theme {self._theme} has no color key {key}; run scripts/gen_win_tokens.py")
        return value

    def _size(self, key: str) -> str:
        value = T.token(key)
        if not value:
            raise KeyError(f"missing scale token {key}; run scripts/gen_win_tokens.py")
        return value

    # ── 样式 ─────────────────────────────────────────────────
    def _apply_style(self) -> None:
        """按层级与尺寸组装 QSS；所有色值/尺寸都来自生成令牌，缺令牌即抛错。"""
        bg_key, fg_key, border_key = _KIND_TOKENS[self._kind]
        height_key, pad_key, font_key = _SIZE_TOKENS[self._size_name]

        bg = self._color(bg_key)
        fg = self._color(fg_key)
        border = f"1px solid {self._color(border_key)}" if border_key else "none"
        radius = self._size("ds_radius_md")
        height = self._size(height_key)
        pad = self._size(pad_key)
        font = self._size(font_key)

        # 主色按钮悬停用更深一档；其余层级保持底色（避免误用主色 `hover`）
        hover_bg = self._color("primaryFillHover") if self._kind == "primary" else bg

        # A-53 收口（Win 侧）：禁用态用 --disabled-bg / --disabled-text。
        # 此前用 borderLight/textDim 顶替，是因为 disabledBg/disabledText 在 Web 侧
        # 还没接线（ui-system.md §10.6 遗留项）；Web 的 applyThemeToDom 接线后，
        # 两端统一走 `disabled`* 令牌，避免 Win 端继续偏离 DS 的禁用态口径。
        disabled_bg = self._color("disabledBg")
        disabled_fg = self._color("disabledText")

        self.setStyleSheet(
            f"QPushButton {{"
            f" background: {bg};"
            f" color: {fg};"
            f" border: {border};"
            f" border-radius: {radius};"
            f" min-height: {height};"
            f" padding: 0 {pad};"
            f" font-size: {font};"
            f" font-weight: 500;"
            f" }}"
            f" QPushButton:hover {{ background: {hover_bg}; }}"
            f" QPushButton:disabled {{ background: {disabled_bg}; color: {disabled_fg}; }}"
        )

    # ── 便于测试/调试 ─────────────────────────────────────────
    @property
    def kind(self) -> str:
        return self._kind

    @property
    def size_name(self) -> str:
        return self._size_name
