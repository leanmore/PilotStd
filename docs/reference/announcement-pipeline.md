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

> 2026-10-21：识别**修改单公告**（标题含“修改单”）。此类公告的附件是修改内容表格，不是标准清单；解析器只从标题提取被修改标准（如 `GB/T 2260-2007`），不再把附件表格当标准列表。

> 2026-10-22：新增 **本地 CPU OCR**（`rapidocr-onnxruntime` + `pypdfium2`，扫描版 PDF 用）。设置页 `OCR → 本地 CPU` 可切换；Docker 镜像内置运行库，模型随 wheel 提供；单公告逐页串行，线程数由 compose 的 `OMP_NUM_THREADS=1` 限制。

> 2026-10-22：OCR 设置改为两项——`云端优先`（空值，先云后本地）、`本地（CPU）优先`（`local`，先本地后云）；`FallbackOcrProvider` 在文本为空时回退，整份 PDF 一次调用，避免逐页重复云端调度。

> 2026-10-22 补充：OCR 主备由 FallbackOcrProvider 实现；云端优先/本地优先在整份 PDF 级别回退，单页失败不会重复云端调度。

> 2026-10-21：GB 公告表格新增识别“国家标准外文名称 / 语种”列；`announcement_record` 增加 `language`/`foreign_name`，唯一键改为 `(source_site,pid,standard_number,language)`，同一标准号的不同语种分行保留（v70 迁移）。

> 2026-10-22：PDF 文本表新增语种提示提取（英文/俄文/德文/法文/日文/老挝文等）；2019 年第 11 号 141 条外文版按 `(标准号, 语种)` 入库。

> 2026-10-22：新增源站标准号纠错维护列表 `pilotstd/announcement/data/source_code_corrections.json`（可用 `PILOTSTD_CODE_CORRECTIONS` 指向外部 JSON 覆盖）；仅对指定公告+精确名称生效：视频中物品图像→GA/T 1018-2013，裂头蚴病的诊断→WS 438-2013。

> 2026-10-22：内置维护列表 pilotstd/announcement/data/source_code_corrections.json 纳入版本控制（.gitignore 例外），不再依赖运行时文件。

> 2026-10-22：reparse 清理范围从 (pid, source_site) 扩展为 (source_site, announce_no)，清掉源站 PID 变更留下的旧 pid 残留，避免新旧记录并存导致 reconcile 偏差。

> 2026-10-23：Windows 本地 OCR 模型由设置页从 RapidOCR 官方 wheel 下载并 SHA256 校验，安装到 models/ocr。

> 2026-10-23：DB 公告附件增加 dbba downloadRnAtt 链接识别；.doc 按 UTF-16 文本提取；附件行数多于网页表格时以附件为主，2014年第4号地方标准由52行补齐为223行。

> 2026-10-23：混合型公告（网页表格+附件）改为实际解析附件，附件行数多于网页时以附件为准；DB 2014年第4号 52→223。

> 2026-10-24：文本表格过滤“代替标准号”列产生的日期残片；DB 2014 第4号从 223 行收敛为 215 条标准。

> **2026-11-02 去重修正**：标准号破折号 -/—/－ 与名称尾部日期/行号统一后生成去重键；修复 2026 年第 45 号公告 21 项被 HTML+附件解析成 42 项。存量重复行需单独清理。


> **2026-11-02 名称清洗**：_clean_std_name 去掉名称尾部日期/行号与控制字符；已清理 2026 年第 45 号存量 42→21 行。

> **2026-11-03 入库口径统一（v72）**：标准号归一化收敛为**唯一实现**
> `pilotstd/core/std_utils.py::normalize_std_code`（覆盖 `- — － – − ‑ ﹣`、软连字符、
> 零宽字符、连接符两侧空格），网页解析、附件解析、合并、去重、入库唯一键五处共用；
> `normalize_std_code_text` 保留为**长度保持**的字符级版本（解析器要用匹配下标回切原文，
> 任何压缩空白都会截断标准号）。
> **去重规则改为全字段 100% 一致**：先对标准号、名称、代替标准号、发布日期、实施日期、
> 作废日期、语种、外文名、备案号、主管部门逐字段归一化，再整体比对；**任一字段不同即保留**
> （旧实现用「标准号 + 名称前20字」做键，会把同年号但日期/代替号不同的两条误合并）。
> 合并阶段判「附件条目是否已存在」也用归一化后的标准号，合并完成后再跑一次全字段去重。
> 计数补全：`_dedupe_full_fields` 记 `dedupe: 42 -> 21 (dropped 21)`；`_bulk_insert_records` 用
> `rowcount` 记 `announcement_record 入库: inserted=N duplicates=M`。
> 存量迁移 **v72** 只做「可安全归一化」的改写：归一化后撞键且**全字段相同**才删重复，
> 字段有差异则**保留两行并记 WARNING**（去重不得掩盖解析差异），最后按公告重算
> `standard_count`。2026年第45号实测：reparse 后 `records=21`、`standard_count=21`、
> `/api/announce/reconcile` 返回 `items=[]`；2026年第30号实测 **509 条**（508 标准 + 1 修改单，
> 第 508 条 `GB/T 48012.2-2026`）。真实样本回归：`tests/test_announcement_real_samples.py`
> （fixtures `announcement_gb_2026_{45,30}.html`）。
>
> **同批修两个解析缺陷（2026-11-03 实测）**：
> ① `_is_amendment` 原来只判断标题是否含「修改单」，而 30 号标题是「…等 508 项推荐性国家标准和
> 1 项推荐性国家标准修改单的公告」→ 整份公告被当修改单、`_parse_amendment` 抠不出标准号 →
> **reparse 返回 0 条（HTTP 400）**。现改为：标题出现「N 项…标准 / N 项…修改单」批量计数即走正常清单解析。
> ② 附件把「代替标准号」列末字挤进名称列（`部 2026-11-01  249`），残留 1 条假标准（509→510）；
> `_METADATA_DATE_PREFIX` 由「行首日期」放宽为「名称开头 0~3 字符内出现日期」。
> 部署后自检：reparse 30 号应返回 `records=509`，且 `standard_count=509`。
>
> **2026-11-03 reparse 外键修复**：单条公告重解析原实现是「先 DELETE 该公告全部记录再插入」，
> 若这些记录被 `user_favorites.record_id` / `favorite_downloads.record_id` /
> `date_reminder_log.record_id` 引用，DELETE 直接触发
> `sqlite3.IntegrityError: FOREIGN KEY constraint failed`（线上 reparse 30 号实测 500）。
> 现改为：**先按唯一键原地 upsert**（`ON CONFLICT(source_site,pid,standard_number,language) DO UPDATE`，
> 保留 row id，收藏引用不断）→ 再清理本次未解析出来的旧行；**被引用的旧行保留并记 WARNING**，
> 绝不制造悬空外键。契约：`tests/test_reparse_cleanup.py`（含「收藏引用时 id 不变、名称已更新」）。


> **2026-11-04 交叉比对修复（D4-1 / D4-2）**：`matcher._parse_std_code` 改用
> `parse_std_number().raw_code`（带斜杠形态 `GB/T`），并让 `_find_in_file_index` 用
> `REPLACE(logical_code,'/','')` 做 **`GB/T` ↔ `GBT` 双向兼容**；同号多版本先按年代号精确匹配。
> 公告年代号大于本地文件年号时，按**公告自身年代号**写 `announcement_match` 行并标注
> `is_new_version=true` / `local_year` / `match_status=new_version`（“发现新版”），
> **不覆盖**旧版状态；公告更旧时直接跳过，避免回退覆盖。
> 修复前生产实测：含斜杠公告 201,499 条，`matched=1` 仅 1 条。契约：
> `tests/test_announcement_matcher_slash_code.py`（含 `GBT 1234-2020.pdf` 扫描入库后与
> `GB/T 1234-2020` 公告匹配的回归）。

> **2026-11-04 修改单隔离（D4-3）**：`matcher` 遇到 `std_name` 含“修改单”只写
> `announcement_record`，**不写** `announcement_match`——修改单与本体共用标准号，
> 写缓存会用修改单的实施日期覆盖本体状态。

> **2026-11-04 熔断通知（D4-4）**：`CircuitBreaker.record_failure` 触发冻结时，
> 通过 `pilotstd.core.notification.notify_system` 钩子发 `task_execution_failed`
> 系统通知（容器 `docker/app.py` 启动时注入 manager 的 `send_event`）。
> 无钩子（如单元测试/桌面端未接入）时静默降级，不影响抓取。

> **2026-11-04 审计补丁**：`replaced`（被代替）匹配改用**旧标准自身年代号**建缓存键
> （此前误用新公告年份，导致旧标准永远写不进“被代替”、并生成不存在的标准号）；
> 缓存键补上分部号（`GB/T 1234.1-2020`），与 `get_full_info` 的精确 JOIN 对齐；
> 同一公告的多条同号旧版只写一次“发现新版”行，避免计数虚高。
