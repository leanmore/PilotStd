#!/usr/bin/env python3
"""Phase 2a POC：附件解析效果人工评估

用法:
    python scripts/poc_attachment_parser.py

流程:
    1. 用 SamrGbCrawler 抓取最新 5 条 GB 公告
    2. 对每条公告，分别记录 HTML 解析结果和附件解析结果
    3. 输出到 data/poc_attachment_results.json（人工阅读）
    4. 人工逐条标记：完全可用 / 部分可用 / 不可用
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pilotstd.announcement.adapters import SamrGbCrawler  # noqa: E402
from pilotstd.announcement.parser import parse_announcement_detail  # noqa: E402

# ── 全局收集器 ──
poc_log: list[dict[str, Any]] = []


def make_patched_parse_items(original_func):
    """返回一个 monkey-patched _parse_items，捕获附件解析详情。"""

    def _patched(self, raw_detail, ocr_provider=None):
        from pilotstd.announcement.parser import find_attachment_url as _find_url

        # 先走原始流程（正常入库）
        items = original_func(self, raw_detail, ocr_provider)

        # ── POC 附加：捕获附件解析的完整过程 ──
        attachment_url = _find_url(raw_detail) or ""

        # 解析 HTML 表格（Layer 1）
        html_items, html_meta = parse_announcement_detail(raw_detail, None, "", ocr_provider=ocr_provider)

        entry: dict[str, Any] = {
            "attachment_url": attachment_url,
            "html_meta": html_meta,
            "html_items": html_items,
            "html_count": len(html_items),
            "att_items": [],
            "att_count": 0,
            "att_error": None,
        }

        # 有附件时，独立跑一次附件解析（不影响主流程）
        if attachment_url:
            try:
                att_bytes = self._download_attachment(attachment_url)
                if att_bytes:
                    att_items, _att_meta = parse_announcement_detail(
                        raw_detail, att_bytes, attachment_url, ocr_provider=ocr_provider
                    )
                    # 只保留附件独有、HTML 未覆盖的条目
                    html_codes = {(i.get("std_code", ""), i.get("std_name", "")[:20]) for i in html_items}
                    att_only = [
                        i for i in att_items if (i.get("std_code", ""), i.get("std_name", "")[:20]) not in html_codes
                    ]
                    entry["att_items"] = att_only
                    entry["att_count"] = len(att_only)
                else:
                    entry["att_error"] = "download returned None"
            except Exception as e:
                entry["att_error"] = str(e)

        poc_log.append(entry)
        return items

    return _patched


def main():
    print("Phase 2a POC: 公告附件解析效果评估")
    print("=" * 50)

    # 挂载 patch
    original = SamrGbCrawler._parse_items
    SamrGbCrawler._parse_items = make_patched_parse_items(original)

    try:
        crawler = SamrGbCrawler()
        since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"抓取 GB 公告 (since={since}, page_size=5)...")
        items = crawler.fetch_announcements(since_date=since, page_size=5)

        print(f"抓取完成: {len(items)} 条标准记录")
        print(f"其中 {len(poc_log)} 条公告有详情页解析记录")

        # 分类统计
        with_att = [e for e in poc_log if e["attachment_url"]]
        no_att = [e for e in poc_log if not e["attachment_url"]]
        att_has_result = [e for e in with_att if e["att_count"] > 0]
        att_empty = [e for e in with_att if e["att_count"] == 0 and not e.get("att_error")]
        att_error = [e for e in with_att if e.get("att_error")]

        print(f"\n┌─ HTML 表格解析: {sum(e['html_count'] for e in poc_log)} 条")
        print(f"├─ 有附件的公告: {len(with_att)} 条")
        print(f"│  ├─ 附件解析有补充: {len(att_has_result)} 条")
        print(f"│  ├─ 附件无补充: {len(att_empty)} 条")
        print(f"│  └─ 附件下载/解析失败: {len(att_error)} 条")
        print(f"└─ 纯 HTML 公告: {len(no_att)} 条")

        # 输出 JSON
        out_path = PROJECT_ROOT / "data" / "poc_attachment_results.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_at": datetime.now().isoformat(),
                    "total_announcements": len(poc_log),
                    "with_attachments": len(with_att),
                    "att_has_result": len(att_has_result),
                    "att_empty": len(att_empty),
                    "att_error": len(att_error),
                    "entries": poc_log,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"\n详细结果已写入: {out_path}")
        print("\n下一步: 打开 JSON 文件，逐条核对附件解析结果，标记:")
        print("  [OK] 完全可用 / [WARN] 部分可用 / [FAIL] 不可用")

    finally:
        # 恢复原始方法
        SamrGbCrawler._parse_items = original


if __name__ == "__main__":
    main()
