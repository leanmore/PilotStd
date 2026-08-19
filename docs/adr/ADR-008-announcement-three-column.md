# ADR-008：首页公告三栏分类

- **日期**：2026-Q2
- **状态**：✅ Accepted

## 上下文（Context）

Web 端首页需要展示公告列表，但公告包含不同类型（国家标准 / 行业标准 / 地方标准），
单一列表难以让用户快速定位目标类型。早期实现将全部公告混排展示，用户需手动筛选。

## 决策（Decision）

公告按**三栏分组展示**：国标（national）/ 行标（industry）/ 地标（local）。

- 后端统计接口按类型分组返回：`GET /api/announce/stats` 返回 `gb_count` / `hb_count` / `db_count` 分类计数（依据：docker/api/announce.py `_get_check_stats()`，按 `announcement_record.source_site` 分组）。
- 前端首页按三栏渲染公告列表，类型标识来自 `SOURCE_SITE_TO_TYPE` 映射（依据：pilotstd/constants/announce_types.py，`announcement_gb/hb/db` → `gb/hb/db`）。
- 公告列表接口 `GET /api/announce/results` 的每条结果携带 `standard_type` 字段供前端分组（依据：docker/api/announce.py L204-207）。

## 后果（Consequences）

**正面**：
- 用户可按类型快速定位目标公告
- 三栏分组与公告抓取适配器（samr_gb/hb/db）一一对应，语义清晰

**负面**：
- 前端需维护三栏布局与类型映射，新增公告类型时需同步前端
- 类型判定依赖 `source_site` 命名规范（`announcement_` 前缀）

> 本文档由 2026-08-19 文档整理从 ADR 索引内联描述补建（原仅索引登记无独立文件）。
