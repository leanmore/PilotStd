# 适配器开发指南

## 站点架构差异表（Q22 系列实战总结）

五个站点，五种完全不同的技术架构。没有任何两个可以复用同一套解析策略。

| 适配器 | 站点 | 架构类型 | 核心特征 | 编码 | 分页 |
|--------|------|----------|---------|------|------|
| TTBZ | 团体标准平台 | REST API | JSON 直连，结构化程度最高 | UTF-8 | POST pageNum |
| MEE | 生态环境部子栏目 | 服务端渲染列表 | 政务 CMS 静态 `<li>` 列表，GET 参数驱动 | UTF-8 | GET page |
| NRSIS | 自然资源标准平台 | 服务端渲染表格 | Portal 框架内嵌，GBK 编码 | GBK | GET pageNo |
| JTST | 交通运输部子功能 | iframe + 卡片式 HTML | Hash 路由门户内嵌，GET 分页 | UTF-8 | GET iframe |
| CCSN | 工程建设标准化协会 | GET 跳转 + ViewState 分页 | WebForms 混合模式，顺序翻页，双表格干扰 | GBK | POST btnNext |

## 核心原则

### 1. 永远不要根据域名/后缀猜测技术栈

- `.aspx` 不等于 POST 表单搜索（CCSN 实际是 GET `?KeyWord=`）
- `#/` 不等于 REST API（需抓包确认）
- 深层路径不等于静态页
- 每个政府/协会站点是独立历史产物，必须逐个逆向

### 2. Task 0 是不可压缩的

Q22-05 若跳过 Task 0 直接按计划编码，产出物将 100% 不可用：

| 计划假设 | 实际 | 后果 |
|----------|------|------|
| POST + ViewState 搜索 | GET `?KeyWord=` | 请求永远失败 |
| `__EVENTVALIDATION` 存在 | 不存在 | 参数缺失报错 |
| 标准编号在列 0 | 在列 2 | 解析到表头文字 |
| 有状态列 | 无 | 字段为空 |
| `__EVENTARGUMENT=Page$2` | `btnNext` 顺序翻页 | 分页跳转失败 |

### 3. 先找真实 API，再定方案

执行顺序：
1. 浏览器打开目标页面，F12 → Network → XHR/Fetch
2. 找到真实数据接口（可能是 iframe、AJAX、JS 跳转）
3. curl 验证接口可达性
4. 根据**实际**接口写计划
5. 根据计划写测试 → 实现

禁止：看一眼 URL → 脑补技术栈 → 写代码

### 4. 编码检测

- 先 `curl -o` 保存为二进制
- 检查 `<meta charset>` 或响应头 `Content-Type`
- 常见：UTF-8（多数）、GBK（老旧政府站）
- 不要假设 UTF-8

### 5. 新适配器检查清单

- [ ] 真实 API 端点已 curl 验证
- [ ] 编码已确认（非假设）
- [ ] 搜索结果 DOM 结构已截图/保存
- [ ] 字段映射已用真实数据验证（≥3 条采样）
- [ ] 分页机制已确认（GET/POST/iframe/ViewState）
- [ ] 空结果行为已测试
- [ ] 特殊参数已记录（tid/channelid/op/repeFlag）
- [ ] Fixture 文件已提交
