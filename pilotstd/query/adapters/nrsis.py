# pilotstd/query/adapters/nrsis.py
"""
自然资源标准查询适配器

URL: http://www.nrsis.org.cn/portal/xxcx/std
搜索方式: GET 参数 pageNo, pageSize, key, level, repeFlag, zxd
响应格式: HTML 表格（服务端渲染）

编码: UTF-8（经 Task 0 确认，无 BOM）
选择器: table.table tbody tr（lxml 自动补 tbody）
表头: 序号 | 标准号 | 标准名称 | 发布日期 | 实施日期 | 标准状态
分页: 文本"共X条数据"，正则提取总数
"""

import logging
import re
import time
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

logger = logging.getLogger(__name__)

# 分页总数提取正则
_TOTAL_COUNT_RE = re.compile(r"共\s*(\d+)\s*条")


class NRSISAdapter(BaseAdapter):
    """自然资源标准查询适配器。"""

    SEARCH_URL = "http://www.nrsis.org.cn/portal/xxcx/std"

    # Task 0 产出：结果行选择器（实际表格 class="table table-bordered hidden-xs"）
    ROW_SELECTOR = "table.table tbody tr"

    # Task 0 产出：语义名 → 列索引映射
    # 实际表头: 序号/标准号/标准名称/发布日期/实施日期/标准状态
    HEADER_MAP = {
        "标准编号": 1,
        "标准名称": 2,
        "发布日期": 3,
        "实施日期": 4,
        "状态": 5,
    }

    # 空结果判定关键词
    EMPTY_RESULT_KEYWORDS = ["暂无数据", "未找到", "没有找到"]

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1  # 指数退避基数（秒）

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "http://www.nrsis.org.cn/",
            },
        )

    @property
    def site_name(self) -> str:
        return "nrsis"

    @property
    def site_label(self) -> str:
        return "自然资源标准信息服务平台"

    # ── 编码解码（多级回退） ──

    def _decode_content(self, content: bytes) -> str:
        """多策略解码：BOM → UTF-8 → GBK → 兜底。"""
        # 1. BOM 剥离
        if content.startswith(b"\xef\xbb\xbf"):
            content = content[3:]
        # 2. UTF-8（严格模式）
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        # 3. GBK（覆盖 GB2312 超集）
        try:
            return content.decode("gbk")
        except UnicodeDecodeError:
            pass
        # 4. 兜底（替换无法解码的字节）
        return content.decode("gbk", errors="replace")

    # ── 指令层 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询自然资源标准，返回全部匹配结果列表。"""
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        params: dict[str, Any] = {
            "pageNo": kwargs.get("pageNo", 1),
            "pageSize": kwargs.get("pageSize", 20),
            "key": keyword,
        }
        # 可选过滤参数
        for opt in ("level", "repeFlag", "zxd"):
            if opt in kwargs:
                params[opt] = kwargs[opt]

        # 指数退避重试
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._client.get(self.SEARCH_URL, params=params)
                break
            except Exception as e:
                last_error = e
                if attempt == self.MAX_RETRIES - 1:
                    logger.debug(f"nrsis.org.cn 请求失败: {last_error}")
                    return []
                delay = self.RETRY_BASE_DELAY * (2**attempt)
                time.sleep(delay)

        if resp.status_code != 200:
            return []

        html = self._decode_content(resp.content)

        # 空结果判定（注意：用 kw 避免遮蔽外层 keyword）
        for kw in self.EMPTY_RESULT_KEYWORDS:
            if kw in html:
                return []

        soup = BeautifulSoup(html, "lxml")
        rows = soup.select(self.ROW_SELECTOR)
        if not rows:
            return []

        results: list[QueryResult] = []
        for row in rows:
            result = self._parse_result(row, keyword)
            if result:
                results.append(result)

        return results

    # ── 引擎层 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配（精确匹配优先，否则返回最新）。"""
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                return c
        best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        return best

    def _parse_result(
        self,
        row: Any,
        search_term: str = "",
        header_map: dict[str, int] | None = None,
    ) -> Optional[QueryResult]:
        """从 BeautifulSoup Tag 解析标准信息，基于表头映射驱动。"""
        if header_map is None:
            header_map = self.HEADER_MAP

        cols = row.find_all("td")
        if len(cols) < 2:
            return None

        # 安全获取列值
        def get_col(key: str) -> str:
            """按表头映射键名获取列文本，越界返回空字符串。"""
            idx = header_map.get(key, -1)
            if idx < 0 or idx >= len(cols):
                return ""
            return cols[idx].text.strip()

        std_no = get_col("标准编号")
        name = get_col("标准名称")
        publish_date = get_col("发布日期")
        implement_date = get_col("实施日期")
        status_text = get_col("状态")

        # 无标准号且无名称 → 表头行或空行
        if not std_no and not name:
            return None

        # 状态归一化
        status_map = {"现行": "现行", "即将实施": "即将实施", "废止": "废止", "已废止": "废止"}
        status = status_map.get(status_text, status_text) if status_text else "未知"

        # 匹配状态
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            name,
            std_no,
        )

        result = QueryResult(
            standard_number=std_no,
            standard_name=name,
            status=status,
            match_status=match_status,
            implementation_date=implement_date or publish_date,
            publish_date=publish_date or implement_date,
            responsible_dept="自然资源部",
            source_site=self.site_name,
        )
        return result
