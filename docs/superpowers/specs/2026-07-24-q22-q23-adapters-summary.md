# Q22-Q23 适配器开发总结

> 日期：2026-07-24 | 覆盖：14 个新适配器 + 1 个架构重构

## 一、交付清单

| 编号 | 适配器 | 站点 | 架构 | 测试 | 数据量 | 侦查方式 |
|------|--------|------|------|------|--------|---------|
| Q22-01 | TTBZ | 全国团体标准平台 | json_api_post | 10 | 全量 | curl |
| Q22-02 | MEE | 生态环境部 | html_key_value_li | 10 | 分页 | curl |
| Q22-03 | NRSIS | 自然资源标准 | html_table | 12 | 分页(GBK) | curl |
| Q22-04 | JTST | 交通运输部 | iframe_card | 12 | iframe分页 | curl |
| Q22-05 | CCSN | 工程建设标准化 | viewstate | 10 | ViewState分页 | curl |
| Q22-06 | JJG | 计量技术规范 | json_api_get | 9 | GET分页 | curl |
| Q22-07 | SPPT | 食品安全国标(8086) | json_array_filter | 8 | 无需 | curl |
| Q22-08 | SPPT_Local | 食品安全地标(8087) | vue_datalist | 9 | 单页 | curl |
| Q22-09 | GongBiaoKu | 工标库 | html_key_value_ul | 9 | 单页 | curl |
| Q22-10 | Energy | 能源标准平台 | json_api_get | 14 | 分页 | curl→HTTPS修正 |
| Q23-02 | TDPress | 铁路标准平台 | json_api_get | 17 | GET分页 | curl |
| Q23-03 | NCHA | 文物保护标准 | json_api_post | 16 | POST分页 | Playwright(9005端口) |
| Q23-04 | MIIT | 工信部行业标准 | json_api_post_form | 11 | 15条/页 | Playwright(JSL绕过) |
| Q23-05 | CSSN | 中国标准服务网 | json_api_get | 11 | 10000+ | Playwright(JSL绕过) |

**合计：14 种架构，158 个测试，零复用。**

## 二、五站侦查方法论

| 站点 | 侦查方式 | 结果 | 关键发现 |
|------|---------|------|---------|
| cssn.net.cn | Playwright | VIABLE | API 在 JSL 挑战前暴露，无需 Cookie |
| std.miit.gov.cn | Playwright | VIABLE | form-urlencoded POST，`stadardNum` 拼写陷阱 |
| nhc.gov.cn | Playwright headless | BLOCKED | 企业级 WAF 检测 TLS 指纹，39 字节空响应 |
| bz.ncha.gov.cn | Playwright | VIABLE | 后端在 9005 端口，非 80 |
| biaozhun.tdpress.com | curl | VIABLE | jQuery EasyUI，GET 即可 |

**规律**：JSL/CDN 反爬仅保护页面加载，不保护 API 端点。Playwright 的核心价值不是"绕过反爬"，而是"在执行 JS 时自动触发 API 调用暴露端点 URL"。

## 三、架构重构：去硬编码化（FIX-20260724-002）

### 问题
`docker/api/adapter.py` 中 `_ALL_ADAPTER_NAMES` 和 `target_names` 是独立维护的硬编码列表，与 `ADAPTER_TYPE_MAP` 重复。新增适配器需修改 3 处硬编码。

### 修复
```
Before:
  _ALL_ADAPTER_NAMES = ["ahbz","std_gov","hbba","iso_gov","njbz365","csres","dbba"]  # 7个
  target_names = ["ahbz","std_gov","hbba","iso_gov","njbz365","csres","dbba"]        # 7个

After:
  _get_all_query_adapters() → 从 ADAPTER_TYPE_MAP 动态派生 → 21 个全部自动纳入
```

### 新增适配器标准流程（4 步）
1. 创建 `adapters/new_site.py`，定义 `DISPLAY_NAME = "中文名"`
2. 在 `ADAPTER_TYPE_MAP` 注册路由
3. 在 `PROD_PRIORITY` 注册优先级
4. 创建测试 + fixture + 冒烟脚本

不再需要修改任何硬编码列表、前端映射或 API 端点代码。

## 四、关键设计决策

| 决策 | 日期 | 影响 |
|------|------|------|
| `ADAPTER_TYPE_MAP` 作为适配器唯一真实来源 | 2026-07-24 | 消除 4 处硬编码重复 |
| `DISPLAY_NAME` 模块级常量 | 2026-07-24 | 前端自动显示中文名 |
| 日志标签自动派生 `last.upper()[:6]` | 2026-07-24 | 新增适配器日志不丢失 |
| CST 时区显式指定 | 2026-07-24 | 容器 UTC 环境日期不偏移 |
| NHC 卫健委最终放弃 | 2026-07-24 | WAF TLS 指纹检测不可绕过 |

## 五、已知限制

| 项目 | 说明 |
|------|------|
| CSSN count=10000 上限 | API 固定上限，非真实总数 |
| MIIT 15 条/页 | 无分页参数，截断时有 WARNING 日志 |
| NCHA 9005 端口 | 非标准端口，需监控连通性 |
| CSRES 动态 IP | 纯 IP 站点，IP 变更后需手动更新 |

## 六、测试覆盖

```
tests/test_energy.py     14 passed
tests/test_tdpress.py    17 passed
tests/test_ncha.py       16 passed
tests/test_miit.py       11 passed
tests/test_cssn.py       11 passed
G-025 门禁               21 query + 3 announce 全部可导入
```
