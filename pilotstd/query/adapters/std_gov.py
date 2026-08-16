# 模块：项目/查询/适配器/_脚本
# 全国标准信息公共服务平台（...）查询适配器
# 参考_(,2024-2025)
# 分隔
# 2026-05适配网站改版：搜索结果从改为布局
# 搜索入口:...//?=<>
# 详情入口:...///?=<>
# 下载入口:...///视图?=<>(即)
# ⚠️ 修改本文件后请在本地运行国内站点端到端测试验证（见 tests/test_e2e_adapters.py，CI 不运行）

import logging
import re
from typing import Any, List, Optional

import requests
from bs4 import BeautifulSoup

from ..models import QueryResult
from ..network import safe_get
from ..search_strategy import map_status
from .base import BaseAdapter

DISPLAY_NAME = "国家标准公开"

logger = logging.getLogger(__name__)


class StdGovAdapter(BaseAdapter):
    """全国标准信息公共服务平台查询适配器（新版 Bootstrap 页面）。"""

    def __init__(self, session: requests.Session | None = None):
        """初始化国家标准公开适配器，注入 requests session 并设置请求头。"""
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )

    @property
    def site_name(self) -> str:
        return "std_gov"

    @property
    def site_label(self) -> str:
        return "国家标准公开"

    # ── 覆盖：多结果搜索 ─────────────────────────────────────

    def _search_candidates(self, search_term: str) -> list[QueryResult]:
        """std_gov 多结果搜索（自动翻页）。"""
        return self._search_multi(search_term)

    # ── 搜索 ──────────────────────────────────────────────

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """单结果兼容接口。"""
        candidates = self._search_multi(search_term)
        return candidates[0] if candidates else None

    def _search_multi(self, search_term: str) -> List[QueryResult]:
        """搜索并解析搜索结果页（新版 Bootstrap panel 布局）。"""
        logger.debug("搜索: %s @std_gov", search_term)
        params = {"q": search_term}
        resp = safe_get(self._session, self.get_search_url(), self.site_name, params=params, timeout=15)
        if resp is None:
            return []
        resp.encoding = "utf-8"

        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # 结果计数为 0 则无匹配
        nums_div = soup.select_one("div.nums")
        if nums_div:
            span = nums_div.find("span")
            if span and span.get_text(strip=True) == "0":
                return []

        # 新版页面每条结果为..
        panels = soup.select("div.panel.post")
        if not panels:
            return []

        results = []
        for panel in panels:
            r = self._parse_result(search_term, panel)
            if r and r.standard_name:
                results.append(r)
        return results

    def _parse_result(self, search_term: str, panel: Any) -> Optional[QueryResult]:
        """从单个 div.panel.post 中提取标准信息。"""
        # 标准名称链接
        name_link = panel.select_one("a[tid]")
        if not name_link:
            return None
        full_text = name_link.get_text(" ", strip=True)

        # 优先用-解析标准号（新版两格式均可靠），回退到正则
        en_code = panel.select_one("span.en-code")
        if en_code:
            raw = en_code.get_text(strip=True)
            # 有"4053.1-2025"和"30000.30-2025"两格式，
            # 统一插入代号与序号间的空格
            std_number = re.sub(r"([A-Z]+(?:/[A-Z]+)?)(\d)", r"\1 \2", raw)
            # 从_去掉编号前缀得到名称
            if full_text.upper().replace(" ", "").startswith(std_number.upper().replace(" ", "")):
                std_name = full_text[len(std_number) :].strip().lstrip("-/ ")
            else:
                std_name = full_text.replace(raw, "", 1).strip().lstrip("-/ ")
        else:
            # 旧版回退：正则匹配
            m = re.match(
                r"([A-Z]{2,}(?:\s*/\s*[A-Z]+)?)\s*(\d{1,6}(?:[\.\-]\d{1,4})*(?:\s*[\.\-]\s*(?:19|20)\d{2})?)",
                full_text,
            )
            if m:
                code_part = re.sub(r"\s*/\s*", "/", m.group(1))
                std_number = f"{code_part} {m.group(2)}".strip()
                std_name = full_text[m.end() :].strip().lstrip("-/ ")
            else:
                return None

        # →用作
        pid = name_link.get("pid", "")
        # 发布日期：-中第一个
        pub_date = ""
        impl_date = ""
        footer = panel.select_one("div.panel-footer")
        if footer:
            times = footer.select("time.post-date")
            if len(times) >= 1:
                pub_date = times[0].get_text(strip=True)
            if len(times) >= 2:
                impl_date = times[1].get_text(strip=True)

        # 标准状态：现行(-)/即将实施(-)/废止(-)
        status_text = ""
        for label_cls, default_text in [
            ("span.s-status.label-success", "现行"),
            ("span.s-status.label-info", "即将实施"),
            ("span.s-status.label-danger", "废止"),
            ("span.s-status.label-warning", ""),
            ("span.label-info", "即将实施"),
        ]:
            span = panel.select_one(label_cls)
            if span:
                txt = span.get_text(strip=True)
                status_text = txt if txt else default_text
                break

        # 是否采标：-且文本为"采"
        is_ref = False
        ref_labels = panel.select("span.s-status.label-default")
        for rl in ref_labels:
            if rl.get_text(strip=True) == "采":
                is_ref = True
                break

        return QueryResult(
            standard_number=std_number,
            standard_name=std_name,
            status=map_status(status_text),
            implementation_date=impl_date,
            publish_date=pub_date,
            is_adopted=is_ref,
            is_downloadable=not is_ref,
            source_site=self.site_name,
            hcno=pid,
        )

    # ── 元数据 ──────────────────────────────────────────────

    def get_meta(self, hcno: str) -> Optional[dict[str, Any]]:
        """通过 pid 获取标准详细元数据（新版详情页）。"""
        resp = safe_get(
            self._session,
            "https://std.samr.gov.cn/gb/search/gbDetailed",
            self.site_name,
            params={"id": hcno},
            timeout=15,
        )
        if resp is None:
            return None
        resp.encoding = "utf-8"
        return self._parse_meta(hcno, resp.text)

    def _parse_meta(self, hcno: str, html: str) -> Optional[dict[str, Any]]:
        """解析新版详情页 HTML，提取标准名称、状态、预览/下载权限。"""
        soup = BeautifulSoup(html, "lxml")
        bor = soup.select_one("div.bor2")
        if not bor:
            return None
        tdlist = bor.select_one("table.tdlist")
        if not tdlist:
            return None

        allow_preview = bor.select_one("button.ck_btn") is not None
        allow_download = bor.select_one("button.xz_btn") is not None

        name_cn = ""
        name_tag = tdlist.select_one("tr:nth-of-type(1) td b")
        if name_tag:
            name_cn = name_tag.get_text(strip=True)

        status_text = ""
        status_tag = tdlist.select_one("tr:nth-of-type(3) td span")
        if status_tag:
            status_text = status_tag.get_text(strip=True)

        return {
            "hcno": hcno,
            "name_cn": name_cn,
            "status": map_status(status_text),
            "allow_preview": allow_preview,
            "allow_download": allow_download,
        }
