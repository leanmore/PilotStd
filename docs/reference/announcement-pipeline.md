# 公告解析入库流程

## 流程概览

| 阶段 | 输入 | 处理 | 输出 |
|------|------|------|------|
| 采集 | 原始公告文件（PDF/DOCX） | 文件监控服务检测新文件 | 文件路径入队 |
| 解析 | 文件路径 | Parser 提取正文、元数据 | 结构化数据 |
| 清洗 | 结构化数据 | Service 层状态机处理 | 清洗后数据 |
| 入库 | 清洗后数据 | 写入 SQLite | announcement_record 记录 |

## 状态机流转

| 当前状态 | 触发事件 | 目标状态 | 说明 |
|----------|----------|----------|------|
| pending | 文件检测 | parsing | 开始解析 |
| parsing | 解析成功 | parsed | 正文提取完成 |
| parsing | 解析失败 | failed | 记录错误日志 |
| parsed | 清洗完成 | cleaned | Service 层处理完毕 |
| failed | 重试 | parsing | 重新解析 |

## 关键字段规范

| 字段 | 类型 | 说明 |
|------|------|------|
| source_type | TEXT | 来源标识，映射表见 `announcement-sources.md` |
| parse_status | TEXT | pending / parsing / parsed / cleaned / failed |
| row_index | INTEGER | 原始文件中的行号索引 |
| created_at | TEXT | ISO 8601 格式 |
| updated_at | TEXT | ISO 8601 格式，每次更新自动刷新 |

## 约束

- Parser 层只做正文提取，禁止包含业务逻辑
- **熔断器配置读取的失败可见性（2026-10-17，体检 D-8 第 7 批）**：`announcement/_circuit_breaker.py::_durations` 读配置失败原 `pass` 并静默回退默认冻结档位；现记 debug。契约由 `tests/test_silent_error_observability_batch7.py` 锁定。
- **OCR 线程优先级失败可见性（2026-10-17，体检 D-8 第 11 批）**：`ocr/_pdf_utils._set_thread_priority_idle` 在 `SetThreadPriority` 不可用时原 `pass`；现记 debug。契约由 `tests/test_silent_error_observability_batch11.py` 锁定。
- 清洗逻辑统一在 Service 层的状态机中完成
- 日期字段必须使用 ISO 8601 格式，禁止使用其他格式
- 附件正文解析失败（含 `.doc`/OLE2 这类 python-docx 不支持的格式）记为 **WARNING 日志**并返回空正文；此前为 DEBUG 级，正文为空时**无任何可见痕迹**（R15 修复）。引入 antiword/textract 解析器一事仍登记在台账观察项
- 缓存行的状态判定（`现行` / `即将实施` / `被代替`，见 `pilotstd/announcement/matcher.py`）自 **R14-4b（#32-B，2026-10-01）** 起统一引用权威字典 `pilotstd/core/status.py` 的 `Status.*.value`（取代原中文字面量），取值与判定优先级不变

## 增量 checkpoint 与失败回退（2026-10-18）

定时抓取（`auto_announce`）按适配器维护 `fetch_checkpoint.last_notice_date`，每次只拉取该日期之后的公告。
历史缺陷：单条公告详情抓取失败时，失败项被跳过但 checkpoint 仍推进到本批最大日期，导致失败的公告
**永久不会重抓**。2026-08 个别公告漏抓即由此产生（典型日志：`公告详情获取失败`）。

现行为：适配器记录本轮详情失败公告的发布日期；`engine._check_one_adapter` 若发现有失败，
把 checkpoint 回退到**最早失败日期的前一天**并标记 `checkpoint_force`，`write_checkpoint` 允许
强制回退；下一轮会重新包含失败项。无失败时仍按本批最大日期前进。

回归测试：`tests/test_announcement_checkpoint_regression.py`（4 例：失败回退、无失败前进、
强制回退、详情失败记录日期）。历史漏抓恢复方式：手动按 `since_date` 补抓，它走
`check_announcements_filtered`，不写 checkpoint。

> 兼容性：失败列表只接受字符串日期（测试替身/MagicMock 的未知属性按无失败处理），避免门禁/单测替身被误判为失败。

## 标准号解析：全角连接符与多段分册号（2026-10-18 实测）

HB 公告 `2026年第7号（总第315号）` 源站 `STD_COUNT=674`，部署库仅 668 条；差集为：
`SJ/T 11460.6.1-2025`、`SJ/T 11460.6.2-2025`、`SJ/T 11461.4.1-2025`、
`SJ/T 12089.1.1-2025`、`DY/Z 14.3-2026`、`DY/Z 14.5-2026`。

根因：`STD_CODE_PATTERN` 的分册号只允许一个 `.部分号`，且未归一化源站的全角连接符
（`－`/`／`/`？`）；这些行在 `parse_html_table` 的 `STD_CODE_PATTERN.match` 处被整行跳过。
修复：解析前统一归一化全角连接符；分册号改为 `(?:.\d+)*`；允许代号与顺序号之间出现 `/`。
回归：`tests/test_announcement_parser.py::TestFullwidthStandardCodes`。

**同类缺口仍在**：对 2026 年 HB 全量源站复核，10 月 588/554、4 月 286/263 等公告仍有
未解析行（不同表格结构/空编号），属后续 D-13 类系统补测范围；本次先修可复现的 6 条。

> 展示层保留源站原始标准号写法（全角/半角混排），`_normalize_code_text` 仅用于正则匹配与去重键；黄金样本 `002_hb_2026_07` 已按 674 条更新。

## 2026-09/10 缺口复核（2026-10-18）

GB/DB/HB 公告头完整；详情记录缺口为 DB 9月第8号 18 条、HB 9月第8号 7 条、HB 10月第9号 34 条（GB 第42号为附件型，去重后与部署一致）。
根因均为标准号前缀/连接符变体：`DB52T`、`DB11/ `、`NB/SH/T`、`SJ/T-`、`HG/T … 一 …`、`QB T`、多段分册号、全角 `－/／/？`。解析器已泛化前缀与归一化；完整清单见 `docs/records/2026-10-18-announcement-gap-audit.md`。

## 单条公告强制重解析（2026-10-18）

历史缺口修复入口：`POST /api/announcements/{announce_no}/reparse`。
与 `/parse` 的差异：`/parse` 只处理附件且要求 `attachment_url`；`reparse` 对 HTML/附件型都通过适配器
重新取详情，先解析成功再删除旧 `announcement_record` 并重建，避免解析失败先丢数据。
服务实现：`pilotstd.announce.crawler_service.AnnounceCrawler.reparse_from_source`。

## 公告号前导空格（2026-10-18 实测）

源站 GB 第36/37/38号的 `CODE` 带**前导空格**（`' 2026年第36号'`）。入库未 strip 时：
- `/api/announce/results` 能列出，但前端按 `announce_no` 请求详情会 404；
- 表现为“国家标准公告缺少第36、37、38号”。

修复：`_fetch_list` 对 `PID/CODE/TITLE/NOTICE_DATE` 统一 `strip()`；详情/记录/状态查询
改用 `TRIM(announce_no)=?` 兼容历史脏数据；列表查询返回 `TRIM(announce_no) AS announce_no`。
回归：`tests/test_announcement_base_full.py::TestFetchList::test_strips_whitespace_around_code`。

> 2026-10-20：公告行提取改用 `core.std_utils.STD_CODE_TOKEN_PATTERN`，与 `parse_std_number` 共用同一 token 语法/归一化；跨层不变量测试保证“提取出的号必能被语义解析”，避免再次出现提取成功、matcher 拒绝的静默丢记录。

> 2026-10-21（P2 防漏）：BaseAnnounceCrawler._warn_if_count_mismatch 在源站 STD_COUNT 与解析条目数不一致时记 WARNING（含 diff），非法 STD_COUNT 也告警；不再静默跳过。

> 2026-10-21（P2 入库对账）：GET /api/announce/reconcile 返回 standard_count 与实际记录数不一致的公告（declared/actual/diff），实现见 pilotstd.announcement.reconcile；用于部署后巡检，不自动改数据。

> 2026-10-21：解析器新增**国家标准样品编号**语法（`04-2809-F01-2025`、`GSB 03-4369-2025`），并处理 PDF 将 `04-2162-F01-` 与年份拆行的情形；旧逻辑会截成 `F01-2025`，把不同样品合并。

> 2026-10-21：GB 公告表格新增识别“国家标准外文名称 / 语种”列；`announcement_record` 增加 `language`/`foreign_name`，唯一键改为 `(source_site,pid,standard_number,language)`，同一标准号的不同语种分行保留（v70 迁移）。

> 2026-10-21：公告列表查询改为 nnouncement_record UNION ALL announcements 并按公告号去重；有公告头但 0 条记录的公告也会显示（计数为空），避免漏抓公告在刷新后消失。
