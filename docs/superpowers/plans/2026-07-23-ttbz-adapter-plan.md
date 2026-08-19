> ⚠️ **ARCHIVED (2026-08-19): 不再维护。** TTBZ 适配器已实现（pilotstd/query/adapters/ttbz.py），计划执行完毕
>
---

# TTBZ 团体标准适配器 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 PilotStd 新增全国团体标准信息平台（ttbz.org.cn）查询适配器，支持按标准号/关键词查询团体标准。

**Architecture:** 新建 `TTBZAdapter(BaseAdapter)`，实现两层接口——指令层 `query_standards()` 返回 `list[QueryResult]`，引擎层 `_search()` 返回单条最佳匹配。POST JSON API → 解析 `data.rows` → 映射为 QueryResult 列表。动态属性承载 QueryResult 不存在的字段（`standard_name_en`, `field`）。

**Tech Stack:** Python 3.11+, requests.Session, unittest.mock

**Design Doc:** `docs/superpowers/specs/2026-07-23-ttbz-adapter-design.md`

---

### Task 1: 编写测试（TDD 红阶段）

**Files:**
- Modify: `tests/test_adapters.py`

- [ ] **Step 1: 添加 ttbz mock 辅助函数和测试类**

在 `tests/test_adapters.py` 末尾追加以下内容：

```python
# ════════════════════════════════════════════════════════════════
# 辅助：构造 ttbz API 返回结果的工具函数
# ════════════════════════════════════════════════════════════════


def _make_ttbz_response(*rows):
    """构造 ttbz API 返回格式。data.rows 为列表。"""
    return {"code": 200, "message": "操作成功", "data": {"total": len(rows), "rows": list(rows)}}


def _ttbz_row(
    standard_no="T/CAS 123-2024",
    title_cn="团体标准中文名称",
    title_en="Group Standard English Name",
    publish_date="2024-01-01",
    implement_date="2024-07-01",
    status_name="现行",
    organ_name="中国标准化协会",
    standard_field="化工",
    unique_id="abc123def456",
):
    return {
        "standardUniqueId": unique_id,
        "standardNo": standard_no,
        "standardTitleCn": title_cn,
        "standardTitleEn": title_en,
        "publishDate": publish_date,
        "implementDate": implement_date,
        "standardStatusName": status_name,
        "organName": organ_name,
        "standardField": standard_field,
    }


class TestTTBZAdapter(unittest.TestCase):
    """ttbz.org.cn 团体标准适配器单元测试。"""

    def setUp(self):
        from pilotstd.query.adapters.ttbz import TTBZAdapter

        self.a = TTBZAdapter()

    # ── _parse_result 单元测试 ──

    def test_parse_result_maps_all_fields(self):
        """验证所有字段正确映射到 QueryResult。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "T/CAS 123-2024")
        self.assertEqual(r.standard_number, "T/CAS 123-2024")
        self.assertEqual(r.standard_name, "团体标准中文名称")
        self.assertEqual(r.publish_date, "2024-01-01")
        self.assertEqual(r.implementation_date, "2024-07-01")
        self.assertEqual(r.status, "现行")
        self.assertEqual(r.responsible_dept, "中国标准化协会")
        self.assertEqual(r.source_site, "ttbz")
        self.assertEqual(r.hcno, "abc123def456")

    def test_parse_result_dynamic_attrs_standard_name_en(self):
        """验证动态属性 standard_name_en 存在且类型正确。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "")
        self.assertTrue(hasattr(r, "standard_name_en"),
                        "动态属性 standard_name_en 必须存在")
        self.assertEqual(r.standard_name_en, "Group Standard English Name")
        self.assertIsInstance(r.standard_name_en, str)

    def test_parse_result_dynamic_attrs_field(self):
        """验证动态属性 field 存在且类型正确。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "")
        self.assertTrue(hasattr(r, "field"),
                        "动态属性 field 必须存在")
        self.assertEqual(r.field, "化工")
        self.assertIsInstance(r.field, str)

    def test_parse_result_empty_fields_use_defaults(self):
        """验证 API 返回空值时使用默认值。"""
        rec = _ttbz_row(
            standard_no="",
            title_cn="",
            title_en="",
            publish_date="",
            implement_date="",
            status_name="",
            organ_name="",
            standard_field="",
            unique_id="",
        )
        r = self.a._parse_result(rec, "")
        self.assertEqual(r.standard_number, "")
        self.assertEqual(r.standard_name, "")
        self.assertEqual(r.publish_date, "")
        self.assertEqual(r.implementation_date, "")
        self.assertEqual(r.status, "未知")
        self.assertEqual(r.responsible_dept, "")
        self.assertEqual(r.hcno, "")
        self.assertEqual(r.standard_name_en, "")

    def test_parse_result_unknown_status_preserved(self):
        """验证非标准状态值原样保留。"""
        rec = _ttbz_row(status_name="已废止")
        r = self.a._parse_result(rec, "")
        self.assertEqual(r.status, "已废止")

    def test_parse_result_is_adopted_false(self):
        """验证团体标准不应标记为采标。"""
        rec = _ttbz_row()
        r = self.a._parse_result(rec, "")
        self.assertFalse(r.is_adopted)

    # ── _search 单元测试（mock HTTP） ──

    def _mock_response(self, rows):
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_ttbz_response(*rows)
        self.a._session.request = MagicMock(return_value=mock_resp)

    def test_search_exact_match(self):
        """验证精确匹配搜索返回正确结果。"""
        self._mock_response([_ttbz_row(standard_no="T/CAS 123-2024")])
        r = self.a._search("T/CAS 123-2024")
        self.assertIsNotNone(r)
        self.assertEqual(r.standard_number, "T/CAS 123-2024")
        self.assertEqual(r.match_status, "exact")

    def test_search_no_results(self):
        """验证无结果返回 None。"""
        self._mock_response([])
        r = self.a._search("NONEXISTENT")
        self.assertIsNone(r)

    def test_search_network_error(self):
        """验证网络异常返回 None 而非抛出异常。"""
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.side_effect = ValueError("bad json")
        self.a._session.request = MagicMock(return_value=mock_resp)
        r = self.a._search("T/CAS 123-2024")
        self.assertIsNone(r)

    # ── query_standards 单元测试（mock HTTP） ──

    def test_query_standards_returns_list(self):
        """验证 query_standards 返回 list[QueryResult]。"""
        self._mock_response([
            _ttbz_row(standard_no="T/CAS 001-2024"),
            _ttbz_row(standard_no="T/CAS 002-2024"),
        ])
        results = self.a.query_standards("T/CAS")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].standard_number, "T/CAS 001-2024")

    def test_query_standards_empty_keyword(self):
        """验证空关键词返回空列表，不报错。"""
        results = self.a.query_standards("")
        self.assertEqual(results, [])

    def test_query_standards_network_timeout(self):
        """验证网络超时返回空列表，不抛出异常。"""
        from unittest.mock import MagicMock

        self.a._session.request = MagicMock(
            side_effect=Exception("Connection timed out")
        )
        results = self.a.query_standards("T/CAS 123")
        self.assertEqual(results, [])

    def test_query_standards_passes_kwargs_as_form_data(self):
        """验证 **kwargs 透传为 form data 参数。"""
        self._mock_response([])
        self.a.query_standards(
            "T/CAS",
            organName="中国标准化协会",
            publishDateBegin="2024-01-01",
            publishDateEnd="2024-12-31",
        )
        call_args = self.a._session.request.call_args
        data = call_args[1]["data"]
        self.assertIn(("organName", "中国标准化协会"), data.items())
        self.assertIn(("publishDateBegin", "2024-01-01"), data.items())
        self.assertIn(("publishDateEnd", "2024-12-31"), data.items())

    def test_query_standards_sets_required_headers(self):
        """验证 POST 请求包含必要的 headers。"""
        self._mock_response([])
        self.a.query_standards("T/CAS")
        call_args = self.a._session.request.call_args
        headers = call_args[1].get("headers", {})
        self.assertIn("X-Requested-With", headers)
        self.assertIn("Referer", headers)
```

- [ ] **Step 2: 运行测试确认全部失败（红）**

```bash
pytest tests/test_adapters.py::TestTTBZAdapter -v
```

预期：全部 16 条测试 FAIL（`TTBZAdapter` 类和 `query_standards` 方法尚不存在）。

- [ ] **Step 3: 提交测试骨架**

```bash
git add tests/test_adapters.py
git commit -m "test(ttbz): add failing tests for TTBZAdapter (Q22-01)"
```

---

### Task 2: 实现 TTBZAdapter（TDD 绿阶段）

**Files:**
- Create: `pilotstd/query/adapters/ttbz.py`

- [ ] **Step 1: 创建适配器文件**

创建 `pilotstd/query/adapters/ttbz.py`：

```python
# pilotstd/query/adapters/ttbz.py
# 全国团体标准信息平台（ttbz.org.cn）查询适配器
# API: POST https://www.ttbz.org.cn/cms-proxy/ms/portal/standardInfo/getPortalStandardList
# 响应 JSON 的 data.rows 包含标准列表

import logging
from typing import Any, Optional

import requests

from ..models import QueryResult
from ..network import safe_post
from ..search_strategy import (
    _parse_result_number,
    match_result,
)
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class TTBZAdapter(BaseAdapter):
    """全国团体标准信息平台查询适配器。

    API: POST /cms-proxy/ms/portal/standardInfo/getPortalStandardList
    请求参数: pageNo, pageSize, standardName（核心），organName/publishDateBegin 等可选。
    返回 data.rows（非 records），每条含 standardNo/standardTitleCn 等字段。

    已知限制：
    - 不支持 status 独立过滤参数
    - standardTitleEn 和 standardField 以动态属性挂载（QueryResult 无对应字段）
    """

    API_URL = (
        "https://www.ttbz.org.cn/cms-proxy/ms/portal/standardInfo/getPortalStandardList"
    )

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.ttbz.org.cn/standard.html",
            }
        )

    @property
    def site_name(self) -> str:
        return "ttbz"

    @property
    def site_label(self) -> str:
        return "全国团体标准信息平台"

    # ── 指令层：公开接口，返回列表 ──

    def query_standards(self, standard_number: str, **kwargs: Any) -> list[QueryResult]:
        """按标准号或关键词查询团体标准，返回全部匹配结果列表。

        Args:
            standard_number: 标准号（如 "T/CAS 123-2024"）或关键词（如 "团体标准"）
            **kwargs: 可选过滤参数 — organName, publishDateBegin, publishDateEnd,
                      standardField, pageNo, pageSize

        Returns:
            list[QueryResult]: 查询结果列表。网络异常/解析失败/空结果均返回空列表。
        """
        keyword = standard_number.strip() if standard_number else ""
        if not keyword:
            return []

        data: dict[str, Any] = {
            "pageNo": kwargs.pop("pageNo", 1),
            "pageSize": kwargs.pop("pageSize", 20),
            "standardName": keyword,
        }
        # 透传额外过滤参数
        for key in ("organName", "publishDateBegin", "publishDateEnd",
                     "standardField", "implementDateBegin", "implementDateEnd",
                     "standardType"):
            if key in kwargs:
                data[key] = kwargs.pop(key)

        resp = safe_post(
            self._session,
            self.API_URL,
            self.site_name,
            data=data,
            timeout=15,
        )
        if resp is None or resp.status_code != 200:
            return []

        try:
            payload = resp.json()
        except ValueError:
            logger.debug("ttbz JSON 解析失败", exc_info=True)
            return []

        rows = payload.get("data", {}).get("rows", [])
        if not rows:
            return []

        return [self._parse_result(rec, keyword) for rec in rows]

    # ── 引擎层：融入 BaseAdapter 渐进搜索体系 ──

    def _search(self, search_term: str) -> Optional[QueryResult]:
        """搜索并返回最佳匹配。多候选时选 standard_number 精确匹配或最新发布者。"""
        candidates = self.query_standards(search_term)
        if not candidates:
            return None
        # 精确匹配
        for c in candidates:
            if c.standard_number == search_term:
                return c
        # 取最新发布
        best = max(candidates, key=lambda c: getattr(c, "publish_date", "") or "")
        return best

    def _build_search_data(self, search_term: str) -> dict[str, Any]:
        """构建搜索请求 form data。BaseAdapter 兼容接口。"""
        return {"pageNo": 1, "pageSize": 15, "standardName": search_term}

    def _parse_result(self, rec: dict[str, Any], search_term: str = "") -> QueryResult:
        """将 API 返回的单条 JSON 映射为 QueryResult。

        动态属性说明（QueryResult 无对应字段，以动态属性挂载）：
        - result.standard_name_en: str — 英文名称，来源 rec["standardTitleEn"]
        - result.field: str — 标准领域，来源 rec["standardField"]
        """
        code = rec.get("standardNo", "")
        ch_name = rec.get("standardTitleCn", "")
        en_name = rec.get("standardTitleEn", "")
        raw_status = rec.get("standardStatusName", "")
        field = rec.get("standardField", "")
        unique_id = rec.get("standardUniqueId", "")
        organ_name = rec.get("organName", "")

        publish_date = rec.get("publishDate", "") or ""
        implement_date = rec.get("implementDate", "") or ""

        # 状态映射：仅对明确的几个值做归一化
        status_map = {"现行": "现行", "即将实施": "即将实施", "废止": "废止"}
        mapped = status_map.get(raw_status, raw_status) if raw_status else "未知"

        # 匹配状态
        target = _parse_result_number(search_term) if search_term else {}
        _, match_status = match_result(
            target.get("code", ""),
            target.get("number", 0),
            target.get("year", 0),
            ch_name,
            code,
        )

        result = QueryResult(
            standard_number=code,
            standard_name=ch_name,
            status=mapped,
            match_status=match_status,
            implementation_date=implement_date,
            publish_date=publish_date,
            responsible_dept=organ_name,
            source_site=self.site_name,
            hcno=unique_id,
        )
        # 动态属性：QueryResult 无对应字段，以动态属性承载
        result.standard_name_en = en_name  # type: ignore[attr-defined]
        result.field = field  # type: ignore[attr-defined]
        return result
```

- [ ] **Step 2: 运行测试确认全部通过（绿）**

```bash
pytest tests/test_adapters.py::TestTTBZAdapter -v
```

预期：全部 16 条测试 PASS。

- [ ] **Step 3: 提交适配器主体**

```bash
git add pilotstd/query/adapters/ttbz.py tests/test_adapters.py
git commit -m "feat(ttbz): add TTBZAdapter with query_standards and _search (Q22-01)"
```

---

### Task 3: 注册适配器到工厂和路由

**Files:**
- Modify: `pilotstd/query/adapters/__init__.py`
- Modify: `pilotstd/query/site_config.py`
- Modify: `pilotstd/query/search_strategy.py`
- Modify: `pilotstd/query/engine/_constants.py`
- Modify: `pilotstd/query/__init__.py`

- [ ] **Step 1: 修改 `__init__.py` 注册导入**

在 `pilotstd/query/adapters/__init__.py` 中添加：

```python
# 在现有 import 后追加
from .ttbz import TTBZAdapter

# 在 __all__ 列表中追加
"TTBZAdapter",
```

修改后的完整文件：

```python
# pilotstd/query/adapters/__init__.py
from .base import BaseAdapter
from .csres import CsresAdapter
from .dbba import DbbaAdapter
from .hbba import HbbaAdapter
from .iso_gov import IsoGovAdapter
from .njbz365 import Njbz365Adapter
from .std_gov import StdGovAdapter
from .ttbz import TTBZAdapter

__all__ = [
    "BaseAdapter",
    "CsresAdapter",
    "DbbaAdapter",
    "StdGovAdapter",
    "Njbz365Adapter",
    "HbbaAdapter",
    "IsoGovAdapter",
    "TTBZAdapter",
]
```

- [ ] **Step 2: 修改 `site_config.py` 添加 SiteState**

在 `pilotstd/query/site_config.py` 的 `create_default_sites()` 返回值列表末尾（`csres` 之后）追加：

```python
        SiteState(
            name="ttbz",
            base_url="https://www.ttbz.org.cn",
            max_requests=100,
            daily_limit=400,
            cooldown_seconds=1,
        ),
```

- [ ] **Step 3: 修改 `search_strategy.py` 将团标主路由指向 ttbz**

在 `pilotstd/query/search_strategy.py` 中，将第 275 行：

```python
    "group": {"primary": "ahbz", "fallback": "njbz365"},
```

改为：

```python
    "group": {"primary": "ttbz", "fallback": "ahbz"},
```

- [ ] **Step 4: 修改 `_constants.py` 在路由链中加入 ttbz**

在 `pilotstd/query/engine/_constants.py` 第 13 行，将：

```python
PROD_PRIORITY = ["ahbz", "std_gov", "hbba", "iso_gov", "njbz365", "csres"]
```

改为：

```python
PROD_PRIORITY = ["ahbz", "std_gov", "hbba", "iso_gov", "njbz365", "ttbz", "csres"]
```

- [ ] **Step 5: 修改 `query/__init__.py` 添加懒加载函数**

在 `pilotstd/query/__init__.py` 的 `_get_mock_adapter` 函数之后追加：

```python
def _get_ttbz_adapter() -> Type[Any]:
    """懒加载团体标准适配器（TTBZAdapter）。"""
    from .adapters.ttbz import TTBZAdapter

    return TTBZAdapter
```

- [ ] **Step 6: 运行现有测试确认注册无误**

```bash
pytest tests/test_adapters.py -v --tb=short
```

预期：全部已有测试 + 16 条新测试均 PASS。无 import 错误。

- [ ] **Step 7: 提交注册变更**

```bash
git add pilotstd/query/adapters/__init__.py pilotstd/query/site_config.py pilotstd/query/search_strategy.py pilotstd/query/engine/_constants.py pilotstd/query/__init__.py
git commit -m "feat(ttbz): register TTBZAdapter in factory, routing, and site config (Q22-01)"
```

---

### Task 4: 集成验证（端到端）

**Files:**
- Modify: `tests/test_e2e_adapters.py`（可选，添加 e2e 测试）

- [ ] **Step 1: 手工验证真实 API 调用**

```bash
python -c "
from pilotstd.query.adapters.ttbz import TTBZAdapter
a = TTBZAdapter()
results = a.query_standards('GB/T')
print(f'找到 {len(results)} 条结果')
if results:
    r = results[0]
    print(f'首条: {r.standard_number} {r.standard_name}')
    print(f'英文名: {getattr(r, \"standard_name_en\", \"N/A\")}')
    print(f'领域: {getattr(r, \"field\", \"N/A\")}')
    print(f'发布机构: {r.responsible_dept}')
    print(f'发布日期: {r.publish_date}')
    print(f'状态: {r.status}')
"
```

预期：输出 ≥ 1 条结果，各字段非空。

- [ ] **Step 2: 手工验证引擎兼容性**

```bash
python -c "
from pilotstd.query.adapters.ttbz import TTBZAdapter
a = TTBZAdapter()
r = a._search('T/CAS')
print(f'搜索引擎返回: {r.standard_number if r else \"None\"} {r.standard_name if r else \"\"}')
r2 = a.query_with_strategy('T/CAS', 'T/CAS', 123, 2024, None, '', '')
print(f'query_with_strategy 返回: {r2.standard_number} match={r2.match_status}')
"
```

预期：`_search` 返回单条结果，`query_with_strategy` 正常工作。

- [ ] **Step 3: 运行全量测试确保无回归**

```bash
pytest tests/ -v --tb=short -x
```

预期：全部测试 PASS，无回归错误。

- [ ] **Step 4: 运行门禁**

```bash
bash scripts/check_all.sh
```

预期：零错误。

---

### Task 5: 收尾

- [ ] **Step 1: 最终提交**

```bash
git add -A
git commit -m "feat(adapter): add TTBZ adapter for group standards (Q22-01)"
```
