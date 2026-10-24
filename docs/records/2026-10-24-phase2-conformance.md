# 通知二期裁决落地核对（2026-10-24）

> **性质**：只读核对。逐条把 18 项裁决对到代码，标出**已实现 / 未实现 / 待核**。
> **用途**：施工前先确认"哪些已经做过"，避免重建。原件裁决见 `docs/records/2026-10-24-notification-phase2-decisions.md`。

## 结论速览

| 结论 | 数量 | 编号 |
|---|---|---|
| 已实现 | 10 | Q1、Q2、Q3、Q4、Q5/N2、Q6、Q9（改判并入 G-045）、Q10、N1、Q11 |
| 部分/偏离 | 0 | — |
| 未实现 | 0 | — |
| 待核 | 7 | Q7、Q8、N3、N4、N5、N6、N7 |

## 逐项核对

| ID | 裁决 | 核对结果 | 证据 |
|---|---|---|---|
| Q1 | 3 个多余事件保留但不默认订阅 | **已实现** | 三者的 `default_channels=()`（`event_spec_data.py`：standard_first_registered / normalize_complete / download_started），出厂默认不订阅 |
| Q2 | 5 个重复事件订阅层只留其一 | **已实现（默认订阅层）** | 每对重复事件只有一方有默认渠道：`validity_batch_report`(wechat) ↔ `validity_round_summary`(无)；`announcement_check_complete`(wechat) ↔ `announce_fetch_summary`(无)。用户级订阅在 Web 设置页自选 |
| Q3 | 补"待确认"文案 | **已实现** | `_builders_batch.py:241,256` 按 `pending>0` 分支 |
| Q4 | 聚合键二元 | **已实现** | `aggregate_keys.py` 明确 v2 二元模式与非法值回退 |
| Q5 | 阶段 3 只做 URL 按钮 | **符合** | `edit_message` 仅在 `channels/{base,feishu,telegram}.py` 定义，**全库 0 调用方** |
| Q6 | 记录始终开、投递可关 | **已实现** | `_dispatcher.send_event`：`if not host._enabled` → `_record_when_disabled()`（默认开，环境变量可回滚）→ 只写库 `status=skipped`，不调用渠道 |
| Q7 | Windows 15 事件走托盘 | 待核 | 托盘能力存在（`_window_lifecycle.py`），分端路由未取证 |
| Q8 | 只改 CLI 帮助文档 | 待核 | 未查 `docs/guides/用户帮助文档.md` 的 CLI 章节 |
| Q9 | 新增"声明 vs 实现"门禁 | **改判已落地（2026-10-24）** | 原裁决"新增独立门禁"；经核对 B1 已覆盖同语义，改为并入 G-045 并在 `gates.md` G-045 节留痕，不新增编号 |
| Q10 | 用户时刻清单作第二 SSOT | **已实现** | `user_moments.py`（111 行）+ `user_moments_data.json` |
| Q11 | 新增管道级时刻 | **已实现（2026-10-24，`f409ab1e`）** | 新增 `auto_pipeline_summary`：`events.py` + `event_spec_data.py` + 构建器 + 三语文案 + 用户时刻 #38；`_auto.py` 两个入口收尾各发一次；G-045 覆盖 44/44 |
| N1 | 警告绕过静默 | **已实现（2026-10-24）** | 原缺口：`_dispatcher.do_send:196` 不看级别；已改为 `_QUIET_BYPASS_LEVELS = {warning, error}` 分流，回归 `tests/unit/core/notification/test_dispatcher_quiet_bypass.py`（4 例） |
| N2 | 终局不改写 | **符合** | 无任何 `edit_message` 调用点，改写路径不存在 |
| N3 | 先补耗时埋点 | 待核 | 未查桌面/定时任务的耗时记录 |
| N4 | 凭证平滑双读 | 待核 | 未查 `_credentials.py` |
| N5 | 先做已取证渠道 | 待核 | 企微/飞书能力补齐与否未取证 |
| N6 | 4 处硬编码英文标签保持 | 待核 | 未查 schema 标签 |
| N7 | 新门禁缓阻断 | 待核 | 未查门禁配置 |

## 两个值得注意的发现

1. **Q9 已改判并留痕**：原裁决要求"新增独立门禁"，实际能力在 G-045 的 B1 维度里。经决策者同意改为"并入 G-045 + 在 gates.md 记录"，不新增编号——避免拆成两个薄门禁。
2. **N1 原是缺口，已修**：修复前 `do_send` 只看"是否静音"、不看级别，警告会被一起延后；2026-10-24 已按裁决改为 warning/error 绕过，并加 4 例回归。教训：**静音是"降噪"不是"静音一切"**。

## 下一步

| 顺序 | 事项 | 类型 |
|---|---|---|
| 1 | ~~实测 N1（静音期内发警告）~~ **已完成并修复** | 代码 + 测试 |
| 2 | ~~Q11 管道级时刻~~ **已完成（`f409ab1e`）** | 代码 + 文案 + 测试 |
| 3 | ~~Q9 补独立门禁或改判~~ **已改判并入 G-045** | 门禁 |
| 4 | ~~Q1/Q2/Q6 核对~~ **已完成，均符合裁决** | 只读 |
| 5 | 剩余待核：Q7、Q8、N3、N4、N5、N6、N7 | 只读 |
