#!/usr/bin/env python3
"""G-039 冲突标记检查（门禁脚本）。

**背景**（2026-09-26）：一次合并中，解析脚本断言失败后同一条命令里的
`git add` + `git commit` 仍然执行，产生了一个**带 `<<<<<<< / ======= / >>>>>>>` 的合并提交**，
而它通过了当时 pre-commit 的全部门禁——没有任何机制能拦住这类提交。本门禁补这个口子。

判定规则：
- **冲突块**：一行以 7 个 `<` 开头，且其后存在一行以 7 个 `>` 开头 → 该两块之间
  以 7 个 `=` 开头的行也一并报告（`=======` 在 Markdown 里是合法的 Setext 标题下划线，
  故**只在成块时**才算违规，避免误伤）。
- **孤立标记**：单独一行以 7 个 `<` 或 7 个 `>` 开头，同样判违规（残缺的合并残留）。

扫描范围（优先级从高到低）：
1. 命令行显式给出的路径；
2. 暂存区（`git diff --cached --name-only`，pre-commit 场景）；
3. 全库已跟踪文件（`git ls-files`，CI 全量场景）。

排除：
- `.gitignore` 忽略的文件（走 `_gate_paths.is_git_ignored`，与其它门禁同口径）；
- `WHITELIST_NAME_SUFFIXES` 内的文件名（**仅供"用于测试本门禁自身"的 fixture**）。

只使用标准库。本脚本正文用**字符串拼接**构造标记，因此自身不含字面量、可被自己扫描。
"""

import io
import subprocess
import sys
from pathlib import Path

from _gate_paths import is_git_ignored

# Windows 控制台默认编码无法输出部分字符，统一改用 UTF-8 输出
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 标记用拼接构造：本文件因此不含字面量，自身可被本门禁扫描
_LEFT = "<" * 7
_RIGHT = ">" * 7
_EQUAL = "=" * 7

# 白名单：仅限"用于测试本门禁自身"的 fixture 文件名后缀（避免测试夹具被判违规）
WHITELIST_NAME_SUFFIXES = ("conflict-marker-fixture.txt",)

# 单行片段展示长度上限（避免把整行超长 SQL 打进日志）
_SNIPPET_MAX = 80


def _is_whitelisted(path: Path) -> bool:
    """判断文件是否属于"测试本门禁自身"的白名单夹具。"""
    return any(path.name.endswith(suffix) for suffix in WHITELIST_NAME_SUFFIXES)


def _staged_files() -> list[Path]:
    """返回暂存区中新增/修改/重命名的文件（pre-commit 场景）。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    return [PROJECT_ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def _tracked_files() -> list[Path]:
    """返回全库已跟踪文件（CI 全量场景）。"""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    return [PROJECT_ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def collect_targets(argv: list[str]) -> list[Path]:
    """按优先级确定扫描目标：显式路径 > 暂存区 > 全库已跟踪文件。"""
    if argv:
        return [Path(a).resolve() for a in argv]
    staged = _staged_files()
    return staged if staged else _tracked_files()


def find_violations(path: Path) -> list[tuple[int, str]]:
    """返回该文件的冲突标记行 [(行号, 行内容)]；无违规返回空列表。"""
    if _is_whitelisted(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []  # 二进制或不可读文件跳过（冲突标记只可能出现在文本里）
    lines = text.splitlines()
    left = [i for i, line in enumerate(lines) if line.startswith(_LEFT)]
    right = [i for i, line in enumerate(lines) if line.startswith(_RIGHT)]
    if not left and not right:
        return []

    hits: set[int] = set()
    for i in left:
        # 冲突块 = 本行 + 其后最近的 >>>>>>> 行；只报**标记行**，不报块内业务内容
        # （真实冲突块可能上千行，逐行打日志没有意义）
        after = [j for j in right if j > i]
        if after:
            end = after[0]
            hits.add(i)
            hits.add(end)
            hits.update(n for n in range(i + 1, end) if lines[n].startswith(_EQUAL))
        else:
            hits.add(i)  # 孤立 <<<<<<<（残缺残留）
    for j in right:
        if not any(i < j for i in left):
            hits.add(j)  # 孤立 >>>>>>>
    return [(n + 1, lines[n]) for n in sorted(hits)]


def main(argv: list[str] | None = None) -> int:
    """入口：扫描目标文件并输出违规清单；有违规返回 1。"""
    args = list(sys.argv[1:] if argv is None else argv)
    targets = collect_targets(args)
    violations: list[tuple[Path, int, str]] = []
    scanned = 0
    for path in targets:
        if not path.is_file() or is_git_ignored(path, PROJECT_ROOT):
            continue
        scanned += 1
        for lineno, line in find_violations(path):
            violations.append((path, lineno, line))

    print("=" * 60)
    print("G-039: 冲突标记检查（禁止 <<<<<<< / ======= / >>>>>>> 入库）")
    print("=" * 60)
    print(f"  扫描文件: {scanned}")
    print(f"  违规行: {len(violations)}")
    if violations:
        for path, lineno, line in violations:
            rel = path.relative_to(PROJECT_ROOT) if PROJECT_ROOT in path.parents else path
            print(f"  [MARKER] {rel}:{lineno}: {line[:_SNIPPET_MAX]}")
        print("\nFAIL: 提交内容含合并冲突标记，请解决冲突后再提交。")
        return 1
    print("\nPASS: 未发现冲突标记。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
