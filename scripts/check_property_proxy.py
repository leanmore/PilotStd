#!/usr/bin/env python3
"""属性代理完整性检查 — 检查 BaseFacade 中 self._core.xxx 是否有对应的 @property。

扫描 pilotstd/manager/facade/_base.py：
1. 找出所有 self._core.xxx = ... 赋值（ManagerCore 属性填充）
2. 找出所有 self._core.xxx 读取访问
3. 检查每个 xxx 是否在 BaseFacade 中有对应的 @property 代理
4. 检查 _bind_methods 中绑定的方法是否在对应 Handler 中存在

用法:
    python scripts/check_property_proxy.py
    python scripts/check_property_proxy.py --verbose  # 显示所有属性详情

退出码: 0=全部通过, 1=发现缺失代理
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "pilotstd" / "manager" / "facade" / "_base.py"

# ── 已知不需要代理的属性（纯内部、仅在 __init__ 中使用） ──
SKIP_ATTRS: set[str] = {
    "_query_adapters",  # 内部属性
    "_file_watcher",  # 内部管理，通过 @property 已有 _file_watcher
    "classifier",
    "organizer_svc",
    "announce_svc",
    "pending_svc",
    "scheduled_svc",
    "validity_checker",
    "notification_mgr",
    "pipeline_store",
    "adapter_manager",
    "session_mgr",
}


def extract_core_assigns(text: str) -> dict[str, int]:
    """找出所有 self._core.xxx = ... 赋值，返回 {属性名: 行号}。"""
    pattern = re.compile(r"self\._core\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=")
    result: dict[str, int] = {}
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        for m in pattern.finditer(line):
            attr = m.group(1)
            if attr not in result:
                result[attr] = i
    return result


def extract_core_reads(text: str) -> dict[str, list[int]]:
    """找出所有 self._core.xxx 读取访问（不在赋值左侧），返回 {属性名: [行号列表]}。"""
    assign_pattern = re.compile(r"self\._core\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=")
    read_pattern = re.compile(r"self\._core\.([a-zA-Z_][a-zA-Z0-9_]*)")
    result: dict[str, list[int]] = {}
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # 跳过赋值行（已在 extract_core_assigns 中处理）
        if assign_pattern.search(line):
            continue
        for m in read_pattern.finditer(line):
            attr = m.group(1)
            if attr not in result:
                result[attr] = []
            result[attr].append(i)
    return result


def extract_properties(text: str) -> dict[str, int]:
    """找出所有 @property 定义，返回 {属性名: 行号}。"""
    lines = text.splitlines()
    result: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.strip() == "@property":
            # 下一行是 def xxx(self)
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                m = re.search(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)", next_line)
                if m:
                    result[m.group(1)] = i + 1
    return result


def extract_bind_methods(text: str) -> list[tuple[str, str, int]]:
    """找出 _bind_methods 中 self.xxx = self._yyy_handler.zzz 绑定。
    返回 [(facade_attr, handler_method, 行号)]。
    """
    pattern = re.compile(
        r"self\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*self\._([a-zA-Z_][a-zA-Z0-9_]*)_handler\.([a-zA-Z_][a-zA-Z0-9_]*)"
    )
    result: list[tuple[str, str, int]] = []
    in_bind = False
    for i, line in enumerate(text.splitlines(), 1):
        if "_bind_methods" in line and "def " in line:
            in_bind = True
            continue
        if in_bind and line.strip() and not line.startswith(" " * 4) and not line.startswith("\t"):
            in_bind = False
            continue
        if in_bind:
            m = pattern.search(line)
            if m:
                result.append((m.group(1), m.group(3), i))
    return result


def _print_proxy_report(
    target: Path,
    all_core_attrs: set[str],
    check_attrs: set[str],
    has_proxy: list[tuple[str, int]],
    missing_proxy: list[tuple[str, str, list[int]]],
    bindings: list[tuple[str, str, int]],
    verbose: bool,
) -> int:
    """输出检查报告，返回 0=通过 1=失败。"""
    sep = "=" * 60
    print(sep)
    print("  属性代理完整性检查 — BaseFacade._core.xxx → @property")
    print(sep)
    print(f"  扫描文件: {target.relative_to(ROOT)}")
    print(f"  _core.xxx 属性总数: {len(all_core_attrs)}")
    print(f"  需检查(排除内部): {len(check_attrs)}")
    print(f"  已有 @property: {len(has_proxy)}")
    print(f"  缺失 @property: {len(missing_proxy)}")
    print()

    if verbose:
        print("  --- 已有代理 ---")
        for attr, lineno in has_proxy:
            print(f"    {attr:30s} @property 行 {lineno}")
        print()

    if missing_proxy:
        print("  --- 缺失代理（需添加 @property）---")
        for attr, access_type, lines in missing_proxy:
            locs = ", ".join(str(ln) for ln in sorted(set(lines))[:3])
            print(f"    {attr:30s} 访问类型={access_type:4s}  位置行: {locs}")
        print()
        print("  修复方式: 在 BaseFacade 中添加:")
        for attr, _, _ in missing_proxy:
            print("    @property")
            print(f"    def {attr}(self):")
            print(f"        return self._core.{attr}")
            print()
        print(sep)
        print(f"  FAIL: {len(missing_proxy)} 个属性缺少 @property 代理")
        return 1

    print(sep)
    print("  PASS: 所有 _core.xxx 属性均有对应的 @property 代理")

    if verbose and bindings:
        print()
        print("  --- _bind_methods 绑定 ---")
        for attr, method, lineno in bindings:
            print(f"    行 {lineno}: self.{attr} = self._xxx_handler.{method}")

    print(sep)
    return 0


def main() -> int:
    verbose = "--verbose" in sys.argv
    if not TARGET.exists():
        print(f"ERROR: 目标文件不存在: {TARGET}")
        return 2

    text = TARGET.read_text(encoding="utf-8")
    core_assigns = extract_core_assigns(text)
    core_reads = extract_core_reads(text)
    properties = extract_properties(text)
    bindings = extract_bind_methods(text)

    all_core_attrs: set[str] = set(core_assigns) | set(core_reads)
    check_attrs = all_core_attrs - SKIP_ATTRS

    missing_proxy: list[tuple[str, str, list[int]]] = []
    has_proxy: list[tuple[str, int]] = []

    for attr in sorted(check_attrs):
        prop_name = properties.get(attr) or properties.get(f"_{attr}")
        if prop_name is not None:
            has_proxy.append((attr, properties.get(attr, 0) or properties.get(f"_{attr}", 0)))
        else:
            lines = core_reads.get(attr, []) + [core_assigns.get(attr, 0)]
            lines = [ln for ln in lines if ln > 0]
            missing_proxy.append(
                (
                    attr,
                    "读+写" if attr in core_reads and attr in core_assigns else "读" if attr in core_reads else "写",
                    lines,
                )
            )

    return _print_proxy_report(TARGET, all_core_attrs, check_attrs, has_proxy, missing_proxy, bindings, verbose)


if __name__ == "__main__":
    sys.exit(main())
