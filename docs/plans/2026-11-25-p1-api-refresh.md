# P1-7.1 复核：API / ASME 编号识别与匹配（2026-11-25 当前代码实测）

| 项目 | 值 |
|------|-----|
| 任务 | P1-7.1 复核（上一轮 `docs/plans/2026-11-24-p1-api-asme-gap.md` 之后的回归测量） |
| 日期 | 2026-11-25 |
| 代码状态 | `main` HEAD `bbc60b61`（工作树干净，未改任何代码/配置） |
| 性质 | **只读复核**：仅新增本报告；探针脚本/输出在 `%TEMP%`（`C:\Temp\p1r_api_refresh_probe.py`、`p1r_impact_probe.py`、`p1r_api_refresh_probe.json`） |
| 样本 | 任务指定 16 条（主矩阵）+ 上一轮报告 §2.1/§2.2 的 40 条（同口径对比） |
| 结论一句话 | 上一轮的「ASME B 系列拆号自 mismatch / API 类型词污染代号 / BPVC 全 MISS」**已修复**；但按「A+B 双通道字段全对」口径，16 条样本当前仅 **7/16**、40 条样本 **21/40**，**P1-7.1 仍不可闭合**：剩 3 类识别缺口 + 4 类下游消费缺口（查询 target、归档键/文件名、路由、前端回落）。 |

> 已查阅（文档依据，非记忆）：
> - `docs/plans/2026-11-24-p1-api-asme-gap.md` §1.1/§1.2/§2.1/§2.2/§2.3/§3.2/§4（上一轮缺口与 40 条样本集）
> - `docs/reference/附录一 标准代号完整清单.md` §5.4「年份识别规则」（无年份 → `year=0`）、§5.5「当前覆盖状态」（ASME BPVC ❌）
> - `docs/architecture/modules/parser.md` §「ASME BPVC 识别口径扩展（2026-11-24，P1-7.1 B-5）」
> - `docs/reference/download-pipeline.md` §「下载结果携带后端解析字段（2026-11-24，P1-C1）」
> - `docs/guides/人工测试方案.md:71`（1.7 `ASME B16.5` 期望解析）与 `tests/test_scanner.py:135-138`（无年份被拒绝）的冲突仍存在
>
> 实测证据：`python C:\Temp\p1r_api_refresh_probe.py`（A/B/match/前端/查询 target/键命名全量矩阵）、`python C:\Temp\p1r_impact_probe.py`（路由/键/文件名影响面）。本报告表格逐行来自这两份实跑输出。

---

## 0. 摘要

1. **已修复（实测确认）**：
   - `ASME B16.5-2020`/`B31.3-2024`/`Y14.5-2018` A+B 均 → `ASME/16/5/2020` 等正确字段；`match_result` 自比对 **0 条 mismatch**（上一轮 2 条）。
   - `API STD 610-2004`/`API RP 520-2020`/`API Q1-2023` A 通道代号不再被污染（`APISTD`→`API`，类型词进 `num_prefix`）。
   - `ASME BPVC.VIII.1-2025`、`Section VIII Div.1-2021` A+B 均能识别；`Section II Part D` A 能识别，B 因无年份仍失败。
   - 40 条样本 A 通道「正确」从上一轮 **4/40 → 31/40**。
2. **仍不达标**：16 条样本 A 通道 9/16、B 通道 7/16、A+B 同时正确 **7/16**；match 可靠（A 正确且不 mismatch）9/16；前端 raw 仅 1/16。40 条样本 A+B 同时正确 21/40（仍 19 条失败）。
3. **剩余缺口分两类**：识别侧（ASME 类型词仍污染 A 代号、无年份 B 硬拒、多字母/连字符后缀与联合标准、版次当年份）；消费侧（查询 target 拼接错、归档键/文件名表示错、前端 year 门回落、有效性登记被畸形键拒绝）。

---

## 1. 当前覆盖率总表

### 1.1 任务指定 16 条样本

| 指标 | 结果 | 说明 |
|------|------|------|
| A 通道字段全对 | **9/16**（56.3%） | `parse_std_number` 的 `code/number/part/year/num_prefix/num_suffix` 全部符合期望 |
| B 通道字段全对 | **7/16**（43.8%） | `StandardParser.parse` 同口径；6 条 MISS、3 条部分（丢 `num_prefix`/后缀） |
| A+B 同时全对 | **7/16**（43.8%） | 即「识别链路闭合」口径 |
| match 自比对不 mismatch | A 可解析的 13/13 | 另 3 条 A MISS 无从自比对；上一轮 `ASME B16.5-2020`/`B31.3` 自 mismatch 已修 |
| match 可靠（A 正确 + `exact`） | **9/16** | 其余 7 条：3 条 A MISS 靠模糊「伪 exact」（4/5/16）、2 条 canonical mismatch（14/15）、2 条 A 丢 part 但 part 未参与判定（6/7） |
| 前端 `standardParser.ts` raw | **1/16** | 只有 `API 610-2004` |
| 下载→归档（后端字段优先） | 13/16 可入队，9/16 字段正确 | A 解析非空即可入队；`API 579-1` 等 4 条字段错 |
| 扫描→规范化（B 字段 + 前端回落） | **7/16** | `TaskView.vue:305` 要求 `year>0`，B 无年份/前端 raw 全盲导致其余被跳过 |

### 1.2 上一轮 40 条样本（同口径，可直接对比）

| 通道 | 上一轮（2026-11-24） | 本轮（2026-11-25） | 变化 |
|------|----------------------|--------------------|------|
| A `parse_std_number` | 正确 4 / 部分 2 / 错 11 / MISS 23 | **正确 31 / 部分 2 / 错 2 / MISS 5** | 正确 +27 |
| B `StandardParser.parse` | 正确 21 / 部分 1 / 错 4 / MISS 14 | **正确 23 / 部分 2 / 错 3 / MISS 12** | 正确 +2（BPVC 带年份） |
| C 前端 raw | 正确 2 / MISS 38 | **正确 2 / MISS 38** | 无变化 |
| A+B 同时正确 | 上轮未统计 | **21/40** | 仍 19 条失败 |

分类口径（与上一轮一致）：`正确`=主字段+字母前后缀全对；`部分`=主字段对但字母前后缀丢失；`错`=返回非空但主字段错位；`MISS`=返回 None。

---

## 2. 逐条矩阵（16 条任务样本）

记号：`A` = `pilotstd.core.std_utils.parse_std_number`；`B` = `pilotstd.scan.parser.StandardParser.parse`（按真实文件名口径传入 `样本+.pdf`）；`M` = `pilotstd.query.search_strategy.match_result`（本地=期望字段，站点返回串=样本）；`FE` = 前端 `web/src/utils/standardParser.ts`（node 直接加载真实 TS）。
字段缩写：`代号/序号/部分号/年份`；`pre`=`num_prefix`，`suf`=`num_suffix`。

| # | 样本 | 期望字段 | A 通道实测 | B 通道实测 | M（本地=期望） | FE raw | 判定 |
|---|------|---------|-----------|-----------|----------------|--------|------|
| 1 | `API 610-2004` | API/610/–/2004 | ✅ API/610/–/2004 | ✅ API/610/–/2004 | exact（精确解析） | ✅ API/610/2004 | ✅ 达标 |
| 2 | `API STD 610` | API/610/–/0 pre=STD | ✅ API/610/–/0 pre=STD | **MISS** | exact（精确解析） | ❌ None | ⚠️ 仅 A 达标（B 无年份拒绝） |
| 3 | `API SPEC 6D-2021` | API/6/–/2021 pre=SPEC suf=D | ✅ API/6/–/2021 pre=SPEC suf=D | ✅ 同 A | exact | ❌ None | ✅ 达标（归档靠后端字段） |
| 4 | `API RP 2A-WSD` | API/2/–/0 pre=RP suf=A-WSD | **MISS** | 部分 API/2/–/0 pre=RP suf=A（丢 `-WSD`） | exact（**模糊回退**） | ❌ None | ❌ 失败 |
| 5 | `API TR 938-C` | API/938/–/0 pre=TR suf=C | **MISS** | **MISS** | exact（**模糊回退**） | ❌ None | ❌ 失败 |
| 6 | `API 579-1` | API/579/1/0 | ❌ API/579/**–**/0（part 丢） | **MISS** | exact（精确解析，但 part 未参与判定） | ❌ None | ❌ 失败 |
| 7 | `API 579-1/ASME FFS-1` | API/579/1/0（联合标准） | ❌ API/579/**–**/0（part 与 `/ASME FFS-1` 均丢） | **MISS** | exact（精确解析；联合段被忽略） | ❌ None | ❌ 失败 |
| 8 | `ASME B16.5-2020` | ASME/16/5/2020 pre=B | ✅ ASME/16/5/2020 pre=B | ✅ 同 A | exact | ❌ None | ✅ 达标 |
| 9 | `ASME B31.3-2024` | ASME/31/3/2024 pre=B | ✅ ASME/31/3/2024 pre=B | ✅ 同 A | exact | ❌ None | ✅ 达标 |
| 10 | `ASME Y14.5-2018` | ASME/14/5/2018 pre=Y | ✅ ASME/14/5/2018 pre=Y | ✅ 同 A | exact | ❌ None | ✅ 达标 |
| 11 | `ASME BPVC.VIII.1-2025` | ASME/8/1/2025 pre=VIII | ✅ ASME/8/1/2025 pre=VIII | ✅ 同 A | exact | ❌ None | ✅ 达标 |
| 12 | `ASME BPVC Section VIII Div.1-2021` | ASME/8/1/2021 pre=VIII | ✅ ASME/8/1/2021 pre=VIII | ✅ 同 A | exact | ❌ None | ✅ 达标 |
| 13 | `ASME BPVC Section II Part D` | ASME/2/–/0 pre=II suf=D | ✅ ASME/2/–/0 pre=II suf=D | **MISS** | exact（精确解析） | ❌ None | ⚠️ 仅 A 达标（B 无年份拒绝） |
| 14 | `ASME PTC 4-2013` | ASME/4/–/2013 pre=PTC | ❌ **ASMEPTC**/4/–/2013（代号污染） | 部分 ASME/4/–/2013 pre=**空**（丢 PTC） | **mismatch** | ❌ None | ❌ 失败 |
| 15 | `ASME CSD-1-2024` | ASME/1/–/2024 pre=CSD | ❌ **ASMECSD**/1/–/2024（代号污染） | 部分 ASME/1/–/2024 pre=**空**（丢 CSD） | **mismatch** | ❌ None | ❌ 失败 |
| 16 | `ASME A112.18.1/CSA B125.1` | ASME/112/18/0 pre=A（联合/三级编号） | **MISS** | **MISS** | exact（**模糊回退**） | ❌ None | ❌ 失败 |

**汇总**：✅ 7 条（1/3/8/9/10/11/12）；⚠️ 2 条（2/13，仅 B 无年份缺口）；❌ 7 条（4/5/6/7/14/15/16）。

### 2.1 `match_result` 细节（自比对 vs canonical）

| 现象 | 样本 | 说明 |
|------|------|------|
| 自比对 exact（修复确认） | 1/2/3/6/7/8/9/10/11/12/13 | 上一轮 `ASME B16.5-2020`/`B31.3` 自 mismatch 已修 |
| 自比对 exact 但「一致地错」 | 14/15 | A 把 `ASME PTC` 解析成 `ASMEPTC`，本地与站点串用同一错误代号 → `exact`；用**期望代号** `ASME` 比对才是 mismatch（canonical 检测才能暴露） |
| canonical mismatch | 14/15 | `match_result("ASME", 4, 2013, "", "ASME PTC 4-2013")` → `(False, "mismatch")`，**同一编号配正确本地记录也会被判 mismatch** |
| 「伪 exact」（A MISS 走模糊） | 4/5/16 | `_exact_parse_match` 返回 None → `_fuzzy_text_match` 只查「代号子串+序号词边界」；`API 579-1`/`API TR 938-C`/`A112.18.1` 的 part/后缀/联合段完全不校验 → 会采纳错版本/错分部结果 |
| part 未参与判定 | 6/7 | `_exact_parse_match`（`search_strategy.py:112-116`）在「本地 part 或结果 part 任一为 None」时直接视为 `part_match=True` |

### 2.2 前端 `standardParser.ts` 现状（是否仍作回落路径）

- **代码未变**：`web/src/utils/standardParser.ts:12` 仍是单条正则 `^([A-Z][A-Z0-9/]+)\s*(\d+(?:\.\d+)?)\s*[—\-:]\s*(\d{4})$`；16 条 raw 仅 1 条（`API 610-2004`），40 条仅 2 条（与上一轮完全一致）。
- **仍作回落路径，两处**：
  1. `web/src/utils/taskPipeline.ts:39-53`：下载结果**优先消费后端字段**（`dl.logical_code && dl.number`），仅在后端字段缺失时 `parseStandardNumber(dl.standard_number)`。P1-C1 已让 `docker/api/download.py:41-53` 输出 `/api/download` 的 `logical_code/number/year/num_prefix` → 下载归档不再 38/40 丢件，但后端 A 解析失败的 3/16 仍回落前端并丢弃。
  2. `web/src/views/TaskView.vue:301-322`：扫描件规范化 `(f.logical_code && f.number && f.year) ? ... : parseStandardNumber(...)`。**`f.year` 用了真值判断** → 后端 B 可解析但 `year=0` 的件（`API Spec 5L`、`API 6D`、`API Bull 2U` 等，B 通道 `_exact_match_no_year` 合法产物）会回落前端正则 → `null` → `console.warn` 后**跳过规范化，进而 `buildArchiveItems` 不纳入归档**（同一批文件在 Web 五段式里丢失）。
- 结论：前端已从「唯一口径」降级为「回落口径」，但回落覆盖面仍 1/16；且 year 门使「B 能解析、前端不能」的件继续丢。

### 2.3 上一轮 40 条样本中仍失败的 19 条（A+B 未同时正确）

| # | 样本 | A | B | 备注 |
|---|------|---|---|------|
| 1 | `API Spec 5CT-2018` | ✅ | ❌ 错：`suf=C`、`year=0` | B `_NUM` 只允许 1 个尾字母，后段整段丢 |
| 2 | `API STD 610` | ✅ | MISS | B 无年份拒绝 |
| 3 | `API RP 2A-WSD` | MISS | 部分：`suf=A`（丢 `-WSD`） | A/B 均不支持连字符多段后缀 |
| 4 | `API 6D` | 部分：`suf` 丢 | ✅ | A 兜底解析不保留字母后缀 |
| 5 | `API 6D-2021` | 部分：`suf` 丢 | ✅ | 同上 |
| 6 | `API Q1` | ✅ | MISS | B 无年份拒绝 |
| 7 | `API MPMS 11.1` | ✅ | MISS | B 无年份拒绝 |
| 8 | `API TR 938-C` | MISS | MISS | 多字母+连字符后缀 |
| 9 | `API 610-11th` | ✅（版次被丢，恰好 year=0） | ❌ 错：`year=2011` | B 版次当年份（G4） |
| 10 | `API STD 610-11th Edition` | MISS | ❌ 错：`year=2011` | A 无版次解析；B 版次当年份 |
| 11 | `API 579-1/ASME FFS-1` | ❌ 错：part 丢 | MISS | 联合标准无解析分支 |
| 12 | `ASME B16.5` | ✅ | MISS | B 无年份拒绝（与 `docs/guides/人工测试方案.md:71` 期望冲突） |
| 13 | `ASME PTC 4-2013` | ❌ 错：`ASMEPTC` | 部分：`pre` 丢 | ASME 类型词污染 A 代号；B 无 ASME 系列 handler |
| 14 | `ASME PTC 4` | MISS | MISS | A/B 均无「ASME 系列+无年份」通道 |
| 15 | `ASME C1` | ✅ | MISS | B 无年份拒绝 |
| 16 | `ASME CSD-1` | MISS | MISS | ASME 系列+无年份 |
| 17 | `ASME BPVC Section VIII Div.1` | ✅ | MISS | B 无年份拒绝 |
| 18 | `ASME BPVC.II.D` | ✅ | MISS | B 无年份拒绝 |
| 19 | `ASME BPVC Section II Part D` | ✅ | MISS | B 无年份拒绝 |

---

## 3. 仍失败项明细 + 根因 + 影响

### 3.1 16 条中 9 条未全通道达标（分类）

| 类别 | 样本 | 期望 vs 实际 | 根因（`文件:行`） | 影响 |
|------|------|-------------|------------------|------|
| **F1 ASME 类型词污染 A 代号** | 14 `ASME PTC 4-2013`、15 `ASME CSD-1-2024` | 期望 `ASME + pre=PTC/CSD`；实际 A=`ASMEPTC/ASMECSD` | `pilotstd/core/std_utils.py:412-447` `_try_parse_variant_prefix`：只有 `tokens[0]=="API"` 才拆类型词（432-438）；ASME 的 `PTC/CSD` 被 `STD_CODE_TOKEN_PATTERN` 的代号段（`std_utils.py:319-321`）吞进代号 | ① canonical `match_result` 判 mismatch；② `classify_std_code("ASMEPTC")` 未命中 `CODE_ROUTES`，路由落 `_FOREIGN_FALLBACK=["ahbz","njbz365"]`（`pilotstd/query/engine/_constants.py:23,33-52`）→ **选错站**（应走 `asme`）；③ `build_standard_number` 写出 `ASMEPTC 4-2013`，有效性登记/索引代号错 |
| **F2 无年份在 B 通道硬拒** | 2 `API STD 610`、13 `ASME BPVC Section II Part D`（40 条样本中另有 8 条同因） | A 正确、B MISS | `pilotstd/scan/parser/_result_builder.py:122-124` `require_year=True` 时 `year<=0` 直接失败；`_exact_matcher.py:225-226` 的无年份通道要求 `num_suffix` 非空（`API STD 610`/`ASME B16.5` 无后缀 → 拒） | 扫描/归档无法识别无年份编号（与附录 §5.4「无年份 year=0」口径冲突）；Web 规范化直接跳过；公告无年份编号无法走扫描链路 |
| **F3 多字母/连字符后缀、联合标准、A 系列三级编号** | 4 `API RP 2A-WSD`、5 `API TR 938-C`、7 `API 579-1/ASME FFS-1`、16 `ASME A112.18.1/CSA B125.1` | 全 MISS 或 part 丢失 | `pilotstd/core/std_utils_api.py:13-17`：后缀 `([A-Z]{1,2})?` 只接受数字后直接连字母、不接受 `-C`；`std_utils.py:385-387` `_LETTER_SERIES_RE` 只认 `[BCY]`；`std_utils.py:281-293` 兜底只取第一段数字（`579-1` 的 part 丢）；无联合标准（`/ASME FFS-1`）分支；`scan/parser/_constants.py:143` `_NUM` 同样只允许 1 个尾字母 | 这类编号无法识别/无法归档；A MISS 时 `match_result` 走模糊回退给出「伪 exact」，part/后缀不参与 → **可能采纳错误版本**（尤其 `API 579-1` 会匹配任意含 `579` 的结果） |
| **F4 版次当年份（B）** | 40 条中 9/10（`API 610-11th`、`API STD 610-11th Edition`） | B `year=2011` | `scan/parser/_constants.py:147` `_YEAR_LOOSE` 允许两位年份；`pilotstd/scan/edition_detect.py:65-70` `edition_skip_pattern` 不匹配 `11th` | 年份错位 → 匹配 `newer/older` 判定错、下载版本判断错；该缺口上一轮 G4 未修 |
| **F5 B 通道 ASME 系列前缀丢失** | 14/15 的 B 侧（另 40 条中 `ASME PTC 4` 全 MISS） | 期望 `pre=PTC/CSD`，实际空 | `pilotstd/scan/parser/_foreign.py:71-98` `_handle_type_prefix` 只有 API/MSS/MIL/SAE/IEC 分支；`_handle_special_sep` 的 ASME 分支是 `pass`（123-126） | 归档键/文件名丢失系列词（`ASME 4-2013` 无法区分 `PTC 4`）；上一轮 G7 未修 |
| **F6 A 通道字母后缀丢失** | 40 条中 `API 6D`/`API 6D-2021`（16 条外） | A `suf` 丢（兜底只取数字） | `std_utils.py:281-293` `_try_parse_fallback` 正则 `([A-Z]+(?:/[A-Z]+)?)\s*(\d+)` 不含尾字母；无类型词形态不进 `_try_parse_api_typed` | A 派生的搜索变体/键丢 `D`（`API 6` vs `API 6D` 去重/索引混淆），B 侧正确但扫描路径不受影响 |

### 3.2 跨样本共性缺口（识别正确也仍会出问题，必须同批处理）

| ID | 缺口 | 证据（实跑） | 根因（`文件:行`） | 影响 |
|----|------|-------------|------------------|------|
| **R1** | **查询层 target 拼接未跟上新字段口径** | 16 条样本用 `BaseAdapter.query_with_strategy` 实际生成的搜索词，只有 **4/16** 含期望 designator/productcode：`API 610-2004`、`ASME B16.5-2020`、`B31.3-2024`、`Y14.5-2018`。BPVC 生成 `ASME VIII8.1-2025`（期望 `BPVC.VIII.1`）；`API STD 610`→`API STD610-0`→productcode `STD610-0`；`API SPEC 6D-2021`→`SPEC6`；`API 579-1`→`579.1-0`；`ASME BPVC Section II Part D`→`II2-0` | `pilotstd/query/adapters/base.py:169-172`：`f"{code} {num_prefix}{number}{num_suffix}{part_str}-{year}"`（前缀与序号直接粘连、忽略 `num_suffix`、`year=0` 也追加 `-0`）；`_search_progressive` 第 2~4 步同口径（134/142/149）；`pilotstd/query/engine/_single.py:185-186` 缓存/日志 target 连 `num_prefix` 都没有；`_single.py:127` 交给适配器的是重建串而不是用户原始串，导致 `asme.py:82-118` 的 designator 归一化对 BPVC 失效（其 `query_standards` 覆盖 `asme.py:164-166` 未被 QueryEngine 使用） | 解析正确也搜不到 → 查询返回「未找到」→ 下载/归档链不触发（漏检）；BPVC 变体仍把卷号当分册（`search_strategy.py:13-34` 的 `build_code_variants("ASME",8,2025,"VIII")` → `ASME BPVC VIII.8-2025`，上一轮 G8 未修）。**不是选错站**，是命中不到 |
| **R2** | **归档键/文件名表示层未对齐 `num_prefix/num_suffix`** | B：`ASME B16.5-2020`→`get_full_number()`=`ASME BB16.5-2020`（双前缀）、`API SPEC 6D-2021`→`API SPEC 6DD-2021`（双后缀）、`API 6D-2021`→`API 6DD-2021`；A/B 的 `build_standard_number`：`API STD610`、`API SPEC6-2021`、`ASME VIII8.1-2025`、`API 6`（丢 D）；`C:\Temp\p1r_impact_probe.py` 实测全部复现 | `pilotstd/models.py:45-55` `get_full_number` 把 `num_prefix` 与 `raw_number`（已含前缀/后缀）再拼一次；`pilotstd/core/std_utils.py:42-61` `build_standard_number` **无 `num_suffix` 参数**且 `{prefix}{number}` 无分隔；`std_utils.py:15-21` `CANONICAL_KEY_RE=^\S+ \d+` 不接受字母前缀键 → `pilotstd/core/validity_checker.py:48-54` 把 `ASME B16.5-2020`/`ASME VIII8.1-2025` 判「畸形标准号」拒绝登记 | ① `docker/api/scan.py:109` 直接把 `get_full_number()` 作为扫描结果 `standard_number` → 前端展示/文件名双字母（`ASME BB16.5-2020`）；② 有效性登记对 **ASME B/Y 系列 + BPVC** 全被拒（漏跟踪）；③ 去重/索引键丢 suffix（`API 6` 与 `API 6D` 撞键）；④ 下载文件名 `make_standard_filename`（`file_utils.py:385-419`）未传 `num_prefix`（`pilotstd/download/engine.py:396-416`，411 行）→ BPVC 下载件名 `ASME 8.1-2025.pdf` / `ASME 2-2021.pdf`，卷/册信息丢失（II.D 与 II.D.M 有撞名风险） |
| **R3** | **前端回落 + year 真值门** | raw 1/16、2/40；`API Spec 5L`/`API 6D`/`API Bull 2U` 等 B 可解析但 `year=0` | `web/src/views/TaskView.vue:305`（`f.logical_code && f.number && f.year`）、`:307` 回落；`web/src/utils/standardParser.ts:12` 正则；`web/src/utils/taskPipeline.ts:39-53`（下载侧已改为后端优先） | Web 五段式：`year=0` 的扫描件回落前端 → `null` → 不进入 `normalizeResults` → `buildArchiveItems` 的 `archiveMap` 缺失 → **文件不归档**（静默 warn）；旧接口/后端字段缺失的下载件同样丢（P1-C1 只解决新接口） |

---

## 4. 结论与剩余工作量

### 4.1 P1-7.1 是否可闭合

**当前不能闭合。** 按任务验收口径（A/B 双通道字段正确 + 匹配不误判）：

- 16 条任务样本：**7/16 全通道达标**（43.8%），⚠️ 2 条仅 A（B 无年份），❌ 7 条失败；前端 raw 1/16。
- 40 条上轮样本：A 31/40、B 23/40、**A+B 21/40**，仍 19 条失败。
- 上一轮修复已确认生效（B 系列自 mismatch 清零、API 类型词不污染、BPVC 带年份识别），但剩余失败集中在「无年份/后缀/联合标准/版次」四类识别形态与「查询 target/归档键」两类下游消费，且**识别正确不等于链路可用**（BPVC 解析全对，但 16 条样本的查询搜索词仅 4/16 命中期望且 BPVC 全 miss；归档键畸形、下载文件名丢卷册）。

建议闭合判据（二选一，需任务方确认）：
1. **严格**：16 条样本 A+B 全对 ≥ 16/16，且查询/归档键冒烟通过（按本报告 R1/R2 修完）；
2. **分阶段**：识别侧先达 16/16（F1~F6），下游 R1/R2 单独立项，P1-7.1 仅以「A+B 全对 + 无 canonical mismatch」收口。

### 4.2 剩余工作量估计

| 批次 | 内容 | 涉及文件数 | 用例数估计 |
|------|------|-----------|-----------|
| B-7 | 无年份放开（A/B 口径统一：`validate_result` + no_year 通道 + 回归无年份样本） | 3（`_result_builder.py`/`_exact_matcher.py`/`__init__.py`） | 8~10 |
| B-8 | 多字母/连字符后缀 + 联合标准 + A 系列三级编号（`_try_parse_api_typed`/`_LETTER_SERIES_RE`/新增联合解析） | 3（`std_utils_api.py`/`std_utils.py`/`_constants.py`） | 10~12 |
| B-9 | ASME 类型词与系列（A 拆 PTC/CSD + B `_foreign` ASME handler + `PRESERVED_MULTI_WORD`） | 3（`std_utils.py`/`_foreign.py`/`_constants.py`） | 8~10 |
| B-10 | 版次/两位年份约束（`_YEAR_LOOSE` + `edition_skip_pattern`） | 2（`_constants.py`/`edition_detect.py`） | 4~6 |
| B-11 | 表示层/归档键（`get_full_number`/`build_standard_number`/`CANONICAL_KEY_RE`/`make_standard_filename` + 调用点 `engine.py`/`_organize.py`） | 5~6 | 8~10 |
| B-12 | 查询 target 构造与 BPVC 变体（`base.py`/`_single.py`/`search_strategy.py`/`asme.py`） | 4 | 6~8 |
| B-13 | 前端 year 门 + 回落（`TaskView.vue` + 四件套） | 1~2（+测试） | 2~3（前端用例） |
| 文档回写 | `core.md`/`parser.md`/`query.md` + `08-known-boundaries`/`26-fix-dossiers`/`27-implementation-log` | 6 | — |

合计：**代码/测试约 13~15 个文件、45~58 个用例**，建议拆成 3 个提交批次（识别侧 B-7~B-10 → 表示/键 B-11 → 查询/前端 B-12~B-13），每批先失败测试后修，前端改动必跑四件套。

---

## 5. 复现方式与边界

```powershell
# 仓库根目录，当前 HEAD bbc60b61
python C:\Temp\p1r_api_refresh_probe.py   # 16 条主矩阵 + 40 条对比 + 前端 raw + 查询 target 捕获
python C:\Temp\p1r_impact_probe.py        # 路由/归档键/文件名影响面

# 前端真实 TS 由探针内 node 子进程直接加载（Node v24.15.0）：
#   import('file:///D:/PilotStd/web/src/utils/standardParser.ts')
# 若 Node 版本过低会报 type-stripping 失败，此时仅看 A/B/match/查询。
```

- 本次为**只读复核**：未改生产代码/配置/测试，未 git commit/push；B 通道使用真实 `build_code_mapping()`；查询 target 用真实 `BaseAdapter.query_with_strategy` 捕获搜索词（`_search_candidates` 返回空，**无网络请求**）。
- 前端现有测试佐证：`pnpm.cmd exec vitest run src/utils/taskPipeline.test.ts src/utils/standardParser.test.ts` → **28 passed**（任务管线后端优先契约已绿；但 `TaskView.vue` 内联 year 门无测试覆盖）。
- 后端相关既有测试：`python -m pytest tests/test_std_utils_asme.py tests/unit/scan/parser/test_bpvc_section_snapshot.py tests/unit/query/test_search_strategy_code_noise.py -q` → **83 passed**（已修部分不回退，但未锁本报告仍失败的样本）。
- 期望口径说明：`API RP 2A-WSD` 按「`number=2`、`num_suffix=A-WSD`」，`API 579-1`/联合标准按「`part=1`（联合段可另立字段）」，`ASME A112.18.1/CSA B125.1` 按「`ASME/112/18` 且第三级 `.1` 暂不可表达」；若任务方采用不同字段口径，仅影响这 3 条的判定，不改变「仍失败」结论。
- 未覆盖：真实站点端到端命中（凭据/网络受限）；`ASME BPVC` 组件的 `schema/API` 设计（是否需要新增「卷/册/篇」字段）；下载件真实归档路径（无 API/ASME 付费下载件）。

---

## 6. 交付自检

- [x] 16 条任务样本全部实跑；A/B/match/前端四列齐全（§2）
- [x] 40 条上一轮样本同口径复测，给出「上一轮 vs 本轮」对比（§1.2、§2.3）
- [x] 覆盖率先给总表（§1），再给逐条矩阵（§2），再给失败明细+根因+影响（§3）
- [x] 所有根因落到 `文件:行`；所有结论附实测命令/产物（`C:\Temp\p1r_*`）
- [x] 区分「识别缺口」与「下游消费缺口」（§3.1 vs §3.2），并说明「识别正确但链路不可用」的 BPVC/API 案例
- [x] 未改生产代码/配置/其它文档；只新增本报告；未 commit/push
