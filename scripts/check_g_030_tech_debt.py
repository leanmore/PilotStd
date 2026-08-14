#!/usr/bin/env python3
"""
G-030: 技术债联动检查。

检测策略（增量检测）:
  - 仅检查本次变更中**新增**的 # TECH-DEBT: / # TODO(debt): 标记
  - 忽略已有存量标记、文档文件中的标记
  - 联动要求: 同次提交必须包含对技术债登记簿的变更

技术债登记簿路径（按优先级）:
  1. docs/governance/tech-debt-register.md（专用登记簿）
  2. docs/technical-debt.md（通用技术债文档）
"""
import re
import subprocess
import sys
from pathlib import Path

# 控制台-8编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 技术债寄存器候选路径（存在任一即可）
DEBT_REGISTER_PATHS = [
    PROJECT_ROOT / "docs" / "governance" / "tech-debt-register.md",
    PROJECT_ROOT / "docs" / "technical-debt.md",
]

# 修正: 正则表达式转义，精确匹配合法格式
DEBT_PATTERNS = [
    r"#\s*TECH-DEBT\s*:\s*",
    r"#\s*TODO\s*\(\s*debt\s*\)\s*:\s*",
]

# 检测范围：仅源代码目录
SOURCE_DIRS = ["pilotstd/", "docker/", "web/src/"]

# 排除路径（文档、测试、脚本中的标记不触发-030）
EXCLUDE_PREFIXES = ["docs/", "tests/", "scripts/", "web/node_modules/"]


def get_staged_diff() -> str:
    """获取暂存区新增行的 diff。"""
    try:
        # 1. 优先暂存区
        result = subprocess.run(
            ["git", "diff", "--cached", "-U0"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        if result.stdout.strip():
            return result.stdout

        # 2.持续集成合并请求场景
        result = subprocess.run(
            ["git", "diff", "-U0", "origin/main..."],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        if result.stdout.strip():
            return result.stdout

        # 3. 最近一次提交
        result = subprocess.run(
            ["git", "diff", "-U0", "HEAD~1"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"   ⚠️  git diff 失败: {e}")
        return ""


def get_staged_files() -> list[str]:
    """获取暂存区变更的文件列表。"""
    try:
        # 1. 暂存区
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        if result.stdout.strip():
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        # 说明：2.持续集成合并请求
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "origin/main..."],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        if result.stdout.strip():
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        # 3. 最近提交
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def is_excluded(filepath: str) -> bool:
    """检查文件路径是否在排除范围内。"""
    fp = filepath.replace("\\", "/")
    for prefix in EXCLUDE_PREFIXES:
        if fp.startswith(prefix):
            return True
    return False


def is_source_file(filepath: str) -> bool:
    """检查是否属于源代码目录。"""
    fp = filepath.replace("\\", "/")
    for src_dir in SOURCE_DIRS:
        if fp.startswith(src_dir):
            return True
    return False


def extract_new_debt_markers(diff_text: str) -> list[tuple[str, int, str]]:
    """
    从 diff 中提取新增的技术债标记。
    返回 [(文件路径, 行号, 标记内容), ...]。
    """
    results = []
    current_file = ""
    current_line = 0

    for line in diff_text.split("\n"):
        # 跟踪当前文件
        if line.startswith("+++ "):
            # 提取文件路径(去除/或/前缀)
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path

        # 跟踪行号(@@-,+,@@)
        elif line.startswith("@@ "):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1)) - 1

        # 仅检查新增行
        elif line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            # 去除行首的 + 再检查
            content = line[1:]
            for pattern in DEBT_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    if is_source_file(current_file) and not is_excluded(current_file):
                        results.append((current_file, current_line, content.strip()))
        elif not line.startswith("-"):
            current_line += 1

    return results


def has_debt_register_change(staged_files: list[str]) -> bool:
    """检查暂存区是否包含技术债登记簿的变更。"""
    staged_set = {f.replace("\\", "/") for f in staged_files}
    for register_path in DEBT_REGISTER_PATHS:
        rel = str(register_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if rel in staged_set:
            return True
    return False


def main():
    print("🔍 G-030: 技术债联动检查（增量检测）...")

    staged_files = get_staged_files()
    diff_text = get_staged_diff()

    if not diff_text:
        print("🟢 G-030: 无变更，跳过检查")
        sys.exit(0)

    new_markers = extract_new_debt_markers(diff_text)

    if not new_markers:
        print("🟢 G-030: 未检测到新增技术债标记，通过")
        sys.exit(0)

    print(f"🔍 G-030: 检测到 {len(new_markers)} 个新增技术债标记:")
    for filepath, lineno, content in new_markers:
        print(f"   {filepath}:{lineno}  {content[:80]}")

    # 检查是否同步更新了登记簿
    if has_debt_register_change(staged_files):
        print("✅ G-030: 技术债登记簿已同步更新，通过")
        sys.exit(0)
    else:
        print("❌ G-030: 新增技术债标记但未更新登记簿！")
        register_paths_str = " 或 ".join(
            [str(p.relative_to(PROJECT_ROOT)) for p in DEBT_REGISTER_PATHS]
        )
        print(f"   请在同次提交中更新 {register_paths_str}")
        print(f"   新增标记所在文件: {', '.join(sorted(set(f for f, _, _ in new_markers)))}")
        sys.exit(1)


if __name__ == "__main__":
    main()
