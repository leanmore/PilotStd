#!/usr/bin/env python3
"""文档同步门禁：核心模块变更时检查对应架构文档是否同步更新。

变更来源回退链（T-25，2026-09-27 修复）：
  `--range A..B` → 环境变量 `DOCS_SYNC_RANGE` → `--base`/`BASE_BRANCH`（`origin/<base>...HEAD`）
  → `origin/main...HEAD` → `HEAD~1..HEAD` → 无变更。

**为什么需要这条回退链**：原实现只做 `git diff --name-only origin/<base>..HEAD`——CI 推送到 main 时
`origin/main` 与 `HEAD` 相同（浅克隆下甚至不存在）→ 恒"无变更文件"、恒 `exit 0`，
该 CI 步骤因此长期空转（2026-09-27 第十一轮 T-25 事故：CI 的 `Docs sync check` 步骤名与
`scripts/docs_sync_check.py` 形近，实际调用的是本脚本，而本脚本又恒绿 → 双重空转）。

严格模式语义（与 `docs_sync_check.py --strict` 对齐）：
  `--strict`       告警期——发现未同步时打印 `[docs-compliance] WARN(告警期)` 并 **仍 `exit 0`**（绝不静默 PASS）
  `--strict-block` 阻断期——发现未同步时 `exit 1`
  不带标志        保持历史行为（发现未同步即 `exit 1`）
"""

import os
import subprocess
import sys
from pathlib import Path

# 控制台编码兼容（Windows 控制台无法输出叉号与中文，实测会抛编码异常并造成假性非零退出码）
# 后果说明：该异常发生在“告警期本该返回零”的分支之前，会让本地复跑被误判成阻断失败。
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parent.parent
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")

# 核心模块变更 → 必须同步更新的架构文档
DOC_COVERAGE_MAP: dict[str, str] = {
    "pilotstd/core/": "docs/architecture/modules/core.md",
    "pilotstd/query/": "docs/architecture/modules/query.md",
    "pilotstd/scan/": "docs/architecture/modules/scan.md",
    "pilotstd/ui/": "docs/architecture/modules/ui.md",
    "pilotstd/manager/": "docs/architecture/modules/manager.md",
}


def _run_git(args: list[str]) -> str:
    """运行 git 命令返回 stdout；失败返回空串（不抛异常，交调用方判定）。"""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _split_range(rng: str) -> tuple[str, str]:
    """切分 `A..B` / `A...B`；返回 (left, right)。"""
    rng = (rng or "").strip()
    for sep in ("...", ".."):
        if sep in rng:
            left, _, right = rng.partition(sep)
            return left.strip(), right.strip()
    return "", ""


def _range_is_valid(rng: str) -> bool:
    """两端点都能 rev-parse 才有效（CI 上 before 可能是空串或全 0 SHA）。"""
    left, right = _split_range(rng)
    if not right:
        return False
    left = left.strip(".") or "HEAD"
    right = right.strip(".") or "HEAD"
    if set(left) == {"0"} or set(right) == {"0"}:
        return False
    return all(_run_git(["rev-parse", "--verify", f"{rev}^{{commit}}"]).strip() for rev in (left, right))


def parse_args(argv: list[str]) -> dict:
    """解析 `--range` / `--base` / `--strict` / `--strict-block`。"""
    opts = {"range": None, "base": None, "strict": False, "strict_block": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--range" and i + 1 < len(argv):
            opts["range"] = argv[i + 1].strip()
            i += 2
            continue
        if a == "--base" and i + 1 < len(argv):
            opts["base"] = argv[i + 1].strip()
            i += 2
            continue
        if a == "--strict":
            opts["strict"] = True
            i += 1
            continue
        if a == "--strict-block":
            opts["strict"] = True
            opts["strict_block"] = True
            i += 1
            continue
        i += 1
    return opts


def resolve_range(opts: dict) -> tuple[str | None, str]:
    """按回退链选出变更范围，返回 (range 或 None, 说明)。

    R11-3 加固：候选必须**确实含变更文件**才命中。仅"两端可 rev-parse"但 diff 为空的候选
    （推送到 main 时 origin/main...HEAD 即如此）继续向下回退到 HEAD~1..HEAD，
    绝不落成"无变更文件"的静默空转；`--range` 为调用方硬指定，不做非空过滤。
    """
    # R11-3：严格模式（CI 告警期/阻断期）下要求候选范围确实含变更文件；非严格模式（本地辅助，
    # 可能调用 claude 改写文档）保持“暂存区优先”的旧行为，避免把历史提交误当成本次变更。
    require_changes = bool(opts["strict"])
    candidates: list[tuple[str, str, bool]] = []
    if opts["range"]:
        candidates.append((opts["range"], "--range 指定", True))
    env_range = os.environ.get("DOCS_SYNC_RANGE", "").strip()
    if env_range:
        candidates.append((env_range, "环境变量 DOCS_SYNC_RANGE", False))
    base = (opts["base"] or BASE_BRANCH).strip()
    if base:
        candidates.append((f"origin/{base}...HEAD", f"BASE_BRANCH={base}", False))
    candidates.append(("origin/main...HEAD", "origin/main...HEAD", False))
    candidates.append(("HEAD~1..HEAD", "HEAD~1..HEAD", False))
    empty_fallback: tuple[str, str] | None = None
    for rng, why, hard in candidates:
        if not _range_is_valid(rng):
            continue
        if hard or not require_changes or _range_has_changes(rng):
            return rng, why
        if empty_fallback is None:
            empty_fallback = (rng, f"{why}，该范围无变更")
    return empty_fallback or (None, "无可用范围（无法取到变更）")


def _range_has_changes(rng: str) -> bool:
    """该范围是否确实含变更文件（R11-3：空范围不得作为来源，否则门禁空转仍显通过）。"""
    return bool(get_changed_files(rng))



def get_changed_files(rng: str | None) -> list[str]:
    """取变更文件列表；rng 为 None 时返回空表（由调用方打印"无变更"）。"""
    if not rng:
        return []
    out = _run_git(["diff", "--name-only", rng])
    return [f.strip() for f in out.strip().split("\n") if f.strip()]


def check(changed: list[str]) -> list[str]:
    """返回"未同步"的失败描述列表。"""
    failures: list[str] = []
    for src_prefix, doc_path in DOC_COVERAGE_MAP.items():
        changed_src = [f for f in changed if f.startswith(src_prefix)]
        if not changed_src:
            continue
        if any(f == doc_path for f in changed):
            print(f"[docs-compliance] OK: {src_prefix} 变更已同步文档 {doc_path}")
            continue
        doc_exists = (ROOT / doc_path).exists()
        if doc_exists:
            failures.append(
                f"  ❌ {src_prefix} 模块变更但未更新 {doc_path}\n"
                f"     变更文件: {', '.join(changed_src[:3])}"
                + (f" ...共{len(changed_src)}个" if len(changed_src) > 3 else "")
            )
        else:
            failures.append(f"  ❌ {src_prefix} 模块缺少架构文档 {doc_path}\n     请先创建 {doc_path} 再合入")
    return failures


def main() -> int:
    """入口：检查核心模块变更是否同步更新了对应架构文档。"""
    opts = parse_args(sys.argv[1:])
    rng, why = resolve_range(opts)
    mode = "阻断期" if opts["strict_block"] else ("告警期" if opts["strict"] else "历史行为")
    print(f"[docs-compliance] 变更来源: {rng or '无'}（{why}）｜模式: {mode}")

    changed = get_changed_files(rng)
    if not changed:
        print(f"[docs-compliance] PASS: 无变更文件（{why}）")
        return 0

    failures = check(changed)
    if not failures:
        print("[docs-compliance] PASS: 所有核心模块变更已同步文档")
        return 0

    if opts["strict"] and not opts["strict_block"]:
        # 告警期：必须显式标注未阻断，绝不允许表现成静默通过（第十一轮用户约束）
        # 判定为“未同步”时仍返回零，但日志必须同时给出三要素：来源范围、未同步条数、未阻断声明。
        print(f"[docs-compliance] WARN(告警期): {len(failures)} 项文档未同步 —— **未阻断**（exit 0）")
        for f in failures:
            print(f)
        print("[docs-compliance] 告警期说明：切阻断期请把 CI 该步骤的 --strict 改为 --strict-block")
        return 0

    label = "FAIL(阻断)" if opts["strict_block"] else "FAIL"
    print(f"[docs-compliance] {label}: {len(failures)} 项文档未同步")
    for f in failures:
        print(f)
    return 1


if __name__ == "__main__":
    sys.exit(main())
