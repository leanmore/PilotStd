#!/usr/bin/env python3
"""G-011: 动态属性完整性检查 — 检测 self.xxx 定义与引用的断裂。

扫描 pilotstd/、docker/、scripts/ 下所有 Python 文件，
提取 self.xxx = ... 赋值（定义）和 self.xxx 属性访问（引用），
检测引用但未定义的断裂属性。

过滤策略：
- 跳过 Qt 信号名后缀（_changed, _ready, _signal 等）
- 跳过 _on_xxx 回调方法（由 def 定义）
- 跳过 .connect(self.xxx) 上下文中的引用
- 跳过全大写/下划线_大写常量名
- 方法定义 def xxx(self) 视为 xxx 的合法定义
- 元组解包 (self.xxx, self.yyy) = ... 视为定义
- 跳过 @dataclass 类的字段引用
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [ROOT / "pilotstd", ROOT / "docker", ROOT / "scripts"]

# ── 正则 ──
DEF_RE = re.compile(r"self\.([a-zA-Z_][a-zA-Z0-9_]*) *(?::[^=\n]+)?= (?!=)")
SETATTR_RE = re.compile(r'setattr\s*\(\s*self\s*,\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']')
# 单例模式: cls._instance.xxx = ... → self.xxx 可用
SINGLETON_DEF_RE = re.compile(r"cls\._instance\.([a-zA-Z_][a-zA-Z0-9_]*) *(?::[^=\n]+)?=")
REF_RE = re.compile(r"self\.([a-zA-Z_][a-zA-Z0-9_]*)")
METHOD_DEF_RE = re.compile(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(self\b")
MULTILINE_DEF_RE = re.compile(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")  # self 在下一行的多行定义
MAGIC_RE = re.compile(r"^__[a-z].*__$")
UPPER_CONST_RE = re.compile(r"^_?[A-Z][A-Z_0-9]*$")
# 元组解包: (self.xxx, self.yyy, ...) = expr
TUPLE_UNPACK_RE = re.compile(r"self\.([a-zA-Z_][a-zA-Z0-9_]*)")

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache", "pilotstd_env", "tests"}

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
        "close",  # QWidget.close()
        "_db",  # StandardManager 注入，跨模块继承
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
    if attr in QT_BUILTIN_ATTRS:
        return True
    if attr.startswith("_on_"):
        return True
    if attr.endswith(QT_SIGNAL_SUFFIXES):
        return True
    if UPPER_CONST_RE.match(attr):
        return True
    return False


def _is_tuple_unpack(line: str) -> bool:
    """检测是否为元组解包赋值: (self.x, self.y) = expr 或 self.x, self.y = expr"""
    stripped = line.lstrip()
    # 括号包裹的元组解包
    if stripped.startswith("(") and "self." in stripped[: stripped.index(")") if ")" in stripped else len(stripped)]:
        return True
    # 逗号分割的多重赋值: self.x, self.y = ...
    if ", self." in stripped or stripped.startswith("self.") and ", " in stripped and "=" in stripped:
        parts = stripped.split("=", 1)
        if len(parts) == 2 and "self." in parts[0]:
            return "(" not in parts[0] or ")" in parts[0]
    return False


def extract_defs(file_path: Path) -> list[tuple[str, int]]:
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

        # 单例模式: cls._instance.xxx = ... → self.xxx 可用
        for m in SINGLETON_DEF_RE.finditer(line):
            attr = m.group(1)
            if not MAGIC_RE.match(attr):
                defs.append((attr, i))

        # 元组解包: (self.xxx, self.yyy) = expr
        if _is_tuple_unpack(line):
            for m in TUPLE_UNPACK_RE.finditer(line.split("=", 1)[0]):
                attr = m.group(1)
                if not MAGIC_RE.match(attr) and not _should_skip_attr(attr):
                    defs.append((attr, i))
            continue  # 元组解包行不再用 DEF_RE 处理

        # self.xxx =
        for m in DEF_RE.finditer(line):
            after = line[m.end() :].strip()
            if after.startswith("="):
                continue
            attr = m.group(1)
            if not MAGIC_RE.match(attr):
                defs.append((attr, i))

        # def xxx(self, ...) — 方法定义也是合法属性（含多行）
        md = METHOD_DEF_RE.search(line)
        if md is not None:
            attr = md.group(1)
            if not MAGIC_RE.match(attr):
                defs.append((attr, i))
        else:
            # 多行定义: def xxx( ... self 在下一行
            ml = MULTILINE_DEF_RE.search(line)
            if ml is not None:
                attr = ml.group(1)
                if not MAGIC_RE.match(attr):
                    # 检查后续 1-2 行是否包含 self
                    for offset in (1, 2):
                        if i + offset <= len(lines):
                            if "self" in lines[i + offset - 1]:
                                defs.append((attr, i))
                                break

    return defs


def _find_dataclass_files(py_files: list[Path]) -> set[str]:
    """找出包含 @dataclass 装饰的文件路径集合。"""
    dc_files: set[str] = set()
    for f in py_files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if re.search(r"@dataclass", text):
            dc_files.add(str(f.resolve()))
    return dc_files


def extract_refs(file_path: Path) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return refs

    for i, line in enumerate(lines, 1):
        if _is_comment_or_string(line):
            continue

        method_calls: set[str] = set()
        for m in re.finditer(r"self\.([a-zA-Z_][a-zA-Z0-9_]*) *\(", line):
            method_calls.add(m.group(1))

        connect_attrs: set[str] = set()
        for m in re.finditer(r"\.connect\s*\(\s*(?:self\.)+([a-zA-Z_][a-zA-Z0-9_]*)", line):
            connect_attrs.add(m.group(1))

        has_assign = bool(re.search(r"self\.([a-zA-Z_][a-zA-Z0-9_]*) =", line))
        has_setattr = bool(re.search(r"setattr\s*\(\s*self\s*,", line))
        is_tuple = _is_tuple_unpack(line)

        # 收集本行定义的属性（用于后续排除）
        defined_in_line: set[str] = set()
        if is_tuple:
            for m in TUPLE_UNPACK_RE.finditer(line.split("=", 1)[0]):
                attr = m.group(1)
                if not MAGIC_RE.match(attr):
                    defined_in_line.add(attr)
        if has_assign:
            for m in DEF_RE.finditer(line):
                attr = m.group(1)
                if not MAGIC_RE.match(attr):
                    defined_in_line.add(attr)
        if has_setattr:
            for m in SETATTR_RE.finditer(line):
                attr = m.group(1)
                if not MAGIC_RE.match(attr):
                    defined_in_line.add(attr)

        seen_in_line: set[str] = set()
        for m in REF_RE.finditer(line):
            attr = m.group(1)

            if MAGIC_RE.match(attr):
                continue
            if attr in method_calls:
                continue
            if attr in connect_attrs:
                continue
            if _should_skip_attr(attr):
                continue
            # 本行定义的同名属性不算断裂引用
            if attr in defined_in_line:
                continue
            if attr not in seen_in_line:
                seen_in_line.add(attr)
                refs.append((attr, i))

    return refs


def main() -> int:
    # ── 收集文件 ──
    py_files: list[Path] = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for f in scan_dir.rglob("*.py"):
            if any(p in f.parts for p in EXCLUDE_DIRS):
                continue
            py_files.append(f)

    # ── 找出 dataclass 文件 ──
    dc_files = _find_dataclass_files(py_files)

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

    # ── 去重 ──
    broken: dict[tuple[str, str], tuple[str, Path, int]] = {}
    for attr, fpath, lineno in all_refs:
        if attr not in def_index:
            key = (str(fpath), attr)
            if key not in broken:
                # dataclass 文件中的属性引用通常来自类字段定义，跳过
                if str(fpath.resolve()) in dc_files:
                    continue
                broken[key] = (attr, fpath, lineno)

    # ── 输出 ──
    print("G-011: 动态属性完整性检查")
    print("=" * 60)
    print(f"扫描目录: {', '.join(str(d) for d in SCAN_DIRS)}")
    print(f"扫描文件: {len(py_files)}")
    print(f"定义数: {sum(len(v) for v in def_index.values())}")
    print(f"引用数: {len(all_refs)}")
    print(f"断裂引用: {len(broken)}")
    print()

    if broken:
        print("FAIL: 以下属性被引用但未在扫描范围内任何文件中定义：")
        for attr, fpath, lineno in sorted(broken.values(), key=lambda x: (str(x[1]), x[2])):
            rel = fpath.relative_to(ROOT) if ROOT in fpath.parents else fpath
            similar = sorted(
                [d for d in def_index if d.startswith(attr[:4]) and abs(len(d) - len(attr)) <= 3],
                key=lambda d: abs(len(d) - len(attr)),
            )[:3]
            print(f"  [ATTR] {rel}:{lineno} self.{attr}")
            if similar:
                print(f"         ─ 相似属性: {', '.join(similar)}")
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
