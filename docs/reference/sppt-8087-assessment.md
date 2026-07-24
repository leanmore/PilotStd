# SPPT 8087 地方标准平台探测记录

日期: 2026-07-24 | 状态: 初步探测完成，待正式立项

## 结论

**8087 与 8086 不同构**，不能简单复用 SPPTAdapter 替换 `accessData` 参数。

## 证据

| 项目 | 8086（国标） | 8087（地方标准） |
|------|-------------|-----------------|
| 首页 | 相同 625B 自动 POST form | 相同 |
| `accessData` | `gj` | `df` |
| 搜索参数 | `keyword`/`isLength`/`num_tn` | `query`/`pageIndex`/`standard_code`/`status` |
| API 响应 | JSON 数组 | **返回 HTML 重定向页**（即使带 session cookie） |
| 额外字段 | 无 | `s_impl_date`/`e_impl_date`/`startTime`/`endTime` |

## 推测

8087 可能使用不同的后端框架（非 8086 的 jQuery AJAX + JSON 模式），需要浏览器 DevTools 抓包确认真实数据接口。

## 建议

正式立项时安排 0.5 人天，使用 Playwright 打开 8087 页面，从 Network 面板捕获真实 XHR 请求。
