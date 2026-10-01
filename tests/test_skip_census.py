"""tests/test_skip_census.py — 跳过普查工具的受控测试（T-20 / R11-4，2026-09-27）。

工具的价值在于「口径分离」：静态调用点 ≠ 运行期跳过。这里用内嵌样本锁定解析与分类行为，
并用**真实仓库**校验静态口径计数与 R11-4 实测一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import skip_census as sc  # noqa: E402

SAMPLE = """
SKIPPED [1] tests/test_e2e_adapters.py:40: 外部 API 行为不稳定，std_gov 搜索结果可能变更
SKIPPED [1] tests/test_scanner.py:494: 系统不支持此长度文件名
SKIPPED [2] tests/unit/query/engine/test_batch_dispatch.py:125: 需要 ThreadPoolExecutor + 真实组件
SKIPPED [1] tests/test_ocr_fallback.py:87: 缺少可用 OCR provider
SKIPPED [1] tests/test_cssn.py:27: Fixture not found
SKIPPED [1] tests/test_mock_pipeline.py:37: Mock适配器连续20次未返回结果（概率极低）
1 failed, 10 passed, 7 skipped in 1.00s
"""


def test_classify_covers_all_documented_categories() -> None:
    assert sc.classify("Fixture not found; run Task 0 first.") == "fixture"
    assert sc.classify("系统不支持此长度文件名") == "platform"
    assert sc.classify("hbba 无响应") == "network"
    assert sc.classify("依赖 HTTP 请求（requests.get）") == "network"
    assert sc.classify("需要 ThreadPoolExecutor + 真实组件") == "dependency"
    assert sc.classify("Mock适配器连续20次未返回结果（概率极低）") == "random"
    assert sc.classify("") == "other"


def test_parse_rs_report_expands_counts_and_classifies() -> None:
    records = sc.parse_rs_report(SAMPLE)
    assert len(records) == 7  # 6 行，其中一行 `[2]` 展开
    by_category = sc.summarize(records)["by_category"]
    assert by_category["network"] == 1  # e2e:40（外部 API 不稳定）
    assert by_category["platform"] == 1  # scanner:494（系统不支持此长度文件名）
    assert by_category["dependency"] == 3  # ThreadPoolExecutor ×2 + OCR provider ×1
    assert by_category["fixture"] == 1
    assert by_category["random"] == 1


def test_parse_rs_report_ignores_non_skip_lines() -> None:
    assert sc.parse_rs_report("1 failed, 10 passed\nno skips here\n") == []


def test_summarize_reports_per_file_counts() -> None:
    summary = sc.summarize(sc.parse_rs_report(SAMPLE))
    assert summary["total"] == 7
    assert summary["by_file"]["tests/unit/query/engine/test_batch_dispatch.py"] == 2


def test_static_inventory_matches_r11_4_measurement() -> None:
    """静态口径：`self.skipTest` 60 处（T-20 原登记值）——运行期实测远小于此，故两者必须分开统计。"""
    counts = sc.static_inventory()["counts"]
    assert counts["skipTest"] == 60, f"self.skipTest 静态调用点由 60 变为 {counts['skipTest']}；请同步主簿 T-20"
    # T-29 / R13-1：8 处永久 skip 转为真实用例；T-33 / R13-2：最后 2 处 GUI 空壳占位删除。
    # 故 tests/ 下**永久 skip 应为 0**——任何新增都必须在此登记并同步主簿。
    assert counts["mark_skip"] == 0, (
        f"永久 skip 标记应为 0，实测 {counts['mark_skip']}；"
        "新增永久 skip 需同步主簿并说明理由"
    )


def test_t29_files_have_no_permanent_skip_and_no_stub_body() -> None:
    """T-29（R13-1）：两个曾含 4 处永久 skip 的文件必须①零永久 skip、②无用例是空壳 `pass`。"""
    import ast

    inventory = sc.static_inventory()
    targets = (
        "tests/unit/manager/facade/test_query_subsystem_snapshot.py",
        "tests/unit/query/engine/test_batch_dispatch.py",
    )
    for rel in targets:
        hits = [site for site in inventory["sites"]["mark_skip"] if site.startswith(rel)]
        assert hits == [], f"{rel} 不应再有永久 skip：{hits}"

        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        stubs = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_")
            and all(isinstance(stmt, ast.Pass) for stmt in node.body)
        ]
        assert stubs == [], f"{rel} 存在空壳用例（def test_x(): pass）：{stubs}"

