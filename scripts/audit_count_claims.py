#!/usr/bin/env python3
"""G-052 第二阶段：改动窗口内的"计数类声明"全覆盖审计。

背景（P2-07 / 2026-11-14 裁定）：
- G-052 只校验 `COUNT_CLAIMS` 里登记过的 6 处写死数字；
- 用户裁定扩围口径为"**近 3 个月改动文档 ∩ 含计数类声明**"作分母，
  机器侧**全量**查"有没有声明/有没有理由"，人工侧季度抽检"理由真不真"。

本脚本只做机器侧：扫改动窗口内的文档，找出"计数类声明"，要求它
**要么登记在 COUNT_CLAIMS（由 G-052 校验数字），要么在豁免表里写明理由**。

设计约束：
- 变更窗口用 `git log --since`（可复现、无需 token；PR 变更需 API，不适合做门禁）；
- 分母不是"所有改动文档"，而是"改动文档里真的含计数声明的"——只改错别字的文档不误伤；
- 豁免必须写理由（`scripts/count_claims_exempt.json`），空理由按违规处理；
- 拿到不到 git 历史（浅克隆/非 git 环境）时降级为 WARN，不误红。

用法：
    python scripts/audit_count_claims.py                 # 审计（默认近 3 个月）
    python scripts/audit_count_claims.py --strict        # 有未声明项即 exit 1
    python scripts/audit_count_claims.py --since "6 months ago" --json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)
EXEMPT_PATH = ROOT / "scripts" / "count_claims_exempt.json"

# 计数类声明的"类型登记表"：只认这些口径明确的短语，避免把"N 个"这类泛数字全算进来。
# 新增类型前先确认：数字能从代码/事实里机械核对，否则只会制造误报。
CLAIM_TYPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("router 模块数", re.compile(r"(?<!\d)(\d+)\s*个 router 模块")),
    ("唯一 API 路径数", re.compile(r"(?<!\d)(\d+)\s*个唯一\s*`?/api`?\s*路径")),
    ("route×method 对数", re.compile(r"(?<!\d)(\d+)\s*个\s*route×method")),
    ("迁移可解析表数", re.compile(r"(?<!\d)(\d+)\s*张表")),
    ("迁移模块数", re.compile(r"(?<!\d)(\d+)\s*个迁移模块")),
)


def collect_changed_docs(since: str, root: Path | None = None) -> list[str] | None:
    """返回窗口内改动过的 docs/*.md（相对路径）；拿不到 git 历史时返回 None。"""
    try:
        proc = subprocess.run(
            ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
            cwd=str(root or ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # 非 git 环境 / 超时：交给调用方降级为 WARN，不在这里抛——门禁不能因环境差异误红
        logger.warning("git log 不可用，跳过计数声明审计: %s", exc)
        return None
    if proc.returncode != 0:
        return None
    docs = {
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip().startswith("docs/") and line.strip().endswith(".md")
    }
    return sorted(docs)


def scan_doc(text: str) -> list[tuple[str, str, int]]:
    """返回 [(类型, 数字, 行号)]；行号用于人工复核定位。"""
    hits: list[tuple[str, str, int]] = []
    for name, pattern in CLAIM_TYPES:
        for match in pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            hits.append((name, match.group(1), line_no))
    return hits


def load_exemptions(path: Path) -> tuple[dict[str, str], list[str]]:
    """读取豁免表，返回 (doc -> reason, 结构问题列表)。空理由视为结构问题。"""
    if not path.exists():
        return {}, []
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, str] = {}
    problems: list[str] = []
    # 空理由不构成豁免：否则白名单会退化成"看到红就加一条"，失去治理意义
    for doc, reason in (data.get("exemptions") or {}).items():
        text = str(reason or "").strip()
        if not text:
            problems.append(f"{doc}: 豁免缺少理由（空理由不算豁免）")
            continue
        entries[doc] = text
    return entries, problems


def declared_docs(root: Path | None = None) -> set[str]:
    """COUNT_CLAIMS 里已登记的文档（这些文档的数字由 G-052 校验）。"""
    sys.path.insert(0, str((root or ROOT) / "scripts"))
    import check_docs_drift  # noqa: PLC0415

    return {str(c.get("doc", "")) for c in check_docs_drift.COUNT_CLAIMS}


def check(
    changed: list[str],
    root: Path,
    exemptions: dict[str, str],
    declared: set[str],
) -> tuple[list[str], list[str], list[str]]:
    """返回 (违规, 提醒, 备注)。违规 = 计数声明既未登记也未豁免。"""
    failures: list[str] = []
    warns: list[str] = []
    notes: list[str] = []
    seen: set[str] = set()

    # 分母只算"改动且含计数声明"的文档：只改错别字的文档不误伤
    for rel in changed:
        path = root / rel
        if not path.exists():
            continue
        try:
            hits = scan_doc(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not hits:
            continue
        seen.add(rel)
        if rel in declared or rel in exemptions:
            continue
        sample = ", ".join(f"{name}={num}（L{line}）" for name, num, line in hits[:3])
        failures.append(f"{rel}: {len(hits)} 处计数声明未登记（{sample}）")

    for rel, reason in exemptions.items():
        if rel not in seen:
            warns.append(f"{rel}: 豁免已过期（近窗口内未再出现计数声明）——建议删除或更新理由：{reason}")
    for rel in declared:
        if rel not in seen:
            notes.append(f"{rel}: COUNT_CLAIMS 已登记但近窗口内无命中（可能数字已改表述）")

    return failures, warns, notes


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：审计改动窗口内的计数声明，`--strict` 时有未登记项即失败。"""
    parser = argparse.ArgumentParser(description="G-052 计数声明全覆盖审计（P2-07 第二阶段）")
    parser.add_argument("--since", default="3 months ago", help="git log 时间窗口")
    parser.add_argument("--strict", action="store_true", help="有未登记项时 exit 1")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--root", default=str(ROOT), help="仓库根（测试用）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    # 拿不到 git 历史时返回 None：CLI 降级 WARN，不阻断浅克隆/打包环境
    changed = collect_changed_docs(args.since, root)
    if changed is None:
        print("[WARN] 拿不到 git 历史（浅克隆/非 git 环境），跳过计数声明审计")
        return 0

    exemptions, problems = load_exemptions(root / "scripts" / "count_claims_exempt.json")
    declared = declared_docs(root)
    failures, warns, notes = check(changed, root, exemptions, declared)
    failures = problems + failures

    if args.json:
        print(json.dumps({"failures": failures, "warnings": warns, "notes": notes}, ensure_ascii=False))
    else:
        print(f"G-052 审计：窗口「{args.since}」改动 {len(changed)} 篇文档，"
              f"已登记 {len(declared)} 篇、豁免 {len(exemptions)} 篇")
        for note in notes:
            print(f"  [NOTE] {note}")
        for warn in warns:
            print(f"  [WARN] {warn}")
        for fail in failures:
            print(f"  [FAIL] {fail}")
        if not failures:
            print("PASS: 窗口内计数声明均有登记或豁免理由")

    if failures and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
