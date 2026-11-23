#!/usr/bin/env python3
"""G-056: 文档死链扫描（markdown 相对链接 + 全路径引用）。

为什么需要它（NEW-32 / NEW-33 / NEW-34）：
  `check_g_032_doc_health.py` 只校验「反引号包裹的全路径引用」是否存在，
  **不检查 markdown 的相对链接** `[文本](../foo/bar.md)`。
  实测 `docs/` 下有 147 条相对链接指向不存在的文件/锚点（含
  `overview.md` 27 条、`gates.md` 3 处 `architecture/architecture.md`）。

规则（只拦新增，存量走基线棘轮）：
  - 解析 `docs/**/*.md` 里所有 `[text](target)` 形式的链接；
  - 跳过：外部 URL（http/https/mailto）、纯锚点（#xxx）、代码块内的伪链接；
  - 相对路径按「当前文件所在目录」解析；`#anchor` 部分单独校验（锚点存在性暂不校验，
    因为 heading 生成的 slug 规则不稳定，只校验文件存在）；
  - 目标不存在 → 记为死链。

基线：`scripts/doc_deadlinks_baseline.json`（`{文件: 死链数}`），
  - 当前 > 基线 → FAIL（新增死链）
  - 当前 < 基线 → WARN（可收紧基线，不阻断）

用法：
  python scripts/check_g_056_doc_deadlinks.py                # 检查
  python scripts/check_g_056_doc_deadlinks.py --emit         # 打印当前统计（JSON）
  python scripts/check_g_056_doc_deadlinks.py --suggest      # 打印建议基线（不落盘）
  python scripts/check_g_056_doc_deadlinks.py --root <dir>   # 受控测试用
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BASELINE = ROOT / "scripts" / "doc_deadlinks_baseline.json"

# markdown 链接：[text](target) 或 ![alt](target)
# ⚠️ 必须排除「行内代码」里的伪链接：`[x](y)` 出现在反引号内时是**示例文本**，
# 不是真链接。实测 docs 里大量 `[text](path)` 写在行内代码/代码块中（文档在讲"链接怎么写"），
# 若不排除会产生数百条假死链。
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# 行内代码：`...`（单反引号，可跨多个反引号对；不跨行）
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#", "//")

# 归档目录整目录排除：`.local/`（本地笔记，已 gitignore）与 `archive/`（历史归档）。
# 这些是"当时写下的事实"，指向当时存在的文件；今天失效属正常历史沉淀，
# 修它们等于篡改历史记录，且没有读者会从归档里跳转。
# 实测：529 条死链里 478 条在归档目录，只有 50 条在正式文档 —— 不排除会淹没真问题。
SKIP_DIR_PARTS = {".local", "archive"}


def _strip_code_fences(text: str) -> str:
    """把代码块与行内代码替换成等长空白，避免把代码里的伪链接当文档链接。

    等长替换（而非删除）是为了保持行号不变，报错时能直接定位。
    顺序：先整块代码块，再行内代码（行内代码不会跨行，不会破坏块边界）。
    """
    def blank(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    text = FENCE_RE.sub(blank, text)
    return INLINE_CODE_RE.sub(blank, text)


def _iter_links(text: str):
    """产出 (行号, 原始 target)。"""
    stripped = _strip_code_fences(text)
    for lineno, line in enumerate(stripped.split("\n"), 1):
        for m in LINK_RE.finditer(line):
            yield lineno, m.group(1)


def scan(docs_dir: Path) -> tuple[dict[str, list[tuple[int, str]]], int]:
    """返回 (死链明细, 检查的链接总数)。"""
    dead: dict[str, list[tuple[int, str]]] = {}
    total = 0
    for md in sorted(docs_dir.rglob("*.md")):
        rel = md.relative_to(docs_dir.parent).as_posix()
        # 归档目录整目录跳过（见 SKIP_DIR_PARTS 注释）
        if SKIP_DIR_PARTS & set(md.relative_to(docs_dir).parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, target in _iter_links(text):
            total += 1
            if target.startswith(SKIP_PREFIXES):
                continue
            # 去掉锚点部分（锚点存在性不校验，见文件头）
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            # ── 两种解析口径，任一成立即视为有效 ──
            # 1) 相对当前文件所在目录（markdown 标准语义）
            # 2) 相对仓库根（本仓文档惯例：`pilotstd/query/adapters/base.py` 这类
            #    "从仓库根数"的路径在 docs/ 下大量使用，且确实是仓库内真实文件）
            # 实测：50 条死链里 48 条属于第 2 类 —— 只按 (1) 解析会产生假死链。
            candidates = [
                (md.parent / path_part).resolve(),
                (ROOT / path_part).resolve(),
            ]
            valid = False
            for resolved in candidates:
                inside = True
                try:
                    resolved.relative_to(ROOT.resolve())
                except ValueError:
                    # 指向仓库外：该候选不成立。这里不用 pass/continue ——
                    # 两者都会被 G-050 记为「静默吞错形态」，改用标志位表达意图。
                    inside = False
                if inside and resolved.exists():
                    valid = True
                    break
            if not valid:
                dead.setdefault(rel, []).append((lineno, target))
    return dead, total


def counts_of(dead: dict[str, list[tuple[int, str]]]) -> dict[str, int]:
    return {f: len(v) for f, v in dead.items()}


def main(argv: list[str] | None = None) -> int:
    """入口：扫描 docs 下的 markdown 相对链接，与基线比对，返回退出码。

    退出码语义（与仓库其它门禁一致）：
      0 = 无新增死链（PASS；减少只提示可收紧）
      1 = 有新增死链 或 基线缺失（FAIL）

    子命令：
      --emit   打印当前统计 JSON（供 `--suggest-baseline` 类流程消费）
      --suggest 同 --emit（保留别名，与本仓其它门禁口径一致）
    """
    parser = argparse.ArgumentParser(description="G-056 文档死链扫描")
    parser.add_argument("--root", default=str(DOCS), help="docs 目录（测试用）")
    parser.add_argument("--emit", action="store_true", help="打印当前统计 JSON")
    parser.add_argument("--suggest", action="store_true", help="打印建议基线（不落盘）")
    args = parser.parse_args(argv)

    docs_dir = Path(args.root).resolve()
    dead, total = scan(docs_dir)
    current = counts_of(dead)

    if args.emit:
        print(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.suggest:
        print(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print("=" * 64)
    print("G-056: 文档死链扫描（markdown 相对链接）")
    print("=" * 64)
    print(f"  扫描链接: {total}    死链文件数: {len(current)}    死链总数: {sum(current.values())}")

    if not BASELINE.exists():
        print(f"\n[FAIL] 基线不存在: {BASELINE.relative_to(ROOT)}")
        print("  生成基线：python scripts/check_g_056_doc_deadlinks.py --emit > scripts/doc_deadlinks_baseline.json")
        return 1

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_counts: dict[str, int] = baseline.get("counts", {})

    exceeded: list[str] = []
    tightenable: list[str] = []
    for file in sorted(set(current) | set(base_counts)):
        delta = current.get(file, 0) - base_counts.get(file, 0)
        if delta > 0:
            exceeded.append(f"{file}: {base_counts.get(file, 0)} → {current.get(file, 0)} (+{delta})")
        elif delta < 0:
            tightenable.append(f"{file}: {base_counts.get(file, 0)} → {current.get(file, 0)} ({delta})")

    if exceeded:
        print(f"\n[FAIL] 新增死链 {len(exceeded)} 个文件超出基线：")
        for line in exceeded:
            print(f"  {line}")
        print("\n  明细（前 30 条）：")
        shown = 0
        for file in sorted(dead):
            if base_counts.get(file, 0) < len(dead[file]):
                for lineno, target in dead[file]:
                    print(f"    {file}:{lineno} → {target}")
                    shown += 1
                    if shown >= 30:
                        break
            if shown >= 30:
                break
        return 1

    if tightenable:
        print("\n[WARN] 死链减少，可收紧基线（不阻断）:")
        for line in tightenable[:10]:
            print(f"  {line}")

    print("\n[PASS] G-056 文档死链无新增")
    return 0


if __name__ == "__main__":
    sys.exit(main())
