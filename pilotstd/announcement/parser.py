# 模块：项目//解析器脚本
# 公告数据解析—公告元数据提取+网页表格解析+附件文本提取

import logging
import re
from typing import Any, Optional

from bs4 import BeautifulSoup

from ..core.std_utils import (
    STD_CODE_TOKEN_PATTERN as STD_CODE_PATTERN,
)
from ..core.std_utils import (
    normalize_std_code_text as _normalize_code_text,
)
from ._attachment_parser import (  # noqa: F401 — 重导出
    download_attachment,
    extract_content,
    find_attachment_url,
    parse_attachment_text,
    parse_wps_text,
)

logger = logging.getLogger(__name__)

# 代替标准沿用同一 token 语法
REPLACES_PATTERN = STD_CODE_PATTERN


def parse_announcement_meta(html: str) -> dict[str, str]:
    """从公告详情页 HTML 中提取公告级元数据。

    Returns:
        {title, publish_date}
    """
    meta = {"title": "", "publish_date": ""}
    soup = BeautifulSoup(html, "lxml")

    # 公告标题：<>标签内容
    title_tag = soup.find("title")
    if title_tag:
        meta["title"] = title_tag.get_text(strip=True)

    # 公告发布日期：排除表格内文本（实施日期在表格中），取正文区域第一个日期
    for table in soup.find_all("table"):
        table.decompose()
    text = soup.get_text()
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    if dates:
        # 正文中第一个日期为落款日期（表格已排除，正文开头是发布/批准日期）
        meta["publish_date"] = dates[0]

    return meta


# 统一表头关键词→字段名映射（//数据库三站点共用）
_HEADER_KEYWORD_MAP = [
    ("标准编号", "std_code"),
    ("编号", "std_code"),
    ("标准名称", "std_name"),
    ("外文名称", "foreign_name"),
    ("英文名称", "foreign_name"),
    ("外文名", "foreign_name"),
    ("语种", "language"),
    ("语言", "language"),
    ("名称", "std_name"),
    ("代替", "replaces_code"),
    ("实施日期", "implementation_date"),
    ("发布日期", "publish_date"),
    ("批准日期", "publish_date"),
    ("作废日期", "expiry_date"),
    ("废止日期", "expiry_date"),
    ("备案号", "record_no"),
    ("主管部门", "dept"),
]


def _build_header_map(table: Any) -> dict[int, str]:
    """从表格表头构建 {列索引: 字段名} 映射。"""
    col_map = {}
    thead = table.find("thead")
    headers = thead.find_all("th") if thead else []
    if not headers:
        first_row = table.find("tr")
        if first_row:
            headers = first_row.find_all("th")
    for i, h in enumerate(headers):
        # 去空格归一化（部分表格每个字间有空格，如"国 家 标 准"）
        h_text = h.get_text(strip=True).replace(" ", "")
        for keyword, field_name in _HEADER_KEYWORD_MAP:
            if keyword in h_text:
                col_map[i] = field_name
                break
    return col_map


def _find_col(col_map: dict[int, str], field_name: str) -> Optional[int]:
    """在 col_map 中查找字段名对应的列索引。找不到返回 None。"""
    for idx, name in col_map.items():
        if name == field_name:
            return idx
    return None


def parse_html_table(html: str) -> list[dict[str, Any]]:
    """从公告详情页 HTML 表格中提取标准列表。表头驱动列识别，兼容 GB(5列)/HB(8列)/DB(8列)。
    遍历所有表格，返回第一个同时含标准编号和标准名称列的数据表格。

    Returns:
        [{std_code, std_name, replaces_code, publish_date, implementation_date, record_no, dept}, ...]
    """
    soup = BeautifulSoup(html, "lxml")

    # 遍历所有表格，找第一个含标准编号+标准名称列的数据表格
    for table in soup.find_all("table"):
        col_map = _build_header_map(table)
        code_col = _find_col(col_map, "std_code")
        name_col = _find_col(col_map, "std_name")
        if code_col is None or name_col is None:
            continue

        results = []
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < max(code_col, name_col) + 1:
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]
            # 首列非数字序号 → 跳过（非数据行）
            if not cell_texts[0].isdigit():
                continue

            std_code = cell_texts[code_col]
            if not (
                STD_CODE_PATTERN.match(_normalize_code_text(std_code))
                or SAMPLE_CODE_PATTERN.match(_normalize_code_text(std_code))
            ):
                continue

            # 标准名称列去重：4_()会递归拼接嵌套元素文本，
            # 源站表格常见<><>名称</><>名称</></>导致重复
            if name_col < len(cells):
                name_parts = list(dict.fromkeys(cells[name_col].stripped_strings))
                cell_texts[name_col] = " ".join(name_parts)

            item = {
                "std_code": std_code,
                "std_name": cell_texts[name_col] if name_col < len(cell_texts) else "",
                "foreign_name": "",
                "language": "",
                "replaces_code": "",
                "publish_date": "",
                "implementation_date": "",
                "expiry_date": "",
                "record_no": "",
                "dept": "",
            }
            for col_idx, field_name in col_map.items():
                if col_idx < len(cell_texts) and field_name in item:
                    item[field_name] = cell_texts[col_idx]
            # col_map 的 std_code 会覆盖上面的值；保留源站原始写法（含全角字符），
            # 归一化仅用于匹配，避免改变既有展示/黄金样本。
            item["std_code"] = std_code
            # 日期字段占位符归一化：源站用 -/——/无 表示空值
            for date_field in ("publish_date", "implementation_date", "expiry_date"):
                if item.get(date_field, "") in ("-", "/", "——", "—", "--", "无"):
                    item[date_field] = ""
            results.append(item)

        return results

    return []


def _clean_wps_name(name: str) -> str:
    """清理 WPS 提取文本中的二进制垃圾和非表头残留。"""
    # 页脚标记（安全网：___遗漏的在这里补刀）
    name = re.sub(r"\s*—+\s*PAGE\s*\n?\s*MERGEFORMAT\s*\d*\s*—*\s*", " ", name, flags=re.IGNORECASE)
    name = re.sub(r"PAGE\s*\d+\s*OF\s*\d+", " ", name, flags=re.IGNORECASE)
    # 去除不可打印字符和控制字符（保留中英文、数字、常见标点）
    name = re.sub(
        r"[^一-鿿　-〿＀-￯"
        r"a-zA-Z0-9\s\-—/\.\(\)（）\d]",
        "",
        name,
    )
    # 去除表格表头关键词残留
    for kw in [
        "国家标准",
        "行业标准",
        "地方标准",
        "指导性技术文件",
        "标准化指导性技术文件编号",
        "标准化指导性技术文件名称",
        "标准编号",
        "标准名称",
        "代替标准号",
        "实施日期",
        "发布日期",
        "复审结论",
        "标准废止日期",
        "代替文件号",
    ]:
        name = name.replace(kw, "")
    return name.strip()


def _find_field_text(text: str, matches: list[re.Match[str]], i: int, skip_indices: set[int]) -> tuple[str, str, int]:
    """当前匹配到下一个匹配之间的字段文本 + 代替号检测。返回 (field_text, replaces_code, next_idx)。"""
    next_idx = i + 1
    while next_idx < len(matches) and next_idx in skip_indices:
        next_idx += 1

    if next_idx < len(matches):
        field_text = text[matches[i].end() : matches[next_idx].start()]
    else:
        field_text = text[matches[i].end() : matches[i].end() + 300]

    replaces_code = ""
    if next_idx < len(matches):
        has_chinese = bool(re.search(r"[一-鿿]", field_text))
        if has_chinese and "\n" not in field_text:
            replaces_code = matches[next_idx].group(0)
            skip_indices.add(next_idx)
            post_replaces = text[matches[next_idx].end() : matches[next_idx].end() + 50]
            field_text = field_text + post_replaces

    return field_text, replaces_code, next_idx


def _parse_entry_fields(field_text: str) -> tuple[str, str, str, str]:
    """从字段文本中提取标准名称、代替号、发布日期、实施日期。
    返回 (std_name, replaces_code, publish_date, implementation_date)。"""
    replaces_code = ""
    std_name = _clean_wps_name(field_text)

    replaces_match = REPLACES_PATTERN.search(field_text)
    if replaces_match:
        rep_start = replaces_match.start()
        std_name = _clean_wps_name(field_text[:rep_start])
        replaces_code = replaces_match.group(0)
        field_text = field_text[replaces_match.end() :]

    dates = re.findall(r"(\d{4}-\d{2}-\d{2})", field_text)
    publish_date = dates[0] if dates else ""
    # 附件文本中日期按序排列：发布日期在前，实施日期在后
    implementation_date = dates[1] if len(dates) >= 2 else ""

    return std_name, replaces_code, publish_date, implementation_date


# 国家标准样品编号：04-2809-F01-2025 / GSB 03-4369-2025。
# 必须优先于通用标准号匹配，否则只会截到 F01-2025，把不同样品合并成同一条。
SAMPLE_CODE_PATTERN = re.compile(
    r"(?:(?:GSB\s+\d{2}-\d{3,5})|\d{2}-\d{3,5}-[A-Z]\d{1,3})-\s*\d{4}",
    re.IGNORECASE,
)


def _display_sample_code(raw: str) -> str:
    """PDF 会把 04-2162-F01-\\n2026 拆行；展示时去掉换行/空白，GSB 保留一个空格。"""
    compact = re.sub(r"\s+", "", raw)
    if compact.upper().startswith("GSB"):
        return "GSB " + compact[3:]
    return compact


def _iter_code_matches(normalized: str) -> list[re.Match[str]]:
    """返回样品号 + 标准号的完整匹配，样品号优先，过滤其内部的标准号碎片。"""
    samples = list(SAMPLE_CODE_PATTERN.finditer(normalized))
    sample_spans = [(m.start(), m.end()) for m in samples]
    standards = [
        m
        for m in STD_CODE_PATTERN.finditer(normalized)
        if not any(m.start() < end and m.end() > start for start, end in sample_spans)
    ]
    return sorted(samples + standards, key=lambda m: m.start())


_LANGUAGE_HINTS = (
    "英文",  # i18n-allow: PDF 表格语种标记
    "俄文",  # i18n-allow: PDF 表格语种标记
    "德文",  # i18n-allow: PDF 表格语种标记
    "法文",  # i18n-allow: PDF 表格语种标记
    "日文",  # i18n-allow: PDF 表格语种标记
    "韩文",  # i18n-allow: PDF 表格语种标记
    "蒙古文",  # i18n-allow: PDF 表格语种标记
    "老挝文",  # i18n-allow: PDF 表格语种标记
    "老挝语",  # i18n-allow: PDF 表格语种标记
    "缅甸语",  # i18n-allow: PDF 表格语种标记
    "越南语",  # i18n-allow: PDF 表格语种标记
    "柬埔寨语",  # i18n-allow: PDF 表格语种标记
    "葡萄牙语",  # i18n-allow: PDF 表格语种标记
    "西班牙语",  # i18n-allow: PDF 表格语种标记
    "阿拉伯语",  # i18n-allow: PDF 表格语种标记
)


def _extract_language(text: str) -> str:
    """从附件文本表格里提取语种标记（老 PDF 没有独立语种列）。"""
    for hint in _LANGUAGE_HINTS:
        if hint in text:
            return hint
    return ""


def parse_text_table(text: str) -> list[dict[str, Any]]:
    """从附件文本中提取标准表格。不依赖换行符，用标准编号模式全文本扫描。

    兼容多种 WPS/PDF 提取格式：
      - 标准逐行（每行一条）  → 旧格式，仍支持
      - 同一条目跨行（表头折行） → STD_CODE_PATTERN 跨行不依赖 \\n
      - 多条目拼接在一行（WPS 二进制提取） → finditer 扫描全文本
      - 二进制垃圾前缀（WPS 格式头） → 正则扫描跳过非标准号内容

    Returns:
        [{std_code, std_name, replaces_code, publish_date}, ...]
    """
    results: list[dict[str, Any]] = []
    normalized = _normalize_code_text(text)
    matches = _iter_code_matches(normalized)
    if not matches:
        return results

    skip_indices: set[int] = set()

    for i, match in enumerate(matches):
        if i in skip_indices:
            continue
        std_code = text[match.start() : match.end()]
        if SAMPLE_CODE_PATTERN.fullmatch(_normalize_code_text(std_code)):
            std_code = _display_sample_code(std_code)

        field_text, replaces_code_adjacent, _ = _find_field_text(text, matches, i, skip_indices)

        if not replaces_code_adjacent:
            replaces_code_adjacent = ""  # _find_field_text may return ""

        std_name, replaces_code, publish_date, implementation_date = _parse_entry_fields(field_text)
        language = _extract_language(std_name)
        if language:
            for hint in _LANGUAGE_HINTS:
                std_name = std_name.replace(hint, "")
            std_name = re.sub(r"\s{2,}", " ", std_name).strip()
        # 如果___检测到了代替号但_没扫到，用前者
        if not replaces_code and replaces_code_adjacent:
            replaces_code = replaces_code_adjacent

        if len(std_name) < 2:
            continue

        results.append(
            {
                "std_code": std_code,
                "std_name": std_name,
                "replaces_code": replaces_code,
                "publish_date": publish_date,
                "implementation_date": implementation_date,
                "language": language,
            }
        )

    return results


def _code_key(item: dict[str, Any]) -> str:
    """标准号去重键：代号 + 名称前20字符，用于 HTML 与附件交叉去重。"""
    return item.get("std_code", "") + "|" + item.get("std_name", "")[:20]  # type: ignore[no-any-return]  # dict.get 返回 Any


def _ocr_pdf(pdf_bytes: bytes, ocr_provider: Any) -> str:
    """用 OCR 提供商识别 PDF 全部页面，返回合并文本。"""
    # 内部已拆页+调度，直接返回全文，无需逐页循环
    from pilotstd.announcement.ocr import OcrScheduler

    if isinstance(ocr_provider, OcrScheduler) or getattr(ocr_provider, "full_pdf", False) is True:
        result = ocr_provider.recognize_pdf(pdf_bytes, page_num=1)
        text = getattr(result, "text", None) if not isinstance(result, str) else result
        return text or ""

    total_pages = 1
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        total_pages = len(reader.pages)
    except Exception:
        logger.debug("PDF 页数检测失败，假定 1 页", exc_info=True)

    texts = []
    failed = 0
    for page_num in range(1, total_pages + 1):
        result = ocr_provider.recognize_pdf(pdf_bytes, page_num=page_num)
        if result is not None and getattr(result, "ok", False):  # type: ignore[union-attr]
            texts.append(result.text)  # type: ignore[union-attr]
        else:
            failed += 1

    result = "\n".join(texts)
    logger.info(
        "OCR complete: %d/%d pages, %d chars",
        total_pages - failed,
        total_pages,
        len(result),
    )
    return result


def parse_announcement_detail(
    html: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: str = "",
    ocr_provider: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """解析公告详情页，HTML + 附件交叉校验补全。

    三层回退：
      1. HTML 表格解析（覆盖 ~99.5% 公告）
      2. 附件解析：.wps/.docx 本地、.pdf 先 pypdf 再 OCR
      3. HTML + 附件交叉去重合并

    Args:
        html: 详情页 HTML
        attachment_bytes: 附件原始字节（可选）
        attachment_filename: 附件文件名或URL，用于判断格式（.wps/.pdf/.docx）
        ocr_provider: 可选，BaseOcrProvider 实例，用于 PDF OCR 识别

    Returns:
        (items, meta)
    """
    meta = parse_announcement_meta(html)
    html_items = parse_html_table(html) or []

    # 网页缺发布日期时用公告落款日期补
    for item in html_items:
        if not item.get("publish_date") and meta["publish_date"]:
            item["publish_date"] = meta["publish_date"]

    # 附件解析
    att_items = []
    if attachment_bytes:
        text = parse_attachment_text(attachment_bytes, filename=attachment_filename)
        if text:
            att_items = parse_text_table(text)
        # 便携文档文本提取失败→尝试文字识别
        elif attachment_filename.lower().endswith(".pdf") or (
            attachment_filename and ".pdf" in attachment_filename.lower()
        ):
            if ocr_provider:
                att_text = _ocr_pdf(attachment_bytes, ocr_provider)
                if att_text:
                    att_items = parse_text_table(att_text)

    # 附件比网页表格更完整时以附件为主（DB 公告详情页只展示首屏 52 行，
    # 完整 215/223 行在 .doc 附件中）；否则沿用“网页为主、附件补漏”的合并策略。
    if att_items and len(att_items) > len(html_items):
        logger.info("attachment %d rows > HTML %d rows; use attachment as primary", len(att_items), len(html_items))
        for item in att_items:
            item["_attachment_primary"] = True
        return att_items, meta

    # 交叉去重：网页为主，附件补充未覆盖的标准号
    if html_items and att_items:
        codes = {_code_key(i) for i in html_items}
        new_count = 0
        for item in att_items:
            if _code_key(item) not in codes:
                html_items.append(item)
                new_count += 1
        logger.info("HTML %d rows + attachment %d rows", len(html_items) - new_count, new_count)
        return html_items, meta

    if html_items:
        logger.info("HTML table parsed %d rows", len(html_items))
        return html_items, meta

    if att_items:
        logger.info("attachment parsed %d rows", len(att_items))
        return att_items, meta

    title = meta.get("title", "") or ""
    logger.warning("公告详情页未能解析出标准列表: %s", title[:80])  # i18n-allow: 既有日志文案，保持中文排查可读
    return [], meta


