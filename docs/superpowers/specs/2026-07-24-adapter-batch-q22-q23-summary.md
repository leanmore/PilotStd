# Q22-Q23 适配器批量开发总结

> 日期：2026-07-24 | 覆盖：14 个新适配器 + 1 个架构重构 | 测试：158 用例

## 一、交付清单

| 编号 | 适配器 | 站点 | 架构类型 | 测试 | 侦查方式 |
|------|--------|------|---------|------|---------|
| Q22-01 | TTBZ | 全国团体标准平台 | JSON API (POST) | 10 | curl |
| Q22-02 | MEE | 生态环境部 | HTML key-value `<li>` | 10 | curl |
| Q22-03 | NRSIS | 自然资源标准 | HTML 表格 (GBK) | 12 | curl |
| Q22-04 | JTST | 交通运输部 | iframe 卡片 HTML | 12 | curl |
| Q22-05 | CCSN | 工程建设标准化协会 | ViewState 分页 | 10 | curl |
| Q22-06 | JJG | 计量技术规范 | JSON API (GET) | 9 | curl |
| Q22-07 | SPPT | 食品安全国标 (8086) | JSON 数组过滤 | 8 | curl |
| Q22-08 | SPPT_Local | 食品安全地标 (8087) | Vue dataList 嵌入 | 9 | curl |
| Q22-09 | GongBiaoKu | 工标库 | HTML `<ul>` 分组 | 9 | curl |
| Q22-10 | Energy | 能源标准平台 | JSON API (GET, 纯IP) | 14 | curl→HTTPS修正 |
| Q23-02 | TDPress | 铁路标准平台 | JSON API (GET) | 17 | curl |
| Q23-03 | NCHA | 文物保护标准 | JSON API (POST, 9005端口) | 16 | Playwright |
| Q23-04 | MIIT | 工信部行业标准 | form-urlencoded POST | 11 | Playwright |
| Q23-05 | CSSN | 中国标准服务网 | JSON API (GET) | 11 | Playwright |

**合计：14 种架构，158 个测试，零复用。**

## 二、五站 Playwright 侦查流程

Q23 阶段对 5 个未知站点执行统一的两阶段侦查：

| 站点 | 第一阶段(curl) | 第二阶段(Playwright) | 最终结论 |
|------|---------------|---------------------|---------|
| cssn.net.cn | JSL 壳 (527B) | API 在 JSL 挑战前暴露 | **VIABLE** |
| std.miit.gov.cn | JSL + Vue SPA | XHR 捕获 form-urlencoded POST | **VIABLE** |
| nhc.gov.cn | 412 WAF | Playwright headless 仍被阻断 | **BLOCKED** |
| bz.ncha.gov.cn | Vue SPA 壳 | 发现 9005 端口后端 | **VIABLE** |
| biaozhun.tdpress.com | jQuery EasyUI | curl 即可用 | **VIABLE** |

**核心规律**：JSL/CDN 反爬仅保护页面加载，不保护 API 端点。Playwright 的价值不是"绕过反爬"，而是"在执行 JS 时自动触发 API 调用，暴露端点 URL"。

**放弃标准**（满足任一即放弃）：
- Playwright headless 仍返回空响应或 WAF 页面
- 搜索 API 需要登录/付费/验证码
- DNS 不存在且无替代域名

## 三、去硬编码化改造（FIX-20260724-002）

**问题**：`docker/api/adapter.py` 中 `_ALL_ADAPTER_NAMES` 和 `target_names` 独立维护，与 `ADAPTER_TYPE_MAP` 重复。新增适配器需改 3 处。

**修复**：从 `ADAPTER_TYPE_MAP` 动态派生全部列表，`ADAPTER_TYPE_MAP` 成为适配器注册的唯一真实来源。

**新增适配器标准流程（4 步）**：
1. 创建 `adapters/new_site.py`，继承 `BaseAdapter`，定义 `DISPLAY_NAME = "中文名"`（≤50 字符）
2. 在 `ADAPTER_TYPE_MAP` 注册路由
3. 在 `PROD_PRIORITY` 注册优先级
4. 创建测试 + fixture + 冒烟脚本

不再需要修改任何硬编码列表、前端映射或 API 端点代码。

## 四、NHC 卫健委放弃结论

nhc.gov.cn 是五站中唯一触发放弃标准的站点：
- 企业级 WAF（Cloudflare + 5秒盾 + 验证码）检测 TLS 指纹
- Playwright headless 返回 39 字节空响应
- 经多轮测试（不同 UA、不同 TLS 配置、不同网络环境）确认不可绕过
- **最终决定：放弃，除非 NHC 更换 WAF 策略**

## 五、关键设计决策

| 决策 | 影响 |
|------|------|
| ADAPTER_TYPE_MAP 作为唯一真实来源 | 消除 4 处硬编码重复 |
| DISPLAY_NAME 模块级常量（≤50字符） | 前端自动显示中文名，API 自动暴露 |
| 日志标签自动派生 `last.upper()[:6]` | 新增适配器日志不丢失 |
| CST 时区显式指定 | 容器 UTC 环境日期不偏移 |
| Cookie cutter 适配器脚手架 | Q22 架构模板化，加速后续开发 |

## 六、已知限制

| 项目 | 说明 |
|------|------|
| CSSN count=10000 上限 | API 固定上限，非真实总数 |
| MIIT 15条/页无分页参数 | 截断时有 WARNING 日志 |
| NCHA 9005 端口 | 非标准端口，需监控连通性 |
| Energy 纯 IP | IP 变更后需手动更新 |
