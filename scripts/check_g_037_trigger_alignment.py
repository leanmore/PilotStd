#!/usr/bin/env python3
"""
G-037: 触发条件对齐检查（文档生命周期版）
覆盖三个维度，任一失败即 exit 1 阻断 CI：

1. 读取侧双向对齐：AGENTS.md 8.1 触发条件表 ↔ docs/index.md 文档索引条目，
   任一方向存在遗漏即阻断。
2. 回写侧存在性：AGENTS.md 8.2 回写清单列出的文档必须物理存在。
3. 回写侧覆盖完整性：AGENTS.md 8.1 中标记为「代码说明书」的文档
   必须与 8.2 回写清单完全一致（防止新增代码说明书后漏同步回写清单）。
"""

import re
import sys
from pathlib import Path

# 控制台-8编码兼容
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 可选参数：指定 AGENTS.md 路径（测试副本用），默认取项目根目录
AGENTS_MD = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "AGENTS.md"
INDEX_MD = PROJECT_ROOT / "docs" / "index.md"

# 8.1 表解析锚点（与表格内嵌关键字一致，勿改名）
_TRIGGER_ANCHOR = "读文档触发条件表"
# 8.2 表解析锚点
_WRITEBACK_ANCHOR = "回写侧"


def _is_table_separator(line: str) -> bool:
    """判断是否为 Markdown 表格分隔行（|---|）。"""
    return bool(re.match(r"^\|[-\s|]+\|$", line))


def parse_claude_triggers(text: str) -> set[str]:
    """从 AGENTS.md 8.1 触发条件表中提取文档路径"""
    docs: set[str] = set()
    in_trigger_table = False
    for line in text.splitlines():
        line = line.strip()
        # 检测触发条件表开始
        if _TRIGGER_ANCHOR in line:
            in_trigger_table = True
            continue
        # 表头分隔行，跳过
        if in_trigger_table and _is_table_separator(line):
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


def parse_doc_natures(text: str) -> dict[str, str]:
    """从 AGENTS.md 8.1 触发条件表提取 文档路径 → 文档性质 映射。

    性质取自表格第三列（文档性质），关键字为「代码说明书」/「人的指引」；
    其余视为索引类。
    """
    natures: dict[str, str] = {}
    in_trigger_table = False
    for line in text.splitlines():
        line = line.strip()
        if _TRIGGER_ANCHOR in line:
            in_trigger_table = True
            continue
        if in_trigger_table and _is_table_separator(line):
            continue
        if in_trigger_table and "触发条件" in line and "必须读取的文档" in line:
            continue
        if in_trigger_table and line.startswith("|"):
            match = re.search(r"`([^`]+)`", line)
            if match:
                path = match.group(1)
                nature = "索引"
                if "代码说明书" in line:
                    nature = "代码说明书"
                elif "人的指引" in line:
                    nature = "人的指引"
                natures[path] = nature
        if in_trigger_table and line.startswith("##"):
            break
    return natures


def parse_writeback_docs(text: str) -> set[str]:
    """从 AGENTS.md 8.2 回写侧清单提取文档路径。"""
    docs: set[str] = set()
    in_writeback = False
    for line in text.splitlines():
        line = line.strip()
        # 检测回写清单开始（8.2 标题含「回写侧」）
        if _WRITEBACK_ANCHOR in line:
            in_writeback = True
            continue
        if in_writeback and _is_table_separator(line):
            continue
        # 表头行（文档 | 对应代码范围）
        if in_writeback and "对应代码范围" in line:
            continue
        if in_writeback and line.startswith("|"):
            match = re.search(r"`([^`]+)`", line)
            if match:
                docs.add(match.group(1))
        # 遇到下一个 ## 标题则清单结束
        if in_writeback and line.startswith("##") and _WRITEBACK_ANCHOR not in line:
            break
    return docs


def parse_index_docs(text: str) -> set[str]:
    """从 index.md 中提取所有文档路径"""
    docs: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| 文件") or _is_table_separator(line):
            continue
        match = re.search(r"`([^`]+)`", line)
        if match:
            docs.add(match.group(1))
    return docs


def main() -> int:
    errors: list[str] = []

    if not AGENTS_MD.exists():
        print(f"❌ G-037 失败: {AGENTS_MD} 不存在")
        return 1

    if not INDEX_MD.exists():
        print(f"❌ G-037 失败: {INDEX_MD} 不存在")
        return 1

    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    claude_docs = parse_claude_triggers(agents_text)
    natures = parse_doc_natures(agents_text)
    writeback_docs = parse_writeback_docs(agents_text)
    index_docs = parse_index_docs(INDEX_MD.read_text(encoding="utf-8"))

    # 归一化：取文件名部分比较（文档用完整路径，索引文档用相对路径）
    def _basename(path: str) -> str:
        return Path(path).name or path  # adr/ → adr

    # ── 维度 1：读取侧双向对齐 ──────────────────────────────
    claude_names = {_basename(d) for d in claude_docs}
    index_names = {_basename(d) for d in index_docs}

    # 索引文档自引用（"不确定该读什么"→索引文档）属于正常设计，排除
    claude_names.discard("index.md")

    missing_in_claude = index_names - claude_names
    if missing_in_claude:
        errors.append("以下文档在 index.md 中存在，但 AGENTS.md 触发条件表中缺失：")
        for doc in sorted(missing_in_claude):
            errors.append(f"  - {doc}")

    missing_in_index = claude_names - index_names
    if missing_in_index:
        errors.append("以下文档在 AGENTS.md 触发条件表中存在，但 index.md 中缺失：")
        for doc in sorted(missing_in_index):
            errors.append(f"  - {doc}")

    # ── 维度 2：回写侧存在性 ────────────────────────────────
    for doc in sorted(writeback_docs):
        if not (PROJECT_ROOT / doc).exists():
            errors.append(f"回写侧文档不存在（8.2 清单指向的文件缺失）: {doc}")

    # ── 维度 3：回写侧覆盖完整性 ─────────────────────────────
    # 8.1 标记为「代码说明书」的文档必须与 8.2 回写清单完全一致，
    # 防止新增代码说明书后漏同步回写清单（或回写清单出现非代码说明书条目）。
    code_docs = {p for p, n in natures.items() if "代码说明书" in n}

    missing_in_writeback = code_docs - writeback_docs
    if missing_in_writeback:
        errors.append("以下 8.1 代码说明书文档未列入 8.2 回写清单（漏同步，需补充）：")
        for doc in sorted(missing_in_writeback):
            errors.append(f"  - {doc}")

    extra_in_writeback = writeback_docs - code_docs
    if extra_in_writeback:
        errors.append("以下 8.2 回写清单文档未在 8.1 标记为代码说明书（不一致，需核对）：")
        for doc in sorted(extra_in_writeback):
            errors.append(f"  - {doc}")

    # ── 汇总 ────────────────────────────────────────────────
    if errors:
        print("❌ G-037 文档生命周期检查失败：")
        for err in errors:
            print(err)
        return 1

    print(f"✅ G-037 通过：读取侧 {len(claude_names)} 项对齐；"
          f"回写侧 {len(writeback_docs)} 份文档存在且覆盖一致"
          f"（代码说明书 {len(code_docs)} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
