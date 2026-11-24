# P2 既有适配器「做足」评估：`ttbz` / `energy`（只读摸底）

| 项目 | 值 |
|------|-----|
| 任务包 | P2「已有适配器，评估质量是否满足『做足』要求」 |
| 日期 | 2026-11-24 |
| 性质 | **只读评估**；不改代码/配置/其它文档，不提交 |
| 评估对象 | `pilotstd/query/adapters/ttbz.py`（198 行 / 167 非空）、`pilotstd/query/adapters/energy.py`（205 行 / 171 非空） |
| 对照基线 | `base.py` 契约、`iso_gov.py`（国际站 JSON）、`std_gov.py`（国标 HTML）、`tdpress.py`（JSON 翻页）、`ncha.py`（JSON POST） |
| 证据方式 | 代码/测试/文档阅读 + 本机只读探针（`C:\Temp\p2_eval_probe*.py`，仓库外） + 实际跑测试；**未联网**，联网项标注「需实测」 |
| 结论一句话 | 两者代码层都达到「B 小缺口」；但**在默认 v2 路由下 `ttbz` 自动路由全链路不可达、`energy` 单条查询路径不可达**（§4），叠加 `ttbz` 无真实 fixture / 无冒烟脚本、`energy` 冒烟脚本本身会崩，端到端「做足」评级：**TTBZ=C（明显不足）、Energy=B（小缺口）**。 |

> 已查阅（文档依据，非记忆）：
> - `docs/reference/adapter-development.md` §5「新增适配器标准流程（4 步）」、§6「检查清单」、§7「纯 IP 站点对接范式」、§9「侦查方法论」
> - `docs/onboarding/15-query-adapter-matrix.md`（逐站能力矩阵；第 13/28/39/54 行）、`docs/adapters/README.md`（第 29/32/48-49 行）
> - `docs/architecture/modules/query.md` §适配器错误必须可区分（第 226-237 行）、§行数口径（第 51-54 行）
> - `docs/reference/fixture-schema.md`（fixture 规范，第 26-39 行）
> - `docs/query/README.md` §v2 路由（第 45-61 行）、§22 个适配器摘要（第 219 行）
> - `docs/onboarding/08-known-boundaries.md` §14「下载只有 `openstd_download`；非 GB 无适配器」（第 420-444 行）
> - `docs/debt/06-full-inventory.md` NEW-12/NEW-13（第 148-149 行）
>
> 实测证据（可复现）：`C:\Temp\p2_eval_probe.py` / `probe2.py` / `probe3.py`；测试命令与输出见 §10。

---

## 1. 评估口径

「做足」按 `adapter-development.md` §5（4 步：适配器文件 / 路由注册 / 优先级注册 / 测试+fixture+冒烟）与 §6（8 项 Task 0 检查清单）拆成 6 个维度，每维给出 `文件:行` 证据：

| 维度 | 判据 |
|------|------|
| 1 契约完整性 | `site_name`/`site_label`/`DISPLAY_NAME`/`_search`/`_parse_result` 齐全且签名兼容 `BaseAdapter`（`base.py:39-51, 75-87, 212-217`） |
| 2 字段覆盖 | 15 个 `QueryResult` 字段（`models.py:9-31`）中站点真实可得的字段是否映射；缺字段的业务后果 |
| 3 分页与覆盖度 | 能否翻完 / 是否有静默截断；空结果与异常路径 |
| 4 健壮性 | 超时/重试/编码/反爬/错误可区分（NEW-12/13，`query.md:226-237`） |
| 5 测试覆盖 | 用例数、真实响应 fixture、空结果、异常分支、冒烟脚本 |
| 6 注册一致性 | `registry.py` / `site_config` / `ADAPTER_TYPE_MAP` / 优先级链 / **v2 能力模型** 是否真能路由到 |

> 注：`PROD_PRIORITY` 已不存在——现为 `engine/_constants.py` 的 `_DEFAULT_FALLBACK_CHAIN`（第 16-20 行）+ `ADAPTER_TYPE_MAP`（`search_strategy.py:279-321`）+ v2 `config/site_capabilities.yaml`。`adapter-development.md` §5 第 3 步仍写 `PROD_PRIORITY`，属**文档过期**（§8 文档漂移）。

---

## 2. `ttbz`（全国团体标准信息平台，POST JSON）

### 2.1 契约完整性 — **A（齐全）**

| 契约项 | 证据 | 结论 |
|--------|------|------|
| `site_name` | `ttbz.py:55-57` → `"ttbz"` | ✅ |
| `site_label` | `ttbz.py:59-61` | ✅ |
| `DISPLAY_NAME` | `ttbz.py:21`（6 字，≤50） | ✅ |
| `_search` | `ttbz.py:131-142`，签名与 `base.py:75` 一致 | ✅ |
| `_parse_result` | `ttbz.py:148-197` | ✅ |
| `get_search_url()` | 走 site_config：`site_config/_sites.py:69-77` 有 `search_url` | ✅ |

小瑕疵（非缺陷）：`_search` 与基类 `base.py:75-87` 语义重复（精确匹配优先→取最新发布），且**未调用 `_post_process_result` 钩子**；但本适配器未重写该钩子（全库仅 `csres/hbba/njbz365` 重写，见 `adapters/*.py` 的 `def _post_process_result`），当前**无行为差**，属可维护性问题。

### 2.2 字段覆盖 — **B（缺替代关系/原文入口，无致命项）**

| 字段 | 证据 | 结论 / 业务后果 |
|------|------|----------------|
| 标准号 / 名称 | `ttbz.py:155-156, 185-186` | ✅ |
| 状态 | `ttbz.py:158, 166-172`（`现行/即将实施/废止` 归一，其它值原样保留） | ✅ `被代替` 等合法值透传，测试 `test_parse_result_unknown_status_preserved` 覆盖 |
| 发布日期 / 实施日期 | `ttbz.py:163-164, 189-190` | ✅ 字符串直传；**未校验格式**，若站点返回非 `YYYY-MM-DD`，`is_recently_published` 的 `strptime("%Y-%m-%d")` 会返回 False（`search_strategy.py:330-335`），影响“新发布可下载”判断（需实测） |
| 归口单位 | `ttbz.py:161, 191`（`organName`） | ✅ |
| 站点详情 ID | `ttbz.py:160, 193`（`standardUniqueId`→`hcno`） | ✅ 但**无消费方**（下载侧只映射 `std_gov`，`download/engine.py:424-426`） |
| **替代关系** | 全文件无 `replaces`（`_parse_result` 返回体 `ttbz.py:184-194` 未赋值） | ❌ **缺**。业务后果：`classifier.py:98` 写空 `found_replaces` → `pipeline/router.py:98-110` 对废止/被代替标准只走 `organize`、不会走 `manual_download` 追踪替代版本；UI 第 5 列恒空（`ui/main_window/parts/_query_ops.py:36`）。API 是否返回该字段**需实测**（§9） |
| **废止日期** | 未显式赋值，落到默认值 `"网站无此分类"`（`models.py:24`） | ⚠️ 会被 `classifier.py:105` 原样写入 `found_abolition_date`（全站默认值语义，非本适配器特有） |
| 采标判定 | 恒 False（未赋值，`models.py:19` 默认）；测试 `test_parse_result_is_adopted_false` 锁定该行为 | ⚠️ 团体标准一般非采标，风险低；但若平台数据含采标 T/ 标准会漏判 |
| 原文链接 / 附件 | `QueryResult` **无 URL/附件字段**（`models.py:9-31`） | 全库性能力缺口，非本适配器特有；`standardUniqueId` 已具备拼详情页的前提，但未实现（详情页 URL 形态需实测） |
| 拆分部分 `split_into` | 未调用 `BaseAdapter._detect_split_parts`（`base.py:260-279`） | ⚠️ 多部分标准（`T/XXX 123.1-2024`）不标记，与全库多数适配器一致 |

### 2.3 分页与覆盖度 — **C（只取首页 20 条，且无截断告警）**

- `query_standards(..., pageNo=1, pageSize=20)`（`ttbz.py:80-84`）**支持**翻页参数，但引擎层入口 `_search` 固定只调 `query_standards(search_term)`，即**永远第 1 页 20 条**（`ttbz.py:133`）。
- 未重写 `_search_candidates`（基类默认返单条候选，`base.py:212-217`），因此 `query_with_strategy` 第 5 步“代号变体”搜索同样只拿首页（`base.py:171-199`）。
- 响应里其实有 `data.total`（测试 mock 即含，`tests/test_adapters.py:424-426`），但**未做 `total > len(rows)` 截断告警**——对比 energy 已有告警（`energy.py:163-171`）。
- 业务后果：按完整标准号精确搜索通常 1 页内命中，风险小；但关键词/同名多版/变体搜索会**静默截断**，且运维无法从日志发现。空结果 `[]` 与异常 `[]` 同形（`ttbz.py:113-125`），只能靠日志区分（可接受，全库口径）。

### 2.4 健壮性 — **B（重试/告警齐，仅日志可区分错误）**

| 项 | 证据 | 结论 |
|----|------|------|
| 超时 | `timeout=15`（`ttbz.py:105`），网络层默认 15s（`network.py:17`） | ✅ |
| 重试 | 复用 `safe_post`：502/503/504 与超时/连接重置重试 1 次（`network.py:14-17, 112-136`） | ✅ |
| HTTP 错误日志 | `>=400` 由 `safe_post` 打 warning（`network.py:120-122`）；适配器外层异常保持 debug 并注释分工（`ttbz.py:108-112`），符合 U34-B 口径（`query.md:87`） | ✅ |
| JSON 解析失败 | warning 并返回空（`ttbz.py:116-121`），符合 NEW-13 类要求 | ✅ 但**无测试**（见 2.5） |
| 编码 | JSON 直连（`resp.json()`），UTF-8，无 GBK 风险（`adapter-development.md:9`） | ✅ |
| 反爬 | 显式 UA / `X-Requested-With` / `Referer`（`ttbz.py:40-53`） | ✅ 基础头齐全；是否有 WAF 需实测 |
| 错误可区分 | 日志可区分（warning 文案），但**调用方拿到的都是 `[]`/`None`**，与“无结果”不可区分 | ⚠️ 全库普遍口径（NEW-12/13 只要求日志可区分），非本适配器独有 |
| 资源 | `requests.Session` 由 registry `instantiate_all()` 长期持有（`registry.py:57-77`），不随请求关；符合 NEW-36 对“长驻适配器”的豁免 | ✅ |

### 2.5 测试覆盖 — **C（15 用例全绿，但无真实 fixture / 无冒烟 / 缺关键分支）**

- 用例：`tests/test_adapters.py::TestTTBZAdapter` **14 例**（第 453-612 行）+ 日志级别契约 **1 例**（`tests/query/adapters/test_adapter_log_levels.py:264-277`）= **15 例**；实测全绿（§10）。
- 覆盖到：字段映射 6 例、`_search` 3 例（精确/无结果/500）、`query_standards` 5 例（列表/空关键词/超时/kwargs/headers）。
- **未覆盖**：
  1. JSON 解析失败分支（`ttbz.py:118-121`）——`test_search_network_error` 用 `status=500` 提前 return，`json.side_effect` 根本到不了；
  2. 分页（`pageNo>1`）与 `total>pageSize` 截断；
  3. **没有 fixture**：`tests/fixtures/` 无 `ttbz_*`，`tests/fixture_baseline.py:37-53` 未登记；测试数据全部由 `_ttbz_row()` 手工合成（`tests/test_adapters.py:420-450`）——无法充当“API 改版哨兵”，违反 §6「字段映射已用真实数据验证 ≥3 条」与 §5 第 4 步；
  4. **无冒烟脚本**：`scripts/` 下只有 `smoke_test_{cssn,energy,miit,ncha,tdpress}.py`，无 `smoke_test_ttbz.py`（§5 第 4 步明确要求）。
- 文档 §表格写 TTBZ「10 个测试」（`adapter-development.md:9`），实际 15，**文档数字过期**。

### 2.6 注册一致性 — **D（代码登记齐全，但默认 v2 路由不可达 → 实际不可用）**

登记部分全部正确：

| 注册点 | 证据 |
|--------|------|
| 注册表 | `registry.py:27, 53`；`adapters/__init__.py:22` |
| 站点配置 | `site_config/_sites.py:69-77`（`search_url` 正确、`max_requests=100/daily=400`） |
| 画像 | `site_config/_profiles.py:262-273`（medium/50/primary，`std_prefixes=["T/"]`） |
| 硬编码路由 | `search_strategy.py:302` `"group": {"primary":"ttbz", fallback:"ahbz"}`，`classify_std_code("T/CAS")=="group"`（`std_utils.py:146-148`） |
| v1 评分链 | 实测 `get_priority_chain("T/CIESC")` 首位 = `ttbz`（§10 probe3） |

**但默认 v2 路由不命中（不可用级，详见 §4）**：
- `_single.py:272` 用 `target`（如 `"T/CIESC 001-2019"`）调 `get_route_chain`；v2 意图解析正则 `router_v2.py:131` 要求 **2-6 个字母**开头，`T/...` 只 1 个字母 → `std_type=None` → 判为纯关键词（`router_v2.py:148-155`）→ 只走 L3 全综合站（`router_v2.py:264-266, 323-335`）。
- `ttbz` 在能力模型里是 `level1=特色 / level2=按标准类型区分`（`config/site_capabilities.yaml:156-169`），**不进 L2/L3**；而 `supported_types: ["T/"]` 又永远匹配不到（L1 是精确 `in` 比较，`router_v2.py:293`）。
- 实测：`get_route_chain("T/CIESC")` 与 `get_route_chain("T/CIESC 001-2019")` 均 = **`['njbz365']`**（§10）。
- 批量路径同理：分桶键取 `logical_code`（`_batch_dispatcher.py:178-179` → `_bucket_key` → `_get_priority`），`"T/CIESC"` 同样落到 `njbz365`。
- 只有**手动指定站点**（`preferred_site`，`_single.py:203-207` 绕过 v2）或 `ROUTING_ENGINE_VERSION=v1` 回滚后才走 `ttbz`。
- 健康探针会“骗人”：`health_probe.py:138-141` 对声明了 `query_standards` 的适配器**直接调适配器**，不经路由 → 可能报 `found`，掩盖路由死链。

### 2.7 评级与最大缺口

**综合评级：C（明显不足）**——代码本身 B，端到端因路由不可达降为 C。

| # | 缺口 | 证据 | 影响 |
|---|------|------|------|
| 1 | 默认 v2 路由永不选中 `ttbz`（T/ 标准全链路） | `router_v2.py:131,293` + `site_capabilities.yaml:156-169` + `_single.py:272` + 实测 | **不可用级**：团体标准查询落到 `njbz365` 兜底，命中率与字段质量双降 |
| 2 | 无真实响应 fixture / 无冒烟脚本，API 契约（含 `standardName` 是否支持按编号搜、`replaces` 是否存在）从未用真数据验证 | `tests/test_adapters.py:420-450`；`fixture_baseline.py:37-53`；`scripts/` 无 ttbz 冒烟 | 站点改版/字段变更无法被测试发现；违反 §5/§6 |
| 3 | 分页只取首页 20 条且无截断告警；缺 `replaces` 字段 | `ttbz.py:82,133`；`ttbz.py:184-194` | 同名/关键词搜索静默漏检；废止标准无替代关系，路由不追踪新版 |

---

## 3. `energy`（能源标准信息服务平台，GET JSON Bootstrap Table）

### 3.1 契约完整性 — **A（齐全）**

| 契约项 | 证据 | 结论 |
|--------|------|------|
| `site_name` | `energy.py:50-52` | ✅ |
| `site_label` | `energy.py:54-56` | ✅ |
| `DISPLAY_NAME` | `energy.py:21` | ✅ |
| `_search` | 未重写，走基类 `base.py:75-87` → `_search_candidates`（`energy.py:66-80`） | ✅ 符合基类扩展点设计 |
| `_parse_result` | `energy.py:175-205` | ✅ |
| `get_search_url()` | 走 site_config：`site_config/_sites.py:173-185`（含 `probe_params`，见 ADR-013） | ✅ |

小瑕疵：`query_standards(standard_number, **kwargs)` **完全忽略 `**kwargs`**（`energy.py:60-62`），而同层 `ttbz.py:65,86-96` 支持 `organName/日期` 等过滤参数——公共接口契约不一致（无业务后果，仅扩展性差）。

### 3.2 字段覆盖 — **B（比 TTBZ 完整，`replaces` 已有）**

| 字段 | 证据 | 结论 |
|------|------|------|
| 标准号 / 名称 | `energy.py:177-178, 195-196` | ✅ |
| 状态 | `energy.py:179, 197`（`map_status` 通用表，含现行/即将实施/废止/被代替，`search_strategy.py:214-243`） | ✅ |
| 发布/实施日期 | `energy.py:180-181, 199-200`（`issueDate/actDate`，文档 §7 已给真实规格） | ✅ |
| **替代关系** | `energy.py:182, 201`（`replacedStd`，`null`→`""`） | ✅ **21 站中较完整**（对比 ttbz 缺） |
| 站点详情 ID | `energy.py:183, 204`（`stdId`→`hcno`） | ✅ 无消费方（非 GB 无下载适配器，`08-known-boundaries.md:420-444`） |
| 归口单位 | **硬编码 `""`**（`energy.py:202`） | ⚠️ API 规格（`adapter-development.md:129-141`）无该字段，可接受；如站点实际返回需实测补 |
| 废止日期 | 未显式，落默认 `"网站无此分类"`（`models.py:24`） | ⚠️ 同全库默认值口径 |
| 采标判定 | 未赋值（仅靠 `_single.py:333` 的 `"采标" in status` 兜底） | ⚠️ `state` 一般不含“采标”，漏判风险低 |
| 原文链接 / 附件 | `QueryResult` 无该字段；`stdId` 未拼详情页 URL | 全库性缺口；详情页 URL 形态需实测 |
| 拆分部分 | 未检测（`base.py:260-279` 未用） | ⚠️ 同上 |

### 3.3 分页与覆盖度 — **B（有循环+告警，但封顶 75 条、缺页降级不完整）**

- 循环：`for page in range(MAX_PAGES)`，`offset = page*PAGE_SIZE`（`energy.py:90-99`）；`MAX_PAGES=5 / PAGE_SIZE=15`（第 90-91 行）。
- 终止条件：`total<=PAGE_SIZE` 或 `len(all_rows)>=total_seen` 或本页不足 15 条（`energy.py:150-158`）。
- 未拉完先 `warning` 再返回已取数据（`energy.py:163-171`）——**明显优于 TTBZ**，与文档 §7「分页兜底」要求一致（`adapter-development.md:144-147`）。
- 缺陷：
  1. `limit` 变量恒等于 `PAGE_SIZE`（`energy.py:95,99`），冗余写法；
  2. `total` 缺失时 `total_seen=0 → <=PAGE_SIZE` 立即 break（`energy.py:152-154`），站点改版去掉 `total` 会**静默只取首页**；
  3. 第 2 页起只用主链接、无 fallback（`energy.py:101-105`），单次抖动即提前结束（有 warning，不静默）；
  4. 75 条硬上限，超出仅告警不扩页——单标准号查询几乎不会触发，关键词查询会截断。

### 3.4 健壮性 — **B（NEW-12/13 已修；IP/证书/备用域名有隐患）**

| 项 | 证据 | 结论 |
|----|------|------|
| NEW-12（fallback 吞异常） | 记录 `last_exc` 并在首页失败 warning 里带 `类型: 异常`（`energy.py:107-127`）；契约测试 `test_adapter_log_levels.py:280-285` | ✅ 已修 |
| NEW-13（JSON 失败静默） | warning 明确“可能是 HTML 错误页”后 break（`energy.py:136-142`）；契约测试 `test_c2_log_levels.py:339-345` | ✅ 已修 |
| 超时 | `httpx.Client(timeout=15.0)`（`energy.py:34`） | ✅ |
| 重试 | ❌ 无：页 0 靠 3 个 URL 轮询，页 ≥1 单 URL 单次 | ⚠️ 临时抖动即放弃后续页（有 warning） |
| 自签名证书 | `verify=False`（`energy.py:35`，注释“已评估”） | ⚠️ 已知接受的风险（`query.md:121` 列为刻意豁免） |
| Host 头固定 | `{"Host": "114.251.111.103:18080"}`（`energy.py:36-37`） | ⚠️ 与 `FALLBACK_URLS` 矛盾：备用域名 `https://energy.nbse.org.cn:18080`（第 88 行，注释“待验证”）即使可达，Host 仍是旧 IP → 反向代理无法正确路由，**fallback 名存实亡** |
| 备用 URL 质量 | 第 87 行 `http://...`（HTTP 降级）、第 88 行未验证域名 | ⚠️ 生产代码里带“待验证”域名（`docs/adapters/README.md:48-49` 也标注待验证）；且 `verify=False` 下域名归属无法用证书校验，存在数据来源风险 |
| 编码 | JSON 直连，UTF-8 | ✅ |
| 错误可区分 | 日志按 NEW-12/13 可区分；`QueryResult` 层仍 `[]`/`None` 同形 | ⚠️ 全库口径 |
| 纯 IP 迁移风险 | 模块头注释已提示（`energy.py:6-8`），文档列为每周验证项（`docs/adapters/README.md:48`） | ⚠️ 已知风险 |

### 3.5 测试覆盖 — **B（18 个相关用例，但核心翻页/解析失败未测，fixture 疑似手工）**

- 用例：`tests/test_energy.py` **14 例**（第 17-194 行）+ 日志级别 1 例（`test_adapter_log_levels.py:280-285`）+ 死分支源码断言 1 例（`test_c2_log_levels.py:339-345`）+ 健康探活 2 例（`test_health_check_service.py:134-149,211-218`）≈ **18 例**；实测全绿（§10）。
- 覆盖到：fixture 解析、全字段映射、缺字段、空记录、候选列表、无结果、网络异常、非 200、空关键词、Host 头、自定义 client、年份回退、翻页不完整告警。
- **未覆盖**（关键）：
  1. **多页翻页成功路径**——现有 fixture `total=3`（`tests/fixtures/energy_sample.json:2`），所有用例都因 `total<=15` 在第 1 页 break，第 2 页循环体（offset 递增、`len(rows)<PAGE_SIZE` 判断）从未执行；
  2. JSON 解析失败（HTML 错误页）分支（`energy.py:136-142`）；
  3. fallback URL 成功路径（第 86-89 行轮询）；
  4. 页 ≥1 失败返回部分数据（`energy.py:128-134`）。
- fixture 真实性：`energy_sample.json` 3 条（`stdId` 10001/10002/10003、名称如“能源管理系统技术规范”）看起来是**手工构造**，且 `fixture-schema.md:39` 只登记“3 条/日期为字符串”，无抓包日期/来源——不能承担“API 变更哨兵”职责（是否真实需实测确认）。
- **冒烟脚本存在但当前必崩**：`scripts/smoke_test_energy.py:33` 打印 `adapter.API_URL`，而 `EnergyAdapter` 只有 `BASE_URL`（`energy.py:29`），实测 `hasattr(EnergyAdapter, "API_URL") == False` → 该脚本在第一步就 `AttributeError`，**需实测的入口本身不可用**。

### 3.6 注册一致性 — **C（批量路径可达、单条路径不可达；`ADAPTER_TYPE_MAP["energy"]` 对路由无效）**

| 注册点 | 证据 | 结论 |
|--------|------|------|
| 注册表 | `registry.py:12, 38`；`adapters/__init__.py:7` | ✅ |
| 站点配置 | `site_config/_sites.py:173-185`（纯 IP、`probe_params` 已按 ADR-013 声明） | ✅ |
| 画像 | `site_config/_profiles.py:202-213`（low/50/primary，`std_prefixes=["NB","DL"]`） | ✅ |
| `ADAPTER_TYPE_MAP` | `search_strategy.py:318` `"energy": {"primary":"energy", fallback:"std_gov"}` | ⚠️ **路由无效**：`classify_std_code` 只返回 `gb/industry/db/iso_iec/foreign/group/enterprise/sample/""`（`std_utils.py:100-150`），`NB/DL` 命中 `industry`（`industry_lookup.py:16,48`），查的是 `ADAPTER_TYPE_MAP["industry"]`（其链无 energy，`search_strategy.py:286`）。该条目**仅被 `/api/adapter/status` 用作适配器名来源**（`docker/api/adapter.py:92-108`），不能删；应仿 §8 的 `WW` 先例补 `CODE_ROUTES`（`_constants.py:33-44` 目前无 NB/DL） |
| v1 评分链 | 实测 `get_priority_chain("NB")` 首位 = `energy` | ✅（scorer 正常时 v1 可达；scorer 异常时回退链漏 energy） |
| v2 批量路径 | `logical_code="NB"` → 实测 `get_route_chain("NB")==['energy']` | ✅ 可达（docs/records 生产日志 `代号=NB 路由=energy` 即此路径） |
| **v2 单条路径** | `_single.py:272` 用 `target`（`"NB/T 47016-2023"`）→ `std_type="NB/T"` ∉ `[NB,DL]`（`site_capabilities.yaml:311`）→ L1 不中；L2 选无行业综合站 → 实测链 = `['gongbiaoku','hbba','ahbz','njbz365']`，**无 energy** | ❌ **单条查询（n≤1 或 `use_parallel=False`）不查能源平台**（`_batch.py:116-137`）；可用但不是权威站，hbba 覆盖 NB 故仍可能出结果，属“降级可用” |

### 3.7 评级与最大缺口

**综合评级：B（小缺口）**。

| # | 缺口 | 证据 | 影响 |
|---|------|------|------|
| 1 | 单条查询路径不路由到 energy（批量正常）；`ADAPTER_TYPE_MAP["energy"]` 对硬编码路由无效 | `_single.py:272` + `site_capabilities.yaml:306-319` + `_routing.py:86-103` + 实测 | 单条查询降级到综合站；若 v2 关闭/scorer 异常，硬编码链也不会选 energy |
| 2 | 冒烟脚本必崩（`API_URL` 不存在），fixture 疑似手工且多页/解析失败分支未测 | `scripts/smoke_test_energy.py:33`；`energy.py:29`；`tests/fixtures/energy_sample.json`；`tests/test_energy.py` | 真实网络验证入口失效、翻页核心逻辑无回归保护 |
| 3 | `FALLBACK_URLS` 与固定 Host 矛盾、含未验证域名/HTTP 降级；页 ≥1 无 fallback/重试 | `energy.py:36-37,86-89,101-105` | 备用路径大概率不可用；域名/IP 变更时恢复能力被高估 |

---

## 4. 跨适配器专题：默认 v2 路由可达性（**不可用级**）

> 代码默认 v2（`router_v2.py:390-398`，`ROUTING_ENGINE_VERSION` 缺省 `"v2"`）；部署配置 `docker-compose.yml` / `.env*` 中**均未设置**该变量（已 grep，无命中），故默认行为即 v2。文档侧存在矛盾表述（`docs/onboarding/15-query-adapter-matrix.md:59` 写「默认 v1」，与 `docs/query/README.md:47` 及代码不符——**文档漂移**）。

| 查询形态 | 实际路由链（本机实测，§10） | 是否命中目标适配器 |
|---------|---------------------------|------------------|
| T/ 团体标准，**单条查询** `get_route_chain("T/CIESC 001-2019")` | `['njbz365']` | ❌ ttbz 不在链上 |
| T/ 团体标准，**批量** `get_route_chain("T/CIESC")` | `['njbz365']` | ❌ 同上 |
| NB/T 标准，**单条查询** `get_route_chain("NB/T 47016-2023")` | `['gongbiaoku','hbba','ahbz','njbz365']` | ❌ energy 不在链上 |
| NB 代号桶，**批量** `get_route_chain("NB")` | `['energy']` | ✅ |
| 对照：GB/T `get_route_chain("GB/T 10827.6-2023")` | `['std_gov','csres','cssn']` | ✅（v2 L1 正常） |

根因与最小修法（**需产品/路由决策，建议独立立项**）：

1. **T/ 前缀识别**：`router_v2.py:131` 正则 `^([A-Za-z]{2,6}(?:/[A-Za-z])?)` 不支持单字母 `T/`，且 L1 是精确 `in` 比较（第 293 行）无法匹配 `supported_types: ["T/"]`。修法二选一：① 正则允许 `T/([A-Z]+)` 并把 `intent.std_type` 归一为 `"T/"`、L1 改前缀匹配；② 在 v2 能力模型/路由里给 group 类加显式硬路由。落点：`pilotstd/query/routing/router_v2.py` + `config/site_capabilities.yaml`（+ 用例）。
2. **单条路径用 `target` 而非 `logical_code`**：`_single.py:272`。改为 `get_route_chain(logical_code)` 即可让 `NB`/`DL` 在单条路径命中 energy（对 T/ 仍需第 1 条修复）。落点：`pilotstd/query/engine/_single.py`（+ 用例）。
3. **不能删 `ADAPTER_TYPE_MAP["energy"]`**：它同时是 `/api/adapter/status` 的适配器名来源（`docker/api/adapter.py:92-108`）。v1 兜底需要时在 `engine/_constants.py:33-44` 按 §8 `WW` 先例补 `NB/DL` 路由。

影响面：这是**路由/能力模型层**问题，不是两个适配器文件内部缺陷；但它决定用户能否在默认配置下用到这两个适配器，因此列为「不可用级」（`ttbz` 全链路；`energy` 单条路径）。

---

## 5. `adapter-development.md` §6 检查清单对照

| # | 检查项 | TTBZ | Energy |
|---|--------|------|--------|
| 1 | 真实 API 端点已 curl 验证 | ❓ 无提交证据（无 fixture/E2E/冒烟）→ **需实测** | ⚠️ 部分：探活参数已实测（`test_health_check_service.py:211-218`），搜索字段无抓包证据 |
| 2 | 编码已确认（非假设） | ✅ JSON UTF-8（响应头自适配，风险低） | ✅ 同 |
| 3 | 结果结构已保存 | ❌ 无 | ⚠️ 有 fixture 但疑似手工构造 |
| 4 | 字段映射真实数据验证 ≥3 条 | ❌ 合成数据 | ⚠️ fixture 3 条（真实性待核） |
| 5 | 分页机制已确认 | ⚠️ 参数已确认、未循环 | ✅ 已循环+告警 |
| 6 | 空结果行为已测试 | ✅ `test_search_no_results` | ✅ `test_search_candidates_no_results` |
| 7 | 特殊参数已记录 | ✅ `ttbz.py:29-36`（pageNo/pageSize/standardName；不支持 status 过滤） | ✅ `adapter-development.md:119-142`（tid/op/limit/offset） |
| 8 | Fixture 已提交 | ❌ | ✅（真实性待核） |

---

## 6. 最小补齐清单（按优先级；「是否需联网」单列在 §7）

| ID | 优先级 | 文件（改/建） | 补什么 | 用例 | 需新 fixture |
|----|--------|--------------|--------|------|-------------|
| P0-1 | P0 | `pilotstd/query/routing/router_v2.py` + `config/site_capabilities.yaml` | **T/ 前缀识别 + L1 匹配语义**，使 v2 能路由到 `ttbz`（§4-1）；同时补路由用例 | `tests/test_router_v2.py` +2（T/CIESC 单条/批量命中 ttbz） | 否 |
| P0-2 | P0 | `pilotstd/query/engine/_single.py:272` | v2 单条路由改用 `logical_code`（使 `NB/DL` 单条命中 energy） | `tests/query/engine/test_single_v2_route.py` +1（NB 单条链含 energy） | 否 |
| P0-3 | P0 | `scripts/smoke_test_energy.py:33` | `adapter.API_URL` → `adapter.get_search_url()`（当前必崩） | —（脚本自证） | 否 |
| P0-4 | P0 | `tests/fixtures/ttbz_sample.json`（新建）+ `tests/fixture_baseline.py:37-53`（登记） | **TTBZ 真实响应 fixture（≥3 条，脱敏）**；确认 `standardName` 是否按编号搜、`data.total`、状态值、是否含替代字段 | `tests/test_adapters.py::TestTTBZAdapter` +2（fixture 解析/字段字典） | ✅ 新建 |
| P0-5 | P0 | `tests/fixtures/energy_sample.json`（替换真实抓包） | 用真实响应替换疑似手工 fixture（保 `total/rows` 原始字段名） | 现有 5 个 fixture 用例自动受益 | ✅ 替换 |
| P1-1 | P1 | `pilotstd/query/adapters/ttbz.py:82,123-133` | 分页：≥2 页拉取或至少 `total>len(rows)` warning（对齐 energy） | `tests/test_adapters.py` +2（pageNo 透传 / 截断告警） | 否 |
| P1-2 | P1 | `pilotstd/query/adapters/ttbz.py:184-194` | `replaces`（若实测 API 有字段；没有则写入 docstring 限制清单） | +1（有字段时映射断言） | 依实测 |
| P1-3 | P1 | `scripts/smoke_test_ttbz.py`（新建） | §5 第 4 步要求的网络冒烟（搜索+空结果+字段非空断言） | —（脚本自证） | 否 |
| P1-4 | P1 | `tests/test_energy.py` | 多页翻页成功（total=32 造 3 页）、JSON 解析失败、fallback 成功 3 条用例 | +3 | 可复用 fixture 变体 |
| P1-5 | P1 | `pilotstd/query/adapters/energy.py:36-37,86-89` | 处理 Host 固定的 fallback 矛盾：删除未验证域名或按 URL 动态 Host；评估 HTTP 降级 | —（行为测试可选 +1） | 否 |
| P1-6 | P1 | `pilotstd/query/engine/_constants.py:33-44` | （可选）按 §8 先例补 `NB/DL` 硬编码兜底路由，使 scorer/v2 双失败时仍可达 | `tests/test_query.py` +1 | 否 |
| P2-1 | P2 | 文档 | 更新 `adapter-development.md:9,18`（测试数 15/18）、§5 `PROD_PRIORITY`→现路由结构；`onboarding/15:59` 与 `query/README:47` 的「默认 v1/v2」矛盾；`architecture/modules/query.md:33,49` 行数（energy 非空 171、ttbz 167） | — | 否 |
| P2-2 | P2 | `pilotstd/query/adapters/ttbz.py:33-36` | 已知限制补充：无 status 过滤之外，补「无替代字段/仅首页/无详情链接」 | — | 否 |

---

## 7. 工作量估算

| 口径 | 数量 | 明细 |
|------|------|------|
| **P0（阻断可用性/正确性）** | **5 项 / 6 文件 + 1 新建 fixture** | `router_v2.py`、`site_capabilities.yaml`、`_single.py`、`smoke_test_energy.py`、`test_energy.py`/`test_router_v2.py`/`test_single_v2_route.py`、新建 `ttbz_sample.json`、替换 `energy_sample.json` |
| P1（字段/健壮性/测试） | 6 项 / 4 文件 | `ttbz.py`、`energy.py`、`_constants.py`、新建 `smoke_test_ttbz.py`、`tests/test_adapters.py`、`tests/test_energy.py` |
| P2（文档） | 2 项 / 4 文档 | `adapter-development.md`、`onboarding/15`、`query/README.md`、`architecture/modules/query.md` |
| **新增/修改用例合计** | **≈ 11-13 个** | ttbz 5（fixture 2 + 分页 2 + replaces 1）、energy 4（多页/解析失败/fallback/冒烟）、路由 3（ttbz 2 + energy 1） |
| **需新建/替换 fixture** | **2 个** | `tests/fixtures/ttbz_sample.json`（新建）、`tests/fixtures/energy_sample.json`（换真实抓包） |
| **需联网实测** | **4 项** | 见 §9 |

> 只算「适配器自身做足」（不含 §4 路由修复）：约 **3 文件 + 9 用例 + 2 fixture**；加上路由不可用级修复：**+3 文件 + 3 用例**。不涉及数据库/schema/前端，无四件套门禁；但改 `pilotstd/query/` 会触发 G-031 文档联动（`docs/architecture/modules/query.md`）与 G-013（`fix:` 必须带测试）。

---

## 8. 判定与文档漂移（非缺陷，供后续收口）

- `PROD_PRIORITY` 已重构为 `_DEFAULT_FALLBACK_CHAIN`（`engine/_constants.py:16-20`）+ `ADAPTER_TYPE_MAP` + v2 YAML；`adapter-development.md:80-85` 仍写旧名。
- `ADAPTER_TYPE_MAP` 中十余个非粗粒度键（`env/railway/cultural/measurement/...`）对 `_resolve_base_route` 的路由分支**不可达**（`classify_std_code` 只返回 8 类粗标签，`std_utils.py:100-150`），但仍是 `/api/adapter/status` 的名字来源（`docker/api/adapter.py:92-108`），**不可清理**；v1 实际靠 scorer 命中。属系统性问题，不在本次两适配器范围。
- 文档测试数/行数：`adapter-development.md:9` TTBZ「10 个测试」（实际 15）、`:18` Energy「13」（实际 18 相关）；`architecture/modules/query.md:33,49` 行数（非空）energy 159→171、ttbz 164→167。

---

## 9. 需实测项（本机未联网，无法确认；给出测法）

| # | 待确认 | 怎么测 |
|---|--------|--------|
| 1 | TTBZ `getPortalStandardList` 真实响应结构：`data.total`、`standardStatusName` 取值集合、**是否有替代字段**、`standardName` 参数是否支持按标准号搜 | `curl -s -k -X POST '<site_config ttbz search_url>' -H 'X-Requested-With: XMLHttpRequest' -H 'Referer: https://www.ttbz.org.cn/standard.html' --data 'pageNo=1&pageSize=20&standardName=T/CAS 123-2024'`，保存响应为 fixture（脱敏） |
| 2 | TTBZ 是否有详情页 URL（用于原文链接） | 浏览器打开一条结果看地址栏/`standardUniqueId` 的消费方式（F12→Network） |
| 3 | energy 真实响应是否含归口/详情/附件字段；`state` 是否只有 `现行/废止` | `curl -sk 'https://114.251.111.103:18080/zxd/portal/stdPage?keyword=NB%2FT&tid=0&op=&limit=15&offset=0' -H 'Host: 114.251.111.103:18080'`，抓全键名替换 fixture |
| 4 | 生产部署是否真的未设 `ROUTING_ENGINE_VERSION=v1`（决定 §4 严重度） | 生产容器 `docker exec ... env | grep ROUTING_ENGINE_VERSION`（**只读**），或看 `/api/health` 旁路由日志 `[v2 Router]` 前缀是否出现 |

> 实测 1/3 的结果会直接改变 P1-2（ttbz replaces）与字段覆盖结论；实测 4 若发现生产已回滚 v1，则 §4 降级为「潜在缺陷」。

---

## 10. 证据附录

### 10.1 测试实跑

```
$ python -m pytest tests/test_energy.py "tests/test_adapters.py::TestTTBZAdapter" -q
28 passed, 2 warnings in 2.50s

$ python -m pytest tests/query/adapters/test_adapter_log_levels.py -q
17 passed

$ python -m pytest tests/test_query.py -q -k "route or group"
10 passed, 73 deselected
```

### 10.2 路由/解析探针输出（`C:\Temp\p2_eval_probe3.py`）

```
parse_std_number 'T/CAS 123-2024' -> {'raw_code': 'T/CAS', 'code': 'TCAS', 'number': 123, 'year': 2024}
v2 enabled by default: True
v2 route_chain 'T/CIESC 001-2019' -> ['njbz365']
v2 route_chain 'T/CIESC'          -> ['njbz365']
v2 route_chain 'NB/T 47016-2023'  -> ['gongbiaoku', 'hbba', 'ahbz', 'njbz365']
v2 route_chain 'NB'               -> ['energy']
v2 route_chain 'DL'               -> ['energy']
v1 scorer chain NB:      ['energy', 'hbba', 'std_gov', ...]
v1 scorer chain T/CIESC: ['ttbz', 'std_gov', 'jjg', ...]
v1 scorer chain NB/T:    ['energy', 'hbba', 'std_gov', ...]
```

### 10.3 行数（口径：总行 / 非空行）

| 文件 | 总行 | 非空行 |
|------|------|--------|
| `pilotstd/query/adapters/ttbz.py` | 198 | 167 |
| `pilotstd/query/adapters/energy.py` | 205 | 171 |
| `tests/test_energy.py` | 198 | 166 |
| `tests/fixtures/energy_sample.json` | 32 | 32 |
| 本文件 `docs/plans/2026-11-24-p2-recon-existing.md` | 370 | 289 |

### 10.4 关键证据索引（本报告引用的 `文件:行`）

- 契约基类：`base.py:39-51, 75-87, 212-217, 257-279`
- TTBZ：`ttbz.py:21, 29-36, 38-53, 55-61, 65-127, 131-142, 148-197`
- Energy：`energy.py:21, 29, 32-48, 50-56, 60-62, 66-80, 82-173, 175-205`
- 模型：`models.py:9-31`；状态：`core/status.py:37-45`；通用映射：`search_strategy.py:165-243`
- 路由：`engine/_routing.py:43-121, 149-173`；`engine/_constants.py:16-20, 33-44`；`routing/router_v2.py:94-110, 128-175, 283-335, 390-398`；`engine/_single.py:203-210, 256-329`
- 注册：`registry.py:32-54`；`site_config/_sites.py:69-77, 173-185`；`site_config/_profiles.py:202-213, 262-273`；`config/site_capabilities.yaml:156-169, 306-319`
- 下游影响：`manager/classifier.py:93-106`；`pipeline/router.py:92-110, 174-183`；`download/engine.py:424-426`；`ui/main_window/parts/_query_ops.py:36`
- 测试：`tests/test_adapters.py:420-612`；`tests/test_energy.py:17-194`；`tests/query/adapters/test_adapter_log_levels.py:264-285`；`tests/test_c2_log_levels.py:336-345`；`tests/test_health_check_service.py:123-149, 211-218`；`tests/fixture_baseline.py:37-53`
