> ⚠️ **ARCHIVED (2026-08-19): 不再维护。** TTBZ 适配器已实现，设计落地
>
---

# Q22-01 TTBZ 团体标准适配器 — 设计方案

> 日期：2026-07-23 | 状态：待审批

---

## 一、背景与目标

为 PilotStd 新增全国团体标准信息平台（ttbz.org.cn）查询适配器，支持按标准号/关键词查询团体标准。

### 站点信息

| 属性 | 值 |
|------|-----|
| URL | https://www.ttbz.org.cn/standard.html |
| 需求强度 | 刚需 |
| 数据独占性 | 高（全国团体标准唯一官方平台） |
| 技术方案 | httpx + JSON API |

---

## 二、接口分析

### 请求

- **方法**：POST
- **URL**：`https://www.ttbz.org.cn/cms-proxy/ms/portal/standardInfo/getPortalStandardList`
- **Content-Type**：`application/x-www-form-urlencoded`
- **必要 Headers**：`X-Requested-With: XMLHttpRequest`、`Referer: https://www.ttbz.org.cn/standard.html`

### 请求参数（form data）

| 参数 | 类型 | 说明 |
|------|------|------|
| pageNo | int | 页码 |
| pageSize | int | 每页条数 |
| standardName | string | 标准名称/编号关键词 |
| organName | string | 发布机构（可选） |
| publishDateBegin/End | string | 发布日期范围（可选） |
| standardField | string | 标准领域（可选） |

### 响应结构

```json
{
  "code": 200,
  "data": {
    "total": 1234,
    "rows": [{ "standardNo": "T/CAS 123-2024", "standardTitleCn": "...", ... }]
  }
}
```

**关键差异**：ttbz 返回 `data.rows`，而 BaseAdapter 的 `_post_search_candidates` 期望 `records` 键，因此不能直接复用该方法。

---

## 三、架构设计

### 3.1 两层接口

| 层 | 方法 | 返回值 | 用途 |
|----|------|--------|------|
| 指令层 | `query_standards(number, **kwargs)` | `list[QueryResult]` | 外部直接调用，返回全部匹配结果 |
| 引擎层 | `_search(term)` | `Optional[QueryResult]` | 融入 BaseAdapter 渐进搜索体系 |

`_search` 内部调用 `query_standards` 取第一条结果返回。

### 3.2 字段映射

| API 字段 | QueryResult 字段 | 方式 |
|----------|-----------------|------|
| `standardNo` | `standard_number` | 直接映射 |
| `standardTitleCn` | `standard_name` | 直接映射 |
| `standardTitleEn` | `result.standard_name_en` | 动态属性 |
| `publishDate` | `publish_date` | 直接映射 |
| `implementDate` | `implementation_date` | 直接映射 |
| `standardStatusName` | `status` | 直接映射 |
| `organName` | `responsible_dept` | 直接映射（语义最近） |
| `standardField` | `result.field` | 动态属性 |
| `standardUniqueId` | `hcno` | 直接映射 |

QueryResult 不包含 `standard_name_en`、`publisher`、`field` 字段。前两者以动态属性承载，`organName` 映射到语义最近的 `responsible_dept`。

### 3.3 类结构

```
TTBZAdapter(BaseAdapter)
├── API_URL = "https://www.ttbz.org.cn/cms-proxy/ms/portal/standardInfo/getPortalStandardList"
├── site_name → "ttbz"
├── site_label → "全国团体标准信息平台"
├── __init__()          → 创建 httpx.Client + headers
├── query_standards()   → POST API → 解析 data.rows → list[QueryResult]  [指令层]
├── _search()           → 调 query_standards 取首条                      [引擎层]
├── _parse_result()     → 单条 JSON → QueryResult                       [引擎层]
└── _build_search_data()→ 构造 form data                                [引擎层]
```

### 3.4 错误处理

- 网络异常 → 返回空列表 `[]`
- JSON 解析失败 → 返回空列表 `[]`
- API 返回非 200 → 返回空列表 `[]`
- 不抛出异常

### 3.5 请求频率

单次查询间隔 ≥ 1 秒，通过 `time.sleep(1)` 简单控制。SiteState 中设置 `cooldown_seconds=1`。

### 3.6 动态属性防护措施

`standard_name_en` 和 `field` 作为动态属性挂载到 QueryResult，存在以下风险及对应的防护：

| 风险点 | 防护措施 |
|--------|---------|
| IDE 无提示 | `_parse_result()` 中添加注释说明动态字段名及 API 来源 |
| 序列化遗漏 | 若需导出 JSON，显式包含 `result.standard_name_en` 和 `result.field` |
| 测试覆盖不足 | 单元测试中必须断言这两个动态属性的存在性和值类型 |
| 未来模型升级冲突 | 在 `QueryResult` 类文档中标注 `standard_name_en`、`field` 为"保留字段名"，防止后续版本误加同名字段 |

---

## 四、涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `pilotstd/query/adapters/ttbz.py` | **新建** | 适配器主体 |
| `pilotstd/query/adapters/__init__.py` | 修改 | import + `__all__` |
| `pilotstd/query/site_config.py` | 修改 | 新增 SiteState |
| `pilotstd/query/search_strategy.py` | 修改 | `group` 类型 primary 改为 `ttbz` |
| `pilotstd/query/engine/_constants.py` | 修改 | 路由链加 `ttbz` |
| `pilotstd/query/__init__.py` | 修改 | 懒加载函数 |
| `tests/test_adapters.py` | 修改 | 新增 TestTTBZAdapter |

---

## 五、验收标准

| 检查项 | 验证方式 |
|--------|---------|
| 搜索标准号 | `query_standards("T/CAS 123")` 返回匹配结果 |
| 搜索关键词 | `query_standards("团体标准")` 返回结果列表 |
| 空关键词 | 返回空列表，不报错 |
| 网络异常 | 超时/连接失败时返回空列表 |
| 字段映射 | 所有字段映射正确 |
| 引擎兼容 | `_search("T/CAS 123-2024")` 返回 QueryResult |
