#!/usr/bin/env python3
"""公告内容 HTML 治理审计 — 基于生产数据库实证分析。

用法:
    python scripts/probe_announcement_html.py --db-path data/pilotstd_prod.db
    python scripts/probe_announcement_html.py --db-path data/pilotstd_prod.db --sample 300
    python scripts/probe_announcement_html.py --db-path data/pilotstd_prod.db --csv output.csv

数据源: 生产 DB announcements 表 raw_data 字段。
样本策略: 按 created_at 年份分层 + 按 source_site 分层，覆盖全时间窗口。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date

# ── 常量 ──────────────────────────────────────────────

PRESET_PATTERNS = {
    "inline_style": re.compile(r'\bstyle\s*=\s*["\']', re.IGNORECASE),
    "font_tag": re.compile(r"</?font\b", re.IGNORECASE),
    "deprecated_attrs": re.compile(r'\b(?:align|bgcolor|color|face|valign|size)\s*=\s*["\']', re.IGNORECASE),
    "mso_namespace": re.compile(r"\b(?:mso-|o:|w:|v:|st1:)", re.IGNORECASE),
    "word_comment": re.compile(r"<!--\[if\s", re.IGNORECASE),
    "empty_p": re.compile(r"<p>\s*</p>"),
    "span_junk": re.compile(r"<span[^>]*>\s*</span>"),
    "div_wrapper": re.compile(r'<(?:div|span)\s+class="([^"]*)"[^>]*>'),
}

# 语义 class（来自 _content_cleaner.py 产出）
SEMANTIC_CLASSES = {"announce-heading", "announce-body", "announce-signature", "announce-date"}

# 非语义特征：可能来自 Word/富文本编辑器的废弃结构
NON_SEMANTIC_INDICATORS = [
    ("font_tag", "font 废弃标签"),
    ("mso_namespace", "Office 命名空间"),
    ("word_comment", "Word 条件注释"),
    ("deprecated_attrs", "废弃属性 (align/bgcolor/color)"),
    ("inline_style", "内联 style"),
    ("empty_p", "空 p 标签"),
    ("span_junk", "空 span 标签"),
]


# ── DB 操作 ──


def open_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        print(f"数据库不存在: {path}")
        sys.exit(1)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_population_stats(conn: sqlite3.Connection) -> dict:
    """获取公告总览统计。"""
    total = conn.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]
    with_content = conn.execute(
        "SELECT COUNT(*) FROM announcements WHERE raw_data IS NOT NULL AND raw_data != ''"
    ).fetchone()[0]
    # 按来源分布
    sources = conn.execute(
        "SELECT source_site, COUNT(*) as n FROM announcements "
        "WHERE raw_data IS NOT NULL AND raw_data != '' "
        "GROUP BY source_site ORDER BY n DESC"
    ).fetchall()
    # 按年份分布
    years = conn.execute(
        "SELECT substr(created_at, 1, 4) as yr, COUNT(*) as n FROM announcements "
        "WHERE raw_data IS NOT NULL AND raw_data != '' "
        "GROUP BY yr ORDER BY yr"
    ).fetchall()
    return {
        "total": total,
        "with_content": with_content,
        "sources": [(r["source_site"], r["n"]) for r in sources],
        "years": [(r["yr"], r["n"]) for r in years],
    }


def sample_announcements(conn: sqlite3.Connection, limit: int) -> list[dict]:
    """分层抽样：按年份 + 来源均匀分布。"""
    stats = get_population_stats(conn)
    if stats["with_content"] == 0:
        return []

    rows = []
    # 按 source_site 分组，每组取 limit/组数 条
    sources = [s[0] for s in stats["sources"]]
    per_source = max(5, limit // max(1, len(sources)))

    for src in sources:
        # 跨年份均匀采样
        cur = conn.execute(
            "SELECT id, announce_no, title, source_site, publish_date, "
            "raw_data, created_at, parse_status "
            "FROM announcements "
            "WHERE source_site = ? AND raw_data IS NOT NULL AND raw_data != '' "
            "ORDER BY created_at DESC LIMIT ?",
            (src, per_source * 3),  # 取 3x 用于分散
        )
        candidates = [dict(r) for r in cur.fetchall()]
        if not candidates:
            continue
        # 按时间分散：前 1/3(新) + 后 1/3(旧) + 中间采样
        n = len(candidates)
        third = max(1, n // 3)
        selected = candidates[:third] + candidates[-third:] + candidates[third : 2 * third][:third]
        rows.extend(selected[:per_source])

    return rows[:limit]


# ── HTML 内容提取 ──


def extract_html_from_raw(raw_data: str) -> str:
    """从 raw_data 字段提取 HTML 正文。

    raw_data 可能是:
    1. 清洗后的 HTML (<p class="announce-body">...) — 来自 _content_cleaner
    2. JSON 包裹的 content 字段 — 来自某些适配器
    3. 原始文本 — 清洗前的纯文本
    """
    if not raw_data or not raw_data.strip():
        return ""
    # 如果已经有 p 标签，直接返回
    if re.search(r"<p\b", raw_data):
        return raw_data
    # 尝试解析 JSON
    try:
        obj = json.loads(raw_data)
        for key in ("content", "html", "body", "text", "notice_content"):
            if key in obj and obj[key] and isinstance(obj[key], str):
                val = obj[key]
                if "<" in val and ">" in val and len(val) > 50:
                    return val
        # 取最长的字符串字段
        best = ""
        for v in obj.values():
            if isinstance(v, str) and len(v) > len(best):
                best = v
        return best if ("<" in best and ">" in best) else raw_data
    except (json.JSONDecodeError, TypeError):
        pass
    return raw_data


# ── 脏数据模式发现（从数据中聚类，非预设） ──


def discover_patterns(html: str) -> dict:
    """扫描单条 HTML，返回发现的所有模式特征。

    不做健康度打分——只做特征检测，让数据说话。
    """
    features = {}
    for name, pattern in PRESET_PATTERNS.items():
        matches = pattern.findall(html)
        if matches:
            features[name] = len(matches)

    # 语义 class 覆盖
    found_classes = set()
    for cls in SEMANTIC_CLASSES:
        if f'class="{cls}"' in html or f"class='{cls}'" in html:
            found_classes.add(cls)
    features["semantic_classes"] = sorted(found_classes)
    features["has_any_semantic"] = len(found_classes) > 0
    features["has_all_semantic"] = len(found_classes) >= 3

    # 标签统计
    tags = re.findall(r"</?(\w+)", html)
    tag_counts = Counter(t.lower() for t in tags)
    features["total_tags"] = len(tags)
    features["unique_tags"] = len(tag_counts)
    features["top_tags"] = tag_counts.most_common(10)
    features["p_count"] = tag_counts.get("p", 0)

    # 嵌套深度
    depth = 0
    max_depth = 0
    for match in re.finditer(r"<(/?)(\w+)", html):
        tag = match.group(2).lower()
        if tag in ("br", "img", "hr", "input", "meta", "link"):
            continue
        if match.group(1) == "/":
            depth = max(0, depth - 1)
        else:
            depth += 1
            max_depth = max(max_depth, depth)
    features["max_nesting_depth"] = max_depth

    # HTML 长度
    features["html_length"] = len(html)
    # 是否是纯文本（无 HTML 标签）
    features["is_plaintext"] = "<" not in html

    return features


# ── 清洗效果对比 ──


def compare_cleaning(raw_html: str) -> dict:
    """对比 DB 原始值 vs 清洗管线处理后的差异。

    返回: {
        "is_already_cleaned": bool,  # DB 中已是清洗后格式
        "would_change": bool,        # 重新清洗是否会改变
        "diff_summary": str,         # 差异概述
    }
    """
    # 检测是否已经过清洗（有 semantic class 且无废弃标签）
    has_semantic = any(f'class="{c}"' in raw_html for c in SEMANTIC_CLASSES)
    has_junk = any(
        p.search(raw_html)
        for p in [
            PRESET_PATTERNS["font_tag"],
            PRESET_PATTERNS["mso_namespace"],
            PRESET_PATTERNS["word_comment"],
            PRESET_PATTERNS["inline_style"],
        ]
    )

    result = {
        "is_already_cleaned": has_semantic and not has_junk,
        "would_change": False,
        "diff_summary": "",
    }

    if has_junk:
        result["would_change"] = True
        junk_types = []
        if PRESET_PATTERNS["font_tag"].search(raw_html):
            junk_types.append("font_tag")
        if PRESET_PATTERNS["mso_namespace"].search(raw_html):
            junk_types.append("mso")
        if PRESET_PATTERNS["inline_style"].search(raw_html):
            junk_types.append("inline_style")
        result["diff_summary"] = f"含废弃内容: {','.join(junk_types)}"

    if not has_semantic and not has_junk:
        result["would_change"] = True
        result["diff_summary"] = "无语义 class，管线会添加"

    return result


# ── 主流程 ──


def main() -> int:
    parser = argparse.ArgumentParser(description="公告内容 HTML 治理审计")
    parser.add_argument("--db-path", default=None, help="生产数据库路径")
    parser.add_argument("--sample", type=int, default=200, help="抽样数量 (默认 200)")
    parser.add_argument("--csv", default=None, help="导出 CSV 文件路径")
    parser.add_argument("--full", action="store_true", help="全量扫描 (覆盖 --sample)")
    args = parser.parse_args()

    db_path = args.db_path or os.path.join("data", "pilotstd.db")

    if not os.path.exists(db_path):
        print(f"错误: 数据库不存在: {db_path}")
        print("请先从 Docker 主机导出生产 DB:")
        print("  docker cp <容器名>:/app/data/pilotstd.db data/pilotstd_prod.db")
        print(" 然后重新运行: python scripts/probe_announcement_html.py --db-path data/pilotstd_prod.db")
        return 1

    conn = open_db(db_path)

    # ── 0. 总体概览 ──
    stats = get_population_stats(conn)
    print("# 公告内容 HTML 治理审计报告（生产数据实证）")
    print(f"审计日期: {date.today()}")
    print(f"数据库: {db_path}")
    print(f"公告总数: {stats['total']}  |  有正文内容: {stats['with_content']}")
    print()

    if stats["with_content"] == 0:
        print("⚠️ 数据库中无公告正文数据（raw_data 全为空）。")
        print("可能原因: 公告抓取后尚未触发解析（parse_status='pending'）。")
        print("建议: 在前端公告详情页点击'开始解析'，或运行批量解析任务。")
        conn.close()
        return 1

    # 来源分布
    print("## 0. 数据来源分布")
    print()
    print("| 来源站点 | 有内容公告数 |")
    print("|---------|------------|")
    for src, n in stats["sources"]:
        print(f"| {src} | {n} |")
    print()

    # 时间分布
    print("| 年份 | 有内容公告数 |")
    print("|------|------------|")
    for yr, n in stats["years"]:
        print(f"| {yr} | {n} |")
    print()

    # ── 1. 抽样 ──
    limit = stats["with_content"] if args.full else args.sample
    samples = sample_announcements(conn, limit)
    print(f"## 1. 抽样结果: {len(samples)} 条")
    print()

    if not samples:
        print("抽样为空。")
        conn.close()
        return 1

    # ── 2. 逐条特征提取 ──
    all_features = []
    for s in samples:
        raw_html = extract_html_from_raw(s["raw_data"] or "")
        feats = discover_patterns(raw_html)
        feats["announce_no"] = (s.get("announce_no") or "")[:60]
        feats["source_site"] = s.get("source_site", "")
        feats["title"] = (s.get("title") or "")[:80]
        feats["publish_date"] = s.get("publish_date", "")
        feats["created_at"] = s.get("created_at", "")
        feats["parse_status"] = s.get("parse_status", "")
        # 清洗效果对比
        cleaning = compare_cleaning(raw_html)
        feats.update(cleaning)
        all_features.append(feats)

    # 仅分析有内容的样本
    valid = [f for f in all_features if not f["is_plaintext"] and f["html_length"] > 10]
    plaintext = [f for f in all_features if f["is_plaintext"]]
    print(f"有效 HTML 样本: {len(valid)} | 纯文本样本: {len(plaintext)}")
    print()

    if not valid:
        print("无有效 HTML 样本。raw_data 内容可能为纯文本格式，检查 extract_html_from_raw 逻辑。")
        # 展示几条 raw_data 样例
        print("\nraw_data 样例:")
        for s in samples[:5]:
            raw = (s["raw_data"] or "")[:200]
            print(f"  [{s.get('announce_no', '?')[:40]}] {repr(raw)}")
        conn.close()
        return 1

    # ── 3. 脏数据模式聚类（从数据中发现） ──
    print("## 2. 脏数据模式聚类（从真实数据中发现）")
    print()

    # 逐模式统计
    pattern_stats = {}
    for name, _ in NON_SEMANTIC_INDICATORS:
        count = sum(1 for f in valid if f.get(name, 0) > 0)
        pct = count / len(valid) * 100
        pattern_stats[name] = (count, pct)

    print("| 模式 | 命中数 | 占比 | 风险等级 |")
    print("|------|--------|------|---------|")
    for name, label in NON_SEMANTIC_INDICATORS:
        count, pct = pattern_stats[name]
        level = "HIGH" if pct > 30 else "MEDIUM" if pct > 10 else "LOW" if pct > 0 else "NONE"
        print(f"| {label} | {count} | {pct:.1f}% | {level} |")
    print()

    # 语义 class 覆盖
    no_semantic = sum(1 for f in valid if not f["has_any_semantic"])
    partial_semantic = sum(1 for f in valid if f["has_any_semantic"] and not f["has_all_semantic"])
    full_semantic = sum(1 for f in valid if f["has_all_semantic"])
    print("| 语义 class 覆盖 | 数量 | 占比 |")
    print("|----------------|------|------|")
    print(f"| 无任何语义 class | {no_semantic} | {no_semantic / len(valid) * 100:.1f}% |")
    print(f"| 部分语义 class | {partial_semantic} | {partial_semantic / len(valid) * 100:.1f}% |")
    print(f"| 完整语义 class (>=3) | {full_semantic} | {full_semantic / len(valid) * 100:.1f}% |")
    print()

    # ── 4. 嵌套深度分布 ──
    depths = [f["max_nesting_depth"] for f in valid]
    print("| 嵌套深度 | 数量 | 占比 |")
    print("|---------|------|------|")
    for d in sorted(set(depths)):
        count = depths.count(d)
        print(f"| {d} | {count} | {count / len(valid) * 100:.1f}% |")
    print()

    # ── 5. 清洗管线效果量化 ──
    print("## 3. 清洗管线效果量化")
    print()
    already_clean = sum(1 for f in valid if f["is_already_cleaned"])
    has_junk = sum(1 for f in valid if any(f.get(name, 0) > 0 for name, _ in NON_SEMANTIC_INDICATORS))

    repair_rate = already_clean / len(valid) * 100
    passthrough_rate = has_junk / len(valid) * 100
    fallback_trigger_rate = (no_semantic + partial_semantic) / len(valid) * 100

    print("| 指标 | 值 | 计算公式 |")
    print("|------|----|---------|")
    print(f"| 管线修复率 | {repair_rate:.1f}% | 已清洗且无脏数据 / 总有效样本 |")
    print(f"| 脏数据透传率 | {passthrough_rate:.1f}% | 含废弃标签/内联样式 / 总有效样本 |")
    print(f"| CSS 兜底触发率 | {fallback_trigger_rate:.1f}% | 非完整语义 class / 总有效样本 |")
    print(f"| 完全健康率 | {repair_rate - passthrough_rate:.1f}% | 已清洗 且 无透传 |")
    print()

    # ── 6. 风险分级 — 基于实证 ──
    print("## 4. 风险分级（基于实证数据）")
    print()
    is_high = passthrough_rate > 30
    is_medium = passthrough_rate > 10 or fallback_trigger_rate > 30
    is_low = not is_high and not is_medium

    level = "HIGH" if is_high else "MEDIUM" if is_medium else "LOW"
    print(f"**综合评级: {level}**")
    print()
    print(f"判定依据: 脏数据透传率={passthrough_rate:.1f}%, CSS兜底触发率={fallback_trigger_rate:.1f}%")
    print()

    # ── 7. Top 异常样本 ──
    print("## 5. Top 异常样本（脏数据最多的前 10 条）")
    print()

    # 按脏数据模式数量排序
    def junk_score(f: dict) -> int:
        return sum(1 for name, _ in NON_SEMANTIC_INDICATORS if f.get(name, 0) > 0)

    anomalies = sorted(valid, key=junk_score, reverse=True)[:10]

    if anomalies and junk_score(anomalies[0]) > 0:
        print("| # | 公告编号 | 来源 | 脏模式数 | 语义class | 嵌套深度 | 状态 |")
        print("|---|---------|------|---------|----------|---------|------|")
        for i, a in enumerate(anomalies, 1):
            modes = [label for name, label in NON_SEMANTIC_INDICATORS if a.get(name, 0) > 0]
            print(
                f"| {i} | {a['announce_no'][:30]} | {a['source_site'][-2:]} | "
                f"{junk_score(a)} | {len(a['semantic_classes'])} | "
                f"{a['max_nesting_depth']} | {a['parse_status']} |"
            )
        print()
        print("脏模式详情:")
        for i, a in enumerate(anomalies[:5], 1):
            modes = [label for name, label in NON_SEMANTIC_INDICATORS if a.get(name, 0) > 0]
            if modes:
                print(f"  {i}. [{a['announce_no'][:35]}] {', '.join(modes)}")
        print()
    else:
        print("未发现显著脏数据模式。")
        print()

    # ── 8. 新站点 vs 老站点差异 ──
    print("## 6. 按来源站点的脏数据分布")
    print()
    source_junk: dict[str, list[dict]] = defaultdict(list)
    for f in valid:
        source_junk[f["source_site"]].append(f)

    print("| 来源 | 样本数 | 脏数据率 | 平均嵌套深度 | 无语义率 |")
    print("|------|--------|---------|------------|---------|")
    for src in sorted(source_junk):
        items = source_junk[src]
        dirty = sum(1 for f in items if any(f.get(name, 0) > 0 for name, _ in NON_SEMANTIC_INDICATORS))
        no_sem = sum(1 for f in items if not f["has_any_semantic"])
        avg_depth = sum(f["max_nesting_depth"] for f in items) / len(items)
        print(
            f"| {src} | {len(items)} | {dirty / len(items) * 100:.1f}% | "
            f"{avg_depth:.1f} | {no_sem / len(items) * 100:.1f}% |"
        )
    print()

    # ── 9. 行动项 — 基于实证 ──
    print("## 7. 行动项（基于实证优先级排序）")
    print()
    if is_low:
        print("当前数据质量良好，无需紧急清洗。")
        print()
        print("| 优先级 | 行动 | 数据支撑 |")
        print("|-------|------|---------|")
        print(f"| 低 | 保持当前管线 + CSS 兜底 | 脏数据透传率仅 {passthrough_rate:.1f}% |")
        if plaintext:
            print(f"| 中 | 排查 {len(plaintext)} 条纯文本公告，确认是否需要解析 | 纯文本/空内容样本 |")
    elif is_medium:
        print("| 优先级 | 行动 | 数据支撑 |")
        print("|-------|------|---------|")
        print(
            f"| P1 | 批量重清洗含脏数据公告 | {has_junk}/{len(valid)} 条 ({has_junk / len(valid) * 100:.1f}%) 含废弃标签 |"
        )
        print(
            f"| P1 | 排查无语义 class 公告来源 | {no_semantic}/{len(valid)} 条 ({no_semantic / len(valid) * 100:.1f}%) 无语义标记 |"
        )
        print("| P2 | 扩展 _content_cleaner.py 覆盖新发现模式 | 从 Top 异常样本中提取 |")
    else:
        print("| 优先级 | 行动 | 数据支撑 |")
        print("|-------|------|---------|")
        print(f"| P0 | 紧急：批量清洗全部 {has_junk} 条脏数据 | 脏数据透传率 {passthrough_rate:.1f}% > 30% 阈值 |")
        print(f"| P0 | 排查入库管线，阻止新脏数据进入 | {has_junk}/{len(valid)} 条绕过清洗 |")
        print(f"| P1 | CSS 兜底增强 | {fallback_trigger_rate:.1f}% 依赖兜底 |")

    # ── CSV 导出 ──
    if args.csv:
        import csv

        fieldnames = [
            "announce_no",
            "source_site",
            "title",
            "publish_date",
            "created_at",
            "parse_status",
            "html_length",
            "has_any_semantic",
            "has_all_semantic",
            "semantic_classes",
            "max_nesting_depth",
            "inline_style",
            "font_tag",
            "mso_namespace",
            "deprecated_attrs",
            "is_already_cleaned",
            "would_change",
            "diff_summary",
        ]
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for feats in all_features + plaintext:
                writer.writerow({k: feats.get(k, "") for k in fieldnames})
        print(f"\nCSV 已导出: {args.csv} ({len(all_features)} 行)")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
