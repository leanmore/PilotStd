# 下载流程（openstd 国家标准全文公开系统）

> 本文是 `pilotstd/download/adapters/openstd_download.py` 的"文字映射"：描述**当前代码实际执行的下载链路**、两个历史事故点、以及守护这条链路的防回归测试。
> G-031 映射：`pilotstd/download/` → 本文（改该目录下任何文件都必须同批同步本文，见 `docs/governance/gates.md` G-031）。
>
> 代码基准：`pilotstd/download/adapters/openstd_download.py`（395 行，HEAD = `ba9af616`）。

---

## 一、总览

下载一条标准的完整链路（代码位置见下文逐条）。下标的"步骤"编号沿用模块 docstring 的说法（那里把 [2]~[4] 拆成"取验证码图 / ddddocr 识别 / 提交 verifyCode"三步，故称 **6 步**）；按函数划分则是 5 步（`_visit_detail` / `_open_download_page` / `_handle_captcha` / `_fetch_view` + hcno 解析），`_do_download` 的 docstring 称"5 步链路"（`:226`）。两种说法指的是同一条链。

```
task ──► [0] hcno 解析（openstd 搜索页）        _resolve_hcno / _lookup_hcno / parse_hcno_from_search_page
     ──► [0'] 详情页预访问 newGbInfo?hcno=      _visit_detail
     ──►  ┌─ 每轮（_VIEW_ROUNDS = 2 轮）─────────────────────────────┐
          │ [1] 全文下载页 showGb?type=download   _open_download_page │
          │ [2] 验证码图 gc?_<ts>                 _handle_captcha     │
          │ [3] OCR 识别 4 位      ┐                                  │
          │ [4] 提交 verifyCode    ┘（每轮 2 次尝试）                 │
          │ [5] 取文件 viewGb?hcno=               _fetch_view         │
          └──────────────────────────────────────────────────────────┘
```

`hcno` 解析成功之前**不进入**验证码阶段；解析不到直接失败（`download()` :175-187）。

---

## 二、hcno：唯一的权威来源是 openstd 搜索页

### 2.1 来源与解析

| 环节 | 代码位置 | 说明 |
|------|---------|------|
| 搜索页 URL | `openstd_download.py:92-98`（`search_url`，装饰器在 `:91`） | 由 `BASE_URL` 派生 → `{BASE_URL}/std_list_type`，即 `https://openstd.samr.gov.cn/bzgk/std/std_list_type` |
| 查询参数 | `openstd_download.py:133-142` | `p.p1=0&p.p2=<标准号>&p.p90=circulation_date&p.p91=desc` |
| 逐行解析 | `openstd_download.py:48-49`（`_HCNO_ROW_RE`）、`65-78`（`parse_hcno_from_search_page`） | 匹配 `onclick="showInfo('<hcno>')"` 并**同时取出该行显示的标准号** |
| 标准号归一 | `openstd_download.py:55-62`（`_norm_std_no`） | 去空白（含全角空格）、`—`/`－`→`-`、`／`→`/`、大写 |
| 解析入口 | `openstd_download.py:130-158`（`_lookup_hcno`）、`160-169`（`_resolve_hcno`） | 顺序：`task.extra["hcno"]`（显式传入，供手工/GUI）→ openstd 搜索页；解析不到返回空串 |

**必须逐行按标准号匹配，不能取页面第一个 `showInfo(...)`**（`:68-71` 的注释与 `parse_hcno_from_search_page` 的比较逻辑）：搜索页会同时返回多条结果，2026-09-26 实测搜 `GB/T 5310-2008` 时首条是 `GB 2024-2016`——取首条会把**别的标准**的全文当成该收藏的下载内容。

### 2.2 ⛔ 禁用 `std_gov` 查询结果的 `pid` 当 hcno

`pilotstd/query/adapters/std_gov.py`（查询流程）产出的 `pid` 与下载流程需要的 `hcno` 是**两个不同的标识**，openstd 下载侧**不识别 pid**。

实测事实（`openstd_download.py:27-33` 记录，2026-09 现场）：请求 `newGbInfo?hcno=<pid>` 的响应，与"空 hcno"和"损坏 hcno"的响应**逐字节相同** ——

```
sha1 = b93e289a82d884a4    响应长度 = 18610 字节（三者一致）
```

因此代码**刻意不回退** `task.query_result.hcno`：回退只会让失败推迟到验证码之后，并**伪装成"验证码问题"**（`:160-169` 的 docstring 明写这一点，`:153-157` 的告警文案也点名"std_gov 的 pid 不是 hcno，禁止回退使用"）。

同理，`download()` 在解析不到 hcno 时给出显式错误文案（`:179-182`）：

```
无法获取下载标识(hcno): <标准号>（openstd 搜索页未匹配到该标准号；std_gov 的 pid 不能当 hcno 用）
```

---

## 三、端点族：`/bzgk/std/*`，不是 `/bzgk/gb/*`

`BASE_URL = "https://openstd.samr.gov.cn/bzgk/std"`（`openstd_download.py:89`），全流程 6 个请求全部落在该命名空间：

| 请求 | 路径 | 代码位置 |
|------|------|---------|
| 搜索页 | `/bzgk/std/std_list_type` | `:98` |
| 详情页 | `/bzgk/std/newGbInfo?hcno=<H>` | `:194` |
| 全文下载页 | `/bzgk/std/showGb?type=download&hcno=<H>&request_locale=zh` | `:216` |
| 验证码图 | `/bzgk/std/gc?_<毫秒>` | `:323` |
| 提交验证码 | `POST /bzgk/std/verifyCode` | `:372` |
| 取文件 | `/bzgk/std/viewGb?hcno=<H>` | `:260` |

**为什么不能退回 `/bzgk/gb/*`**（`openstd_download.py:21-25`，2026-09 起站点迁移）：

- 旧路径对 **GET** 是 301，`requests` 自动跟随 → 表面上"还能用"；
- 旧路径对 **POST** 是 301 → `requests` 会把请求**降级为 GET**，**表单体被丢弃** → `verifyCode` 恒返回 `error`。
- 被丢弃的正是验证码文本，**与 OCR 准确率无关**。生产日志 2026-09-24~26 连续 **15 次** `verifyCode 结果: error`、**0 次** `success`，即此因。

代码里两处把这条钉死：`BASE_URL` 上方的注释（`:88`）与 `TestEndpointPathGuard`（见第六节）。

---

## 四、完整步骤链（按代码实际顺序）

### [0] hcno 解析 —— `_resolve_hcno`（`:160-169`）

见第二节。失败即返回 `None`，不进入验证码阶段。

### [0′] 详情页预访问 —— `_visit_detail`（`:189-207`）

`GET {BASE}/newGbInfo?hcno=<H>`，作用有二：

1. **建立会话**（后续请求沿用同一 `requests.Session` 的 cookie）；
2. **提前暴露失效 hcno**：若响应 200 但页面里查不到该标准号，打 warning（`:200-206`）——`pid`/空/篡改 hcno 都会命中这条（服务端返回同一张"标准不存在"的壳页面）。

返回详情页 URL，供后续请求当 `Referer`（浏览器点击链路同款）。该步失败**不致命**（`:196-199` 捕获异常后继续）。

### [1] 全文下载页 —— `_open_download_page`（`:209-223`）

```
GET {BASE}/showGb?type=download&hcno=<H>&request_locale=zh     Referer: 详情页
```

**这一步不可跳过。** 站点自身 JS 里写着后续动作 `window.location.href = "viewGb?hcno=" + hcno`，适配器按站点自身顺序执行。

对照实验（2026-09-26 实测，GB/T 5613-2026）：

| 序列 | 结果 |
|------|------|
| 跳过全文下载页（直接 gc → verifyCode → viewGb） | 200 + **0 字节** |
| 走完整序列（下载页 → gc → verifyCode → viewGb） | **251074 字节** PDF |

不打开该页偶尔也能成功，但**新会话首下必空**（`:212-214` 的注释）。

### [2] 验证码图片 —— `_handle_captcha`（`:314-329`）

```
GET {BASE}/gc?_<毫秒>     Referer: 全文下载页
```

期望 `Content-Type` 含 `image`；否则打 **error** 级日志"端点是否已迁移？"（`:331-339`）——端点迁移会在这一步第一时间暴露，而不是等到 `verifyCode` 报 error。

### [3] OCR 识别 —— `_handle_captcha`（`:341-356`）

`ddddocr.DdddOcr().classification(img_resp.content)`；`ImportError` 或任何异常都降级（`:349-352` 只打 warning，不抛）。
识别结果长度 ≠ 4 时走 `captcha_callback` 手工兜底（`:355-356`）。

### [4] 提交验证码 —— `_handle_captcha`（`:369-394`）

```
POST {BASE}/verifyCode     body: verifyCode=<4位>     Referer: 全文下载页
```

期望响应体恰为 `success`（`:379-380`）；返回非 `success` 且响应体像 HTML 或超长时打 error"端点可能已迁移"（`:381-387`）。

**每轮最多 2 次尝试**（`:321` 的 `for attempt in range(2)`）：第 1 次识别失败或提交失败时**换一张新图**重试，第 2 次仍失败才置 `验证码提交失败（已重试）`（`:393`）。

### [5] 取文件 —— `_fetch_view`（`:258-308`）

```
GET {BASE}/viewGb?hcno=<H>     Referer: 全文下载页     timeout=120s, stream=True
```

校验三件事：

| 校验 | 代码位置 | 失败文案 |
|------|---------|---------|
| HTTP 200 | `:268-276` | `viewGb HTTP <code>` |
| 非空（200 + 0 字节 = 会话未通过验证码，或该标准暂无全文） | `:279-283` | `viewGb 返回空内容（会话未通过验证码，或该标准暂无全文）` |
| `%PDF` 文件头 | `:296-297` | 兜底：`>1000` 字节且前 50 字节不含 `html` 也接受（`:298-299`）；否则 `viewGb 返回非 PDF 内容`（`:301`） |

并从 `Content-Disposition` 提取文件名写入 `task.extra["filename_from_header"]`（`:285-293`）。

### 轮次与重试语义（务必区分）

`_VIEW_ROUNDS = 2`（`:51-52`），整轮循环在 `_do_download`（`:225-256`）：

- **整轮重试只在"验证码通过、但 `viewGb` 取到 0 字节/无效内容"时发生**（`:238-255`），第二轮 = `_open_download_page` → `_handle_captcha` → `_fetch_view` **全部重做**（重开下载页 → 重新要验证码）。第 2 轮多为"会话授权未落地"。
- **OCR 识别失败不消耗轮次**：`_handle_captcha` 内识别失败会 `continue` 换图重试（`:359-360`），两次都失败才置 `error_message`，`_do_download` 随即 `return None`（`:235-236`）——**不会**进入第二轮。
- 因此单条标准最多 **2 轮 × 2 次验证码尝试 = 4 次** `gc` + `verifyCode`。
- 每轮取到文件会打 info `viewGb 第N轮取到全文`（`:241-247`），用于现场统计"两轮是否够用"。
- 进入下一轮前会清空 `task.error_message`（`:255`），避免上一轮的失败文案假冒本轮结果。

---

## 五、历史事故（三次回归的完整链条）

### 5.1 相关提交（均已在仓内核实）

| commit | 日期 | 结论 |
|--------|------|------|
| `c574ccda` | 2026-05-26 | `fix: 恢复gb688下载流程—先showGb建立会话再viewGb下载+openstd搜索hcno`。**只改 `pilotstd/download/adapters/gb688.py`**（当时文件名，+216/-48）。新增 `OPENSTD_SEARCH = "https://openstd.samr.gov.cn/bzgk/gb/std_list"` 与 `_search_hcno()`；hcno 从 `showInfo('...')` 提取，正则 `showInfo\('([A-F0-9]+)'\)`。 |
| `70b631b4` | 2026-06-02 | gb688.py（+5/-4）：把 `_search_hcno()` 提到 `query_result.hcno` **之前**；新增注释"std_gov 的 pid 是新版格式，不可用于 gb688.cn 的 viewGb 直链"。 |
| `d6a56b11` | 2026-06-02 | gb688.py（+33/-15）：补"⚠️ 架构前提（已反复验证，禁止修改）"与"⚠️ 顺序不可改"。**但实测该提交的代码与本意相反**：注释写"顺序不可改"，diff 却把 `query_result.hcno` 兜底**挪到 `_search_hcno()` 之下成为无条件兜底**（旧写法 `if not hcno:` 缩进层级更深）——即"注释说要防的东西"正是这次改出来的。 |
| `f04f1b92` | 2026-06-03 | 文件已于 `f247cf2e`（2026-06-02 14:19）改名为 `openstd_download.py`。本提交（+?/-?，openstd_download.py 记 122 行变更）**保留** `_search_hcno()`，改用 `_try_extract_hcno(standard_number)` 按标准号搜索（含前缀变体回退），并把 pid 兜底换成 `resolve_hcno_from_pid(...)` 惰性获取。 |
| `f4f812e7` | 2026-06-04 | 见 5.2。 |

> 提示词里的 `c574ccda` 被描述为"可用的 `_search_hcno` 用 `/bzgk/gb/std_list`"——**实测：该提交确实用了这个 URL，但改的是 `pilotstd/download/adapters/gb688.py`（不是 `openstd_download.py`；后者改名发生在 `f247cf2e`）**。

### 5.2 `f4f812e7`（新平台重写）：三处改动同时埋下隐患

`f4f812e7af887112f15bcf077bae57856a661321`（2026-06-04 13:42:20，`fix: 下载适配器重写 + pipeline入队去重——openstd新平台适配`），共 11 文件 +267/-271，其中 `pilotstd/download/adapters/openstd_download.py` 记 `358 ++++----`。

该提交的 message 自述"删除 `_search_hcno` 等死代码（301→167 行）"，实测 diff 三处关键改动：

| # | 改动 | 实测 diff | 后果 |
|---|------|----------|------|
| A | 删掉 `_search_hcno()` / `_try_extract_hcno()`（当时**可用**的 hcno 搜索：openstd 搜索页 `showInfo()` 逐行提取） | `-    def _search_hcno(...)`、`-    def _try_extract_hcno(...)`、`-    OPENSTD_SEARCH = ...`、`-    OPENSTD_DETAIL = ...` | hcno 失去权威来源 |
| B | hcno 来源换成 `query_result.hcno`（即 `std_gov` 的 **pid**） | `+    ⚠️ hcno 来源：std_gov 适配器查询结果的 pid 即新平台 hcno，无需额外搜索步骤。query_result.hcno 直接使用。`；`-            from pilotstd.query.search_strategy import resolve_hcno_from_pid` / `+            hcno = getattr(task.query_result, "hcno", "")`；`search_strategy.py` 里的 `resolve_hcno_from_pid` + `GB_DETAILED_URL` 同批删除（-33 行） | pid 不是 hcno（第二节实测）；失败被推迟到验证码之后并伪装成"验证码问题" |
| C | `BASE_URL` 写死成 `/bzgk/gb` | `-    BASE_URL = "http://c.gb688.cn/bzgk/gb"` → `+    BASE_URL = "https://openstd.samr.gov.cn/bzgk/gb"` | 端点迁移后 POST 遇 301 降级为 GET、body 丢失 → `verifyCode` 恒 error |

A + B + C 叠加 = **下载链长时间全量失败**：现场 2026-09-24~26 连续 **15 次** `verifyCode` 提交、**0 次** `success`（见台账 #21）。

### 5.3 修复

`532d994f`（2026-09-26，`fix(download): openstd 下载链路修复——新路径 /bzgk/std + hcno 权威来源（搜索页）`，3 文件 +390/-109）与 `62fba6ef`（同日，`hcno 解析器边界用例 + viewGb 轮次可观测`，2 文件 +84/-1）落地三项修复：hcno 回到 openstd 搜索页、端点族迁 `/bzgk/std/*`、新增「全文下载页」步骤。现场真实站点实测 9/9 下载成功。

> 这也是本文存在的原因：这三个事实此前**只存在于代码 docstring 与台账行里**——下一位维护者看不到全貌就会再改一次。

---

## 六、防回归测试（`tests/download/adapters/test_openstd_download.py`，43 个用例）

> 实测：`python -m pytest tests/download/adapters/test_openstd_download.py -q --no-header` → **43 passed**。

### 6.1 三个契约测试（本节重点）

| 测试 | 位置 | 测什么 |
|------|------|--------|
| `TestHcnoResolution::test_query_result_pid_is_not_used_as_hcno` | `tests/download/adapters/test_openstd_download.py:129-144` | **pid ≠ hcno 契约**。构造"搜索页只返回别的标准号 + `task` 里带 `query_result.hcno="PID_FROM_STD_GOV"`"，断言：① `download()` 返回 `None` 且 `error_message` 含"无法获取下载标识(hcno)"；② `_handle_captcha` **一次都没被调用**（解析不到 hcno 不得进入验证码阶段）；③ mock server 日志里**没有 `/viewGb` 请求**（不得拿 pid 去下载）。—— 这条就是把 2026-09 事故（5.2 B）钉死。 |
| `TestHcnoResolution::test_search_row_number_must_match` | `tests/download/adapters/test_openstd_download.py:146-153` | **按行匹配契约**。搜索页只返回 `GB 2024-2016`（目标标准号是 `GB/T 1234-2020`），断言返回 `None` 且 `_handle_captcha` 未被调用 —— 防止"取首条"把**别的标准**全文当成本条下载。 |
| `TestEndpointPathGuard` | `tests/download/adapters/test_openstd_download.py:619-649` | **端点族契约**（类 docstring 写明 301 降级机理）。三个断言：① `test_base_url_is_std_namespace`（`:627-630`）直接断言 `OpenstdDownloadAdapter.BASE_URL.endswith("/bzgk/std")`，失败信息即"旧 /bzgk/gb 会 301，POST 体丢失导致 verifyCode 恒 error"；② `test_search_url_shares_base_namespace`（`:632-635`）断言 `search_url == f"{BASE_URL}/std_list_type"`（防止"端点改了、搜索页还指旧路径"的漂移）；③ `test_all_requests_use_std_paths`（`:637-649`）跑完整下载流程后断言 mock server 日志里**没有任何以 `/bzgk` 开头的硬编码路径**。 |

### 6.2 其余防回归/边界测试（逐个说明）

| 测试 | 位置 | 测什么 |
|------|------|--------|
| `TestHcnoResolution::test_missing_hcno_returns_none` | `:91-100` | `extra={}` 且无 `query_result` → `None` + "无法获取下载标识(hcno)" |
| `TestHcnoResolution::test_extra_none_returns_none` | `:102-111` | `extra=None` 时同样安全失败（不抛 `AttributeError`） |
| `TestHcnoResolution::test_hcno_resolved_from_openstd_search_page` | `:113-127` | 无显式 hcno 时确实去搜索页解析，并断言**最后一次 `/viewGb` 请求带的是搜索页解析出的那个 hcno** |
| `TestHcnoParser::test_picks_matching_row_not_first` | `:664-677` | 目标在第 2 行时必须返回第 2 行的 hcno（真实事故：搜 `GB/T 5310-2008` 首条是 `GB 2024-2016`），反向也成立 |
| `TestHcnoParser::test_no_match_returns_empty_not_first` | `:679-682` | 无匹配必须返回空串，不得退化为取首条 |
| `TestHcnoParser::test_empty_target_returns_empty` | `:684-687` | 空/全空白的目标标准号 → 空串 |
| `TestHcnoParser::test_normalization_case_and_spacing` | `:689-700` | 归一化：大小写、普通空格、全角空格、`—` 破折号、全角斜杠 `／` 都要能对上 |
| `TestHcnoParser::test_ignores_rows_without_matchable_number` | `:702-711` | 页面夹杂"查看详细"等非标准号锚点时不误伤 |
| `TestHcnoParser::test_short_or_non_hex_ids_ignored` | `:713-721` | hcno 必须是 16–40 位十六进制；`NOT_A_HCNO` 这类占位/脏数据不得被当成 hcno |
| `TestShowGbError::test_detail_page_connection_error_is_not_fatal` | `:162-178` | 详情页预访问网络异常**不致命**：仍走验证码 + viewGb 并成功 |
| `TestCaptchaFailure::test_ocr_fails_without_callback` | `:187-202` | ddddocr 返回空串且无 callback → 两次重试后置"验证码识别失败" |
| `TestCaptchaFailure::test_callback_returns_invalid_then_fail` | `:204-220` | callback 返回长度 ≠ 4 → 重试后仍失败 |
| `TestCaptchaFailure::test_verify_code_non_success_twice` | `:222-239` | `verifyCode` 两次非 `success` → "验证码提交失败" |
| `TestCaptchaFailure::test_ddddocr_import_error_falls_back_to_callback` | `:241-260` | `ddddocr` 未安装 → callback 兜底成功（`error_message` 保持空） |
| `TestCaptchaFailure::test_ddddocr_exception_falls_back_to_callback` | `:262-281` | `ddddocr` 抛非 `ImportError` 异常 → 同样降级到 callback |
| `TestCaptchaFailure::test_captcha_image_fetch_error` | `:283-291` | 验证码图片 GET 失败 → 立即"验证码图片获取失败" |
| `TestCaptchaFailure::test_verify_code_request_exception_then_retry` | `:293-312` | `verifyCode` POST 两次网络异常 → 失败 |
| `TestCaptchaFailure::test_verify_code_first_exception_second_success` | `:314-341` | `verifyCode` 第 1 次异常、第 2 次成功 → 通过 |
| `TestViewGbErrors::test_view_gb_network_error` | `:350-366` | `viewGb` 两轮都网络异常 → "PDF 下载请求失败" |
| `TestViewGbErrors::test_view_gb_empty_first_round_then_pdf` | `:368-395` | **轮次语义**：首轮空内容 → 自动重开下载页重试并成功；断言 `viewGb` 恰好被请求 2 次、`filename_from_header` 来自第 2 轮 |
| `TestViewGbErrors::test_view_gb_non_200` | `:397-406` | HTTP 500 → `viewGb HTTP 500` |
| `TestViewGbErrors::test_view_gb_empty_content` | `:408-417` | 200 + 0 字节 → "空内容" |
| `TestViewGbErrors::test_view_gb_non_pdf_small_html` | `:419-430` | 小体积（<1000B）HTML → "非 PDF" |
| `TestViewGbErrors::test_view_gb_large_content_with_html` | `:432-444` | >1000B 但前缀含 html → "非 PDF" |
| `TestViewGbErrors::test_view_gb_large_binary_no_html_returns_content` | `:446-458` | >1000B 且不含 html → 按有效内容接受 |
| `TestViewGbErrors::test_view_gb_content_disposition_filename` | `:460-476` | `Content-Disposition` 文件名写入 `task.extra` |
| `TestViewGbErrors::test_extra_none_gets_initialized_for_filename` | `:478-496` | `task.extra=None` 时先初始化再写文件名 |
| `TestDoDownloadCaptchaFail::test_captcha_fails_returns_none_from_do_download` | `:505-521` | `_do_download` 在验证码失败时**提前返回**（不继续 viewGb） |
| `TestContentDispositionVariants`（5 例） | `:529-564` | 文件名变体：单引号、无引号、带额外参数（`; size=456`）、有 `attachment` 无 `filename=`、无该响应头 |
| `TestFullDownload::test_full_download_happy_path` | `:573-586` | 完整 5 步链路正常通过，`error_message` 为空 |
| `TestCanHandle`（4 例） | `:594-612` | 路由判断：`source_site == "openstd_download"` 才接管；`std_gov`/空串不接管；`site_name` 契约 |
| `TestEndpointPathGuard`（3 例，已列于 6.1） | `:619-649` | 见 6.1 |
| `TestHcnoParser`（6 例，已列于上） | `:661-721` | 见上 |

> 计数口径：6.1 的 3 个契约测试 + 上表 33 行 = 去重后 **43** 个测试（上表中"（5 例）""（4 例）"各占一行但含多个用例；`TestEndpointPathGuard` 的 3 例与 6.1 重复列示）。与 `pytest` 实测的 **43 passed** 一致。

---

## 七、维护须知

1. **改 `pilotstd/download/` 必须同批改本文**——G-031 已挂映射（`docs/governance/gates.md` G-031），否则 pre-commit 直接 FAIL。
2. **不要"清理死代码"式删 `_lookup_hcno` / `parse_hcno_from_search_page`**——它们是 `f4f812e7` 删过一次的可用实现（5.2 A）。
3. **不要把 `BASE_URL` 改回 `/bzgk/gb`**（3 与 5.2 C）。
4. **不要给 hcno 加 `query_result.hcno` 兜底**（2.2 与 5.2 B）；`TestHcnoResolution::test_query_result_pid_is_not_used_as_hcno` 会拦住。
5. 修改后至少跑：
   ```bash
   python -m pytest tests/download/adapters/test_openstd_download.py -q
   python scripts/check_g_031_docs_sync.py
   ```
