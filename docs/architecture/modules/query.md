# 模块文档：查询适配器（Query Adapters）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/query/adapters/` |
| G-031 映射 | `pilotstd/query/adapters/` |
| 核心类 | `BaseAdapter` (ABC) |
| 适配器数 | 8（7 生产 + 1 Mock） |
| 总行数 | ~1,666 |
| 状态 | 活跃 |

## 模块职责

封装各标准查询网站的 API 调用，统一为 `QueryResult` 输出。每个适配器负责一个站点的搜索请求构造、响应解析、结果标准化。基类提供渐进式搜索策略和评分机制，子类只需实现站点特定的 `_search` 或 `_search_candidates`。

## 适配器清单

| 适配器 | 类名 | 站点 | 行数 |
|--------|------|------|------|
| 国家标准 | `StdGovAdapter` | openstd.samr.gov.cn | 190 |
| 南京标准 | `Njbz365Adapter` | njbz365.cn | 385 |
| 标准资源网 | `CsresAdapter` | csres.com | 252 |
| 安徽标准 | `AhbzAdapter` | ahbz.org.cn | 156 |
| 河北标准 | `HbbaAdapter` | hbba.org.cn | 163 |
| 电标备案 | `DbbaAdapter` | dbba.sacinfo.org.cn | 98 |
| ISO 官网 | `IsoGovAdapter` | iso.org | 111 |
| Mock | `MockQueryAdapter` | — (测试用) | 93 |

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
- [查询引擎](../query/README.md) — 批量查询、路由、配额管理
