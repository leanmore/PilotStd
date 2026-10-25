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

## 相关文档

- [管理模块](manager.md) — 适配器调用方（`StandardManager` 门面）
- [查询引擎](../../query/README.md) — 批量查询、路由、配额管理
