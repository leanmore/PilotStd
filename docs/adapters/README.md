# 适配器维护清单

> 最后更新：2026-07-27 | 22 个适配器（含 1 个 Mock 测试适配器）

## 完整清单

注册表：[pilotstd/query/adapters/registry.py:32-54](pilotstd/query/adapters/registry.py#L32-L54)
配置：[pilotstd/query/site_config.py:8-87](pilotstd/query/site_config.py#L8-L87)

| # | site_name | 适配器类 | 类型 | 日配额 | 状态 | 备注 |
|---|-----------|---------|------|--------|------|------|
| 1 | ahbz | AhbzAdapter | 综合 | 800 | 活跃 | GB首选(30%), 国外主站 |
| 2 | std_gov | StdGovAdapter | 国标 | 800 | 活跃 | GB主力(40%), 9类兜底 |
| 3 | njbz365 | Njbz365Adapter | 综合 | 800 | 活跃 | JWT/CSRF会话, 全类型 |
| 4 | csres | CsresAdapter | 兜底 | 200 | **受限** | 24h硬冷却, 最终兜底 |
| 5 | hbba | HbbaAdapter | 行业 | 800 | 活跃 | 冷却15min最长 |
| 6 | dbba | DbbaAdapter | 地标 | 800 | 活跃 | 全国各省地标 |
| 7 | iso_gov | IsoGovAdapter | 国际 | 800 | 活跃 | ISO/IEC/ASTM/ASME |
| 8 | cssn | CSSNAdapter | 行业 | 1000 | 活跃 | 行业首选, 10000上限 |
| 9 | miit | MIITAdapter | 行业 | 300 | **受限** | 15条截断, 无翻页 |
| 10 | mee | MEEAdapter | 环境 | 500 | 活跃 | 生态环境专用 |
| 11 | nrsis | NRSISAdapter | 自然资源 | 300 | 活跃 | 3次指数退避重试 |
| 12 | jtst | JTSTAdapter | 交通 | 500 | 活跃 | 交通运输专用 |
| 13 | ccsn | CCSNAdapter | 工程 | 500 | 活跃 | ASP.NET ViewState |
| 14 | jjg | JJGAdapter | 计量 | 1000 | 活跃 | 配额最高, 20页 |
| 15 | sppt | SPPTAdapter | 食品 | 500 | 活跃 | 自签名SSL |
| 16 | sppt_local | SPPTLocalAdapter | 食品地标 | 300 | **待验证** | ≤6条, 无翻页, SSR HTML |
| 17 | gongbiaoku | GongBiaoKuAdapter | 工程 | 500 | 活跃 | 无状态字段 |
| 18 | energy | EnergyAdapter | 能源 | 100 | **待验证** | 纯IP, 配额最低 |
| 19 | tdpress | TDPressAdapter | 铁路 | 500 | 活跃 | EasyUI JSON |
| 20 | ncha | NCHAAdapter | 文保 | 500 | 活跃 | WW/WW/T 主站 |
| 21 | ttbz | TTBZAdapter | 团体 | 400 | 活跃 | 冷却1s极短 |
| — | mock | MockQueryAdapter | 测试 | — | 仅测试 | 不注册到 ALL_ADAPTERS |

## 状态判定标准（量化定义）

| 状态 | 判定条件 |
|------|----------|
| **活跃** | 近30天有成功请求，配额使用率 > 50%，无持续冷却 |
| **受限** | 配额使用率 < 50% 或频繁触发冷却（近7天冷却 > 3次） |
| **待验证** | 上次成功验证 > 90天，或有已知功能缺陷未修复 |
| **待废弃** | 连续失败 > 7天且无修复计划 |

## 需定期验证的适配器

| 适配器 | 验证方法 | 频率 | 原因 |
|--------|----------|------|------|
| **energy** | `curl -k https://114.251.111.103:18080/portal` | 每周 | 纯IP站点，IP迁移/封禁风险 |
| **energy** | `curl -k https://energy.nbse.org.cn:18080/portal` | 每月 | 域名待验证 |
| **miit** | Playwright 侦察翻页参数 | 每季 | API 参数可能随网站改版变更 |
| **sppt_local** | 正则提取 dataList 验证 | 每月 | SSR HTML 结构可能随前端构建变更 |
| **csres** | `curl http://www.csres.com` | 每日(监控) | 24h硬冷却，最终兜底不可用影响最大 |
| **nrsis** | 指数退避重试有效性 | 每季 | 内置3次重试，需确认仍有效 |

## 新增适配器标准流程

### 1. 开发规范

```
1. 创建 adapter 文件: pilotstd/query/adapters/{name}.py
   - 继承 BaseAdapter [src: base.py:21]
   - 实现 site_name, site_label property
   - 实现 _search_candidates() 或 _fetch_candidates()
   - 实现 _parse_result() 映射到 QueryResult

2. 实现约束:
   - 使用 httpx.Client 或 requests.Session
   - 网络请求超时 ≤ 15s
   - 异常捕获后返回 [] 或 None，禁止传播异常
   - 记录 logger.debug/error（非 print）
```

### 2. 注册

```
3. 在 registry.py ALL_ADAPTERS 添加条目
4. 在 site_config.py 添加 SiteState 配置
   - max_requests: 建议 50-200
   - daily_limit: 建议 300-1000
   - cooldown_seconds: 建议 2-600
5. 在 search_strategy.py ADAPTER_TYPE_MAP 添加路由条目
   - 指定 primary 和 fallback
6. 在 announce_types.py 添加 source_site 映射（如是公告类）
```

### 3. 测试要求

```
7. 单元测试: tests/test_{name}.py
   - mock HTTP 响应
   - 覆盖: 正常结果、空结果、网络异常、JSON解析失败、截断
8. 冒烟测试: scripts/smoke_test_{name}.py
   - 真实网络请求
   - 验证 API 仍可访问
```

### 4. 文档更新

```
9. 本文档更新适配器清单
10. docs/query/README.md 更新路由配置说明（如路由角色变更）
11. docs/configuration/README.md 更新配额默认值（如有）
```

### 5. 上线检查清单

| # | 检查项 |
|---|--------|
| □ | ruff check 通过 |
| □ | 单元测试通过 |
| □ | 冒烟测试通过 |
| □ | ADAPTER_TYPE_MAP 路由正确 |
| □ | site_config 配额合理（不与其他适配器冲突） |
| □ | 本文档状态列已更新 |
