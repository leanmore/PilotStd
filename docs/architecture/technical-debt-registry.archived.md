# 技术债登记簿（已归档，停止维护）

> **状态：⛔ 已废止（2026-09-27，第十轮·架构优化与债务清算轮）**
>
> **技术债唯一数据源（Single Source of Truth）＝ [`docs/technical-debt.md`](../technical-debt.md)。**
> 本文件不再更新：任何债务、已接受决策、已跳过测试的登记一律写入主簿；本文件仅作为归档留痕保留文件名与去向说明。

## 一、归档原因（实测）

1. **数据源不唯一**：本簿与 `docs/technical-debt.md` 并存，各自一套编号，需手工互指——原正文即写着"本登记簿编号 #21 = `docs/technical-debt.md` 第二节 #15"，读者必须同时看两份才能定位一条债。
2. **核心数据已过期**：本簿「六、G-010 警告基线（Backlog，**9 文件**）」与实测不符——2026-09-27 实测 `check_g_010_code_size.py`：**警告档（>400 且 ≤500）3 个**、**阻断档（>500）0 个**（且本簿表格里的 `check_g_012_sql_schema.py` 499、`docker/auth.py` 490、`AnnounceDetail.vue` 476、`api/announce_detail.py` 454、`notification/manager.py` 479、`check_g_012_comment_density.py` 452 均已被第八轮拆分治理）。
3. **门禁联动已由主簿承接**：`scripts/docs_sync_check.py` 的「架构模式变化（Handler/Mixin）」触发目标原指向本簿，已于同轮改指 `docs/technical-debt.md`。

## 二、内容去向（逐节处理，2026-09-27）

| 原节 | 处理 |
|---|---|
| 一、已跳过的测试（13 条登记，现存 6 条） | **并入**主簿「四、已跳过测试」——13 行明细（含文件:行号与处理方式）逐字保留；其中"已删除"类条目的实测更正由主簿本轮 T-10 执行 |
| 二、已接受的设计决策（8 条） | #1~#5 与主簿原有 5 条同源（不重复登记）；**#6 JWT_SECRET 固定默认值 → 主簿「五」#6**；**#7 内存会话存储（无持久化）→ 主簿「五」#7**；#8 `__init_tr` 命名不规范（已修复）属「一、已清理」性质，不另立条目 |
| 三、已知问题（21 条） | 已修复/已解决者与主簿「一、已清理」重复或已过时（不再单列）；**#6 WebSocket 广播无用户级路由 → 主簿「五」#8**；**#3 `_batch.py` 溢出回收部分内联、#4 迁移链顺序依赖 → 主簿「六、观察项」**（2026-09-27 编号收敛前为「六-B」）（均标注"并入留痕、无新增行动"）；#19/#20 即主簿 TD-13/TD-14（已修复）；#21 即主簿 #15（已接受并关闭，2026-09-26） |
| 四、Mypy 豁免项 | **并入**主簿「一、已清理」并**判定作废**——原文"mypy 错误不阻断 pre-commit（使用 `--no-verify`），CI 中 non-blocking"与现行 **G-038（历史遗留错误清零）** 及 **P-104（门禁不绕过）** 直接冲突 |
| 五、处理流程图 | **废弃**——与主簿「〇、登记规则与分类标准」重叠；且原正文代码块未闭合（文档缺陷） |
| 四、已跳过的环境依赖（1 项：`pytest-asyncio`） | **废弃**——实测 `tests/test_health.py` 已无 `async def`/`asyncio` 引用，且 `pytest-asyncio` 未在任何 `requirements*.txt` 中声明 → 该依赖项随测试改写自然消失 |
| 六、G-010 警告基线（Backlog，9 文件） | **废弃**（数据过期，见「一、归档原因」第 2 条）；现行数据见主簿台账 #11 |

## 三、历史原文获取

本文件归档前的完整内容仍可从 git 历史取得（无需恢复文件）：

```bash
git show ba9af616:docs/architecture/technical-debt-registry.md
```

- `ba9af616` = 本簿（旧路径 `docs/architecture/technical-debt-registry.md`）**最后一次内容变更**的提交。
- 归档提交本身亦可取归档前版本：`git show <本提交的父提交>:docs/architecture/technical-debt-registry.md`。
