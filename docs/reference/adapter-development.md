# 适配器开发指南

## 站点架构差异表（Q22 系列实战总结）

五个站点，五种完全不同的技术架构。没有任何两个可以复用同一套解析策略。

| 适配器 | 站点 | 架构类型 | 核心特征 | 编码 | 分页 | 测试 |
|--------|------|----------|---------|------|------|------|
| TTBZ | 团体标准平台 | JSON API (POST) | JSON 直连，结构化程度最高 | UTF-8 | POST pageNum | 10 |
| MEE | 生态环境部 | HTML key-value `<li>` 列表 | 政务 CMS，分类过滤+正则提取标准号 | UTF-8 | GET page | 10 |
| NRSIS | 自然资源标准平台 | HTML 表格 | Portal 框架内嵌，GBK 编码，首列数字检测 | GBK | GET pageNo | 12 |
| JTST | 交通运输部 | iframe 卡片 HTML | Hash 路由门户内嵌，卡片式解析 | UTF-8 | GET iframe | 12 |
| CCSN | 工程建设标准化协会 | ViewState 分页 | WebForms 混合模式，双表格干扰 | GBK | POST btnNext | 10 |
| JJG | 国家计量技术规范 | JSON API (GET) | 隐藏 API 端点，纯结构化数据 | UTF-8 | GET pageNum | 9 |
| SPPT | 食品安全国标 (8086) | JSON 数组过滤 | 自签名 SSL，混合公告/标准需过滤 CODE | UTF-8 | 无需 | 8 |
| SPPT_Local | 食品安全地标 (8087) | Vue dataList 嵌入 | SSR HTML 内嵌 JSON，正则提取+省份映射 | UTF-8 | 无(仅首页) | 9 |
| GongBiaoKu | 工标库 | HTML key-value `<ul>` 分组 | 每 ul 4 个 li 键值对，正则提取标签前缀 | UTF-8 | 无(单页) | 9 |
| Energy | 能源标准信息服务平台 | JSON API (GET) | 纯 IP + 自签名证书，Bootstrap Table AJAX 加载，Host Header 显式声明 | UTF-8 | GET limit/offset | 13 |
| TDPress | 铁路标准信息服务平台 | JSON API (GET) | jQuery EasyUI，GET 请求，TRUE/FALSE 状态映射，毫秒时间戳 | UTF-8 | GET page/rows | 17 |
| NCHA | 文物保护标准平台 | JSON API (POST) | 微服务架构（API 在 9005 端口），itemCode 分类过滤，非标日期格式 | UTF-8 | POST currentPage/pageSize | 16 |

**合计：12 种架构，139 个测试，零复用。**

## 核心原则

### 1. 永远不要根据域名/后缀猜测技术栈

- `.aspx` 不等于 POST 表单搜索（CCSN 实际是 GET `?KeyWord=`）
- `#/` 不等于 SPA（JJG 的 `#` 仅为锚点，实际是纯 SSR + 隐藏 JSON API）
- 深层路径不等于静态页
- HTML 页面不等于无 API（JJG 的 JSON API 隐藏在 SSR 页面之下）
- 每个政府/协会站点是独立历史产物，必须逐个逆向

### 2. Task 0 是不可压缩的

6 个适配器中 **5 个的计划假设被 Task 0 部分或完全推翻**。跳过 Task 0 的代价是 100% 返工。

典型案例——Q22-05 CCSN：

| 计划假设 | 实际 | 后果 |
|----------|------|------|
| POST + ViewState 搜索 | GET `?KeyWord=` | 请求永远失败 |
| `__EVENTVALIDATION` 存在 | 不存在 | 参数缺失报错 |
| 标准编号在列 0 | 在列 2 | 解析到表头文字 |
| 有状态列 | 无 | 字段为空 |
| `__EVENTARGUMENT=Page$2` | `btnNext` 顺序翻页 | 分页跳转失败 |

### 3. 先找真实 API，再定方案

执行顺序：
1. 浏览器打开目标页面，F12 → Network → XHR/Fetch
2. 找到真实数据接口（可能是 iframe、AJAX、JS 跳转）
3. curl 验证接口可达性
4. 根据**实际**接口写计划
5. 根据计划写测试 → 实现

禁止：看一眼 URL → 脑补技术栈 → 写代码

### 4. 编码检测

- 先 `curl -o` 保存为二进制
- 检查 `<meta charset>` 或响应头 `Content-Type`
- 常见：UTF-8（多数）、GBK（老旧政府站）
- 不要假设 UTF-8

### 5. 新增适配器标准流程（4 步，FIX-20260724-002 生效）

新增一个查询适配器只需以下 4 步。**系统自动识别，无需修改任何硬编码列表或前端代码。**

```
1. 创建 pilotstd/query/adapters/new_site.py
   - 继承 BaseAdapter，实现 site_name/site_label/_search/_parse_result
   - 定义模块级常量 DISPLAY_NAME = "新站点中文名"（≤50 字符）
   - DISPLAY_NAME 会被 API 自动暴露为 display_name 字段，前端自动显示

2. 在 ADAPTER_TYPE_MAP 注册路由（search_strategy.py）
   - 若为标准代号前缀（如 WW/T），添加入口到对应类型的 chain
   - 若为新类型，添加 {"primary": "new_site", "fallback": "std_gov"}

3. 在 PROD_PRIORITY 注册优先级（engine/_constants.py）
   - 在合适位置插入 "new_site"

4. 创建测试 + fixture + 冒烟脚本
   - tests/test_new_site.py（≥7 用例）
   - tests/fixtures/new_site_sample.json
   - scripts/smoke_test_new_site.py
```

**不再需要**：修改 `docker/api/adapter.py`、前端 `fullName()`、`_ALL_ADAPTER_NAMES`、`target_names` 或任何其他硬编码列表。`/api/adapter/status` 自动纳入新适配器，首页集群卡片自动显示其中文名。

### 6. 新适配器检查清单（Task 0 侦查）

- [ ] 真实 API 端点已 curl 验证
- [ ] 编码已确认（非假设）
- [ ] 搜索结果 DOM 结构已截图/保存
- [ ] 字段映射已用真实数据验证（≥3 条采样）
- [ ] 分页机制已确认（GET/POST/iframe/ViewState）
- [ ] 空结果行为已测试
- [ ] 特殊参数已记录（tid/channelid/op/repeFlag）
- [ ] Fixture 文件已提交

### 7. 纯 IP 站点对接范式（Q22-10 Energy 实战总结）

政府/国企内部标准平台常见部署在纯 IP（无域名）的 HTTPS 服务器上，使用自签名证书。此类站点的对接要点：

**协议探测**
- 先尝试 `https://`。若 HTTP 返回 400 "plain HTTP request was sent to HTTPS port"，即确认 HTTPS。
- 自签名证书需 `verify=False`（httpx）或 `verify=False`（requests）。

**Host Header 显式声明**
- 纯 IP 站点的 Host 头必须为 `IP:Port`，否则反向代理可能路由失败。
- 在 httpx.Client 初始化时显式设置 `headers={"Host": "IP:Port"}`。

**AJAX 端点发现**
- Bootstrap Table 页面通常是空壳 `<table>`，数据由 JS 异步加载。
- 搜索页面源码中的 `bootstrapTable({url: ...})` 调用，找到真实 AJAX 端点。
- `queryParams` 函数定义了附加参数（如 `tid`、`op`），需一并传递。

**Energy 站点 AJAX 接口规格（可复用范式）**

```
GET https://114.251.111.103:18080/zxd/portal/stdPage
  ?keyword=<关键词>
  &tid=0              # 标准分类 ID（0=全部）
  &op=                # 操作类型（留空）
  &limit=15           # 每页条数（Bootstrap Table server-side pagination）
  &offset=0           # 偏移量

响应:
{
  "total": 19,        # 总条数（用于分页判断）
  "rows": [{
    "stdCode": "NB/T 10456-2021",   # 标准编号
    "stdId": 116255,                 # 内部 ID
    "replacedStd": "NB/T ...",       # 代替标准（null 表示无）
    "stdName": "标准名称",           # 标准名称
    "state": "现行",                 # 状态（现行/废止）
    "issueDate": "2021-07-01",       # 发布日期
    "actDate": "2021-10-01"          # 实施日期
  }]
}
```

**分页兜底**
- 当前 `limit=15`，若 `total > len(rows)` 表示有未拉取的结果页。
- 建议在 `_fetch_candidates` 中增加 `total` 与 `len(rows)` 的比对 warning 日志。
- 完整分页需循环 `offset += limit` 直到 `offset >= total`。

### 8. NCHA 文物保护标准 — 微服务端口注意事项

- **API 端口 9005**：后端 API 部署在 9005 端口（非标准 80/443），80 端口仅提供 Vue SPA 静态资源。
- **运维风险**：防火墙策略变更可能阻断 9005 端口访问。建议在生产环境监控中加入 `tcping bz.ncha.gov.cn:9005` 连通性探针。
- **WW 路由修正**：`classify_std_code("WW")` 返回 `"industry"` 而非 `"cultural"`，导致通用路由层无法自动匹配 ncha。已在 `CODE_ROUTES` 中添加 `"WW": ["ncha", "std_gov"]` 和 `"WW/T": ["ncha", "std_gov"]` 硬路由。未来若新增其他行业代号的专业站点，需注意 `classify_std_code` 的返回值与 `ADAPTER_TYPE_MAP` 的匹配关系。

### 9. 站点侦查方法论（Q23 五站实战总结）

**curl 探测 → Playwright 侦查的两阶段模型**：

| 阶段 | 工具 | 目标 | 耗时 |
|------|------|------|------|
| 第一阶段 | curl/httpx | 页面可达性、协议、SSL、响应头 | 2 分钟/站 |
| 第二阶段 | Playwright | XHR 捕获、JSL 绕过、API 端点发现 | 5-10 分钟/站 |

**核心发现**：JSL/CDN 反爬仅保护页面加载，不保护 API 端点。Playwright 的核心价值不是"绕过反爬"，而是"在执行 JS 的过程中自动触发 API 调用，暴露端点 URL"。

**Playwright 侦查模板**：

```python
# 1. 页面加载 + on_response 监听
page.on("response", lambda r: capture_if_json(r))
page.goto(url)

# 2. 自动触发搜索（暴露 XHR 端点）
page.fill('input[placeholder*="标准"]', "GB/T")
page.click('button:has-text("搜索")')

# 3. 导出 Cookies + 捕获的 API 列表
# 4. curl 独立复现验证（关键步骤——确认 API 脱离浏览器可用）
```

**五站侦查结论**：

| 站点 | 第一阶段 | 第二阶段 | 最终 |
|------|---------|---------|------|
| cssn.net.cn | JSL 壳 (527B) | Playwright 自动触发 API | VIABLE |
| miit.gov.cn | JSL + Vue SPA | Playwright 捕获 XHR | VIABLE |
| nhc.gov.cn | 412 WAF | Playwright 仍被阻断 | **BLOCKED** |
| ncha.gov.cn | Vue SPA 壳 | Playwright 发现 9005 端口 | VIABLE |
| tdpress.com | jQuery EasyUI | curl 即可用 | VIABLE |

**放弃标准**（满足任一即放弃）：
- Playwright headless 仍返回空响应或 WAF 页面
- 搜索 API 需要登录/付费/验证码
- DNS 不存在且无替代域名

**NHC 卫健委是唯一触发放弃标准的站点**（企业级 WAF 检测 TLS 指纹，39 字节空响应）。
