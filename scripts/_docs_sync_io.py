#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs 联动同步检查 · **git/IO/Claude 助手族**（T-41/2-B 从 `docs_sync_check.py` 拆出，守 G-010）。

职责：git 差异与提交信息读取、触发条件判定、Claude 调用与文件读写。
主模块按原样**再导出**这些名字 ⇒ 既有调用方与（按文件路径加载主模块的）测试不受影响。
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "STATUS.md"
VERSION_FILE = PROJECT_ROOT / "pilotstd/__init__.py"


# 判定：pilotstd/ 下是否有 .py 新增/删除/重命名——需同步「模块与功能清单」文档。
def _has_new_or_deleted_pyfiles(staged_tuples):
    """pilotstd/ 下 .py 文件新增/删除/重命名"""
    for status, filepath in staged_tuples:
        p = Path(filepath)
        if str(p).startswith("pilotstd") and p.suffix == ".py" and status[0] in ("A", "D", "R"):
            return True
    return False


# 判定：diff 中是否出现新的 *Handler 类或移除 *Mixin——架构模式变化需同步架构文档。
def _has_handler_or_mixin_change(_tuples, diff_text):
    """diff 中出现新的 *Handler 类或移除了 *Mixin"""
    return bool(re.search(r"^[+-].*class \w+(Handler|Mixin)\b", diff_text, re.MULTILINE))


# 判定：测试文件数是否大幅变化——测试规模变化需同步覆盖率/技术债说明。
def _test_files_changed_significantly(staged_tuples):
    """tests/ 下 .py 文件增减数 >= 3"""
    added = deleted = 0
    for status, fp in staged_tuples:
        if fp.startswith("tests") and fp.endswith(".py"):
            if status[0] == "A":
                added += 1
            elif status[0] == "D":
                deleted += 1
    return abs(added - deleted) >= 3


# 判定：是否改动 docker/——容器与 API 变更需同步架构文档。
def _has_docker_changes(staged_tuples):
    return {"Dockerfile", "docker-compose.yml"} & {Path(f).name for _, f in staged_tuples}


# 判定：是否改动 docs/index.md 或 README——索引类文档自身变更不触发二次提醒。
def _has_index_or_readme_changes(staged_tuples):
    return any(fp in ("docs/index.md", "README.md") for _, fp in staged_tuples)


# 判定：是否改动 .github/workflows/——CI 变更需同步 CI 教训与门禁清单。
def _has_workflow_changes(staged_tuples):
    return any(fp.startswith(".github/workflows/") for _, fp in staged_tuples)


# 判定：是否存在任意源码改动（兜底规则用）。
def _has_any_source_change(staged_tuples):
    return any(fp.startswith(("pilotstd/", "docker/", "web/src/", "tests/")) for _, fp in staged_tuples)


# 判定：提交是否为 feat/fix —— 只有这两类才认为需要同步文档。
def _is_feat_or_fix_commit(commit_msg):
    fl = (commit_msg or "").strip().split("\n")[0]
    return bool(re.match(r"^(feat|fix)(\(.+\))?:", fl))


# 执行 git 命令并返回标准输出；失败返回空串（调用方按「无输出」处理，不抛异常）。
def _run_git(args):
    """运行 git 命令，返回 stdout（去除末尾换行）。失败返回空字符串。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
            cwd=PROJECT_ROOT,
        )
        return result.stdout.rstrip("\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


# 读取当前提交信息（优先 HEAD，回退到最近一次提交）。
def _get_commit_message():
    for p in [PROJECT_ROOT / ".git" / "COMMIT_EDITMSG", Path(os.getenv("GIT_DIR", "")) / "COMMIT_EDITMSG"]:
        if p and Path(p).exists():
            return Path(p).read_text(encoding="utf-8", errors="replace")
    return ""


# 调用 Claude 生成文档更新内容；不可用时返回空串，由调用方降级为「只提示不阻断」。
def _call_claude(prompt, timeout=120):
    """调用 claude CLI 并返回输出内容。失败返回 None。"""
    print(f"  调用 claude CLI（超时 {timeout}s）...", end=" ", flush=True)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            encoding="utf-8",
            timeout=timeout,
            env={**os.environ},
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            print("✓")
            return result.stdout.strip()
        else:
            print(f"✗ claude 返回码 {result.returncode}")
            if result.stderr:
                print(f"   stderr: {result.stderr[:500]}")
            return None
    except FileNotFoundError:
        print("✗ claude 命令未找到，请确认已安装 claude CLI 并在 PATH 中")
        return None
    except subprocess.TimeoutExpired:
        print(f"✗ claude 调用超时（{timeout}s）")
        return None
    except Exception as e:
        print(f"✗ claude 调用异常: {e}")
        return None


# 读取文本文件；不存在返回空串（避免调用方到处判空）。
def _read_file(path):
    """安全读取文件内容。"""
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


# 写回文档内容（调用方已确认路径在受控范围内）。
def _write_file(path, content):
    """写入文件，确保父目录存在。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  -> 已写入 {path.relative_to(PROJECT_ROOT)}")


# 把更新后的文档加入暂存区（供提交者复核后再提交）。
def _git_add(path):
    """暂存文件。"""
    path = Path(path)
    result = subprocess.run(
        ["git", "add", str(path)],
        capture_output=True,
        encoding="utf-8",
        timeout=30,
        cwd=PROJECT_ROOT,
    )
    if result.returncode == 0:
        print(f"  -> 已 git add {path.relative_to(PROJECT_ROOT)}")
    else:
        print(f"  -> git add 失败: {result.stderr.strip()}")


# 读取包版本号（用于文档中的版本标注）。
def _get_version():
    """从 pilotstd/__init__.py 读取版本号。"""
    content = _read_file(VERSION_FILE)
    m = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    return m.group(1) if m else "0.0.0"


# 探测 Claude 可用性：不可用时函数返回 False，主流程据此走「只提示」分支。
def _check_claude_available():
    """检查 claude 命令是否可用。"""
    try:
        subprocess.run(["claude", "--version"], capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

