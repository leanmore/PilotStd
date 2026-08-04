#!/usr/bin/env python3
"""
Pre-commit 文档自动同步门禁。
检测暂存区变更 → 对照映射表识别需更新的文档 → 调用 claude 生成新内容 → git add。
环境变量: AUTO_FIX_DOCS=true|false（默认 true）; CLAUDE_TIMEOUT=120
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# ─── 路径常量 ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "STATUS.md"  # 项目状态文件
VERSION_FILE = PROJECT_ROOT / "pilotstd/__init__.py"  # 版本号来源


# ─── 触发判断函数 ────────────────────────────────────────────


def _has_new_or_deleted_pyfiles(staged_tuples):
    """pilotstd/ 下 .py 文件新增/删除/重命名"""
    for status, filepath in staged_tuples:
        p = Path(filepath)
        if str(p).startswith("pilotstd") and p.suffix == ".py" and status[0] in ("A", "D", "R"):
            return True
    return False


def _has_handler_or_mixin_change(_tuples, diff_text):
    """diff 中出现新的 *Handler 类或移除了 *Mixin"""
    return bool(re.search(r"^[+-].*class \w+(Handler|Mixin)\b", diff_text, re.MULTILINE))


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


def _has_docker_changes(staged_tuples):
    return {"Dockerfile", "docker-compose.yml"} & {Path(f).name for _, f in staged_tuples}


def _has_index_or_readme_changes(staged_tuples):
    return any(fp in ("docs/index.md", "README.md") for _, fp in staged_tuples)


def _has_workflow_changes(staged_tuples):
    return any(fp.startswith(".github/workflows/") for _, fp in staged_tuples)


def _has_any_source_change(staged_tuples):
    return any(fp.startswith(("pilotstd/", "docker/", "web/src/", "tests/")) for _, fp in staged_tuples)


def _is_feat_or_fix_commit(commit_msg):
    fl = (commit_msg or "").strip().split("\n")[0]
    return bool(re.match(r"^(feat|fix)(\(.+\))?:", fl))


# ─── 触发规则定义 ─────────────────────────────────────────────
TRIGGER_RULES = [
    {
        "name": "模块结构变化",
        "match_fn": _has_new_or_deleted_pyfiles,
        "targets": [("docs/specs/模块与功能清单.md", "claude", True)],
    },
    {
        "name": "架构模式变化（Handler/Mixin）",
        "match_fn": lambda t, d: _has_handler_or_mixin_change(t, d),
        "targets": [
            ("docs/architecture/architecture.md", "claude", True),
            ("docs/architecture/technical-debt-registry.md", "claude", True),
        ],
    },
    {
        "name": "测试文件数大幅变化",
        "match_fn": _test_files_changed_significantly,
        "targets": [("docs/development.md", "claude", True)],
    },
    {
        "name": "Docker 基础设施变更",
        "match_fn": _has_docker_changes,
        "targets": [("docs/guides/Docker使用指南.md", "claude", True)],
    },
    {
        "name": "索引/README 路径变更",
        "match_fn": _has_index_or_readme_changes,
        "targets": [("docs/index.md", "claude", True)],
    },
    {
        "name": "CI/CD 工作流变更",
        "match_fn": _has_workflow_changes,
        "targets": [("docs/development.md", "claude", True)],
    },
    {
        "name": "feat:/fix: 提交",
        "match_fn": lambda t, d, m: _is_feat_or_fix_commit(m),
        "targets": [("CHANGELOG.md", "claude", True)],
    },
    {
        "name": "源代码变更（通用 STATUS 更新）",
        "match_fn": _has_any_source_change,
        "targets": [("STATUS.md", "claude", False)],
    },
]


# ─── 工具函数 ────────────────────────────────────────────────


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


def _get_commit_message():
    for p in [PROJECT_ROOT / ".git" / "COMMIT_EDITMSG", Path(os.getenv("GIT_DIR", "")) / "COMMIT_EDITMSG"]:
        if p and Path(p).exists():
            return Path(p).read_text(encoding="utf-8", errors="replace")
    return ""


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


def _read_file(path):
    """安全读取文件内容。"""
    path = Path(path)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _write_file(path, content):
    """写入文件，确保父目录存在。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  -> 已写入 {path.relative_to(PROJECT_ROOT)}")


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


def _get_version():
    """从 pilotstd/__init__.py 读取版本号。"""
    content = _read_file(VERSION_FILE)
    m = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    return m.group(1) if m else "0.0.0"


def _check_claude_available():
    """检查 claude 命令是否可用。"""
    try:
        subprocess.run(["claude", "--version"], capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ───构建函数─────────────────────────────────────────


def _build_claude_prompt(doc_path, current_content, diff_text, commit_msg, trigger_name):
    """根据文档类型和变更内容构建传给 claude CLI 的提示词。"""
    doc_name = Path(doc_path).name
    prompts = {
        "模块与功能清单.md": (
            "你是文档维护助手。根据 git diff 更新模块清单："
            "维护 Markdown 表格（路径/文件数/说明），新增模块追加行、删除的删行。\n\n"
        ),
        "architecture.md": (
            "你是架构文档维护助手。根据 diff 在 architecture.md 中"
            "追加或修改架构决策记录，保持日期+标题格式，更新 Handler/Mixin 数量。\n\n"
        ),
        "technical-debt-registry.md": (
            "你是技术债维护助手。修复的问题改状态为✅已修复+日期，新决策在「已接受的设计决策」表格追加。\n\n"
        ),
        "development.md": (
            "你是开发指南维护助手。更新测试统计（如果 diff 含测试文件变化），"
            "更新 CI 命令（如果 workflow 变化）。保留其它内容。\n\n"
        ),
        "Docker使用指南.md": (
            "你是 Docker 指南维护助手。根据 Dockerfile/docker-compose.yml 变化更新部署命令、环境变量、端口映射。\n\n"
        ),
        "index.md": "你是文档索引维护助手。根据 diff 中的链接/路径变化更新表格。\n\n",
        "CHANGELOG.md": (
            "你是 CHANGELOG 维护助手。按 Keep a Changelog 格式在 Unreleased 章节追加变更条目。"
            f"当前版本号：{_get_version()}。如果没有 Unreleased 章节则创建。\n\n"
        ),
        "STATUS.md": "你是状态文件维护助手。在「最新进展」区域追加本次提交摘要（日期、变更描述、测试数变化）。\n\n",
    }
    base = prompts.get(doc_name, "你是文档维护助手。根据 git diff 更新文档，保留现有格式。\n\n")
    parts = [base, f"## 触发规则\n{trigger_name}\n"]
    if commit_msg:
        parts.append(f"## Commit Message\n{commit_msg.strip()}\n")
    parts.append(f"## 当前文档内容\n```\n{current_content}\n```\n")
    parts.append(f"## Git Diff\n```diff\n{diff_text}\n```\n")
    parts.append("直接输出更新后的完整文档内容，不要额外说明。")
    return "\n".join(parts)


# ─── 文档更新执行 ────────────────────────────────────────────


def update_document(doc_relpath, strategy, in_repo, diff_text, commit_msg, trigger_name, auto_fix, claude_timeout=120):
    """
    更新单个文档。
    返回 True 表示文档已被修改。
    """
    doc_path = PROJECT_ROOT / doc_relpath
    current_content = _read_file(doc_path)

    if strategy == "skip":
        return False

    # 构建并由生成新内容
    if strategy == "claude" and auto_fix:
        prompt = _build_claude_prompt(doc_relpath, current_content, diff_text, commit_msg, trigger_name)
        new_content = _call_claude(prompt, timeout=claude_timeout)
        if new_content is None:
            print(f"  ⚠ claude 调用失败，跳过 {doc_relpath}")
            return False
        # 确保内容以换行结束
        if not new_content.endswith("\n"):
            new_content += "\n"
    elif strategy == "claude" and not auto_fix:
        print(f"  ⚠ 自动修复已禁用，跳过 {doc_relpath}")
        return False
    else:
        return False

    # 内容无变化则跳过
    if new_content == current_content:
        print(f"  -> 内容无变化，跳过 {doc_relpath}")
        return False

    # 写入文件
    _write_file(doc_path, new_content)

    # 入仓文档执行
    if in_repo:
        _git_add(doc_path)
    else:
        print(f"  -> {doc_relpath} 不入仓，跳过 git add")

    return True


# ─── 主流程 ──────────────────────────────────────────────────


def _get_staged_files():
    """获取暂存区文件列表 [(status, path), ...]"""
    out = _run_git(["diff", "--cached", "--name-status"])
    result = []
    for line in out.split("\n"):
        line = line.strip()
        if line:
            parts = line.split("\t")
            if len(parts) >= 2:
                result.append((parts[0], parts[1]))
    return result


def _match_trigger_rules(staged_files, diff_text, commit_msg):
    """逐一检查触发规则，返回去重后的 (trigger_name, doc_path, strategy, in_repo) 列表"""
    triggered = []
    for rule in TRIGGER_RULES:
        fn = rule["match_fn"]
        n = fn.__code__.co_argcount
        try:
            matched = {
                3: fn(staged_files, diff_text, commit_msg),
                2: fn(staged_files, diff_text),
                1: fn(staged_files),
            }.get(n, False)
        except Exception as e:
            print(f"  ⚠ 规则「{rule['name']}」异常: {e}")
            continue
        if not matched:
            continue
        print(f"  🔔 触发规则: {rule['name']}")
        for doc, strategy, in_repo in rule["targets"]:
            if any(Path(f).name == Path(doc).name for _, f in staged_files):
                print(f"    -> {doc} 已在暂存区，跳过")
                continue
            triggered.append((rule["name"], doc, strategy, in_repo))
    # 去重
    seen, deduped = set(), []
    for tn, doc, s, r in triggered:
        k = (doc, s, r)
        if k not in seen:
            seen.add(k)
            deduped.append((tn, doc, s, r))
    return deduped


def _execute_updates(deduped, diff_text, commit_msg, auto_fix, claude_timeout):
    """执行文档更新，返回 (成功数, 失败数)"""
    updated = failed = 0
    for tn, doc, s, r in deduped:
        print(f"\n  [{tn}] → {doc}")
        if update_document(doc, s, r, diff_text, commit_msg, tn, auto_fix, claude_timeout):
            updated += 1
        else:
            failed += 1
    return updated, failed


def main():
    """主入口。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 60)
    print("  文档自动同步门禁")

    # 1. 读取环境变量
    auto_fix = os.environ.get("AUTO_FIX_DOCS", "true").strip().lower() in ("true", "1", "yes")
    claude_timeout = int(os.environ.get("CLAUDE_TIMEOUT", "120"))
    print(f"  自动修复: {'开启' if auto_fix else '关闭'}")
    print(f"  claude 超时: {claude_timeout}s")

    # 2. 获取变更信息
    staged_files = _get_staged_files()
    if not staged_files:
        print("  无暂存区变更，跳过")
        print("=" * 60)
        return 0

    diff_text = _run_git(["diff", "--cached"])
    commit_msg = _get_commit_message()

    # 3.检查可用
    if auto_fix and not _check_claude_available():
        print("  claude 不可用，降级为仅检查模式")
        auto_fix = False

    # 4. 匹配规则
    deduped = _match_trigger_rules(staged_files, diff_text, commit_msg)
    if not deduped:
        print("  所有文档已是最新")
        print("=" * 60)
        return 0

    # 5. 执行更新
    updated, failed = _execute_updates(deduped, diff_text, commit_msg, auto_fix, claude_timeout)

    # 6. 汇总
    print(f"\n  结果: {updated} 个已更新", end="")
    if failed:
        print(f", {failed} 个失败（不阻塞）", end="")
    print()
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
