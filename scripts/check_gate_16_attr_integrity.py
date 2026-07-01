#!/usr/bin/env python3
"""GATE-16: 动态属性完整性检查 — 检测 self.xxx 定义与引用的断裂。

扫描 pilotstd/ui/ 下所有 Python 文件，提取 self.xxx = ... 赋值（定义）
和 self.xxx 属性访问（引用），检测引用但未定义的断裂属性。

过滤策略（减少 Qt/PyQt6 框架误报）：
- 跳过 Qt 信号名后缀（_changed, _ready, _signal 等）
- 跳过 _on_xxx 回调方法（由 def 定义）
- 跳过 .connect(self.xxx) 上下文中的引用
- 跳过 setattr 动态属性
- 方法定义 def xxx(self) 视为 xxx 的合法定义
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIR = ROOT / "pilotstd" / "ui"

# ── 正则 ──
# 支持 self.xxx = value 和 self.xxx: Type = value（类型注解赋值）
# (?!.*=) → (?!=) 修复：避免 keyword 参数中的 = 被误判为双等号
DEF_RE = re.compile(r"self\.([a-zA-Z_][a-zA-Z0-9_]*) *(?::[^=\n]+)?= (?!=)")
SETATTR_RE = re.compile(r'setattr\s*\(\s*self\s*,\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']')
REF_RE = re.compile(r"self\.([a-zA-Z_][a-zA-Z0-9_]*)")
METHOD_DEF_RE = re.compile(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(self\b")
MAGIC_RE = re.compile(r"^__[a-z].*__$")
UPPER_CONST_RE = re.compile(r"^[A-Z][A-Z_0-9]*$")  # 全大写常量名

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache"}

# Qt 信号名后缀 — 这些通常是 PyQt6/PySide6 内置信号，不纳入检查
QT_SIGNAL_SUFFIXES = (
    "_changed",
    "_ready",
    "_occurred",
    "_signal",
    "_finished",
    "_started",
    "_received",
    "_result",
    "_processed",
    "_succeeded",
    "_failed",
)

# Qt 框架内置属性（QThread, QObject, QWidget 等）
QT_BUILTIN_ATTRS = frozenset(
    {
        "progress",
        "error",
        "finished",
        "started",
        "batch_ready",
        "stage_changed",
        "connected",
        "disconnected",
        "message_received",
        "error_occurred",
        "drives_ready",
        "scan_batch",
        "scan_progress",
        "query_progress",
        "download_progress",
        "download_result",
        "archive_result",
        "query_result",
        "stage_changed",
        "close",  # QWidget.close()
        "_db",  # StandardManager 注入，不在 ui/ 范围内定义
    }
)


def _is_comment_or_string(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        return True
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return True
    return False


def _should_skip_attr(attr: str) -> bool:
    """跳过已知的 Qt 框架属性、全大写常量等。"""
    if attr in QT_BUILTIN_ATTRS:
        return True
    if attr.startswith("_on_"):
        return True
    if attr.endswith(QT_SIGNAL_SUFFIXES):
        return True
    if UPPER_CONST_RE.match(attr):
        return True
    return False


def extract_defs(file_path: Path) -> list[tuple[str, int]]:
    """提取 self.xxx = ... 和 def xxx(self, ...) 定义。"""
    defs: list[tuple[str, int]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return defs

    for i, line in enumerate(lines, 1):
        if _is_comment_or_string(line):
            continue

        # setattr(self, "xxx", ...)
        for m in SETATTR_RE.finditer(line):
            attr = m.group(1)
            if not MAGIC_RE.match(attr):
                defs.append((attr, i))

        # self.xxx =
        for m in DEF_RE.finditer(line):
            after = line[m.end() :].strip()
            if after.startswith("="):
                continue
            attr = m.group(1)
            if not MAGIC_RE.match(attr):
                defs.append((attr, i))

        # def xxx(self, ...) — 方法定义也是合法属性
        md = METHOD_DEF_RE.search(line)
        if md is not None:
            attr = md.group(1)
            if not MAGIC_RE.match(attr):
                defs.append((attr, i))

    return defs


def extract_refs(file_path: Path) -> list[tuple[str, int]]:
    """提取 self.xxx 属性引用（过滤方法调用和 Qt 信号）。"""
    refs: list[tuple[str, int]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return refs

    for i, line in enumerate(lines, 1):
        if _is_comment_or_string(line):
            continue

        # 收集方法调用
        method_calls: set[str] = set()
        for m in re.finditer(r"self\.([a-zA-Z_][a-zA-Z0-9_]*) *\(", line):
            method_calls.add(m.group(1))

        # 收集 .connect(self.xxx) 上下文中的属性（Qt 信号处理函数引用，跳过）
        connect_attrs: set[str] = set()
        for m in re.finditer(r"\.connect\s*\(\s*(?:self\.)+([a-zA-Z_][a-zA-Z0-9_]*)", line):
            connect_attrs.add(m.group(1))

        # 检查赋值
        has_assign = bool(re.search(r"self\.([a-zA-Z_][a-zA-Z0-9_]*) =", line))
        has_setattr = bool(re.search(r"setattr\s*\(\s*self\s*,", line))

        seen_in_line: set[str] = set()
        for m in REF_RE.finditer(line):
            attr = m.group(1)

            # 过滤条件
            if MAGIC_RE.match(attr):
                continue
            if attr in method_calls:
                continue
            if attr in connect_attrs:
                continue
            if _should_skip_attr(attr):
                continue
            if has_assign and attr in seen_in_line:
                continue
            if attr not in seen_in_line:
                seen_in_line.add(attr)
                refs.append((attr, i))

        # 赋值行：移除本行已定义的属性引用
        if has_assign or has_setattr:
            defined_in_line: set[str] = set()
            for m in DEF_RE.finditer(line):
                attr = m.group(1)
                if not MAGIC_RE.match(attr):
                    defined_in_line.add(attr)
            for m in SETATTR_RE.finditer(line):
                attr = m.group(1)
                if not MAGIC_RE.match(attr):
                    defined_in_line.add(attr)
            refs = [(a, ln) for a, ln in refs if not (ln == i and a in defined_in_line)]

    return refs


def main() -> int:
    if not SCAN_DIR.exists():
        print(f"GATE-16 SKIP: {SCAN_DIR} 不存在")
        return 0

    # ── 收集文件 ──
    py_files: list[Path] = []
    for f in SCAN_DIR.rglob("*.py"):
        if any(p in f.parts for p in EXCLUDE_DIRS):
            continue
        py_files.append(f)

    # ── 定义索引 ──
    def_index: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for f in py_files:
        for attr, lineno in extract_defs(f):
            def_index[attr].append((f, lineno))

    # ── 引用索引 ──
    all_refs: list[tuple[str, Path, int]] = []
    for f in py_files:
        for attr, lineno in extract_refs(f):
            all_refs.append((attr, f, lineno))

    # ── 去重引用（同一文件同一属性多次引用只计一次断裂） ──
    broken: dict[tuple[str, str], tuple[str, Path, int]] = {}
    for attr, fpath, lineno in all_refs:
        if attr not in def_index:
            key = (str(fpath), attr)
            if key not in broken:
                broken[key] = (attr, fpath, lineno)

    # ── 输出 ──
    print("GATE-16: 动态属性完整性检查")
    print("=" * 60)
    print(f"定义数: {sum(len(v) for v in def_index.values())}")
    print(f"引用数: {len(all_refs)}")
    print(f"断裂引用: {len(broken)}")
    print()

    if broken:
        print("FAIL: 以下属性被引用但未在 pilotstd/ui/ 任何文件中定义：")
        for attr, fpath, lineno in sorted(broken.values(), key=lambda x: (x[1], x[2])):
            rel = fpath.relative_to(ROOT)
            similar = sorted(
                [d for d in def_index if d.startswith(attr[:4]) and abs(len(d) - len(attr)) <= 3],
                key=lambda d: abs(len(d) - len(attr)),
            )[:3]
            print(f"  [ATTR] {rel}:{lineno} self.{attr}")
            if similar:
                print(f"         ─ 未找到定义。相似属性: {', '.join(similar)}")
        print()
        print("=" * 60)
        print(f"汇总: {len(broken)} 断裂 / {len(all_refs)} 总引用")
        print("FAIL: 请修复上述属性引用后再提交。")
        return 1

    print("=" * 60)
    print(f"汇总: 0 断裂 / {len(all_refs)} 总引用")
    print("PASS: 所有动态属性引用均存在对应定义。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
