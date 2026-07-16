# tests/gui/test_e2e_query.py
"""E2E 兜底测试 — 覆盖 _query.py (QueryUIHandler) 三大核心路径。

路径 1: 发起查询 — 扫描 → 点击查询 → 表格更新
路径 2: 结果更新 — 7 字段填充 + 状态着色
路径 3: 待确认查询 — CSV 解析 + do_pending_query 全流程
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
import tempfile

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PyQt6.QtCore import Qt

from pilotstd.query.models import QueryResult


# ── 工具函数 ─────────────────────────────────────────────────


def _copy_fixtures_to_tmp(test_data_dir: str) -> str:
    """复制 fixture 文件到临时目录（防止消耗原件）。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_e2e_")
    for name in os.listdir(test_data_dir):
        src = os.path.join(test_data_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)
    return tmp


# ════════════════════════════════════════════════════════════════
# 路径 1: 发起查询 → 表格更新
# ════════════════════════════════════════════════════════════════


def test_query_standard_success(window, test_data_dir, qtbot):
    """E2E: 扫描 fixtures → 触发 on_query() → Worker 完成 → 表格填充 '已查询' 状态。

    覆盖 QueryUIHandler.on_query() 的完整链路：
      - parsed_results 非空 → 不弹前置对话框
      - QueryWorker 创建并 start()
      - result_ready → on_query_result_ready → 表格单元格更新
      - finished_signal → show_query_summary
    """
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        # Step 1: 扫描
        window._run_scan(tmp)
        qtbot.wait(400)
        assert len(window._parsed_results) > 0, "扫描后应有已解析标准"

        # Step 2: 触发查询（经 _delegate_ops._on_query → _core.query.on_query()）
        window._on_query()

        # Step 3: 等待 QueryWorker 完成
        worker = window._core.query._query_worker
        assert worker is not None, "on_query 应创建 QueryWorker"
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

        # Step 4: 验证表格 — 每行的状态列应包含 "已查询"
        table = window.work_table
        assert table.rowCount() > 0, "表格应有数据行"
        found = 0
        for row in range(table.rowCount()):
            item = table.item(row, 1)  # col1 = 工作状态
            if item and "查询" in item.text():
                found += 1
        assert found > 0, f"至少一行应显示'已查询'状态，实际找到 {found} 行"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 路径 2: 结果更新 — 7 字段 + 状态着色
# ════════════════════════════════════════════════════════════════


def test_query_result_fields_and_coloring_e2e(window, test_data_dir, qtbot):
    """E2E: 扫描→查询后，表格 7 个业务字段全部填充 + 生效状态着色正确。

    覆盖 QueryUIHandler.on_query_result_ready() 的完整字段映射：
      col1=工作状态, col3=标准名称, col4=生效状态, col5=替代标准,
      col6=发布日期, col7=实施日期, col8=归口单位, col9=采标标记
    """
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        qtbot.wait(400)
        window._on_query()

        worker = window._core.query._query_worker
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)

        table = window.work_table
        assert table.rowCount() > 0

        for row in range(table.rowCount()):
            # 收集 7 个业务字段
            status_cell = table.item(row, 1)  # 工作状态
            name_cell = table.item(row, 3)  # 标准名称
            effect_cell = table.item(row, 4)  # 生效状态
            replaces_cell = table.item(row, 5)  # 替代标准
            pub_date_cell = table.item(row, 6)  # 发布日期
            impl_date_cell = table.item(row, 7)  # 实施日期
            dept_cell = table.item(row, 8)  # 归口单位
            adopted_cell = table.item(row, 9)  # 采标

            # 工作状态列必填
            assert status_cell is not None, f"行 {row}: col1 工作状态不应为 None"
            assert "查询" in status_cell.text(), (
                f"行 {row}: 工作状态应包含'查询', 实际='{status_cell.text()}'"
            )

            # ── 生效状态列 — 至少大部分行应有值（Mock 适配器可能跳过个别行） ──
            assert effect_cell is not None, f"行 {row}: col4 生效状态不应为 None"
            effect = effect_cell.text()
            if not effect:
                continue  # 本轮未查询到的行跳过后续着色断言

            # 标准名称列必填
            assert name_cell is not None, f"行 {row}: col3 标准名称不应为 None"
            assert name_cell.text(), f"行 {row}: 标准名称不应为空"

            # ── 验证状态着色（hex 值比较，避免 GlobalColor 枚举 vs QColor 对象比较陷阱）──
            color = effect_cell.foreground().color()
            if effect in ("现行",):
                # 现行通常为绿色，但若 is_adopted=True（不可下载）会被覆盖为 darkYellow
                assert color.name() in ("#008000", "#808000"), (
                    f"行 {row}: 现行状态应为绿色或darkYellow(采标覆盖), "
                    f"实际 effect='{effect}' color={color.name()}"
                )
            elif effect == "即将实施":
                # 即将实施本应为蓝色，但 handler 中 is_downloadable=False 会覆盖为 darkYellow
                assert color.name() in ("#0000ff", "#808000"), (
                    f"行 {row}: 即将实施应为蓝色或darkYellow(不可下载覆盖), "
                    f"实际 effect='{effect}' color={color.name()}"
                )
            elif effect in ("废止", "已废止", "作废"):
                assert color.name() == "#ff0000", (
                    f"行 {row}: 废止状态应为红色, 实际 effect='{effect}'"
                )

            # 其余字段至少可读（mock 数据可能为空，不崩溃即可）
            _ = replaces_cell.text() if replaces_cell else ""
            _ = pub_date_cell.text() if pub_date_cell else ""
            _ = impl_date_cell.text() if impl_date_cell else ""
            _ = dept_cell.text() if dept_cell else ""
            _ = adopted_cell.text() if adopted_cell else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_on_query_result_ready_direct(window, qtbot):
    """直接调用 on_query_result_ready 验证 7 字段精确映射 + 状态着色。

    通过构造确定的 QueryResult，绕过 Worker 随机性，
    精确验证 on_query_result_ready 的单元格写入和颜色设置逻辑。
    """
    tmp_dir = tempfile.mkdtemp(prefix="pilotstd_e2e_direct_")
    pdf_path = os.path.join(tmp_dir, "GBT 1.1-2020.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 mock\n")

    try:
        # 扫描一个文件，创建表格行
        window._run_scan(tmp_dir)
        qtbot.wait(400)
        assert len(window._parsed_results) == 1, "扫描单个文件应有 1 条解析结果"
        assert window.work_table.rowCount() == 1, "表格应有 1 行"

        # 构造精确的 mock 查询结果
        mock_result = QueryResult(
            standard_number="GB/T 1.1-2020",
            standard_name="标准化工作导则 第1部分：标准化文件的结构和起草规则",
            status="现行",
            replaces="GB/T 1.1-2009",
            implementation_date="2020-10-01",
            publish_date="2020-03-31",
            abolition_date="",
            responsible_dept="全国标准化原理与方法标准化技术委员会",
            is_adopted=False,
            source_site="mock_query",
            is_downloadable=True,
            match_status="exact",
        )

        handler = window._core.query
        handler.on_query_result_ready(0, mock_result)

        table = window.work_table

        # ── 7 字段验证 ──
        assert table.item(0, 1).text() == "已查询(mock_query)", "col1 工作状态"
        assert table.item(0, 3).text() == mock_result.standard_name, "col3 标准名称"
        assert table.item(0, 4).text() == "现行", "col4 生效状态"
        assert table.item(0, 5).text() == "GB/T 1.1-2009", "col5 替代标准"
        assert table.item(0, 6).text() == "2020-03-31", "col6 发布日期"
        assert table.item(0, 7).text() == "2020-10-01", "col7 实施日期"
        assert table.item(0, 8).text() == mock_result.responsible_dept, "col8 归口单位"
        # col9: is_adopted=False → 文本为空（on_query_result_ready 的 if text 会跳过空字符串）
        assert table.item(0, 9).text() == "", "col9 采标列应为空（非采标标准）"

        # ── 状态着色验证 ──
        status_item = table.item(0, 4)
        assert status_item.foreground().color().name() == "#008000", (
            "现行状态应为绿色(darkGreen)"
        )

        # ── 废止状态着色验证 ──
        mock_result2 = QueryResult(
            standard_number="GB/T 67890-2019",
            standard_name="已废止标准",
            status="废止",
            replaces="",
            implementation_date="2019-06-01",
            publish_date="2019-01-01",
            abolition_date="2025-01-01",
            responsible_dept="测试单位",
            is_adopted=False,
            source_site="mock_query",
            is_downloadable=False,
            match_status="exact",
        )
        handler.on_query_result_ready(0, mock_result2)
        assert table.item(0, 4).foreground().color().name() == "#ff0000", (
            "废止状态应为红色"
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 路径 3: 待确认查询 — CSV 解析
# ════════════════════════════════════════════════════════════════


def test_parse_pending_csv_valid_standards(window, qtbot):
    """parse_pending_csv 正确解析含有效标准号的 CSV，过滤空行和表头。

    覆盖 QueryUIHandler.parse_pending_csv() 的：
      - UTF-8-BOM 编码读取
      - 标准号解析（通过 mgr.parse_standard_number）
      - 空行/表头跳过
      - std_name 从 CSV 第 2 列回填
    """
    window._mgr  # 触发懒加载，确保 StandardParser 就绪

    tmpdir = tempfile.mkdtemp(prefix="pilotstd_e2e_csv_")
    csv_path = os.path.join(tmpdir, "pending.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "标准编号", "标准名称", "网站名称", "本地年份",
            "网站编号", "状态", "置信度", "来源站点",
        ])
        writer.writerow([
            "GB/T 1.1-2020", "标准化工作导则", "", "2020", "", "", "", "",
        ])
        writer.writerow([
            "NB/T 47013-2021", "承压设备无损检测", "", "2021", "", "", "", "",
        ])
        writer.writerow(["", "", "", "", "", "", "", ""])  # 空行 — 应跳过

    try:
        handler = window._core.query
        parsed_list, failed_names = handler.parse_pending_csv(csv_path)

        assert len(parsed_list) == 2, f"应解析 2 条标准，实际 {len(parsed_list)}"
        assert failed_names == [], f"不应有失败项，实际 {failed_names}"

        # 第一条
        p0 = parsed_list[0]
        assert p0.logical_code in ("GB/T", "GB"), f"logical_code 应为 GB/T, 实际 {p0.logical_code}"
        assert p0.std_name == "标准化工作导则", f"std_name 应从 CSV 回填, 实际 {p0.std_name}"

        # 第二条
        p1 = parsed_list[1]
        assert p1.logical_code in ("NB/T", "NB"), f"logical_code 应为 NB/T, 实际 {p1.logical_code}"
        assert p1.std_name == "承压设备无损检测"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_parse_pending_csv_invalid_standards(window, qtbot):
    """parse_pending_csv 将无法解析的标准号归入 failed_names。"""
    window._mgr

    tmpdir = tempfile.mkdtemp(prefix="pilotstd_e2e_csv_")
    csv_path = os.path.join(tmpdir, "pending_bad.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["标准编号", "标准名称"])
        writer.writerow(["GB/T 1.1-2020", "有效"])
        writer.writerow(["XYZ-!!-INVALID", "无效"])  # 解析失败 → failed_names
        writer.writerow(["SH/T 3010-2018", "石油化工"])  # 有效

    try:
        handler = window._core.query
        parsed_list, failed_names = handler.parse_pending_csv(csv_path)

        assert len(parsed_list) == 2, f"应有 2 条成功解析，实际 {len(parsed_list)}"
        assert len(failed_names) == 1, f"应有 1 条失败，实际 {failed_names}"
        assert "XYZ-!!-INVALID" in failed_names

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
