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
    assert counts["mark_skip"] >= 8, "永久 skip 标记数不应少于 R11-4 实测的 8 处"
