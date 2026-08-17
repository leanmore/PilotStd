# gongbiaoku 搜索逻辑排查报告

> 排查日期：2026-08-17
> 排查对象：[pilotstd/query/adapters/gongbiaoku.py](../pilotstd/query/adapters/gongbiaoku.py)
> 触发背景：v1.1 分类分析中 ISO 试查询（"ISO 9001" / "IEC 62304"）返回无关国标（GB 消防/建筑）

## 一、排查结论（TL;DR）

**根因类型：B — 数据源本身不支持国际标准（后端数据库无 ISO/IEC 数据）**

gongbiaoku 适配器代码逻辑无 bug，搜索词被正确透传给后端；问题出在 gongbiaoku.com 后端对国际标准关键词的模糊匹配兜底，返回了无关国标。

对应处理：`search_reliability = "medium"`，notes 注明数据源限制。

## 二、代码分析

### 2.1 搜索主入口

[`query_standards()`](pilotstd/query/adapters/gongbiaoku.py#L61-L90) 是搜索主入口，链路如下：

1. **关键词提取**（[gongbiaoku.py:63](pilotstd/query/adapters/gongbiaoku.py#L63)）：`keyword = standard_number.strip()`，仅去除首尾空白，不做前缀拆分、过滤或转换。
2. **请求参数组装**（[gongbiaoku.py:67](pilotstd/query/adapters/gongbiaoku.py#L67)）：`params = {"txt": keyword}`，关键词作为 `txt` 参数原样传递。
3. **请求发送**（[gongbiaoku.py:70](pilotstd/query/adapters/gongbiaoku.py#L70)）：`self._client.get(self.get_search_url(), params=params, timeout=15)`。`get_search_url()` 返回 [site_config.py:427](pilotstd/query/site_config.py#L427) 的 `search_url="https://www.gongbiaoku.com/search"`，实际请求为 `https://www.gongbiaoku.com/search?txt=ISO 9001`（httpx 自动做 URL 编码）。

**分析结论**：搜索词 "ISO 9001" 被原样、正确地传递给后端，无截断、无编码错误、无前缀丢失。排除类型 A（搜索逻辑 Bug）。

### 2.2 关键词拼接/编码与前缀处理

- 整个 gongbiaoku.py **无任何对 ISO/IEC/IEEE/国际 前缀的特殊处理逻辑**（grep 确认零匹配）。
- 对比 [iso_gov.py:58](pilotstd/query/adapters/iso_gov.py#L58) 有硬过滤 `if not any(kw in search_term.upper() for kw in ("ISO", "IEC")): return []`——支持国际标准的站点会主动识别并拦截国际标准关键词；gongbiaoku 无此类逻辑，对国际标准关键词"不设防"地透传给后端。

**分析结论**：gongbiaoku 在代码层面没有引入任何会导致国际标准关键词被篡改、截断或误匹配的逻辑。

### 2.3 结果解析

[`_parse_ul()`](pilotstd/query/adapters/gongbiaoku.py#L125-L161)：

1. 用 `_LABEL_RE`（[gongbiaoku.py:26](pilotstd/query/adapters/gongbiaoku.py#L26)）匹配 `<li>` 文本中的"标准名称/标准编号/发布日期/实施日期"四个字段。
2. 调用 [`match_result()`](pilotstd/query/search_strategy.py#L145-L174) 判断匹配状态：先精确解析标准编号逐字段比对（[search_strategy.py:170](pilotstd/query/search_strategy.py#L170)），失败则模糊回退（[search_strategy.py:174](pilotstd/query/search_strategy.py#L174)）。

**分析结论**：解析逻辑是通用的标准字段解析，对任何标准（国内或国际）一视同仁，无"把 ISO 结果解析成国标"的特殊 bug。试查询返回的"GB 消防/建筑"是后端返回的原始结果，不是解析错误。排除类型 C（解析逻辑 Bug）。

## 三、根因判断

排除 A、C 后，综合以下证据判定根因为类型 B：

1. 适配器代码无 bug（见 2.1、2.2）。
2. 试查询结果（v1.1）："ISO 9001" / "IEC 62304" 返回无关国标（GB 消防/建筑），说明后端对国际标准关键词做了模糊匹配兜底，而非返回空结果或正确国际标准。
3. site_config.py 中 gongbiaoku 的配置佐证：
   - `std_prefixes: []`（[site_config.py:196](pilotstd/query/site_config.py#L196)）——未声明任何标准前缀，包括国际标准。
   - `reliability: "low"`（[site_config.py:198](pilotstd/query/site_config.py#L198)）——已标记低可靠性。
4. 域名定位佐证：gongbiaoku.com（工标库）定位为国内工程标准库，无国际标准收录迹象。

**最终判定：类型 B — 数据源本身不支持国际标准（后端数据库无 ISO/IEC 数据），模糊匹配兜底返回无关国标。**

## 四、后续建议（本次不执行修复）

类型 B 属数据源能力边界，无法通过修改适配器代码修复。缓解措施：

1. **路由层隔离（已实现）**：[search_strategy.py:252-294](pilotstd/query/search_strategy.py#L252-L294) 的 `ADAPTER_TYPE_MAP` 中，gongbiaoku 仅在 `construction_std` 作为 primary，未出现在 `iso`/`iec`/`gb`/`industry` 的 chain 里，国际标准查询不会被路由到 gongbiaoku。
2. **能力模型标记（本次产出）**：site_capabilities.yaml 中 gongbiaoku 标记 `search_reliability=medium` + notes 数据源限制，供后续路由评分器避免将国际标准查询分配给 gongbiaoku。

## 五、验证

- 代码行号引用经逐行核对（gongbiaoku.py:61-90、125-161；site_config.py:196-198、427；search_strategy.py:145-174、252-294；iso_gov.py:58）。
- 本次仅排查 + 更新能力模型，未修改任何适配器代码。
