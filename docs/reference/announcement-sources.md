# 公告来源标识映射表

本文档是公告来源标识的唯一真相源。代码实现位于 `docker/api/announce_detail.py`。

## Source 映射表

| 数据库值 | URL 标识符 | 中文名 |
|---------|-----------|--------|
| announcement_gb | annc_gb | 国家标准 |
| announcement_hb | annc_hb | 行业标准 |
| announcement_db | annc_db | 地方标准 |

## 使用规则

- 新增来源时，必须同时更新本文档和 `docker/api/announce_detail.py`
- 禁止在代码中硬编码来源标识符，必须引用本文档中的映射关系
- 数据库值与 URL 标识符的映射关系不可逆，修改需提交 ADR
