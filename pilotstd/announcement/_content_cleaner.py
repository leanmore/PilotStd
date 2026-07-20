# pilotstd/announcement/_content_cleaner.py
# 公告正文清洗 — 从 matcher.py 拆分

import re

# ── 常量 ──────────────────────────────────────────────

# 标准号行首正则（防误伤正文中的字母组合）
_STD_CODE_LINE_PATTERN = re.compile(
    r"^(GB|GB/T|GB/Z|HG|HG/T|JB|JB/T|SN|SN/T|WS|WS/T|MH|MH/T|"
    r"YB|YB/T|YS|YS/T|JT|JT/T|TY|TY/T|DB|DB/T|DY|DY/T|"
    r"FZ|QB|QC|SJ|WJ|YD|GY|LY|MT|NB|YC|JR|DZ|HY|TD|"
    r"DL|TB|YY|AQ)\s*[\d ]"
)

# 统计汇总表 + 标准清单表列名关键词
_STATS_COLUMN_KEYWORDS = [
    # 统计汇总表（备案月报）
    "标准发布部门", "省市区", "行业领域", "备案数量", "发布部门", "备案单位", "统计", "合计",
    # 标准清单表（国标/行标/地标公告）
    "标准编号", "标准名称", "代替标准", "实施日期", "发布日期", "作废日期", "废止日期",
    "主管部门", "代替标准号", "备案号", "复审结论",
]

# 公告引言段落模式（退出表格区块的信号）
_ANNOUNCEMENT_INTRO_PATTERN = re.compile(
    r"\d{4}年\d{1,2}月.*(?:共(?:发布|废止)|批准|公告如下|现予以|现发布)\d*项?"
)

# 独立日期行模式
_DATE_LINE_PATTERN = re.compile(r"^\d{4}[-年]\d{1,2}[-月]\d{1,2}日?$")

# 附表标题模式
_APPENDIX_TITLE_PATTERN = re.compile(r"^附表\d+")

# 落款日期拆分模式：末尾 "机关名称 日期"
_SIGNATURE_DATE_PATTERN = re.compile(
    r"(.{4,}(?:委员会|管理局|总局|部|厅|局|院|中心|公司|协会))\s+(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)$"
)


# ── 公开 API ──────────────────────────────────────────


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

        if _is_table_entry(stripped):
            in_table = True
            continue
        if in_table and _is_table_exit(stripped):
            in_table = False
            result.append(stripped)
            continue
        if in_table:
            continue

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

    # ── 落款日期拆分 ──
    if paragraphs:
        last = paragraphs[-1]
        m = _SIGNATURE_DATE_PATTERN.search(last)
        if m:
            org = m.group(1).strip()
            date_str = m.group(2).strip()
            prefix = last[: m.start()].strip()
            if prefix:
                paragraphs[-1] = prefix
                paragraphs.append(org)
            else:
                paragraphs[-1] = org
            paragraphs.append(date_str)

    html_parts = ["<p>" + p + "</p>" for p in paragraphs]
    if paragraphs and _DATE_LINE_PATTERN.match(paragraphs[-1]):
        html_parts[-1] = '<p style="text-align:right">' + paragraphs[-1] + "</p>"

    return "\n".join(html_parts)


# ── 内部辅助 ──────────────────────────────────────────


def _is_table_entry(stripped: str) -> bool:
    """检测是否进入表格区块。"""
    if stripped.startswith("序号"):
        if any(kw in stripped for kw in _STATS_COLUMN_KEYWORDS):
            return True
    if re.match(r"^\d+\s+[A-Z]+[/\s]", stripped):
        return True
    if _APPENDIX_TITLE_PATTERN.match(stripped):
        return True
    if _STD_CODE_LINE_PATTERN.match(stripped):
        return True
    if stripped.startswith("中文名称：") or stripped.startswith("中文名称:"):
        return True
    if sum(1 for kw in _STATS_COLUMN_KEYWORDS if kw in stripped) >= 3:
        return True
    return False


def _is_table_exit(stripped: str) -> bool:
    """检测是否退出表格区块。"""
    if _ANNOUNCEMENT_INTRO_PATTERN.search(stripped):
        return True
    if _DATE_LINE_PATTERN.match(stripped):
        return True
    if re.match(r"^[一二三四五六七八九十\d]+[、．.]", stripped) and len(stripped) > 10:
        return True
    if "\t" not in stripped and re.search(r"[。；，、]", stripped) and len(stripped) > 20:
        return True
    return False
