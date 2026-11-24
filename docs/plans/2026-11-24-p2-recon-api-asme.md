# Task 0 站点侦查：API Webstore 与 ASME（P2-7.2 前置）

| 项目 | 值 |
|------|-----|
| 任务 | P2-7.2「新增/评估适配器」→ Task 0 站点侦查（API Webstore / ASME） |
| 日期 | 2026-11-24 |
| 性质 | 只读侦查；**未改任何代码/配置/其他文档，未 git commit/push** |
| 侦查方法 | `docs/reference/adapter-development.md` §9 两阶段模型（curl/httpx 探测 → Playwright 捕获 XHR） |
| 工具 | curl 8.22.0、httpx 0.28.0、Python 3.14、Node 24.15、Playwright **1.62.0**（本机 `web/node_modules/.pnpm/playwright@1.62.0`） |
| 网络 | 本次**实测成功**（两站均可从本机直连，无代理、无分片/镜像；无需 TLS 绕过） |
| 结论一句话 | **两站均 VIABLE**（无需登录/付费/captcha 即可拿到标准元数据），但都**不是**普通 HTML/GET-JSON 站点：API Webstore 需用公开 Coveo 搜索 token 发 **POST** 查询；ASME 需先做 designator 规整，且其结果要等 P1-7.1 的 `ASME B16.5` 拆号修复（G1/G2）后 match 才能达标。 |

> 已查阅（文档依据，非记忆）：
> - `docs/reference/adapter-development.md` §9「站点侦查方法论」（两阶段模型 + 五站结论 + 放弃标准）、§5「新增适配器标准流程」、§6「新适配器检查清单」
> - `pilotstd/query/adapters/base.py`（`BaseAdapter` 契约：`site_name`/`site_label`/`_search`/`_parse_result`；`_search_candidates` 才返回多候选）
> - `pilotstd/query/adapters/iso_gov.py`（英文站字段口径：`standard_number/standard_name/status/publish_date/responsible_dept/hcno`）
> - `pilotstd/query/models.py`（`QueryResult` 字段全集与 `is_found()` 契约）
> - `pilotstd/query/search_strategy.py`（`ADAPTER_TYPE_MAP`、`map_status`、`_strip_code_noise`、`match_result`/`_exact_parse_match`）
> - `pilotstd/query/adapters/registry.py`、`pilotstd/query/site_config/_profiles.py`、`_sites.py`（注册与站点画像）
> - `docs/plans/2026-11-24-p1-api-asme-gap.md`（P1-7.1 编号识别缺口：ASME B 系列拆号、API 类型词污染代号）
>
> 证据工件（仓库外，`%TEMP%`=`C:\Temp`）：`C:\Temp\recon1\*.bin/*.json`、`C:\Temp\recon\*.js|*.py|*.json`、`*_dom.txt`、截图 `api_autocomplete.png / api_search_results.png / api_detail_610.png / asme_detail.png / asme_search.png`。

---

## 1. 第一阶段：curl / httpx 探测（可达性、协议、WAF、页面形态）

### 1.1 实测结果（`curl.exe -sS -L --compressed`，UA=Chrome 131，2026-11-24 14:5x UTC）

| # | URL | HTTP | size_download | Content-Type | 结论 |
|---|-----|------|---------------|--------------|------|
| 1 | `https://www.apiwebstore.org/` | **200** | 154,496 B | text/html; charset=utf-8 | 可达；**SSR 页，不是 SPA 空壳**（HTML 内嵌 Trending Standards 全量数据） |
| 2 | `https://www.api.org/products-and-services/standards` | 200 | 8,773 B | text/html | 可达（导航/官网，另用 Coveo 做站内搜索） |
| 3 | `https://www.apiwebstore.org/standards/610` | 200 | 131,171 B | text/html | 可达；**商品详情页是客户端渲染壳**（curl 原文无商品字段，浏览器执行后渲染，见 §2.3） |
| 4 | `https://www.asme.org/` | **200** | 171,424 B | text/html; charset=utf-8 | 可达；SSR（Vue 2.7.16 + jQuery） |
| 5 | `https://www.asme.org/codes-standards/find-codes-standards` | **200** | 30,568 B（传输，解压后 146,392 B） | text/html | 可达；产品列表壳，数据由 `/api/products` 异步加载 |
| 6 | `https://www.asme.org/search` | 200 | 36,072 B（解压后 161,293 B） | text/html | 可达；站内搜索页，hash 路由 `#stq=` |
| 7 | `https://store.asme.org/` | **000 / DNS 失败** | 0 | — | `curl: (6) Could not resolve host` → **ASME 无独立 store 域名**，官方商品目录就在 `www.asme.org/codes-standards` |
| 8 | `https://store.accuristech.com/api`（+ `global.ihs.com`、`www.techstreet.com/api/`，旧 API 标准经销商） | **403** | 3,281 / 3,261 / 3,282 B | text/html | 第三方经销站点对自动化直接 403，**不作为数据源**（也未纳入） |

### 1.2 协议 / TLS / WAF / 反爬特征

| 维度 | API Webstore（`www.apiwebstore.org`） | ASME（`www.asme.org`） |
|------|--------------------------------------|--------------------------|
| 协议 / TLS | HTTPS 1.1/2，证书有效（未用 `-k`，无 TLS 错误） | HTTPS 1.1/2，证书有效；HSTS `max-age=31536000` |
| 承载 | Microsoft **Azure Front Door**（`x-azure-ref`、`X-Cache: PRIVATE_NOSTORE`）+ Sitecore XM Cloud/SXA（Cookie `sxa_site=Webstore`、`shell#lang`） | Microsoft **Azure App Service**（`ARRAffinity` / `ARRAffinitySameSite`）+ `Request-Context: appId=cid-v1:…` |
| Cloudflare / JSL / WAF | **无**（0 命中 cloudflare / turnstile / `__NEXT_DATA__`） | **无**（0 命中 cloudflare / turnstile；无 412/527） |
| 反爬动作 | 无验证码、无登录墙；只有登录/注册用 reCAPTCHA SiteKey（登录页才触发） | 无验证码、无登录墙；`/api/products` 裸 curl 即 200 |
| 页面类型 | 首页 SSR（内嵌 Sitecore page data）；`/standards` 与 `/standards/{code}` 路由客户端渲染 | 全站 SSR + 局部 AJAX（列表 JSON、站内搜索 JSONP） |
| 编码 | UTF-8 | UTF-8 |
| 结论 | 非 Cloudflare/JSL 型，无「第一阶段即 BLOCKED」迹象 | 同左 |

> 说明：`asme.org` 首页/列表页均返回带 `ARRAffinity` 的 Set-Cookie，但后续 JSON 接口**不需要带 cookie**（见 §2.4 裸 curl 复现）。

---

## 2. 第二阶段：Playwright 捕获 XHR + 脱离浏览器独立复现

### 2.1 API Webstore — 真实接口是 Coveo Search API（POST）

**Playwright 过程**：打开 `https://www.apiwebstore.org/` → 等 5s → 定位 MUI Autocomplete（`input[placeholder="Search Standards and Training"]`）→ 输入 `API 610`（带 200ms/字符间隔）→ 回车 → 页面跳到 `https://www.apiwebstore.org/standards#q=API%20610`（显示 “Showing 1110 results for 'API 610'”）。`page.on('request'|'response')` 捕获到的 JSON 端点（节选）：

| 捕获 | 端点 | 说明 |
|------|------|------|
| XHR POST | `https://platform.cloud.coveo.com/rest/search/v2/querySuggest?organizationId=americanpetroleuminstituteproductionafn6944o` | 输入联想（`{"q":"API 610","pipeline":"API Webstore","searchHub":"Webstore",…}`） |
| XHR POST | `https://platform.cloud.coveo.com/rest/search/v2?organizationId=americanpetroleuminstituteproductionafn6944o` | **真实搜索接口**，body 含 `q/pipeline/searchHub/tab/fieldsToInclude/facets…`，`fieldsToInclude` 明确列出 `productcode/edition/status/publisheddate/ispreviousedition/…` |
| XHR GET | `https://ecommerce-prod-apim.azure-api.net/cart-order/cartOrder/anontoken` | 商城匿名 token（仅购物车/详情页需要，**搜索不需要**） |
| XHR GET | `https://www.apiwebstore.org//sitecore/api/jss/dictionary/webstore/en?sc_apikey={01D9ED26-…}` | Sitecore 词典，与标准数据无关 |

关键请求头：`Authorization: Bearer xx4ad653a7-23e9-4d24-9a39-b6a0742d799d`（**Coveo 公开 search token**，非用户凭据）、`Content-Type: application/json`、`Referer: https://www.apiwebstore.org/`。token 与 orgId 均出现在公开前端 bundle `https://www.apiwebstore.org/dist/webstore/static/js/main.f6ec489d.js`（5,432,899 B，各命中 1 次），可自动刷新。

**脱离浏览器独立复现（关键步骤，已实测）**：
- httpx 最小 body：`POST` 上述 URL，`{"q":"API 610","pipeline":"API Webstore","searchHub":"Webstore","tab":"default","locale":"en-US","numberOfResults":10,"firstResult":0}` → **200，26,666 B，`totalCount=1110`，10 条结果**。
- curl 最小 body（`--data-binary @file`，仅 `productcode/edition/status/producttype/publisheddate/type` 6 个 fields）→ **200，7,935 B，1.08 s**。
- 去掉 `Authorization` → **401**（`NoAuthenticationException`，“You must provide credentials…”）；换假 token → **401**（`InvalidTokenException`，“Invalid token”）。→ 只有 token 是门槛，**无 cookie/无登录/无验证码**。
- 精确过滤（aq 高级查询）`@productcode=="<code>" @producttype=="Standard"` 实测通过：`610 / 6D / 5CT / Q1 / 579-1 / 2A-WSD / 938-C / 12C` 各返回 1 条（含字母、连字符、`-WSD` 后缀的 productcode 均可用引号形式精确命中）；`producttype==Standard` 可滤掉 Training/Datasheet（`q=API 610` 从 1110 缩到 897）。

**字段映射（3 条真实样本 → `QueryResult`）**：

| 样本 | 返回 `raw`（真实值） | 映射到 `QueryResult` |
|------|----------------------|----------------------|
| API STD 610 | `title="API STD 610: Centrifugal Pumps for Petroleum, Petrochemical and Natural Gas Industries"`，`productcode=610`，`type=STD`，`edition=13`，`status=Current`，`publisheddate=06/29/2026`，`producttype=Standard`，`committee="CRE: Committee on Refinery Equipment"`，`permanentid=12c58856…` | `standard_number="API STD 610-2026"`；`standard_name="Centrifugal Pumps for Petroleum, Petrochemical and Natural Gas Industries"`；`status="现行"`；`publish_date="2026-06-29"`；`responsible_dept="CRE: Committee on Refinery Equipment"`；`hcno="12c588567517…"` |
| API SPEC 6D | `title="API SPEC 6D: Specification for Valves"`，`productcode=6D`，`type=SPEC`，`edition=25`，`status=Current`，`publisheddate=11/01/2021` | `standard_number="API SPEC 6D-2021"`；`standard_name="Specification for Valves"`；`status="现行"`；`publish_date="2021-11-01"` |
| API SPEC 5L | `title="API SPEC 5L: Line Pipe"`，`productcode=5L`，`type=SPEC`，`edition=47`，`status=Current`，`publisheddate=06/02/2026` | `standard_number="API SPEC 5L-2026"`；`standard_name="Line Pipe"`；`status="现行"`；`publish_date="2026-06-02"` |

补充真实状态样本：`API STD 682` → `status=Reaffirmed`（→ 现行）；`API SPEC 12C` → `status=Replaced`（→ 被代替）；`API STD 630` → `status=Revised`（语义待定，建议按现行处理并登记风险）。

**字段缺口（API Webstore）**：① 无中文名；② 无实施日期/废止日期（`implementation_date/abolition_date` 填 `"网站无此分类"`）；③ 无代替标准字段（`replaces` 留空）；④ `status` 取值 `Current/Reaffirmed/Revised/Replaced` 与 `map_status()` 现有词表**不重合**（现有只有 Active/Withdrawn/Superseded/Obsolete/Replaced…），需在适配器内自行映射；⑤ 年份取 `publisheddate` 的年份而非 edition 年份（610 第 13 版 publisheddate=2026，存在“上架/再发布日 ≠ 版次年”的风险）；⑥ 详情页 `uri/clickUri` 指向 APIM `sync/product/...`（非人类页面），人类链接需自行拼 `https://www.apiwebstore.org/standards/{productcode}`（已验证 `/standards/610` 渲染出 “API STD 610 / Edition 13 / Status Current”）；⑦ 索引只保留每个 productcode 的**最新版**（历史版查询会回落为 newer，见 §2.2 分页/匹配说明）。

**分页机制（实测）**：offset 型 —— `firstResult` + `numberOfResults`（Coveo 标准）。`q=API 610`：`firstResult=0,n=5` → `['610','610','682','630','30']`；`firstResult=5,n=5` → `['12C','11L2','2554','2552','2555']`，**无重叠**；`totalCount` 恒为 1110（`aq` 滤 Standard 后 897）。未实测 >2 页与 Coveo 默认结果窗口上限（>1000 条时可能截断），登记为待验证项。

### 2.2 ASME — `/api/products`（GET，结构化最好）

**Playwright 过程**：打开 `https://www.asme.org/codes-standards/find-codes-standards`（等 8s）→ 捕获到真实 XHR：`GET https://www.asme.org/api/products?type=Codes-Standards&page=1&perPage=25&sortBy=&sortByDir=asc`（200，`total=678`、`pages=28`）。站点无自由文本搜索框属于商品目录（只有 Designator/Year/Format/Topic 分面过滤）；站内全文搜索走另一条 Swiftype JSONP（§2.3）。

**脱离浏览器独立复现（关键步骤，已实测，裸 curl 无 cookie）**：
`GET https://www.asme.org/api/products?type=Codes-Standards&page=1&perPage=5&fullDesignator=B16.5` → **200，8,563 B，`total=1`**。
- designator 覆盖实测：`B16.5 / B31.3 / BPVC.VIII.1 / PTC 4 / CSD-1 / Y14.5 / A112.18.1/CSA B125.1` 均 `total=1` 精确命中；`ZZZ99.9` → `total=0`（空结果行为正常）。
- 年份过滤实测：`fullDesignator=B16.5&designatorYearStart=2020&designatorYearEnd=2020` → `total=1`（PDF 版，`DesignatorYear=2020`）；`2003/2003` → `total=1`（2003 版）。
- `perPage` 上限：`perPage=100` → 200，85,735 B，100 条（分页可用）；`page=2` 与 `page=1` 结果不同（§2.4）。
- 无 `Authorization`、无 cookie 依赖（响应里的 `ARRAffinity` 不回传也 200）。

**字段映射（3 条真实样本 → `QueryResult`）**：

| 样本 | 返回字段（真实值） | 映射到 `QueryResult` |
|------|--------------------|----------------------|
| B16.5 | `Title="B16.5 - Pipe Flanges and Flanged Fittings: NPS 1/2 through NPS 24, Metric/Inch Standard"`，`FullDesignator="B16.5"`，`DesignatorYear=2025`，`Subtitle="B16.5 - 2025"`，`ProductURL="/codes-standards/find-codes-standards/b16-5-pipe-flanges-…?productKey=M01525"`，`Format="Print Book"`，`ISBN=9780791876855`，`Editions=[2025,2020,2017,2013,2003]` | `standard_number="ASME B16.5-2025"`；`standard_name="Pipe Flanges and Flanged Fittings: NPS 1/2 through NPS 24, Metric/Inch Standard"`；`publish_date="2025"`；`status="现行"`（=最新版推断）；`link` 见下；`hcno="M01525"` |
| B31.3 | `Title="B31.3 - Process Piping"`，`FullDesignator="B31.3"`，`DesignatorYear=2024`，`ProductURL="…/b31-3-process-piping?productKey=A0372U"`，`Pages=592`，`ListPrice=695.0`，`Editions=[2024,2022,2020,…]` | `standard_number="ASME B31.3-2024"`；`standard_name="Process Piping"`；`publish_date="2024"`；`status="现行"`；`hcno="A0372U"` |
| PTC 4 | `Title="PTC 4 - Fired Steam Generators"`，`FullDesignator="PTC 4"`，`DesignatorYear=2013`，`Subtitle="PTC 4 - 2013 (R2023)"`，`PublishYear=2013`，`ProductURL="…/fired-steam-generators?productKey=C02513"`，`Editions=[2013]` | `standard_number="ASME PTC 4-2013"`；`standard_name="Fired Steam Generators"`；`publish_date="2013"`；`status="现行"`；`hcno="C02513"` |

链接口径：`link = "https://www.asme.org" + ProductURL`（相对路径 + `?productKey=`，详情页 SSR，已验证可打开并显示 B16.5 商品/版次）。

**字段缺口（ASME）**：① **无状态字段**（`status` 必须推断：`DesignatorYear == max(WebsiteProductGrouping.Editions)` → 现行，否则被代替；这是推断值，需在文档标注）；② `PublishDate` 恒为 `0001-01-01T00:00:00`（不可用），只能用 `DesignatorYear`/`PublishYear`；③ 无实施/废止日期、无归口单位、无代替关系字段；④ 结果为“商品”粒度（同一设计ator 只保证返回 1 个 format 的 1 条：如 B16.5 只回 Print Book 2025，PDF 同号商品需靠 `WebsiteProductGrouping.Formats` 得知）；⑤ designator 形态需规整：`B16.5`（点号）、`PTC 4`（空格）、`CSD-1`（连字符）、`BPVC.VIII.1`（点号分册）、`A112.18.1/CSA B125.1`（联合标准）五种并存，查询号 `ASME BPVC Section VIII Div.1` 等需先归一化为 `BPVC.VIII.1`。

**分页机制（实测）**：page 型 —— `page` + `perPage`（`total=678`、`pages=28`@25；`perPage=100` 可用）。`page=1&sortBy=title` 与 `page=2&sortBy=title` 返回不同 designator（`A112.1.2…` vs `A112.14.6…`），无重叠。适配器只需 top N（单号精确查询用 `fullDesignator` 即可，无需翻页）。

### 2.3 ASME 站内全文搜索（备用通路，GET JSONP）

Playwright 在 `https://www.asme.org/search#stq=B16.5&stp=1` 捕获到：
`GET https://api.swiftype.com/api/v1/public/engines/search.json?q=B16.5&engine_key=y_SSQuh11QNkmVqM6A5n&page=1&per_page=10&spelling=strict`（JSONP `callback=`）。
裸 curl 复现：**200，9,964 B**，`record_count=38`，首条即 `Pipe Flanges and Flanged Fittings…` 的 asme.org 商品页；但结果**混入新闻页/PDF/xlsx**（第 2 条是 society-news，第 3 条是 getmedia PDF），**不适合作为标准号精确查询主通路**，仅可作“名称模糊搜索”兜底。`engine_key` 明文出现在 `/search` 页内联脚本（`var searchEngineKey = "y_SSQuh11QNkmVqM6A5n"`），同样可刷新。

### 2.4 门槛 / 反爬小结

| 门槛 | API Webstore | ASME |
|------|--------------|------|
| 登录 | 不需要（搜索/详情均可匿名） | 不需要 |
| 付费 | 元数据免费；全文 PDF 付费（本适配器不下载） | 元数据免费；标准正文付费 |
| 验证码 | 无（仅账号登录有 reCAPTCHA 配置） | 无 |
| API key / token | **需要公开 Coveo search token**（`xx4ad653a7-…`，仅检索权限；缺失/错误 → 401） | 不需要（`/api/products`）；Swiftype 需公开 `engine_key` |
| Cookie 依赖 | 无 | 无 |
| 请求方法约束 | **搜索为 POST JSON**（只读检索） | GET |
| 限流 | 未观测到（本次 <20 次请求）；未测峰值 | 未观测到；`perPage=100` 正常 |
| 数据时效 | 索引 = 每 productcode 最新版 | 每 designator 当前可售版次 |

> ⚠️ **与「只读：只允许 GET/HEAD/OPTIONS」的口径冲突提示**：Coveo 搜索是 **POST**（JSON 查询体，纯检索，非表单/写操作，与第二阶段“自动触发一次搜索并复现 API”要求一致）。已核对：未注册账号、未提交购买/表单、未触发任何下载。若任务包要求严格“零 POST”，API Webstore 无 GET 版搜索接口，只能退回 Playwright 自动化（更重、更脆），需任务方明确口径。

---

## 3. 结论与风险

### 3.1 结论

| 站点 | 结论 | 判定依据 |
|------|------|----------|
| **API Webstore** | **VIABLE** | 公开 Coveo 检索 API 已 curl/httpx 双通道独立复现（200；q=API 610 → 1110 条；`aq` 精确 productcode 全形态命中）；字段足够映射 `standard_number/name/status/publish_date/hcno`；无需登录/付费/captcha；分页 offset 可用 |
| **ASME** | **VIABLE（带依赖）** | `/api/products` 裸 curl 200；`fullDesignator` 精确命中 8 种 designator 形态，年份过滤可用；字段足够映射；无需登录。但**状态需推断**，且结果编号 `ASME B16.5-2025` 会被现有 `parse_std_number` 拆成 `ASMEB1/6/5`，`match_result` 判 mismatch/code_only（P1-7.1 已证），**必须等 P1 G1/G2 修复后**才能达到 `MATCH_SCORE_CONFIRMED=50` 阈值 |

### 3.2 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | API Webstore 的 Coveo token/orgId 轮换（前端发版） | 401，适配器静默返回空 | 从首页 HTML 找 `main.<hash>.js` → 正则提取 token/orgId 缓存；401 时刷新一次重试；加 warning 日志 |
| R2 | API Webstore 用 POST（口径冲突见 §2.4） | 若硬约束禁 POST 则不可实现 | 需任务方确认口径；备选 Playwright（不推荐） |
| R3 | ASME 编号与匹配链路不兼容（P1 G1/G2） | 结果判 mismatch/code_only（20 分）→ 待确认 | P2 排在 P1 之后；先合 P1 的 ASME B 系列/BPVC 修复，再接入 |
| R4 | ASME designator 归一化不全（`BPVC Section VIII Div.1`、册/篇字母、联合标准） | 查不到或查错 | 适配器内做归一化映射表 + 单测覆盖 8 种形态；无法归一化时回退 Swiftype 名称搜索 |
| R5 | 站点改版（Sitecore 发版 / ASME 目录重构） | JSON 契约变化 | 解析失败打 warning 并返回空（沿用 iso_gov 的 `ValueError` 日志范式），fixture 冻结真实响应 |
| R6 | 年份口径差异（API `publisheddate` 可能是上架日；ASME 只有版次年） | `publish_date` 语义偏差，影响“取最新”排序 | 文档标注；匹配只依赖编号不做年份强校验（沿用 `_search_progressive` 第 4 步 newer/older 兜底） |
| R7 | 限流未知 | 批量查询被限/封 | `request_interval` 设 ≥1.0s；沿用 SiteState 冷却机制；仅取 top-N 单号查询 |
| R8 | 商品站性质：API/ASME 标准正文均付费 | 用户可能期待“可下载” | `is_downloadable` 沿用 iso_gov 口径（非采标=True，实际下载链对非 GB 站点本就不自动下载，见 `08-known-boundaries`）；文档说明只提供元数据 |

---

## 4. 预估工作量（两站合计）

| 项 | API Webstore | ASME | 合计 |
|----|--------------|------|------|
| 新增适配器文件 | `api_webstore.py`（Coveo POST + token 刷新 + 状态映射，~150 行） | `asme.py`（`/api/products` + designator 归一化 + 状态推断，~160 行） | 2 文件 / ~310 行 |
| Fixture | 1 个（`tests/fixtures/api_webstore_610.json`，真实响应裁剪） | 1 个（`tests/fixtures/asme_b165.json`） | 2 文件 |
| 单测 | ~10 例（精确/空结果/字母 code/状态映射/分页/token 失败） | ~10 例（8 种 designator + 年份 + 空结果；另加归一化表驱动） | **~21-24 例** |
| 冒烟脚本 | `scripts/smoke_test_api_webstore.py` | `scripts/smoke_test_asme.py` | 2 文件 |
| 注册/配置 | `registry.py`(+2 行)、`_profiles.py`(+2 画像)、`_sites.py`(+2 SiteState)、`search_strategy.py` `ADAPTER_TYPE_MAP`（`asme`/`api` 的 primary 改指新适配器）、必要时 `engine/_constants.py` `CODE_ROUTES` | 同左（共享同一批文件，需串行改避免冲突） | ~5 文件 / ~40 行 |
| 文档联动 | `docs/reference/adapter-development.md` 架构差异表 +1~2 行、`08-known-boundaries`（非 GB 元数据边界） | 同左 | 2 文档 |
| 前置依赖 | 无 | **P1 G1（ASME B 系列拆号）/ G2（BPVC 写法）必须先行** | P1 约 0.5~1 人日 |
| 开发估算 | 0.5~1 人日 | 1~1.5 人日（含归一化与依赖联调） | **约 2~2.5 人日（不含 P1 前置）** |

文件数合计：**约 12~14 个文件**（2 适配器 + 2 fixture + 2 smoke + ~5 注册配置 + 2 文档，测试用例并入现有 `tests/test_adapters.py` 或各自新文件）；用例数 **21~24**。

---

## 5. 下一步（若要实现，第一步做什么）

1. **先做 API Webstore**（无前置依赖、证据最完整）：新建 `pilotstd/query/adapters/api_webstore.py`，实现：
   - `_search_candidates()`：把查询串解析成 `productcode`（正则 `API\s+(?:(?:STD|SPEC|RP|BULL|TR|MPMS|TDB|PUBL)\s+)?([0-9][0-9A-Z]*(?:-[0-9A-Z]+)?)`，注意 `6D/5CT/579-1/2A-WSD/938-C` 等形态）；
   - `POST https://platform.cloud.coveo.com/rest/search/v2?organizationId=…`，body `{q:"", aq:'@productcode=="<code>" @producttype=="Standard"', pipeline:"API Webstore", searchHub:"Webstore", numberOfResults:10, firstResult:0}`，头 `Authorization: Bearer <token>`；
   - token 从 `main.<hash>.js` 懒加载提取（缓存），401 刷新重试一次；
   - `status` 映射表 `Current/Reaffirmed→现行`、`Replaced→被代替`、`Revised→现行（登记风险）`；`standard_number=f"API {type} {code}-{year(publisheddate)}"`；link 用 `/standards/{code}`；`hcno` 用 `permanentid`。
   - 落 fixture + ≥10 单测（`tests/test_adapters.py` 追加 `TestApiWebstoreAdapter`，HTTP 用 `safe_post` mock）+ 冒烟脚本，再注册到 `registry.py`/`site_config`/`ADAPTER_TYPE_MAP["api"]`。
2. **等 P1 G1/G2 合入后**再接 ASME：`asme.py` 用 `GET /api/products?type=Codes-Standards&page=1&perPage=5&fullDesignator=<归一化 designator>`（有年份时加 `designatorYearStart/End`），`standard_number=f"ASME {FullDesignator}-{DesignatorYear}"`，`publish_date=str(DesignatorYear)`，link=`https://www.asme.org` + `ProductURL`，`status` 按 edition 是否最新推断；归一化映射表 `B16.5 / PTC 4 / CSD-1 / BPVC.VIII.1 / A112.18.1/CSA B125.1 / Section VIII Div.1→BPVC.VIII.1` 单测锁定。
3. **不要**把 `docs/plans` 里的结论当“已经实现”——本次零代码改动；两站都应在 `ADAPTER_TYPE_MAP` 里保持 `iso_gov` 为 fallback，避免新适配器改版时整链失败。

---

## 6. 复现命令（供下一位侦查/实现者）

```powershell
# API Webstore：Coveo 检索（最小复现；curl 需 --data-binary @file 避免 PowerShell 吞引号）
curl.exe -sS -X POST "https://platform.cloud.coveo.com/rest/search/v2?organizationId=americanpetroleuminstituteproductionafn6944o" `
  -H "Authorization: Bearer xx4ad653a7-23e9-4d24-9a39-b6a0742d799d" -H "Content-Type: application/json" `
  --data-binary "@C:\Temp\recon1\coveo_min.json"     # 200 / 7,935 B

# ASME：精确 designator（裸 curl，无 cookie）
curl.exe -sS "https://www.asme.org/api/products?type=Codes-Standards&page=1&perPage=5&fullDesignator=B16.5"   # 200 / 8,563 B

# ASME：站内全文搜索（备用）
curl.exe -sS "https://api.swiftype.com/api/v1/public/engines/search.json?q=B16.5&engine_key=y_SSQuh11QNkmVqM6A5n&page=1&per_page=5&spelling=strict"  # 200 / 9,964 B
```

Playwright 侦查脚本（仓库外）：`C:\Temp\recon\api_search2.js`（API 搜索 XHR）、`C:\Temp\recon\api_detail.js`（详情页）、`C:\Temp\recon\asme.js`（列表/详情/站内搜索）、`C:\Temp\recon\asme_search5.js`（Swiftype 捕获）；httpx 复现：`C:\Temp\recon\coveo_repro.py` / `coveo_detail.py` / `coveo_aq2.py`。

---

## 7. 交付自检

- [x] 两站均完成第一阶段（状态码/字节数/WAF/SPA 判定，实测值见 §1）
- [x] 两站均完成第二阶段（Playwright 加载 + 触发搜索 + `page.on("response")` 捕获 XHR，URL/方法/请求头/参数已记录）
- [x] 两站真实 API 均**脱离浏览器独立复现成功**（curl + httpx，状态码/字节数见 §2）
- [x] 各取 **3 条真实样本**映射 `BaseAdapter`/`QueryResult` 字段，缺口已列
- [x] 分页机制实测（API：`firstResult/numberOfResults`；ASME：`page/perPage`）
- [x] 反爬/门槛实测（登录/付费/验证码/API key 逐项结论见 §2.4）
- [x] 结论 VIABLE + 工作量 + 风险 + 下一步
- [x] 只写本文件；未改代码/配置/其他文档；未 commit/push；临时脚本在 `%TEMP%`

**文件行数：224 行**（`[IO.File]::ReadAllLines` 实测，LF 换行无 BOM；26,054 字节，UTF-8）。
