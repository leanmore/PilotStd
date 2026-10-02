# tests/test_gate_coverage_summary.py
# L-23：锁定三个通知门禁的 [覆盖摘要] 格式契约，防止"PASS 掩盖空洞"回归
"""三个通知门禁（G-043 / G-044 / G-045）的 `[覆盖摘要]` 格式契约。

设计意图：门禁的 `PASS` 只说明"已检查项通过"，不说明**豁免了什么、没检查什么**。
本测试锁定该摘要的存在性、段结构与关键内容，使"PASS 掩盖空洞"的回归无法通过 CI：

1. 三脚本均须打印 `[覆盖摘要]`，且**必有**四个段标签（范围 / 检查项 / 检查口径 /
   未覆盖说明）；
2. `豁免明细` 是**条件段**——有豁免条目才打印（G-043 有 7 项，故 5 段全出；
   G-044/G-045 无豁免条目，故 4 段）——这是省略空段，不是结构差异；
3. 每处摘要的 `未覆盖说明` 都不得为空（不得只声明通过而不声明未覆盖范围）；
4. 三处段标签的**名称、缩进、顺序**必须逐字一致（防止各自漂移）。

实现说明：以子进程调用脚本并解析 stdout，而非导入其内部函数——门禁的对外契约是
"进程退出码 + 标准输出"，测试须验证该契约本身。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 三处通知门禁（与 docs/governance/notification_coverage.md §五 的门禁表一致）
GATES = (
    "check_sensitive_endpoint_audit.py",  # G-043
    "check_terminology.py",  # G-044
    "audit_notification_coverage.py",  # G-045
)

MARKER = "[覆盖摘要]"
# 规范顺序（与 scripts/_gate_coverage_summary.py 模块 docstring 逐字一致）。
# `豁免明细` 与 `跟踪项明细` 是**同一段的两种标题**（由 exemptions_label 区分为
# "豁免"或"跟踪"语义），故按规范顺序并列在第 4 位。
ALL_SECTIONS = ("范围", "检查项", "检查口径", "豁免明细", "跟踪项明细", "未覆盖说明")
# 必有段：三处门禁都必须出现
REQUIRED_SECTIONS = ("范围", "检查项", "检查口径", "未覆盖说明")
# 第 4 段（豁免/跟踪明细）的标题，按门禁语义区分
DETAIL_LABELS = {
    "check_sensitive_endpoint_audit.py": "豁免明细",
    "check_terminology.py": "豁免明细",
    "audit_notification_coverage.py": "跟踪项明细",
}


def _run_gate(script: str) -> str:
    """运行门禁脚本，返回其 stdout + stderr（三脚本当前均 PASS，退出码应为 0）。"""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=180,
    )
    assert result.returncode == 0, f"{script} 退出码 {result.returncode}（应 0）：{result.stdout[-400:]}"
    return result.stdout + result.stderr


def _summary_block(output: str) -> str:
    """截取 `[覆盖摘要]` 到其后首个空行为止的文本块（= 完整摘要）。"""
    lines = output.splitlines()
    start = next((i for i, line in enumerate(lines) if MARKER in line), None)
    assert start is not None, f"输出缺少 {MARKER}"
    block: list[str] = []
    for line in lines[start:]:
        if block and not line.strip():
            break
        block.append(line)
    return "\n".join(block)


def _section_items(block: str, label: str) -> list[str]:
    """返回指定段（形如 `  豁免明细:`）下的全部 `    - ` 子项。

    只取该段自己的子项：`检查口径` 段也用同样的 `    - ` 前缀，若整体扫描会把
    口径子项误计入明细条目数。
    """
    lines = block.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == f"{label}:"), None)
    if start is None:
        return []
    items: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("    - "):
            items.append(line)
        elif line.strip():
            break  # 进入下一段
    return items


@pytest.mark.parametrize("script", GATES)
def test_gate_prints_coverage_summary_with_required_sections(script: str) -> None:
    """每个门禁都须打印摘要，且包含全部**必有**段标签。"""
    block = _summary_block(_run_gate(script))
    for section in REQUIRED_SECTIONS:
        assert re.search(rf"^  {section}:", block, re.M), f"{script} 缺少段「{section}」：\n{block}"


@pytest.mark.parametrize("script", GATES)
def test_uncovered_section_is_non_empty(script: str) -> None:
    """`未覆盖说明` 不得为空——这是 L-23 的核心价值（显式声明不检查什么）。"""
    block = _summary_block(_run_gate(script))
    match = re.search(r"^  未覆盖说明: (.+)$", block, re.M)
    assert match is not None, f"{script} 的未覆盖说明段格式异常：\n{block}"
    # 去掉固定前缀「未覆盖 —— 」后仍须有实质内容
    body = match.group(1).replace("未覆盖 —— ", "").strip()
    assert len(body) >= 20, f"{script} 的未覆盖说明过短（{body!r}）"


@pytest.mark.parametrize("script", GATES)
def test_section_labels_and_indent_are_identical(script: str) -> None:
    """段标签的名称、缩进、顺序必须与规范完全一致（防各自漂移）。

    第 4 段按 `DETAIL_LABELS` 取该门禁应有的标题（豁免明细 / 跟踪项明细），
    其余段的名称与顺序在四处（公共函数 + 三处调用）必须逐字相同。
    """
    block = _summary_block(_run_gate(script))
    detail = DETAIL_LABELS[script]
    # 该门禁应出现的段标签（按规范顺序）
    expected = [s for s in ALL_SECTIONS if s != "豁免明细" or detail == "豁免明细"]
    expected = [s for s in expected if s != "跟踪项明细" or detail == "跟踪项明细"]
    found = [s for s in expected if re.search(rf"^  {s}:", block, re.M)]
    assert found == expected, f"{script} 段标签/顺序不符：期望 {expected}，实际 {found}"
    assert found[0] == "范围" and found[1] == "检查项", f"{script} 前两段应为 范围/检查项：{found}"
    assert found[-1] == "未覆盖说明", f"{script} 末段应为 未覆盖说明：{found}"
    assert detail in found, f"{script} 缺少第 4 段「{detail}」：{found}"


def test_exempt_detail_lists_actual_items() -> None:
    """`豁免/跟踪明细` 段须存在并**逐条列出实际名单**，而非只给计数。

    L-23 的核心是"PASS 不得掩盖空洞"：只显示"豁免 26"看不出豁免了什么。三处门禁的
    豁免/跟踪数据源**都是可枚举名单**（G-043 待接入路由 7 项、G-044 豁免键 16 + 豁免词
    10、G-045 未登记事件 38 项），故三处都必须打印明细段，且条目数与 `检查项` 行的
    豁免计数一致。段标题按语义区分：G-045 用「跟踪项明细」，其余用「豁免明细」。
    """
    labels = DETAIL_LABELS
    for script, label in labels.items():
        block = _summary_block(_run_gate(script))
        section = re.search(rf"^  {label}:$", block, re.M)
        assert section is not None, f"{script} 缺少「{label}」段（豁免计数 > 0 却无名单）：\n{block}"
        # 明细条目数须等于 `检查项` 行声明的豁免计数
        exempted = re.search(r"豁免 (\d+)", block)
        assert exempted is not None, f"{script} 检查项行缺少豁免计数：\n{block}"
        expected = int(exempted.group(1))
        items = _section_items(block, label)
        assert len(items) == expected, (
            f"{script} 「{label}」条目数 {len(items)} != 豁免计数 {expected}（名单与计数不一致）"
        )
        assert expected > 0, f"{script} 的豁免计数应为正数：{expected}"


def test_g044_declares_three_layer_scope() -> None:
    """G-044 须显式声明三层检查的不同覆盖范围（防被误读为全量校验）。"""
    block = _summary_block(_run_gate("check_terminology.py"))
    for keyword in ("三语存在性", "禁用词", "术语三语值与表严格相等"):
        assert keyword in block, f"G-044 摘要缺少口径「{keyword}」：\n{block}"
    # 「严格相等」仅覆盖登记键——该差异是 B-1 的核心，必须出现在摘要中
    match = re.search(r"术语三语值与表严格相等 -> (\d+) 键", block)
    assert match is not None, f"G-044 未给出严格相等检测的键数：\n{block}"
    assert int(match.group(1)) < 100, "严格相等检测应只覆盖登记键（远少于作用域内 221 键）"


def test_g045_declares_unchecked_fields_and_desktop_toast() -> None:
    """G-045 须声明未校验的字段与未登记的 desktop_toast（L-22 方案 B 的显式化）。"""
    block = _summary_block(_run_gate("audit_notification_coverage.py"))
    for keyword in ("level", "module", "aggregation", "builder_keys", "desktop_toast"):
        assert keyword in block, f"G-045 摘要缺少「{keyword}」：\n{block}"
    # desktop_toast 的表述须说明"无独立构建器与 i18n 键"，而非"没有 i18n 支持"
    assert "无独立构建器与 i18n 键" in block, f"G-045 对 desktop_toast 的表述不准确：\n{block}"
