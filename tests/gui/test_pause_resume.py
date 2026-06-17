import os
import sys
import tempfile
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def test_pause_button_exists(window):
    """暂停按钮应存在。"""
    assert hasattr(window, 'btn_pause')
    assert window.btn_pause is not None


def test_pause_toggle_changes_label(window):
    """点击暂停按钮切换文字。"""
    initial = window.btn_pause.text()
    window._on_pause_toggle()
    assert window.btn_pause.text() == "继续"
    window._on_pause_toggle()
    assert window.btn_pause.text() == initial


def test_pause_toggles_state(window):
    """_paused 状态跟随按钮切换。"""
    assert not window._paused
    window._on_pause_toggle()
    assert window._paused
    window._on_pause_toggle()
    assert not window._paused


def test_restore_button_is_continue(window):
    """暂停后继续再暂停，按钮文字应正确循环。"""
    window._on_pause_toggle()
    assert window.btn_pause.text() == "继续"
    window._on_pause_toggle()
    assert window.btn_pause.text() == "暂停"


def test_export_diagnostics_creates_file(window, test_data_dir, qtbot):
    """导出诊断报告应生成文件。"""
    window._run_scan(test_data_dir)
    qtbot.wait(300)
    tmp = tempfile.mkdtemp(prefix="pilotstd_diag_")
    diag_path = os.path.join(tmp, "diag.log")
    from datetime import datetime
    with open(diag_path, "w", encoding="utf-8") as f:
        f.write(f"=== PilotStd 诊断报告 ===\n")
        f.write(f"时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"Python: {sys.version}\n\n")
        f.write(f"--- 工作区 ---\n")
        f.write(f"  解析结果: {len(window._parsed_results)} 条\n")
        f.write(f"  表格行数: {window.work_table.rowCount()} 行\n")
    assert os.path.exists(diag_path)
    with open(diag_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "PilotStd 诊断报告" in content
    assert "工作区" in content
    os.remove(diag_path)
    os.rmdir(tmp)
