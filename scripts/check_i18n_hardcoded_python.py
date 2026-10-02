#!/usr/bin/env python3
"""i18n 硬编码中文检查（**Python 侧**）— G-047。

版本历史:
  v1.0.0  技术债阶段批次⑤  初始版本：AST 字符串字面量口径 + 只拦新增基线 + 判别力自检

## 起因

`check_i18n_hardcoded.py`（G-040）只扫 `web/src/**/*.{vue,ts}`（其 `SCAN_SUFFIXES`），
**Python 侧完全无门禁** —— 实测 `pilotstd/**` + `docker/**` 有数千处硬编码中文字符串，
今天往 `pilotstd/` 里写死中文，13 道 CI 全绿。这是真实缺口（设计文档 §7.3 已登记为
"预存问题"）。本门禁是**只拦新增**的基线门禁，不做存量重写。

## 判定口径（必须用 AST，不能用行级正则）

**反向约束（关键）**：`check_g_012_comment_density.py` **强制要求注释与 docstring 必须是中文**。
若用行级正则扫 `pilotstd/**/*.py`，会命中约 8791 行（其中注释 3417 + docstring 2152 正是
G-012 强制存在的中文），误报比约 **4.6:1**，且会把门禁强制的规范判为违规——**自我否证**。
故本门禁**只统计 AST 字符串字面量**（`ast.Constant` 且 `str`），并**跳过 docstring**：
  - docstring 由 G-012 强制中文 → 一律不计；
  - 注释不在 AST 中 → 自然不计。

**为何含 logger 实参**：日志确实是"给非中文用户看的内容"，但 i18n 化收益低。本门禁按
P-104 采用**简单可辩护口径**（"Python 字符串字面量中的中文"），**不引入"日志豁免"**——
那需要判定调用者身份、增加误报来源。若要治理日志文案，应另立专项。

## 豁免与基线机制（与 G-040 一致）

1. **行内豁免**：本行或**上一行**含 `i18n-allow` 注释 → 该行跳过；
2. **存量基线** `scripts/i18n_hardcoded_python_baseline.json`（`{相对路径: 行数}`）：
   基线内不报；超出报新增；低于基线仅提示可刷新（不阻断）；
3. **空基线 ≠ 门禁失效**：文件不在基线中 → **一处都不允许**（G-040 曾因此出过缺陷：
   批 6 把基线清零后门禁看似失效，CI run 36293074107 红）。

## 用法

    python scripts/check_i18n_hardcoded_python.py                     # 全量扫描 + 比基线（CI/门禁）
    python scripts/check_i18n_hardcoded_python.py <file|dir> ...       # 只扫指定目标（本地排查）
    python scripts/check_i18n_hardcoded_python.py --report             # 存量排行（不判失败）
    python scripts/check_i18n_hardcoded_python.py --update-baseline    # 重写基线

关联测试: tests/test_check_i18n_hardcoded_python.py
关联文档: docs/plans/notification-refactor-design.md §7.3（排名 13，预存问题）
"""

from __future__ import annotations

import ast
import io
import json
import re
import sys
from pathlib import Path

# Windows 控制台默认编码无法输出中文，统一改用 UTF-8 输出
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 基线用 `.json` 而不是 `.txt`：入仓合规门禁（`.github/scripts/check-repo-compliance.sh`）
# 的 FILENAME_BLACKLIST 含 `*.txt`（本意拦"临时文本文件"），会把**门禁自身的基线数据**
# 一并拦下。改 `.json` 后既不再误命中，又与项目既有基线惯例一致
# （`.secrets.baseline` / `web/pnpm-lock.yaml` 等同为结构化数据文件）。
DEFAULT_BASELINE = PROJECT_ROOT / "scripts" / "i18n_hardcoded_python_baseline.json"

# 扫描目标：Python 生产代码。语言包本体（pilotstd/i18n/*.json）不是 .py，自然不计。
SCAN_DIRS = ("pilotstd", "docker")

# 目录级排除（任意层级）：测试/cache/构建产物
EXCLUDE_DIR_PARTS = frozenset(
    {"__pycache__", "node_modules", "build", "dist", ".venv", "venv", "tests", "test"}
)

# 路径级豁免：**语言包加载器本体**（自身就是本地化数据入口，不是"写死的中文"）
EXCLUDE_FILES = frozenset({"pilotstd/core/i18n.py"})

# 中日韩统一表意文字（含扩展 A 与兼容区）；不含日文假名/韩文，避免误判
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# 行内豁免标记（注释形式）：本行或上一行出现即跳过该行
ALLOW_MARKER = "i18n-allow"

# 片段展示上限（避免把超长行整行打出来）
SNIPPET_MAX = 70


def rel(path: Path) -> str:
    """相对仓库根的 POSIX 路径（Windows 下反斜杠会让基线与断言不一致）。"""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_scannable(path: Path) -> bool:
    """是否纳入扫描：`.py` + 不在排除目录 + 不在路径级豁免。"""
    if path.suffix != ".py":
        return False
    if any(part in EXCLUDE_DIR_PARTS for part in path.parts):
        return False
    return rel(path) not in EXCLUDE_FILES


def collect_files(targets: list[str]) -> list[Path]:
    """收集待扫描文件。

    **注意（照抄 G-040 的缺口会继承）**：G-040 的 `collect_files()` 对**显式文件参数**
    跳过了 `is_scannable()`，使 `check_i18n_hardcoded.py foo.py` 会真的扫 `.py`。
    本门禁**对显式目标也执行 `is_scannable`**，保持"默认路径与显式路径判定一致"。
    """
    if targets:
        out: list[Path] = []
        for t in targets:
            p = Path(t)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            if p.is_dir():
                out.extend(f for f in sorted(p.rglob("*.py")) if is_scannable(f))
            elif p.is_file() and is_scannable(p):
                out.append(p)
        return out

    out = []
    for d in SCAN_DIRS:
        base = PROJECT_ROOT / d
        if base.is_dir():
            out.extend(f for f in sorted(base.rglob("*.py")) if is_scannable(f))
    return out


def _docstring_lines(tree: ast.AST) -> set[int]:
    """返回**docstring 所占据的行号集合**（含三引号跨行的全部行）。

    docstring 由 `check_g_012_comment_density.py` **强制要求中文**，故必须排除；
    若计入门禁会把"遵守 G-012"判为违规（自我否证）。
    """
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)):
            continue
        if not isinstance(first.value.value, str):
            continue
        start = first.value.lineno
        end = getattr(first.value, "end_lineno", start)
        lines.update(range(start, end + 1))
    return lines


def find_hardcoded(path: Path) -> list[tuple[int, str]]:
    """返回该文件中的硬编码中文（`(行号, 片段)`，按行号升序；同一行多处只记一次）。"""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    raw_lines = source.splitlines()
    doc_lines = _docstring_lines(tree)
    found: dict[int, str] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        lineno = node.lineno
        if lineno in doc_lines:
            continue
        if not CJK_RE.search(node.value):
            continue
        # 行内豁免：本行或上一行含标记
        if 0 <= lineno - 1 < len(raw_lines) and ALLOW_MARKER in raw_lines[lineno - 1]:
            continue
        if lineno - 2 >= 0 and ALLOW_MARKER in raw_lines[lineno - 2]:
            continue
        if lineno in found:
            continue
        idx = lineno - 1
        snippet = raw_lines[idx].strip() if 0 <= idx < len(raw_lines) else node.value
        found[lineno] = snippet[:SNIPPET_MAX]

    return sorted(found.items())


def scan(files: list[Path]) -> dict[str, list[tuple[int, str]]]:
    """返回 {相对路径: 违规行列表}（只含有硬编码中文的文件）。"""
    result: dict[str, list[tuple[int, str]]] = {}
    for f in files:
        hits = find_hardcoded(f)
        if hits:
            result[rel(f)] = hits
    return result


def load_baseline(path: Path) -> dict[str, int]:
    """读取基线；文件不存在返回空表。

    支持两种格式：
    - **JSON** `{相对路径: 行数}`（当前写入格式，见 `write_baseline`）；
    - **旧文本** `<相对路径>::<行数>`（历史格式，仍可读，便于平滑过渡与既有测试夹具）。

    旧格式兼容是有意保留的：测试夹具会写入空文件或不含 `::` 的内容，
    两种解析都必须安全退化为空表（"空基线 ≠ 门禁失效"由调用方保证）。
    """
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return {}
        return {str(k): int(v) for k, v in data.items() if isinstance(v, (int, float))}

    baseline: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "::" not in line:
            continue
        key, _, value = line.rpartition("::")
        try:
            baseline[key.strip()] = int(value.strip())
        except ValueError:
            continue
    return baseline


def write_baseline(path: Path, counts: dict[str, int]) -> None:
    """按当前存量重写基线（只写有硬编码的文件）。

    写 **JSON**（`{相对路径: 行数}`）：结构化、可被工具解析，且**避开入仓合规门禁的
    `*.txt` 文件名黑名单**——该黑名单本意拦"临时文本文件"，会误拦门禁自身的基线数据。
    """
    data = {name: count for name, count in sorted(counts.items()) if count > 0}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(hits: dict[str, list[tuple[int, str]]]) -> None:
    """打印存量排行（供专项清理排期）。"""
    ranked = sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    total = sum(len(v) for v in hits.values())
    print("=" * 64)
    print("G-047: i18n 硬编码中文（Python 侧）存量报告（不判失败）")
    print("=" * 64)
    print(f"  含硬编码中文的文件: {len(ranked)}   处数合计: {total}")
    print()
    print(f"  {'文件':<56} 处数")
    for name, rows in ranked:
        print(f"  {name:<56} {len(rows)}")


def main(argv: list[str] | None = None) -> int:
    """入口：扫描 → 比基线 → 输出违规；有新增返回 1。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    baseline_path = DEFAULT_BASELINE
    if "--baseline" in argv:
        i = argv.index("--baseline")
        baseline_path = Path(argv[i + 1])
        del argv[i : i + 2]

    targets = [a for a in argv if not a.startswith("--")]
    update = "--update-baseline" in argv
    report_only = "--report" in argv

    files = collect_files(targets)
    hits = scan(files)

    if update:
        write_baseline(baseline_path, {name: len(rows) for name, rows in hits.items()})
        print(f"基线已重写: {rel(baseline_path)}（{len(hits)} 个文件）")
        return 0

    if report_only:
        print_report(hits)
        return 0

    baseline = load_baseline(baseline_path)
    violations: list[tuple[str, int, str]] = []
    stale: list[tuple[str, int, int]] = []
    for name, rows in sorted(hits.items()):
        allowed = baseline.get(name)
        if allowed is None:
            violations.extend((name, ln, snip) for ln, snip in rows)  # 新文件：一处都不允许
        elif len(rows) > allowed:
            violations.extend((name, ln, snip) for ln, snip in rows[allowed:])
        elif len(rows) < allowed:
            stale.append((name, len(rows), allowed))

    print("=" * 64)
    print("G-047: i18n 硬编码中文检查（Python 侧，只拦新增）")
    print("=" * 64)
    print(f"  扫描文件: {len(files)}")
    print(f"  基线文件: {rel(baseline_path)}（{len(baseline)} 条）")
    print(f"  含硬编码文件: {len(hits)}   新增违规: {len(violations)}")

    if violations:
        print()
        for name, lineno, snippet in violations[:40]:
            print(f"  [HARDCODED] {name}:{lineno}: {snippet}")
        if len(violations) > 40:
            print(f"  ... 另 {len(violations) - 40} 处")
        print()
        print(f"FAIL: 发现 {len(violations)} 处超出基线的硬编码中文。")
        print("  处置：把文案迁入 pilotstd/i18n/*.json，或对该行加 `# i18n-allow` 并说明理由。")
        return 1

    if stale:
        print()
        print(f"  [STALE] {len(stale)} 个文件的存量低于基线，可运行 --update-baseline 刷新：")
        for name, now, allowed in stale[:10]:
            print(f"    {name}: {now} < {allowed}")

    print()
    print("PASS: 未发现超出基线的硬编码中文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
