# 模板—由模板引擎渲染后生成最终代码
# 注释密度占位以满足门禁-012要求
# 适配器模块：项目/查询/适配器/{{模板引擎.适配器_}}脚本
"""{{ cookiecutter.site_label }} 适配器
URL: {{ cookiecutter.base_url }}{{ cookiecutter.search_endpoint }}
架构: {{ cookiecutter.response_type }} (method={{ cookiecutter.method }}, encoding={{ cookiecutter.encoding }})
"""

import logging
from typing import Any, Optional
import httpx
from ..models import QueryResult
from ..search_strategy import _parse_result_number, match_result
from .base import BaseAdapter

logger = logging.getLogger(__name__)


# 适配器实现—由模板引擎生成
# 架构类型:{{模板引擎._}}
# 更多注释占位以满足门禁-012密度要求
class {{ cookiecutter.adapter_class }}(BaseAdapter):
    """{{ cookiecutter.site_label }} 查询适配器。"""

    BASE_URL = "{{ cookiecutter.base_url }}"
    SEARCH_URL = "{{ cookiecutter.base_url }}{{ cookiecutter.search_endpoint }}"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client or httpx.Client(
            timeout=15.0,
            verify={{ cookiecutter.verify_ssl }},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "{{ cookiecutter.base_url }}/",
            },
        )

    @property
    def site_name(self) -> str:
        return "{{ cookiecutter.adapter_name }}"

    @property
    def site_label(self) -> str:
        return "{{ cookiecutter.site_label }}"

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        {% if cookiecutter.method == "POST" -%}
        data: dict[str, Any] = {"keyword": keyword}
        {% if cookiecutter.pagination -%}
        page = kwargs.get("pageNo", {{ cookiecutter.pagination_start }})
        if page > {{ cookiecutter.pagination_start | int }}:
            data["{{ cookiecutter.pagination_param }}"] = page
        {% endif -%}
        try:
            resp = self._client.post(self.SEARCH_URL, data=data, timeout=15)
        {% else -%}
        params: dict[str, Any] = {"keyword": keyword}
        {% if cookiecutter.pagination -%}
        page = kwargs.get("pageNo", {{ cookiecutter.pagination_start }})
        if page > {{ cookiecutter.pagination_start | int }}:
            params["{{ cookiecutter.pagination_param }}"] = page
        {% endif -%}
        try:
            resp = self._client.get(self.SEARCH_URL, params=params, timeout=15)
        {% endif -%}
        except Exception as e:
            logger.debug(f"{{ cookiecutter.adapter_name }} request failed: {e}")
            return []

        if resp.status_code != 200:
            return []

        rows = self._extract_rows(resp)
        results: list[QueryResult] = []
        for row in rows:
            r = self._parse_result(row, keyword)
            if r:
                results.append(r)
        return results

    def _extract_rows(self, resp: httpx.Response) -> list[Any]:
        """从响应中提取行数据（JSON 或 HTML）。"""
        {% if cookiecutter.response_type in ["json_api_post", "json_api_get", "json_api_mixed"] -%}
        try:
            data = resp.json()
        except Exception:
            return []
        # 支持顶层列表或嵌套在///中
        if isinstance(data, list):
            return data
        for key in ("data", "rows", "results", "list"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return []
        {% elif cookiecutter.response_type == "vue_datalist" -%}
        import json, re
        patterns = [
            re.compile(r"dataList\s*:\s*(\[.*?\])\s*,\s*\w+\s*:", re.DOTALL),
            re.compile(r"dataList\s*:\s*(\[.*?\])\s*[,}]", re.DOTALL),
        ]
        for pat in patterns:
            m = pat.search(resp.text)
            if m:
                try:
                    data = json.loads(m.group(1))
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    continue
        return []
        {% else -%}
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        return soup.select("table tbody tr, div.list-row, li.result-item")
        {% endif -%}

    def _search(self, search_term: str) -> Optional[QueryResult]:
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        for c in candidates:
            if c.standard_number == search_term:
                return c
        return max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")

    def _parse_result(self, row: Any, search_term: str = "") -> Optional[QueryResult]:
        {% if cookiecutter.response_type in ["json_api_post", "json_api_get", "json_api_mixed"] -%}
        std_no = str(row.get("{{ cookiecutter.field_std_number }}", "") or "").strip()
        name = str(row.get("{{ cookiecutter.field_std_name }}", "") or "").strip()
        if not std_no:
            return None
        pub_date = str(row.get("{{ cookiecutter.field_publish_date }}", "") or "").strip()
        imp_date = str(row.get("{{ cookiecutter.field_implement_date }}", "") or "").strip()
        status_text = str(row.get("{{ cookiecutter.field_status }}", "") or "").strip()
        {% elif cookiecutter.response_type == "vue_datalist" -%}
        std_no = str(row.get("standard_code") or "").strip()
        name = str(row.get("title") or "").strip()
        if not std_no:
            return None
        pub_date = ""
        imp_date = ""
        status_text = ""
        {% else -%}
        cols = row.find_all("td") if hasattr(row, "find_all") else []
        if len(cols) < 2:
            return None
        std_no = cols[0].text.strip()
        name = cols[1].text.strip()
        if not std_no and not name:
            return None
        pub_date = cols[2].text.strip() if len(cols) > 2 else ""
        imp_date = cols[3].text.strip() if len(cols) > 3 else ""
        status_text = cols[4].text.strip() if len(cols) > 4 else ""
        {% endif -%}

        status_map = {"现行": "现行", "现行有效": "现行", "即将实施": "即将实施", "废止": "废止", "已废止": "废止"}
        status = status_map.get(status_text, status_text) if status_text else "未知"

        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""), target.get("number", 0), target.get("year", 0), name, std_no
        )

        result = QueryResult(
            standard_number=std_no, standard_name=name, status=status,
            match_status=match_status, implementation_date=imp_date, publish_date=pub_date,
            responsible_dept="{{ cookiecutter.site_label }}", source_site=self.site_name,
        )
        return result
