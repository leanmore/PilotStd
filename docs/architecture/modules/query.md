# 模块文档：查询适配器（Query Adapters）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/query/adapters/` |
| G-031 映射 | `pilotstd/query/adapters/` |
| 核心类 | `BaseAdapter` (ABC) |
| 适配器数 | 22（21 生产 + 1 Mock），非空行合计 **3,256** |
| 文件数 | 27 个 `.py`（22 个适配器 + 5 个基础设施文件，后者非空行 619） |
| 总行数 | **3,875** 非空行（= 3,256 + 619；2026-10-25 实测） |
| 状态 | 活跃 |

> **2026-11-14（A-33）**：`pilotstd/query/__init__.py` 删除 20 个 `_get_*_adapter` 懒加载函数——生产 0 调用、唯一消费者是测试自锁，且会绕过 `adapters/registry.py` 单一真相源。**适配器类统一从 `pilotstd/query/adapters/registry.py` 的 `ALL_ADAPTERS` 获取**，不要在本包再加同类 getter（`tests/test_query_init.py` 只保留顶层导出契约）。

## 模块职责

封装各标准查询网站的 API 调用，统一为 `QueryResult` 输出。每个适配器负责一个站点的搜索请求构造、响应解析、结果标准化。基类提供渐进式搜索策略和评分机制，子类只需实现站点特定的 `_search` 或 `_search_candidates`。

基类模块另有 `pick_best_result(candidates, search_term)`（2026-10-25 从 6 个适配器抽取）：精确匹配优先（按输入顺序取首个命中），否则取 `publish_date` 最新；6 个适配器的 `_search` 改为委托它，行为与原实现逐行等价。

## 适配器清单

> **站点列口径**：`get_search_url()` 运行时取值（代码**实际发出搜索请求**的地址），**不是标准来源域名**；`Mock` 无站点。
> 少数站点为 IP/非标准端口（`energy`、`ncha`），另有适配器的 URL 来自 registry/site_config 而非文件内字面量（如 `ahbz`）。

| 适配器 | 类名 | 站点 | 非空行 |
|--------|------|------|--------|
| 安徽标准 | `AhbzAdapter` | bzxx.ahbz.org.cn | 157 |
| 工程建设 | `CCSNAdapter` | www.ccsn.org.cn | 182 |
| 标准资源网 | `CsresAdapter` | www.csres.com | 255 |
| 中国标准服务网 | `CSSNAdapter` | www.cssn.net.cn | 116 |
| 电标备案 | `DbbaAdapter` | dbba.sacinfo.org.cn | 100 |
| 能源 | `EnergyAdapter` | 114.251.111.103:18080 | 159 |
| 工标库 | `GongBiaoKuAdapter` | www.gongbiaoku.com | 136 |
| 河北标准 | `HbbaAdapter` | hbba.sacinfo.org.cn | 165 |
| 国际标准（经 SAMR） | `IsoGovAdapter` | std.samr.gov.cn | 113 |
| 计量 | `JJGAdapter` | jjg.spc.org.cn | 128 |
| 交通 | `JTSTAdapter` | jtst.mot.gov.cn | 149 |
| 生态环境 | `MEEAdapter` | www.mee.gov.cn | 152 |
| 工信 | `MIITAdapter` | std.miit.gov.cn | 123 |
| Mock | `MockQueryAdapter` | —（mock/测试专用） | 96 |
| 文物 | `NCHAAdapter` | bz.ncha.gov.cn:9005 | 150 |
| 南京标准 | `Njbz365Adapter` | www.njbz365.cn | 149 |
| 自然资源 | `NRSISAdapter` | www.nrsis.org.cn | 188 |
| 食品安全国标 | `SPPTAdapter` | sppt.cfsa.net.cn:8086 | 113 |
| 食品安全地标 | `SPPTLocalAdapter` | sppt.cfsa.net.cn:8087 | 146 |
| 国家标准 | `StdGovAdapter` | std.samr.gov.cn | 194 |
| 铁路 | `TDPressAdapter` | biaozhun.tdpress.com | 121 |
| 团体标准 | `TTBZAdapter` | www.ttbz.org.cn | 164 |

> **行数口径**：非空行（`sum(1 for l in text.splitlines() if l.strip())`）。22 个适配器合计 **3,256**；
> 5 个基础设施文件（`base` 235、`registry` 68、`_njbz365_session_manager` 240、`_shared_ssl` 31、`__init__` 45）合计 **619**；
> 目录总计 **3,875** 非空行 / 27 个 `.py`。**2026-10-25（A-14）重算**；顺带修正 `IsoGovAdapter` 站点
> （旧表误写 iso.org，实际经 std.samr.gov.cn 搜索）。

> **重算命令**（复算请用同一口径；Git Bash 或 WSL）：

```bash
python - <<'PY'
import ast, importlib, pathlib
d = pathlib.Path("pilotstd/query/adapters")
for p in sorted(d.glob("*.py")):
    src = p.read_text(encoding="utf-8")
    nb = sum(1 for l in src.splitlines() if l.strip())
    classes = [n.name for n in ast.parse(src).body
               if isinstance(n, ast.ClassDef) and n.name.endswith("Adapter")
               and n.name != "BaseAdapter"]
    if not classes:
        print(f"{p.name}\tINFRA\t{nb}")
        continue
    if len(classes) > 1:
        print(f"!! {p.name} multiple: {classes}")
    mod = importlib.import_module("pilotstd.query.adapters." + p.stem)
    for c in classes:
        url = getattr(mod, c)().get_search_url() if c != "MockQueryAdapter" else ""
        print(f"{c}\t{nb}\t{url}")
PY
```

> **2026-10-05 类型标注级修正（G-031 联动，P2 步 B B1 收口）**：pilotstd/query/adapters/_njbz365_session_manager.py 的两处 params 由 dict[str, str] 标注为 **dict[str, Any]**（含 from typing import Any），以消除 mypy 因**跟随 import 链**对 Session.post(json=...) 值类型协变不兼容的判定；**运行期行为零变化**（纯标注）。该传递性扫描口径问题已登记 docs/technical-debt.md:419。

> **状态值字典（R14-4b / #32-B，2026-10-01）**：各适配器的状态字面量（`现行` / `即将实施` / `废止` / `已废止` / `作废` / `被代替` / `未知`）与各 `status_map` 归一化表已统一引用权威字典 `pilotstd/core/status.py` 的 `Status.*.value`（取代原中文字面量）。**归一化结果与取值集合不变**，仅消除散落的硬编码字符串。

> **编码回退的预期失败（2026-10-17，体检 D-8 第 5 批）**：`nrsis._decode_content` 的两次 `UnicodeDecodeError` 分支属**预期回退链**（UTF-8 → GBK → `errors="replace"`），不是吞错——已加注释明确，不纳入静默吞错治理。
> **第 11 批（同日）**：`dbba`/`hbba` 的 `act_date` 解析失败、`_batch_dispatcher` 的 `bucket_crash` 指标递增失败、`rotator.reset_all_cooldowns` 的 `adapter_state` 清理失败，均由 `pass` 改 debug；契约见 `tests/test_silent_error_observability_batch11.py`。

> **2026-11-08 替代标准字段日志（U34-B）**：`csres` / `hbba` / `njbz365` 的 `replaces` 解析保持 `debug`（字段缺失不阻断主查询，只影响路由判断），但按异常类型区分「网络请求失败 / 解析失败」并统一 `%s` 占位；`ttbz` 的 `safe_post` 已在重试耗尽/HTTP>=400 时 `warning`、`energy` 翻页且已有数据时上层已 `warning`，这两处保持 `debug` 并加注释，避免同一失败两条告警。契约见 `tests/query/adapters/test_adapter_log_levels.py` 的组 3/4 用例。

> **2026-11-08 适配器失败日志升 warning（U34-B）**：**24 处**「请求失败 / 非 200 / 业务码异常 / JSON 解析失败 / `dataList` 提取失败」由 `debug` 或**完全无日志**升为 `warning`（口径：站点 + 阶段 + 异常/状态码；查询词一律 `%r` 且截断 50 字符，URL 可直出）。涉及 `ccsn`（GET + 分页 POST + 2 处非 200）、`gongbiaoku`、`jjg`、`jtst`、`mee`、`nrsis`（重试耗尽 + 非 200）、`sppt`（请求 + 非 200 + JSON）、`sppt_local`（请求 + 非 200 + `dataList`）、`ttbz`（JSON）、`miit`/`ncha`（业务码，与同文件 HTTP/JSON 的 `error` 对齐）、`iso_gov`（JSON，原为静默）、`energy`（第 1 页全 fallback 失败）。契约见同一测试文件的组 1/2 用例。

> **2026-11-08 死分支清理与级别统一（U34-C2）**：① `energy._fetch_candidates` **删除**不可达的 `debug` 分支——第 0 页无数据时下方 `if not rows: break` 已退出，能进到 page≥1 必然 `all_rows` 非空 ⇒ 「翻页失败且一条都没拿到」永远不会发生；原位置改为注释说明，不再留"看起来有日志、实际跑不到"的代码。② `_njbz365_session_manager._do_request` 的三个 `except` **统一为 `error`**（原先「超时最终失败 error / 其他请求异常 error / JSON 解析失败**无日志**」三档不一致；按「请求最终失败仍是 error」的语义并轨，不再降级）；文案统一为「njbz365 会话 …失败: %s」。契约见 `tests/test_c2_log_levels.py` 与 `tests/query/adapters/test_adapter_log_levels.py`。

## 架构

```
BaseAdapter (ABC)
├── query_with_strategy()  — 5 步渐进搜索（完整号→空格回退→去前缀→去年份→代号变体）
├── _search_candidates()   — 子类重写以返回多结果
├── _post_process_result() — 结果后处理钩子
└── 抽象属性
    ├── site_name: str
    └── site_label: str

每个 Adapter 子类
├── _search() / _search_candidates()  — 站点特定搜索逻辑
├── _do_request()                     — HTTP 请求（可选）
└── 可选钩子
    ├── supports_replaces_detail: bool
    └── fetch_replaces_detail()
```

## HTTP 客户端与 SSL 复用（技术债 #22，2026-09-26）

12 个适配器各自在 `__init__` 构造 `httpx.Client`（签名统一为 `client: httpx.Client | None = None`，便于测试注入）。httpx 在 `verify=True`（默认）时会**为每个 Client** 调 `ssl.create_default_context()` → `load_verify_locations()` 重新加载整份证书包，本机实测单次 ≈1.3s；9 个默认校验的适配器各付一次 → `StandardManager()` 构造中位 **6.74s**，而生产侧有 12 处构造点，交互型操作会直接卡住界面。

修法：新增 `pilotstd/query/adapters/_shared_ssl.py`，暴露进程级单例 `default_ssl_context()`（`ssl.SSLContext`，加锁保证首次只加载一次）；9 个默认校验的适配器改为 `httpx.Client(verify=default_ssl_context(), ...)`。httpx 的 `_config.create_ssl_context()` 对 `isinstance(verify, ssl.SSLContext)` 直接 return，故传 context 后既不新建 context 也不加载证书包。**构造中位 6.74s → 0.036s**（min 0.035s；首次含一次 0.23s 的证书包加载）。

| 分档 | 适配器 | 处置 |
|------|--------|------|
| 默认校验（9） | `ccsn` / `cssn` / `gongbiaoku` / `jjg` / `jtst` / `miit` / `ncha` / `nrsis` / `tdpress` | 传共享 context |
| 自签名站点（3） | `energy` / `sppt` / `sppt_local` | **保持 `verify=False`**（刻意豁免；httpx 该分支本就不加载证书包） |

**不要**改成共享 `httpx.Client` 实例：Client 带会话状态（cookie、连接池、代理），多适配器共用会串会话；也**不要**给 `verify=False` 的三处传共享 context（会把自签名豁免变成强制校验，直接连不上）。

## 路由机制

搜索策略位于 `pilotstd/query/search_strategy.py`：

| 函数 | 作用 |
|------|------|
| `match_result()` | 将 API 返回结果与本地解析信息比对，返回 exact/newer/older/code_only/mismatch |
| `build_code_variants()` | 生成代号变体（如 GB→GB/T、DIN→DIN EN）用于渐进搜索 |
| `_exact_parse_match()` | 解析标准编号后逐字段比对 |
| `_fuzzy_text_match()` | 文本中模糊匹配代号+顺序号+年份 |

评分矩阵：`exact=100, newer=80, older=50, code_only=20, mismatch=0`

## 依赖关系

- `pilotstd.query.models.QueryResult` — 输出数据模型
- `pilotstd.query.search_strategy` — 匹配评分引擎
- `pilotstd.query.network` — HTTP 请求层（`safe_get`、`safe_post`）
- `pilotstd.core.std_utils.parse_std_number` — 标准号解析

## 查询引擎请求节流与测试模式

`pilotstd/query/engine/` 下的执行器（`_single.py`、`_mini_bucket.py`、`_csres.py`）在真实查询时按站点 `request_interval` 与桶间错峰间隔执行 `time.sleep`，避免对目标站点产生高频请求。

测试模式下（`PYTEST_RUNNING=1`，由 `tests/conftest.py` 的 `pytest_configure` 注入）跳过所有节流 sleep，保证测试不因等待而超时；CI 同时通过 iptables 硬阻断 + conftest socket guard 保证测试绝不真实出网（见 `docs/ci-lessons.md` §六）。

## 安全扫描备注（2026-11-08）

`_njbz365_session_manager` 的请求签名按站点协议要求使用 MD5；`energy` / `sppt` / `sppt_local`
对政府自签名站点保留 `verify=False`。三处均加 `# nosec` 并注明“协议要求 / 已评估”，
**无行为变更**，仅让 bandit HIGH 清零（U2）。

## 静默吞错收口（2026-11-09，U-3/U-4 批 3）

`pilotstd/query/adapters/base.py::_post_search_candidates` 的「搜索响应 JSON 解析失败」由
**无日志直接 `return []`** 改为 `warning`（文案带适配器名）——解析失败与「站点确实没有结果」
不再同形；返回值契约不变。

同批（不在本目录映射内）：`pilotstd/query/rotator.reset_all_cooldowns` 的
「清空 `adapter_state` 冷却记录失败」由 `debug` 升 `warning`——原实现失败后仍打印
「所有站点冷却已重置」，日志与实际状态相反。

## 查询缓存新鲜度（2026-11-09，P0-02）

`CacheRepository.get()` 的主表 `standard_info_cache` 仍按 `data_state='stale'` 拒绝命中；公告回退 `announcement_match` 补 TTL 守卫：

- `data_state='stale'` → 不命中；
- `expires_at` 可解析时优先；
- 缺失时按 `cached_at + active_ttl`（默认 30 天；`active_ttl<=0` 不按时间过期）兜底；
- 两个时间都缺失时保守命中（无法判断，不因脏行一刀切）。

`announcement/matcher.py` 写入的 `expires_at` 当前为 `NULL`，所以 TTL 实际靠 `cached_at`。回退过期后查询会回源；网络压力需在验证环境观察。回归：`tests/test_query.py`（5 条缓存三态 + 1 条 QueryEngine 全链）。

## 批次完成审计（P1-04，2026-11-10）

`_batch_dispatcher._persist_batch_state()` 只在批次结束时写 `batch_state` 一行 `status='completed'`，**全仓没有 SELECT/恢复逻辑**；该表是完成审计，不是断点续传。历史迁移 docstring 仍写“断点续传”，以 `docs/query/README.md` 的“批次完成审计”段为准。若将来要做续跑，需先定义稳定 batch_id、幂等重入、stale 判定与读侧恢复，再单独立项。

## 相关文档

- [管理模块](manager.md) — 适配器调用方（`StandardManager` 门面）
- [查询引擎](../../query/README.md) — 批量查询、路由、配额管理

- **零调用清理（2026-11-13，P2-03 批 1）**：删除 _constants.get_fallback_chain；_DEFAULT_FALLBACK_CHAIN 仍被 _routing 与测试使用。

## 溢出/配额语义修正（2026-11-15，P3-16）

- `QuotaManager.all_exhausted()`：判断全部站点批次配额是否耗尽，用于区分"空链"是配额问题还是无路由。
- `_overflow._process_overflow_item`：
  - `start` 只在主站**确实尝试过**（`item_chains` 记录）时跳过它；原判定 `_bucket_key` 恒等于 `chain[0]`，导致空链/未尝试也被跳过；
  - **单站链允许同站重试一次**（每条目上限一次，`_retried` 记录），失败后不再重试；
  - 空链且 v2 配额全耗尽 → `match_status="quota_exhausted"` + 指标 `quota_exhausted`；否则 `chain_exhausted`；
  - 适配器"未找到"哨兵（`error_message` 已设、`match_status` 空）按 NG 处理，不再记 `[LO]` 0 分。
- `_mini_bucket._process_single_query`：同样的哨兵判定，`[LO]` 只用于真实低分结果。
- 回归：`tests/test_p316_overflow_semantics.py`（4 例：哨兵=NG、真实低分仍 LO、单站重试一次、空链配额原因）。

## 引擎指标补充（2026-11-15，M1）

- `_mini_bucket._record_no_result` 与 `_overflow._try_overflow_site`：查询未找到（None/哨兵）
  计 `no_result`，与 `quota_exhausted`/`chain_exhausted` 并列；`build_standard_number`
  增加 `num_prefix` 供归档登记/核销（TSG Z8002-2022）。

## 适配器健康检查（2026-11-17）

- pilotstd/query/health_probe.py：21 站固定探针，站点级适配器走 query_standards，
  搜索引擎型走 query_with_strategy（与主链同入口）；三态 found/no_result/error + 耗时，
  写结构化日志与 /app/data/health_probe.json。
- POST /api/adapters/health/run（admin）手动触发；dapter_health 每小时调度。
- 2026-11-17：探针按 standard_info_cache 的 exact 记录校准（10 站）；无 exact 缓存的 11 站标
  probe_pending，不计入 found/no_result，避免误报。

- 2026-11-17：_collect_csres_results 对“csres 后台结果晚到、idx 已有 NG 结果”改为 found 覆盖，并补 _prog_ok；修复 API stats.found 与日志评分不一致。

- 2026-11-18：query_batch_parsed 在 _handle_overflow 之后**再次** _collect_csres_results；overflow 会把未命中项写 pending，晚到的 csres found 必须二次合并才能进入 stats.found。

- 2026-11-18：csres 日志改用 csres_state_text(result)，仅 is_found() 打“找到”；修复“not-found 被日志标成找到 评分=100”的误导。

## 注释语言规范化（2026-11-19）

- G-012 [LANG] 改为按词判定后，本模块注释里的英文普通词改为中文、裸标识符加反引号；
  仅注释与 docstring 变更，AST 比对无代码变化（全仓 504 行，见 27 日志 #81）。

## 适配器错误必须可区分（2026-11-23，NEW-12 / NEW-13）

**NEW-12（energy fallback）**：`energy.py` 在首页用主链接 + `FALLBACK_URLS` 轮询，
原 `except Exception: continue` 吞掉所有异常（含 DNS/TLS/编码）。最终只报
「第 1 页请求失败（含 fallback，status=None）」，**站点不可达与代码 bug 无法区分**。
修法：记录最后一次异常，warning 里带上 `type(e).__name__: e`。

**NEW-13（jjg / energy 的 JSON 解析）**：`resp.json()` 失败时直接 `break` 且无日志。
站点返回 HTML 错误页时会**静默返回 0 结果**，看起来像「没查到」。
修法：补 `warning`，明确区分「无结果」与「解析失败」。

**守护**：G-050 的 continue/break 档已覆盖这两类（2026-11-23 补）。

## 网络层 Session 生命周期（2026-11-23，NEW-38）

`safe_raw_get` / `safe_raw_post` 原实现每次 `requests.Session()` 后**直接 return，不关闭**，
公告附件下载 / OCR 路径高频调用会持续泄漏连接池。

修法：`with requests.Session() as session:`，但**必须先读 `resp.content` 再让 with 退出** ——
`requests` 的 `Response.content` 是惰性读取的，Session 关闭后未读取的响应体
无法再流式读取。先读一次会缓存到内存，之后调用方读 `resp.content` 命中缓存，
行为与原实现完全一致。

**守护**：`tests/test_resource_leaks.py`（验证 `__exit__` 被调用 + 响应体已读）。

## 代号噪音表扩展：API 类型词（2026-11-24，P1-7.1 B-6）

`search_strategy._strip_code_noise` 噪音表补 `SPEC/BULL/MPMS/TDB/PUBL/RP/TR`（`API STD 610` 等
此前被拼成 `APISTD`，搜索命中不到），并加 `len(code)-len(suffix) >= 2` 守卫，
避免 `ARP`/`TR` 这类真短代号被剥空。`Q` 不进噪音表——已在解析源头拆分，避免误剥以 Q 结尾的代号。
回归：`tests/test_std_utils_asme.py`（含 `_strip_code_noise` 用例）。

## v2 路由：团体标准与斜杠变体不可达修复（2026-11-24，P2 侦查发现）

**现象（实测 `get_route_chain`）**：

| 输入 | 修复前 | 修复后 |
|---|---|---|
| `T/CIESC 001-2019` | `['njbz365']`（**ttbz 永远选不中**，直落 L3 兜底） | `['ttbz']` |
| `T/CECS`（批量纯代号） | `['njbz365']` | `['ttbz']` |
| `NB/T 47016-2023` | `['gongbiaoku','hbba','ahbz','njbz365']`（energy 不可达） | `['energy']` |
| `HJ/T` / `TB/T` / `YD/T` / `DZ/T` / `JT/T` | 全部落 L2 通用兜底 | 分别命中 `mee` / `tdpress` / `miit` / `nrsis` / `jtst` |

**三处根因与修法**：

1. **`T/<组织>` 被当成纯关键词**：`_STD_PREFIX_RE` 要求 2~6 个字母，`T/CECS` 只有 1 个字母+斜杠
   → `std_type=None` → `is_keyword_query=True` → 跳过 L1/L2 直落 L3。
   修法：新增 `_T_GROUP_RE`（`^T/`）在通用正则前识别为 `"T/"`（与 `ttbz` 的
   `supported_types: ["T/"]` 对齐；`TB/T` 以 `TB/` 开头不受影响）。
2. **`NB/T` 推不出「能源」领域**：`energy` 声明 `industries: ["能源"]`，但
   `_STD_TYPE_TO_INDUSTRY` 只有 `NB`/`DL` → 单条查询 `std_type=NB/T` 推不出领域被过滤。
   修法：`_extract_industry` 增加**基码回退**（`NB/T` → `NB`）；
   `site_capabilities.yaml` 的 `energy` 补 `NB/T`/`DL/T` 声明（精确命中优先于基码）。
3. **斜杠变体系统性漏配**：真实标准号中 14+ 个族是 `<基码>/T`（HJ/T、TB/T、YD/T、DZ/T、JT/T…），
   而站点只声明基码。修法：`_route_l1` 改走 `_type_matches()`——**声明优先、未声明才按基码回退**。
   「已被任何站点声明的类型不做基码回退」这条守卫很关键：否则 `GB/T` 会落到只声明 `GB`
   的站点（过匹配，实测会破坏国标 L1 链 `std_gov→csres→cssn`）。

**回归锚点**：`tests/test_router_v2.py::TestGroupStdAndEnergyRouting`、
`::test_slash_variant_base_code_routing`、`::test_declared_types_do_not_fall_back`。
查询域广域回归 673 passed。

**未变**：`SH/T`/`JB/T`/`HG/T` 等**无特色站**的族仍落 L2 通用链（`hbba` 本身是 L2 综合站），
属正确行为；国标/行标/地标既有链不变。

## 新增重庆标准信息平台适配器 `cqis`（2026-11-24，P2 批次 A1）

**站点**：`http://db.cqis.cn/`（重庆市智慧市场监管一体化平台 — 地方标准信息公开）。
**为何值得接**：重庆 DB50 的**权威源**，且提供**全文 PDF 附件**（`AttachmentUrl`）；
现有 `dbba`（全国地标平台）只有题录、无全文。

**接口形态（实测）**：

| 用途 | 请求 | 说明 |
|---|---|---|
| 检索 | `POST /LocalStandard/GetDB50ShareList`（form-urlencoded） | `queryJson={"FinishCode": <标准号>, ...}` + `page` + `rows` |
| 详情 | `POST /LocalStandard/GetPublicInfo`（JSON body `{"keyValue": <id>}`） | **本适配器未调用**：列表已含所需全部字段 |

**关键坑（已落进适配器注释与测试）**：
1. **按编号检索要用 `queryJson.FinishCode`**，`BZName` 匹配的是**标准名称**（用编号搜 BZName 会 0 条）；
2. 响应 **`total` 字段不可靠**（实测恒为 1/2），以 `rows` 实际内容为准；
3. 站点**仅 HTTP**（HTTPS 握手失败），故 `base_url` 用 http；
4. 状态修正：`ReleaseStatus=现行` 但 `ActiveTime` 在未来 → 「即将实施」（与 `dbba` 同口径）。

**注册点（6 处，缺一即不可达）**：`adapters/cqis.py` / `adapters/__init__.py` / `adapters/registry.py` /
`site_config/_sites.py` / `site_config/_profiles.py` / `config/site_capabilities.yaml`；
另 v1 硬路由 `engine/_constants.py`（`DB50` → `cqis` 优先）与 `search_strategy.ADAPTER_TYPE_MAP`
（`db50` → `cqis`）。

**v2 路由现状（按「零路由改动」方案）**：`cqis` 在 `site_capabilities.yaml` 声明 `supported_types: [DB]`
（`_extract_std_type` 对 `DB50/T` 统一产出 `DB`），与 `dbba` 同属 L1，`dbba` 在前、`cqis` 紧随：
`DB50/T 950-2026 → ['dbba', 'cqis']`。**省份精准粒度**（让 `cqis` 在 DB50 查询中排首位）是待决项，
需 v2 支持省份粒度（约 0.25–0.5 人日），见 `docs/plans/2026-11-24-p2-adapter-recon-summary.md` §4。

**回归锚点**：`tests/test_cqis.py`（12 例，全部基于 `tests/fixtures/cqis_sample.json` 的真实响应）；
真实冒烟 `scripts/smoke_test_cqis.py`（本地可跑，CI 不跑）。

## 新增 API Webstore 适配器 `api_webstore`（2026-11-24，P2 批次 A2）

**站点**：`https://www.apiwebstore.org/`（美国石油学会标准在线商店）。
**为何值得接**：API 标准（`API STD/SPEC/RP/TR`）此前只能落到 `iso_gov` 兜底，
而官方商店是**权威源**且元数据完整（状态/版次/发布日期/归口委员会）。

**接口形态（实测，非推断）**：真实搜索接口是 **Coveo Search**：
`POST https://platform.cloud.coveo.com/rest/search/v2?organizationId=<orgId>`，JSON body。

| 用途 | 查询式 | 实测 |
|---|---|---|
| 精确检索 | `aq='@productcode=="<code>" @producttype=="Standard"'` | `610/6D/5CT/579-1/2A-WSD/938-C/Q1` 各 1 条 |
| 兜底检索 | `q=<原查询>` + `aq='@producttype=="Standard"'` | `q="API 610"` 1110 条 → 过滤后 897 |
| 分页 | `firstResult` + `numberOfResults` | offset 型，无重叠 |

**关键坑（已落进适配器与测试）**：
1. **`token` 是唯一门槛**：无 token/假 token 均 401。token（`xx…`，公开 search token，非用户凭据）
   藏在公开前端 `bundle` 里；适配器在 401 时**自动从 `bundle` 重新解析并重试一次**（`_refresh_token`），
   自愈失败才返回空并打 `warning`；
2. `publisheddate` 是 `MM/DD/YYYY`，需转 ISO；无实施/废止日期、无代替关系；
3. 索引**只保留每个 `productcode` 的最新版**（历史版查询会回落为 newer、判 `newer`）；
4. `type` 取值 `STD/SPEC/RP/TR`，`standard_number` 重建为 `API <type> <code>-<year>`。

**路由**：`_extract_std_type("API STD 610-2026")` → `API`；
`site_capabilities.yaml` 声明 `supported_types: [API]`（L1）→
`API STD 610-2026 → ['api_webstore']`；v1 硬路由 `CODE_ROUTES["API"] = [api_webstore, iso_gov, csres]`，
`ADAPTER_TYPE_MAP["api"]` 的 primary 由 `iso_gov` 改为 `api_webstore`。

**回归锚点**：`tests/test_api_webstore.py`（23 例，基于真实响应 fixture，含 token 自愈、401 重试、
自由文本回退全文检索）；真实冒烟 `scripts/smoke_test_api_webstore.py`（CI 不跑）。

**未做**：ASME（同为 P2 批次 B，需先做 designator 归一化；其依赖的 P1 拆号修复已合入）。

## 新增 ASME 适配器 `asme`（2026-11-24，P2 批次 B1）

**站点**：`https://www.asme.org/`（ASME 官方商品目录，标准元数据权威源）。
**为何值得接**：ASME 标准此前只能落 `iso_gov` 兜底；且 P1-7.1 报告指出
`ASME B16.5` 在旧解析器下被拆成 `ASMEB1/6/5`（自 mismatch）——**P1 拆号修复已合入 `9e884765`**，
本适配器是它的下游消费方。

**接口形态（实测）**：`GET https://www.asme.org/api/products?type=Codes-Standards&fullDesignator=<designator>`
→ `total/results[]`。实测命中：`B16.5` / `B31.3` / `BPVC.VIII.1` / `PTC 4` / `CSD-1` / `Y14.5` /
`A112.18.1/CSA B125.1`；`ZZZ99.9` → `total=0`（空结果行为正常）。无需登录/cookie/验证码。

**designator 归一化（本适配器核心逻辑）**：商品目录要求**精确** designator：

| 输入 | 归一化 |
|---|---|
| `ASME B16.5-2025` | `B16.5` |
| `ASME BPVC.VIII.1-2025` | `BPVC.VIII.1` |
| `ASME BPVC Section VIII Div.1-2021` | `BPVC.VIII.1` |
| `ASME BPVC Section II Part D` | `BPVC.II.D`（目录中细分为 `.C`/`.M`，精确查空时自动补查） |
| `ASME PTC 4-2013` / `ASME Y14.5-2018` | `PTC 4` / `Y14.5` |

归一化正则**必须整串锚定**：早期版本用 `search` 把 `BPVC.IX` 里的 `V` 误当罗马数字 → `BPVC.V`（已修，测试锁定）。

**字段缺口与推断口径**：
- **无 `status` 字段** → 按「请求年份 vs `DesignatorYear`」推断：同版/无年份→现行；
  请求更旧年份（目录只索引最新版）→ 被代替（`Status.SUPERSEDED`）；
- `PublishDate` 恒为 `0001-01-01`（不可用）→ `publish_date` 只用 `DesignatorYear`；
- 无实施/废止日期、无代替关系、无归口单位。

**路由**：`_extract_std_type("ASME B16.5-2025")` → `ASME`；
`site_capabilities.yaml` 声明 `supported_types: [ASME]`（L1）→
`ASME B16.5-2025 → ['asme']`；v1 `CODE_ROUTES["ASME"]`、`ADAPTER_TYPE_MAP["asme"]`
的 primary 由 `iso_gov` 改为 `asme`。

**回归锚点**：`tests/test_asme.py`（20 例：归一化 8 形态、真实 fixture 字段映射、
旧年份→被代替、`BPVC.II.D`→`.C`/`.M` 补查、5 个网络异常分支）；
真实冒烟 `scripts/smoke_test_asme.py`（4 个真实 designator，CI 不跑）。

## P2 批次 B2：团体标准与能源标准适配器补齐（2026-11-24）

依据 `docs/plans/2026-11-24-p2-recon-existing.md` 对 `ttbz`/`energy` 的评估结论。

### ttbz（全国团体标准信息平台）—— 原实现按标准号查询**恒为 0 条**

真实接口与站点前端（`standard.html` 的 `params` 构造）实测：

| 问题 | 实证 | 修法 |
|---|---|---|
| **参数用错**（不可用级） | `standardName` 是**名称**过滤；传标准号（如 `T/BSCA 0006—2026`）→ `total=0` | 改用 **`standardNo`**（站点前端 `params.standardNo`，前缀/模糊匹配），再用 `match_result` 选精确项 |
| **缺会话引导** | 直接 `POST` 接口 → **403「访问受限」** | 首次请求前 `GET standard.html` 取 `JSESSIONID`（`_ensure_session`，失败不阻断） |
| **只取首页** | 原实现 `pageSize=20` 单页 | 最多 `MAX_PAGES=3` 页；**命中 exact 或到达 total 即停** |
| **字段缺映射** | 真实响应含 `abolishDate` | 映射到 `abolition_date`；`replaces` 接口不返回 → **留空不臆造**（文档已注明） |

**实测效果**：`T/BSCA 0006—2026` 从 **0 条 → 20 条候选且首条为 exact**；`T/CECS → 60 条`（3 页上限）。
**真实响应 fixture**：`tests/fixtures/ttbz_sample.json`（2026-11-24 实测冻结，未人工构造）。
**冒烟**：`scripts/smoke_test_ttbz.py`（真实网络，`T/BSCA`/`T/CECS 2355—2026` 两组）。

### energy（能源标准平台）—— 三处结构性缺陷

| 问题 | 实证 | 修法 |
|---|---|---|
| **冒烟脚本必崩** | `smoke_test_energy.py:33` 引用不存在的 `adapter.API_URL` → `AttributeError` | 改 `adapter.get_search_url()` |
| **未验证域名 fallback** | `https://energy.nbse.org.cn:18080` 从未实测可达，且与固定 `Host` 头矛盾（会拿到错误主机响应），站点故障时白等 15 秒 | **删除**该 fallback，只保留同主机 `HTTP` 降级 |
| **多页/解析失败/fallback 无用例** | 旧 fixture `total=3` 从不进第 2 页 | 新增 `tests/test_energy_pagination.py`（翻页 3 例 + fallback 3 例 + 解析失败/年份回退 3 例） |

**真实响应 fixture**：`tests/fixtures/energy_sample.json` 已替换为 **2026-11-24 实测**数据
（现行/废止/即将实施 三种状态各 1 条，原文件为手工构造 `stdId=10001~10003`）。
**冒烟**：`scripts/smoke_test_energy.py` **真实网络通过**（19 项检查）。

### 回归锚点
`tests/test_ttbz.py`（19 例：参数/会话引导/分页/字段/异常）、
`tests/test_energy_pagination.py`（9 例）、`tests/test_energy.py`（14 例，真实 fixture）、
`tests/test_adapters.py` 的 TTBZ 段（14 例，保持绿）。

## 适配器 HTTP 纪律与默认参数修正（2026-11-25，第三轮深扫）

方向 C 第三轮深扫（口径：HTTP 超时 / 资源泄漏 / 可变默认参数 / 裸 except / 锁纪律）发现并修 3 处：

| 位置 | 问题 | 影响 | 修法 |
|---|---|---|---|
| `adapters/nrsis.py` 查询调用 | **缺 `timeout`** | 站点不响应时请求**无限挂起**，外层的指数退避重试也会一起挂 | 补 `timeout=15` |
| `adapters/ahbz.py::_search` | 每次查询 `requests.Session()` 且**从不关闭** | 每次查询泄漏一个连接池 | 改 `with requests.Session()`（响应体已在 `_search_single` 内读完） |
| `adapters/base.py::_try_exact_search` | `accepted_statuses: set = {"exact"}` **可变默认参数** | 潜在跨调用共享可变对象（当前只读，未触发） | 默认改 `None` + 函数内构造 |

**回归**：`tests/unit/query/test_adapter_http_discipline.py`（5 例：timeout 必填、
Session 必须 `with` 关闭、默认参数为 `None`、默认口径仍只接受 exact）。

**同轮复核后判定不改**（详见 `docs/plans/2026-11-25-deep-scan3.md`）：
`network.py` 的 `safe_raw_*` 用 `with Session`（已关闭）；`announcement/base.py` 有
`owns_session` + finally 关闭；各适配器 `__init__` 内建的 Session/Client 是长生命周期实例，正常。

## 查询 target 构造统一 + BPVC 变体修复（2026-11-25，批次10 / P1-7.1 B-12）

已查阅：`docs/plans/2026-11-25-p1-api-refresh.md` §3.2 R1（16 条样本仅 4/16 生成期望
designator/productcode、BPVC 全 miss）；`docs/plans/2026-11-24-p1-api-asme-gap.md` §4 G8。

- **唯一 target 构造**：`search_strategy.build_query_target` 委托编号表示层
  （`core.std_number_format.format_standard_number`），`BaseAdapter.query_with_strategy`、
  `BaseAdapter._search_progressive`、`SingleQueryHandler._query_one` 三处共用；
  修复 `code prefix+number+suffix+part-year` 直接粘连、`year=0` 追加 `-0`、忽略 `num_suffix`。
- **`num_suffix` 透传**：`query_with_strategy(..., num_suffix=...)` 已在生产链路接通
  （`_query_subsystem` 七元组 → `_batch` → `_single._query_one` / `_query_one_v2` →
  `_step_query_adapters` → 适配器），`API 6D` 这类后缀不再在查询时丢失。
- **BPVC 代号变体**：`build_code_variants` 增加 `part` 参数，ASME 罗马卷号变体改为点号写法
  `ASME BPVC.VIII.1-2025`（修复前把卷号当分册号生成 `BPVC VIII.8`）。
- **路由代号归一化**：`engine/_constants.normalize_route_code` 把历史脏代号
  `ASMEPTC`/`ASMECSD`/`ASME PTC` 归一为 `ASME`，`_resolve_base_route` 先归一化再查
  `CODE_ROUTES`，避免落通用国外兜底链 `_FOREIGN_FALLBACK`（应走 `asme` 站点）。

**回归锚点**：`tests/unit/query/test_query_target_construction.py`、
`tests/query/engine/test_single_v2_route.py`（`num_suffix` 透传 2 例）、`tests/test_query.py`。
