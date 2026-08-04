#!/usr/bin/env python3
"""信号连接完整性检查 — 检查 pyqtSignal 定义、connect、emit 三者是否齐全。

扫描 pilotstd/ui/ 下所有 Python 文件：
1. 找出所有 pyqtSignal 定义
2. 找出所有 .connect( 调用（关联到信号变量名）
3. 找出所有 .emit( 调用（关联到信号变量名）
4. 按信号变量名匹配，输出缺失项

用法:
    python scripts/check_signal_connect.py
    python scripts/check_signal_connect.py --verbose  # 显示所有信号详情

退出码: 0=全部完整, 1=发现缺失
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIR = ROOT / "pilotstd" / "ui"

# ── 已知的 PyQt 内置信号（不需要检查 connect/emit 完整性） ──
PYQT_BUILTIN_SIGNALS = {
    "clicked",
    "triggered",
    "toggled",
    "textChanged",
    "currentRowChanged",
    "itemDoubleClicked",
    "itemExpanded",
    "customContextMenuRequested",
    "sectionResized",
    "timeout",
    "activated",
    "aboutToQuit",
    "currentIndexChanged",
    "currentChanged",
    "valueChanged",
    "editingFinished",
    "returnPressed",
    "stateChanged",
    "selectionChanged",
}


def find_signal_defs(file_path: Path) -> list[tuple[str, int, str]]:
    """找出文件中所有 pyqtSignal 定义。
    返回 [(变量名, 行号, 信号签名)]。
    """
    results: list[tuple[str, int, str]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return results

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # 匹配: xxx = pyqtSignal(...) 或 xxx = pyqtSignal(int, str) 等
        m = re.search(r"(\w+)\s*=\s*pyqtSignal\b", stripped)
        if m:
            sig_name = m.group(1)
            results.append((sig_name, i, stripped))
    return results


def find_connects(file_path: Path) -> list[tuple[str, int, str]]:
    """找出文件中所有 .connect( 调用。
    返回 [(信号变量名/对象属性, 行号, 原始行)]。
    """
    results: list[tuple[str, int, str]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return results

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # 匹配模式:
        # 1. self._xxx.yyy.connect(...)  → yyy 是信号名
        # 2. self._xxx.connect(...)      → _xxx 是 worker 的信号组
        # 3. self.xxx.connect(...)       → xxx 是信号名

        # 提取 .connect( 前面的部分
        for m in re.finditer(r"(\w+)\.connect\s*\(", stripped):
            sig = m.group(1)
            if sig not in PYQT_BUILTIN_SIGNALS:
                results.append((sig, i, stripped[:80]))

        # 提取 self._xxx_worker.zzz.connect( → zzz 是信号
        for m in re.finditer(r"_worker\.(\w+)\.connect\s*\(", stripped):
            sig = m.group(1)
            if sig not in PYQT_BUILTIN_SIGNALS:
                results.append((sig, i, stripped[:80]))

        # 提取 self._xxx_worker.error.connect( 等
        for m in re.finditer(r"\.(\w+)\.connect\s*\(", stripped):
            sig = m.group(1)
            if sig not in PYQT_BUILTIN_SIGNALS and sig not in {"set", "get", "add", "remove"}:
                results.append((sig, i, stripped[:80]))

    return results


def find_emits(file_path: Path) -> list[tuple[str, int, str]]:
    """找出文件中所有 .emit( 调用。"""
    results: list[tuple[str, int, str]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return results

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # 说明：self._xxx.emit(...)
        for m in re.finditer(r"(\w+)\.emit\s*\(", stripped):
            sig = m.group(1)
            if sig not in PYQT_BUILTIN_SIGNALS:
                results.append((sig, i, stripped[:80]))

    return results


def _collect_signals(
    py_files: list[Path],
) -> tuple[dict, dict, dict]:
    """收集所有信号定义、connect、emit。"""
    all_defs: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    all_connects: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    all_emits: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for f in py_files:
        for name, lineno, _ in find_signal_defs(f):
            all_defs[name].append((f, lineno))
        for name, lineno, _ in find_connects(f):
            all_connects[name].append((f, lineno))
        for name, lineno, _ in find_emits(f):
            all_emits[name].append((f, lineno))
    return all_defs, all_connects, all_emits


def _print_signal_report(
    custom_signal_names: set[str],
    all_defs: dict,
    all_connects: dict,
    all_emits: dict,
    py_files: list[Path],
) -> int:
    """输出信号检查报告，返回 0=通过 1=失败。"""
    complete: list[str] = []
    missing_connect: list = []
    missing_emit: list = []
    missing_def: list = []

    for sig in sorted(custom_signal_names):
        has_def = sig in all_defs
        has_connect = sig in all_connects
        has_emit = sig in all_emits
        if has_def and has_connect and has_emit:
            complete.append(sig)
        elif has_def and has_emit and not has_connect:
            missing_connect.append((sig, all_defs[sig], all_emits[sig]))
        elif has_def and has_connect and not has_emit:
            missing_emit.append((sig, all_defs[sig], all_connects[sig]))
        elif not has_def and has_connect:
            missing_def.append((sig, all_connects[sig]))

    sep = "=" * 60
    print(sep)
    print("  信号连接完整性检查")
    print(sep)
    print(f"  扫描目录: {SCAN_DIR.relative_to(ROOT)}")
    print(f"  扫描文件: {len(py_files)}")
    print(f"  自定义信号总数: {len(custom_signal_names)}")
    print(f"  完整信号(定义+connect+emit): {len(complete)}")
    print(f"  缺失 connect: {len(missing_connect)}")
    print(f"  缺失 emit: {len(missing_emit)}")
    print(f"  缺失定义: {len(missing_def)}")
    print()

    if missing_connect:
        print("  --- 缺失 connect 的信号 ---")
        for sig, defs, emits in missing_connect:
            def_loc = f"{defs[0][0].relative_to(ROOT)}:{defs[0][1]}"
            emit_locs = ", ".join(f"{p.relative_to(ROOT)}:{ln}" for p, ln in emits[:3])
            print(f"    {sig:25s} 定义={def_loc}")
            print(f"    {'':25s} emit位置={emit_locs}")
            print()
    else:
        print("  [OK] 所有有定义的信号都有 connect")

    if missing_emit:
        print("  --- 缺失 emit 的信号 ---")
        for sig, defs, connects in missing_emit:
            def_loc = f"{defs[0][0].relative_to(ROOT)}:{defs[0][1]}"
            con_locs = ", ".join(f"{p.relative_to(ROOT)}:{ln}" for p, ln in connects[:3])
            print(f"    {sig:25s} 定义={def_loc}")
            print(f"    {'':25s} connect位置={con_locs}")
            print()

    if missing_def:
        print("  --- 被连接但无定义的信号 ---")
        for sig, connects in missing_def:
            con_locs = ", ".join(f"{p.relative_to(ROOT)}:{ln}" for p, ln in connects[:3])
            print(f"    {sig:25s} connect位置={con_locs}")
            print()

    print(sep)
    total_issues = len(missing_connect) + len(missing_emit) + len(missing_def)
    if total_issues > 0:
        print(f"  FAIL: {total_issues} 个信号不完整")
        return 1
    print("  PASS: 所有自定义信号定义、connect、emit 完整")
    print(sep)
    return 0


def main() -> int:
    """入口：扫描 pilotstd/ui/ 下所有 Python 文件，检查 pyqtSignal 的 connect/emit 完整性。"""
    if not SCAN_DIR.exists():
        print(f"ERROR: 扫描目录不存在: {SCAN_DIR}")
        return 2

    py_files = sorted(
        p for p in SCAN_DIR.rglob("*.py") if "__pycache__" not in p.parts and "pilotstd_env" not in p.parts
    )
    all_defs, all_connects, all_emits = _collect_signals(py_files)
    all_signal_names = set(all_defs) | set(all_connects) | set(all_emits)
    custom_signal_names = all_signal_names - PYQT_BUILTIN_SIGNALS
    return _print_signal_report(custom_signal_names, all_defs, all_connects, all_emits, py_files)


if __name__ == "__main__":
    sys.exit(main())
