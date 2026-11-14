# P2-03 批 2：零调用符号裁定（2026-11-14）

> 台账：`docs/governance/ISSUE_LEDGER.md` P2-03（零调用函数/方法）。
> 批 1（2026-11-13）已删 `get_fallback_chain`、`execute_request_interval`；本批处理其余 13 组。
> **结论：0 删除，全部按「公开 API / 脚本入口 / 测试夹具 / UI 遗留」保留，并写明触发条件。**
> 判定口径：`git grep -w <符号>` 统计"定义处 / 生产引用 / 测试引用 / 脚本引用"；
> 只有"生产 0、脚本 0、测试仅覆盖自身"才具备删除资格——本批没有一组同时满足且改动可控。

---

## 一、裁定表

| # | 符号 | 定义处 | 生产引用 | 测试/脚本引用 | 裁定 | 理由与触发条件 |
|---|---|---|---|---|---|---|
| 1 | `CacheManager.mark_stale/mark_valid` | `pilotstd/core/cache_manager.py` | 0 | 2 个测试文件 | **保留** | 缓存失效 API 面：`get`/`put` 之外的显式失效入口，属可用的公开方法；删掉会让"要不要失效"只能在调用点抄内部状态。触发：若确认缓存永不需要显式失效（只靠 TTL），随缓存模块重构一并删 |
| 2 | `TaskQueue.register_handler` | `pilotstd/task/queue.py` | 0 | 3 个测试文件 | **保留** | 队列扩展点（handler 注册）；测试以它构造"有处理器的队列"。触发：任务中心定型为"固定 handler 表"时删 |
| 3 | `TaskQueue.pause` | `pilotstd/task/queue.py` | 0 | `tests/stress_selfcheck.py:189`（压测脚本） | **保留** | 脚本入口在用（压测暂停/恢复）；且与 `resume` 成对，单删会破坏状态机语义。触发：压测脚本改用别的方式控速时删 |
| 4 | `PipelineStore.is_stop_requested/mark_interrupted` | `pilotstd/task/pipeline_store.py` | 0 | 1 个测试文件 | **保留（但注明是"未接线契约"）** | 与 P1-04 同源：`batch_state` 已定性为"只写不读的审计表、不做断点续跑"，这两个方法是同一套"中断/续跑"契约的残留。**没有消费者 = 没有假承诺**（不像 P1-04 曾有表注释承诺续跑），故不删；触发：做真正的"重启后续跑"时要么接线、要么删 |
| 5 | `verify_password` | `pilotstd/core/security.py:27` | 0 | 2 个测试文件 | **保留（标安全注意）** | 兼容 `salt:sha256` 旧哈希的分支；生产登录走 `verify_password_with_salt`/`pwd_context`。删它要同时删两处测试（含 bcrypt 正常路径断言），属安全模块改动，**不搭在 triage 批里做**。触发：确认存量库无旧格式哈希后，连同旧分支单独一批删除 |
| 6 | `to_iso` | `pilotstd/core/time_utils.py:80` | 0 | 1 个测试文件 | **保留** | 纯转换工具（str/datetime → ISO），测试锁行为；与 `iso_now`/`parse_iso` 同族，删一个反而让 API 不一致。触发：统一时间工具时再评估 |
| 7 | `days_ago_iso` | `pilotstd/core/time_utils.py:88` | 0（生产） | `tests/test_query.py` 作**夹具**构造"31 天前的缓存行" | **保留** | 生产零调用，但测试用它造过期数据；删除等于把测试里的日期算术搬回去，收益为负 |
| 8 | `install_wheel_bytes` | `pilotstd/announcement/ocr/_model_manager.py` | 0 | 1 个测试文件 | **保留** | OCR 模型安装的"从已下载 wheel 字节装入"入口，离线安装路径用得上；删了离线场景要重写。触发：OCR 模型改为在线按需下载、确认无离线安装需求时删 |
| 9 | `parse_hcno_from_search_page` | `pilotstd/download/adapters/openstd_download.py` | 0 | 1 个测试文件 | **保留** | 下载适配器的页面解析 helper；适配器站点改版时是首选排查/复用点。触发：openstd 站点改版后确认新解析器完全替代时删 |
| 10 | `DirBuilder.ensure_expire_dir` | `pilotstd/organizer/dir_builder.py` | 0 | 1 个测试文件 | **保留** | C20 已裁定"规格描述错、`safe_move` 懒建目录"，方法本身是对的兜底；U38 已记录零调用。触发：目录构建重构时把"懒建"收敛到一处再删 |
| 11 | `scope_of` | `pilotstd/core/config/scope.py:41` | `scripts/migrate_notification_scope.py:37` | 1 个测试文件 | **保留** | 有脚本消费者（迁移脚本用它决定键归属），不是死代码 |
| 12 | `_on_query_result_ready`（MainWindow） | `pilotstd/ui/main_window/parts/_query_ops.py:24` | 0（信号 `query_result_ready` 已于 W1-U1 删除） | 8 处调用（`tests/gui/test_coverage_queries.py` 7 + `test_main_window_core.py` 1） | **保留，但登记为"UI 遗留清理批"首项** | W1-U1 已给出处置（删方法 + 迁移两处测试），但那两处测试实际在断言"列渲染"，要迁到 `QueryUIHandler.on_query_result_ready` 才能删，属重构而非清理。触发：下一次 UI 结构改动（P2-08 拆分/TaskView 再膨胀）时一并做 |
| 13 | 21 个 `_get_*_adapter` 懒加载 getter | 19 个在 `pilotstd/query/__init__.py` | 0 | 0 | **保留** | A-33 已裁定：模板已停止生成新 getter，现存仅作兼容；一次删 21 个会改动查询包导出面。触发：下次清理遗留代码时整批删 + 同步 `__all__` |

---

## 二、为什么不删（方法论）

1. **本批的收益是"决策留痕"，不是行数**。13 组里 12 组是"生产 0 引用"，但它们分别是扩展点（1/2/3/4）、工具族（6/7）、离线能力（8）与站点解析器（9）——删除会让下次改到这些模块的人重新判断"这里为什么空着"。
2. **唯一"看着该删"的 12 号需要重构**：`_on_query_result_ready` 的测试在断言列渲染，删方法必须先把断言迁到在用的 `QueryUIHandler` 路径，否则是拿覆盖率换行数。
3. **安全模块不搭车**：5 号 `verify_password` 涉及旧哈希分支与两处密码测试，按"最小 diff"原则单独立批。
4. **删除的判据**（供下一批复用）：`git grep -w` 生产=0 且脚本=0 且测试仅"直接调用被测符号本身"（不含夹具/断言连带），且删除后 `__all__`/导出面同步。

---

## 三、给下一批的动作清单

| 批 | 内容 | 前置 |
|---|---|---|
| 批 3（可选） | 删 12 号 `_on_query_result_ready` + 迁移 8 处测试断言到 `QueryUIHandler` | 与 UI 结构改动同批 |
| 批 4（可选） | 删 13 号 21 个 getter + 同步 `query/__init__.py` 导出 | 确认无动态 `getattr` 调用（已 grep 0） |
| 批 5（可选） | 删 5 号 `verify_password` 的旧哈希分支 + 两处测试 | 先确认存量库无 `salt:sha256` 格式哈希 |
