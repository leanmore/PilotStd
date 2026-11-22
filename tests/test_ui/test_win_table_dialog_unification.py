"""Win 端表格/弹窗统一守护（DS 模块二-C）：源码内不得再构造裸 QTableWidget / QDialog。

对应 G-029「UI 变更需同步测试」：本文件是 `pilotstd/ui/**` 表格与弹窗替换的守护用例，
与 `tests/gui/test_base_table.py` / `test_base_dialog.py` 的控件单测互补
（那边测控件自身，这边测「调用点有没有漏替换」）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
UI_ROOT = ROOT / "pilotstd" / "ui"

# 只拦「构造调用」：`QTableWidget.EditTrigger`、类型标注 `parent: QDialog` 不算
CALL = re.compile(r"(?<![\w.])(QTableWidget|QDialog)\(")


def _ui_sources() -> list[Path]:
    """返回 pilotstd/ui 下所有 py 源文件（排除缓存）。"""
    return [p for p in sorted(UI_ROOT.rglob("*.py")) if "__pycache__" not in p.parts]


def test_no_raw_qtablewidget_or_qdialog_instantiation() -> None:
    """不得再用裸 QTableWidget(...) / QDialog(...) 构造；统一走 BaseTable / BaseDialog。"""
    offenders = []
    for path in _ui_sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if CALL.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:90]}")
    assert not offenders, "发现未替换的表格/弹窗构造：\n" + "\n".join(offenders)


def test_base_modules_exist_and_use_tokens() -> None:
    """BaseTable / BaseDialog 必须存在，且样式从跨端令牌产物取（禁止手写色值）。"""
    for name, cls in (("base_table.py", "BaseTable"), ("base_dialog.py", "BaseDialog")):
        module = UI_ROOT / "widgets" / name
        assert module.exists(), f"缺少 {module}"
        text = module.read_text(encoding="utf-8")
        assert f"class {cls}" in text, f"{name} 未定义 {cls}"
        assert "tokens_generated" in text, f"{cls} 必须从跨端令牌产物取样式"


def test_dialog_subclasses_keep_their_public_surface() -> None:
    """替换基类后，各弹窗的构造签名、信号、exec() 用法必须原样保留。"""
    expectations = {
        "pilotstd/ui/dialogs.py": [
            "class ConfigPageDialog(BaseDialog):",
            "class ExportFileListDialog(BaseDialog):",
            "self.setWindowTitle(title)",
            "self.resize(650, 480)",
        ],
        "pilotstd/ui/welcome_dialog.py": [
            "class WelcomeDialog(BaseDialog):",
            "self.setModal(True)",
            "self.btn_close.clicked.connect(self.accept)",
        ],
        "pilotstd/ui/pages/settings/_dialog.py": [
            "class SettingsDialog(BaseDialog):",
            "def closeEvent(self, event) -> None:",
            "self.page.stop_workers()",
        ],
        "pilotstd/ui/pages/rules_page.py": [
            "class RuleEditDialog(BaseDialog):",
            "def _on_accept(self) -> None:",
        ],
        "pilotstd/ui/pages/task_page.py": [
            "class TaskCenterDialog(BaseDialog):",
            "self.setWindowTitle(_(\"title_task_center\"))",
        ],
        "pilotstd/ui/pending_query_dialog.py": [
            "class PendingQueryDialog(BaseDialog):",
            "self.setMinimumSize(540, 320)",
        ],
    }
    for rel, snippets in expectations.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in text, f"{rel} 缺少：{snippet}"


def test_dialog_exec_semantics_use_base_dialog_enum() -> None:
    """exec() 结果比较可写 BaseDialog.DialogCode（与 QDialog.DialogCode 同一枚举），语义不变。"""
    from PyQt6.QtWidgets import QDialog

    from pilotstd.ui.widgets.base_dialog import BaseDialog

    assert BaseDialog.DialogCode is QDialog.DialogCode
    assert BaseDialog.DialogCode.Accepted == 1
    assert BaseDialog.DialogCode.Rejected == 0

    for rel in (
        "pilotstd/ui/pages/rules_page.py",
        "pilotstd/ui/main_window/parts/_query_ops.py",
        "pilotstd/ui/main_window/parts/_export_ops.py",
        "pilotstd/ui/core/handlers/_query.py",
        "pilotstd/ui/core/handlers/_cleanup.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "BaseDialog.DialogCode." in text, f"{rel} 未改用 BaseDialog.DialogCode"


def test_work_table_is_base_table() -> None:
    """工作区表格与任务中心表格必须实例化 BaseTable（不是裸 QTableWidget）。"""
    setup = (UI_ROOT / "main_window" / "parts" / "_ui_setup_ops.py").read_text(encoding="utf-8")
    task = (UI_ROOT / "pages" / "task_page.py").read_text(encoding="utf-8")
    assert "self.work_table = BaseTable()" in setup
    assert "self.task_table = BaseTable()" in task


def test_table_column_behavior_preserved() -> None:
    """替换后必须保留列数/列宽/排序/只读/选择行为（不能只换类名丢语义）。"""
    setup = (UI_ROOT / "main_window" / "parts" / "_ui_setup_ops.py").read_text(encoding="utf-8")
    for snippet in (
        "self.work_table.setAlternatingRowColors(True)",
        "self.work_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)",
        "self.work_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)",
        "self.work_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)",
        "self.work_table.setSortingEnabled(True)",
    ):
        assert snippet in setup, f"工作区表格丢失语义：{snippet}"


def test_generated_tokens_have_table_and_dialog_tokens() -> None:
    """跨端令牌必须提供表格/弹窗所需键，否则 BaseTable/BaseDialog 会在运行时报错。"""
    import importlib.util

    path = ROOT / "pilotstd" / "ui" / "tokens_generated.py"
    spec = importlib.util.spec_from_file_location("_tokens_for_table_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in (
        "ds_radius_md",
        "ds_radius_lg",
        "space_9",
        "space_10",
        "space_18",
        "space_20",
        "size_20",
        "font_size_11",
        "font_size_13",
        "font_weight_semibold",
        "line_height_normal",
    ):
        assert name in module.TOKENS, f"缺少尺度令牌 {name}"

    assert set(module.THEME_COLORS) == {"light", "dark", "green", "blue"}
    for theme, colors in module.THEME_COLORS.items():
        for key in ("surface", "surfaceRaised", "text", "border", "borderLight", "selected", "textHeading"):
            assert key in colors, f"主题 {theme} 缺少颜色键 {key}"
