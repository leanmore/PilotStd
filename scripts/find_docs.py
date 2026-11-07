#!/usr/bin/env python3
"""按关键词查找项目文档（新人入门/问题台账/参考手册）。

用途：任务开始或排查前，先跑一次，避免只靠记忆。
不读取代码、不联网、不修改任何文件。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOCS = ROOT / "docs"
EXCLUDE_DIRS = {"archive", "archived", "plans", "debt"}


def _split_terms(query: str) -> list[str]:
    """按空白/逗号拆词；保留中文词组。"""
    return [t for t in re.split(r"[\s,，;；]+", query.strip()) if t]


def _read(path: Path) -> str:
    """读取 Markdown；编码损坏时替换，不因单个文件中断全量检索。"""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def search(root: Path, query: str, limit: int = 8) -> list[dict]:
    """返回按相关度排序的文档列表。"""
    terms = _split_terms(query)
    if not terms:
        return []
    lowered = [t.lower() for t in terms]
    results: list[dict] = []

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        # 归档/计划/债务目录是历史材料，默认不参与“当前事实”检索
        if EXCLUDE_DIRS & set(rel.parts):
            continue
        text = _read(path)
        if not text:
            continue
        name = str(rel).replace("\\", "/").lower()
        lines = text.splitlines()
        headings = [ln.lstrip("# ").strip() for ln in lines if ln.startswith("#")]
        heading_text = "\n".join(headings).lower()
        body = text.lower()

        # 权重：路径 > 标题 > 正文；onboarding 文档额外加权，优先给新人入口
        score = 6 if "onboarding/" in name else 0
        hits: list[str] = []
        for term in lowered:
            score += name.count(term) * 8
            score += heading_text.count(term) * 4
            score += body.count(term)
            for heading in headings:
                if term in heading.lower():
                    hits.append(heading)
        if score <= 0:
            continue
        # 同名标题去重，保留前 3 条
        uniq: list[str] = []
        for h in hits:
            if h not in uniq:
                uniq.append(h)
        results.append({"path": str(rel).replace("\\", "/"), "score": score, "hits": uniq[:3]})

    results.sort(key=lambda item: (-item["score"], item["path"]))
    return results[:limit]


def main(argv: list[str] | None = None) -> int:
    """命令行入口：解析参数、打印命中结果；无命中返回 1。"""
    parser = argparse.ArgumentParser(description="按关键词查找 PilotStd 文档")
    parser.add_argument("query", help="关键词，空格分隔，例如：通知 未读 聚合")
    parser.add_argument("--root", default=str(DEFAULT_DOCS), help="文档根目录")
    parser.add_argument("--limit", type=int, default=8, help="最多返回条数")
    args = parser.parse_args(argv)

    results = search(Path(args.root), args.query, args.limit)
    if not results:
        print("没有匹配的文档。换个关键词，或先看 docs/onboarding/README.md。")
        return 1

    print(f"关键词：{args.query}")
    for idx, item in enumerate(results, 1):
        print(f"{idx}. {item['path']}  (score={item['score']})")
        for hit in item["hits"]:
            print(f"   - {hit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
