# P1-7.1 API / ASME 编号规则与现有识别匹配核查（编号识别缺口报告）

| 项目 | 值 |
|------|-----|
| 任务包 | P1-7.1「API / ASME 编号规则与现有识别匹配核查」 |
| 日期 | 2026-11-24 |
| 性质 | 只读摸底 + 实测探针；**不改生产代码/配置** |
| 探针脚本 | `%TEMP%\ds_apiasme_probe.py`（仓库外，`C:\Temp\ds_apiasme_probe.py`） |
| 样本规模 | 40 条（API 20 / ASME 20），全部实际跑过 |
| 结论一句话 | API/ASME 编号在**前端基本全盲**、在**主解析入口 `parse_std_number` 大面积错位或识别不出**，其中 ASME B 系列错位已导致**匹配链路把同一编号判成 mismatch**；ASME BPVC「Section / 册 / 篇」体系几乎全不识别。 |

> 已查阅（文档依据，非记忆）：
> - `docs/reference/附录一 标准代号完整清单.md` §5.2「ASME / API」、§5.4「年份识别规则」、§5.5「当前覆盖状态」
> - `docs/PITFALLS.md` P-04「站点代号带噪音后缀（`API STD`）导致 exact 被判 mismatch」
> - `docs/architecture/modules/parser.md` §解析流程、§已知待办
> - `docs/guides/人工测试方案.md` 1.7「检查国外标准解析：`ASME B16.5` → 代号 ASME + 部分号 5」
> - `docs/reference/announcement-pipeline.md` 第 109 行（`STD_CODE_TOKEN_PATTERN` 与 `parse_std_number` 共用 token 语法）
> - `docs/onboarding/08-known-boundaries.md`（非 GB 标准不自动下载的边界）
>
> 实测证据：`C:\Temp\ds_apiasme_probe.py` 全量输出（本报告表格逐行来自该输出，可复现）。

---

## 1. 现有识别逻辑（代码位置 + 支持规则摘要）

系统里对「标准号字符串」有三条独立解析路径，本次三条全部实测：

| 通道 | 代码位置 | 调用场景 |
|------|---------|---------|
| A `parse_std_number` | `pilotstd/core/std_utils.py:402-447` | 公告提取后语义解析、查询结果比对 `_parse_result_number`、matcher |
| B `StandardParser.parse` | `pilotstd/scan/parser/__init__.py:213-241` | 扫描文件名解析（归档/索引/下载路由） |
| C 前端 `parseStandardNumber` | `web/src/utils/standardParser.ts:5-25` | Web 任务流程回落解析（下载件归档、规范化步骤） |

辅助链路：匹配 `match_result` / `_exact_parse_match`（`pilotstd/query/search_strategy.py:37-190`）、搜索变体 `build_code_variants`（同文件 13-34）。

### 1.1 A：`parse_std_number` 支持规则

入口按优先级依次尝试 8 个解析器（`std_utils.py:433-442`）：

```
sample → variant_prefix → db_standard → general_format → roman → dot_prefix → multi_hyphen → fallback
```

| 维度 | 现状 |
|------|------|
| 代号 | 纯正则、**不查 code_mapping**。`_PFX` 概念只存在于 B 通道；A 通道靠各解析器自己的 `([A-Z]+...)` |
| 类型前缀 | 仅 `_try_parse_general_format` 的 `(?:([A-Z]+)\s+)?` 捕获（`std_utils.py:203-207`），且**只对大小写混合有效**（大小写不敏感 + 类 `[A-Z]+`）：`API Spec` 能进 `num_prefix`，`API STD` 全大写会被 `_try_parse_variant_prefix` 的 token 正则吞进代号 |
| token 正则 | `STD_CODE_TOKEN_PATTERN`（`std_utils.py:316-318`）：`([A-Z][A-Z0-9]*(?:\s+[A-Z][A-Z0-9]*)*...)\s*...(\d+(?:\.\d+)*)\s*[—\-...]\s*(\d{4})`，**只认 4 位年份**、编号体无字母前后缀 |
| 编号体 | `general_format`: `(\d+)(?:\.(\d+))?(?:[Pp](\d+))?`；**无多字母后缀**（`5CT`/`6A`/`938-C` 不行） |
| 年份分隔 | `[—\-:\s]`；合法年份 `(19\|20)\d{2}` |
| 无年份 | 只有 `fallback`（`std_utils.py:278-290`）能返回 year=0，且要求「代号紧跟数字」；带类型前缀/字母/点号即失效 |
| 版次 | **完全不处理** `11th` / `11th Edition` |
| ASME BPVC | **无专用解析器**；通用 roman 解析器要求 `CODE 罗马数字` 紧邻（`std_utils.py:225-245`），遇到 `BPVC` / `Section` 即失败 |

### 1.2 B：`StandardParser.parse` 支持规则

7 通道顺序（`__init__.py:217-226`）：`DB → group → BPVC → ITU → exact → typed → fuzzy → no_year`。

| 维度 | 现状 |
|------|------|
| 代号 | `_PFX`（`_constants.py:132`）：`[A-Z]{2,}(?:[\-\s]+[A-Z]{2,})*(?:/[A-Z]+)?`，支持 `BS EN`/`ANSI/UL`/`ITU-T` |
| 类型前缀 | `_TYPE`（`_constants.py:145`）+ 后处理 `API_TYPES`（`_constants.py:98`）→ 仅 API / MIL / SAE / MSS / IEC 有 handler（`_foreign.py:71-98`）；**ASME 的 PTC/CSD/Y 系列无 handler** |
| 编号体 | `_NUM = [A-Z]?\d{1,6}[A-Z]?`（`_constants.py:133`）：前导 1 字母、尾部**仅 1 字母** |
| 分册 | `_PART_SHORT = [\.\-](\d{1,2})`（`_constants.py:134`） |
| 年份 | `_YEAR4=(19\|20)\d{2}`；`_YEAR_LOOSE=(19\|20)\d{2}\|\d{2}`（`_constants.py:136-137`） |
| 版次跳过 | `edition_skip_pattern()`（`pilotstd/scan/edition_detect.py:65-70`）：`\d+版` / `X Edition`；**不匹配 `11th`** |
| 无年份 | 仅 `_exact_match_no_year`（`_exact_matcher.py:209-235`），且要求 `num_suffix` 非空（219-220），否则拒绝 |
| BPVC | `_ASME_BPVC_RE`（`_constants.py:123-129`）：`^ASME\s+(?:BPVC[\.\-\s]*)?([IVXLCDM]+)(?:[\.\-](\d{1,2})(?=[\-]\d{4}))?(?:[\-](\d{4}))?`；**不含 `Section` / `Div(ision)` / 册篇字母** |
| 校验 | `validate_result`（`_result_builder.py:100-139`）：`require_year=True` 时 year≤0 直接判失败 |

### 1.3 C：前端 `parseStandardNumber` 支持规则

`web/src/utils/standardParser.ts:12` 只有一条正则：

```
^([A-Z][A-Z0-9/]+)\s*(\d+(?:\.\d+)?)\s*[—\-:]\s*(\d{4})$
```

即：**代号不能含空格**、**编号必须是纯数字**、**必须有 4 位年份**。`standardParser.test.ts:86-99` 已把「贪婪吞数字」等行为登记为“当前实现边界（非产品承诺）”。

### 1.4 匹配链路与搜索变体

- `_parse_result_number`（`search_strategy.py:37-43`）直接委托 A 通道。
- `_strip_code_noise`（`search_strategy.py:48-57`）只剥 `STD`/`STANDARD` 尾部噪音。
- `_exact_parse_match`（`search_strategy.py:93-132`）：**顺序号不等立即 mismatch**，不再走模糊回退。
- `build_code_variants`（`search_strategy.py:13-34`）：ASME 罗马前缀生成 `ASME BPVC {prefix}.{number}`，**用卷号当分册号**；API 追加 `API Std` / `API Spec` 变体。

---

## 2. 样本集与实测结果

### 2.0 方法与记号

- 探针直接 import 真实实现：`from pilotstd.core.std_utils import parse_std_number`、`StandardParser(build_code_mapping())`；前端用 `node --experimental-strip-types` **直接加载真实 `standardParser.ts`**（不是正则移植）。
- 运行：`python C:\Temp\ds_apiasme_probe.py`（约 30s，含 node 子进程）。
- 记号 `code/number/part/year/pre/suf`：`pre`=`num_prefix`，`suf`=`num_suffix`，`-`=None；`MISS`=返回 None。
- 「识别错」= 返回非 None 但 `code`/`number`/`part`/`year` 与规范期望不符；「部分」= 主字段对但字母前后缀丢失。

### 2.1 API 样本（20 条）

| # | 编号 | 期望解析 | `parse_std_number` 实测 | `StandardParser` 实测 | 前端实测 | 结论 |
|---|------|---------|------------------------|----------------------|---------|------|
| 1 | `API Spec 5L` | API/5/-/y=0/pre=Spec/suf=L | MISS | API/5/-/y=0/pre=Spec/suf=L | MISS | A/C 识别不出 |
| 2 | `API Spec 5L-2018` | API/5/-/y=2018/pre=Spec/suf=L | MISS | API/5/-/y=2018/pre=Spec/suf=L | MISS | A/C 识别不出 |
| 3 | `API Spec 5CT-2018` | API/5/-/y=2018/pre=Spec/suf=CT | MISS | API/5/-/y=0/pre=Spec/suf=C | MISS | B **识别错**（年份丢、后缀截断） |
| 4 | `API STD 610` | API/610/-/y=0/pre=STD | MISS | MISS | MISS | **三通道全 MISS**（无年份） |
| 5 | `API STD 610-2004` | API/610/-/y=2004/pre=STD | **APISTD/610/-/y=2004** | API/610/-/y=2004/pre=STD | MISS | A **代号污染** |
| 6 | `API RP 520-2020` | API/520/-/y=2020/pre=RP | **APIRP/520/-/y=2020** | API/520/-/y=2020/pre=RP | MISS | A **代号污染** |
| 7 | `API RP 2A-WSD` | API/2/-/y=0/pre=RP | MISS | API/2/-/y=0/pre=RP/suf=A | MISS | A/C 识别不出；B 丢 `-WSD` |
| 8 | `API 6D` | API/6/-/y=0/suf=D | API/6/-/y=0/suf=（空） | API/6/-/y=0/suf=D | MISS | A 部分（后缀丢） |
| 9 | `API 6D-2021` | API/6/-/y=2021/suf=D | API/6/-/y=2021/suf=（空） | API/6/-/y=2021/suf=D | MISS | A 部分（后缀丢） |
| 10 | `API Spec 6A-2018` | API/6/-/y=2018/pre=Spec/suf=A | MISS | API/6/-/y=2018/pre=Spec/suf=A | MISS | A/C 识别不出 |
| 11 | `API Q1` | API/1/-/y=0/pre=Q | MISS | MISS | MISS | **三通道全 MISS** |
| 12 | `API Q1-2023` | API/1/-/y=2023/pre=Q | **APIQ/1/-/y=2023** | API/1/-/y=2023/pre=Q | MISS | A **代号污染** |
| 13 | `API MPMS 11.1` | API/11/1/y=0/pre=MPMS | MISS | MISS | MISS | **三通道全 MISS**（无年份+点号分册） |
| 14 | `API TR 938-C` | API/938/-/y=0/pre=TR | MISS | MISS | MISS | **三通道全 MISS**（字母后缀） |
| 15 | `API Bull 2U` | API/2/-/y=0/pre=Bull/suf=U | MISS | API/2/-/y=0/pre=Bull/suf=U | MISS | A/C 识别不出 |
| 16 | `API 610-11th` | API/610/-/y=0 | API/610/-/y=0 | **API/610/-/y=2011** | MISS | B **版本号当年份** |
| 17 | `API STD 610-11th Edition` | API/610/-/y=0/pre=STD | MISS | **API/610/-/y=2011/pre=STD** | MISS | A 识别不出 + B 版本号当年份 |
| 18 | `API 579-1/ASME FFS-1` | API/579/-/y=0 | API/579/-/y=0 | MISS | MISS | 联合标准 B/C 识别不出 |
| 19 | `API 610-2004` | API/610/-/y=2004 | API/610/-/y=2004 | API/610/-/y=2004 | API/610/-/y=2004 | 全通道 OK（基线） |
| 20 | `API 620-2013` | API/620/-/y=2013 | API/620/-/y=2013 | API/620/-/y=2013 | API/620/-/y=2013 | 全通道 OK（基线） |

### 2.2 ASME 样本（20 条）

| # | 编号 | 期望解析 | `parse_std_number` 实测 | `StandardParser` 实测 | 前端实测 | 结论 |
|---|------|---------|------------------------|----------------------|---------|------|
| 1 | `ASME B16.5` | ASME/16/5/y=0/pre=B | MISS | MISS | MISS | **三通道全 MISS**（无年份；与 `人工测试方案.md` 1.7 期望冲突） |
| 2 | `ASME B16.5-2020` | ASME/16/5/y=2020/pre=B | **ASMEB1/6/5/y=2020** | ASME/16/5/y=2020/pre=B | MISS | A **拆号错位**（number 16→6） |
| 3 | `ASME B16.34-2017` | ASME/16/34/y=2017/pre=B | **ASMEB1/6/34/y=2017** | ASME/16/34/y=2017/pre=B | MISS | A **拆号错位** |
| 4 | `ASME B31.3-2020` | ASME/31/3/y=2020/pre=B | **ASMEB3/1/3/y=2020** | ASME/31/3/y=2020/pre=B | MISS | A **拆号错位** |
| 5 | `ASME B31.1-2020` | ASME/31/1/y=2020/pre=B | **ASMEB3/1/1/y=2020** | ASME/31/1/y=2020/pre=B | MISS | A **拆号错位** |
| 6 | `ASME B1.1-2019` | ASME/1/1/y=2019/pre=B | **ASMEB/1/1/y=2019** | ASME/1/1/y=2019/pre=B | MISS | A **代号污染** |
| 7 | `ASME Y14.5-2018` | ASME/14/5/y=2018/pre=Y | **ASMEY1/4/5/y=2018** | ASME/14/5/y=2018/pre=Y | MISS | A **拆号错位** |
| 8 | `ASME PTC 4-2013` | ASME/4/-/y=2013/pre=PTC | **ASMEPTC/4/-/y=2013** | ASME/4/-/y=2013/pre=（空） | MISS | A 代号污染 + B 部分（系列前缀丢） |
| 9 | `ASME PTC 4` | ASME/4/-/y=0/pre=PTC | MISS | MISS | MISS | **三通道全 MISS** |
| 10 | `ASME C1` | ASME/1/-/y=0/pre=C | MISS | MISS | MISS | **三通道全 MISS**（`ASME C1` 现行目录无此号，见 §6） |
| 11 | `ASME CSD-1` | ASME/1/-/y=0/pre=CSD | MISS | MISS | MISS | **三通道全 MISS** |
| 12 | `ASME BPVC Section VIII Div.1` | ASME/8/1/y=0/pre=VIII | MISS | MISS | MISS | **三通道全 MISS** |
| 13 | `ASME BPVC Section VIII Div. 1-2021` | ASME/8/1/y=2021/pre=VIII | MISS | **ASME/1/-/y=2021** | MISS | B **识别错**（把 Div.1 当序号 1） |
| 14 | `ASME BPVC Section VIII, Division 1-2021` | ASME/8/1/y=2021/pre=VIII | MISS | MISS | MISS | **三通道全 MISS** |
| 15 | `ASME BPVC.VIII.1-2021` | ASME/8/1/y=2021/pre=VIII | MISS | ASME/8/1/y=2021/pre=VIII | MISS | A/C 识别不出（**官方点号写法主入口不支持**） |
| 16 | `ASME BPVC VIII-1-2021` | ASME/8/1/y=2021/pre=VIII | **ASMEBPVCVIII/1/-/y=2021** | ASME/8/1/y=2021/pre=VIII | MISS | A **拆号错位**（number 8→1） |
| 17 | `ASME BPVC.IX-2021` | ASME/9/-/y=2021/pre=IX | MISS | ASME/9/-/y=2021/pre=IX | MISS | A/C 识别不出 |
| 18 | `ASME BPVC.II.D` | ASME/2/-/y=0/pre=II（册 D） | MISS | MISS | MISS | **三通道全 MISS** |
| 19 | `ASME BPVC.II.D.M-2021` | ASME/2/-/y=2021/pre=II（册 D/M） | MISS | MISS | MISS | **三通道全 MISS** |
| 20 | `ASME BPVC Section II Part D` | ASME/2/-/y=0/pre=II（册 D） | MISS | MISS | MISS | **三通道全 MISS** |

### 2.3 匹配链路影响（`match_result`）

本地字段 vs 站点返回编号串（`tests/unit/query/test_search_strategy_code_noise.py` 同口径）：

| 本地标准 | 站点返回编号 | 实测 | 期望 | 说明 |
|---------|-------------|------|------|------|
| API 610-2004 | `API STD 610-2004` | exact | exact | 靠 `_strip_code_noise` 兜住 P-04 |
| API 610-2004 | `API Spec 610-2004` | exact | exact | `Spec` 走 general 分支，恰好未污染 |
| API 6D-2021 | `API Spec 6D-2021` | exact | exact | — |
| API 6D-2021 | `API 6D-2021` | exact | exact | — |
| ASME VIII.1-2021 | `ASME BPVC.VIII.1-2021` | **code_only**（20 分） | exact | A 通道解析出 None → 掉到模糊文本，`8` 不在串中 |
| ASME VIII.1-2021 | `ASME BPVC Section VIII Div.1-2021` | **code_only** | exact | 同上 |
| ASME B16.5-2020 | `ASME B16.5-2020` | **mismatch** | exact | **同一编号与自身比对失败**：A 通道把 B16.5 解析成 number=6 |
| ASME B31.3-2020 | `ASME B31.3-2020` | **mismatch** | exact | 同上，number 解析成 1 |

> 影响：`ASME B16.5-2020` / `ASME B31.3-2020` 这类“站点返回与本地完全同号”的结果会被判 `mismatch`（score 0），低于 `MATCH_SCORE_CONFIRMED=50`（`search_strategy.py:206`），进入待确认/不采纳；ASME BPVC 只有 `code_only`（20 分）同样达不到确认阈值。

### 2.4 搜索变体实测

`build_code_variants("ASME", 8, 2021, num_prefix="VIII")` → `['ASME BPVC VIII.8-2021', 'ASME BPVC VIII.8', 'ASME BPVC VIII-2021']`

- 卷 VIII 的**分册号 1** 被写成 `.{number}`=`8`（应为 `VIII.1`），搜索词本身是错号。
- `API` 变体 → `['API Std 610-2004', 'API Spec 610-2004']`（正常）。

---

## 3. 缺口分类统计

### 3.1 按通道汇总（40 条样本）

| 通道 | 正确 OK | 部分字段缺失 | 识别错 | 识别不出(MISS) |
|------|--------|-------------|--------|----------------|
| A `parse_std_number` | 4 | 2 | **11** | **23** |
| B `StandardParser.parse` | 21 | 1 | **4** | **14** |
| C 前端 `parseStandardNumber` | 2 | 0 | 0 | **38** |

补充计数：

- **三通道同时 MISS（系统对该编号完全无解）= 13 条**：
  `API STD 610`、`API Q1`、`API MPMS 11.1`、`API TR 938-C`、`ASME B16.5`、`ASME PTC 4`、`ASME C1`、`ASME CSD-1`、`ASME BPVC Section VIII Div.1`、`ASME BPVC Section VIII, Division 1-2021`、`ASME BPVC.II.D`、`ASME BPVC.II.D.M-2021`、`ASME BPVC Section II Part D`。
- **前后端结果不一致或单边失败 = 38/40**；只有 `API 610-2004`、`API 620-2013` 两条全通道一致。
- 前端覆盖：仅「纯数字编号 + 冒号/短横 + 4 位年份」的 `API 610-2004` 型可解析（2/40）。

### 3.2 缺口类型（A 识别不出 / B 识别错）

**类型 A：完全识别不出**

| 子类 | 样本 | 根因 |
|------|------|------|
| A1 无年份 | `API STD 610`、`API Q1`、`API MPMS 11.1`、`ASME B16.5`、`ASME PTC 4`、`ASME C1`、`ASME CSD-1`、`ASME BPVC Section VIII Div.1`、`ASME BPVC.II.D`、`ASME BPVC Section II Part D` | B 通道 `validate_result` 要求 year>0（`_result_builder.py:122-127`），`_exact_match_no_year` 只放行字母后缀（`_exact_matcher.py:219-220`）；A 通道各解析器都要 4 位年份，`fallback` 又只认「代号紧邻数字」 |
| A2 BPVC 官方写法 | `ASME BPVC.VIII.1-2021`、`ASME BPVC.IX-2021`、`ASME BPVC.II.D.M-2021` | A 通道无 BPVC 解析器（通用 roman 被 `BPVC.` 卡住）；B 通道 `_ASME_BPVC_RE` 只认 `ASME [BPVC] 罗马` 紧邻（`_constants.py:123-129`），`Section`/`Part`/册篇字母不进 |
| A3 多字母后缀/联合标准 | `API TR 938-C`、`API 579-1/ASME FFS-1` | `_NUM` 与 general 编号体仅 1 个字母后缀；联合标准无解析分支 |

**类型 B：识别出但字段错位 / 年份错**

| 子类 | 样本（证据） | 根因 |
|------|-------------|------|
| B1 ASME B 系列被拆号 | `ASME B16.5-2020`→`ASMEB1/6/5`；`B16.34-2017`→`ASMEB1/6/34`；`B31.3-2020`→`ASMEB3/1/3`；`B1.1-2019`→`ASMEB/1/1`；`Y14.5-2018`→`ASMEY1/4/5` | A 通道 `_try_parse_variant_prefix`（`std_utils.py:378-399`）复用 `STD_CODE_TOKEN_PATTERN`（316-318），代号组 `[A-Z][A-Z0-9]*(?:\s+[A-Z][A-Z0-9]*)*` **允许尾随数字**，把 `B16`/`B31`/`Y14` 当成代号段，剩余 `6`/`3` 当序号 |
| B2 API 大写类型前缀污染代号 | `API STD 610-2004`→`APISTD`；`API RP 520-2020`→`APIRP`；`API Q1-2023`→`APIQ` | 同一 token 正则把全大写类型词（`STD`/`RP`/`Q1`）并入代号；小写混合（`Spec`）反而不污染——**同一体系因大小写产生两种结果** |
| B3 BPVC 卷号被序号吃掉 | `ASME BPVC VIII-1-2021`→`ASMEBPVCVIII/1`；SCAN `ASME BPVC Section VIII Div. 1-2021`→`ASME/1` | A 通道 variant 把 roman 并入代号、`1` 当序号；B 通道 exact 通道把 `Div. 1` 的 `1` 当序号（BPVC 专用通道被 `Section` 阻断，回落到通用 exact） |
| B4 系列前缀丢失 | SCAN `ASME PTC 4-2013`→`pre=（空）`；`API RP 2A-WSD`→`suf=A`（丢 WSD） | `_PFX` 贪婪吃掉 `ASME PTC` 后 `trim_prefix` 截回 `ASME`，ASME 无 series handler；`_NUM` 仅 1 字母后缀 |
| B5 版本号被当年份 | SCAN `API 610-11th`→y=2011；`API STD 610-11th Edition`→y=2011 | `regex_typed` 的 `_YEAR_LOOSE` 允许 2 位年份（`_constants.py:137`），`edition_skip_pattern` 不匹配 `11th`；无「两位年份后不得跟 st/nd/rd/th」约束 |
| B6 字母后缀截断/年份丢失 | SCAN `API Spec 5CT-2018`→suf=C、y=0 | `_NUM=[A-Z]?\d{1,6}[A-Z]?` 只允许 1 个尾字母，`T-2018` 落在匹配外，年份也一起丢 |

### 3.3 与现有文档/测试的冲突

| 文档/测试 | 内容 | 与实测冲突 |
|-----------|------|-----------|
| `docs/guides/人工测试方案.md:71` | 1.7 `ASME B16.5` → 代号 ASME + 部分号 5 | 实测 B 通道**拒绝**该文件名（`tests/test_scanner.py:135-138` 明确断言 `assertIsNone`），A/C 也 MISS |
| `docs/reference/附录一 标准代号完整清单.md:243` | 无年份 → `year=0` | 实测无年份在 B 通道被 `validate_result` 拒绝；A 通道仅 fallback 有限支持 |
| `docs/reference/附录一 标准代号完整清单.md:178,247` | “ASME BPVC 罗马数字 ❌ / match_result 无法正常匹配” | 部分成立：SCAN 对 `BPVC.VIII.1-2021` 可解析，但 A 通道 + match_result 确实不可用；文档未覆盖 `Section`/册篇 |
| `tests/unit/core/test_std_utils.py:216-218` | `parse_std_number("ASME VIII.1-2021")` 仅断言 `is not None` | 断言过弱，未锁 `number=8/part=1`，错位不会被测出 |
| `tests/test_query.py:953-963` | 期望变体 `ASME BPVC VIII.8-2021` | 把「卷号当分册号」的错误固化进测试 |

---

## 4. 修复建议（缺口 → 改哪里 → 风险）

通用原则：A/B 通道解析口径要统一（同一编号两边字段应一致），否则匹配链路会继续在「扫描能解析、比对解析不出」之间抖动。建议按 P0→P2 分批，每批先补失败测试。

| ID | 缺口 | 改动点（文件:函数/正则） | 建议改法 | 风险 / 注意事项 |
|----|------|------------------------|----------|----------------|
| **G1**（P0） | ASME B 系列被拆号（`ASME B16.5-2020`→`ASMEB1/6`），连带 `match_result` 自 mismatch | `pilotstd/core/std_utils.py:378-399` `_try_parse_variant_prefix`；需要时约束 `std_utils.py:316-318` `STD_CODE_TOKEN_PATTERN` | 在 variant 分支**不直接返回 token 结果**：代号段限制为 `[A-Z][A-Z]*`（不含数字），或命中 `STD_CODE_TOKEN_PATTERN` 后再用通用格式重解析一次，取 `number/part` 正确者；确保 `ASME B16.5-2020` → `ASME/16/5/y=2020` | 🔴 `STD_CODE_TOKEN_PATTERN` 被公告提取共用（`pilotstd/announcement/parser.py:11,27,135,274`，跨层不变量测试 `tests/test_announcement_parser.py:192-205`）。优先只改 `_try_parse_variant_prefix` 的后处理，**不要直接改共享正则**；必须回归 `DB52T`/`NB/SH/T`/`HG/T 一` 变体用例 |
| **G2**（P0） | BPVC 官方写法（`BPVC.VIII.1`、`Section VIII Div.1`、`II.D`、`II.D.M`）A 通道全 MISS；B 通道 Section/册篇不识别 | `std_utils.py` 新增 `_try_parse_bpvc`（插在 variant 之前）；`pilotstd/scan/parser/_constants.py:123-129` 扩展 `_ASME_BPVC_RE`；`_exact_matcher.py:128-154` | 统一 BPVC 语法：`ASME (BPVC[.\-]?)? (Section\s+)? ([IVXLCDM]+) (Div(ision)?\.?\s*(\d))? (\.?([A-Z](\.?[A-Z])*))? (-year)?`；卷号→number（阿拉伯），分册→part，册/篇字母（D/M）→`num_suffix`，year 可缺省 | 🟠 `ParsedStdInfo` 没有「册/篇」字段（`models.py:19-21` 只有 num_prefix/num_suffix/part）。复用 `num_suffix="D"`/`"D.M"` 属**语义约定变更**，会影响 `get_full_number`、归档文件名、DB 唯一键；若新增字段则触发 schema/API 变更（跨模块，需单独立项）。BPVC 无年份（`ASME BPVC.II.D`）同样受 G5 约束 |
| **G3**（P1） | API 大写类型前缀污染代号（`API STD 610`→`APISTD`） | `std_utils.py:378-399` `_try_parse_variant_prefix`；`pilotstd/query/search_strategy.py:48-57` `_strip_code_noise` | variant 结果里把首个 token 之后命中 `API_TYPES`（`_constants.py:98`）的段拆到 `num_prefix`；`_strip_code_noise` 噪音表补 `SPEC/RP/BULL/TR/MPMS/TDB/PUBL`，或直接改用修复后的 `code` | 🟡 与 G1 同一函数，建议合并一次改；`_strip_code_noise` 放宽会改变匹配判定，需回归 `test_search_strategy_code_noise.py`（3 例）与 `test_adapters.py:162-170` |
| **G4**（P1） | 版次被当年份（`API 610-11th`→2011） | `pilotstd/scan/parser/__init__.py:85-115` 的 `regex_typed/regex_typed_v2`；`_constants.py:137` `_YEAR_LOOSE`；`pilotstd/scan/edition_detect.py:65-70` `edition_skip_pattern` | 方案 a：`_YEAR_LOOSE` 加负向断言「两位年份后不得紧跟 `st|nd|rd|th`」；方案 b：`_preprocess_input` 先用 `extract_edition` 识别并剥离版次再匹配；保留 `GB1234-86` 两位年份路径（`_expand_short_year`，`__init__.py:174-187`） | 🟠 两位年份是 D1-1 修复过的既有契约（`tests/test_scanner.py:94-97`、`_number_extractor.py:12-20`）。改 `_YEAR_LOOSE` 影响全部 typed 通道，需全量回归 parser 测试 |
| **G5**（P1） | 无年份编号大面积识别不出（`API STD 610`/`ASME B16.5`/`API Q1`…） | `_result_builder.py:100-139`；`_exact_matcher.py:209-235`；`std_utils.py:278-290`；`models.py:57-60` `is_valid_standard` | 对 `FOREIGN_CODE_SET`（`_constants.py:63-90`）内的 API/ASME 等放开 `require_year=False`（BPVC/类型前缀/点号分册同样走该通道）；A 通道在 variant 后增加「代号+编号」兜底（含类型前缀与 `.part`）；**先统一文档口径**（附录 §5.4 与代码二选一） | 🔴 「year>0」是库表/文件名/去重/`is_valid_standard` 的隐含前提（`models.py:57-60`）。放宽会产生 year=0 记录，需确认 DB schema 允许、归档命名不冲突、前端展示正确；建议先做只读影响面核查，再决定是否改 |
| **G6**（P2） | 多字母后缀截断（`5CT`→`C`、`RP 2A-WSD`→`A`） | `_constants.py:133` `_NUM` | `_NUM` 尾字母 `[A-Z]?` → `(?:[A-Z]{1,3})?`（可选再加 `(?:-[A-Z]{1,3})?` 覆盖 `2A-WSD`） | 🟠 `_NUM` 被所有国外代号共用（`_PFX` 后接 `_NUM`），放宽会改变 `MIL-STD-810G`、`MSS SP 55` 等既有解析，需逐代号回归 |
| **G7**（P2） | ASME 系列（PTC/CSD/Y）前缀丢失/不识别 | `pilotstd/scan/parser/_foreign.py:101-126` `_handle_special_sep`（ASME 分支目前 `pass`） | 在 ASME handler 里按 `ASME\s+(PTC|CSD|Y|NQA)\b` 写入 `num_prefix`；并把 `ASME PTC`/`ASME CSD` 加入多词前缀保护（`_constants.py:11-61`） | 🟢 局部；但 `PTC` 与 `B16` 的 `B` 语义不同（系列 vs 分类字母），需确认 `get_full_number`（`models.py:45-55`）的拼接分隔符正确 |
| **G8**（P2） | `build_code_variants` 用卷号当分册号 | `pilotstd/query/search_strategy.py:13-34` | 签名增加 `part`，ASME 变体改为 `ASME BPVC {prefix}.{part}`（无 part 时回退 `{prefix}.{number}` 或 `{prefix}-{year}`） | 🟡 现有测试 `tests/test_query.py:963` 断言 `ASME BPVC VIII.8-2021`（错误期望），需同批改测试；搜索变体变化会影响适配器命中率，需真实站点抽验 |
| **G9**（P1） | 前端解析器几乎不覆盖 API/ASME（38/40 MISS），下载件被跳过归档 | `web/src/utils/standardParser.ts:12` | 见 §5，前端需同步改；或改为优先使用后端字段、前端不做标准号解析 | 🟡 前端四件套必跑；`standardParser.test.ts:86-99` 的“当前实现边界”断言必须同批更新 |

---

## 5. 特别说明：前端 `standardParser.ts` 是否需要同步改

**需要同步改，而且优先级不低于后端。**

理由（实测 + 调用链）：

1. 覆盖不足：40 条 API/ASME 样本前端只解析出 2 条（`API 610-2004`、`API 620-2013`），38 条返回 `null`。所有 ASME（代号含空格）、`API STD/Spec/RP`（类型词）、`API 6D`（字母后缀）、无年份编号全部失败。
2. 有真实业务后果：`web/src/utils/taskPipeline.ts:39-54` 对下载结果调用 `parseStandardNumber(dl.standard_number)`，**解析失败直接 `continue` 跳过归档**（仅 `console.warn`）。即 `ASME B16.5-2020`、`API STD 610-2004`、`ASME BPVC.VIII.1-2021` 这类下载件不会进入归档队列。`web/src/views/TaskView.vue:304-312` 的规范化步骤同样在字段缺失时回落该函数，失败即跳过。
3. 前后端不一致：同一条编号 `StandardParser` 能解析、前端 `null`（38/40），Web 侧展示/归档与桌面侧行为分叉。

建议（按侵入性从低到高）：

- **方案一（推荐）**：前端不再自行解析标准号。`dl.standard_number` 下载结果应带后端已解析字段（`logical_code/number/year/num_prefix/part`，与 scan 结果同构）；解析失败时至少不要静默跳过归档，改为“落库待确认/提示用户”，避免丢件。
- **方案二（最小正则修复）**：把 `standardParser.ts:12` 扩展到与 A/B 通道同口径：允许代号含空格与多段、可选类型词、编号前后字母、`.part`、年份可缺省；返回 `part/num_prefix/num_suffix`。必须同批更新 `standardParser.test.ts`（尤其 86-99 的边界断言）并跑 `pnpm.cmd run type-check/lint/test/build`。
- 建议优先修后端 G1~G3 后再让前端复用同一套规则（或共享契约测试样例），避免前端成为“第二套口径”。

---

## 6. 复现方式与边界

```powershell
# 仓库根目录
python C:\Temp\ds_apiasme_probe.py
# 需要输出机器可读 JSON 时：
$env:P1_DUMP_JSON=1; python C:\Temp\ds_apiasme_probe.py
```

- 探针依赖 Node（本机 v24.15.0）直接加载真实 `standardParser.ts`；若 Node 版本过低，探针会报 `node 执行失败`，此时可仅看 A/B 两通道。
- 本次为**只读核查**：未改任何生产代码/配置/测试，未 git commit/push；B 通道使用 `build_code_mapping()` 真实映射。
- `ASME C1` 说明：ASME 现行 C 类标准为 **CSD-1**（Controls and Safety Devices for Automatically Fired Boilers，如 [ASME CSD-1-2024](https://store.sfs.fi/en/asme-csd-1-2024)、[ANSI/ASME CSD-1 修订公告](https://share.ansi.org/Shared%20Documents/Standards%20Action/2011%20PDFs/SAV4242.pdf)），公开目录中未见 `ASME C1` 标准号。本报告按任务样例字面测试；无论按 `C1` 还是 `CSD-1`，当前均为三通道 MISS，结论不变。**建议任务方确认 `ASME C1` 是否为笔误**。
- 未覆盖：`API 579-1/ASME FFS-1` 这类联合标准仅验证“识别不出”，未验证归档命名；BPVC 册/篇字母的存储字段方案（新增字段 vs 复用 `num_suffix`）需单独立项评估 schema 影响；无年份放开后的 DB/索引影响未核查（见 G5）。

---

## 7. 交付自检

- [x] API 样本 ≥8（实际 20）、ASME 样本 ≥8（实际 20），全部实际跑过
- [x] 每条缺口均有「期望 vs 实际」证据（§2 表格 + §3 根因）
- [x] 区分「识别不出」（23 / 14 / 38 by 通道）与「识别错」（11 / 4 / 0）
- [x] 前端与后端对同一批样本做了对比（38/40 不一致）
- [x] 未改生产代码/配置/其他文档；探针在仓库外 `%TEMP%`
- [x] 修复建议全部落到「文件:函数/正则 + 风险」
