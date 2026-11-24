# P2 Task 0 站点侦查：重庆市标准信息网 / 福建省标准信息网

| 项目 | 值 |
|------|-----|
| 任务包 | P2「新适配器」Task 0 站点侦查（两站） |
| 日期 | 2026-11-24（侦查环境时间 22:52–23:15 CST） |
| 性质 | **只读侦查**：仅 GET/HEAD/OPTIONS；未注册、未提交业务表单、未下载；不改代码/配置/其它文档，不提交 |
| 侦查对象 | 目标 A：重庆市地方标准公开平台（任务称「重庆市标准信息网」）；目标 B：福建省标准信息服务平台（任务称「福建省标准信息网」） |
| 证据方式 | 第一阶段 curl/httpx + 第二阶段 Playwright（chromium，headless）+ curl 独立复现；探针脚本与原始响应全部落在 `C:\Temp`（仓库外） |
| 结论一句话 | **重庆 VIABLE**（真实 JSON API 已 curl 复现，HTTP 明文、无鉴权；含路由接入预计 0.75–1.5 人日）；**福建 BLOCKED**（唯一官方入口 TCP 全部超时，ICMP 可达而兄弟政务站可达，Playwright 亦无法打开；零代码可写）。 |

> 已查阅（文档依据，非记忆）：
> - `docs/reference/adapter-development.md` §1「永远不要根据域名/后缀猜测技术栈」、§3「先找真实 API」、§4「编码检测」、§5「新增适配器标准流程」、§6「新适配器检查清单」、§7「纯 IP 站点对接范式」、§9「站点侦查方法论」
> - `pilotstd/query/adapters/base.py`（`BaseAdapter` 契约：`site_name/site_label/_search/_search_candidates/_build_search_data/_post_search_candidates/_post_process_result/_detect_split_parts`）
> - `pilotstd/query/adapters/dbba.py`（地方标准 JSON POST 参考口径：`map_status`/`is_adopted`/`ts_to_date`/`status="废止"` 处理）
> - `pilotstd/query/adapters/ahbz.py`（模糊检索 + 客户端精确过滤 + 日期归一参考）
> - `pilotstd/query/models.py`（`QueryResult` 15 个字段）、`pilotstd/core/status.py`（`Status` 枚举）、`pilotstd/query/search_strategy.py:240-321`、`pilotstd/query/engine/_constants.py:29-47`、`config/site_capabilities.yaml:141-147`

---

## 0. 结论摘要

| 站点 | 官方入口（确认方式） | 第一阶段 | 第二阶段 | 结论 | 预估工作量 |
|------|----------------------|----------|----------|------|-----------|
| 重庆市地方标准公开平台 | `http://db.cqis.cn/`（搜索结果 + 实测 200） | HTTP 200，58,229 B（解压后），UTF-8，ASP.NET MVC 5.2；**无 TLS** | Playwright 触发搜索并捕获 `POST /LocalStandard/GetDB50ShareList`；curl 独立复现成功 | **VIABLE**（注：v2 路由需先解决省份粒度，见 §6.4） | **0.75–1.5 人日** |
| 福建省标准信息服务平台 | `http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx`（**二手**：省/县政府公开答复） | 全部端口 TCP 超时（0 B，curl exit 28）；ICMP 可达 | Playwright `net::ERR_CONNECTION_TIMED_OUT` | **BLOCKED**（网络/IP 白名单门槛，非验证码非登录） | **0 人日**（复测前置） |

**两站合计：0.75–1.5 人日（仅 CQ 可排期，其中含 v2 省份路由接入 0.25–0.5 人日；FJ 需网络条件变化后重新侦查）。**

---

## 1. 侦查方法与边界

按 `adapter-development.md` §9 两阶段执行，且严格遵守 §1「不按域名后缀猜技术栈」：

1. **第一阶段（curl/httpx，2 分钟/站）**：确认正确官方域名 → 记录状态码/字节数/编码/响应头/是否 SPA 壳/是否 WAF。
2. **第二阶段（Playwright，5–10 分钟/站）**：加载页面 → 填入标准号并触发一次检索 → 捕获 XHR/JSON 端点 → 记录 URL/方法/参数 → **curl 独立复现**（关键：确认脱离浏览器可用）。
3. **字段映射**：≥3 条真实样本 → `QueryResult`，列缺口；**分页**、**反爬/门槛**、**空结果**逐一实测。
4. 全部原始响应与探针脚本落在 `C:\Temp\cqfj_probe\`、`C:\Temp\probe_*.py`、`C:\Temp\recon_playwright.py`（仓库外，见 §8）。

工具版本：`curl 8.22.0`、`Python 3.14.2`、`httpx 0.28.0`、`playwright 1.62.0`（chromium-1234 已装）。

---

## 2. 第一阶段：域名确认与可达性

> 纪律：**搜索到的 URL 与实测结果分开写**。搜索只用于找入口，不用于下技术结论。

### 2.1 重庆：搜索来源 vs 实测

| 来源类型 | URL | 说明 |
|----------|-----|------|
| 搜索结果（二手） | `http://db.cqis.cn/General/ConnectUs` | 重庆市地方标准信息公开网站（省/市市场监管局系统） |
| 搜索结果（二手） | `http://db.cqis.cn/db50help/` | 平台使用指南，页面文案为「重庆市地方标准信息公开和共享平台」 |
| 公开汇总（二手） | `http://db.cqis.cn` | 《中国中小企业 2024 蓝皮书》列举「重庆市地方标准 网址」 |
| **实测入口** | `http://db.cqis.cn/` | **HTTP 200** |

**未发现独立域名的「重庆市标准信息网」**：重庆侧公开入口就是 `db.cqis.cn`（重庆市智慧市场监管一体化平台—地方标准信息公开）。任务标题中的「重庆市标准信息网」按此官方平台对接，侦查报告内统一称 `db.cqis.cn`。

实测（curl/httpx，`verify=False`，跟随跳转）：

| URL | 方法 | 状态码 | 字节数 | 编码 | 备注 |
|-----|------|--------|--------|------|------|
| `http://db.cqis.cn/` | GET | **200** | **58,229**（解压后） | **UTF-8** | `Content-Encoding: gzip`；`Set-Cookie: __RequestVerificationToken`；`Server`/`X-Powered-By` 被打码；`X-AspNetMvc-Version: 5.2`、`X-AspNet-Version: 4.0.30319` |
| `https://db.cqis.cn/` | GET | — | 0 | — | `ConnectError: [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE]` → **站点只提供 HTTP** |
| `http://db.cqis.cn/LocalStandard/Index` | GET | **200** | **59,175** | UTF-8 | 地方标准检索页（真实搜索入口） |
| `http://db.cqis.cn/LocalStandard/SeniorIndex` | GET | **200** | **76,263** | UTF-8 | 高级检索页 |
| `http://db.cqis.cn/db50help/` | GET | **200** | **268,145** | UTF-8 | 平台指南 |
| `http://db.cqis.cn/LocalStandard/GetDB50ShareList?page=1&rows=15` | **GET** | **404** | 4,155 | UTF-8 | 证明列表接口**只接受 POST**（GET 不会误返回数据） |

页面标题（UTF-8 解码）：`重庆市智慧市场监管一体化平台—地方标准信息公开`。

编码结论：**UTF-8（页面与 JSON 均实测可 UTF-8 解码，GBK 解码失败）**；不含 GBK/GB2312 陷阱。无 SPA 壳、无 JSL/WAF 挑战页（首页即完整 HTML）。

### 2.2 福建：搜索来源 vs 实测

| 来源类型 | URL | 说明 |
|----------|-----|------|
| 搜索结果（二手，官方答复） | `http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx` | 福建省政府 2013 答复、古田县政府 2024-12 答复均给此地址 |
| 搜索结果（二手，官方答复） | `http://pt.fjbz.org.cn:8060/` | 福建省市场监管局「如何查询福建省地方标准」答复 |
| 搜索结果（二手，索引快照） | `http://pt.fjbz.org.cn:8060/default.aspx` | 快照文案：「标准检索…完整或部分标准号…中文/英文名称关键词…专业版查询」 |
| 搜索结果（二手） | `http://www.fjbz.org.cn/`、`http://fjis.org.cn/` | 福建省标准化研究院官网（同一 IP） |
| **实测** | 上述全部 | **无一可达（TCP 层）** |

DNS（`Resolve-DnsName` 实测，非猜测）：

- `pt.fjbz.org.cn` → A `220.160.53.32`
- `www.fjbz.org.cn` → A `220.160.53.32`
- `fjbz.org.cn` → A `220.160.53.32` + AAAA `240e:678:c00:100::1401`
- `fjis.org.cn` → A `220.160.53.32`

实测（每个 URL 均重试 ≥2 次，`--max-time 8~20`）：

| URL / 目标 | 方法 | 结果 | 证据 |
|------------|------|------|------|
| `http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx` | GET | **超时，0 B** | `curl exit 28`；Playwright `net::ERR_CONNECTION_TIMED_OUT` |
| `http://pt.fjbz.org.cn:8060/`、`/default.aspx` | GET | 超时，0 B | `curl exit 28` |
| `https://pt.fjbz.org.cn:8060/` | GET | 超时，0 B | `curl exit 28` |
| `http://www.fjbz.org.cn/`、`https://www.fjbz.org.cn/` | GET | 超时，0 B | 首次 httpx 曾报 `ConnectError WinError 10061（连接被拒绝）`，后续全部超时 |
| `http://pt.fjbz.org.cn/`（80）、`http://fjis.org.cn/` | GET | 超时，0 B | `curl exit 28` |
| `220.160.53.32` 端口 `80/443/8060/8080/8443/9000` | TCP | **全部 False** | `Test-NetConnection -InformationLevel Quiet` |
| IPv6 `240e:678:c00:100::1401` :80 / :8060 | GET | 超时，0 B | `curl -6 exit 28` |
| ICMP `220.160.53.32` | ping | **2/2 通，404/409 ms** | `Test-Connection` → **主机在线** |
| tracert `220.160.53.32` | — | 到 `61.154.8.117`、`120.36.77.234`（福州电信动态段）后超时 | 路径到达福建电信边缘，目标侧丢弃 |
| 第三方 TLS 扫描（二手） | — | `myssl.com` 对 `www.fjbz.org.cn:8060` 记录「connection reset by peer」 | 说明非本机独有，公网扫描器亦被拒 |

**对照组（证明本机网络与「福建政务网」可达，阻断是目标站点特有）**：

| 对照 URL | 状态码 | 字节数 |
|----------|--------|--------|
| `http://www.fujian.gov.cn/` | **200** | 423,621 |
| `http://scjgj.fujian.gov.cn/` | **200** | 103,031 |
| `https://std.samr.gov.cn/` | **200** | 109,033 |
| `https://dbba.sacinfo.org.cn/stdList` | **200** | 32,530 |

另：`web_fetch` 工具侧（另一网络）取 `http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx` 亦失败（`fetch failed`），二手旁证站点对外不可达。

---

## 3. 重庆站（`db.cqis.cn`）— **VIABLE**

### 3.1 站点画像（实测，非猜测）

- 架构：**ASP.NET MVC 5.2**（`.NET Framework 4.0.30319`）服务端渲染 + jQuery AJAX 分页；非 SPA、非 JSL、非 WAF 挑战页。
- 协议：**仅 HTTP**（HTTPS TLS 握手失败）。无纯 IP 需求、无自签名证书问题（`db.cqis.cn` 是正常域名）。
- 编码：UTF-8（页面 + JSON）。列表接口 `Content-Type: text/html; charset=utf-8`（返回值却是 JSON，属站点契约不规范，`resp.json()` 仍可用）；详情接口 `Content-Type: application/json; charset=utf-8`。
- 页面与 API 的关系：**首页/检索页 HTML 只是壳，结果表 `#bodyList` 由 JSON 渲染**（`cq_search.html:978-1087`）→ **适配器不需要解析 HTML**。

### 3.2 真实 API（Task 0 核心产物，已 curl 复现）

前端来源：`/SharePage/js/jquery-ajax-pager.js`（`sjAjaxPager`，默认 `type: "POST"`）+ 检索页内联脚本。

**列表 / 检索接口**

```
POST http://db.cqis.cn/LocalStandard/GetDB50ShareList
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
（无 token / 无 Cookie 要求，实测裸请求即 200）

queryJson={"FinishCode":"<标准号>","BZName":"<名称>","SourceName":"<地区>",
           "ClassificationIndustry":"","StandardCategory":"","OtherCategory":""}
page=1        # 1 起，前端 sjAjaxPager 传入
rows=15       # 默认 15；实测 15/50/100/200/300/500/1000 均接受
```

响应 JSON（顶层键）：

```json
{"rows":[{...}], "draftCompanyList":[{...}], "draftPersonList":[{...}],
 "total":1, "page":1, "records":2168}
```

> **陷阱**：`total` 恒为 `1`（对 2168 条结果也是 1），**分页总数只能用 `records`**；`page` 回显当前页。

**详情接口（列表字段不够时补查）**

```
POST http://db.cqis.cn/LocalStandard/GetPublicInfo?timestamp=<毫秒时间戳>
body: keyValue=<BZProjectPublicId>
响应: {"info":{...}, "draftCompanyList":[...], "draftPersonList":[...]}
```

详情页 HTML 入口：`http://db.cqis.cn/LocalStandard/Details?BZProjectPublicId=<uuid>`（页面 JS 再发上面的 AJAX）。
全文/PDF：`AttachmentUrl` 为站内相对路径，`HEAD` 实测 **200 / `application/pdf` / `Content-Length: 218475` / `Accept-Ranges: bytes`**（在线浏览走 `/LocalStandard/ShowPdf?keyValue=<uuid>`）。

### 3.3 第二阶段：Playwright 实跑证据

脚本：`C:\Temp\recon_playwright.py`（headless chromium，UA=Chrome 125）。

```
[CQ] goto homepage → title=重庆市智慧市场监管一体化平台—地方标准信息公开
[CQ] fill #FinishCode="DB50/T" → click button.btn-search
     after-search url=http://db.cqis.cn/LocalStandard/Index?FinishCode=DB50%2FT&BZName=&SourceName=%E9%87%8D%E5%BA%86
     结果 DOM 行数=15；分页文案="... 1 2 ... 144 145 下一页 末页 共 145 页"
[CQ] 捕获 XHR:
     POST http://db.cqis.cn/LocalStandard/GetDB50ShareList
       post_data=queryJson=%7B%22FinishCode%22%3A%22DB50%2FT%22%2C%22SourceName%22%3A%22%E9%87%8D%E5%BA%86%22%2C%22BZName%22%3A%22%22%2C...
       → 200, ctype=text/html; charset=utf-8, body 首段为 rows[]
     点结果标题 → http://db.cqis.cn/LocalStandard/Details?BZProjectPublicId=dba6c814-...
       详情 number=DB50/T 950-2026 / name=荣昌卤鹅加工技术规范
       捕获 POST /LocalStandard/GetPublicInfo?timestamp=1795532949000  body=keyValue=dba6c814-...
```

浏览器实际请求体（与本文 §3.2 一致，字段顺序随机不影响）：`queryJson` 内含 `FinishCode / SourceName / BZName / ClassificationIndustry / StandardCategory / OtherCategory`，外加 `page`、`rows`。

### 3.4 curl / httpx 独立复现（关键：脱离浏览器可用）

```bash
# 列表：curl 复现（无 UA/Referer/X-Requested-With 也成功，见 §3.8）
curl -s -X POST "http://db.cqis.cn/LocalStandard/GetDB50ShareList" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode 'queryJson={"FinishCode":"DB50/T 950","BZName":"","SourceName":"","ClassificationIndustry":"","StandardCategory":"","OtherCategory":""}' \
  --data "page=1&rows=15"
# → 200, records=2, rows=[DB50/T 950-2026(现行), DB50/T 950-2019(废止)]

# 详情
curl -s -X POST "http://db.cqis.cn/LocalStandard/GetPublicInfo" \
  --data "keyValue=dba6c814-91c0-483d-a691-2f08a3029833"
# → 200, info={Project_FinishCODE: "DB50/T 950-2026", RevocatoryDate: null, ScopeApplication: "...", ...}
```

复现判据（全部达到）：① 无登录/验证码；② 无 Cookie/Token 依赖；③ 返回与浏览器完全一致的结构化字段；④ 空结果与越界页行为确定（见 §3.6）。

### 3.5 字段映射（4 条真实样本 → `QueryResult`）

**样本来源**：列表接口 `FinishCode="DB50/T 950"`（2 条）+ `"DB50/T 2073"` + `"DB50/T 867.71"`；详情接口取 `dba6c814-…` 一条。

| # | 标准号（`Project_FinishCODE`） | 名称（`BZName`） | 状态（`ReleaseStatus`） | 发布（`ReleaseTime`） | 实施（`ActiveTime`） | 代替（`ReplaceStandardNumber`） |
|---|------|------|------|------|------|------|
| 1 | `DB50/T 950-2026` | 荣昌卤鹅加工技术规范 | 现行 | 2026-09-24 | 2026-12-01 | `DB50/T 950-2019` |
| 2 | `DB50/T 950-2019` | 荣昌卤鹅加工技术规范 | **废止** | 2019-12-02 | 2020-03-01 | （空） |
| 3 | `DB50/T 2073-2026` | 早熟梨种植采收全程质量控制规范 | 现行 | 2026-09-24 | **2026-12-01（未来）** | （空） |
| 4 | `DB50/T 867.71-2025` | 安全生产技术规范 第71部分：城市供水企业 | 现行 | 2025-03-24 | 2025-06-24 | （空） |

样本 1 的详情接口返回（节选，真实值）：

```
FilingNumber=131818-2026  CCSNum=X22  ICSNum=67.120.10
StandardDepartment=重庆市市场监督管理局（批准发布单位）
CompetentDepartment=重庆市经济和信息化委员会（行业主管部门）
ProposeCompany=重庆市经济和信息化委员会（提出单位）
UnderCompany=重庆市经济和信息化委员会（归口单位）
ClassificationIndustryName=工业  StandardCategoryName=方法标准
RevocatoryDate=null
ScopeApplication=本文件规定了荣昌卤鹅加工的卫生要求…适用于荣昌卤鹅的生产加工。
AttachmentUrl=/UploadFile/2026/DB50_BZProjectPublic/dba6c814-…/DB50T 950-2026 荣昌卤鹅加工技术规范.pdf
```

映射表（表头 = `QueryResult` 字段）：

| QueryResult 字段 | ← 站点字段 | 处理口径 / 缺口 |
|------------------|-----------|-----------------|
| `standard_number` | `Project_FinishCODE` | 完整含 `DB50/T` 前缀与空格（`DB50/T 950-2026`），可直接用；标准号解析交给 `_parse_result_number`/`match_result` |
| `standard_name` | `BZName` | 纯 UTF-8 文本，**无 HTML 实体**；注意个别历史名称含混合括号/多余空格（如 DB35/T 1134-2018「文化办公用纸( 含新闻纸）」），非实体问题 |
| `status` | `ReleaseStatus` | 实测值 `现行` / `废止`（JS 另支持 `即将实施`）→ `Status.ACTIVE / Status.WITHDRAWN / Status.UPCOMING`。**另需按 dbba 口径修正**：`现状=现行` 但 `ActiveTime > now` 时归 `即将实施`（样本 3 即此情形，站点自身仍标「现行」） |
| `publish_date` | `ReleaseTime` | `"2026-09-24 00:00:00"` → 需截断为 `YYYY-MM-DD`（非毫秒时间戳，**不能**用 `ts_to_date`） |
| `implementation_date` | `ActiveTime` | 同上截断 |
| `abolition_date` | `RevocatoryDate` | **仅详情接口有**；列表接口无此字段 → 不补详情时保持默认「网站无此分类」（须与 dbba 同口径） |
| `replaces` | `ReplaceStandardNumber` | 列表即有，**无需**详情页；`supports_replaces_detail` 可保持 `False` |
| `responsible_dept` | 详情：`UnderCompany`（归口单位） | 列表只有 `StandardDepartment`（批准发布单位）；口径需与 dbba（`chargeDept`）对齐后二选一 —— **这是唯一需要产品口径确认的字段** |
| `is_adopted` | 无字段 | 缺口：用 `is_adopted(name)` 名称启发式（与 dbba 一致），无法识别题录外采标 |
| `hcno` | `BZProjectPublicId` | uuid，拼详情页 `?BZProjectPublicId=`；下载侧不消费该字段（`models.py:24-27`） |
| `is_downloadable` | `AttachmentUrl` + `ReleaseStatus` | 站点对「现行 + 有附件」提供在线浏览/PDF 直链（HEAD 200）；可置 `True`，但**是否水印版未验证**（本次只 HEAD，未下载） |
| `split_into` | 站点天然有分部号（`950` / `867.71` / `1699.9`） | 可复用 `BaseAdapter._detect_split_parts`（`base.py:260-279`） |

**缺口汇总（地方站常见项逐条核对）**：

1. ✅ 标准号带 `DBxx/T` 前缀 —— 站点已带完整前缀，无需补；
2. ✅ 名称无 HTML 实体 —— 纯文本，无需 `html.unescape`；
3. ⚠️ 状态在列表页有（`ReleaseStatus`），但**废止日期、归口/提出/主管、范围、起草单位只在详情接口**；
4. ⚠️ 列表 `total` 恒 1（见 §3.2），分页必须用 `records`；
5. ⚠️ 状态与实施日期可矛盾（`现行` + 未来 `ActiveTime`）→ 需后处理；
6. ❌ 无采标字段（只能名称启发式）；
7. ❌ 无英文名 / 无摘要级标准分类（有 ICS/CCS 但 `QueryResult` 无对应字段）。

### 3.6 分页机制（实测）

| 项 | 实测结果 |
|----|----------|
| 机制 | **POST 表单 + `page` / `rows`**（非 ViewState、非 iframe、非 offset） |
| 页码 | `page` 从 **1** 起；`page=1/2/3` + `rows=1` 实测分别返回第 1/2/3 条、越界返回 `rows: []` |
| 页大小 | 默认 15；`rows` 实测支持 15/50/100/200/300/500/1000（1000 条全返回，上限未继续探） |
| 总数 | 用 `records`（`DB50/T`：2168 条 → 15 条/页共 145 页，与前端分页文案一致） |
| 空结果 | `{"rows":[],...,"total":1,"page":1,"records":0}`（HTTP 200，不报错） |
| 排序 | 未发现可传排序参数；返回顺序由站点固定（适配器不应依赖顺序，精确号命中通常 1–2 条） |

### 3.7 检索语义（影响适配器实现，实测）

| 输入（`FinishCode`） | `records` | 说明 |
|----------------------|-----------|------|
| `DB50/T 950` | 2 | 前缀+序号模糊命中（含 2019/2026 两版）→ **客户端必须再精确过滤** |
| `DB50/T 950-2026` | 1 | 完整号精确命中 |
| `DB50/T 1` | 1147 | **不是前缀匹配**（命中 `DB50/T 1699.9-2026` 等）→ 站点做分词/包含匹配 |
| `db50/t 950` | 2 | **大小写不敏感** |
| `DB50/T950-2026`（无空格） | **0** | 对**空格敏感**，与 ahbz 的教训相同（`ahbz.py:68-69`） |
| `DB50` | 2342 | 代号级 |
| `DB35/T`（`SourceName` 空） | 866 | 见 §3.9：本站镜像了全国地标 |
| `BZName=荣昌卤鹅` | 3 | 名称检索可用（含多版本/相关标准） |
| `BZName=卤鹅` | 3 | 名称子串命中 |

结论：适配器应「**按归一化后的标准号检索 + 客户端精确过滤**」（`match_result`），并对空格敏感做回退变体（复用 `BaseAdapter._search_progressive` 即可）。

### 3.8 反爬 / 门槛（实测）

| 检查项 | 结果 |
|--------|------|
| 验证码 | 无（首页/检索页/API 均无） |
| 登录 | 检索、详情、列表均**不需要**登录 |
| Token / Cookie | 页面有 `__RequestVerificationToken` 隐藏域，但 **API 未校验**：不带 Cookie、不带该 token 的裸 POST 仍 200 |
| 请求头要求 | **无**：`httpx` 只带默认头（UA=`python-httpx/0.28.0`，无自定义 UA/Referer/X-Requested-With/Cookie/Token）实测 200（`probe_cq_headers.py`） |
| WAF / JSL / CDN 壳 | 未观察到（首页直出完整 HTML；无 527 B 空壳、无 412、无 JS 挑战） |
| 限速 | 本次共 ~40 次请求无 429/封禁；无 `Retry-After` |
| 协议 | **仅 HTTP**（明文）；HTTPS 握手失败，生产接入需接受明文传输风险 |
| DNS 稳定性 | 侦查期间**出现过 1 次** `getaddrinfo failed`（瞬时），已有 `network.py` 重试可覆盖；建议适配器保留重试 |

### 3.9 覆盖度重要发现：本站是全国地方标准镜像

`FinishCode=""` 且 `SourceName=""` 时 `records=33,678` —— 该「重庆平台」**不只收录 DB50，而是镜像了全国各省地方标准**：

- `DB50/T`：2,168 条；`DB50`：2,342 条（重庆）
- `DB35/T`（福建）：**866 条**，`SourceName=福建`，`StandardDepartment=福建省质量技术监督局` 等
- `SourceName` 可过滤地区（`重庆` / `福建` / …，与 dbba 的省份概念一致）

因此：
1. **重庆适配器实际可作「地方标准第二数据源」**（与 dbba 数据重叠，需评估权威性与滞后，见 §7 风险）；
2. **福建地标（DB35/T）的题录可经此镜像拿到**（866 条），但 `AttachmentUrl` 为空 → **只有题录，没有福建全文**；
3. 适配器定位建议：**DB50 主用本适配器（cqis），DB35 仍走 dbba**，避免用镜像数据替代权威源。

DB50/T 前 1000 条状态分布：`现行` 818 / `废止` 182（本批未见 `即将实施`）；`AttachmentUrl` 覆盖 1000/1000。

### 3.10 与现有 `dbba` 的能力差异（决定「是否值得新建适配器」）

实测对照（`dbba` 用现成适配器接口 `POST https://dbba.sacinfo.org.cn/stdQueryList`，同一批号）：

| 样本 | `dbba`（现行唯一路由） | `db.cqis.cn` |
|------|------------------------|--------------|
| `DB50/T 950-2026` | ✅ 有；`status=现行`、`issueDate=1790179200000`、`actDate=1796054400000`、`reviseStdCodes=DB50/T 950-2019`、`chargeDept=重庆市市场监督管理局` | ✅ 有，字段更多（备案号/ICS/CCS/批准发布单位/归口/范围/起草单位） |
| `DB50/T 950-2019` | ✅ 有；`status=已被代替`（无废止日期） | ✅ 有；`status=废止` |
| `DB35/T 1136-2018` | ✅ 有（题录） | ✅ 有（题录，`AttachmentUrl` 空） |
| **标准全文** | ❌ 无（`dbba` 适配器固定 `is_downloadable=False`，`dbba.py:119`） | ✅ **公开 PDF 直链**（`AttachmentUrl`，HEAD 200/`application/pdf`） |
| 废止日期 | ❌ 无此字段 | ✅ 详情接口 `RevocatoryDate` |

结论：**题录层面 cqis 相对 dbba 是「更细而非更全」**（dbba 已覆盖两省样本）；新建 cqis 的**主要增量价值是「重庆地方标准全文 PDF 直链 + 废止日期/备案号等字段」**，其次是作为 dbba 的独立第二数据源。这一点应在 Task 1 立项时确认是否为目标 —— 若只需要题录，直接复用 dbba 即可，无需新适配器。

---

## 4. 福建站（`pt.fjbz.org.cn:8060`）— **BLOCKED**

### 4.1 正确入口（二手来源，非实测）

- 主入口：`http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx`（福建省政府公开答复 2013、古田县政府答复 2024-12）
- 首页：`http://pt.fjbz.org.cn:8060/default.aspx`（快照文案：标准检索、完整或部分标准号、中英文名称关键词、专业版查询）
- 详情：`.../StandardSearch/StdInfo.aspx?ID=2140014`（搜索结果快照）
- 标准跟踪：`.../standardinfo/StandardFollow.aspx`
- 「新三样」检索：`.../newenergyproducts/newenergyindex.aspx`（福建日报 2024-06 报道）
- 版权：福建省标准化研究院（0591-87577729）

> 以上仅为**入口线索**，用于说明「站点确实存在过、入口是哪个」。**技术形态（POST/ViewState/接口）一律未验证，不得据此设计** —— `adapter-development.md` §1 明确禁止按 `.aspx` 猜 WebForms。

### 4.2 第二阶段：Playwright 实跑证据

```
[FJ] goto http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx (timeout=25s)
  ERROR Error: Page.goto: net::ERR_CONNECTION_TIMED_OUT at http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx
  FJ captured XHR: []
```

即：**浏览器层也打不开**，不是"JS 渲染后才发包"的问题，而是 TCP 层不可达 → 触发 `adapter-development.md` §9 放弃标准第 1 条（Playwright headless 仍无法取得响应）。

### 4.3 阻断归因（证据链，不脑补）

| 观察 | 含义 |
|------|------|
| ICMP 2/2 通（404/409 ms） | 目标**主机在线**，网络路径可达 |
| TCP 80/443/8060/8080/8443/9000 **全部超时/拒绝** | 目标侧对 TCP 做了丢弃/拒绝 |
| `www.fujian.gov.cn`、`scjgj.fujian.gov.cn` 均 200 | **不是**本机网络/福建区域封锁；是目标站点特有 |
| 同 IP 的 `fjis.org.cn`（省标准化研究院）同样不可达 | 整台 `220.160.53.32` 的 Web 服务对外不可达 |
| `myssl.com` 扫描同端口得到 `connection reset by peer`（二手） | 公网第三方扫描器亦被拒，非本机独有 |
| 全过程 0 字节响应，无 WAF 页面 | 不是「企业 WAF 返回 412/空包」，而是 **TCP 未建立**（与 NHC 的 WAF 情形不同） |

**结论口径**：无法区分「服务已停止（仅网关 ICMP 存活）」与「服务做 IP 白名单/内网限制」，两者都导致 **BLOCKED**。据此**不得**写任何实现计划。

### 4.4 备选路径评估

| 备选 | 可行性 | 结论 |
|------|--------|------|
| 全国标准信息公共服务平台 `dbba.sacinfo.org.cn`（已有 `dbba` 适配器） | 可达（本次 200） | DB35 题录可查，**已有覆盖**，无需新适配器 |
| 重庆平台镜像（§3.9） | 可达 | DB35/T 866 条题录可查，但**无 AttachmentUrl/全文**、数据可能滞后 |
| 福建省政府/省局站点 | 可达 | 只有通知与解读，无可检索标准库 |
| 第三方阅读/代理抓取 | 不可行 | `r.jina.ai` TLS 连接失败（exit 35）；`web_fetch` 亦 `fetch failed` |

**结论：福建站当前无可落地的适配器实现路径；DB35 的题录需求已被 dbba 覆盖，福建站独有价值仅在「福建本地全文阅览」（且二手资料显示需登录）。**

### 4.5 重新侦查条件（一次性给全，避免反复试）

满足任一即可重开 Task 0：

1. 从**福建省内网络/单位 VPN/白名单出口**复测 `curl -v http://pt.fjbz.org.cn:8060/default.aspx` 得到 200 与字节数；
2. 官方渠道公布**新域名/新端口**（现域名仍是 2013 年公布的那一个，需以省局最新答复为准）；
3. 确认服务已下线 → 直接关闭该适配器任务，DB35 需求交由 dbba 兜底。

复测清单（一次跑完即可判定）：`curl -o` 落盘 + `Content-Type`/`<meta charset>` + 搜索页表单 `method/action` + 一次搜索的 `page.on("request")` 捕获 + 空结果行为。

---

## 5. 工作量估算

| 项 | 内容 | 估算 |
|----|------|------|
| **CQ 适配器本体** | `pilotstd/query/adapters/cqis.py`（约 130–160 行，参照 dbba 体量 123 行）+ 测试 ≥7 例 + fixture 3 条 + 冒烟脚本 + 3 份文档回写 | **0.5–1 人日（4–8 h）** |
| **CQ 路由接入（必需，见 §6.4）** | v2 当前 `DB50/T 950-2026 → ['dbba']`（`std_type='DB'`），cqis 无法进入 DB 路由；需在 v2 增加省份粒度或接受 L2 兜底 | **+0.25–0.5 人日**（含路由测试） |
| CQ 可选增强 | 详情接口二次请求（补废止日期/归口/范围）→ 每命中多 1 次 POST + 限速/失败降级 | +0.25 人日（非必需，建议二期） |
| **FJ 适配器** | 当前 **0**；若 §4.5 条件满足，先 0.5 人日复测再估实现（若为 POST+ViewState 则 1–1.5 人日；若是 JSON API 则 0.5 人日） | **0 人日（不可排期）** |
| **两站合计（可交付）** | 仅 CQ（本体 + 路由） | **0.75–1.5 人日** |

> 若 Task 1 决定 cqis 只作 L2 兜底（不改 v2 路由），则 0.5–1 人日即可交付，但 `DB50` 查询默认仍由 dbba 命中、cqis 基本不会被调用 —— 需 lead 先确认目标态。

---

## 6. 下一步第一步（Task 1 起手）

**第一件事不是写 adapter，而是先冻结真实响应为 fixture 并写失败测试**（TDD，且 §6 检查清单要求「字段映射已用真实数据验证 ≥3 条」「Fixture 文件已提交」）：

1. 用 §3.4 的 curl 复现命令抓 2 类响应，落 `tests/fixtures/cqis_sample.json`：
   - `GetDB50ShareList`（`DB50/T 950` 的 2 条：现行 + 废止，覆盖状态/代替/日期）；
   - `GetPublicInfo`（样本 1 的详情，覆盖 `RevocatoryDate`/归口/范围）。
2. 写 `tests/test_cqis.py` ≥7 例并**先红**：精确命中、历史版本（废止）、模糊结果客户端过滤（`DB50/T 1` 不得误配）、空结果（`records=0`）、网络错误、编码（UTF-8 中文名）、详情补字段/不补字段两态。
3. 再实现 `pilotstd/query/adapters/cqis.py`（`_search_candidates` 走 POST + `match_result` 客户端精确过滤；`_parse_result` 按 §3.5 映射；`is_downloadable` 依 `AttachmentUrl`+状态；`hcno=BZProjectPublicId`）。
4. 注册（4 处，勿漏 v2；**v2 路由是本次最大集成风险，先实测再改**）：
   - 实测现状（本机跑 `get_route_chain`，只读）：`DB50/T 950-2026`、`DB35/T 1136-2018`、`DB50/T`、`DB50 950` → 全部 `std_type='DB'`、路由链 `['dbba']`；v2 默认启用（`ROUTING_ENGINE_VERSION` 未设 → v2）。
   - 原因：`router_v2.py:131` 的 `_STD_PREFIX_RE` 只取字母段，`DB50/T` 被归一为 `DB`；`_type_matches`（`router_v2.py:306-325`）对 `supported_types` 做精确匹配，**声明 `[DB50]` 永远不会命中** → 不要照搬「加 supported_types」的做法。
   - 可选方案（Task 1 需 lead 决策，按侵入性排序）：
     a. **L2 兜底（零路由改动）**：cqis 声明 level1=特色/level2=按标准类型区分 + `supported_types: [DB]`，仅在 dbba 无结果时被调用；交付快但基本不会被命中；
     b. **v2 省份粒度（+0.25–0.5 人日）**：`IntentParser` 对 `DB\d{2,4}(/T)?` 单独识别（如 `DB50/T`），并在 `_type_matches` 增加「省份前缀回退」，同时补路由测试（防 dbba 被误抢）；
     c. **v1 硬路由（仅当 `ROUTING_ENGINE_VERSION=v1`）**：`_constants.py:41-43` 生成的 `DB50`/`DB50/T` 链改为 `["cqis","dbba","ahbz"]` —— **默认 v2 下不生效，不能作为唯一改动**。
   - 无论选哪个：`pilotstd/query/adapters/__init__.py` + `registry.py` 必须登记；`ADAPTER_TYPE_MAP` 的 `"db"` 主适配器保持 `dbba` 不变（避免全国地标被镜像数据接管）。
5. 文档联动（G-031）：`docs/onboarding/15-query-adapter-matrix.md`、`docs/query/README.md`、`docs/reference/adapter-development.md` 架构差异表；若改了路由，还需按 AGENTS.md G-031 同步 `pilotstd/query/` 对应模块文档。
6. 验收：`python -m pytest tests/test_cqis.py -q` 全绿 + 真实站 3 条样本与 fixture 逐字段对齐 + 路由断言（目标态：`get_route_chain("DB50/T 950-2026").sites[0] == "cqis"`；兜底态：链中含 `cqis`）。
7. 同时向 lead 报 **FJ=BLOCKED 不排实现**，只登记复测条件。

---

## 7. 风险清单

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| 1 | 本站是**全国地标镜像**（33,678 条），与 dbba 数据重叠且可能滞后 | 若把 `"db"` 全局路由改到 cqis，会造成数据口径漂移 | **只让 DB50 走 cqis**；dbba 保持 `"db"` 主适配器（`ADAPTER_TYPE_MAP` 不动） |
| 2 | 列表接口 `Content-Type: text/html`（实为 JSON） | 契约不规范；未来若加 `X-Content-Type-Options`/WAF 可能影响 `resp.json()` | 用 `resp.json()` 但容错；测试锁定该行为 |
| 3 | `total` 恒 1、真实总数在 `records` | 分页写错会静默只取首页 | 分页函数只用 `records`；加 `records > len(rows)` 的 warning 日志 |
| 4 | 状态与实施日期矛盾（`现行` + 未来 `ActiveTime`，样本 3） | 「即将实施」漏判，下游下载/公告判定偏差 | 按 dbba 口径 `act_date > now → UPCOMING` |
| 5 | 列表缺 `abolition_date`/归口/范围，详情接口才有 | 不补详情则字段缺失；补详情则请求数翻倍 | 一期不补（维持默认值），二期按需 + 限速 |
| 6 | 仅 HTTP，明文传输 | 生产合规风险 | 记录在案；适配器默认无 sensitive 数据（公开标准题录） |
| 7 | 检索对空格敏感、且 `DB50/T 1` 非前缀匹配 | 直接搜完整号可能 0 结果或多结果 | 复用 `_search_progressive` 变体 + `match_result` 精确过滤 |
| 8 | DNS 瞬时失败（本次出现 1 次） | 偶发查询失败 | 复用 `safe_post`/`network.py` 重试 |
| 9 | FJ 站点不可达且原因未定 | 若后续网络放开，本文件不是其技术方案（无实测依据） | 严禁基于二手 `.aspx` 猜 ViewState；重开 Task 0 按 §4.5 复测 |
| 10 | `AttachmentUrl` PDF 是否水印版未验证 | `is_downloadable=True` 可能高估 | 二期抽样验证（本次遵守「不下载」约束未验证） |
| 11 | **v2 路由不认省份**：`DB50/T → std_type='DB'`，实测路由链 `['dbba']`，cqis 声明 `[DB50]` 永远不命中 | 适配器写完却查不到（"注册了但不可达"）——与 ttbz 的历史问题同型 | 先按 §6.4 选定方案（L2 兜底 / v2 省份粒度 / v1 硬路由）并加路由测试；验收必须断言 `get_route_chain` 链中含 cqis |
| 12 | 题录层面 dbba 已覆盖 DB50/DB35 样本，cqis 的增量主要是**全文 PDF + 更细字段** | 若 Task 1 目标仅是「查得到标准号/名称/状态」，新建适配器收益低 | 立项前确认目标；若目标是全文/废止日期/备案号，则 cqis 值得建（§3.10） |

---

## 8. 证据与复现清单（全部在仓库外）

探针脚本（`C:\Temp\`）：`probe_cq_fj.py`（通用 URL 探测）、`probe_cq_api.py`（编码变体）、`probe_cq_api2.py`、`probe_cq_samples.py`（样本）、`probe_cq_extra.py`（详情/rows/HTTPS）、`probe_cq_filters.py`（检索语义）、`probe_cq_final.py`（镜像/状态分布）、`probe_cq_detail.py`（详情接口）、`probe_cq_headers.py`（头依赖）、`recon_playwright.py`（两阶段侦查）、`parse_fj_scjgj.py`。

原始响应（`C:\Temp\cqfj_probe\`）：
- `http_db_cqis_cn_.bin`（首页 58,229 B）、`cq_search.html`（检索页 59,175 B）、`cq_search2.html`、`pager.js.txt`（分页 JS 反混淆）、`cq_details.html`（详情页 36,721 B）
- `cq_samples_utf8.txt`（4 条真实样本全字段）、`cq_detail_api_utf8.txt`（详情 API 全字段）、`cq_extra_utf8.txt`（详情/rows/HTTPS）、`cq_filters_utf8.txt`（检索语义）、`cq_final_utf8.txt`（全国镜像/状态分布）、`cq_header_deps_utf8.txt`（无头请求 200 证据）
- `playwright_recon_utf8.txt`（CQ 捕获的 XHR + FJ `ERR_CONNECTION_TIMED_OUT`）

最小复现命令（复制即可）：

```bash
# CQ 列表
curl -s -X POST "http://db.cqis.cn/LocalStandard/GetDB50ShareList" \
  --data-urlencode 'queryJson={"FinishCode":"DB50/T 950","BZName":"","SourceName":"","ClassificationIndustry":"","StandardCategory":"","OtherCategory":""}' \
  --data "page=1&rows=15"

# CQ 详情
curl -s -X POST "http://db.cqis.cn/LocalStandard/GetPublicInfo" \
  --data "keyValue=dba6c814-91c0-483d-a691-2f08a3029833"

# FJ 不可达证据（预期 exit 28 / 0 B）
curl -sv --connect-timeout 15 "http://pt.fjbz.org.cn:8060/StandardSearch/StdSearch.aspx"
```

---

## 附录 A：CQ 响应字段全清单（实测）

列表 `rows[]` 键：`BZProjectPublicId, Project_FinishCODE, FinishCode(null), FilingNumber, BZName, ReplaceStandardNumber, BatchMonth, Batch, Keyword, SourceName, StandardDepartment, PV, DownloadPV, ReleaseTime, ActiveTime, SortCode, DeleteMark, ReleaseStatus, ReviewStatus, ReviewAdvice, ReviewAdviceTime, ReviewTime, ReviewConfirmTime, Description, IsImport, AttachmentUrl, CreateDate, CreateUserId, CreateUserName, ModifyDate, ModifyUserId, ModifyUserName, WatermarkDocUrl, ICSNum, ICSName, CCSNum, CCSName, ProposeCompany, UnderCompany, CompetentDepartment, DraftCompany, FirstDraftCompany, DraftPerson, FirstDraftPerson, RevocatoryDate, ScopeApplication, ClassificationIndustry, StandardCategory, OtherCategory, ClassificationIndustryName, StandardCategoryName, OtherTargetName, IsSelf, PreviewNum, DownloadNum`（列表实测不含 ICSName/CCSName 等少数字段，详情接口齐全）。

顶层键：`rows / draftCompanyList / draftPersonList / total / page / records`。

`draftCompanyList[]`：`DraftCompanyId, DraftCompanyName`；`draftPersonList[]`：`RecordId, BZProjectPublicId, DraftPersonName, DraftCompanyId, Idx, TotalNum`。
