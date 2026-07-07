# pilotstd/ui/themes.py
# 四套主题样式表 + 标题栏深色/浅色自适应
# 重构：提取公共 QSS 模板 + 配色变量字典，减少重复代码

import ctypes
from typing import Any

# ═══════════════════════════════════════════════════════════
# 配色方案字典（与 Web 端 themes.ts 保持一致的色值）
# ═══════════════════════════════════════════════════════════
COLOR_SCHEMES: dict[str, dict[str, str]] = {
    "经典白": {
        "bg": "#f1f5f9",  # 降低亮度，更柔和
        "surface": "#ffffff",
        "surface_alt": "#f8fafc",
        "text": "#475569",
        "text_bright": "#334155",
        "text_dim": "#94a3b8",
        "text_heading": "#0f172a",
        "border": "#e2e8f0",
        "border_light": "#f1f5f9",
        "primary": "#6366f1",
        "primary_light": "#818cf8",
        "primary_dark": "#4f46e5",
        "primary_darker": "#4338ca",
        "primary_bg": "rgba(99, 102, 241, 0.15)",
        "primary_text": "#ffffff",
        "disabled_bg": "#e2e8f0",
        "disabled_text": "#94a3b8",
        "gridline": "#f1f5f9",
        "hover_bg": "#f8fafc",
        "log_bg": "#f8fafc",
    },
    "暗夜黑": {
        "bg": "#0f172a",
        "surface": "#1e293b",
        "surface_alt": "#334155",
        "text": "#cbd5e1",
        "text_bright": "#e2e8f0",
        "text_dim": "#94a3b8",
        "text_heading": "#f1f5f9",
        "border": "#475569",
        "border_light": "#334155",
        "primary": "#6366f1",
        "primary_light": "#818cf8",
        "primary_dark": "#4f46e5",
        "primary_darker": "#4338ca",
        "primary_bg": "rgba(129, 140, 248, 0.2)",
        "primary_text": "#ffffff",
        "disabled_bg": "#475569",
        "disabled_text": "#94a3b8",
        "gridline": "#334155",
        "hover_bg": "#334155",
        "log_bg": "#0f172a",
    },
    "护眼绿": {
        "bg": "#e8f5e9",  # 降低亮度，更柔和
        "surface": "#f6fbf7",  # 从纯白改为极浅绿色，降低刺眼感
        "surface_alt": "#dcfce7",
        "text": "#166534",
        "text_bright": "#15803d",
        "text_dim": "#65a77d",
        "text_heading": "#14532d",
        "border": "#bbf7d0",
        "border_light": "#dcfce7",
        "primary": "#22c55e",
        "primary_light": "#4ade80",
        "primary_dark": "#16a34a",
        "primary_darker": "#15803d",
        "primary_bg": "rgba(34, 197, 94, 0.15)",
        "primary_text": "#ffffff",
        "disabled_bg": "#bbf7d0",
        "disabled_text": "#86efac",
        "gridline": "#dcfce7",
        "hover_bg": "#e8f5e9",
        "log_bg": "#e8f5e9",
    },
    "科技蓝": {
        "bg": "#0c1222",
        "surface": "#151e32",
        "surface_alt": "#1e293b",
        "text": "#cbd5e1",
        "text_bright": "#e2e8f0",
        "text_dim": "#94a3b8",
        "text_heading": "#f1f5f9",
        "border": "#1e293b",
        "border_light": "#1e293b",
        "primary": "#0ea5e9",
        "primary_light": "#38bdf8",
        "primary_dark": "#0284c7",
        "primary_darker": "#0369a1",
        "primary_bg": "rgba(14, 165, 233, 0.2)",
        "primary_text": "#ffffff",
        "disabled_bg": "#1e293b",
        "disabled_text": "#475569",
        "gridline": "#1e293b",
        "hover_bg": "#1e293b",
        "log_bg": "#0c1222",
    },
}

# 暗色主题集合
DARK_THEMES = {"暗夜黑", "科技蓝"}

# ═══════════════════════════════════════════════════════════
# 公共 QSS 模板（结构样式，颜色通过变量注入）
# ═══════════════════════════════════════════════════════════
COMMON_QSS = """
/* === 全局 === */
QMainWindow {{ background-color: {bg}; }}
QDialog, QWidget {{ background-color: {surface}; color: {text}; font-size: 10pt; }}

/* === 菜单栏 === */
QMenuBar {{ background-color: {surface}; color: {text_bright}; border-bottom: 1px solid {border}; }}
QMenuBar::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_light}, stop:1 {primary});
    color: {primary_text};
    border-radius: 4px;
}}
QMenu {{ background-color: {surface}; color: {text_bright}; border: 1px solid {border}; border-radius: 8px; }}
QMenu::item {{ text-align: left; padding: 8px 24px; border-radius: 4px; margin: 2px 4px; }}
QMenu::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_light}, stop:1 {primary});
    color: {primary_text};
}}

/* === 工具栏 === */
QToolBar {{
    background-color: {surface};
    border-bottom: 1px solid {border};
    spacing: 8px;
    padding: 6px 8px;
}}

/* === 按钮（主色） === */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_light}, stop:1 {primary});
    color: {primary_text};
    border: none;
    padding: 8px 18px;
    border-radius: 6px;
    font-weight: 500;
}}
QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary}, stop:1 {primary_dark}); }}
QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {primary_dark}, stop:1 {primary_darker});
}}
QPushButton:disabled {{ background: {disabled_bg}; color: {disabled_text}; }}

/* === 输入框 === */
QLineEdit {{
    border: 1px solid {border};
    border-radius: 6px;
    padding: 8px 12px;
    background-color: {bg};
    color: {text};
}}
QLineEdit:focus {{ border-color: {primary}; background: {surface}; }}

/* === 文件树 === */
QTreeWidget {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text};
    outline: 0;
}}
QTreeWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {gridline}; }}
QTreeWidget::item:selected {{ background: {primary_bg}; color: {primary}; border-radius: 4px; }}
QTreeWidget::item:hover {{ background-color: {hover_bg}; border-radius: 4px; }}

/* === 工作表 === */
QTableWidget {{
    background-color: {bg};
    alternate-background-color: {surface};
    gridline-color: {gridline};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {primary_bg};
    selection-color: {text_bright};
}}
QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {surface}, stop:1 {bg});
    color: {text_dim};
    padding: 10px 8px;
    border: none;
    border-right: 1px solid {border};
    font-weight: 600;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{ background: {surface_alt}; }}

/* === 进度条 === */
QProgressBar {{
    border: 1px solid {border};
    border-radius: 6px;
    text-align: center;
    background-color: {surface};
    color: {text_dim};
    font-size: 10pt;
    height: 24px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {primary_light}, stop:1 {primary});
    border-radius: 5px;
}}

/* === 日志区 === */
QTextEdit {{
    background-color: {log_bg};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text};
    font-family: 'JetBrains Mono', Consolas, "Microsoft YaHei", monospace;
    font-size: 9pt;
    padding: 8px;
}}

/* === 状态栏 === */
QStatusBar {{ background-color: {surface}; color: {text_dim}; font-size: 10pt; border-top: 1px solid {border}; }}

/* === Splitter === */
QSplitter::handle {{ background-color: {border}; width: 3px; border-radius: 2px; }}

/* === 分组框 === */
QGroupBox {{
    font-weight: bold;
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 18px;
    background: {surface};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 8px; color: {text_dim}; }}

/* === 滚动条（垂直） === */
QScrollBar:vertical {{ background: {bg}; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

/* === 滚动条（水平） === */
QScrollBar:horizontal {{ background: {bg}; height: 10px; border-radius: 5px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 40px; }}
QScrollBar::handle:horizontal:hover {{ background: {text_dim}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

/* === 滚动区右下角交汇区 — 消除深色主题下灰色方块。width/height=0 彻底隐藏 === */
QAbstractScrollArea::corner {{ background: transparent; border: none; width: 0px; height: 0px; }}

/* === 标签页 === */
QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {bg}; }}
QTabBar::tab {{
    background: {surface};
    padding: 10px 20px;
    border: 1px solid {border};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {bg}; color: {primary}; border-bottom: 2px solid {primary}; }}
"""


def generate_qss(theme_name: str) -> str:
    """根据主题名称生成完整 QSS。"""
    colors = COLOR_SCHEMES.get(theme_name)
    if not colors:
        return ""
    return COMMON_QSS.format(**colors)


def _set_titlebar_dark_mode(hwnd: int, dark: bool) -> None:
    """通过 DWM API 设置 Windows 标题栏深色/浅色模式。"""
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(ctypes.c_int(1 if dark else 0)),
            ctypes.sizeof(ctypes.c_int),
        )
    except (AttributeError, OSError):
        pass


def apply_theme(app: Any, theme_name: str) -> None:
    """应用主题样式表 + 标题栏明暗自适应。"""
    qss = generate_qss(theme_name)
    if qss:
        app.setStyle("Fusion")  # 强制 Fusion 确保 QMenu/QMessageBox 受 CSS 和翻译控制
        app.setStyleSheet(qss)
    else:
        app.setStyleSheet("")
        app.setStyle("Fusion")

    dark = theme_name in DARK_THEMES
    for widget in app.topLevelWidgets():
        if widget.isWindow() and int(widget.winId()) != 0:
            _set_titlebar_dark_mode(int(widget.winId()), dark)
