# SPPT 8087 地方标准平台 Task 0 评估报告

日期: 2026-07-24 | 状态: Task 0 完成，待适配器立项

## 结论

**8087 与 8086 不同构**，不能简单复用 SPPTAdapter。但已确认可行。

## 架构差异

| 项目 | 8086（国标） | 8087（地方标准） |
|------|-------------|-----------------|
| 数据格式 | JSON 数组（AJAX 响应） | **SSR 嵌入 JSON**（Vue.js `dataList`） |
| 请求方式 | GET `?task=indexSearch&keyword=` | POST `task=index&keyword=` |
| 参数名 | `keyword` | `keyword` |
| `accessData` | `gj` | `df` |
| 分页 | 无需（全量返回） | `pageIndex` 参数（但服务端可能忽略） |
| 字段 | `CODE`/`TITLE`/`PDATE`/`SSRQ` | `standard_code`/`title`/`province`/`id`/`rn` |
| Cookie | 无 | **JSESSIONID**（session cookie, expires=-1） |
| 反爬 | 无 | 5 次连续请求未触发 |

## 数据格式

服务端渲染的 HTML 中嵌入 Vue.js `dataList`：
```json
[{
  "province": "江苏",
  "id": "2051C156-...",
  "title": "食品安全地方标准 即食菜肴",
  "rn": "1",
  "standard_code": "DB S32/003-2025"
}]
```

## 适配器实现要点

1. **请求**: POST `task=index&accessData=df&keyword=X&tabActive=1` 带 JSESSIONID cookie
2. **解析**: 正则提取 `dataList: [{...}]` JSON 数组
3. **字段映射**: `standard_code` → standard_number, `title` → standard_name, `province` → 额外字段
4. **分页**: `pageIndex` 参数效果待确认，首次实现可先取第 1 页
5. **Cookie**: 需保持 JSESSIONID（首次 GET 获取，后续 POST 携带）

## Task 0 检查表

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | Network 全量请求导出 | ✅ HAR + JSON |
| 2 | 隐藏 JSON API | ✅ 已确认：SSR 嵌入，非独立 API |
| 3 | Cookie 来源/有效期 | ✅ JSESSIONID，session cookie |
| 4 | 搜索参数名/方法 | ✅ POST `task=index&keyword=X&accessData=df` |
| 5 | 分页机制 | ⚠️ `pageIndex` 参数存在但效果待验证 |
| 6 | 反爬压力测试 | ✅ 5 次连续请求未触发 |
| 7 | 标准数据提取 | ✅ DB S32/003-2025 等完整字段 |
| 8 | SSL 证书 | ✅ 自签名（与 8086 相同） |

## 工时预估

1 人天：解析 SSR JSON + 注册 + 测试
