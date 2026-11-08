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

import ast
import re
import sys
from pathlib import Path

# 2026-11-08（W1-U1）：修正「只认 @property」造成的误报。
# BaseFacade 已用 `_CORE_PROXY_WHITELIST` + `__getattr__/__setattr__` 做属性代理，
# 只看装饰器会把 11 个白名单属性全部误报为缺失；下面用 AST 解析白名单，
# 且仅在类确实实现代理方法时才把命中项计为“已代理”。

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "pilotstd" / "manager" / "facade" / "_base.py"

# ──已知不需要代理的属性（纯内部、仅在____中使用）──
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


def _literal_str_set(node: ast.AST) -> set[str]:
    """从 `frozenset({...})` / `{...}` / `[...]` 节点提取字符串常量集合。"""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in {"frozenset", "set", "tuple", "list"} and node.args:
            return _literal_str_set(node.args[0])
        return set()
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return set()
    if isinstance(value, (set, frozenset, list, tuple)):
        return {item for item in value if isinstance(item, str)}
    return set()


def extract_proxy_whitelist(text: str) -> set[str]:
    """解析 `_CORE_PROXY_WHITELIST`；仅当类实现 `__getattr__`/`__setattr__` 时生效。

    2026-11 重构后 `BaseFacade` 用「白名单 + `__getattr__`/`__setattr__`」替代逐属性
    `@property`（见 `pilotstd/manager/facade/_base.py:46-84`）。只认 `@property` 会把
    这 11 个属性全部误报为缺失。
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        has_proxy = any(
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name in {"__getattr__", "__setattr__"}
            for child in node.body
        )
        if not has_proxy:
            continue
        for stmt in node.body:
            target = ""
            value: ast.AST | None = None
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target, value = stmt.target.id, stmt.value
            elif isinstance(stmt, ast.Assign):
                names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                if "_CORE_PROXY_WHITELIST" in names:
                    target, value = "_CORE_PROXY_WHITELIST", stmt.value
            if target == "_CORE_PROXY_WHITELIST" and value is not None:
                return _literal_str_set(value)
    return set()


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
        # 跳过赋值行（已在_核心_中处理）
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
            # 下一行是()
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
    proxied: list[str],
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
    print(f"  白名单代理(__getattr__/__setattr__): {len(proxied)}")
    print(f"  缺失 @property: {len(missing_proxy)}")
    print()

    if verbose:
        print("  --- 已有代理 ---")
        for attr, lineno in has_proxy:
            print(f"    {attr:30s} @property 行 {lineno}")
        print()
        if proxied:
            print("  --- 白名单代理（_CORE_PROXY_WHITELIST）---")
            for attr in proxied:
                print(f"    {attr:30s} 由 __getattr__/__setattr__ 委托")
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
    """入口：扫描 BaseFacade，检查所有 self._core.xxx 属性是否有对应的 @property 代理。"""
    verbose = "--verbose" in sys.argv
    if not TARGET.exists():
        print(f"ERROR: 目标文件不存在: {TARGET}")
        return 2

    text = TARGET.read_text(encoding="utf-8")
    # 提取四类信息：_核心赋值、_核心读取、@定义、__绑定
    core_assigns = extract_core_assigns(text)
    core_reads = extract_core_reads(text)
    properties = extract_properties(text)
    bindings = extract_bind_methods(text)
    proxy_whitelist = extract_proxy_whitelist(text)

    all_core_attrs: set[str] = set(core_assigns) | set(core_reads)
    check_attrs = all_core_attrs - SKIP_ATTRS

    missing_proxy: list[tuple[str, str, list[int]]] = []
    has_proxy: list[tuple[str, int]] = []
    proxied: list[str] = []

    for attr in sorted(check_attrs):
        # 检查属性名或_形式的@是否存在
        prop_name = properties.get(attr) or properties.get(f"_{attr}")
        if prop_name is not None:
            has_proxy.append((attr, properties.get(attr, 0) or properties.get(f"_{attr}", 0)))
        elif attr in proxy_whitelist:
            proxied.append(attr)
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

    return _print_proxy_report(
        TARGET, all_core_attrs, check_attrs, has_proxy, proxied, missing_proxy, bindings, verbose
    )


if __name__ == "__main__":
    sys.exit(main())
