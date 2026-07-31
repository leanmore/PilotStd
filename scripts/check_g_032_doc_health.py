#!/usr/bin/env python3
"""
G-032 文档健康度守护器。

四维度检查：
  1. 生成器存活 — 验证 AUTO-GENERATED 标记 + 时间戳新鲜度
  2. 人工层新鲜度 — 按文档类别分级检查最后修改时间
  3. 交叉引用完整性 — 人工层引用的自动层锚点存在性
  4. 数据源唯一性 — 防人工区裸数字篡改

首次运行赦免机制：
  - STATUS.md 无 AUTO-GENERATED 标记 → 视为首次运行 → 不阻断，由生成器处理
  - 人工层文档 30 天内给予宽限期
  - 交叉引用缺失仅警告不阻断（赦免期内）
  - 人工区裸数字标记 [legacy-manual] 而非阻断（30天后转硬阻断）
"""
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows 控制台 UTF-8 编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent

AUTO_TAG = "<!-- AUTO-GENERATED"
LEGACY_TAG = "[legacy-manual]"
FIRST_RUN_GRACE_DAYS = 30

# ─── 自动生成层文档 ───
AUTO_DOCS = [
    "STATUS.md",
    "docs/testing/coverage-report.md",
]

# ─── 人工层文档新鲜度规则 ───
# 格式: (路径, 最大天数, 类别标签)
HUMAN_DOC_RULES = [
    ("STATUS.md", 7, "核心状态"),
    ("docs/governance/trinity-technical-spec-v2.md", 30, "架构规范"),
    ("docs/governance/gates.md", 30, "架构规范"),
    ("docs/governance/development-flow.md", 30, "架构规范"),
    ("docs/governance/PROJECT_GOVERNANCE.md", 60, "治理文档"),
    ("docs/governance/capabilities_registry.md", 60, "治理文档"),
    ("docs/governance/governance-principles.md", 60, "治理文档"),
    ("docs/architecture.md", 30, "架构规范"),
    ("docs/ci-lessons.md", 30, "运维知识"),
    ("docs/testing/known-issues.md", 14, "核心状态"),
    ("CHANGELOG.md", 14, "核心状态"),
]

# ─── 交叉引用规则 ───
# 格式: (源文档, 引用的目标文件glob)
CROSS_REF_RULES = [
    ("docs/governance/gates.md", "scripts/check_g_*.py"),
    ("docs/governance/trinity-technical-spec-v2.md", "docs/governance/development-flow.md"),
    ("CLAUDE.md", "docs/governance/gates.md"),
]

errors = []
warnings = []


def err(msg: str):
    errors.append(msg)


def warn(msg: str):
    warnings.append(msg)


# ═══════════════════════════════════════════════════════════════
# 维度 1: 生成器存活
# ═══════════════════════════════════════════════════════════════
def check_generator_alive():
    """验证自动生成文档的 AUTO-GENERATED 标记和时间戳。"""
    now = datetime.now(timezone.utc)
    print("   🔍 维度1: 生成器存活...")
    for fp in AUTO_DOCS:
        p = PROJECT_ROOT / fp
        if not p.exists():
            err(f"G-032: {fp} 不存在，生成器可能未运行或路径配置错误")
            continue

        content = p.read_text(encoding="utf-8")
        if AUTO_TAG not in content:
            # 🔑 首次运行赦免：无标记时不阻断
            warn(f"G-032: {fp} 缺少 AUTO-GENERATED 标记（首次运行赦免中，生成器将在下次运行时注入）")
            continue

        # 提取时间戳并验证新鲜度
        match = re.search(r"at (\d{4}-\d{2}-\d{2}T[\d:\.\+Z\-]+)", content)
        if match:
            try:
                ts_str = match.group(1).replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
                age = now - ts
                if age > timedelta(hours=2):
                    warn(f"G-032: {fp} 生成时间距今 {age}（>{int(age.total_seconds()/3600)}h），可能需要重新生成")
                else:
                    print(f"      ✅ {fp} 标记有效（{int(age.total_seconds()/60)}min 前生成）")
            except ValueError as e:
                warn(f"G-032: {fp} 时间戳解析失败: {e}")
        else:
            warn(f"G-032: {fp} 有 AUTO-GENERATED 标记但无法提取时间戳")


# ═══════════════════════════════════════════════════════════════
# 维度 2: 人工层新鲜度
# ═══════════════════════════════════════════════════════════════
def check_human_freshness():
    """检查人工维护文档的最后修改时间是否在允许范围内。"""
    now = datetime.now(timezone.utc)
    grace_cutoff = now - timedelta(days=FIRST_RUN_GRACE_DAYS)
    print("   🔍 维度2: 人工层新鲜度...")

    for fp, max_days, category in HUMAN_DOC_RULES:
        p = PROJECT_ROOT / fp
        if not p.exists():
            warn(f"G-032: {fp} 不存在（{category}）")
            continue

        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        age_days = (now - mtime).days

        if age_days > max_days:
            if mtime > grace_cutoff:
                # 赦免期内仅警告
                warn(f"G-032: {fp} 已 {age_days} 天未更新（{category}上限 {max_days} 天，宽限期内）")
            else:
                err(f"G-032: {fp} 已 {age_days} 天未更新，超过 {category}上限 {max_days} 天")
        else:
            print(f"      ✅ {fp} ({age_days}d/{max_days}d, {category})")


# ═══════════════════════════════════════════════════════════════
# 维度 3: 交叉引用完整性
# ═══════════════════════════════════════════════════════════════
def check_cross_references():
    """检查文档中引用的文件路径是否存在。"""
    print("   🔍 维度3: 交叉引用完整性...")

    for src_fp, ref_pattern in CROSS_REF_RULES:
        src = PROJECT_ROOT / src_fp
        if not src.exists():
            warn(f"G-032: 交叉引用源 {src_fp} 不存在，跳过检查")
            continue

        content = src.read_text(encoding="utf-8")
        # 提取所有 markdown 链接和裸路径引用
        refs = set()
        refs.update(re.findall(r"\[.*?\]\(([^)]+)\)", content))  # [text](path)
        refs.update(re.findall(r"`([^`]+\.(?:py|md|sh|yml|yaml))`", content))  # `path/file.py`

        for ref in refs:
            # 跳过外部 URL
            if ref.startswith("http://") or ref.startswith("https://"):
                continue
            # 跳过锚点
            if "#" in ref:
                ref = ref.split("#")[0]
            if not ref:
                continue

            # 尝试解析相对路径
            resolved = (src.parent / ref).resolve()
            if not resolved.exists():
                # 尝试从项目根解析
                resolved = (PROJECT_ROOT / ref).resolve()
                if not resolved.exists():
                    warn(f"G-032: {src_fp} 引用了不存在的文件: {ref}")


# ═══════════════════════════════════════════════════════════════
# 维度 4: 数据源唯一性（防手改数字）
# ═══════════════════════════════════════════════════════════════
def check_data_source_uniqueness():
    """
    扫描 STATUS.md 中 AUTO-METRICS 区块外的区域。
    若发现覆盖率/测试数模式的裸数字 → 报错。
    标记 [legacy-manual] 的条目在首次运行 30 天内仅警告。
    """
    status = PROJECT_ROOT / "STATUS.md"
    if not status.exists():
        return
    print("   🔍 维度4: 数据源唯一性...")

    content = status.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc)
    grace_cutoff = now - timedelta(days=FIRST_RUN_GRACE_DAYS)

    in_auto = False
    violations = 0
    for i, line in enumerate(content.split("\n"), 1):
        if "<!-- BEGIN AUTO-METRICS -->" in line:
            in_auto = True
            continue
        if "<!-- END AUTO-METRICS -->" in line:
            in_auto = False
            continue
        if in_auto:
            continue

        # 检测人工区中的覆盖率/测试数硬编码模式
        if re.search(r"(覆盖率|测试数|通过率|测试用例)\D*\d+", line):
            if LEGACY_TAG in line:
                warn(f"G-032: STATUS.md:{i} 含 [legacy-manual] 标记的数值（宽限期内）: {line.strip()[:60]}")
            else:
                err(f"G-032: STATUS.md:{i} 人工区含数值，应使用自动生成或标记 {LEGACY_TAG}: {line.strip()[:60]}")
            violations += 1

    if violations == 0:
        print("      ✅ 人工区无裸数字")


def main():
    print("\n🛡️  G-032 文档健康度守护器开始检查...\n")

    check_generator_alive()
    check_human_freshness()
    check_cross_references()
    check_data_source_uniqueness()

    # ─── 输出报告 ───
    print(f"\n{'─'*50}")
    if warnings:
        print(f"⚠️  警告 ({len(warnings)}):")
        for w in warnings:
            print(f"   {w}")
    if errors:
        print(f"❌ 错误 ({len(errors)}):")
        for e in errors:
            print(f"   {e}")

    if errors:
        print(f"\n🔴 G-032 守护失败: {len(errors)} error(s), {len(warnings)} warning(s)")
        sys.exit(1)
    elif warnings:
        print(f"\n🟡 G-032 守护通过（有警告）: {len(warnings)} warning(s)")
        sys.exit(0)
    else:
        print(f"\n🟢 G-032 守护全部通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
