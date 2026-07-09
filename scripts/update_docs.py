#!/usr/bin/env python3
"""
自动更新文档中的可量化数据（测试数、文件引用、聚合器描述等）
在 pre-commit 中自动运行。
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

    # 替换 "测试数: N" 或 "测试数：N"
    content = re.sub(r"测试数[：:]\s*\d+", f"测试数: {count}", content)
    # 替换 "✅ N passed"
    content = re.sub(r"✅\s*\d+\s*passed", f"✅ {count} passed", content)
    # 替换 "N passed"
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
    """更新 technical-debt-registry.md 中的条目状态"""
    filepath = DOCS_DIR / "architecture/technical-debt-registry.md"
    if not filepath.exists():
        return False

    content = filepath.read_text(encoding="utf-8")
    original = content

    # 条目 #9: Toast 配置
    content = re.sub(r"(\|.*?#9.*?)状态[：:]\s*已接受", r"\1状态: 已移除（功能已删除）", content, flags=re.DOTALL)

    # 条目 #16: stderr 修复
    content = re.sub(r"(\|.*?#16.*?)状态[：:]\s*已禁用", r"\1状态: 已移除（功能已删除）", content, flags=re.DOTALL)

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def update_module_list() -> bool:
    """更新模块与功能清单.md 中的文件列表"""
    filepath = DOCS_DIR / "specs/模块与功能清单.md"
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
    # Windows 控制台可能默认 GBK，emoji 会抛 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    changed_files = []

    # 1. 从 STATUS.md 提取测试数（源头）
    test_count = extract_test_count_from_status()
    print(f"[update_docs] 从 STATUS.md 提取测试数: {test_count}")

    # 2. 同步测试数到其他文档
    docs_to_sync = [
        DOCS_DIR / "development.md",
        DOCS_DIR / "index.md",
        DOCS_DIR / "specs/模块与功能清单.md",
    ]
    for doc in docs_to_sync:
        if update_test_count_in_file(doc, test_count):
            changed_files.append(doc)
            print(f"  -> 更新 {doc.relative_to(PROJECT_ROOT)}")

    # 3. 更新 STATUS.md 中的聚合器描述
    if update_aggregator_description():
        changed_files.append(STATUS_FILE)
        print(f"  -> 更新 {STATUS_FILE.relative_to(PROJECT_ROOT)} (聚合器描述)")

    # 4. 更新技术债务条目
    if update_tech_debt_entries():
        changed_files.append(DOCS_DIR / "architecture/technical-debt-registry.md")
        print("  -> 更新 docs/architecture/technical-debt-registry.md")

    # 5. 更新模块清单
    if update_module_list():
        changed_files.append(DOCS_DIR / "specs/模块与功能清单.md")
        print("  -> 更新 docs/specs/模块与功能清单.md")

    # 6. 如果有文件被修改，git add
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
