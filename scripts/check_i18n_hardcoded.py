#!/usr/bin/env python3
"""G-040 i18n 硬编码检查（门禁脚本）。

**背景**（2026-09-26）：项目支持 zh-CN / zh-TW / en 三语，但前端组件长期把中文写死在模板与脚本里。
`web/src/views/settings/SettingsTabSchedule.vue` 整页 0 处 `t()`，用户切到英文界面仍看到中文；
而当时所有门禁都拦不住——`check_i18n_key_count.py` 只比对 locales 的**顶层** key，与组件是否用 i18n 无关。
本门禁补这个口子：**扫组件里的中文，且只拦新增**。

判定规则：
- 扫描 `web/src/**/*.vue`、`web/src/**/*.ts`，**跳过**测试文件、`.d.ts`、`web/src/locales/`（语言包本体）；
- 去掉注释（`//` 整行、`/* */`、`<!-- -->`）后，**行内出现中日韩统一表意文字**（U+3400–U+9FFF、U+F900–U+FAFF）
  即记一处违规，输出「文件:行号: 片段」；
- 例外：
  1. **行内豁免标记**：本行或上一行含 `i18n-allow` 注释（用于开发日志、正则字符类等确不需翻译的文案）；
  2. **存量基线** `scripts/i18n_hardcoded_baseline.txt`（`<相对路径>::<行数>`）：基线内**不报告**，
     只有 **超出基线**（新写死的中文）才 FAIL；低于基线只提示基线过期（不阻断），便于逐步偿还。

用法：
  python scripts/check_i18n_hardcoded.py                     # 全量扫描 + 比基线（CI/门禁）
  python scripts/check_i18n_hardcoded.py <file|dir> ...       # 只扫指定目标（本地排查）
  python scripts/check_i18n_hardcoded.py --report             # 存量排行（不判失败，供专项清理排期）
  python scripts/check_i18n_hardcoded.py --update-baseline    # 重写基线（偿还后同步）

关联测试: tests/test_check_i18n_hardcoded.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

# Windows 控制台默认编码无法输出中文，统一改用 UTF-8 输出
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_SRC = PROJECT_ROOT / "web" / "src"
DEFAULT_BASELINE = PROJECT_ROOT / "scripts" / "i18n_hardcoded_baseline.txt"

# 扫描目标：仅前端源码；语言包本体（locales/）不计入硬编码
SCAN_SUFFIXES = (".vue", ".ts")
EXCLUDE_DIR_PARTS = ("locales", "node_modules", "dist")
EXCLUDE_NAME_SUFFIXES = (".test.ts", ".spec.ts", ".d.ts")

# 中日韩统一表意文字（含扩展 A 与兼容区）；不含日文假名/韩文，避免误判
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# 行内豁免标记（注释形式）：本行或上一行出现即跳过该行
ALLOW_MARKER = "i18n-allow"

# 片段展示上限（避免把超长行整行打出来）
SNIPPET_MAX = 70

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def strip_comments(text: str) -> str:
    """去掉块注释/HTML 注释（保留换行以维持行号），并把整行 `//` 注释置空。

    只把**行首为 `//`** 的行当注释，避免把 `https://…` 这类字符串误当注释截断。
    """
    text = _BLOCK_COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    text = _HTML_COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    return "\n".join("" if line.lstrip().startswith("//") else line for line in text.splitlines())


def is_scannable(path: Path) -> bool:
    """是否属于扫描范围（后缀 / 目录 / 文件名后缀三重过滤）。"""
    if path.suffix not in SCAN_SUFFIXES:
        return False
    if any(part in EXCLUDE_DIR_PARTS for part in path.parts):
        return False
    return not any(path.name.endswith(suffix) for suffix in EXCLUDE_NAME_SUFFIXES)


def find_hardcoded(path: Path) -> list[tuple[int, str]]:
    """返回该文件里「写了中文」的行 [(行号, 片段)]；注释与豁免行不计。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    raw_lines = raw.splitlines()
    stripped = strip_comments(raw).splitlines()
    hits: list[tuple[int, str]] = []
    for idx, line in enumerate(stripped):
        if not CJK_RE.search(line):
            continue
        # 豁免：本行或上一行的原始文本里带 i18n-allow 标记
        if ALLOW_MARKER in raw_lines[idx] or (idx > 0 and ALLOW_MARKER in raw_lines[idx - 1]):
            continue
        hits.append((idx + 1, " ".join(line.split())[:SNIPPET_MAX]))
    return hits


def collect_files(targets: list[str]) -> list[Path]:
    """展开扫描目标：显式路径（文件或目录）优先，否则扫 web/src 全量。"""
    if not targets:
        return sorted(p for p in WEB_SRC.rglob("*") if p.is_file() and is_scannable(p))
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*") if q.is_file() and is_scannable(q)))
        elif p.is_file():
            files.append(p)
    return files


def rel(path: Path) -> str:
    """相对仓库根展示路径。"""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_baseline(path: Path) -> dict[str, int]:
    """读取基线（`<相对路径>::<行数>`）；文件不存在返回空表。"""
    if not path.is_file():
        return {}
    baseline: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
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
    """按当前存量重写基线（只写有硬编码的文件）。"""
    lines = [
        "# G-040 i18n 硬编码基线（由 scripts/check_i18n_hardcoded.py --update-baseline 生成，勿手改）",
        "# 格式: <相对仓库根路径>::<当前存量行数>；门禁只拦「超出基线」的新增，低于基线仅提示可刷新。",
    ]
    lines += [f"{name}::{count}" for name, count in sorted(counts.items()) if count > 0]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def scan(files: list[Path]) -> dict[str, list[tuple[int, str]]]:
    """返回 {相对路径: 违规行列表}（只含有中文的文件）。"""
    result: dict[str, list[tuple[int, str]]] = {}
    for f in files:
        hits = find_hardcoded(f)
        if hits:
            result[rel(f)] = hits
    return result


def print_report(hits: dict[str, list[tuple[int, str]]]) -> None:
    """打印存量排行（供专项清理排期）。"""
    ranked = sorted(hits.items(), key=lambda kv: -len(kv[1]))
    total = sum(len(v) for v in hits.values())
    print("=" * 60)
    print("G-040: i18n 硬编码存量报告（不判失败）")
    print("=" * 60)
    print(f"  含硬编码中文的文件: {len(ranked)}   行数合计: {total}")
    print()
    print(f"  {'文件':<58} 行数")
    for name, rows in ranked:
        print(f"  {name:<58} {len(rows)}")


def main(argv: list[str] | None = None) -> int:
    """入口：扫描 → 比基线 → 输出违规；有新增返回 1。"""
    args = list(sys.argv[1:] if argv is None else argv)
    baseline_path = DEFAULT_BASELINE
    if "--baseline" in args:
        i = args.index("--baseline")
        baseline_path = Path(args[i + 1])
        del args[i : i + 2]

    targets = [a for a in args if not a.startswith("--")]
    update = "--update-baseline" in args
    report_only = "--report" in args

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

    print("=" * 60)
    print("G-040: i18n 硬编码检查（组件里不得新写死中文）")
    print("=" * 60)
    print(f"  扫描文件: {len(files)}")
    print(f"  基线文件: {rel(baseline_path)}（{len(baseline)} 条）")
    print(f"  含硬编码文件: {len(hits)}   新增违规行: {len(violations)}")
    if violations:
        for name, lineno, snippet in violations[:50]:
            print(f"  [HARDCODED] {name}:{lineno}: {snippet}")
        if len(violations) > 50:
            print(f"  … 其余 {len(violations) - 50} 行省略")
        print("\nFAIL: 新增了硬编码中文文案。请改用 t('...')（key 加到 web/src/locales/ 三语），")
        print("      确不需翻译的（开发日志/正则）在该行或上一行加 `i18n-allow` 注释。")
        return 1
    for name, now, allowed in stale[:10]:
        print(f"  [STALE] {name}: 现 {now} 行 < 基线 {allowed} 行 —— 可重跑 --update-baseline 收紧")
    print("\nPASS: 未发现超出基线的硬编码中文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
