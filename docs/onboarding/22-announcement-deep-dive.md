# 22 · 公告抓取/解析/匹配/OCR 细分

> 来源：`pilotstd/announcement/`、`docs/reference/announcement-*.md`，2026-11-07。  
> 一句话：**3 个 SAMR 公告源 → 解析表格/附件 → 与 file_index 交叉比对 → 写 announcement_match/record**。

---

## 一、抓取编排

| 项 | 事实 |
|---|---|
| 公告类型 | `gb` / `hb` / `db` |
| 适配器 | `samr_gb` / `samr_hb` / `samr_db` |
| 并发 | `AnnounceEngine.check_all()` 用 3 线程并发，单源失败不阻塞其他 |
| 单源 | `check_one()` |
| 断点 | `fetch_checkpoint.last_notice_date`；详情失败回退到最早失败日前一天 |
| 熔断 | `_circuit_breaker.py`；按标准类型持久化健康状态 |
| OCR | 可注入 provider；PDF 附件走 OCR 调度 |
| 去重 | `announcement_record` 唯一键含 `source_site,pid,standard_number,language`；v72 归一化标准号 |
| 公告号 | 同一 `announce_no/PID` 可能跨 HB/DB/GB，详情/reparse 必须带 `source` |

---

## 二、解析

### 1. 公告元数据

- 标题：HTML `<title>`；
- 发布日期：去掉表格后正文第一个 `YYYY-MM-DD`（表格里的实施日期不算）。

### 2. 表格

`parse_html_table`：

- 表头关键词映射（标准编号/名称/外文名/语种/代替/实施日期/发布日期/作废日期/备案号/主管部门）；
- 全角/半角连接符归一；
- 分册号支持 `(?:.\d+)*`；
- 解析失败的行记录，不阻断整表。

### 3. 附件

- PDF/DOCX/WPS：`_attachment_parser`；
- `.doc` / OLE2：python-docx 不支持，记 **WARNING** 并返回空正文；
- 图片/扫描件：OCR provider（百度默认，腾讯/阿里/本地可配；失败互相回退）；
- 附件正文解析失败不阻断公告主记录。

### 4. 标准号

- 用 `STD_CODE_TOKEN_PATTERN`；
- 入库前 `normalize_std_code`（破折号/斜杠/全角）；
- 修改单单独标记，不写 `announcement_match`（避免覆盖本体状态）。

---

## 三、匹配

`AnnouncementMatcher.match_and_update()`：

1. 按 `announce_no` 归并公告级元数据（publish_date/title/standard_count/row_index）；
2. 每条：`correct_std_code` → `normalize_std_code` → `parse_std_number`；
3. 查 `file_index`：`logical_code` 双向兼容（`GB/T` ↔ `GBT`）+ number；有 year 先同 year，没有再退回同号全部；
4. 直接号匹配不到时，用 `replaces_code` 尝试替代号匹配；
5. 命中 → 写 `announcement_record` + `announcement_match`；
6. `announcement_match` 键含 part，避免分册互相覆盖；
7. `standard_count` 是“同公告条目数”，**不能 SUM**，否则 N² 膨胀；
8. 公告年份旧于本地新版时，不覆盖本地缓存。

### 状态来源

- `announcement_match.result_json.status` 是有效性 L1 的结构化来源；
- `announcement_record` 没有独立“公告类型/状态”列，名称关键词只作废止负证据。

---

## 四、OCR

| 项 | 事实 |
|---|---|
| 默认 | 百度云 `basicGeneralPdf` |
| 可选 | 腾讯云 / 阿里云 / 本地 |
| 策略 | `provider` 显式指定；空白/cloud=云端优先；local=本地优先；失败互相回退 |
| PDF | 直接 base64 上传，无需转图片 |
| 调度 | `OcrScheduler` + 计数器 + provider 冷却 |
| 用量 | 百度每月免费 1000 次，月均约 50 次 |
| 失败 | 单附件失败不阻断公告主流程 |

---

## 五、已知问题/边界

1. `announcement_record` 有 **21 万+** 行，`data_state` 大量 stale；
2. `announcement_match` 的 `expires_at` 多为 NULL，缓存新鲜度没有硬保证；
3. `.doc`/OLE2 正文为空，只有 WARNING；
4. 部分公告表格结构/空编号仍会漏解析（历史已知缺口）；
5. 同一公告号跨来源必须带 `source`，否则 409；
6. 修改单只入 record，不写 match；
7. 公告年份旧于本地新版时不覆盖，避免历史重抓回退。

---

## 六、一句话记忆

> 三源并发抓 → 表格/附件解析 → 按标准号找 file_index → 命中写 match/record；  
> 修改单不写 match，公告年份旧不覆盖新，`standard_count` 不能 SUM。
