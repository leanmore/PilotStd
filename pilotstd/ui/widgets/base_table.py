"""Win 端 BaseTable：样式全部取自 tokens_generated（跨端令牌产物）。

与 Web 的 `<AppTable>` 一一对应（docs/reference/ui-system.md §12.1）：
  表头背景 `--surface-raised` / 表头字色 `--text` / 字号 `--font-size-11` / 字重 600
  斑马纹 `--surface-raised` / 行 hover 与选中 `--selected`
  边框 `--border`（外框）+ `--border-light`（行分隔）/ 圆角 `--ds-radius-md`

样式来自 `pilotstd/ui/tokens_generated.py`（由 `scripts/gen_win_tokens.py` 从 Web 的
design-tokens.css / themes.ts 生成），因此两端色值与尺度永远一致；缺令牌即抛错，
禁止在控件里手写色值或尺寸字面量（G-055）。

── 表头字色为什么是 `--text` 而不是 `--text-secondary` ──
Web 端实测（style.css 的 RETAINED 注释 + Tech-Debt #8）：Aura 的组件作用域 token 解析后是
直接值，root 级注入覆盖不到；改用 `--text-dim` 时浅色主题实测仅 2.4–2.6:1，不满足 WCAG AA，
改用 `--text` 后 ≈7:1（浅色深字 / 深色浅字自适应）。层级感由「加粗 + 小字号」承担，不靠降亮度。
Win 端照抄同一结论，不另立标准。

── 为什么 `--selected` 必须先合成成不透明色 ──
Web 的 `--selected` 是主色 8% 透明的 rgba，浏览器里叠在行底色上。Qt 的 item view
委托（QStyledItemDelegate）**不会**把 `::item` 的半透明背景按行底色合成：实测把该 rgba
原样写进 `QTableWidget::item:selected`，渲染出来是一块明显偏深的主色（R/G/B 三个通道都被
主色顶替，亮度接近主色本身），而不是预期的近白色；同样的 rgba 写法在普通 QLabel 上却是
正确的近白色。故这里用 `_composite()` 先把 alpha 令牌按行底色（`surface`）压成 `#rrggbb`
再交给 QSS。代价：斑马行（`surface-raised`）上的 hover/选中与普通行用同一个合成值，
色差 < 1 个 8bit 阶，肉眼不可辨 —— 但换来「悬停/选中」在任何行上都稳定可见。

── 为什么 item/表头的水平内边距是 0，而不是 Web 的 `--space-14` ──
Web 表格没有窄列；Win 端工作区表格有 **34px 的「序号」列**、54px 的「工作状态」列
（`table_constants.py` 的 `WORK_COLUMNS` + `_ui_setup_ops._col_specs`）。实测（Microsoft YaHei
9pt / 正文 13px、表头 11px 600；`QHeaderView::section { padding: 10px Npx }`）：

| 水平内边距 | 34px「序号」表头墨迹宽（字宽 26px） | 54px「工作状态」表头（字宽 52px） |
|---|---|---|
| 0px  | 23px，正常 | 45px，正常 |
| 4px  | 23px，正常 | 45px，正常 |
| 8px  | 18px，被挤扁 | 38px，被挤扁 |
| 14px | **整列空白**（省略到 0 像素） | 26px，只剩半个字 |

单元格同理（`QTableWidget::item`）：34px 列在 14px 水平内边距下 ink 为 None。
故水平内边距交给 Qt 委托的默认 item margin（实测约 4px，34px 列可完整显示），
**竖直方向保留 DS 的 `--space-9` / `--space-10`** —— 行高节奏（38px / 37px）才是两端观感
一致的主要来源。这是 Win 端为「既有窄列」付的局部代价，不是新口径：Web 端没有对应场景。

── 为什么行高/表头高要显式设 ──
QSS 的 `::item { padding }` 只影响 `sizeHintForRow()`，**不会**改 `rowHeight()`
（Qt 的 `verticalHeader` 默认段高仍是 30px，实测 padding 9px 时文字仍居中不裁切，但行高没变）。
要让行高真正对齐 Web 的「9px + 9px + 行高 1.5 倍字号」，必须在 QSS 之外显式设
`verticalHeader().setDefaultSectionSize()` 与 `horizontalHeader().setFixedHeight()`。
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QTableWidget, QWidget

from pilotstd.ui import tokens_generated as T

logger = logging.getLogger(__name__)

# 四主题白名单：未知主题必须显式报错，不能静默回退 light（否则配色错误无人发现）
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
    """取像素尺度令牌并转成整数（行高换算需要数值）。"""
    value = _size(key)
    if not value.endswith("px"):
        raise ValueError(f"scale token {key} is not a px length: {value!r}")
    return int(float(value[: -len("px")]))


def _line_px(font_key: str, line_key: str) -> int:
    """字号令牌 × 行高倍数令牌 → 行高像素（向上取整，避免小数字号被截断后裁字）。"""
    font = _px(font_key)
    ratio = float(_size(line_key))
    return int(font * ratio + 0.5)


def _rgb(value: str) -> tuple[int, int, int] | None:
    """解析十六进制或 rgb/rgba 形式的颜色；无法解析时返回 None。"""
    text = value.strip().lower()
    if text.startswith("#"):
        body = text[1:]
        if len(body) == 3:
            return tuple(int(ch * 2, 16) for ch in body)  # type: ignore[return-value]
        if len(body) >= 6:
            return (int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16))
        return None
    if text.startswith("rgb"):
        start = text.find("(")
        end = text.find(")")
        if start < 0 or end < 0:
            return None
        parts = [p.strip() for p in text[start + 1 : end].split(",")]
        if len(parts) < 3:
            return None
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            # 令牌值由 gen_win_tokens.py 生成，正常不会走到这里；一旦出现说明
            # tokens_generated.py 里有非法颜色，必须留痕（G-050：失败不可见）。
            logger.warning("BaseTable: 无法解析 rgb 颜色 %r，按不可解析处理", value)  # i18n-allow: 内部诊断日志
            return None
    return None


def _alpha(value: str) -> float:
    """取 rgba 颜色的 alpha（0–1）；非 rgba 或解析失败按不透明处理。"""
    text = value.strip().lower()
    if not text.startswith("rgba"):
        return 1.0
    start = text.find("(")
    end = text.find(")")
    if start < 0 or end < 0:
        return 1.0
    parts = [p.strip() for p in text[start + 1 : end].split(",")]
    if len(parts) < 4:
        return 1.0
    raw = parts[3]
    try:
        if raw.endswith("%"):
            return max(0.0, min(1.0, float(raw[:-1]) / 100.0))
        number = float(raw)
    except ValueError:
        # 同上：令牌产物里的非法 alpha 必须留痕，不能静默当成不透明。
        logger.warning("BaseTable: 无法解析 rgba alpha %r，按不透明处理", value)  # i18n-allow: 内部诊断日志
        return 1.0
    # Qt/CSS 两种写法都收：0–1 的浮点，或 0–255 的整数
    return max(0.0, min(1.0, number if number <= 1.0 else number / 255.0))


def _composite(fg: str, bg: str) -> str:
    """把（可能半透明的）fg 叠在不透明 bg 上，返回 `#rrggbb`。

    Qt 的 item view 委托不会替我们合成半透明 `::item` 背景（见模块 docstring 的实测），
    所以必须在交给 QSS 之前先算成不透明色。
    """
    fg_rgb = _rgb(fg)
    bg_rgb = _rgb(bg)
    if fg_rgb is None or bg_rgb is None:
        # 无法解析就原样返回：宁可让测试里的「取色」断言先红，也不要静默换成别的颜色
        return fg
    a = _alpha(fg)
    blended = tuple(int(round(f * a + b * (1.0 - a))) for f, b in zip(fg_rgb, bg_rgb))
    return "#{:02x}{:02x}{:02x}".format(*blended)


class BaseTable(QTableWidget):
    """跨端统一数据表格（Win 端）。

    与 Web 的 `<AppTable>` 对应；业务侧只负责「哪些列 + 什么数据 + 列宽」，
    表头/斑马纹/hover/边框/圆角一律由本控件承担（§12.1、§12.3 禁止项）。

    ── 参数 ──
      theme   : 四主题之一（light/dark/green/blue），未知值抛 ValueError
      striped : 是否启用斑马纹（默认 True，对应 Web 的 `stripedRows`）
    """

    def __init__(
        self,
        rows: int = 0,
        columns: int = 0,
        *,
        theme: str = "light",
        striped: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(rows, columns, parent)
        if theme not in _THEMES:
            raise ValueError(f"unknown theme: {theme!r}; expected one of {_THEMES}")
        self._theme = theme
        self._striped = bool(striped)
        self._apply_style()

    # ── 样式 ─────────────────────────────────────────────────
    def _apply_style(self) -> None:
        """按主题组装 QSS 并设置行高；所有色值/尺寸都来自生成令牌，缺令牌即抛错。"""
        theme = self._theme
        surface = _color(theme, "surface")
        raised = _color(theme, "surfaceRaised")
        text = _color(theme, "text")
        border = _color(theme, "border")
        border_light = _color(theme, "borderLight")
        selected = _composite(_color(theme, "selected"), surface)
        radius = _size("ds_radius_md")
        font_body = _size("font_size_13")
        font_head = _size("font_size_11")
        weight_head = _size("font_weight_semibold")
        pad_row = _px("space_9")
        pad_head = _px("space_10")

        self.setStyleSheet(
            f"QTableWidget {{"
            f" background: {surface};"
            f" alternate-background-color: {raised};"
            f" gridline-color: {border_light};"
            f" border: 1px solid {border};"
            f" border-radius: {radius};"
            f" color: {text};"
            f" font-size: {font_body};"
            f" selection-background-color: {selected};"
            f" selection-color: {text};"
            f" }}"
            # 表头：背景抬升一档、字色 text（不是 textSecondary，见模块 docstring）、
            # 11px / 600；大写（text-transform）与字距 0.6px 是 Web 端 CSS 特性，
            # Qt QSS 不支持 text-transform，跳过（§12.1 的「大写不适用 Qt」）。
            f" QHeaderView::section {{"
            f" background: {raised};"
            f" color: {text};"
            f" border: none;"
            f" border-right: 1px solid {border_light};"
            f" border-bottom: 1px solid {border};"
            f" padding: {pad_head}px 0px;"
            f" font-size: {font_head};"
            f" font-weight: {weight_head};"
            f" }}"
            f" QHeaderView::section:hover {{ background: {selected}; }}"
            # 单元格：只留行分隔线（border-light），不加竖线 —— 竖线由 setShowGrid(False) 关掉，
            # 与 Web 的「整表不被线条切碎」一致。
            f" QTableWidget::item {{"
            f" padding: {pad_row}px 0px;"
            f" border-bottom: 1px solid {border_light};"
            f" }}"
            f" QTableWidget::item:hover {{ background: {selected}; }}"
            f" QTableWidget::item:selected {{ background: {selected}; color: {text}; }}"
            # 左上角交叉按钮（两个表头交汇处）单独上色，否则露出系统默认灰块
            f" QTableCornerButton::section {{ background: {raised}; border: none; }}"
        )

        # 斑马纹：Web 用 stripedRows，Qt 对应 setAlternatingRowColors + alternate-background-color
        self.setAlternatingRowColors(self._striped)
        # 关闭默认网格：DS 只要行分隔线，不要竖线
        self.setShowGrid(False)

        # 行高/表头高必须显式设（QSS 的 ::item padding 不改 rowHeight，见模块 docstring）
        row_height = 2 * pad_row + _line_px("font_size_13", "line_height_normal")
        header_height = 2 * pad_head + _line_px("font_size_11", "line_height_normal")
        vertical = self.verticalHeader()
        if vertical is not None:
            vertical.setDefaultSectionSize(row_height)
            # 选中列时不要把表头画成高亮色（Web 端表头恒为 surface-raised）
            vertical.setHighlightSections(False)
        horizontal = self.horizontalHeader()
        if horizontal is not None:
            horizontal.setFixedHeight(header_height)
            horizontal.setHighlightSections(False)

        # 与 BaseInput 同款坑：应用级样式表存在时，控件首次 polish 前 sizeHint/尺寸
        # 用的是未套控件 QSS 的值；立即 polish 让构造完成即拿到令牌尺寸，避免首帧按旧值排版。
        self.ensurePolished()
        self.updateGeometry()

    # ── 便于测试/调试 ─────────────────────────────────────────
    @property
    def theme_name(self) -> str:
        return self._theme

    @property
    def striped(self) -> bool:
        return self._striped
