# P1-5 复核 · 「未知标准」定性刷新（2026-11-25）

> **结论先行（TL;DR）**
>
> 1. **数据层未变**：生产 `file_index` 仍为 776 条，状态分布与 2026-11-24 摸底**逐值相同**
>    （现行 572 / 废止 95 / 作废 58 / 被代替 21 / 即将实施 20 / 未生效 10）。
> 2. **代码口径已变**：状态口径修复 `5c501fbb`（作废计入废止族）已在 HEAD（`bbc60b61`）。
>    按 **HEAD 真实代码**在「生产 shape 夹具」上执行：**已废止 174、未知 30**（修复前 116 / 88），
>    总数守恒 776。这与上一轮报告 §5.1 对「完成 A1 后」的预测 **572 / 174 / 30 完全一致**。
> 3. **定性结论仍成立**：剩余 30 条「未知」= **即将实施 20 + 未生效 10**，
>    **真未知仍然 = 0**（解析失败 / 状态字段缺失 / 空编号 / 空名称 / 非标准内容全部为 0）。
> 4. **但「未知」桶未归零**：C2（`未生效` 归一 + `即将实施` 统计桶）未做；HEAD 下
>    `?status=未生效` 仍被**静默忽略并返回全表 776**；写入端仍可再生产 `未生效` 脏值。
> 5. **关键部署事实**：生产 API 运行版本 `0e92e5d2`（构建于 2026-11-24 19:34），
>    落后 HEAD **45 个提交**且**不含**修复 `5c501fbb`（修复提交时间 20:50）——
>    **A1 修复尚未上线**，所以当前生产页面实测仍是 `88 / 116`。页面数字要等部署后才变。
> 6. **新发现口径漏洞**：`未生效` 过滤静默失效、`unknown` 仍是「补集」机制（任何新状态都会被吞进未知）
>    —— 均有 `文件:行` 与建议修法，见 §5；本次**未改任何代码**。

---

## 0. 已查阅依据（AGENTS.md §0 强制）

| 类型 | 路径 / 位置 | 用途 |
|---|---|---|
| 上一轮报告 | `docs/plans/2026-11-24-p1-unknown-standards.md` §1.4「口径推导」L114-125、§5.1 L328-340 | **复用其分类规则**（作废族 / 即将实施 / 未生效 / 真未知）与预测数字 |
| 修复决策 | `docs/plans/2026-11-24-p1-fix-decision.md` L20（A1）、L41-42（C2/C3）、L75、L89-90 | 确认 A1 已合入、C2 待产品确认、C3 需窗口 |
| 模块文档 | `docs/architecture/modules/manager.md` L371-383；`docs/architecture/modules/core.md` L888-897 | 修复后的官方口径（废止族 = 废止+被代替+作废） |
| 已知边界 | `docs/onboarding/08-known-boundaries.md` §4 L129-147 | `standard_validity` 非归档第一权威，不构成本次「未知」成因 |
| 代码 | 见 §4 逐条 `文件:行` | 口径定义与执行路径的唯一事实源 |
| 仓库检索 | `python scripts/find_docs.py "未知 状态 口径 废止 作废"` | 命中 core.md / manager.md 状态口径节，已打开 |

---

## 1. 当前 vs 上一轮：数量对比与变化原因

### 1.1 四类定性对比（口径不变，数字按 HEAD 代码重算）

| 类 | 上一轮（2026-11-24，旧代码口径） | 当前（2026-11-25，HEAD 代码口径） | 变化 | 变化原因（可追溯） |
|---|---:|---:|---:|---|
| A. `作废`（废止族） | **58**（被折叠进「未知」） | **58**（归入「已废止」） | 未知 −58 / 已废止 +58 | 修复 `5c501fbb`：`standard_service.py` L29-30、L89-91；`_file_index_query.py` L97-103 |
| B. `即将实施` | **20**（在「未知」桶） | **20**（仍在「未知」桶） | 0 | 无统计桶（B 未做），且 `unknown` 补集未排除 `即将实施`：`standard_service.py` L92-102 |
| C. `未生效` | **10**（在「未知」桶，`status_key=unknown`） | **10**（同左） | 0 | C2 未做：`status.py` L79-81 无别名、L106-115 回退 `unknown` |
| D. 真未知（解析失败/字段缺失/非标准内容） | **0** | **0** | 0 | 数据完整性四项全 0（§2.3 SQL ④） |
| **合计** | **88** | **30 + 58 = 88**（归类改变，总量不变） | — | 纯**口径修正**，非数据增减 |

> 一句话：**88 还是那 88 条**，只是 58 条 `作废` 从「未知」搬到了「已废止」；没有新增/丢失任何记录。

### 1.2 三卡数字对比（区分「部署态」与「HEAD 代码态」）

| 指标 | 上一轮实测（旧代码） | 当前 **HEAD 代码口径**（夹具实测） | 当前**生产部署态**实测（旧代码） |
|---|---:|---:|---:|
| active（现行） | 572 | **572** | 572 |
| inactive（已废止） | 116 | **174** | 116 |
| unknown（未知） | 88 | **30** | 88 |
| total（守恒） | 776 | **776** | 776 |
| 首页 `/api/stats` 的 expired | 116 | **174** | 116 |

- 「HEAD 代码口径」= 用生产实读的状态分布（§2.1）喂给 **HEAD 真实代码**（`StandardService.get_stats`、
  `FileIndexQuery.get_status_stats`）得到的数字，见 §2.4。
- 「生产部署态」= 直接调生产 `GET /api/standards/status/stats` 的结果（附录 A）；生产版本落后 HEAD 45 个提交，
  所以**页面尚未体现修复**。
- 修复后 `?status=unknown` 的 `status_key` 集合预计为 `{upcoming, unknown}`、**不含 `voided`**；
  夹具实测为 `{upcoming:20, unknown:10}` —— 与上一轮 §5.1 的验收条件一致。

### 1.3 上一轮预测 vs 本次实测

上一轮报告 §5.1 L331 预测「完成 A1 后」：`现行 572 / 已废止 174 / 即将实施（无桶）/ 未知 30 / 合计 776`。
本次按 HEAD 代码实测：**572 / 174 / 30 / 776** —— **逐项命中**，说明 A1 的效果与摸底结论自洽。

---

## 2. 数据来源与方法（真实取证，非回忆）

### 2.1 生产只读测量（数据层）

- 被测环境：生产 Docker API `http://192.168.1.18:9028`（只读）。
- 健康检查：`/api/health` → `200`，`version=0e92e5d2c94a22424120de756b3e4a0d255632e8`，
  `schema_version=76`；采集时间 **2026-11-25 19:09–19:25（Asia/Shanghai）**。
- 只读客户端：仓库现成 `scripts/ops/_probe_common.py`——写方法白名单只有
  `POST /api/login`、`POST /query`（白名单常量 L62-65），且 `POST /query` 发送前由
  `_assert_read_only_sql()` 强制单条 `SELECT/PRAGMA/EXPLAIN` 并拒绝写关键字（L158-175）。
- 登录：`POST /api/login` → `200 登录成功（用户 mystdpilot，角色 admin）`。
- **只读自证**：本次全部请求序列 = `POST /api/login`（2 次）+ `POST /query`（17 条单条 `SELECT`）+
  若干 `GET`；`client.write_calls()` 只含上述两类（附录 B）。**未执行任何 `INSERT/UPDATE/DELETE`。**

### 2.2 本地库不可用说明

本地 `data/pilotstd.db` 存在（4,231,168 B，mtime 2026-11-25 06:16），但
**`file_index` = 0 行**（`standard_validity` 仅 1 行）——这是被清空的开发库，不是生产快照，
**不能用于本复核**。因此与上一轮一致，改用**生产只读 SQL**（数据层 = 生产实测，可信度最高）。

### 2.3 实际执行的关键只读 SQL（逐条跑过）

```sql
-- ① 生产原始状态分布（776 条总盘）
SELECT status, COUNT(*) AS c FROM file_index WHERE status IS NOT NULL
GROUP BY status ORDER BY c DESC;
-- → 现行 572 / 废止 95 / 作废 58 / 被代替 21 / 即将实施 20 / 未生效 10

-- ② 规模与空值自证
SELECT COUNT(*) FROM file_index;                       -- 776
SELECT COUNT(*) FROM file_index WHERE status IS NULL;  -- 0

-- ③ HEAD 口径「未知」明细（NOT IN 四值：现行/废止/被代替/作废）
SELECT id, logical_code||' '||number||CASE WHEN year>0 THEN '-'||year ELSE '' END AS num,
       status, std_name, file_path, scanned_at
FROM file_index
WHERE status IS NOT NULL AND status NOT IN ('现行','废止','被代替','作废')
ORDER BY status, logical_code, number, part;            -- 30 行（§3 全量列出）

-- ④ 30 条数据质量（证明不是脏数据）
SELECT status, COUNT(*) c,
       SUM(CASE WHEN TRIM(std_name)='' THEN 1 ELSE 0 END) empty_name,
       SUM(CASE WHEN number<=0 THEN 1 ELSE 0 END) bad_number,
       SUM(CASE WHEN TRIM(logical_code)='' THEN 1 ELSE 0 END) empty_code,
       SUM(CASE WHEN year<=0 THEN 1 ELSE 0 END) no_year,
       SUM(CASE WHEN file_path LIKE '%过期作废%' THEN 1 ELSE 0 END) in_expire_dir
FROM file_index WHERE status IS NOT NULL AND status NOT IN ('现行','废止','被代替','作废')
GROUP BY status;
-- → 即将实施 20：empty_name 0 / bad_number 0 / empty_code 0 / no_year 0 / in_expire_dir 0
-- → 未生效  10：同上全 0

-- ⑤ 是否存在超出 Status 九值枚举的脏值
SELECT status, COUNT(*) FROM file_index WHERE status NOT IN
('现行','即将实施','废止','已废止','被代替','作废','过期','待确认','未知')
GROUP BY status;                                        -- → 未生效 10（唯一枚举外值）

-- ⑥ 与 standard_validity / announcement_match 交叉对照（30 条）
-- → validity：即将实施 16 / 未知 9 / 现行 5
-- → 公告口径：即将实施 24 / 无匹配 6；其中「未生效」10 条公告口径 100% = 即将实施
```

### 2.4 HEAD 代码口径验证（计算层）

为避免「只按记忆读代码」，把**生产实测分布**（776 行）灌入临时 SQLite 夹具
（`%TEMP%\p1r_fixture.db`），直接调用 **HEAD 真实代码**（不是重写规则）：

| 调用 | 实测输出 |
|---|---|
| `StandardService.get_stats()` | `{"现行":572, "已废止":174, "未知":30}`，total 776 |
| `StandardService.get_list(filters={'status': resolve_status_filter('unknown')})` | total **30** |
| `... resolve_status_filter('withdrawn')` | total **174** |
| `... resolve_status_filter('voided')` | total **58**（作废仍可单独筛出，未被吞并） |
| `... resolve_status_filter('upcoming')` | total **20** |
| `... resolve_status_filter('未生效')` | 解析为 `None` → 过滤被忽略 → total **776**（漏洞，见 §5.1） |
| `FileIndexQuery.get_status_stats()`（首页卡片源） | `{current:572, expired:174, pending:0, upcoming:20}` |
| 未知桶 30 条的 `status_key` 分布 | `upcoming:20, unknown:10`（**不含 voided**） |
| `status_key('未生效')` / `normalize_status('未生效')` | `'unknown'` / `'未生效'`（原样） |
| `search_strategy.map_status('未生效')` | `'未生效'`（写入侧仍原样透传） |

单测复核：`python -m pytest tests/test_standard_service.py tests/unit/core/test_file_index_query_snapshot.py -q`
→ **47 passed**（含 2 例锁定生产分布 572/95/58/21/20/10 → 174/30；1 例锁定首页 `expired` 含作废）。

---

## 3. 真未知剩余清单（30 条全量）+ 类别统计

> 列说明：`file_index.status` 是状态判定的唯一输入字段；`validity(chk)` 来自
> `standard_validity`（`LEFT JOIN`，JOIN 键含年份）；`公告口径/实施日` 来自
> `announcement_match.result_json`；「HEAD 归类」是按 HEAD 代码算出的归属。
> **30 条均为真实标准文件**（路径在 `/standards/...` 标准库树内、名称/编号/年份完整、`file_path` 无空值）。

### 3.1 类别统计

| 类别 | 条数 | 目录 | validity 分布 | 公告口径 | HEAD 下的 `status_key` | 定性 |
|---|---:|---|---|---|---|---|
| 即将实施 | **20** | 常规 20 / 过期作废 0 | 即将实施 11 / 现行 5 / 未知 4 | 即将实施 14 / 无匹配 6 | `upcoming` | 合法状态，统计页无独立桶 |
| 未生效 | **10** | 常规 10 / 过期作废 0 | 即将实施 5 / 未知 5 | **即将实施 10/10** | `unknown`（枚举外值回退） | 「即将实施」同义词/脏值 |
| **真未知** | **0** | — | — | — | — | 解析失败/状态缺失/空字段/非标准内容均为 0 |
| 合计 | **30** | 常规 30 | 即将实施 16 / 现行 5 / 未知 9 | 即将实施 24 / 无匹配 6 | `upcoming` 20 + `unknown` 10 | 全部有确定语义 |

### 3.2 即将实施 20 条（`status_key=upcoming`）

| # | id | 标准号 | 名称 | file_index.status | validity(chk) | 公告口径 / 实施日 | HEAD 归类 |
|---:|---:|---|---|---|---|---|---|
| 1 | 3562 | GB 2970-2026 | 6 厚钢板超声检测方法 | 即将实施 | 未知(1) | 无匹配 | 即将实施 |
| 2 | 3438 | GB 4053-2025 | 固定式金属梯及平台安全要求 第3部分-工业防护栏杆及平台 | 即将实施 | 现行(2) | 即将实施 / 2027-01-01 | 即将实施 |
| 3 | 3596 | GB 5613-2026 | 6 铸钢牌号表示方法 | 即将实施 | 即将实施(1) | 无匹配 | 即将实施 |
| 4 | 3600 | GB 7607-2026 | 6 柴油机油换油指标 | 即将实施 | 即将实施(1) | 无匹配 | 即将实施 |
| 5 | 3551 | GB 13237-2026 | 6 优质碳素结构钢冷轧钢板及钢带 | 即将实施 | 即将实施(1) | 无匹配 | 即将实施 |
| 6 | 3017 | GB 15499-2025 | 生产安全事故伤害损失工作日判定 | 即将实施 | 即将实施(1) | 即将实施 / 2027-01-01 | 即将实施 |
| 7 | 3553 | GB 18047-2026 | 车用压缩天然气 | 即将实施 | 未知(0) | 即将实施 / 2027-08-01 | 即将实施 |
| 8 | 3573 | GB 38305-2025 | 头部防护 救援头盔 | 即将实施 | 现行(1) | 即将实施 / 2027-01-01 | 即将实施 |
| 9 | 3618 | GB/T 2520-2026 | 冷轧电镀锡钢板及钢带 | 即将实施 | 即将实施(1) | 即将实施 / 2027-02-01 | 即将实施 |
| 10 | 3609 | GB/T 12337-2026 | 钢制球形储罐 | 即将实施 | 即将实施(1) | 即将实施 / 2027-04-01 | 即将实施 |
| 11 | 3611 | GB/T 14180-2026 | 缠绕式垫片试验方法 | 即将实施 | 现行(1) | 即将实施 / 2027-02-01 | 即将实施 |
| 12 | 3612 | GB/T 14983-2026 | 耐火材料 抗碱性试验方法 | 即将实施 | 现行(1) | 即将实施 / 2027-02-01 | 即将实施 |
| 13 | 3703 | GB/T 20671-2026 | 26 非金属垫片材料分类体系及试验方法 第4部分：垫片材料密封性试验方法 | 即将实施 | 即将实施(1) | 无匹配 | 即将实施 |
| 14 | 3616 | GB/T 20671-2026 | 26 非金属垫片材料分类体系及试验方法 第11部分：合成聚合材料抗霉性测定方法 | 即将实施 | 即将实施(1) | 无匹配 | 即将实施 |
| 15 | 3619 | GB/T 30825-2026 | 热处理温度测量 | 即将实施 | 现行(1) | 即将实施 / 2027-02-01 | 即将实施 |
| 16 | 3632 | GB/T 47881-2026 | 稀土系储氢合金 吸放氢反应热力学性能测试方法 | 即将实施 | 未知(0) | 即将实施 / 2027-02-01 | 即将实施 |
| 17 | 3634 | GB/T 47921-2026 | 钢制输氢管道氢脆敏感性测试和评估方法 | 即将实施 | 即将实施(1) | 即将实施 / 2027-02-01 | 即将实施 |
| 18 | 3635 | GB/T 47995-2026 | 变形高温合金 焊丝 | 即将实施 | 即将实施(1) | 即将实施 / 2027-02-01 | 即将实施 |
| 19 | 3636 | GB/T 48191-2026 | 环氧乙烷反应器 | 即将实施 | 即将实施(1) | 即将实施 / 2027-04-01 | 即将实施 |
| 20 | 3637 | GB/T 48307-2026 | 锂离子动力电池产品缺陷风险防范 生产管理要求 | 即将实施 | 未知(0) | 即将实施 / 2027-04-01 | 即将实施 |

### 3.3 未生效 10 条（`status_key=unknown`，语义 = 即将实施）

| # | id | 标准号 | 名称 | file_index.status | validity(chk) | 公告口径 / 实施日 | HEAD 归类 |
|---:|---:|---|---|---|---|---|---|
| 21 | 3031 | GB 27900-2026 | 消防员呼救器 | 未生效 | 未知(2) | 即将实施 / 2027-04-01 | 未知（应=即将实施） |
| 22 | 3667 | GB/T 711-2026 | 优质碳素结构钢热轧钢板和钢带 | 未生效 | 即将实施(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 23 | 3638 | GB/T 4842-2026 | 纯氩、高纯氩和超纯氩 | 未生效 | 未知(0) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 24 | 3658 | GB/T 6396-2026 | 复合钢板 力学及工艺性能试验方法 | 未生效 | 即将实施(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 25 | 3491 | GB/T 8028-2026 | 汽油机油换油指标 | 未生效 | 未知(0) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 26 | 3498 | GB/T 16923-2026 | 钢件的正火与退火 | 未生效 | 即将实施(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 27 | 3494 | GB/T 47832-2026 | 电动机综合保护装置通用技术条件 | 未生效 | 未知(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 28 | 3509 | GB/T 47877-2026 | 液氢储运用不锈钢无缝钢管 | 未生效 | 即将实施(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 29 | 3492 | GB/T 47880-2026 | 稀土系储氢合金 吸放氢循环稳定性测试方法 | 未生效 | 即将实施(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |
| 30 | 3503 | GB/T 47914-2026 | 复合钢管超声检测方法 | 未生效 | 未知(1) | 即将实施 / 2027-02-01 | 未知（应=即将实施） |

### 3.4 30 条「不是脏数据」的完整性证据

| 维度 | 结果 | 来源 |
|---|---|---|
| 空名称 / 坏编号 / 空代号 / 缺年份 | **0 / 0 / 0 / 0** | SQL ④ |
| `file_path` 为空 | **0** | SQL 附加 |
| `status` 为 NULL | **0**（全表 0） | SQL ② |
| 状态值超出 `Status` 九值枚举 | 仅 `未生效` 10 条（语义=即将实施） | SQL ⑤ |
| 目录分布 | 常规 30（过期作废 0） | SQL ④ |
| 公告侧可匹配 | 24 / 30（其余 6 条无公告记录，仅 Query 侧状态） | SQL ⑥ |
| 名称解析残留（数字前缀，如 `6 厚钢板…`） | 6 / 30（全库 12 / 776） | 独立解析问题，非「未知」成因 |

---

## 4. 规则证据（每类 ≥3 条真实样本 + `文件:行`）

### 4.1 A 类：`作废` → 已归入废止族（本次 58 条已离开「未知」）

**规则链（HEAD）**

| 规则 | 位置 | 行为 |
|---|---|---|
| `作废` 是合法枚举值，且本就属废止族 | `pilotstd/core/status.py` L42、L139-141、L145-147 | `VOIDED="作废"` ∈ `ABOLISHED_STATUSES` / `ABOLISHED_STATUSES_WITH_EXPIRED` |
| 「已废止」筛选 = 废止 + 被代替 + 作废 | `pilotstd/manager/standard_service.py` L29-30 | `IN ('废止','被代替','作废')` |
| 「未知」筛选 = NOT IN 上述四值 | 同文件 L31-40 | `NOT IN ('现行','废止','被代替','作废')` |
| 统计「已废止」计入作废 | 同文件 L89-91 | `s[废止]+s[被代替]+s[作废]` |
| 统计「未知」= 四值之外补集 | 同文件 L92-102 | 遍历 `by_status` 求和 |
| 首页卡片 `expired` 计入作废（同类扩散点） | `pilotstd/core/_file_index_query.py` L97-103 | `current / expired / pending / upcoming` |
| 首页 `/api/stats` 数据源 | `docker/api/stats.py` L20-23 | `mgr.file_index.get_status_stats()` |
| 状态页统计端点 | `docker/api/standards.py` L53-69 | 返回 `active / inactive / unknown` |
| 文档同批回写 | `docs/architecture/modules/manager.md` L371-383；`core.md` L888-897 | 官方口径「废止族 = 废止+被代替+作废」 |
| 回归测试 | `tests/test_standard_service.py` L135-154、L156-161；`tests/unit/core/test_file_index_query_snapshot.py` L156-167 | 锁定 174/30 与首页 expired 含作废 |

**真实样本（≥3，均物理位于 `过期作废/`，HEAD 下归类 = 已废止）**

| # | 标准号 | 名称 | file_index.status | HEAD 当前归类 | 判定依据（文件:行） |
|---:|---|---|---|---|---|
| 1 | API 685-2000 | CN 石油重化学和天然气工业用无密封式离心泵 | 作废 | **已废止（废止族）** | `standard_service.py` L29-30 `IN` 含作废；L89-91 统计 |
| 2 | GB 32284-2015 | 石油化工离心泵能效限定值及能效等级 | 作废 | **已废止** | 同上；文件路径 `/过期作废/` |
| 3 | GB 50202-2002 | 建筑地基基础施工质量验收规范 | 作废 | **已废止** | 同上；文件路径 `/过期作废/` |
| 4 | GB 50183-2004 | 石油天然气工程设计防火规范 | 作废 | **已废止** | 同上；文件路径 `/过期作废/` |
| 5 | HG 20203-2000 | 化工机器安装工程施工及验收通用规范 | 作废 | **已废止** | 同上；**唯一** validity 也判「作废」(chk=3) 的强证据 |

> 验证：修复后 `?status=voided` 仍单独返回 58 条（`standard_service.py` L41 精确匹配兜底），
> 且 `?status=unknown` 的 30 条中 `status_key` **不含 `voided`**（夹具实测）——作废未被吞并。

### 4.2 B 类：`即将实施` → 合法状态，但统计无独立桶

**规则链（HEAD）**

| 规则 | 位置 | 行为 |
|---|---|---|
| 合法枚举 `UPCOMING="即将实施"` | `pilotstd/core/status.py` L38；英文键映射 L66 | `status_key='upcoming'` 正常映射 |
| 统计响应只有 3 字段 | `docker/api/standards.py` L21-26 | `active / inactive / unknown`，无 upcoming |
| `unknown` 补集未排除 upcoming | `pilotstd/manager/standard_service.py` L92-102 | 20 条被算进「未知」 |
| 列表筛选可单独取 | `pilotstd/core/status.py` L127-130 → `standard_service.py` L41 | `?status=upcoming` → `status='即将实施'` 精确匹配 20 条 |
| 前端无第 4 卡/筛选 | `web/src/views/StandardsStatusView.vue` L63-70、L168-187；`web/src/utils/stdStatus.ts` L66-70 | 仅 3 项；`upcoming` 严重度已定义但未展示 |

**真实样本（≥3，均在常规目录，实施日期在未来）**

| # | 标准号 | 名称 | file_index.status | HEAD 当前归类 | 判定依据（文件:行） |
|---:|---|---|---|---|---|
| 1 | GB 15499-2025 | 生产安全事故伤害损失工作日判定 | 即将实施 | 未知桶；可 `?status=upcoming` 单筛 | validity 即将实施 + 公告即将实施（2027-01-01）**双源一致**；`status.py` L38 |
| 2 | GB 2970-2026 | 6 厚钢板超声检测方法 | 即将实施 | 未知桶 | validity 即将实施(chk=1)；`status.py` L38；`standard_service.py` L92-102 |
| 3 | GB 4053-2025 | 固定式金属梯及平台安全要求 第3部分-工业防护栏杆及平台 | 即将实施 | 未知桶 | 公告即将实施(2027-01-01)；validity 现行（跨源冲突，见 §6.3） |
| 4 | GB 18047-2026 | 车用压缩天然气 | 即将实施 | 未知桶 | 公告即将实施(2027-08-01)；validity 未知(chk=0) |

### 4.3 C 类：`未生效` → 枚举外脏值，语义 = 即将实施（读取侧未归一）

**规则链（HEAD）**

| 规则 | 位置 | 行为 |
|---|---|---|
| `Status` 九值枚举**无** `未生效` | `pilotstd/core/status.py` L37-45 | `ALL_STATUS_VALUES` 不含该值（L76） |
| 别名表只有 `废止→已废止` | 同文件 L79-81、L84-90 | `normalize_status('未生效')='未生效'`（原样） |
| `status_key` 回退 `unknown` | 同文件 L106-115 | 枚举外值 → `STATUS_EN_KEYS.get(..., 'unknown')` |
| 过滤入参无法识别 → 返回 `None` | 同文件 L118-130 | `resolve_status_filter('未生效')=None` → 调用方忽略过滤 |
| 忽略过滤的调用方 | `docker/api/standards.py` L88-91 | 无 `filters['status']` → 返回全表 |
| 写入端原样落库 | `pilotstd/manager/organize/organizer.py` L252 | `status=getattr(p,'effect_status','') or '现行'`，无归一/白名单 |
| 查询链状态映射无 `未生效` 条目 | `pilotstd/query/search_strategy.py` L214-235、L238-243 | `map_status('未生效')='未生效'`（夹具实测透传） |
| 现版本唯一生产归一化点 | `pilotstd/query/adapters/njbz365.py` L98 | `未生效 → Status.UPCOMING.value`（仅该站点适配器） |

**真实样本（≥3，公告口径 10/10 均 = 即将实施）**

| # | 标准号 | 名称 | file_index.status | HEAD 当前归类 | 判定依据（文件:行） |
|---:|---|---|---|---|---|
| 1 | GB 27900-2026 | 消防员呼救器 | 未生效 | 未知桶；`status_key=unknown` | `status.py` L37-45 无枚举、L106-115 回退；公告即将实施(2027-04-01) |
| 2 | GB/T 711-2026 | 优质碳素结构钢热轧钢板和钢带 | 未生效 | 未知桶 | validity 即将实施 + 公告即将实施(2027-02-01) |
| 3 | GB/T 4842-2026 | 纯氩、高纯氩和超纯氩 | 未生效 | 未知桶 | 公告即将实施(2027-02-01)；`status.py` L118-130 过滤失效 |
| 4 | GB/T 47914-2026 | 复合钢管超声检测方法 | 未生效 | 未知桶 | 公告即将实施(2027-02-01)；validity 未知(chk=1) |

### 4.4 D 类：真未知 = 0 的证据

- `status IS NULL` = 0；空名称/坏编号/空代号/缺年份 = 0；`file_path` 空 = 0（§2.3 SQL ②④）。
- 30 条标准号均符合「代号 + 顺序号-年代号」；名称正常中文；路径在标准库树内 → 无乱码、无解析失败。
- 结论：**不存在「源站无数据 / 无法解析 / 抓了非标准内容」导致的未知**（上一轮结论继续成立）。

---

## 5. 新发现 / 仍存在的口径漏洞（只报告，未改代码）

### 5.1 【高】`未生效` 过滤参数被静默忽略（`?status=未生效` → 返回全表 776）

- **现象（HEAD 夹具实测）**：`resolve_status_filter('未生效')` 返回 `None` → `docker/api/standards.py`
  L88-91 不设置过滤条件 → `get_list` 返回 **776 条**。生产部署态同样返回 776（附录 A）。
  用户点「筛选未生效」实际看到的是全库，**不是过滤结果，也不是空列表/400**。
- **连带的语义错位**：HEAD 下「未知」桶 30 条中，`status_key=upcoming` 有 20 条、
  `status_key=unknown` 仅 10 条。前端若用 `status_key` 归类，会与「未知 30」这张卡的数字错位。
- **涉及位置**：
  - `pilotstd/core/status.py` L79-81（别名表缺 `未生效`）、L106-115（回退 `unknown`）、L118-130（无法识别返回 `None`）
  - `docker/api/standards.py` L88-91（`None` 时静默忽略过滤）
- **建议修法（C2，不改库）**：
  1. `_STATUS_ALIASES` 增加 `'未生效': Status.UPCOMING.value`（10/10 公告口径佐证语义相同）；
  2. `pilotstd/query/search_strategy.py` `STATUS_MAP` 增加 `('未生效', Status.UPCOMING.value)`，防新数据再写脏值；
  3. `resolve_status_filter()` 对**非空但无法识别**的入参不再返回 `None`（API 层返回 400 或至少 WARN 日志），避免「筛选静默失效」；
  4. 补单测：`status_key('未生效')=='upcoming'`、`resolve_status_filter('未生效')=='即将实施'`、
     `?status=未生效` total=20（别名解析为 `即将实施`，与 `?status=upcoming` 一致），**不再返回 776**。

### 5.2 【中】`unknown` 仍是「补集」机制：任何新状态值都会被静默吞进「未知」

- **位置**：`pilotstd/manager/standard_service.py` L92-102（`st not in (现行,废止,被代替,作废)` 全部计入未知）；
  `_map_filter_status` L31-40 同口径。
- **风险**：A1 修好了**具体值** `作废`，但没有修**机制**。当前 `过期`/`待确认` 虽 0 行，
  但一旦写入端（`organizer.py` L252 原样落库）产生任何枚举外值，都会直接计入「未知」并使卡片虚高，
  且不会报错/告警。这正是本次 88 条「未知」的**结构性成因**，不排除以别的值复发。
- **建议修法**：`get_stats()` / `_map_filter_status()` 改为显式枚举（正面列出各桶），
  并对「枚举外值」记 WARN + 单测守卫（例如 `assert set(dist) <= ALL_STATUS_VALUES`）；
  或至少在 `get_stats()` 里发现补集含 `ALL_STATUS_VALUES` 之外的值时写一条 WARNING。

### 5.3 【低】API 契约常量与实际接受范围不一致（3 值 vs 9 值）

- `pilotstd/core/status.py` L160-164：`API_VALID_STATUSES` 仅 `(现行, 已废止, 未知)`；
- `docker/api/standards.py` L50：`_VALID_STATUSES = status_dict.API_VALID_STATUSES` **定义后未使用**（死常量）；
- 同文件 L74 docstring 只列 `active/withdrawn/unknown` 三个键，但实际 `resolve_status_filter`
  走 `ALL_STATUS_VALUES`（`status.py` L76、L130），`voided`/`upcoming`/`作废` 等**均被接受**。
- **建议**：契约常量与 docstring 更新为九值（或明确「3 个展示桶 + 6 个兼容值」），删除未使用的 `_VALID_STATUSES`。

### 5.4 【中】写入端未归一（C3 未做）：存量清洗后仍会再生

- `pilotstd/manager/organize/organizer.py` L252：`effect_status` **原样**写入 `file_index.status`，无白名单/归一；
- `pilotstd/query/search_strategy.py` L214-235 的 `STATUS_MAP` 没有 `未生效` 条目
  （`map_status('未生效')='未生效'` 已实测），`pilotstd/query/adapters/miit.py`/`cssn.py`/`ncha.py`
  等仍存在原样透传站点状态文本的写法。
- **建议**：按 `docs/plans/2026-11-24-p1-fix-decision.md` L42/C3 执行——写入前 `normalize_status()` +
  九值白名单（枚举外落 `unknown` 并 WARN）；存量 10 条 `未生效` 清洗需生产维护窗口（本任务禁止写库）。

### 5.5 【流程】A1 修复未部署：生产页面仍为旧数字

- 生产 `/api/health` `version=0e92e5d2`（2026-11-24 19:34 构建），落后 HEAD `bbc60b61` **45 个提交**；
  修复提交 `5c501fbb` 时间 2026-11-24 20:50，**晚于**该构建，故不在部署版本中。
- **建议**：部署含 `5c501fbb` 的构建后，按 HEAD 口径做一次只读复验：
  `stats == {active:572, inactive:174, unknown:30}`、`?status=withdrawn` total=174、
  `?status=unknown` total=30 且 `status_key` 不含 `voided`、`/api/stats.expired=174`、总数 776。

---

## 6. 结论：是否可判定「未知标准定性」任务闭合

### 6.1 定性层：**可以闭合**

- 上一轮结论「88 = 58 作废 + 20 即将实施 + 10 未生效，真未知 0」**仍然成立**；
- 58 条 `作废` 已按修复后的口径归入**已废止**（HEAD 实测 174），不再污染「未知」；
- 剩余 30 条全部有确定语义：`即将实施` 20（合法状态）+ `未生效` 10（即将实施同义词），
  **无一条属于解析失败 / 状态缺失 / 空字段 / 非标准内容**。
- 因此「未知标准定性」这一**分析任务**可判定闭合——「未知」不是数据缺失，而是
  「即将实施族 × 统计桶缺失 + 枚举未归一」的口径问题，与上一轮定性一致。

### 6.2 数值层：**不能闭合（未知仍为 30，非 0）**

要达成「未知 = 0」，还差三件事（对应 `docs/plans/2026-11-24-p1-fix-decision.md` L89-90）：

| 缺口 | 现状（HEAD） | 做完后（累计） | 工作量 / 风险 |
|---|---:|---:|---|
| （基线） | 未知 **30** = 即将实施 20（`status_key=upcoming`）+ 未生效 10（`status_key=unknown`） | — | — |
| C2 `未生效→即将实施` 归一（读取侧别名 + `STATUS_MAP` + **统计聚合复用归一** + 过滤不再静默） | `?status=未生效` → 776（静默） | 未知**卡片数字仍是 30**（`get_stats` 补集仍吞 `即将实施`），但 10 条 `status_key`→`upcoming`、`?status=未生效`→20，不再静默 | 2 文件 + 单测；**低**（不写库、无契约破坏） |
| B `即将实施` 统计桶（stats 加 `upcoming` 字段 + **unknown 补集排除 `即将实施`** + 前端第 4 卡/筛选 + 四件套） | 未知 30 | **未知 0 / upcoming 30**（前提：C2 已同批归一；若未做 C2 则未知 10 / upcoming 20） | 后端 2 文件 + 前端 4 文件 + 四件套；**中** |
| C3 写入端归一 + 存量 10 行清洗 | 会再生 | 不再生 | 写生产库需窗口（红线）；**中高** |
| 部署 A1 | 页面 88/116 | 页面 30/174 | 发布动作；**低** |

> 备注：C2+B 的顺序上，B 需要产品先确认「三分类 → 四分类」口径（`p1-fix-decision.md` L41 标注
> 「跨前后端 + 需产品确认三分类口径」）。若产品坚持只展示三卡，则 30 条将长期留在「未知」——
> 此时正确做法是**在文案/文档中明确「未知 = 即将实施族（尚未生效）」**，而不是继续修数据。

### 6.3 是否值得继续修：**值得，但按优先级分批**

1. **先部署 A1（低风险、零代码）**：上线后页面从 88/116 → 30/174，立刻消除 58 条误解；
2. **C2（P1，低风险）**：10 条 `未生效` 在读取侧归入即将实施，并修掉「筛选静默失效」这个更隐蔽的 API 缺陷；
   注意：C2 **单独不会改变「未知 30」这张卡的数字**（`get_stats` 仍是原始状态补集），它的价值是 `status_key`/过滤自洽；
3. **B（P1，中风险，需产品确认）**：给 `即将实施` 正式展示位，并让 `unknown` 补集排除 `即将实施`，
   `未知` 才能真正归零（30 → 0）；
4. **C3（P2，需窗口）**：写入端归一 + 存量清洗，防止再生；本轮复核已证明**存量仍在**（10 条）。

### 6.4 建议验收（部署后只读复验清单）

```
GET /api/standards/status/stats        → {"active":572,"inactive":174,"unknown":30}   # 部署 A1 后
GET /api/standards/status?status=withdrawn&page_size=1 → total=174
GET /api/standards/status?status=voided&page_size=1    → total=58
GET /api/standards/status?status=unknown&page_size=100 → total=30；items[].status_key 不含 "voided"
GET /api/stats                         → expired=174（首页卡片同口径）
总数守恒：572+174+30 = 776
C2 单独完成后：`?status=未生效` → 20（与 upcoming 一致）；「未知」卡片数字仍 30
C2+B 都完成后（终态）：stats unknown=0、upcoming=30；首页 /api/stats expired=174
```

---

## 7. 数据来源与可信度声明

| 证据 | 来源 | 可信度 | 局限 |
|---|---|---|---|
| 776 条状态分布、30 条明细、validity/公告交叉 | **生产只读 SQL**（`POST /query`，2026-11-25 19:09–19:25） | **生产实测（最高）** | 数据为采集时点快照；生产数据自 2026-11-24 起未变（分布逐值相同） |
| 174 / 30 等「HEAD 口径」数字 | **本地执行 HEAD 真实代码 + 生产 shape 夹具**（`%TEMP%`） | **代码口径实测** | 非生产 API 实测：生产未部署该代码，不能用生产接口验证 |
| 生产 API 响应（stats 88/116、`?status=未生效` 776） | 生产部署版本 `0e92e5d2`（旧代码） | 仅代表**部署态** | 不代表 HEAD 代码口径 |
| 本地 `data/pilotstd.db` | 本地文件 | 不可用 | `file_index` 0 行（开发库/已清空），**未采用** |
| 上一轮报告 | `docs/plans/2026-11-24-p1-unknown-standards.md` | 高 | 其数字为旧代码口径，本次已按 HEAD 重算 |

**只读承诺**：本任务未改代码/配置/其它文档，未 `commit`/`push`，未写生产库；临时脚本全部写
`%TEMP%`（`C:\Temp\p1r_*.py`），本报告是唯一写入仓库的文件。

**未做/无法验证**：未部署 HEAD、未跑前端四件套（无前端改动）、未执行 C2/B/C3；
因此「部署后生产接口是否返回 174/30」只能在部署后复验，本报告用「代码口径实测」代替。

---

## 附录 A：接口原始返回（生产部署态 `0e92e5d2`，只读）

```
GET /api/health   → 200 {"status":"ok","version":"0e92e5d2c94a22424120de756b3e4a0d255632e8","schema_version":76}
POST /api/login   → 200 登录成功（用户 mystdpilot，角色 admin）

GET /api/standards/status/stats
→ 200 {"active":572,"inactive":116,"unknown":88}          # 旧代码（修复未部署）

GET /api/standards/status?status=unknown&page=1&page_size=100
→ 200 total=88；items[].status_key ∈ {"voided","upcoming","unknown"}；status ∈ {"作废","即将实施","未生效"}
GET /api/standards/status?status=withdrawn&page=1&page_size=100 → total=116（废止+被代替）
GET /api/standards/status?status=voided&page=1&page_size=100    → total=58
GET /api/standards/status?status=upcoming&page=1&page_size=100  → total=20
GET /api/standards/status?status=未生效&page=1&page_size=100    → total=776（过滤被忽略，实证）

GET /api/stats → 200 {"current":572,"expired":116,"pending":0,"upcoming":20}   # 旧代码
```

### HEAD 代码口径（夹具实测，对应生产分布 572/95/58/21/20/10）

```
StandardService.get_stats()        → {"现行":572, "已废止":174, "未知":30}, total=776
get_list(withdrawn)                → 174
get_list(unknown)                  → 30（status_key: upcoming 20 / unknown 10，不含 voided）
get_list(voided)                   → 58
get_list(upcoming)                 → 20
get_list(未生效)                    → 776（resolve_status_filter=None，过滤被忽略 ← 漏洞）
FileIndexQuery.get_status_stats()  → {"current":572, "expired":174, "pending":0, "upcoming":20}
status_key('未生效') = 'unknown'；normalize_status('未生效') = '未生效'
map_status('未生效') = '未生效'（写入侧透传）
```

## 附录 B：只读自证

```
write_calls（_probe_common.HttpClient 记录的实际写方法调用）：
  POST /api/login
  POST /query × 17（每条均为单条 SELECT，发送前经 _assert_read_only_sql 校验）
无 INSERT / UPDATE / DELETE / DROP / ALTER 语句。
```

## 附录 C：自检清单

- [x] 复用上一轮口径规则（作废族 / 即将实施 / 未生效 / 真未知），未另起炉灶。
- [x] 当前数字真实取证：生产只读 SQL（数据层）+ HEAD 真实代码执行（计算层），非凭记忆。
- [x] 每类 ≥3 条真实样本（A 5 条 / B 4 条 / C 4 条），含标准号、名称、当前归类、`文件:行` 规则。
- [x] 「真未知」剩余清单全量 30 条 + 类别统计 + 原因分类（B 类 20 / C 类 10 / 真未知 0）。
- [x] 新口径漏洞均给出 `文件:行` 与建议修法，**未改代码**。
- [x] 报告结构：当前 vs 上一轮 / 真未知清单 / 规则证据 / 结论与剩余工作 / 数据来源与可信度。
- [x] 唯一写入文件：`docs/plans/2026-11-25-p1-unknown-refresh.md`；临时脚本在 `%TEMP%`。
