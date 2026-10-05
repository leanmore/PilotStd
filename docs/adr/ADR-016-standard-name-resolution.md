# ADR-016: 标准名称解析——「最高可得阶段名」回退链与对外边界命名统一

> 日期：2026-10-05（决策于 2026-10-05 会话；承接 2026-06-20「名称决策」专项 `0f32262b`）
> 状态：✅ Accepted（**批次一、批次二、批次三均已落地**）
> 来源：通知系统验收审查（标准名/号血缘取证 第 1~5 轮）+ 决策者裁定 D1/D2/D3/D7/D8
> 关联：相关代码 `pilotstd/core/name_resolution.py`；相关专项提交 `0f32262b`；相关文档 `docs/plans/notification-system-design/06-spec-and-phasing.md`

---

## 背景

同一个标准的「名称」在系统里存在**多份副本**，分属不同处理阶段：

| 阶段 | 字段 | 写入者 |
|---|---|---|
| ① 解析名 | `announcement_record.std_name` / `file_index.std_name` | 公告附件解析（`docker/api/_announce_detail_parse.py:80-87`）、文件名扫描（`pilotstd/scan/watcher.py:60`） |
| ② 查询名 | `standard_info_cache.result_json` 内的 `standard_name`（读取时映射为 `found_name`） | 网站查询适配器（`pilotstd/query/adapters/*.py`） |
| ③ 决策名 | `final_name`（+ 规范化中间值 `normalized_name`），并**在内存中回写** `std_name` | 名称决策（`pilotstd/pipeline/router.py:271-304`，2026-06-20 专项；**仅对进入下载队列的条目生效**，见 `:260-261`） |

**症状**：下载通知族（`download_started`/`download_failed`/`download_complete`）取名的实现只读 ①
（原 `favorite_download.py::_fetch_std_meta` → `SELECT std_name FROM announcement_record`），于是
「①无对应行」（如 Web「导入下载」手输标准号）或「①已过期」时，通知里的名**为空或过期**；
而 ③ 的决策结果**从不落库**，任何消费方（收藏 API、下载链）都无法读到它。

## 决策

1. **名称取值＝「最高可得阶段名」回退链：③ → ② → ①**，全空返回空串。
   实现为唯一入口 `pilotstd/core/name_resolution.py::fetch_resolved_name()`（纯函数 `resolve_name()` 承载顺序规则）。
   **不保证**来自 ③——这是**预期行为**，不是缺陷（批次一阶段无 v66 迁移时自然回退 ②/①）。
2. **对外边界统一全写 `standard_name`**：API 响应键、通知载荷键、前端类型、spec/契约一律全写；
   **DB 存储层列名本轮不动**（仍为 `std_name` / `found_name` / `final_name`），由上述模块做**单点转换**。
   理由：编号侧本已全写（`standard_number` 为五层主流），名称侧继续用 `std_name` 会造成"左右不对称"；
   且 2026-06-20 专项引入的 `source_name`/`normalized_name`/`final_name` **全是全写**，`std_name` 属更早遗留。
   （本条**撤销**此前的"通知系统新增字段定为 `std_name`"裁定。）
3. **权威名落点唯一化（批次二）**：在 `announcement_record` 新增 `final_name` 列（新迁移 v66），
   由名称决策后写入；**弃用 `pending_lookup.final_name` 作为权威源**（该表是"待确认项"过程表，
   且下载桶条目**不会**产生该行——全库实测下载链与 `pending_lookup` 零交集）。
4. **② 的信息不删除**：`standard_name` 仅降级为"适配器内部名"，
   其值继续保存在 `standard_info_cache.result_json` 与 `pending_lookup.found_name` 中
   （避免丢失"网站上原来叫什么/与我们的名是否不一致"等溯源与人工核对能力）。

## 核心约束

- **批次一边界**：`announcement_record.final_name` 列**尚不存在**时必须正常工作
  ⇒ 用 `PRAGMA table_info` 探测列（先例 `_migrate_v54.py`），且该列**不得出现在批次一的 SELECT 中**；
  批次二加列后**本模块零改动**自动生效。测试锁定：`tests/test_name_resolution.py::test_column_absent_still_works`。
- **契约三处必须同批**：`event_spec.py` 的 `payload_keys`、`tests/test_notification_e2e.py` 的 `TRIGGER_KEYS`、
  生产方 `favorite_download.py` 的载荷键——否则正向断言（`builder ⊆ trigger ∪ whitelist`）**红在 `:388`**。
- **`standards.name` 不动**：它是唯一索引 `idx_standards_four_elements (sha256, code, name, size)` 的一部分
  （`pilotstd/core/db/_migrate_v16_v49.py:372`），且写入用 `INSERT OR IGNORE`（`organizer.py:228`）
  ⇒ 改名会导致**同一文件重复入库**的静默脏数据。
- **不改** `source_name` / `normalized_name` / `final_name` 的既有语义与列名（2026-06-20 专项既定）。
- **通知链路不得因元信息缺失而失败**：所有分支降级为空串、不抛错。

## 批次划分（按数据流方向，每批可独立回滚）

| 批次 | 内容 | 依赖 | 验收 |
|---|---|---|---|
| **一（已完成）** | `name_resolution.py` + `_fetch_std_meta` 改回退链并返回全写键 dict + `event_spec.py`/`TRIGGER_KEYS` 同批补 `standard_name` + 新单测 | 无迁移 | e2e/契约绿 + V4 阻断 0 + 三条下载路径通知有名（取 ②/①，符合 §决策 1） |
| **二（已完成，2026-10-05）** | 迁移 **v66**：`announcement_record` 追加 `final_name` 列 + 从 `pending_lookup.final_name` 关联回填（只填空行）；**写入点**：`manager/classifier.py::QueryClassifier._persist_final_names()`（名称决策出口，`Database.executemany` 批量、独立短连接、best-effort） | 迁移 v66 | 迁移幂等（连跑两次内容不变）+ 回填语义夹具（已有值不覆盖／取 resolved 非空值／无匹配保持 NULL）+ 全量 5145 passed |
| 三（已完成，2026-10-05） | 消费方切换：**B3-a** 批量取值 `fetch_resolved_names`；**B3-b** 收藏 API（列表/导出）批量映射 + 对外键名统一；**B3-c** 待确认接口行内零查询回退链 + 旧键清理（并修复"前端已读 `standard_name` 而后端从未返回"的缺陷）；**B3-d** 本地索引展示名对齐回退链（纯内存、不回查 DB） | 一/二 | 全链路同名同值；对外只留 `standard_name` |

## 批次三：消费方切换与「就地升级」裁定

**裁定（就地升级、无过渡期兼容）**：所有消费方统一走回退链取值，**对外 JSON 键名统一为 `standard_name`**，
旧键 `std_name` 在**边界层**（API 组装处）直接清除，**不设双键过渡期**。
理由：本次改动范围本就包含前端同批改名，不存在"后端先上、前端后跟"的部署窗口；
保留双键读取等于在 D8 契约上开洞，必然成为新的技术债 ⇒ **兼容层本身就是需要再次偿还的债**。

| 子批 | 范围 | 关键实现 |
|---|---|---|
| B3-a | `pilotstd/core/name_resolution.py` | 批量入口 `fetch_resolved_names()`：**固定两次数据查询 + 内存映射** + 超 900 号分块（SQLite 参数上限余量）；与单条版共用 `_name_from_json` 解析口径 |
| B3-b | `docker/api/favorites.py` + 前端 `FavoritesView.vue` | `_apply_resolved_names()` 一次批量覆盖；**未命中回退表内原值**（绝不 null/空串）；JSON 与 CSV **共用同一份**解析结果；对外只留 `standard_name` |
| B3-c | `docker/api/pending.py` + 仪表盘 `PendingItemsCard.vue` | **行内三列零查询**回退链（③`final_name`→②`found_name`→①`std_name`）；保留阶段字段（D4/D5：② 信息不删、语义不动）；清除旧键 `std_name` |
| B3-d | `pilotstd/core/_file_index_query.py` | 展示名 `std_name` 按回退链重算（**纯内存、不回查 DB、无 N+1**）；`found_name` 保持②查询名语义（D5） |

**范围校验（明确"不改"的部分）**：`web/src/types/api.ts` 与 `web/src/composables/useFavorite.test.ts` 中的
`std_name` 属 **`AnnouncementRecord`（公告记录）** 类型/夹具，对应公告接口，**不在批次三范围**（避免越界改名）。

**遗留**：`pending_lookup.final_name` 列仍在（仅历史兼容；③ 的权威落点已是 `announcement_record.final_name`）；
其**物理删除**需独立清理任务 + **新迁移号 v67**，不在批次三范围。

## 批次二补充决策与实现约束

1. **回填判据＝"取所有非空"、不限 `status`**：`pending_lookup.status` 表示"待确认流程"的生命周期
   （pending / resolved / manual_required），与名称优劣无关；已 `resolved` 的行恰恰是**人工确认过的高质量③值**。
   幂等补充：回填语句带 `announcement_record.final_name IS NULL OR = ''` + `EXISTS` 守卫 ⇒ 重跑不覆盖已有值。
2. **写入点语义**：`_persist_final_names()` 紧跟 `_dispatch_by_router()`（即 `apply_actions` ⇒ `_resolve_names` 之后），
   保证「决策 → 持久化」在同一抽象层闭环；仅对**决策确实产出 `final_name`** 的条目写库，且缺 `get_full_number` 的条目跳过。
3. **批量与隔离**：收集 `(final_name, standard_number)` 后**单次 `Database.executemany`**（严禁循环逐条 UPDATE）；
   使用**独立短连接**（独立事务），异常只记 debug ⇒ 失败不影响内存分类结果与后续归档。
4. **匹配不到不报错**：`announcement_record` 唯一键为 `(source_site, pid, standard_number)`，手输/本地扫描来的
   标准号可能没有对应行 ⇒ UPDATE 影响 0 行属正常，静默跳过。
5. **`pending_lookup.final_name` 状态＝已弃用（仅历史兼容）**：自批次二起，③ 的权威落点为
   `announcement_record.final_name`；`pending_lookup.final_name` **不再作为权威源**，仅在回填期作**历史数据来源**，
   待批次三把消费方全部切到 `fetch_resolved_name()` 后可按需清理（**本轮不删列**，避免不可逆）。
6. **测试表结构同步**：v66 追加列后，7 个手工建 `announcement_record` 的测试需同步补列
   （由 `scripts/check_schema_consistency.py` 判定；注意该门禁要求列集一致，且 **SQLite 不接受尾随逗号**）。
