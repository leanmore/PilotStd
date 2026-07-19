# pilotstd/announcement/matcher.py
# 公告交叉比对器 — 公告标准清单 ↔ file_index，更新 announcement_match

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional, Set

from ..core.db import Database
from ..core.file_index import FILE_INDEX_TABLE

logger = logging.getLogger(__name__)

CACHE_TABLE = "announcement_match"

# ── clean_announcement_content 常量 ──────────────────────────

# 标准号行首正则（防误伤正文中的字母组合）
_STD_CODE_LINE_PATTERN = re.compile(
    r"^(GB|GB/T|GB/Z|HG|HG/T|JB|JB/T|SN|SN/T|WS|WS/T|MH|MH/T|"
    r"YB|YB/T|YS|YS/T|JT|JT/T|TY|TY/T|DB|DB/T|DY|DY/T|"
    r"FZ|QB|QC|SJ|WJ|YD|GY|LY|MT|NB|YC|JR|DZ|HY|TD|"
    r"DL|TB|YY|AQ)\s*[\d ]"
)

# 统计汇总表 + 标准清单表列名关键词
_STATS_COLUMN_KEYWORDS = [
    # 统计汇总表（备案月报）
    "标准发布部门",
    "省市区",
    "行业领域",
    "备案数量",
    "发布部门",
    "备案单位",
    "统计",
    "合计",
    # 标准清单表（国标/行标/地标公告）
    "标准编号",
    "标准名称",
    "代替标准",
    "实施日期",
    "发布日期",
    "作废日期",
    "废止日期",
    "主管部门",
    "代替标准号",
    "备案号",
    "复审结论",
]

# 公告引言段落模式（退出表格区块的信号）
_ANNOUNCEMENT_INTRO_PATTERN = re.compile(r"\d{4}年\d{1,2}月.*(?:共(?:发布|废止)|批准|公告如下|现予以|现发布)\d*项?")

# 独立日期行模式
_DATE_LINE_PATTERN = re.compile(r"^\d{4}[-年]\d{1,2}[-月]\d{1,2}日?$")

# 附表标题模式
_APPENDIX_TITLE_PATTERN = re.compile(r"^附表\d+")

# 落款日期拆分模式：末尾 "机关名称 日期"
_SIGNATURE_DATE_PATTERN = re.compile(
    r"(.{4,}(?:委员会|管理局|总局|部|厅|局|院|中心|公司|协会))\s+(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)$"
)


def clean_announcement_content(content: str) -> str:
    """状态机清洗公告正文：剥离标准清单表格，保留公文引言和废止段落。

    逐行处理，三种状态转移：
      - 进入表格：序号+统计列名 / 附表标题 / 标准号行首 / "中文名称："
      - 退出表格：公告引言段落 / 独立日期行
      - 正常文本：保留

    输出：包裹 <p> 标签的 HTML 字符串，落款日期自动拆分右对齐。
    """
    if not content:
        return ""

    lines = content.split("\n")
    result: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not in_table:
                result.append("")
            continue

        # ── 进入/退出表格区块检测 ──
        if _is_table_entry(stripped):
            in_table = True
            continue
        if in_table and _is_table_exit(stripped):
            in_table = False
            result.append(stripped)
            continue
        if in_table:
            continue

        # ── 正常文本：保留 ──
        result.append(stripped)

    # ── 后处理：包裹 <p> 标签 ──
    paragraphs: list[str] = []
    current: list[str] = []
    for line in result:
        if line == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))

    if not paragraphs:
        return ""

    # ── 落款日期拆分：最后一段若含机关名+日期，拆为两行 ──
    if paragraphs:
        last = paragraphs[-1]
        m = _SIGNATURE_DATE_PATTERN.search(last)
        if m:
            org = m.group(1).strip()
            date = m.group(2).strip()
            # 替换最后一段：机关名独立行 + 日期独立行
            prefix = last[: m.start()].strip()
            if prefix:
                paragraphs[-1] = prefix
                paragraphs.append(org)
            else:
                paragraphs[-1] = org
            paragraphs.append(date)

    # 构建 HTML
    html_parts = ["<p>" + p + "</p>" for p in paragraphs]
    # 最后一段若是日期行，加右对齐样式
    if paragraphs and _DATE_LINE_PATTERN.match(paragraphs[-1]):
        html_parts[-1] = '<p style="text-align:right">' + paragraphs[-1] + "</p>"

    return "\n".join(html_parts)


def _is_table_entry(stripped: str) -> bool:
    """检测是否进入表格区块。"""
    # ① 序号行 + 列名关键词
    if stripped.startswith("序号"):
        if any(kw in stripped for kw in _STATS_COLUMN_KEYWORDS):
            return True
    # ② 数据行：行首数字 + 标准号模式
    if re.match(r"^\d+\s+[A-Z]+[/\s]", stripped):
        return True
    # ③ 附表标题
    if _APPENDIX_TITLE_PATTERN.match(stripped):
        return True
    # ④ 标准号行首
    if _STD_CODE_LINE_PATTERN.match(stripped):
        return True
    # ⑤ "中文名称：" 行
    if stripped.startswith("中文名称：") or stripped.startswith("中文名称:"):
        return True
    # ⑥ 多列名聚合（≥3个统计关键词）
    if sum(1 for kw in _STATS_COLUMN_KEYWORDS if kw in stripped) >= 3:
        return True
    return False


def _is_table_exit(stripped: str) -> bool:
    """检测是否退出表格区块。"""
    # ① 公告引言/废止段落
    if _ANNOUNCEMENT_INTRO_PATTERN.search(stripped):
        return True
    # ② 独立日期行
    if _DATE_LINE_PATTERN.match(stripped):
        return True
    # ③ 中文序号段首（一、二、…）
    if re.match(r"^[一二三四五六七八九十\d]+[、．.]", stripped) and len(stripped) > 10:
        return True
    # ④ 不含制表符且含中文标点 → 叙事文本
    if "\t" not in stripped and re.search(r"[。；，、]", stripped) and len(stripped) > 20:
        return True
    return False


class AnnouncementMatcher:
    """将公告中的标准清单与本地 file_index 交叉比对，
    发现匹配时更新 announcement_match。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def match_and_update(
        self,
        items: list[dict[str, Any]],
        source_site: str = "announcement",
    ) -> dict[str, Any]:
        """逐条公告明细比对 file_index，命中则写入两张表（批量模式）。

        入库前先按 announce_no 归一化：同一公告的所有条目强制统一 publish_date、
        announcement_title、standard_count，消除 HTML/PDF 混合解析导致的字段不一致。
        """
        result: dict[str, Any] = {"matched": 0, "updated": 0, "details": []}
        if not items:
            return result

        # ── 归一化：按公告号合并元数据 ──
        items = self._normalize(items)

        log_rows: list[tuple[Any, ...]] = []
        cache_rows: list[tuple[Any, ...]] = []
        now = datetime.now().isoformat()

        for item in items:
            self._process_item(item, source_site, now, log_rows, cache_rows, result)

        # 批量写入：先写记录表再写缓存表，减少数据库往返次数
        if log_rows:
            self._bulk_insert_records(log_rows)
            # 入库成功后回写 parse_status，确保有数据的公告不显示"待解析"
            announce_nos = {row[2] for row in log_rows}
            for anno in announce_nos:
                self._db.execute(
                    "UPDATE announcements SET parse_status='completed', updated_at=? WHERE announce_no=?",
                    (now, anno),
                )
        if cache_rows:
            self._bulk_upsert_cache(cache_rows)
        return result

    @staticmethod
    def _normalize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按 announce_no 分组，统一各条目的公告级元数据。

        - publish_date: 取组内第一个非空值
        - announcement_title: 取组内第一个非空值
        - standard_count: 动态计算 = 该公告下条目总数

        ⚠️ 警告：standard_count 在此处仅表示"所属公告包含的条目数"，
        同一公告的所有记录共享此值，不代表全局唯一标准数。
        统计总数时必须使用 COUNT(*) 或 COUNT(DISTINCT standard_number)，
        严禁使用 SUM(standard_count)，否则会导致数据呈 N² 膨胀。
        """
        from collections import defaultdict

        # 按公告号分组，同公告条目汇聚以便统一元数据
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            anno = item.get("announce_no", "")
            if anno:
                groups[anno].append(item)

        for anno, group in groups.items():
            # 找第一个非空的 publish_date
            best_date = ""
            for it in group:
                d = it.get("publish_date", "")
                if d:
                    best_date = d
                    break
            # 找第一个非空的 title
            best_title = ""
            for it in group:
                t = it.get("announcement_title", "")
                if t:
                    best_title = t
                    break
            # 实际条目数（非全局去重数，仅表示同公告下条目数量）
            total = len(group)

            for idx, it in enumerate(group):
                if best_date:
                    it["publish_date"] = best_date
                if best_title:
                    it.setdefault("announcement_title", best_title)
                it["standard_count"] = total
                it["row_index"] = idx + 1  # 同公告内从 1 开始递增

        return items

    def _process_item(self, item, source_site, now, log_rows, cache_rows, result):
        """逐条处理公告明细：解析标准编号 → 查 file_index → 命中则写缓存和日志。"""
        std_code = item.get("std_code", "")
        replaces_code = item.get("replaces_code", "")
        pid = item.get("_pid", "")
        announce_no = item.get("announce_no", "")
        publish_date = item.get("publish_date", "")
        std_name = item.get("std_name", "")
        implement_date = item.get("implementation_date", "")
        expiry_date = item.get("expiry_date", "")
        confidence = item.get("confidence", 0.0)
        row_index = item.get("row_index", 0)

        parsed = self._parse_std_code(std_code)
        if not parsed:
            return

        matches = self._find_in_file_index(parsed["logical_code"], parsed["number"])
        match_type = "new"

        # 直接匹配失败时，用 replaces_code 尝试替代号匹配
        if not matches and replaces_code:
            replaced_parsed = self._parse_std_code(replaces_code)
            if replaced_parsed:
                matches = self._find_in_file_index(replaced_parsed["logical_code"], replaced_parsed["number"])
                match_type = "replaced"

        matched = 1 if matches else 0
        log_rows.append(
            (
                source_site,
                pid,
                announce_no,
                std_code,
                std_name or None,
                publish_date,
                implement_date,
                expiry_date,
                replaces_code,
                confidence,
                row_index,
                "draft",
                now,
                matched,
                item.get("announcement_title", "") or None,
                item.get("standard_count"),
            )
        )

        if not matches:
            return
        result["matched"] += 1
        for fi_row in matches:
            updated = self._build_cache_row(fi_row, item, match_type, source_site, now, cache_rows)
            if updated:
                result["updated"] += 1
                detail = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
                if match_type == "replaced":
                    detail += f" -> {std_code}"
                result["details"].append(detail)

    def _parse_std_code(self, std_code: str) -> Optional[dict[str, Any]]:
        """解析标准编号字符串为 logical_code + number。委托公用解析器。"""
        from ..core.std_utils import parse_std_number

        r = parse_std_number(std_code)
        if r:
            return {"logical_code": r["code"], "number": r["number"]}
        return None

    def _find_in_file_index(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """在 file_index 中查找匹配 logical_code + number 的记录。"""
        return self._db.fetchall(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=?",
            (logical_code, number),
        )

    def _build_cache_row(
        self,
        fi_row,
        item,
        match_type,
        source_site,
        now,
        cache_rows,
    ) -> bool:
        """构建公告缓存行：根据实施日期判定状态（现行/即将实施/被代替），写入缓存列表。"""
        std_number = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
        today = datetime.now().date()
        implementation_date = item.get("implementation_date", "")
        publish_date = item.get("publish_date", "")

        # 状态判定优先级：被代替 > 即将实施 > 现行
        if match_type == "replaced":
            status = "被代替"
        elif implementation_date:
            try:
                impl_date = datetime.fromisoformat(implementation_date).date()
                status = "即将实施" if today < impl_date else "现行"
            except (ValueError, TypeError):
                status = "现行"
        else:
            status = "现行"

        cache_data = {
            "status": status,
            "standard_name": fi_row["std_name"] or item.get("std_name", ""),
            "replaces": item.get("replaces_code", ""),
            "publish_date": publish_date,
            "implementation_date": implementation_date,
            "announcement_title": item.get("announcement_title", ""),
            "attachment_url": item.get("attachment_url", ""),
            "attachment_path": item.get("attachment_path", ""),
            "match_status": "exact",
            "is_adopted": False,
            "source_site": source_site,
        }

        result_json = json.dumps(cache_data, ensure_ascii=False)
        cache_rows.append((std_number, source_site, result_json, now, None))
        logger.info("公告更新缓存: %s -> %s", std_number, status)
        return True

    def _get_complete_pids(self, source_site: str) -> Set[str]:
        """返回已完全解析的公告 PID 集合（所有条目 std_name 均非空）。"""
        # HAVING COUNT(*) = COUNT(std_name) 确保该公告下所有条目都有名称
        cursor = self._db.execute(
            "SELECT pid FROM announcement_record "
            "WHERE source_site=? "
            "GROUP BY pid "
            "HAVING COUNT(*) = COUNT(std_name) AND COUNT(*) > 0",
            (source_site,),
        )
        rows = cursor.fetchall()
        return {row[0] for row in rows}

    _BATCH_SIZE = 50

    def _bulk_insert_records(self, rows: list[tuple[Any, ...]]) -> None:
        """批量插入公告记录到 announcement_record 表，按 _BATCH_SIZE 分批。"""
        if not rows:
            return
        # 分批插入：避免单条 SQL 过长导致性能下降
        for i in range(0, len(rows), self._BATCH_SIZE):
            batch = rows[i : i + self._BATCH_SIZE]
            placeholders = ",".join("(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)" for _ in batch)
            flat_values = [item for row in batch for item in row]
            self._db.execute(
                "INSERT OR IGNORE INTO announcement_record "
                "(source_site, pid, announce_no, standard_number, std_name, "
                "publish_date, implement_date, expiry_date, superseded_by, confidence, row_index,"
                " status, fetched_at, matched, announcement_title, standard_count) "
                f"VALUES {placeholders}",
                flat_values,
            )

    def _bulk_upsert_cache(self, rows: list[tuple[Any, ...]]) -> None:
        """批量 upsert 公告缓存到 announcement_match 表，按 _BATCH_SIZE 分批。"""
        if not rows:
            return
        # 用 INSERT OR REPLACE 实现幂等 upsert，以 standard_number 为主键
        for i in range(0, len(rows), self._BATCH_SIZE):
            batch = rows[i : i + self._BATCH_SIZE]
            placeholders = ",".join("(?,?,?,?,?)" for _ in batch)
            flat_values = [item for row in batch for item in row]
            self._db.execute(
                "INSERT OR REPLACE INTO announcement_match "
                "(standard_number, source_site, result_json, cached_at, expires_at) "
                f"VALUES {placeholders}",
                flat_values,
            )
