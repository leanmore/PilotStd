# P1-5 · 88 个「未知」标准定性摸底（2026-11-24）

> **结论先行**：88 条「未知」= **58 条「作废」+ 20 条「即将实施」+ 10 条「未生效」**，
> **0 条**属于「源站无数据 / 乱码 / 抓了非标准内容 / 解析失败」。
> 根本原因是**状态写入端未归一 + 统计/筛选端三分类口径缺条目**（不是采集失败）：
> 写入端把 Query 的 `effect_status` 原样落进 `file_index.status`（DB 里因此出现 6 个状态值，
> 其中 3 个落在三分类之外）；而「标准状态」页的统计/筛选只把 `废止 + 被代替` 算作已废止、且产品口径没有「即将实施」桶，
> 于是 `作废 / 即将实施 / 未生效` 三类被整体折叠进「未知」。
>
> 数据环境：生产 Docker API `http://192.168.1.18:9028`（只读；仅发 `GET` 与白名单
> `POST /api/login`、`POST /query`，全部 SQL 为单条 `SELECT`）。
> 采集时间：2026-11-24（Asia/Shanghai）。

---

## 1. 数据来源与方法

### 1.1 只读客户端与凭据

- 客户端：仓库现成只读层 `scripts/ops/_probe_common.py`（`WRITE_ALLOWLIST` 只放行登录与
  `POST /query`，且 `_assert_read_only_sql()` 在发送前校验单条 `SELECT/PRAGMA`，
  见该文件 L62-69、L158-175）。
- 凭据：`config/docker_creds.json`（按行正则读取，不整体 `json.loads`，
  `read_creds()` L145-155）。登录结果：用户 `mystdpilot`，角色 `admin`（实证：`LOGIN: (200, '登录成功（用户 mystdpilot，角色 admin）')`）。
- **只读自证**：本任务全部请求序列只有 `POST /api/login`、`POST /query`、`GET /api/standards/status*`；
  未执行任何 `INSERT/UPDATE/DELETE`。

### 1.2 已查阅的文档与代码（依据来源）

| 类型 | 路径 / 位置 | 用途 |
|---|---|---|
| 文档 | `docs/onboarding/04-data-model.md` L314-325（§六.1/§六.2） | 已知边界：`file_index` 与 `standard_validity` 身份不一致；`standard_validity` 不自动同步 Query 状态，归档只写“未知” |
| 文档 | `docs/onboarding/08-known-boundaries.md` L129-147（#4） | “`effect_status` 来自 Query；`/api/stats` 看 `file_index`，`/api/export/standards` 看 `standard_validity`，两边可能不一致” |
| 文档 | `docs/architecture/modules/manager.md` L113、L222 | 状态统计聚合代码清单；`/api/standards/status` JOIN 必须带年份（2026-11-03 修复） |
| 文档 | `docs/onboarding/17-validity-state-machine.md` L12-20 | L1/L2/L3 判定优先级（L1 只信否定证据） |
| 代码 | `pilotstd/manager/standard_service.py` L18-28、L30-60、L64-83、L104-115 | **统计与筛选口径的唯一定义处**（本报告主因定位） |
| 代码 | `docker/api/standards.py` L53-63、L72-103 | 两个只读端点：`GET /api/standards/status/stats`、`GET /api/standards/status` |
| 代码 | `pilotstd/core/status.py` L30-45、L84-115、L137-164 | 状态枚举 9 值、`status_key()` 回退 `unknown`、`ABOLISHED_STATUSES`（含 `作废`）、`API_VALID_STATUSES`（仅 3 值） |
| 代码 | `pilotstd/manager/organize/organizer.py` L222-232 | **写入端主路径**：`status=getattr(p, "effect_status", "") or 现行` 原样落库，无归一/白名单 |
| 代码 | `pilotstd/ui/core/handlers/archive_flow_engine.py` L36-48 | 桌面归档路径的状态映射（`作废→废止`），与 organizer 原样写入口径不一致 |
| 代码 | `pilotstd/query/search_strategy.py` L210-239 | `STATUS_MAP`：有 `作废→废止`、无 `未生效` 条目（`未生效` 会原样透传） |
| 代码 | `pilotstd/query/adapters/ahbz.py` L27-30 | 安徽站适配器 `W → Status.VOIDED.value（作废）`；`L116` 直接写入 `QueryResult.status` |
| 代码 | `pilotstd/query/adapters/njbz365.py` L96-100 | 站点 `未生效` 已被归一为 `即将实施`（现版本唯一生产点） |
| 代码 | `pilotstd/query/adapters/miit.py` L148、`cssn.py` L136、`ncha.py` L180 | 其余适配器存在**原样透传站点状态文本**的写法（同类风险面） |
| 代码 | `web/src/views/StandardsStatusView.vue` L63-70、L153-172、L237-241 | 前端只有 3 张卡 / 3 个筛选项；状态列直接显示 `data.status` 文本 |
| 代码 | `web/src/utils/stdStatus.ts` L23-41 | 前端状态键分级（`voided` 已在废止族） |
| 对照 | `tests/test_standard_service.py` L23-49、L99-129 | 现有单测锁定旧口径（本报告 §5 修复方案需同步） |

### 1.3 已执行的实际 SQL（全部只读，逐条跑过）

```sql
-- ① 总体分布（页面三卡的真实来源；与 StandardService.get_stats 等价的原始分组）
SELECT status, COUNT(*) AS c FROM file_index WHERE status IS NOT NULL GROUP BY status ORDER BY c DESC;

-- ② 表规模与空值自证
SELECT COUNT(*) AS c FROM file_index;                                  -- 776
SELECT COUNT(*) AS c FROM file_index WHERE status IS NULL;             -- 0

-- ③ 88 条全量明细（导出清单的取数语句，核心）
SELECT f.id, (f.logical_code || ' ' || f.number ||
         CASE WHEN f.year > 0 THEN '-' || f.year ELSE '' END) AS num,
       f.logical_code, f.number, f.year, f.part, f.status, f.std_name, f.raw_number,
       f.file_path, f.scanned_at,
       v.status AS v_status, v.last_status AS v_last_status, v.last_checked_at, v.check_count,
       (SELECT p.source_site   FROM pending_lookup p WHERE p.standard_number = <num> ORDER BY p.id DESC LIMIT 1) AS pl_site,
       (SELECT p.effect_status FROM pending_lookup p WHERE p.standard_number = <num> ORDER BY p.id DESC LIMIT 1) AS pl_effect,
       (SELECT p.reason        FROM pending_lookup p WHERE p.standard_number = <num> ORDER BY p.id DESC LIMIT 1) AS pl_reason,
       (SELECT a.source_site   FROM announcement_record a WHERE a.standard_number = <num> ORDER BY a.id DESC LIMIT 1) AS ar_site,
       (SELECT json_extract(m.result_json,'$.status') FROM announcement_match m WHERE m.standard_number = <num> ORDER BY m.id DESC LIMIT 1) AS am_status,
       (SELECT m.source_site   FROM announcement_match m WHERE m.standard_number = <num> ORDER BY m.id DESC LIMIT 1) AS am_site,
       (SELECT json_extract(m.result_json,'$.implementation_date') FROM announcement_match m WHERE m.standard_number = <num> ORDER BY m.id DESC LIMIT 1) AS am_impl_date
FROM file_index f
LEFT JOIN standard_validity v
  ON (f.logical_code || ' ' || f.number ||
      CASE WHEN f.year > 0 THEN '-' || f.year ELSE '' END) = v.standard_number
WHERE f.status NOT IN ('现行','废止','被代替')
ORDER BY f.status, f.logical_code, f.number, f.part LIMIT 1000;
-- 返回 88 行（与页面一致）

-- ④ 数据质量自证（88 条是否有空名称/坏编号/缺年份/在过期作废目录）
SELECT status, COUNT(*) AS c,
       SUM(CASE WHEN TRIM(std_name) = '' THEN 1 ELSE 0 END) AS empty_name,
       SUM(CASE WHEN number <= 0 THEN 1 ELSE 0 END)        AS bad_number,
       SUM(CASE WHEN TRIM(logical_code) = '' THEN 1 ELSE 0 END) AS empty_code,
       SUM(CASE WHEN year <= 0 THEN 1 ELSE 0 END)          AS no_year,
       SUM(CASE WHEN file_path LIKE '%过期作废%' THEN 1 ELSE 0 END) AS in_expire_dir
FROM file_index WHERE status NOT IN ('现行','废止','被代替') GROUP BY status;

-- ⑤ 与 standard_validity 的对照（88 条）
SELECT v.status AS v_status, COUNT(*) AS c
FROM file_index f LEFT JOIN standard_validity v
  ON (f.logical_code || ' ' || f.number || CASE WHEN f.year > 0 THEN '-' || f.year ELSE '' END) = v.standard_number
WHERE f.status NOT IN ('现行','废止','被代替') GROUP BY v.status ORDER BY c DESC;
```

> 可读性说明：SQL ③ 中重复出现的连接键写作 `<num>`（实际执行时内联为
> `(f.logical_code || ' ' || f.number || CASE WHEN f.year > 0 THEN '-' || f.year ELSE '' END)`）；
> 该语句在 `POST /query` 上一次提交执行，返回 88 行。

接口调用（同样只读）：

```
GET /api/standards/status/stats
GET /api/standards/status?status=unknown&page=1&page_size=100   → total=88, items=88
GET /api/standards/status?status=active&page=1&page_size=1      → total=572
GET /api/standards/status?status=withdrawn&page=1&page_size=1   → total=116
GET /api/standards/status?status=voided&page=1&page_size=1      → total=58   （说明 58 条可单独筛出）
GET /api/standards/status?status=upcoming&page=1&page_size=1    → total=20
GET /api/standards/status?status=未生效&page=1&page_size=1       → total=776  （过滤参数无法解析 → 被忽略）
```

### 1.4 口径推导（三卡数字是怎么来的）

| 口径 | 代码位置 | 实际行为 |
|---|---|---|
| `active`（572） | `standard_service.py` L22-23 / L71-72 | `status = '现行'` |
| `inactive`（116） | L24-25 / L73 | **只**统计 `废止(95) + 被代替(21)`；**不含 `作废`** |
| `unknown`（88） | L26-27 / L74-78 | `status NOT IN ('现行','废止','被代替')` → 把 `作废/即将实施/未生效` 全部吞入 |
| `/api/standards/status?status=unknown` | `_map_filter_status()` L26-27 | 与统计同一条 `NOT IN (3 值)`，所以列表 total=88 与卡片**自洽但不正确** |
| `status_key` | `core/status.py` L106-115 | `作废→voided`、`即将实施→upcoming`、**`未生效` 不在枚举 → 回退 `unknown`** |
| 前端 | `StandardsStatusView.vue` L63-70、L166-172 | 只有 3 个筛选项、3 张卡；状态列直接显示原始中文（`作废/即将实施/未生效`） |

**关键证据（接口层）**：`/api/standards/status?status=unknown` 返回的 88 条，`status_key`
集合是 `{'voided', 'upcoming', 'unknown'}`（不是单一 `unknown`）——说明「未知」桶里混的是
三个**有名字的**状态，而不是“查不到状态”。

---

## 2. 88 条全量清单

> **列说明**
> - `file_index.status`：**状态判定的唯一输入字段**（`/api/standards/status/stats` 与列表都只读它）。
> - `status_key`：API 返回的稳定英文键（`docker/api/standards.py` L97 现算）。
> - 目录：文件是否位于 `过期作废/` 子目录（归档时 `FileMover` 按 `effect_status` 决定，
>   `pilotstd/organizer/mover.py` L37-44）。
> - 来源线索：`file_index` **没有来源站点字段**，只能从 4 张表反查（详见 §4.3）：
>   `announcement_match / announcement_record`（公告来源），`pending_lookup`（查询站点）。
>   `—（四表均无来源字段）` = 抓取链路没有留下任何可反查的来源记录（可观测性缺口，不是数据错误）。
> - `validity.status(chk)`：`standard_validity` 行 + `check_count`；`—（无 validity 行）` 表示该标准号在有效性表无行。
> - 注：`GB/T 20671` 出现两行（part=4 / part=11）但「标准号」列相同 —— 因为接口的
>   `standard_number` 不含 `year/part`（见 §7.1），这是**展示层**缺陷，不是重复记录（DB 内 2 条是不同分部分）。

| # | id | 标准号 | 名称 | file_index.status | status_key | 目录 | 来源线索（字段级） | validity.status(chk) |
|---:|---:|---|---|---|---|---|---|---|
| 1 | 3191 | API 685-2000 | CN 石油重化学和天然气工业用无密封式离心泵 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 2 | 3057 | GB 32284-2015 | 石油化工离心泵能效限定值及能效等级 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=1） |
| 3 | 3581 | GB 50050-2007 | 工业循环冷却水处理设计规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 4 | 3454 | GB 50183-2004 | 石油天然气工程设计防火规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 5 | 3110 | GB 50202-2002 | 建筑地基基础施工质量验收规范 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=1） |
| 6 | 3585 | GB 50205-2001 | 钢结构结构施工质量验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 7 | 3455 | GB 50231-1998 | 机械设备安装工程施工及验收通用规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 8 | 3586 | GB 50235-1997 | 工业金属管道工程施工及验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 9 | 3587 | GB 50236-1998 | 现场设备、工业管道焊接工程施工及验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 10 | 3112 | GB 50726-2011 | 工业设备与管道防腐蚀工程施工规范 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=1） |
| 11 | 3593 | GB 50727-2011 | 工业设备与管道防腐蚀工程施工质量验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 12 | 3613 | GB/T 151-2014 | 热交换器 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 13 | 3661 | GB/T 702-2017 | 热轧钢棒尺寸、外形、重量及允许偏差 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 14 | 3651 | GB/T 5782-2016 | 六角头螺栓 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=1） |
| 15 | 3659 | GB/T 6728-2017 | 结构用冷弯空心型钢 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 16 | 3682 | GB/T 8165-2008 | 不锈钢复合钢板和钢带 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 17 | 3684 | GB/T 8174-2008 | 设备及管道绝热效果的测试与评价 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 18 | 3686 | GB/T 8175-2008 | 设备及管道绝热设计导则 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 19 | 3472 | GB/T 12221-2005 | 金属阀门结构长度 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 20 | 3481 | GB/T 12235-2007 | 石油、石化及相关工业用钢制截止阀和升降式止回阀 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=1） |
| 21 | 3485 | GB/T 12236-2008 | 石油、化工及相关工业用的钢制旋启式止回阀 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 22 | 3125 | GB/T 12245-2006 | 减压阀 性能试验方法 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=1） |
| 23 | 3610 | GB/T 12716-1991 | 60°圆锥管螺纹 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 24 | 3027 | GB/T 13401-2017 | 钢制对焊管件 技术规范 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 25 | 3061 | GB/T 14976-2012 | 流体输送用不锈钢无缝钢管 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 26 | 3053 | GB/T 17897-2016 | 金属和合金的腐蚀 不锈钢三氯化铁点腐蚀试验方法 | 作废 | `voided` | 过期作废 | announcement_match:announcement_gb（公告口径 现行） | 未知（chk=2） |
| 27 | 3534 | HG 20202-2014 | 脱脂工程施工及验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 28 | 3535 | HG 20203-2000 | 化工机器安装工程施工及验收通用规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 作废（chk=3） |
| 29 | 3537 | HG 20234-1993 | 化工建设项目进口设备、材料检验大纲 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 30 | 3538 | HG 20236-1993 | 化工设备安装工程质量检验评定标准 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 31 | 3335 | HG 20592-1997 | 钢制管法兰、垫片、紧固件 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 32 | 3541 | HG 20660-2000 | 压力容器中化学介质毒性危害和爆炸危险程度分类 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 33 | 3546 | HG/T 20675-1990 | 化工企业静电接地设计规程 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=0） |
| 34 | 3334 | HG/T 20679-1990 | 化工管道、设备外防腐设计规定 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 35 | 3523 | JB 4733-1996 | 压力容器用爆炸不锈钢复合钢板 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 36 | 3529 | JB/T 4700-2000 | 压力容器法兰 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 37 | 3530 | JB/T 4703-2000 | 长颈对焊法兰 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 38 | 3531 | JB/T 4710-2005 | 钢制塔式容器 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 39 | 3322 | JB/T 4711-2003 | 压力容器涂覆与运输包装 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 40 | 3323 | JB/T 4736-2002 | 补强圈 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 41 | 3205 | JGJ 61-2003 | (J258-2003) 网壳结构技术规程 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 42 | 3238 | NB/T 47008-2010 | 承压设备用碳素钢和合金钢锻件 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 43 | 3221 | NB/T 47010-2010 | 承压设备用不锈钢和耐热钢锻件 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 44 | 3228 | NB/T 47015-2011 | 压力容器焊接规程 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=3） |
| 45 | 3231 | NB/T 47016-2011 | 承压设备产品焊接试件的力学性能检验 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 46 | 3246 | SH 3137-2013 | 石油化工钢结构防火保护技术规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 47 | 3247 | SH 3501-2011 | 石油化工有毒、可燃介质钢制管道工程施工及验收规范 | 作废 | `voided` | 过期作废 | pending_lookup:csres | 未知（chk=2） |
| 48 | 3274 | SH/T 3405-2012 | 石油化工钢管尺寸系列 | 作废 | `voided` | 过期作废 | pending_lookup:csres | 未知（chk=1） |
| 49 | 3279 | SH/T 3408-2012 | 石油化工钢制对焊管件 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 50 | 3286 | SH/T 3507-2011 | 石油化工钢结构工程施工质量验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 51 | 3288 | SH/T 3510-2011 | 石油化工设备溷凝土基础工程施工质量验收规范 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=2） |
| 52 | 2933 | SH/T 3513-2009 | 石油化工铝制料仓施工质量验收规范 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=2） |
| 53 | 2935 | SH/T 3515-2003 | 大型设备吊装工程施工工艺标准 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=1） |
| 54 | 2943 | SH/T 3548-2011 | 石油化工涂料防腐蚀工程施工质量验收规范 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=1） |
| 55 | 2947 | SH/T 3903-2004 | 石油化工建设工程项目监理规范 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=3） |
| 56 | 3711 | SH/T 3904-2014 | 石油化工建设工程项目竣工验收规定 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 57 | 2949 | SHJ 522-1991 | 石油化工绝热工程施工工艺标准 | 作废 | `voided` | 过期作废 | —（四表均无来源字段） | 未知（chk=2） |
| 58 | 3197 | YB/T 3301-2005 | 焊接H型钢 | 作废 | `voided` | 过期作废 | —（pending_lookup 有行但 source_site 空） | 未知（chk=3） |
| 59 | 3562 | GB 2970-2026 | 6 厚钢板超声检测方法 | 即将实施 | `upcoming` | 常规 | —（pending_lookup 有行但 source_site 空） | 未知（chk=1） |
| 60 | 3438 | GB 4053-2025 | 固定式金属梯及平台安全要求 第3部分-工业防护栏杆及平台 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 现行（chk=2） |
| 61 | 3596 | GB 5613-2026 | 6 铸钢牌号表示方法 | 即将实施 | `upcoming` | 常规 | —（pending_lookup 有行但 source_site 空） | 即将实施（chk=1） |
| 62 | 3600 | GB 7607-2026 | 6 柴油机油换油指标 | 即将实施 | `upcoming` | 常规 | —（pending_lookup 有行但 source_site 空） | 即将实施（chk=1） |
| 63 | 3551 | GB 13237-2026 | 6 优质碳素结构钢冷轧钢板及钢带 | 即将实施 | `upcoming` | 常规 | —（pending_lookup 有行但 source_site 空） | 即将实施（chk=1） |
| 64 | 3017 | GB 15499-2025 | 生产安全事故伤害损失工作日判定 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 65 | 3553 | GB 18047-2026 | 车用压缩天然气 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=0） |
| 66 | 3573 | GB 38305-2025 | 头部防护 救援头盔 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 现行（chk=1） |
| 67 | 3618 | GB/T 2520-2026 | 冷轧电镀锡钢板及钢带 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 68 | 3609 | GB/T 12337-2026 | 钢制球形储罐 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 69 | 3611 | GB/T 14180-2026 | 缠绕式垫片试验方法 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 现行（chk=1） |
| 70 | 3612 | GB/T 14983-2026 | 耐火材料 抗碱性试验方法 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 现行（chk=1） |
| 71 | 3703 | GB/T 20671-2026 | 26 非金属垫片材料分类体系及试验方法 第4部分：垫片材料密封性试验方法 | 即将实施 | `upcoming` | 常规 | —（四表均无来源字段） | 即将实施（chk=1） |
| 72 | 3616 | GB/T 20671-2026 | 26 非金属垫片材料分类体系及试验方法 第11部分：合成聚合材料抗霉性测定方法 | 即将实施 | `upcoming` | 常规 | —（四表均无来源字段） | 即将实施（chk=1） |
| 73 | 3619 | GB/T 30825-2026 | 热处理温度测量 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 现行（chk=1） |
| 74 | 3632 | GB/T 47881-2026 | 稀土系储氢合金 吸放氢反应热力学性能测试方法 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=0） |
| 75 | 3634 | GB/T 47921-2026 | 钢制输氢管道氢脆敏感性测试和评估方法 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 76 | 3635 | GB/T 47995-2026 | 变形高温合金 焊丝 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 77 | 3636 | GB/T 48191-2026 | 环氧乙烷反应器 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 78 | 3637 | GB/T 48307-2026 | 锂离子动力电池产品缺陷风险防范 生产管理要求 | 即将实施 | `upcoming` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=0） |
| 79 | 3031 | GB 27900-2026 | 消防员呼救器 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=2） |
| 80 | 3667 | GB/T 711-2026 | 优质碳素结构钢热轧钢板和钢带 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 81 | 3638 | GB/T 4842-2026 | 纯氩、高纯氩和超纯氩 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=0） |
| 82 | 3658 | GB/T 6396-2026 | 复合钢板 力学及工艺性能试验方法 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 83 | 3491 | GB/T 8028-2026 | 汽油机油换油指标 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=0） |
| 84 | 3498 | GB/T 16923-2026 | 钢件的正火与退火 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 85 | 3494 | GB/T 47832-2026 | 电动机综合保护装置通用技术条件 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=1） |
| 86 | 3509 | GB/T 47877-2026 | 液氢储运用不锈钢无缝钢管 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 87 | 3492 | GB/T 47880-2026 | 稀土系储氢合金 吸放氢循环稳定性测试方法 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 即将实施（chk=1） |
| 88 | 3503 | GB/T 47914-2026 | 复合钢管超声检测方法 | 未生效 | `unknown` | 常规 | announcement_match:announcement_gb（公告口径 即将实施） | 未知（chk=1） |

---

## 3. 抽样比对结果（15 条，分层抽样）

抽样规则：按 `file_index.status` × 「来源线索有无」× 「validity 一致/冲突」× 「目录/分部分/名称异常」
分层，覆盖 A/B/C 三类与全部关键边界。

| # | 标准号 | 状态 | 类 | 抽中理由 | 逐条结论与字段证据 |
|---:|---|---|---|---|---|
| 1 | API 685-2000 | 作废 | A | 无公告匹配、pending 有行；API 系列标准，较老（2000） | 路径:`/过期作废`<br>validity:`未知`(chk=2)<br>公告:`无匹配`<br>pending:`待确认`/`pending` |
| 2 | GB 32284-2015 | 作废 | A | 有公告匹配但公告口径=现行（跨源冲突） | 路径:`/过期作废`<br>validity:`未知`(chk=1)<br>公告:`现行`(impl=2017-01-01)<br>pending:`无行`/`—` |
| 3 | HG 20203-2000 | 作废 | A | 唯一一条 validity 也判「作废」（checker 侧强证据） | 路径:`/过期作废`<br>validity:`作废`(chk=3)<br>公告:`无匹配`<br>pending:`待确认`/`file_moved_quarantine` |
| 4 | HG/T 20675-1990 | 作废 | A | check_count=0；pending.reason=file_moved_quarantine | 路径:`/过期作废`<br>validity:`未知`(chk=0)<br>公告:`无匹配`<br>pending:`待确认`/`file_moved_quarantine` |
| 5 | YB/T 3301-2005 | 作废 | A | check_count=3、validity=未知；pending 待确认 | 路径:`/过期作废`<br>validity:`未知`(chk=3)<br>公告:`无匹配`<br>pending:`待确认`/`pending` |
| 6 | GB 15499-2025 | 即将实施 | B | validity=即将实施 且公告口径=即将实施（双源一致） | 路径:`/常规`<br>validity:`即将实施`(chk=1)<br>公告:`即将实施`(impl=2027-01-01)<br>pending:`无行`/`—` |
| 7 | GB 4053-2025 | 即将实施 | B | validity=现行 与公告口径=即将实施冲突 | 路径:`/常规`<br>validity:`现行`(chk=2)<br>公告:`即将实施`(impl=2027-01-01)<br>pending:`待确认`/`pending` |
| 8 | GB 5613-2026 | 即将实施 | B | pending.reason=file_moved_quarantine，validity=即将实施 | 路径:`/常规`<br>validity:`即将实施`(chk=1)<br>公告:`无匹配`<br>pending:`待确认`/`file_moved_quarantine` |
| 9 | GB/T 20671-2026 | 即将实施 | B | part=4 分部分标准；名称含解析残留「26」前缀；无公告匹配 | 路径:`/常规`<br>validity:`即将实施`(chk=1)<br>公告:`无匹配`<br>pending:`无行`/`—` |
| 10 | GB/T 14983-2026 | 即将实施 | B | validity=现行 与公告口径=即将实施冲突 | 路径:`/常规`<br>validity:`现行`(chk=1)<br>公告:`即将实施`(impl=2027-02-01)<br>pending:`待确认`/`file_moved_quarantine` |
| 11 | GB 27900-2026 | 未生效 | C | validity=未知；公告口径=即将实施（同义证据） | 路径:`/常规`<br>validity:`未知`(chk=2)<br>公告:`即将实施`(impl=2027-04-01)<br>pending:`无行`/`—` |
| 12 | GB/T 711-2026 | 未生效 | C | validity=即将实施，公告口径=即将实施 | 路径:`/常规`<br>validity:`即将实施`(chk=1)<br>公告:`即将实施`(impl=2027-02-01)<br>pending:`待确认`/`file_moved_quarantine` |
| 13 | GB/T 4842-2026 | 未生效 | C | validity=无行/未查（check_count=0）；公告口径=即将实施 | 路径:`/常规`<br>validity:`未知`(chk=0)<br>公告:`即将实施`(impl=2027-02-01)<br>pending:`待确认`/`file_moved_quarantine` |
| 14 | GB/T 16923-2026 | 未生效 | C | validity=即将实施，公告口径=即将实施 | 路径:`/常规`<br>validity:`即将实施`(chk=1)<br>公告:`即将实施`(impl=2027-02-01)<br>pending:`待确认`/`pending` |
| 15 | GB/T 47914-2026 | 未生效 | C | validity=未知；公告口径=即将实施 | 路径:`/常规`<br>validity:`未知`(chk=1)<br>公告:`即将实施`(impl=2027-02-01)<br>pending:`待确认`/`pending` |

**抽样结论**：
1. 15 条中 **15 条都是真实标准**（标准号可解析、名称有效、文件在标准库目录内），
   **0 条**属于源站无数据、乱码或非标准公告。
2. `作废` 5 条全部物理位于 `过期作废/`，且 `validity` 多为「未知」——与
   `docs/onboarding/04-data-model.md` §六.2 已知边界一致（“文件在过期作废不代表 validity 是废止”），
   不影响它们属于**废止族**这一事实。
3. `即将实施` 5 条中 3 条 `validity` 与公告口径一致（即将实施），2 条冲突（validity=现行）；
   但所有文件都在**常规目录**，且实施日期在未来 —— 属于“已归档但尚未生效”，不是“未知”。
4. `未生效` 5 条的公告口径**全部=即将实施** → `未生效` 只是 `即将实施` 的另一种写法/脏值，
   同一语义被 `Status` 枚举漏收，`status_key` 才会回退 `unknown`。
5. 抽样没有发现“89/88 偶发单条异常”的迹象：88 条规则高度一致（58 全部在过期作废目录，
   30 全部在常规目录）。

---

## 4. 定性分布（带数量）

### 4.1 主分类

| 类 | 定性 | 条数 | 占比 | 判定依据（证据） |
|---|---|---:|---:|---|
| **A. 映射/聚合口径缺条目**（`作废`） | 系统把合法的废止族状态折叠进「未知」 | **58** | 65.9% | ① `file_index.status='作废'`（SQL ③）；② `作废` ∈ `Status` 枚举（`core/status.py` L42）且 ∈ `ABOLISHED_STATUSES`（L137-141），前端也把 `voided` 当废止族（`stdStatus.ts` L36-41）；③ 但 `get_stats`/`_map_filter_status` 只认 `废止+被代替`（`standard_service.py` L24-27、L73）；④ 58/58 物理位于 `过期作废/`（SQL ④ 的 `in_expire_dir=58`）；⑤ `?status=voided` 可单独筛出 58 条 → 数据本身不缺，是口径漏算 |
| **B. 统计桶缺失**（`即将实施`） | 合法枚举值，但三分类产品口径没有「即将实施」桶 | **20** | 22.7% | ① `Status.UPCOMING='即将实施'`（`core/status.py` L38）；② `status_key=upcoming` 正常映射（API items 实证）；③ 只能被 `NOT IN(3值)` 的 unknown 桶收走；④ 20/20 在常规目录、实施日期均在未来（公告 `am_impl_date` 2027-01-01/2027-02-01/2027-04-01/2027-08-01）；⑤ `?status=upcoming` total=20 |
| **C. 状态字典缺枚举 + 历史脏值**（`未生效`） | 语义=即将实施，但值不在 `Status` 9 值内 | **10** | 11.4% | ① `file_index.status='未生效'`；② `Status` 枚举无此值 → `status_key()` 回退 `unknown`（`core/status.py` L106-115）；③ 现版本 `pilotstd/` 中 `未生效` 仅出现在 `njbz365.py` L96-100（已归一为`即将实施`）与 `_njbz365_session_manager.py` L158（请求参数枚举，非写入值）→ 写库值只能是历史/外部传入；④ 10/10 公告口径=即将实施（`am_status`）；⑤ `?status=未生效` 无法解析 → 返回全表 776（实证） |
| D. 源站无数据 / 字段为空 | 不存在 | **0** | 0% | SQL ④：88 条 `empty_name=0`、`bad_number=0`、`empty_code=0`、`no_year=0` |
| E. 乱码 / 非标准内容 | 不存在 | **0** | 0% | 88 条标准号均符合 `代号 + 顺序号 + 年代号`；名称为正常中文；无批量乱码特征（仅 7 条名称残留数字前缀“6/26”，为文件名解析尾巴，见 §7.3） |
| F. 解析失败 | 不存在 | **0** | 0% | `file_index.status` 无 NULL（SQL ②：0 行）；88 条均可 JOIN `standard_validity`（88/88 有行）且能按 `logical_code+number+year` 定位 |

**按任务包预设分类归并**（便于对账）：

| 预设类 | 对账结果 | 说明 |
|---|---:|---|
| 系统映射字典缺条目 | **68** | 58 = `作废` 未进聚合口径；10 = `未生效` 不在 `Status` 枚举（含读取侧回退） |
| 统计/产品口径缺桶 | **20** | `即将实施` 合法但三分类无该桶（任务包未预设，归入“口径缺失”而非数据问题） |
| 源站字段为空 | **0** | 88 条名称/编号/年份全非空 |
| 非标准公告 | **0** | 88 条均为真实标准文件，公告侧可匹配 37 条 |
| 解析失败 | **0** | 无 NULL 状态、无坏编号、无空名称 |
| 其他（待核） | 0 | — |

### 4.2 交叉统计（说明这 88 条“不是脏数据”）

| 维度 | 结果 | 来源 |
|---|---|---|
| 88 条在 `file_index` 总盘中的占比 | 88 / 776 = 11.3% | SQL ② |
| 88 条目录分布 | 过期作废 58（全部是 `作废`）/ 常规 30（全部是 `即将实施+未生效`） | SQL ④ |
| 名称 / 编号 / 年份完整性 | 空名称 0、坏编号 0、空代号 0、缺年份 0 | SQL ④ |
| `standard_validity.status` 对照 | `未知` 66、`即将实施` 16、`现行` 5、`作废` 1 | SQL ⑤ |
| `pending_lookup` 记录 | 72 条有行（其中 `effect_status='待确认'` 70 条）；`source_site` 非空仅 2 条（`csres`） | SQL ③ |
| `announcement_match` 匹配 | 39 条；作废→公告口径「现行」15 条（**跨源冲突**）、即将实施→即将实施 14、未生效→即将实施 10 | SQL ③ + §3 抽样 |
| 写入时间 `scanned_at` | 全部集中在 2026-11-13 22:04 ~ 2026-11-17 19:58 | SQL ③ |
| 来源可反查性 | **47 / 88 条四表均无来源站点字段** | SQL ③ |

### 4.3 三条“不是原因”的排除证据

1. **不是 `standard_validity` 未同步**：状态页 `get_stats` 只读 `file_index`（`standard_service.py`
   L69），`standard_validity` 的 66 条「未知」不会进入 88 的口径；且 08-known-boundaries #4
   已登记“归档只写未知、不读 validity”是**已知设计边界**。若有影响，只可能影响“废止与否”的
   判断质量（属 §4.2 的跨源冲突议题），不构成本次「未知」的成因。
2. **不是源站无数据/乱码**：SQL ④ 四项完整性全 0；88 条的标准号/名称/年份均可解析、可 JOIN；
   抽样 15/15 是真实标准。
3. **不是抓了非标准内容**：88 条全部在标准库目录树内、文件名符合
   `代号 顺序号-年代号 名称.pdf` 规范；公告侧 `announcement_record` 也能匹配 37 条（SQL ③）。

---

## 5. 下一步修复方案（分类 → 动作 → 风险）

**目标终态**（同一张 `file_index` 总盘 776 条，解决后四分类之和仍为 776）：

| 时点 | 现行 | 已废止 | 即将实施 | 未知 | 合计 |
|---|---:|---:|---:|---:|---:|
| 现状（页面实测） | 572 | 116 | —（无桶） | 88 | 776 |
| 完成 A1（口径补齐 `作废`） | 572 | **174** | —（无桶） | **30** | 776 |
| 完成 A1 + C2（`未生效` 读取侧别名） | 572 | 174 | **30** | **0** | 776 |

### 5.1 动作清单（按优先级）

| 优先级 | 类 | 动作 | 改动范围（文件:行） | 影响面 | 风险 | 验收 |
|---|---|---|---|---|---|---|
| **P0（建议立即）** | A | **补齐废止族聚合口径**：① `get_stats` 的「已废止」加 `Status.VOIDED.value`；② `_map_filter_status(已废止)` 的 `IN` 加 `作废`；③ `_map_filter_status(未知)` 的 `NOT IN` 加 `作废` | `pilotstd/manager/standard_service.py` L18-28、L64-83（约 6 行）+ `tests/test_standard_service.py` L32-49、L92-96、L99-129（同步旧断言，约 10 行） | `GET /api/standards/status/stats`（inactive 116→174、unknown 88→30）与 `?status=withdrawn`（116→174）、`?status=unknown`（88→30） | **低**：无 DB/Schema/API 契约变更；不写生产库；纯读取口径修正。唯一“风险”是**数字会变**（已废止 +58、未知 −58），需在发布说明标注“口径修正，非新增废止数据” | `pytest tests/test_standard_service.py -q`；生产只读验收：stats 返回 `active=572, inactive=174, unknown=30`；`?status=unknown` total=30 且其 `status_key` **不含** `voided`；`?status=withdrawn` total=174 |
| P1 | C | **`未生效` 读取侧别名（零写库）**：`normalize_status()` 增加 `未生效→即将实施` 别名；`status_key()`/统计聚合复用该归一；`query/search_strategy.py::STATUS_MAP` 增 `('未生效', Status.UPCOMING.value)` 防新数据再写脏值 | `pilotstd/core/status.py` L79-91、L94-115 + `pilotstd/query/search_strategy.py` L210-239 + 单测（`tests/unit/core/test_status.py` 系） | 读取侧 10 条归入「即将实施」；查询链新数据不再产生 `未生效` | **中低**：`normalize_status` 是共享函数（`status_key`、过滤解析），需回归 `/api/query/results`、`/api/pending/requery` 的 `status_key`；不写库 | `status_key('未生效')=='upcoming'` 单测；生产只读：unknown 桶不再含 `未生效` |
| P1 | B | **新增「即将实施」桶**：stats 响应加 `upcoming` 字段（**纯新增字段，向后兼容**）；前端加第 4 张卡/筛选项 + `stdStatus.ts` 已有 `upcoming` 分级 | `docker/api/standards.py` L21-26、L53-63（+1 字段）；`web/src/api/standards.ts` L1-64 类型；`web/src/views/StandardsStatusView.vue` L63-70、L153-172；契约测试 `tests/unit/core/test_status_contract.py`（新增用例） | 前端展示层 + 统计接口新增字段；`unknown` 在完成 A1+C2 后归 0 | **中**：跨前后端；web 必须跑四件套（type-check/lint/test/build）；stats 响应新增字段属向后兼容，老前端不受影响 | 四件套全绿；契约测试断言 `upcoming` 存在且=30；页面 4 卡数字与 SQL 一致 |
| P2（治本） | A/C | **写入端归一 + 白名单**：`organizer.py` 落库前对 `effect_status` 做 `normalize_status()`，只允许 9 个枚举值（未知值落 `unknown` 并 WARN 留痕）；`ahbz.py` 的 `W→作废` 与 `STATUS_MAP`（`作废→废止`）口径统一（二选一：统一成 `废止` 或保留 `作废` 由 A 聚合兜底，**建议保留 `作废` 以保真站点语义**） | `pilotstd/manager/organize/organizer.py` L222-232、`pilotstd/query/adapters/ahbz.py` L27-30 + 适配器/归档链单测 | 阻断“新脏值”再产生；影响归档链（高风险路径） | **中高**：改归档写库语义，需归档链回归 + 真实数据 ≥3 条验证；必须在验证环境先跑 | 归档链测试全绿；新归档记录的 `file_index.status` ⊆ 9 枚举值（SQL 抽检） |
| P2（数据清洗） | C | **`未生效` 存量清洗**：`UPDATE file_index SET status='即将实施' WHERE status='未生效'`（10 行） | 生产维护窗口脚本（dry-run 先行；**本任务禁止执行**，AGENTS.md 红线：不改生产库） | 10 条记录；DB 与页面一致 | **中低**：写生产库需窗口 + 备份 + 审计；建议在 C2（读取侧别名）已让页面正确后再做，降低优先级 | dry-run 输出 10 行目标；执行后 `status_dist` 无 `未生效`；回滚脚本可逆 |
| P2（可观测性） | — | **补来源字段**：`file_index` 新增 `status_source`/`status_updated_at`（新迁移），归档/校验写状态时记录站点 | 新迁移脚本 + `organizer.py`/`validity_checker.py` 写入点 + `docs/architecture.md` | 未来 88 类问题可 5 分钟内定位来源站点（当前 47/88 完全不可反查） | **中**：改 Schema（AGENTS.md：跨模块/改 schema 先出方案），需迁移测试 + 文档联动 | 迁移测试 + schema 一致性门禁 |

### 5.2 建议优先级与理由

1. **先做 A（P0）**：改 1 个文件约 6 行、无契约/schema 变更、不碰生产库，**一步把 88 → 30**（58 条归位已废止）；
   这是投入产出比最高的修复。
2. **再做 C（P1 读取侧别名）**：同样不写库，把剩下 10 条 `未生效` 归入 `即将实施`，`未知` 归 0。
3. **然后 B（P1）**：给 `即将实施` 一个正式展示位（否则终态 30 条仍无处显示，只能被 unknown 桶收走）；
   涉及前端四件套，工作量最大，放最后。
4. A2（写入端归一）与 C1（存量清洗）作为 P2 治本项，防止新脏值再生；D（来源字段）作为可观测性长期项。

### 5.3 门禁与联动预检（改代码时）

| 门禁 | 触发原因（若执行 §5.1 改动） | 处置 |
|---|---|---|
| G-013 修复须带测试 | 改 `standard_service.py` 属逻辑变更 | 先写失败单测（stats 断言新口径）再改实现 |
| G-031 文档联动 | 改 `pilotstd/manager/` + 归档/适配器口径 | 同批更新 `docs/architecture/modules/manager.md`（L113 状态聚合清单）与 `docs/architecture/modules/query.md`；P2.4 改 schema 还要改 `docs/architecture.md` |
| 能力矩阵 | 若改 `pilotstd/core/status.py`（P1 C）或 `docker/api/`（P1 B） | 跑 `python scripts/generate_capabilities.py` 并同批提交 `docs/governance/capabilities_registry.md` |
| 前端四件套 | P1 B 改 `web/` | `type-check / lint / test / build` 全跑 |
| 生产红线 | C1 存量清洗 / D 迁移 | 需维护窗口；禁止在分析阶段 UPDATE 生产库 |

---

## 6. 主因判断与证据链（一句话版）

**最可能主因：状态写入端未做枚举归一 + 状态页三分类聚合口径缺条目（不是采集失败）。**

证据链（代码 → 数据 → 接口三层闭环）：

1. **写入端**：`pilotstd/manager/organize/organizer.py` L230 把 `effect_status` **原样**写入
   `file_index.status`（无归一、无白名单）；`QueryResult.status` 由各适配器直接给出，
   其中 `ahbz.py` L27-30 就定义了 `W→作废`，`search_strategy.py` L210-239 的 `STATUS_MAP`
   没有 `未生效` 条目（原样透传）。
2. **数据端**：`file_index.status` 实际出现 6 个值
   `现行 572 / 废止 95 / 作废 58 / 被代替 21 / 即将实施 20 / 未生效 10`（SQL ①，总和 776）。
3. **读取端**：`standard_service.py` L74-78 的 unknown = `NOT IN ('现行','废止','被代替')`
   → 把后三个值（58+20+10=88）整体当「未知」；`inactive`（L73）又不含 `作废`。
4. **接口端**：`/api/standards/status?status=unknown` 返回 88 条，其 `status_key` 是
   `voided/upcoming/unknown` 三种（不是一种）——自证「未知」桶里是**有名状态**，不是“查不到”。
5. **对照端**：58 条 `作废` 全部在 `过期作废/`（归档时已按废止族搬移），
   `core/status.py` L42/L137-141 与前端 `stdStatus.ts` L36-41 也都把 `作废` 当废止族
   → **口径在系统内部自相矛盾**，不是数据缺失。

---

## 7. 附带发现（不阻塞本次定性，但建议登记）

1. **标准号在状态页缺年代号**：`/api/standards/status` 的 `standard_number` 由
   `standard_service.py` L105 的 `(f.logical_code || ' ' || f.number)` 拼出，**不含 year**；
   实证 API 返回 `"GB 2970"`、`"API 685"`，而 DB 键是 `GB 2970-2026`、`API 685-2000`。
   影响：分部分/多年份标准无法唯一定位（本次 88 条里 `GB/T 20671` 就有 part=4/11 两条同名）。
   建议顺手修（1 处 SQL 拼接 + 前端列宽回归）。
2. **跨源状态冲突 15 条**：58 条 `作废` 中 15 条在 `announcement_match` 里口径为「现行」
   （公告状态由实施日期启发式生成，见 `pilotstd/announcement/matcher.py` L330-358，
   对“废止”并非权威）。建议在 P2 数据治理前人工抽核 3-5 条，确认“作废”是否源站原判；
   这不影响 A 类修复（无论真作废还是待核，它们都属废止族、都该离开「未知」桶）。
3. **名称解析残留 7 条**：如 `"6 厚钢板超声检测方法"`、`"26 非金属垫片材料分类体系…"`，
   是文件名解析把前缀数字并入名称（与 P1-7.1 编号识别同源），属独立问题。
4. **可观测性缺口**：`file_index` 无“状态来源/更新时间”字段，47/88 条无法反查抓取站点；
   建议按 §5.1 P2.4 补字段。
5. **已知边界复用**：`docs/onboarding/08-known-boundaries.md` #4 已登记“归档只写未知、不读 validity”，
   本次建议在该文追加一条：**「标准状态页的『未知』= 三分类口径的补集，不等于数据缺失；
   `作废/即将实施/未生效` 均会被折叠进未知」**，避免后续再次误判。

---

## 8. 验收自检

- [x] 88 条**全部**出现在 §2 清单（逐行编号 1-88，无抽样省略）。
- [x] 每条结论均有「字段 / 接口 / SQL」证据：§2 每行的 `status` 来自 SQL ③；§3 抽样每行给出
      `file_path / validity / 公告 / pending` 四类字段；§4 每类给出代码行号 + SQL 编号。
- [x] 数据只读：全部请求为 `GET` + 白名单 `POST /api/login`、`POST /query`（单条 `SELECT`）；
      未执行任何写库操作。
- [x] 报告结构：数据来源与方法 / 全量清单 / 抽样 15 条 / 定性分布 / 修复方案（分类→动作→风险）/ 主因 / 附带发现。
- [x] 文件路径：`docs/plans/2026-11-24-p1-unknown-standards.md`（本任务唯一写入文件）。

---

## 附录 A：接口原始返回（证据留存）

```
GET /api/standards/status/stats
→ 200 {"active": 572, "inactive": 116, "unknown": 88}

GET /api/standards/status?status=unknown&page=1&page_size=100
→ 200 total=88, items=88；items[].status_key ∈ {"voided","upcoming","unknown"}
   items[0] = {"id":3191,"standard_number":"API 685","status":"作废","status_key":"voided",
                "last_checked_at":"2026-10-14T03:00:00.305334+00:00","check_count":2,...}
   items[1] = {"id":3562,"standard_number":"GB 2970","status":"即将实施","status_key":"upcoming",...}

GET /api/standards/status?status=voided&page=1&page_size=1     → total=58
GET /api/standards/status?status=作废&page=1&page_size=1        → total=58
GET /api/standards/status?status=upcoming&page=1&page_size=1   → total=20
GET /api/standards/status?status=未生效&page=1&page_size=1      → total=776（未解析 → 过滤被忽略）
```

## 附录 B：全量状态分布（SQL ① 原始输出）

| status | count |
|---|---:|
| 现行 | 572 |
| 废止 | 95 |
| 作废 | 58 |
| 被代替 | 21 |
| 即将实施 | 20 |
| 未生效 | 10 |
| **合计** | **776** |
