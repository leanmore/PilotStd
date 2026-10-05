# ADR-016: 标准名称解析——「最高可得阶段名」回退链与对外边界命名统一

> 日期：2026-10-05（决策于 2026-10-05 会话；承接 2026-06-20「名称决策」专项 `0f32262b`）
> 状态：✅ Accepted（批次一已落地；批次二/三待排期）
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
| 二（待排期） | `announcement_record.final_name` 列（v66）+ 名称决策后写入 + 弃用 `pending_lookup.final_name` 作权威源 | 迁移 v66 | ③ 覆盖的条目通知名＝决策结果 |
| 三（待排期） | 收藏 API / 待确认页 / 本地索引统一切到 `fetch_resolved_name()` | 一/二 | 全链路同名同值 |
