# 公告来源标识映射表

本文档是公告来源标识的唯一真相源。来源标识映射的代码实现位于 `docker/api/announce_detail.py`（**公告附件后台解析**已于 2026-09-26 外移到 `docker/api/_announce_detail_parse.py`，不影响本文档的映射口径）。

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

> 2026-10-22：同一 `announce_no/PID` 可能出现在 HB/DB/GB 端点（实测 2014年第4号 PID `5D14...` 在 gnocHb/gnocDb/gnoc 返回三套数据）。详情、records、parse、reparse 均增加 `source` 参数（annc_gb/annc_hb/annc_db），按 `source_site` 过滤，不能只用公告号/PID 定位。
