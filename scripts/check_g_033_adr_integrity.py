#!/usr/bin/env python3
"""
G-033: Architecture Decision Record Integrity Check
检测架构变更是否伴随有效 ADR。

检测策略（三级回退）:
  1. git diff --cached（pre-commit 场景）
  2. git diff origin/main...（CI PR 场景）
  3. git diff HEAD~1（本地最近提交）

ADR 有效性判定: Status 非 proposed/draft 即为有效
MVP 阶段: 输出关联性手动确认提示
"""
import subprocess
import re
import sys
from pathlib import Path

# 控制台-8编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = PROJECT_ROOT / "docs" / "adr"

# 架构变更检测模式
ARCH_PATTERNS = [
    r"pilotstd/core/",
    r"pilotstd/query/engine/",
    r"pilotstd/manager/facade/",
    r"pilotstd/ui/core/handlers/",
    r"docker/api/",
    r"docs/architecture",
    r"docs/governance/",
    r"docs/adr/",
    r"\.github/workflows/",
    r"scripts/check_all\.sh",
    r"scripts/check_g_",
]


def get_changed_files() -> list[str]:
    """获取本次变更的文件列表（三级回退）。"""
    try:
        # 1.优先检查暂存区（-场景）
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        if result.stdout.strip():
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            print(f"   📋 检测暂存区变更: {len(files)} 个文件")
            return files

        # 2.持续集成合并请求场景：对比/入口
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "origin/main..."],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        if result.stdout.strip():
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            print(f"   📋 检测 PR 变更 (origin/main...): {len(files)} 个文件")
            return files

        # 3.回退：最近一次
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(PROJECT_ROOT), timeout=10
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        if files:
            print(f"   📋 检测最近提交变更 (HEAD~1): {len(files)} 个文件")
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"   ⚠️  git diff 失败: {e}")
        return []


def is_architecture_change(filepath: str) -> bool:
    """判断文件是否属于架构变更范围。"""
    fp = filepath.replace("\\", "/")
    for pattern in ARCH_PATTERNS:
        if re.search(pattern, fp):
            return True
    return False


def parse_adr_status(content: str) -> str | None:
    """从 ADR 文档内容中提取 Status 字段。"""
    # 尝试多种格式
    patterns = [
        r"##\s*Status\s*\n\s*(\S+)",
        r"\*\*Status\*\*:\s*(\S+)",
        r"状态[：:]\s*(\S+)",
        r">\s*\*\*状态\*\*[：:]\s*(\S+)",
    ]
    for pat in patterns:
        match = re.search(pat, content, re.IGNORECASE)
        if match:
            return match.group(1).lower().strip()
    return None


def validate_adr() -> bool:
    """执行 G-033 检查。返回 True 表示通过。"""
    changed = get_changed_files()
    arch_changes = [f for f in changed if is_architecture_change(f)]

    if not arch_changes:
        print("🟢 G-033: 无架构变更，跳过检查")
        return True

    print(f"🔍 G-033: 检测到 {len(arch_changes)} 个架构变更文件:")
    for f in arch_changes[:10]:
        print(f"      {f}")
    if len(arch_changes) > 10:
        print(f"      ... 及其他 {len(arch_changes) - 10} 个文件")

    if not ADR_DIR.exists():
        print(f"❌ G-033: ADR 目录 {ADR_DIR} 不存在，请创建 docs/adr/")
        return False

    # 收集所有架构决策及其状态
    adr_files = list(ADR_DIR.glob("ADR-*.md"))
    if not adr_files:
        print(f"❌ G-033: 架构变更需伴随有效 ADR，但 {ADR_DIR} 中无 ADR 文件")
        print(f"   变更文件: {', '.join(arch_changes[:5])}")
        return False

    valid_adrs = []
    pending_adrs = []
    for adr_file in sorted(adr_files):
        try:
            content = adr_file.read_text(encoding="utf-8")
            status = parse_adr_status(content)
            if status is None:
                print(f"   ⚠️  无法解析 {adr_file.name} 的 Status 字段，视为无效")
                continue
            if status in ("proposed", "draft"):
                pending_adrs.append((adr_file.name, status))
            else:
                valid_adrs.append((adr_file.name, status))
        except (OSError, UnicodeDecodeError) as e:
            print(f"   ⚠️  读取 {adr_file.name} 失败: {e}")

    if not valid_adrs:
        print(f"❌ G-033: 架构变更需伴随有效 ADR（非 proposed/draft 状态）")
        print(f"   当前 ADR 状态: {[(n, s) for n, s in pending_adrs]}")
        print(f"   变更文件: {', '.join(arch_changes[:5])}")
        return False

    print(f"✅ G-033: 找到 {len(valid_adrs)} 个有效 ADR: "
          f"{', '.join([n for n, _ in valid_adrs[:5]])}")
    if pending_adrs:
        print(f"   ⚠️  另有 {len(pending_adrs)} 个未生效 ADR (proposed/draft): "
              f"{', '.join([n for n, _ in pending_adrs])}")

    # 最小可行阶段：关联性手动确认提示
    print(f"⚠️  G-033: 请手动确认上述 ADR 与本次架构变更的关联性")
    print(f"   变更范围: {', '.join(arch_changes[:3])}"
          f"{'...' if len(arch_changes) > 3 else ''}")
    return True


if __name__ == "__main__":
    sys.exit(0 if validate_adr() else 1)
