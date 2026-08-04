#!/usr/bin/env python3
"""
G-037: 触发条件对齐检查
比对 CLAUDE.md 触发条件表与 docs/index.md 文档索引条目，确保完全一致。
任一方向存在遗漏即阻断。
"""

import re
import sys
from pathlib import Path

# 控制台-8编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"
INDEX_MD = PROJECT_ROOT / "docs" / "index.md"


def parse_claude_triggers(text: str) -> set[str]:
    """从 CLAUDE.md 触发条件表中提取文档路径"""
    docs = set()
    in_trigger_table = False
    for line in text.splitlines():
        line = line.strip()
        # 检测触发条件表开始
        if "读文档触发条件表" in line:
            in_trigger_table = True
            continue
        # 表头分隔行，跳过
        if in_trigger_table and re.match(r"^\|[-\s|]+\|$", line):
            continue
        # 表头行，跳过
        if in_trigger_table and "触发条件" in line and "必须读取的文档" in line:
            continue
        # 数据行
        if in_trigger_table and line.startswith("|"):
            match = re.search(r"`([^`]+)`", line)
            if match:
                docs.add(match.group(1))
        # 遇到下一个 ## 标题则表结束
        if in_trigger_table and line.startswith("##"):
            break
    return docs


def parse_index_docs(text: str) -> set[str]:
    """从 index.md 中提取所有文档路径"""
    docs = set()
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| 文件") or re.match(r"^\|[-\s|]+\|$", line):
            continue
        match = re.search(r"`([^`]+)`", line)
        if match:
            docs.add(match.group(1))
    return docs


def main() -> int:
    errors: list[str] = []

    if not CLAUDE_MD.exists():
        print(f"❌ G-037 失败: {CLAUDE_MD} 不存在")
        return 1

    if not INDEX_MD.exists():
        print(f"❌ G-037 失败: {INDEX_MD} 不存在")
        return 1

    claude_docs = parse_claude_triggers(CLAUDE_MD.read_text(encoding="utf-8"))
    index_docs = parse_index_docs(INDEX_MD.read_text(encoding="utf-8"))

    # 归一化：取文件名部分比较（文档用完整路径，索引文档用相对路径）
    def _basename(path: str) -> str:
        return Path(path).name or path  # adr/ → adr

    # 索引文档自引用（"不确定该读什么"→索引文档）属于正常设计，排除
    claude_names = {_basename(d) for d in claude_docs}
    index_names = {_basename(d) for d in index_docs}

    # 索引文档自身不列入比较（文档引用索引文档作为兜底导航，索引文档不列自己）
    claude_names.discard("index.md")

    # 索引文档中有但文档触发条件表中没有
    missing_in_claude = index_names - claude_names
    if missing_in_claude:
        errors.append("以下文档在 index.md 中存在，但 CLAUDE.md 触发条件表中缺失：")
        for doc in sorted(missing_in_claude):
            errors.append(f"  - {doc}")

    # 文档触发条件表中有但索引文档中没有
    missing_in_index = claude_names - index_names
    if missing_in_index:
        errors.append("以下文档在 CLAUDE.md 触发条件表中存在，但 index.md 中缺失：")
        for doc in sorted(missing_in_index):
            errors.append(f"  - {doc}")

    if errors:
        print("❌ G-037 触发条件对齐检查失败：")
        for err in errors:
            print(err)
        return 1

    print(f"✅ G-037 通过：CLAUDE.md 触发条件表与 index.md 完全对齐（{len(claude_names)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
