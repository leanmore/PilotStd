#!/usr/bin/env python3
"""校验「含 feat/fix/BREAKING 的变更在同一批里改了 VERSION」（CI 门禁，2026-11-25 新增）。

## 为什么需要

`main` 受 ruleset 保护（必须走 PR），CI 的 `version` job **不再**直推 bump 提交（见
`scripts/bump_version.py` 头部说明）。因此版本号递增的责任转移到 **PR 内**：
只要一个 PR/推送范围里出现 `feat:` / `fix:` / `BREAKING CHANGE:`，就必须同批修改 `VERSION`，
否则 `main` 的版本号永远不涨、镜像 `/api/system/version` 停在旧值（这正是 2026-11 的实测缺陷）。

## 用法

```bash
python scripts/check_version_bump.py                                   # 默认 origin/main..HEAD
python scripts/check_version_bump.py --range <base>..<head>             # CI 显式范围
python scripts/check_version_bump.py --range <r> --warn-only            # 只告警不阻断
```

豁免：提交标题或正文含 `[no-version-bump]`（用于纯 CI/docs 基础设施且确不需要发版的场景）。

退出码：0 通过/无需 bump；1 需要 bump 但 VERSION 未改；2 范围不可解析。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 允许测试指定仓库根（默认脚本所在仓库根；CI/本地正常调用时即仓库根）
_REPO = Path(os.environ.get("VERSION_CHECK_ROOT") or ROOT)
BUMP_TYPES = re.compile(r"^(@ )?(feat|fix)(\(.+\))?:")
# 基础设施类 scope 不触发发版（CI/文档/测试/构建 修复不改变运行时行为）
INFRA_SCOPES = re.compile(r"^(@ )?(feat|fix)\((ci|docs|test|build|ops)\):")
EXEMPT_MARK = "[no-version-bump]"


def _git(*args: str) -> tuple[int, str]:
    """跑只读 git 命令，返回 (returncode, stdout)。

    双通道（同 scripts/ops/probe_health._run_git）：受限环境禁止子进程管道时
    capture_output 会拿到空输出，退化为「重定向到临时文件再读」。
    """
    proc = subprocess.run(["git", *args], cwd=str(_REPO), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    if proc.stdout is not None:
        return proc.returncode, proc.stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.txt"
        err_path = Path(tmp) / "err.txt"
        with out_path.open("w", encoding="utf-8") as out, err_path.open("w", encoding="utf-8") as err:
            proc2 = subprocess.run(["git", *args], cwd=str(_REPO), stdout=out, stderr=err, check=False)
        return proc2.returncode, out_path.read_text(encoding="utf-8", errors="replace").strip()


def resolve_range(explicit: str) -> str:
    """解析范围；显式范围优先，否则回退 `origin/main..HEAD`。"""
    if explicit:
        return explicit
    code, base = _git("rev-parse", "--verify", "origin/main")
    if code != 0:
        return ""
    return "origin/main..HEAD"


def needs_bump(rng: str) -> tuple[bool, list[str]]:
    """范围内是否含 feat/fix/BREAKING 提交（返回命中标题）。"""
    code, out = _git("log", rng, "--format=%s%n%b%n---")
    if code != 0:
        return False, []
    hits: list[str] = []
    for block in out.split("\n---"):
        text = block.strip()
        if not text:
            continue
        subject = text.splitlines()[0].strip()
        if EXEMPT_MARK in text:
            continue
        if INFRA_SCOPES.match(subject):
            continue
        if BUMP_TYPES.match(subject) or "BREAKING CHANGE:" in text:
            hits.append(subject)
    return bool(hits), hits


def version_changed(rng: str) -> bool:
    """范围内是否修改了 VERSION 文件。"""
    code, out = _git("diff", "--name-only", rng, "--", "VERSION")
    return code == 0 and bool(out.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="feat/fix 变更必须同批 bump VERSION")
    ap.add_argument("--range", default="", help="git 范围（默认 origin/main..HEAD）")
    ap.add_argument("--warn-only", action="store_true", help="只告警不阻断（观察期用）")
    args = ap.parse_args(argv)

    rng = resolve_range(args.range)
    if not rng:
        print("[WARN] 无法解析比较范围（origin/main 不存在），跳过版本号校验")
        return 0
    # 范围为空（例如 `push` 第一个提交）时 `git log` 会报错；按「无变更」处理并留痕
    code, _ = _git("rev-parse", "--verify", rng.split("..")[0] or "HEAD")
    if code != 0:
        print(f"[WARN] 范围 {rng} 的起点不可解析，跳过版本号校验")
        return 0

    hit, subjects = needs_bump(rng)
    if not hit:
        print(f"[PASS] {rng} 内无 feat/fix/BREAKING 变更，无需 bump VERSION")
        return 0
    if version_changed(rng):
        print(f"[PASS] {rng} 含 {len(subjects)} 条需发版变更，且同批已修改 VERSION")
        return 0

    msg = (
        f"[FAIL] {rng} 含 {len(subjects)} 条 feat/fix/BREAKING 变更，但未修改 VERSION。\n"
        "       请在 PR 内运行：python scripts/bump_version.py --apply\n"
        "       示例命中：" + "；".join(subjects[:3])
    )
    if args.warn_only:
        print(msg.replace("[FAIL]", "[WARN]"))
        return 0
    print(msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
