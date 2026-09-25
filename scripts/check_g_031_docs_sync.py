#!/usr/bin/env python3
"""G-031: 文档同步检查。

检查本次 PR 变更的核心模块是否同步更新了对应文档。
- 目标文档存在但未同步更新 → 阻断（exit 1）
- 目标文档不存在 → 按模式处理：`block` 同样阻断，`warn` 仅告警（当前 9 条均为 `block`）
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")

# 映射规则: (源路径前缀, 目标文档路径, 阻断模式)
# 源前缀必须是仓库中真实存在的路径，否则该条永不触发（= 死映射，门禁假绿）；
# 目标文档必须是"承载该源路径事实"的那一份——判据见 docs/governance/gates.md 的 G-031 条目：
# 这次变更改变了哪个事实、承载它的是哪份文档。源前缀按"最长匹配"归属唯一目标文档。
DOC_SYNC_MAP: list[tuple[str, str, str]] = [
    ("pilotstd/scan/parser/", "docs/architecture/modules/parser.md", "block"),
    ("pilotstd/query/adapters/", "docs/architecture/modules/query.md", "block"),
    ("pilotstd/scan/", "docs/architecture/modules/scan.md", "block"),
    ("pilotstd/ui/main_window/", "docs/architecture/modules/ui.md", "block"),
    ("pilotstd/manager/", "docs/architecture/modules/manager.md", "block"),
    # 2026-09-25 补齐长期缺口（技术债 #13/#14）：core.md 自述"G-031 映射 pilotstd/core/"
    # 却一直不在表里（改 core 文件不触发同步，文档可静默过期）；announcement-pipeline.md
    # 是 AGENTS.md §8.2 指定的 announcement 回写目标，同样一直未落地。
    ("pilotstd/core/", "docs/architecture/modules/core.md", "block"),
    ("pilotstd/announcement/", "docs/reference/announcement-pipeline.md", "block"),
    ("scripts/", "docs/governance/gates.md", "block"),
    (".github/workflows/", "docs/governance/gates.md", "block"),
    ("docs/governance/", "docs/governance/README.md", "block"),
    ("docs/adr/", "docs/adr/README.md", "block"),
]

# 机器生成产物豁免：内容由脚本生成、且已登记在目标文档索引中，重生成只改时间戳/行号，
# 不改变索引语义。AGENTS.md §七 又强制其随代码变更一并提交，若不豁免，每次重生成能力矩阵
# 都会撞上"docs/governance/ 需同步 README"，只能靠装饰性改动或绕过门禁过关。
GENERATED_DOCS: set[str] = {"docs/governance/capabilities_registry.md"}

# 仅"新增/删除"才联动的源前缀：只改内容时，目标文档承载的事实没变，不应牵连它。
# 判据是"这次变更改变了哪个事实、承载它的是哪份文档"：改某个架构决策正文只影响那份决策自身，
# "系统有哪些决策"这份清单（docs/adr/README.md）并未变化。
ADD_DELETE_ONLY_PREFIXES: set[str] = {"docs/adr/"}


def _run_diff(args: list[str]) -> list[tuple[str, str]]:
    """执行 git diff --name-status，返回 (状态, 路径) 列表；重命名取新旧两条路径。"""
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True, cwd=str(ROOT))
    except subprocess.CalledProcessError:
        print(f"[G-031] WARN: 无法获取 diff ({' '.join(args)})，跳过该来源")
        return []
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) >= 2:
            entries.extend((parts[0], path) for path in parts[1:])
    return entries


def get_changed_entries() -> list[tuple[str, str]]:
    """返回本次待提交/已提交的 (git 状态, 文件) 列表（相对于 base branch）。

    本地提交前（pre-commit）时，待提交内容还在暂存区、尚未进入 HEAD，
    仅看 `origin/base..HEAD` 会漏掉"正要提交的这一次改动"，门禁等于空转。
    因此同时并入暂存区变更（`git diff --cached`），使本地提交时即可拦住
    "改了代码却忘了同步文档"。

    状态取 git 首字母：`A` 新增 / `D` 删除 / `M` 修改 / `R` 重命名。
    """
    entries: list[tuple[str, str]] = []
    for args in (
        ["git", "diff", "--name-status", f"origin/{BASE_BRANCH}..HEAD"],
        ["git", "diff", "--name-status", "--cached"],
    ):
        entries.extend(_run_diff(args))
    return entries


def _exemption_reason(src_prefix: str, matched: list[str], structural_changes: set[str]) -> str | None:
    """返回豁免原因；None 表示不豁免。豁免一律显式打印，不静默跳过。"""
    if all(f in GENERATED_DOCS for f in matched):
        return "为机器生成产物"
    if src_prefix in ADD_DELETE_ONLY_PREFIXES and not any(f in structural_changes for f in matched):
        return "仅内容修订（无新增/删除/重命名）"
    return None


def main() -> int:
    entries = get_changed_entries()
    changed = sorted({p.replace("\\", "/") for _, p in entries})
    if not changed:
        print("[G-031] PASS: 无变更文件")
        return 0

    changed_set = set(changed)
    # 新增/删除/重命名都改变"有哪些文件"这份事实，供"仅结构性变更才联动"的规则使用
    structural_changes = {p.replace("\\", "/") for st, p in entries if st[:1] in ("A", "D", "R")}

    # 每个变更文件按其最长匹配前缀归属唯一目标文档：一份事实只由一份文档承载，
    # 避免"改了 scan/parser/ 还要顺带碰 scan.md"这类形式联动。
    prefixes = [src for src, _, _ in DOC_SYNC_MAP]
    requirements: dict[str, list[str]] = {}
    for f in changed_set:
        best = max((p for p in prefixes if f.startswith(p)), key=len, default=None)
        if best:
            requirements.setdefault(best, []).append(f)

    failures: list[str] = []
    warnings: list[str] = []

    for src_prefix, doc_path, mode in DOC_SYNC_MAP:
        # 检查是否有变更文件归属该源路径
        matched = sorted(requirements.get(src_prefix, []))
        if not matched:
            continue

        reason = _exemption_reason(src_prefix, matched, structural_changes)
        if reason:
            print(f"[G-031] SKIP: {'、'.join(sorted(matched))} {reason}，豁免 {doc_path} 同步要求")
            continue

        # 检查目标文档是否在变更列表中
        doc_changed = doc_path in changed_set

        if doc_changed:
            print(f"[G-031] OK: {src_prefix} → {doc_path} 已同步更新")
            continue

        # 文档未被修改 — 检查文档是否存在
        doc_full = ROOT / doc_path
        if doc_full.exists():
            failures.append(f"[G-031] FAIL: {src_prefix} 已变更，但 {doc_path} 未同步更新")
        else:
            msg = f"[G-031] WARN: {src_prefix} 已变更，但 {doc_path} 不存在（目标文档待创建）"
            if mode == "warn":
                warnings.append(msg)
            else:
                failures.append(msg)

    # 汇总
    for w in warnings:
        print(f"  {w}")

    if failures:
        print(f"\n{len(failures)} 项文档同步失败:")
        for f in failures:
            print(f"  {f}")
        print("\nFAIL: 请同步更新上述文档后再提交。")
        return 1

    if warnings:
        print(f"\n{len(warnings)} 项告警（不阻断）")

    print("PASS: 文档同步检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
