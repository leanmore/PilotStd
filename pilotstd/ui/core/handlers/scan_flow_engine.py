# pilotstd/ui/core/handlers/scan_flow_engine.py
"""ScanFlowEngine — 扫描文件解析的纯逻辑层（零 Qt、零 I/O、零事件总线）。

提取文件名解析、PDF 头解析、已知结果过滤、结果合并、扫描统计。
所有方法均为纯数据变换，输入输出均为原生 Python 类型。
"""

from __future__ import annotations

import re
from typing import Any


class ScanFlowEngine:
    """扫描相关纯逻辑：文件名解析、PDF 头提取、去重合并、统计生成。"""

    # ── 文件名解析用正则（轻量，不依赖 StandardParser 即可覆盖常见格式）──
    _STD_NUMBER_RE = re.compile(
        r"(?P<code>[A-Z]{2,}/?[A-Z]{0,3})\s*"
        r"(?P<number>\d+(?:\.\d+)?)"
        r"(?:[._-]?(?P<year>\d{4}))?"
    )

    # ── PDF 头部标准号匹配（二进制流中搜索）──
    _PDF_STD_RE = re.compile(
        rb"(?P<code>[A-Z]{2,}(?:/[A-Z]{1,3})?)\s*"
        rb"(?P<number>\d+(?:\.\d+)?)"
        rb"(?:[._-](?P<year>\d{4}))?"
    )

    # ── parse_filename_to_std ──────────────────────────────────

    @staticmethod
    def parse_filename_to_std(filename: str) -> dict[str, Any] | None:
        """从文件名解析标准号信息。

        优先使用项目标准解析器 StandardParser，解析失败时退化为轻量正则匹配。
        不执行任何文件 I/O。

        Args:
            filename: 文件名（如 "GB/T 12345-2020.pdf"、"ISO 9001.pdf"）

        Returns:
            {
                "std_number": str,       # 标准号（如 "GB/T 12345-2020"）
                "logical_code": str,     # 逻辑代号
                "number": int,           # 顺序号
                "year": int,             # 年份（0 表示无年份）
                "part": int | None,      # 部分号
                "std_name": str,         # 标准名称
                "is_valid": bool,        # 是否有效标准号
            }
            或 None（无法解析）
        """
        if not filename or not isinstance(filename, str):
            return None

        # 去掉扩展名，保留纯文件名
        base = filename.rsplit(".", 1)[0].strip()
        if not base:
            return None

        # 优先：项目标准解析器（完整覆盖 94 类代号）
        try:
            from pilotstd.organizer.industry_lookup import build_code_mapping
            from pilotstd.scan.parser import StandardParser

            parser = StandardParser(build_code_mapping())
            parsed = parser.parse(filename)
            if parsed is not None and parsed.logical_code and parsed.number > 0:
                return {
                    "std_number": parsed.get_full_number(),
                    "logical_code": parsed.logical_code,
                    "number": parsed.number,
                    "year": parsed.year,
                    "part": parsed.part,
                    "std_name": parsed.std_name or "",
                    "is_valid": parsed.is_valid_standard,
                }
        except Exception:
            pass

        # 退化：轻量正则匹配
        m = ScanFlowEngine._STD_NUMBER_RE.search(base)
        if m is None:
            return None

        code = m.group("code").rstrip("/")
        number_str = m.group("number")
        year_str = m.group("year")

        try:
            number = int(number_str.split(".")[0])
            part = int(number_str.split(".")[1]) if "." in number_str else None
        except ValueError:
            return None

        year = int(year_str) if year_str else 0

        return {
            "std_number": f"{code} {number_str}" + (f"-{year}" if year else ""),
            "logical_code": code,
            "number": number,
            "year": year,
            "part": part,
            "std_name": "",
            "is_valid": bool(code and number > 0),
        }

    # ── parse_pdf_header ───────────────────────────────────────

    @staticmethod
    def parse_pdf_header(header_bytes: bytes) -> dict[str, Any] | None:
        """从 PDF 文件头部字节中提取标准号信息。

        搜索前 1024 字节中的标准号模式。
        当文件名解析失败（如乱码文件名）时作为补充路径。

        Args:
            header_bytes: 文件前 N 字节（通常 1024）

        Returns:
            {"std_number": str, "logical_code": str, "number": int, "year": int, "title": str}
            或 None（未找到）
        """
        if not header_bytes or not isinstance(header_bytes, bytes):
            return None

        # 截取前 4096 字节（PDF 头部+信息字典通常在文件开头）
        chunk = header_bytes[:4096] if len(header_bytes) > 4096 else header_bytes

        matches = list(ScanFlowEngine._PDF_STD_RE.finditer(chunk))
        if not matches:
            return None

        # 取第一个匹配
        m = matches[0]
        code = m.group("code").decode("ascii", errors="replace").rstrip("/")
        number_str = m.group("number").decode("ascii", errors="replace")
        year_str = m.group("year")
        year = int(year_str.decode("ascii")) if year_str else 0

        try:
            number = int(number_str.split(".")[0])
        except ValueError:
            return None

        return {
            "std_number": f"{code} {number_str}" + (f"-{year}" if year else ""),
            "logical_code": code,
            "number": number,
            "year": year,
            "title": "",
        }

    # ── filter_known_results ───────────────────────────────────

    @staticmethod
    def filter_known_results(results: list[dict[str, Any]], known_numbers: set[str]) -> list[dict[str, Any]]:
        """过滤掉已存在于已知集合中的标准号。

        Args:
            results: 解析结果列表（每项含 "std_number" 键）
            known_numbers: 已知标准号集合（如 {"GB/T 12345-2020", "ISO 9001-2015"}）

        Returns:
            过滤后的结果列表（排除已存在项）
        """
        if not results:
            return []
        if not known_numbers:
            return list(results)

        return [r for r in results if r.get("std_number", "") not in known_numbers]

    # ── merge_results ──────────────────────────────────────────

    @staticmethod
    def merge_results(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """合并两组解析结果，按标准号去重，保留信息更完整的条目。

        合并规则：
        - 新结果标准号不在已有结果中 → 追加
        - 新结果标准号已在已有中 → 保留 std_name 非空者（信息更完整）

        Args:
            existing: 已有结果列表
            new: 新结果列表

        Returns:
            合并后的结果列表（existing 在前，新增项在后）
        """
        if not new:
            return list(existing) if existing else []
        if not existing:
            return list(new)

        merged: list[dict[str, Any]] = list(existing)
        existing_numbers = {r.get("std_number", "") for r in existing}

        for r in new:
            sn = r.get("std_number", "")
            if not sn:
                merged.append(r)
                continue
            if sn not in existing_numbers:
                merged.append(r)
                existing_numbers.add(sn)
            else:
                # 更新已有项：保留信息更完整的
                for i, e in enumerate(merged):
                    if e.get("std_number") == sn:
                        if r.get("std_name") and not e.get("std_name"):
                            merged[i] = r
                        break

        return merged

    # ── build_scan_stats ───────────────────────────────────────

    @staticmethod
    def build_scan_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
        """从解析结果列表生成扫描统计信息。

        Args:
            results: 解析结果列表（每项含 "is_valid"、"std_number"、"std_name" 等键）

        Returns:
            {
                "total": int,              # 总文件数
                "success": int,            # 成功识别数（is_valid=True）
                "failed": int,             # 未识别数（is_valid=False 或 None 结果）
                "with_name": int,          # 含标准名称的条目数
                "unique_codes": list[str], # 涉及的标准代号（去重排序）
            }
        """
        if not results:
            return {"total": 0, "success": 0, "failed": 0, "with_name": 0, "unique_codes": []}

        total = len(results)
        success = sum(1 for r in results if r and r.get("is_valid"))
        failed = total - success
        with_name = sum(1 for r in results if r and r.get("std_name"))
        codes = sorted({r.get("logical_code", "") for r in results if r and r.get("logical_code")})

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "with_name": with_name,
            "unique_codes": codes,
        }
