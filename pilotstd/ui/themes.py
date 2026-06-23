# pilotstd/ui/themes.py
# 四套主题样式表 + 标题栏深色/浅色自适应
# 配色思路：主色统一、灰度分层区分区块、语义三色标识状态

import ctypes
from typing import Any

THEMES: dict[str, str] = {
    "经典白": """
        /* === 全局 === */
        QMainWindow { background-color: #f5f7fa; }
        QDialog, QWidget { background-color: #ffffff; color: #1f2937; font-size: 10pt; }

        /* === 菜单栏 === */
        QMenuBar { background-color: #ffffff; color: #374151; border-bottom: 1px solid #e5e7eb; }
        QMenuBar::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #818cf8, stop:1 #6366f1); color: white; border-radius: 4px; }
        QMenu { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }
        QMenu::item { text-align: left; padding: 8px 24px; border-radius: 4px; margin: 2px 4px; }
        QMenu::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #818cf8, stop:1 #6366f1); color: white; }

        /* === 工具栏 === */
        QToolBar {
            background-color: #ffffff;
            border-bottom: 1px solid #e5e7eb;
            spacing: 8px;
            padding: 6px 8px;
        }

        /* === 按钮（主色） === */
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #818cf8, stop:1 #6366f1);
            color: white;
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-weight: 500;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6366f1, stop:1 #4f46e5); }
        QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4f46e5, stop:1 #4338ca); }
        QPushButton:disabled { background: #d1d5db; color: #9ca3af; }

        /* === 输入框 === */
        QLineEdit {
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 8px 12px;
            background: #ffffff;
            color: #374151;
        }
        QLineEdit:focus { border-color: #6366f1; background: #fafafe; }

        /* === 文件树 === */
        QTreeWidget {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            color: #374151;
            outline: 0;
        }
        QTreeWidget::item { padding: 6px 8px; border-bottom: 1px solid #f3f4f6; }
        QTreeWidget::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(129,140,248,0.15), stop:1 rgba(99,102,241,0.15)); color: #6366f1; border-radius: 4px; }
        QTreeWidget::item:hover { background-color: #f9fafb; border-radius: 4px; }

        /* === 工作表 === */
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f9fafb;
            gridline-color: #f3f4f6;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            selection-background-color: rgba(99,102,241,0.12);
            selection-color: #374151;
        }
        QHeaderView::section {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f9fafb, stop:1 #f3f4f6);
            color: #6b7280;
            padding: 10px 8px;
            border: none;
            border-right: 1px solid #e5e7eb;
            font-weight: 600;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QHeaderView::section:hover { background: #f3f4f6; }

        /* === 进度条 === */
        QProgressBar {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            text-align: center;
            background-color: #f3f4f6;
            color: #6b7280;
            font-size: 10pt;
            height: 24px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #6366f1);
            border-radius: 5px;
        }

        /* === 日志区 === */
        QTextEdit {
            background-color: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            color: #374151;
            font-family: 'JetBrains Mono', Consolas, "Microsoft YaHei", monospace;
            font-size: 9pt;
            padding: 8px;
        }

        /* === 状态栏 === */
        QStatusBar { background-color: #ffffff; color: #6b7280; font-size: 10pt; border-top: 1px solid #e5e7eb; }

        /* === Splitter === */
        QSplitter::handle { background-color: #e5e7eb; width: 3px; border-radius: 2px; }

        /* === 分组框 === */
        QGroupBox {
            font-weight: bold;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 18px;
            background: #ffffff;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 8px; color: #374151; }

        /* === 滚动条 === */
        QScrollBar:vertical { background: #f3f4f6; width: 10px; border-radius: 5px; }
        QScrollBar::handle:vertical { background: #d1d5db; border-radius: 5px; min-height: 40px; }
        QScrollBar::handle:vertical:hover { background: #9ca3af; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

        /* === 标签页 === */
        QTabWidget::pane { border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff; }
        QTabBar::tab { background: #f3f4f6; padding: 10px 20px; border: 1px solid #e5e7eb; border-bottom: none; border-radius: 6px 6px 0 0; margin-right: 2px; }
        QTabBar::tab:selected { background: #ffffff; color: #6366f1; border-bottom: 2px solid #6366f1; }
    """,
    "暗夜黑": """
        /* === 全局 === */
        QMainWindow { background-color: #0f172a; }
        QDialog, QWidget { background-color: #1e293b; color: #e2e8f0; font-size: 10pt; }

        /* === 菜单栏 === */
        QMenuBar { background-color: #1e293b; color: #f1f5f9; border-bottom: 1px solid #334155; }
        QMenuBar::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #818cf8, stop:1 #6366f1); color: white; border-radius: 4px; }
        QMenu { background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155; border-radius: 8px; }
        QMenu::item { text-align: left; padding: 8px 24px; border-radius: 4px; margin: 2px 4px; }
        QMenu::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #818cf8, stop:1 #6366f1); color: white; }

        /* === 工具栏 === */
        QToolBar {
            background-color: #1e293b;
            border-bottom: 1px solid #334155;
            spacing: 8px;
            padding: 6px 8px;
        }

        /* === 按钮（主色） === */
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #818cf8, stop:1 #6366f1);
            color: white;
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-weight: 500;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6366f1, stop:1 #4f46e5); }
        QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4f46e5, stop:1 #4338ca); }
        QPushButton:disabled { background: #334155; color: #64748b; }

        /* === 输入框 === */
        QLineEdit {
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 8px 12px;
            background-color: #0f172a;
            color: #e2e8f0;
        }
        QLineEdit:focus { border-color: #6366f1; background: #162032; }

        /* === 文件树 === */
        QTreeWidget {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #e2e8f0;
            outline: 0;
        }
        QTreeWidget::item { padding: 6px 8px; border-bottom: 1px solid #334155; }
        QTreeWidget::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(129,140,248,0.2), stop:1 rgba(99,102,241,0.2)); color: #818cf8; border-radius: 4px; }
        QTreeWidget::item:hover { background-color: #334155; border-radius: 4px; }

        /* === 工作表 === */
        QTableWidget {
            background-color: #0f172a;
            alternate-background-color: #1e293b;
            gridline-color: #334155;
            border: 1px solid #334155;
            border-radius: 8px;
            selection-background-color: rgba(99,102,241,0.2);
            selection-color: #e2e8f0;
        }
        QHeaderView::section {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e293b, stop:1 #0f172a);
            color: #94a3b8;
            padding: 10px 8px;
            border: none;
            border-right: 1px solid #334155;
            font-weight: 600;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QHeaderView::section:hover { background: #334155; }

        /* === 进度条 === */
        QProgressBar {
            border: 1px solid #334155;
            border-radius: 6px;
            text-align: center;
            background-color: #1e293b;
            color: #94a3b8;
            font-size: 10pt;
            height: 24px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #6366f1);
            border-radius: 5px;
        }

        /* === 日志区 === */
        QTextEdit {
            background-color: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #cbd5e1;
            font-family: 'JetBrains Mono', Consolas, "Microsoft YaHei", monospace;
            font-size: 9pt;
            padding: 8px;
        }

        /* === 状态栏 === */
        QStatusBar { background-color: #1e293b; color: #94a3b8; font-size: 10pt; border-top: 1px solid #334155; }

        /* === Splitter === */
        QSplitter::handle { background-color: #334155; width: 3px; border-radius: 2px; }

        /* === 分组框 === */
        QGroupBox {
            font-weight: bold;
            border: 1px solid #334155;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 18px;
            background: #1e293b;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 8px; color: #94a3b8; }

        /* === 滚动条 === */
        QScrollBar:vertical { background: #0f172a; width: 10px; border-radius: 5px; }
        QScrollBar::handle:vertical { background: #475569; border-radius: 5px; min-height: 40px; }
        QScrollBar::handle:vertical:hover { background: #64748b; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

        /* === 标签页 === */
        QTabWidget::pane { border: 1px solid #334155; border-radius: 8px; background: #0f172a; }
        QTabBar::tab { background: #1e293b; padding: 10px 20px; border: 1px solid #334155; border-bottom: none; border-radius: 6px 6px 0 0; margin-right: 2px; }
        QTabBar::tab:selected { background: #0f172a; color: #818cf8; border-bottom: 2px solid #6366f1; }
    """,
    "护眼绿": """
        /* === 全局 === */
        QMainWindow { background-color: #f0fdf4; }
        QDialog, QWidget { background-color: #ffffff; color: #166534; font-size: 10pt; }

        /* === 菜单栏 === */
        QMenuBar { background-color: #ffffff; color: #15803d; border-bottom: 1px solid #bbf7d0; }
        QMenuBar::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4ade80, stop:1 #22c55e); color: white; border-radius: 4px; }
        QMenu { background-color: #ffffff; color: #15803d; border: 1px solid #bbf7d0; border-radius: 8px; }
        QMenu::item { text-align: left; padding: 8px 24px; border-radius: 4px; margin: 2px 4px; }
        QMenu::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4ade80, stop:1 #22c55e); color: white; }

        /* === 工具栏 === */
        QToolBar {
            background-color: #ffffff;
            border-bottom: 1px solid #bbf7d0;
            spacing: 8px;
            padding: 6px 8px;
        }

        /* === 按钮（主色） === */
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4ade80, stop:1 #22c55e);
            color: white;
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-weight: 500;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #22c55e, stop:1 #16a34a); }
        QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #16a34a, stop:1 #15803d); }
        QPushButton:disabled { background: #bbf7d0; color: #86efac; }

        /* === 输入框 === */
        QLineEdit {
            border: 1px solid #86efac;
            border-radius: 6px;
            padding: 8px 12px;
            background-color: #ffffff;
            color: #166534;
        }
        QLineEdit:focus { border-color: #22c55e; background: #f0fdf4; }

        /* === 文件树 === */
        QTreeWidget {
            background-color: #ffffff;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            color: #166534;
            outline: 0;
        }
        QTreeWidget::item { padding: 6px 8px; border-bottom: 1px solid #f0fdf4; }
        QTreeWidget::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(74,222,128,0.15), stop:1 rgba(34,197,94,0.15)); color: #16a34a; border-radius: 4px; }
        QTreeWidget::item:hover { background-color: #f0fdf4; border-radius: 4px; }

        /* === 工作表 === */
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f0fdf4;
            gridline-color: #dcfce7;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            selection-background-color: rgba(34,197,94,0.12);
            selection-color: #166534;
        }
        QHeaderView::section {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0fdf4, stop:1 #dcfce7);
            color: #15803d;
            padding: 10px 8px;
            border: none;
            border-right: 1px solid #bbf7d0;
            font-weight: 600;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QHeaderView::section:hover { background: #dcfce7; }

        /* === 进度条 === */
        QProgressBar {
            border: 1px solid #bbf7d0;
            border-radius: 6px;
            text-align: center;
            background-color: #f0fdf4;
            color: #15803d;
            font-size: 10pt;
            height: 24px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4ade80, stop:1 #22c55e);
            border-radius: 5px;
        }

        /* === 日志区 === */
        QTextEdit {
            background-color: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            color: #166534;
            font-family: 'JetBrains Mono', Consolas, "Microsoft YaHei", monospace;
            font-size: 9pt;
            padding: 8px;
        }

        /* === 状态栏 === */
        QStatusBar { background-color: #ffffff; color: #15803d; font-size: 10pt; border-top: 1px solid #bbf7d0; }

        /* === Splitter === */
        QSplitter::handle { background-color: #bbf7d0; width: 3px; border-radius: 2px; }

        /* === 分组框 === */
        QGroupBox {
            font-weight: bold;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 18px;
            background: #ffffff;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 8px; color: #15803d; }

        /* === 滚动条 === */
        QScrollBar:vertical { background: #f0fdf4; width: 10px; border-radius: 5px; }
        QScrollBar::handle:vertical { background: #86efac; border-radius: 5px; min-height: 40px; }
        QScrollBar::handle:vertical:hover { background: #4ade80; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

        /* === 标签页 === */
        QTabWidget::pane { border: 1px solid #bbf7d0; border-radius: 8px; background: #ffffff; }
        QTabBar::tab { background: #f0fdf4; padding: 10px 20px; border: 1px solid #bbf7d0; border-bottom: none; border-radius: 6px 6px 0 0; margin-right: 2px; }
        QTabBar::tab:selected { background: #ffffff; color: #22c55e; border-bottom: 2px solid #22c55e; }
    """,
    "科技蓝": """
        /* === 全局 === */
        QMainWindow { background-color: #0c1222; }
        QDialog, QWidget { background-color: #151e32; color: #e2e8f0; font-size: 10pt; }

        /* === 菜单栏 === */
        QMenuBar { background-color: #151e32; color: #f1f5f9; border-bottom: 1px solid #1e293b; }
        QMenuBar::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38bdf8, stop:1 #0ea5e9); color: white; border-radius: 4px; }
        QMenu { background-color: #151e32; color: #f1f5f9; border: 1px solid #1e293b; border-radius: 8px; }
        QMenu::item { text-align: left; padding: 8px 24px; border-radius: 4px; margin: 2px 4px; }
        QMenu::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38bdf8, stop:1 #0ea5e9); color: white; }

        /* === 工具栏 === */
        QToolBar {
            background-color: #151e32;
            border-bottom: 1px solid #1e293b;
            spacing: 8px;
            padding: 6px 8px;
        }

        /* === 按钮（主色） === */
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38bdf8, stop:1 #0ea5e9);
            color: white;
            border: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-weight: 500;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0ea5e9, stop:1 #0284c7); }
        QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0284c7, stop:1 #0369a1); }
        QPushButton:disabled { background: #1e293b; color: #475569; }

        /* === 输入框 === */
        QLineEdit {
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 8px 12px;
            background-color: #0c1222;
            color: #e2e8f0;
        }
        QLineEdit:focus { border-color: #0ea5e9; background: #0f172a; }

        /* === 文件树 === */
        QTreeWidget {
            background-color: #151e32;
            border: 1px solid #1e293b;
            border-radius: 8px;
            color: #e2e8f0;
            outline: 0;
        }
        QTreeWidget::item { padding: 6px 8px; border-bottom: 1px solid #1e293b; }
        QTreeWidget::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(56,189,248,0.2), stop:1 rgba(14,165,233,0.2)); color: #38bdf8; border-radius: 4px; }
        QTreeWidget::item:hover { background-color: #1e293b; border-radius: 4px; }

        /* === 工作表 === */
        QTableWidget {
            background-color: #0c1222;
            alternate-background-color: #151e32;
            gridline-color: #1e293b;
            border: 1px solid #1e293b;
            border-radius: 8px;
            selection-background-color: rgba(14,165,233,0.2);
            selection-color: #e2e8f0;
        }
        QHeaderView::section {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151e32, stop:1 #0c1222);
            color: #94a3b8;
            padding: 10px 8px;
            border: none;
            border-right: 1px solid #1e293b;
            font-weight: 600;
            font-size: 9pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QHeaderView::section:hover { background: #1e293b; }

        /* === 进度条 === */
        QProgressBar {
            border: 1px solid #1e293b;
            border-radius: 6px;
            text-align: center;
            background-color: #151e32;
            color: #94a3b8;
            font-size: 10pt;
            height: 24px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #0ea5e9);
            border-radius: 5px;
        }

        /* === 日志区 === */
        QTextEdit {
            background-color: #0c1222;
            border: 1px solid #1e293b;
            border-radius: 8px;
            color: #cbd5e1;
            font-family: 'JetBrains Mono', Consolas, "Microsoft YaHei", monospace;
            font-size: 9pt;
            padding: 8px;
        }

        /* === 状态栏 === */
        QStatusBar { background-color: #151e32; color: #94a3b8; font-size: 10pt; border-top: 1px solid #1e293b; }

        /* === Splitter === */
        QSplitter::handle { background-color: #1e293b; width: 3px; border-radius: 2px; }

        /* === 分组框 === */
        QGroupBox {
            font-weight: bold;
            border: 1px solid #1e293b;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 18px;
            background: #151e32;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 8px; color: #94a3b8; }

        /* === 滚动条 === */
        QScrollBar:vertical { background: #0c1222; width: 10px; border-radius: 5px; }
        QScrollBar::handle:vertical { background: #334155; border-radius: 5px; min-height: 40px; }
        QScrollBar::handle:vertical:hover { background: #475569; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

        /* === 标签页 === */
        QTabWidget::pane { border: 1px solid #1e293b; border-radius: 8px; background: #0c1222; }
        QTabBar::tab { background: #151e32; padding: 10px 20px; border: 1px solid #1e293b; border-bottom: none; border-radius: 6px 6px 0 0; margin-right: 2px; }
        QTabBar::tab:selected { background: #0c1222; color: #38bdf8; border-bottom: 2px solid #0ea5e9; }
    """,
}

DARK_THEMES = {"暗夜黑", "科技蓝"}


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
    qss = THEMES.get(theme_name)
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
