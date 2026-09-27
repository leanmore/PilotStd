#!/usr/bin/env python3
"""
⚠️ 已归档（2026-09-27，第十轮 T-15）——本脚本**停止维护**，且**不在任何入口中被调用**
（既不在 `.husky/pre-commit`、也不在 `scripts/check_all.sh` 任何模式、也不在 CI 任何步骤）。

**归档判定依据（2026-09-27 实测）**：
- **全库 0 调用点**：`git grep update_docs` 排除自身打印后，仅剩文档中的历史叙述；
- 其五个功能均已被现行机制取代（见下表）；
- 其唯一仍在写入的目标 `docs/archive/specs/模块与功能清单.md` 自身早在 2026-08-19 即标注 ARCHIVED。

**各函数的现行替代方案**（每条已按 ruff E501 `<=120` 列宽折行；归档前为 Markdown 表格）：

- `extract_test_count_from_status()` / `update_test_count_in_file()`
  → `scripts/generate_status_metrics.py`：写 STATUS.md 的 AUTO-METRICS 区块
  （覆盖率取自 `coverage.xml`、测试数取自 `pytest --collect-only`）；
  STATUS.md 人工区禁裸数字由 **G-032 维度 4** 守护；
  `docs/index.md` / `docs/development.md` 的测试数不再自动改写（如需变更走 G-032/G-031 的显式校验路径）。
- `update_aggregator_description()`
  → 聚合器配置常量本身在 `pilotstd/core/notification/aggregate_buffer.py`；
  文档侧由 **`docs/architecture/modules/core.md`**（G-031 block 映射：改 `pilotstd/core/` 必须同批同步该文档）承载，
  不再由本脚本反写 STATUS.md 正文。
- `update_tech_debt_entries()`
  → **已惰性化**（T-02，2026-09-27）：旧簿 `docs/architecture/technical-debt-registry.md` 已废止归档，
  技术债唯一数据源为 `docs/technical-debt.md`（人工维护 + G-030 联动）。
- `update_module_list()`
  → 目标文档 `docs/archive/specs/模块与功能清单.md` 已于 2026-08-19 标 ARCHIVED；
  模块结构现由 `docs/architecture/modules/*` + **G-030/G-031/G-037** 显式校验承担。
- `main()` 末尾的自动 `git add`
  → 无（自动 `git add` 会绕过人工审阅，故整体废弃）。

**历史取回方式**：

```
git log --follow -- scripts/update_docs.archived.py     # 归档前后的完整变更史
git show <归档提交的父提交>:scripts/update_docs.py       # 归档前的原始文件
```

**保留原因**：作为"当年如何自动同步文档"的参考实现留档；**不得在新流程中调用本脚本**。
"""

import re
import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
STATUS_FILE = PROJECT_ROOT / "STATUS.md"


def extract_test_count_from_status() -> int:
    """从 STATUS.md 提取测试数（源头）"""
    if not STATUS_FILE.exists():
        print("  STATUS.md 不存在，跳过")
        return 0

    content = STATUS_FILE.read_text(encoding="utf-8")
    patterns = [
        r"Python\s+(\d+)\s+tests? collected",
        r"测试数[：:]\s*(\d+)",
        r"✅\s*(\d+)\s*passed",
        r"(\d+)\s*passed",
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return int(match.group(1))
    return 0


def update_test_count_in_file(filepath: Path, count: int) -> bool:
    """更新单个文档中的测试数"""
    if not filepath.exists():
        return False

    content = filepath.read_text(encoding="utf-8")
    original = content

    # 替换"测试数:"或"测试数："
    content = re.sub(r"测试数[：:]\s*\d+", f"测试数: {count}", content)
    # 替换"✅"
    content = re.sub(r"✅\s*\d+\s*passed", f"✅ {count} passed", content)
    # 替换""
    content = re.sub(r"(?<![✅])\b(\d+)\s+passed\b", f"{count} passed", content)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def update_aggregator_description() -> bool:
    """从 aggregate_buffer.py 读取聚合策略，更新 STATUS.md"""
    agg_file = PROJECT_ROOT / "pilotstd/core/notification/aggregate_buffer.py"
    if not agg_file.exists():
        return False

    content = agg_file.read_text(encoding="utf-8")
    window = re.search(r"DEFAULT_WINDOW_SECONDS\s*=\s*([\d.]+)", content)
    max_window = re.search(r"MAX_WINDOW_SECONDS\s*=\s*([\d.]+)", content)
    batch_size = re.search(r"DEFAULT_BATCH_SIZE\s*=\s*(\d+)", content)

    if not window or not max_window:
        return False

    desc = (
        f"聚合器配置：首次延时 {window.group(1)} 秒，"
        f"最大窗口 {max_window.group(1)} 秒，"
        f"批次上限 {batch_size.group(1) if batch_size else '10'} 条"
    )

    if not STATUS_FILE.exists():
        return False

    content = STATUS_FILE.read_text(encoding="utf-8")
    if "聚合器" in content:
        content = re.sub(r"聚合器[：:].*?(?=\n\n|\n#|\Z)", f"聚合器: {desc}", content, flags=re.DOTALL)
    else:
        content += f"\n\n聚合器: {desc}\n"

    if content != STATUS_FILE.read_text(encoding="utf-8"):
        STATUS_FILE.write_text(content, encoding="utf-8")
        return True
    return False


def update_tech_debt_entries() -> bool:
    """旧簿（已归档）条目状态更新——2026-09-27 起为**惰性空操作**。

    技术债唯一数据源已改为 `docs/technical-debt.md`（人工维护），旧簿仅归档留痕；
    本函数目标改为归档文件，其正则不再匹配任何条目 → 恒返回 False（不会复活第二数据源）。
    """
    filepath = DOCS_DIR / "architecture/technical-debt-registry.archived.md"
    if not filepath.exists():
        return False

    content = filepath.read_text(encoding="utf-8")
    original = content

    # 条目#9:配置
    content = re.sub(r"(\|.*?#9.*?)状态[：:]\s*已接受", r"\1状态: 已移除（功能已删除）", content, flags=re.DOTALL)

    # 条目#16:修复
    content = re.sub(r"(\|.*?#16.*?)状态[：:]\s*已禁用", r"\1状态: 已移除（功能已删除）", content, flags=re.DOTALL)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def update_module_list() -> bool:
    """更新模块与功能清单.md 中的文件列表"""
    filepath = DOCS_DIR / "archive/specs/模块与功能清单.md"
    if not filepath.exists():
        return False

    content = filepath.read_text(encoding="utf-8")
    original = content

    # 检查文件是否存在，更新状态
    agg_exists = (PROJECT_ROOT / "pilotstd/core/notification/aggregate_buffer.py").exists()
    policy_exists = (PROJECT_ROOT / "pilotstd/core/notification/_policy.py").exists()

    if agg_exists:
        content = re.sub(r"(aggregate_buffer\.py).*?(?=\n)", r"\1 ✅ 已实现", content)
    if policy_exists:
        content = re.sub(r"(_policy\.py).*?(?=\n)", r"\1 ✅ 已实现", content)

    # 更新测试数
    count = extract_test_count_from_status()
    if count:
        content = re.sub(r"测试数[：:]\s*\d+", f"测试数: {count}", content)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def main():
    """主流程"""
    # 控制台可能默认，会抛
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    changed_files = []

    # 1.从文档提取测试数（源头）
    test_count = extract_test_count_from_status()
    print(f"[update_docs] 从 STATUS.md 提取测试数: {test_count}")

    # 2. 同步测试数到其他文档
    docs_to_sync = [
        DOCS_DIR / "development.md",
        DOCS_DIR / "index.md",
        DOCS_DIR / "archive/specs/模块与功能清单.md",
    ]
    for doc in docs_to_sync:
        if update_test_count_in_file(doc, test_count):
            changed_files.append(doc)
            print(f"  -> 更新 {doc.relative_to(PROJECT_ROOT)}")

    # 3.更新文档中的聚合器描述
    if update_aggregator_description():
        changed_files.append(STATUS_FILE)
        print(f"  -> 更新 {STATUS_FILE.relative_to(PROJECT_ROOT)} (聚合器描述)")

    # 4. 更新技术债务条目（旧簿已归档，恒为惰性空操作）
    if update_tech_debt_entries():
        changed_files.append(DOCS_DIR / "architecture/technical-debt-registry.archived.md")
        print("  -> 更新 docs/architecture/technical-debt-registry.archived.md")

    # 5. 更新模块清单
    if update_module_list():
        changed_files.append(DOCS_DIR / "archive/specs/模块与功能清单.md")
        print("  -> 更新 docs/archive/specs/模块与功能清单.md")

    # 6.如果有文件被修改，
    if changed_files:
        unique_files = list(set(changed_files))
        for f in unique_files:
            subprocess.run(["git", "add", str(f)], check=False, capture_output=True)
        print(f"\n[update_docs] 已自动更新 {len(unique_files)} 个文档并 git add")
        return 1  # 有变更
    else:
        print("[update_docs] 所有文档已是最新，无需更新")
        return 0


if __name__ == "__main__":
    sys.exit(main())
