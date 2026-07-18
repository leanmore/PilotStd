# tests/gui/test_coverage_queries.py
# 覆盖 _query_ops.py 未覆盖行：25-51, 55-59, 71-112, 122, 127, 131-134, 139

import csv
import os
import tempfile
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt

# ═══════════════════════════════════════════════════════════
# _on_query_result_ready 覆盖 25-51
# ═══════════════════════════════════════════════════════════


def test_on_query_result_ready_populates_table(window, qtbot):
    """覆盖 25-51：_on_query_result_ready 用查询结果更新表格行各个列。"""
    window._clear_table()

    # 创建 parsed 对象并加入 _parsed_results
    parsed = MagicMock()
    parsed.std_name = "测试标准名称"
    window._parsed_results = [parsed]

    # 在 work_table 中添加一行（10列）
    from pilotstd.ui.workers._common import RowUpdate

    window._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="扫描完成", total=1))

    # 创建 mock result 对象，包含所有需要的属性
    mock_result = MagicMock()
    mock_result.standard_name = "网站返回名称"
    mock_result.source_site = "test_site"
    mock_result.status = "现行"
    mock_result.replaces = "GB/T 1-1990"
    mock_result.publish_date = "2020-01-01"
    mock_result.implementation_date = "2020-06-01"
    mock_result.responsible_dept = "国家标准化管理委员会"
    mock_result.is_adopted = False
    mock_result.is_downloadable = True

    window._on_query_result_ready(0, mock_result)

    table = window.work_table
    # 验证表格各列被更新
    assert table.item(0, 1).text() == "已查询(test_site)"
    assert table.item(0, 3).text() == "网站返回名称"
    assert table.item(0, 4).text() == "现行"
    assert table.item(0, 5).text() == "GB/T 1-1990"


def test_on_query_result_ready_website_no_category(window, qtbot):
    """覆盖 29-32："网站无此分类" 字段替换为空字符串。"""
    window._clear_table()
    parsed = MagicMock()
    parsed.std_name = "测试"
    window._parsed_results = [parsed]

    from pilotstd.ui.workers._common import RowUpdate

    window._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="扫描完成", total=1))

    mock_result = MagicMock()
    mock_result.standard_name = "网站名称"
    mock_result.source_site = "test"
    mock_result.status = "现行"
    mock_result.replaces = "网站无此分类"
    mock_result.publish_date = "网站无此分类"
    mock_result.implementation_date = "网站无此分类"
    mock_result.responsible_dept = "网站无此分类"
    mock_result.is_adopted = False
    mock_result.is_downloadable = True

    window._on_query_result_ready(0, mock_result)
    table = window.work_table
    assert table.item(0, 5).text() == ""  # replaces 清空
    assert table.item(0, 6).text() == ""  # publish_date 清空


def test_on_query_result_ready_status_colors(window, qtbot):
    """覆盖 42-51：不同状态应设置不同前景色，非可下载标准黄色。"""
    window._clear_table()
    parsed = MagicMock()
    parsed.std_name = "测试"
    window._parsed_results = [parsed]

    from pilotstd.ui.workers._common import RowUpdate

    window._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="扫描完成", total=1))

    # 测试 "现行" → darkGreen
    mock_result = MagicMock()
    mock_result.standard_name = "标"
    mock_result.source_site = "s"
    mock_result.status = "现行"
    mock_result.replaces = ""
    mock_result.publish_date = ""
    mock_result.implementation_date = ""
    mock_result.responsible_dept = ""
    mock_result.is_adopted = False
    mock_result.is_downloadable = True
    window._on_query_result_ready(0, mock_result)
    assert window.work_table.item(0, 4).foreground().color() == Qt.GlobalColor.darkGreen

    # 测试 "废止" → red
    mock_result.status = "废止"
    mock_result.replaces = ""
    window._on_query_result_ready(0, mock_result)
    assert window.work_table.item(0, 4).foreground().color() == Qt.GlobalColor.red

    # 测试 "即将实施" → blue
    mock_result.status = "即将实施"
    mock_result.replaces = ""
    window._on_query_result_ready(0, mock_result)
    assert window.work_table.item(0, 4).foreground().color() == Qt.GlobalColor.blue

    # 测试 "待确认" → darkYellow
    mock_result.status = "待确认"
    mock_result.replaces = ""
    window._on_query_result_ready(0, mock_result)
    assert window.work_table.item(0, 4).foreground().color() == Qt.GlobalColor.darkYellow

    # 测试非可下载且非终止状态 → darkYellow（覆盖 50-51）
    mock_result.status = "现行"
    mock_result.is_downloadable = False
    mock_result.replaces = ""
    window._on_query_result_ready(0, mock_result)
    assert window.work_table.item(0, 4).foreground().color() == Qt.GlobalColor.darkYellow


# ═══════════════════════════════════════════════════════════
# _on_pending_query 异常分支 覆盖 55-59
# ═══════════════════════════════════════════════════════════


def test_on_pending_query_exception(window, qtbot):
    """覆盖 55-59：_do_pending_query 抛异常时弹出 critical。"""
    with patch.object(window, "_do_pending_query", side_effect=ValueError("test error")):
        with patch("pilotstd.ui.main_window.parts._query_ops.QMessageBox.critical") as mock_critical:
            window._on_pending_query()
            mock_critical.assert_called_once()


# ═══════════════════════════════════════════════════════════
# _do_pending_query 管理器未就绪 覆盖 63-64
# ═══════════════════════════════════════════════════════════


def test_on_pending_query_mgr_not_ready(window, qtbot):
    """覆盖 63-64：_mgr_ready=False 时 _do_pending_query 提前返回。"""
    window._mgr_ready = False
    window._do_pending_query()  # 不抛异常，静默返回


# ═══════════════════════════════════════════════════════════
# _do_pending_query 工作区非空 覆盖 65-67
# ═══════════════════════════════════════════════════════════


def test_on_pending_query_workspace_not_empty(window, qtbot):
    """覆盖 65-67：_parsed_results 非空时弹出警告。"""
    window._mgr_ready = True  # 已在 mock_main_window fixture 中设为 False，需要覆盖
    window._parsed_results = [MagicMock()]
    with patch("pilotstd.ui.main_window.parts._query_ops.QMessageBox.warning") as mock_warn:
        window._do_pending_query()
        mock_warn.assert_called_once()


# ═══════════════════════════════════════════════════════════
# _do_pending_query 取消选择文件 覆盖 69-70 (隐式)
# ═══════════════════════════════════════════════════════════


def test_on_pending_query_cancel_file_dialog(window, qtbot):
    """用户取消文件选择对话框时提前返回。"""
    window._mgr_ready = True
    window._parsed_results = []
    with patch("pilotstd.ui.main_window.parts._query_ops.QFileDialog.getOpenFileName", return_value=("", "")):
        window._do_pending_query()
    # 不抛异常


# ═══════════════════════════════════════════════════════════
# _do_pending_query CSV 无标准号 覆盖 72-74
# ═══════════════════════════════════════════════════════════


def test_on_pending_query_csv_no_standards(window, qtbot):
    """CSV 解析后 parsed_list 为空时弹出警告。"""
    window._mgr_ready = True
    window._parsed_results = []

    # 用空 CSV 文件让 _parse_pending_csv 返回空列表
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])

        with patch("pilotstd.ui.main_window.parts._query_ops.QFileDialog.getOpenFileName", return_value=(tmp, "")):
            with patch("pilotstd.ui.main_window.parts._query_ops.QMessageBox.warning") as mock_warn:
                window._do_pending_query()
                mock_warn.assert_called_once()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ═══════════════════════════════════════════════════════════
# _parse_pending_csv 空文件 覆盖 121-122
# ═══════════════════════════════════════════════════════════


def test_parse_pending_csv_empty(window, qtbot):
    """覆盖 121-122：只有表头的 CSV 返回两个空列表。"""
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
        parsed_list, failed_names = window._parse_pending_csv(tmp)
        assert parsed_list == []
        assert failed_names == []
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ═══════════════════════════════════════════════════════════
# _parse_pending_csv 解析异常 覆盖 131-134
# ═══════════════════════════════════════════════════════════


def test_parse_pending_csv_with_invalid_std(window, qtbot):
    """覆盖 131-134：parse_standard_number 抛异常时标准号进入 failed_names。"""
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
            w.writerow(["INVALID-123", "无效标准"])
        with patch.object(window._mgr, "parse_standard_number", side_effect=ValueError("无法解析")):
            parsed_list, failed_names = window._parse_pending_csv(tmp)
        assert parsed_list == []
        assert "INVALID-123" in failed_names
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ═══════════════════════════════════════════════════════════
# _parse_pending_csv parse 返回 None 覆盖 138-139
# ═══════════════════════════════════════════════════════════


def test_parse_pending_csv_parse_none(window, qtbot):
    """覆盖 138-139：parse_standard_number 返回 None 时标准号进入 failed_names。"""
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
            w.writerow(["GB/T-none-2020", ""])
        with patch.object(window._mgr, "parse_standard_number", return_value=None):
            parsed_list, failed_names = window._parse_pending_csv(tmp)
        assert parsed_list == []
        assert "GB/T-none-2020" in failed_names
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ═══════════════════════════════════════════════════════════
# _parse_pending_csv 正常解析 覆盖 124-127 (表头跳过)
# ═══════════════════════════════════════════════════════════


def test_parse_pending_csv_skip_header(window, qtbot):
    """覆盖 124-127：CSV 表头被跳过，有效行被解析。"""
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
            w.writerow(["GB/T 1-2020", "基础规范"])
        # 使用真实的 parse_standard_number（mock 环境下已初始化 parser）
        parsed_list, failed_names = window._parse_pending_csv(tmp)
        # 在 mock 环境下 parser 可能成功或失败，但表头行不应出现在结果中
        assert isinstance(parsed_list, list)
        assert isinstance(failed_names, list)
        # 总处理行数应为1（只处理了数据行，表头被跳过）
        assert len(parsed_list) + len(failed_names) == 1
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_parse_pending_csv_skip_empty_row(window, qtbot):
    """覆盖 126-127：空行和首列为空的行被跳过。"""
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
            w.writerow([])  # 空行
            w.writerow(["", ""])  # 首列为空
            w.writerow(["GB/T 1-2020", "有效"])
        parsed_list, failed_names = window._parse_pending_csv(tmp)
        assert len(parsed_list) + len(failed_names) == 1  # 只有第三行被处理
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
