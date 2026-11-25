#!/usr/bin/env python3
"""版本号 bump 工具（本地/PR 内使用）。

## 背景（2026-11-25 修复版本号不升级缺陷）

仓库 `main` 受 ruleset `main-protection` 保护（**必须走 PR**）。原 CI `version` job 用
`GITHUB_TOKEN` **直推 bump 提交到 main** → 被规则拒绝；脚本吞掉 push 失败后仍打 tag，
于是 tag 指向未推送的本地提交 ⇒ **孤儿 tag**（实测 `v0.206.1`/`v0.207.0`），
而 main 的 `VERSION` 永不递增、镜像 `/api/system/version` 永远停在旧值。

新流程：**bump 在 PR 内完成**（本脚本），CI `version` job 只做「校验 + 打 tag」，不再推送。

## 用法

```bash
python scripts/bump_version.py            # 预览将要 bump 到的版本（不写文件）
python scripts/bump_version.py --apply    # 写入 VERSION / __init__.py / CHANGELOG
python scripts/bump_version.py --check    # CI 用：VERSION 与「按 commit 计算出的版本」不一致则 exit 1
```

规则（与 `scripts/version.py` 同一实现）：
- `BREAKING CHANGE:` → major+1；
- `feat:` → minor+1；
- `fix:` → patch+1；
- 都没有 → 不 bump（`--check` 通过，`--apply` 打印无变化）。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
INIT_FILE = ROOT / "pilotstd" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def _git(*args: str) -> str:
    """跑只读 git 命令并返回 stdout（双通道：受限环境退化到文件重定向）。"""
    proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    if proc.stdout is not None:
        return proc.stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.txt"
        with out_path.open("w", encoding="utf-8") as out:
            subprocess.run(["git", *args], cwd=str(ROOT), stdout=out, stderr=subprocess.DEVNULL, check=False)
        return out_path.read_text(encoding="utf-8", errors="replace").strip()


def last_tag() -> str:
    """最近一个**可从 HEAD 到达**的 tag（含  前缀；孤儿 tag 不会污染基准版本）。"""
    return _git("describe", "--tags", "--abbrev=0")


def commit_messages_since(tag: str) -> list[str]:
    """取基准 tag 之后到 HEAD 的提交标题。"""
    out = _git("log", f"{tag}..HEAD", "--format=%s") if tag else _git("log", "--format=%s")
    return [line for line in out.splitlines() if line.strip()]


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def compute_next(base: str, messages: list[str]) -> str | None:
    """按语义化规则计算下一版本；无需 bump 返回 None（复用 `scripts/version.py` 的实现）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from version import bump_version  # noqa: PLC0415  复用单一实现

    return bump_version(base, messages)


def write_version(new_version: str) -> None:
    """写入 VERSION、`pilotstd/__init__.py` 与 CHANGELOG 新条目。"""
    VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")
    init_text = INIT_FILE.read_text(encoding="utf-8")
    init_text = re.sub(
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
        init_text,
        count=1,
        flags=re.MULTILINE,
    )
    INIT_FILE.write_text(init_text, encoding="utf-8")
    if CHANGELOG.exists():
        content = CHANGELOG.read_text(encoding="utf-8")
        if f"## v{new_version} " not in content:
            entry = (
                f"## v{new_version} ({date.today().isoformat()})\n\n"
                "### Fixed\n- 版本号随 PR 递增（发布流程修复）\n\n"
            )
            idx = content.find("\n")
            content = content[: idx + 1] + entry + content[idx + 1 :] if idx >= 0 else entry + content
            CHANGELOG.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """入口：预览 / 写入 / 校验三选一（`--apply` / `--check`）。"""
    # 解析命令行参数：默认预览，不写任何文件
    ap = argparse.ArgumentParser(description="版本号 bump（PR 内执行）")
    ap.add_argument("--apply", action="store_true", help="写入 VERSION/__init__.py/CHANGELOG")
    ap.add_argument("--check", action="store_true", help="校验 VERSION 是否已等于应有版本（CI 用）")
    args = ap.parse_args(argv)

    tag = last_tag()
    base = tag[1:] if tag.startswith("v") else tag
    base = base or "0.0.0"
    current = read_version()
    messages = commit_messages_since(tag)
    expected = compute_next(base, messages)

    if args.check:
        if expected is None:
            print(f"[OK] 自 v{base} 起无 feat/fix/BREAKING，无需 bump（当前 VERSION={current}）")
            return 0
        if current == expected:
            print(f"[OK] VERSION={current} 与提交计算的版本一致（基准 v{base}）")
            return 0
        print(
            f"[FAIL] VERSION={current}，但自 v{base} 起的提交应 bump 到 {expected}。\n"
            f"       请在 PR 内运行：python scripts/bump_version.py --apply",
            file=sys.stderr,
        )
        return 1

    if expected is None:
        print(f"[SKIP] 自 v{base} 起无 feat/fix/BREAKING，无需 bump（当前 VERSION={current}）")
        return 0
    if expected == current:
        print(f"[SKIP] VERSION 已是 {current}（基准 v{base}），无需再 bump")
        return 0

    print(f"[BUMP] v{base} → {expected}（当前 VERSION={current}，提交 {len(messages)} 条）")
    if args.apply:
        write_version(expected)
        print("[已写入] VERSION / pilotstd/__init__.py / CHANGELOG.md")
    else:
        print("[预览] 加 --apply 才会写入文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
