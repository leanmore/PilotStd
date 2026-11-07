# 15 · 查询适配器逐站矩阵（21 站）

> 来源：`pilotstd/query/adapters/registry.py` + `site_config/_profiles.py` + `site_config/_sites.py`，2026-11-07 实测。
> 仅列“站点能力/配额/路由画像”，不复制每个适配器的解析代码；逐站解析细节仍是待补项。

| # | 适配器 | 站点/平台 | 支持代号 | 行业 | 可靠性/权重/角色 | 日限 / 单批 / 间隔 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | `ahbz` | 安徽标准化信息服务平台 | GB, GB/T, DB | — | high/55/primary | 800 / 200 / 0.5s | 安徽平台；GB/DB 通用。 |
| 2 | `ccsn` | 中国工程建设标准化协会 | CECS | 工程建设 | medium/50/primary | 500 / 50 / 1.0s | 工程建设 CECS。 |
| 3 | `csres` | 工标网 | GB, GB/T, GB/Z | — | low/30/background | 200 / 50 / 2.0s |  |
| 4 | `cssn` | 中国标准服务网 | GB, GB/T | — | high/60/primary | 1000 / 100 / 0.3s |  |
| 5 | `dbba` | 地方标准信息服务平台 | DB | — | high/55/primary | 800 / 200 / 0.5s | 地方标准 DB。 |
| 6 | `energy` | 能源标准信息服务平台 | NB, DL | 能源 | low/50/primary | 100 / 30 / 0.5s |  |
| 7 | `gongbiaoku` | 工标库 | — | — | low/40/primary | 500 / 50 / 0.5s | 无标准前缀、通用站、低可靠；用于兜底/模糊。 |
| 8 | `hbba` | 行业标准信息服务平台 | SH, NB, HG, JB, YB, SY, CB, QB, FZ | — | high/55/primary | 800 / 400 / 0.5s | 多行业代号；行业标准主站之一。 |
| 9 | `iso_gov` | ISO/IEC国际标准（全国标准平台子站） | ISO, IEC, IEEE | — | high/60/primary | 800 / 200 / 0.5s | v2 YAML `is_international=false`，所以 v2 对 ISO 会走 njbz365；这是能力模型数据缺口。 |
| 10 | `jjg` | 国家计量技术规范全文公开系统 | JJG, JJF | 计量 | high/60/primary | 1000 / 100 / 0.3s |  |
| 11 | `jtst` | 交通运输部标准查询 | JT, JTG, JTS | 交通 | medium/55/primary | 500 / 50 / 0.5s |  |
| 12 | `mee` | 生态环境部标准查询 | HJ, GB | 环保 | medium/55/primary | 500 / 50 / 0.5s | v1 画像仍含 GB；v2 YAML 已改为 [HJ]。v1 扁平评分可能把 GB 误路由到 mee。 |
| 13 | `miit` | 工信部行业标准查询 | YD, SJ | 工业 | medium/55/primary | 300 / 50 / 0.5s |  |
| 14 | `ncha` | 文物保护标准查询 | WW | 文物 | medium/55/primary | 500 / 50 / 0.5s |  |
| 15 | `njbz365` | 南京标准公共服务平台 | — | — | medium/45/primary | 800 / 200 / 3.0s | 通用站，间隔 3s；v2 常作为国际/模糊兜底。 |
| 16 | `nrsis` | 自然资源标准信息服务平台 | DZ, TD | 自然资源 | medium/55/primary | 300 / 30 / 0.5s |  |
| 17 | `sppt` | 食品安全国家标准数据检索平台 | GB | 食品 | medium/55/primary | 500 / 50 / 0.5s |  |
| 18 | `sppt_local` | 食品安全地方标准数据检索平台 | DB | 食品 | medium/50/primary | 300 / 30 / 0.5s |  |
| 19 | `std_gov` | 全国标准信息公共服务平台 | GB, GB/T, GB/Z | — | high/70/primary | 800 / 400 / 0.3s | 国标主站；hcno/pid 不同，下载侧不读它的 pid。 |
| 20 | `tdpress` | 铁路标准信息服务平台 | TB | 铁路 | medium/55/primary | 500 / 50 / 0.5s |  |
| 21 | `ttbz` | 全国团体标准信息平台 | T/ | — | medium/50/primary | 400 / 100 / 0.5s | 团体标准 T/ 前缀。 |

## 逐站请求模式/坑（细分）

| 适配器 | 请求/解析 | 已知坑 |
|---|---|---|
| `ahbz` | POST JSON | 免费/免鉴权；改后跑本地 E2E |
| `ccsn` | GET + HTML；分页 POST ViewState | 需逐页提 `__VIEWSTATE` |
| `csres` | HTML 多页 + 详情 | **仅 HTTP**，HTTPS 被拒；多页/详情 |
| `cssn` | JSON API GET | 分页 `?page=N`，用 `next` 判终 |
| `dbba` | POST form-urlencoded | 地方标准；改后跑 E2E |
| `energy` | JSON GET（Bootstrap Table） | **纯 IP + 自签名证书**，IP 变更风险高 |
| `gongbiaoku` | HTML | 共享 SSL context；无标准前缀 |
| `hbba` | POST `stdQueryList` | 不支持 year 独立过滤；完整号无结果时去年份重试 |
| `iso_gov` | GET HTML | 去 `<sacinfo>` 高亮；v2 能力模型标为非国际 |
| `jjg` | JSON GET | 参数大小写敏感 |
| `jtst` | iframe HTML 卡片 | 不是表格；卡片式布局 |
| `mee` | HTML 片段 | BeautifulSoup + lxml；画像含 GB |
| `miit` | POST form | 最多 15 条、无分页；参数拼写 `stadardNum` |
| `ncha` | POST JSON | 端口 9005；`itemCode` 缺失=全部 |
| `njbz365` | 会话 + CSRF + 签名 | 有独立 SessionManager；最复杂 |
| `nrsis` | GET HTML 表格 | 正则提“共 X 条”；指数退避 |
| `sppt` | JSON GET | 自签名 SSL；混合公告/标准，需过滤 |
| `sppt_local` | SSR HTML 内嵌 Vue JSON | 分页被服务端忽略，仅首页 ≤6 条 |
| `std_gov` | HTML 搜索/详情 | 新版详情页；pid ≠ hcno |
| `tdpress` | JSON GET | 端点拼写 `queryFomePage`（不是 Form） |
| `ttbz` | POST JSON | 不支持 status 独立过滤 |

## 路由结论

- v1 默认：评分器动态链 + `CODE_ROUTES` 兜底；`GB` 的兜底链可能包含 `mee`（因其画像含 GB）。
- v2 灰度：`ROUTING_ENGINE_VERSION=v2`，能力模型读 `config/site_capabilities.yaml`；默认 v1。
- 21 站中：`std_gov`/`hbba`/`dbba`/`njbz365` 等是主力；`csres` 是 background；`gongbiaoku` 低可靠。
- 下载侧仍只有 `openstd_download`（GB 类），与查询站数量无关。

## 待补

- 每站的 `_search`/解析器/fixture 细节；
- 实际命中率、失败率、429/验证码/登录态；
- 各站对“采标/被代替/即将实施”的字段差异。
