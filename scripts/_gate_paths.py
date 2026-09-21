# 模块：脚本/门禁公共/路径判定脚本
"""门禁公共判定：哪些路径属于"入库产物"。

门禁只评判要进入仓库的内容。被 `.gitignore` 声明为本地草稿的路径（如 `logs/` 下的
一次性脚本、临时探针）不属于仓库内容，其注释密度 / 代码行数 / 命名等指标与仓库质量无关，
不应阻断与之无关的提交 —— 假阳性会逼人绕过门禁，与假绿同样有害
（判据见 docs/governance/governance-principles.md §3.4「只评判入库产物」）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_CACHE: dict[str, set[str]] = {}


def git_ignored_paths(root: Path) -> set[str]:
    """返回被 .gitignore 忽略的仓库内路径（相对 root，目录不带尾斜杠）。

    git 不可用、非仓库或超时时返回空集合，调用方行为回退为"不额外豁免"。
    """
    key = str(root)
    if key not in _CACHE:
        try:
            out = subprocess.run(
                ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--directory"],
                cwd=key,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            ).stdout
            _CACHE[key] = {line.strip().rstrip("/") for line in out.splitlines() if line.strip()}
        except Exception:  # noqa: BLE001 — git 缺失/超时不应让门禁崩溃
            _CACHE[key] = set()
    return _CACHE[key]


def is_git_ignored(filepath: Path, root: Path) -> bool:
    """判断文件是否落在 .gitignore 忽略范围内（按相对 root 的路径前缀匹配）。"""
    ignored = git_ignored_paths(root)
    if not ignored:
        return False
    try:
        rel = filepath.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:  # root 之外的文件不参与本判定
        return False
    return any(rel == item or rel.startswith(item + "/") for item in ignored)
