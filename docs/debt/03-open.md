# 技术债 · 可修复、尚未修复

> 本文件是 `docs/technical-debt.md` 四分类之一：**未修**（正式债 + 可动作项 + 待裁定项）。
> 判据：**有明确动作可做**、且尚未做完。做完即移入 [01-archive-closed.md](01-archive-closed.md)；
> 定性为"不做/不划算"则移入 [02-accepted.md](02-accepted.md)；修完但需盯一段时间则进 [04-watch.md](04-watch.md)。
> **最后核实：2026-10-27**（每条都注明核实方式与时间戳）。
> 回主档：[technical-debt.md](../technical-debt.md)

---

## 一、正式存续债（3 条）

| # | 项目 | 状态 | 现状（实测） | 下一步动作 | 触发条件 |
|---|---|---|---|---|---|
| **T-40** | V6 wechat 真发未取证 | `观察中`（用户 2026-10-17 裁定：**后续再说**） | 本地 `data/config.json` 的 `notification.channels.wechat` = `{"enabled": true, "webhook_url": ""}`（2026-10-16T22:07 实测）⇒ 非部署环境无法真发；渠道契约/错误映射/签名/i18n 单测已覆盖 | 部署环境补一次真发取证（会真的发一条消息到企微） | 用户择期（本轮不做） |
| **T-42** | 渠道调用频率限制未逐家实现 | `基座已具备`（2026-10-17） | 实测（2026-10-16）：限流/退避**只长在 telegram**（27 处命中），`dingtalk` 1、`feishu` 1、`wechat` 4、`base.py` **0** ⇒ 一次 429/抖动只有 telegram 退避重试，其余三家当场丢通知。**2026-10-17 已修**：重试/退避提升为渠道基座 `base._with_retry`（统一 3 次、退避 (2,4)、服务端 `retry after` 优先且截顶 60s、429/5xx 与限流关键词兜底、错误 120s 去重），**四家渠道全部接入**（提交 `191b7259`，2026-10-17T06:19:36+08:00；测试 195 passed） | **残留**：各渠道限流的**具体错误码未逐家取证**（钉钉官方文档 JS 渲染取不到正文；飞书/企微未逐码核对）⇒ 现用 `looks_rate_limited` 关键词兜底，取证到 `errcode`/`code` 后改为**按码判定** | 取到任一家官方限流码时 |
| **T-43** | **企微回调取证** | **已归并入 A-27**（2026-10-29） | A-24 取消后回调只服务菜单点击；端点/验签/解密/EventKey 解析作为 A-27 P1 的验收能力；需一条真实菜单点击报文校准 `EventKey/FromUserName/AgentID` | 随 A-27 |

## 二、可动作项（有明确动作，按"值不值得现在做"排序）

| # | 项目 | 状态 | 现在能做什么 | 触发条件 / 备注 |
|---|---|---|---|---|
| **A-1** | **P7-12：`docker/api/tasks.py:138` 越过 DAO 直调私有 `mgr.task_queue._persist(task)`** | ✅ **已修（2026-10-18）** | `TaskQueue.persist()` 公共入口已加，`docker/api/tasks.py` 改调用它；测试断言 `persist` 被调且 `_persist` 不再被 API 触碰 | **无前置条件，可随时做**（`docs/plans/notification-redesign/10-阶段2投影入口调查.md:72` 明写"不得因 P4b 收尾而勾销"） |
| **A-2** | **G-049 防膨胀门禁只覆盖 `manager.py`**（`scripts/check_g_049_manager_size.py:18` 的 `TARGET`） | ✅ **已修（2026-10-18）** | `TARGETS` 扩展为 manager.py + 6 个通知热点文件，上限=当前有效行+约 5% 余量；`*_data.py` 静态规格表不纳入（避免每加渠道就红）。测试 `tests/test_check_g_049_notification_sizes.py`（3 例） | 触发条件＝通知模块再出现单文件膨胀 |
| **A-3** | **`channel_spec.schema ↔ get_config_schema()` 互证门禁缺失**（现只有字段级断言 `tests/test_channel_spec.py:72-119`） | 未修（可选） | 加一条"声明 ↔ 实现"一致性门禁 | 触发条件＝渠道字段再次漂移 |
| **A-5** | **cookiecutter 真实 CLI 端到端未入 CI** | 观察 | 模板改动涉及 hooks 时补一条真实 CLI 用例（渲染/编译/零字面量已由 jinja2 用例覆盖） | 触发条件＝hooks 变更或脚手架被频繁使用 |
| **A-6** | **`known-issues.md` 第 4 项：Telegram 429 的 55.6% 未复测** | 观察 | 部署后取 `GET /api/notification/logs` 的 success/failed 分布 + 容器日志 429 计数，给出改善证据 | 触发条件＝下次通知量统计复核 |
| **A-9** | **解析失败日志格式未统一**（`pilotstd/scan/parser/__init__.py` 的 `TODO(P2)`） | ✅ **已修（2026-10-28）** | 改为四段键值 `解析失败: path=%s type=%s error=%s detail=%s`（沿用项目既有 `xxx失败: key=%s` 风格，参照 `announcement/base.py:184`、`core/audit.py:51`、`core/cache_manager.py:159`）；`type`=文件扩展名、`error`=no_match、`detail`=尝试的匹配器数；新增 `tests/unit/scan/test_parser_failure_log.py` 断言四字段。定向 29 passed、全量 5812 passed | 无（已收口） |
| **A-10** | **设置页 Tab 定位依赖 DOM 顺序**（`web/src/views/settings/constants.ts` 的 `TODO(P2-FOLLOWUP)`） | ✅ **已修（2026-10-28）** | Tab 按钮加 `:data-tab="t.key"`；3 处测试选择器改为 `.tab-bar button[data-tab]`（保留 tab 按钮限定，避免误抓未来其它 data-tab 元素），active 断言改为 `.tab-bar button[data-tab="storage"].active` 且保留 `.text()==="存储"`（语义不变、定位更精确）；删除 TODO。前端四件套：type-check 0 / lint 0（281 warnings）/ vitest 43 文件 336 例 / build 成功 | 无（已收口） |
| **A-11** | **两条自定义 eslint 规则"已定义但未执行"**（`web/eslint.config.js` 把 `custom/no-raw-i18n-key`、`custom/no-sensitive-persist` 设为 error，但 package.json 无 lint 脚本、CI 无 eslint 步骤） | ✅ **已修（2026-10-25）** | `package.json` 新增 `lint: eslint src`；CI `test-frontend` 在 type-check 后执行 `pnpm run lint`。前置的 56 条 `no-raw-i18n-key` 命中经核查**全为误报**（存键定义，消费处 `t()`），已通过规则重构清零（`96f04c40`，7 个 RuleTester 用例）；`no-sensitive-persist` 仍为 0 命中。当前 `eslint src` = 0 errors / 281 warnings。**保留的"调用参数对象"报告形态当前生产命中 0 条**（是预防未来新增，不是"还有已知违规未处理"）；`npm/pnpm test` 自 2026-06-17 初始提交即在（42 个 `.test.ts`），A3/A4 曾漏跑、已补并写入 AGENTS §十 | 无（已收口）；后续新增违规由 CI 阻断 |
| **A-12** | **6 个适配器的 `_search` 无直接测试**（`ccsn`/`sppt`/`sppt_local`/`jtst`/`mee`/`nrsis`；`tests/` 中 grep 零命中） | ✅ **已修（2026-10-25）** | `test_adapter_search_delegation.py` 覆盖 6 类委托与边界；`test_query_standards.py` 覆盖 6 个适配器的正常 + 非 200 + 传输异常 + 解析层空结果（23 用例，respx/responses 按测试隔离），**并断言实际发出的 method/path/query（POST 含 body）**。历史口径：A-12a（`b44cd533`）的 mock 为 `url__regex=".*"`，只验证了解析层对 fixture 的处理，**请求构造层未被验证**；该缺口在合并版（`c262900c`）收紧 mock 后才覆盖。**遗留观察**：`nrsis` 走 `http://`（`http://www.nrsis.org.cn/portal/xxcx/std`），2026-10-25 实测 HTTP 200、HTTPS 443 拒绝 ⇒ 站点本身无 HTTPS，适配器与站点一致，非明文降级缺陷 | 触发条件＝站点协议变更或新增适配器时 |
| **A-19** | **G-013 不认前端 vitest，前端修复被迫用 `chore`** | ✅ **已修（2026-10-29）** | `is_test_file` 接受 `web/src/**/*.test.ts`；补 1 例；gates.md/README 同步；全量 5823 通过（B5） | 无（已收口） |
| **A-20** | **UI 静音时段开关不生效**（前端只写 `user_preferences`，服务端 `_suppression_queue` 读 `config.json`） | ✅ **已修（2026-10-28）** | 新增 `PUT /api/notification/quiet-hours` 写 `notification.quiet_hours_enabled/start/end`；`saveQuietHours()` 同步调该端点；后端 3 例（写三键/关闭/非法时间 400 不落库）；前端四件套绿；全量 5815 passed。提交 `7bde4efb`。**验证范围**：A3 只验了“新端点能写 config”（200/400），**静音生效链路随 N1 在 B2 验**（`/test` 绕过 dispatcher，验不了） | 无（已收口） |
| **A-21** | **按用户静音时段**（A-20 只做了全局配置；`user_preferences.notification_quiet_hours` 仍不参与服务端判定） | 未修（新立项） | `_suppression_queue.is_quiet_hours()` 需要拿到 `user_id` 并读偏好；涉及 dispatcher/queue/manager 与多用户语义 | 触发条件＝出现多用户/按用户静音的产品需求时 |
| **A-22** | **Q7：Windows 端 15 个共享事件是否走托盘（S4 真实验收）** | 挂起 | 需 Windows 端实跑：触发一个共享事件，确认进托盘且 Web 端仍收到；本机/CI 无法覆盖 | 触发条件＝用户有空在 Windows 本机跑一次（5 分钟） |
| **A-23** | **`/api/notification/test` 绕过 `_dispatcher`，无法用于 N1（静音）验收** | ✅ **已修并验证（2026-10-28）** | 新增 `POST /api/notification/test-event`（`_do_send` + `bypass_aggregation=True`，经 `_dispatcher.do_send` 静音判断）；4 例测试；**B2 真实验收通过**：窗口 21:49–21:55，warning `queued=false` 且 21:49:53 success；info `queued=true`、窗口内无 log；21:58:55 补投 success；quiet 已恢复 false | 无（已收口） |
| **A-24** | **B4：企微 `supports_callback` 通知卡片按钮** | ❌ **已取消（2026-10-29 决策）** | 理由：回调只做“已读确认”是伪需求（送达即已读），带动作回调（重试/审批）无真实需求；**回调基础设施保留**（端点/验签/解密/EventKey 解析）并复用于菜单点击事件；未来若出现“通知内直接操作”需求再重评 | 无（取消） |
| **A-27** | **自定义菜单（企微/飞书/Telegram/钉钉）** | 调研中（2026-10-29 立项，当前主线） | 企微 a（3+5）、飞书 b（3+5 或 5+10，仅单聊）、Telegram c（命令列表）、钉钉 d（待补信息）；菜单动作映射、配置存储、静态/动态生成待方案确认；复用回调端点处理菜单 click | 方案确认后开工 |

| **A-25** | **B7：P-06 备份成功误用 `anomaly_alert`** | ✅ **现有日志已可结案（2026-10-29）** | 全量 451 条日志：`anomaly_alert` 共 5 条，全部标题为「自动备份成功」，日期 `2026-10-12`/`2026-10-19`，均 failed；同一标题在 `2026-10-26` 已是 `task_result`（正确映射）⇒ **历史缺陷、当前已修复**。**限制**：API 列表不返回 `notify_event` 字段，以上用 `event_type` + 标题判定；若需精确核对 `notify_event` 需 DB 查询 | 无（已结案） |
| **A-26** | **通知日志按 `end_date` 过滤会排除当日记录** | ✅ **已修并线上验证（2026-10-29）** | `get_logs` 对仅日期输入补 `T00:00:00`/`T23:59:59`；部署 `3f88dfce`/`0e09e030` 后实测 `start=end=2026-10-29` 返回 **53 条**（`0e09e030` 复验 57 条；修复前为 0）；含 1 例单测 | 无（已收口） |
| **A-28** | **通知配置权威源**（合并原 A-28 `enabled` + A-29 `rules`）：`config.json` 与偏好/DB policy 双源，存在“改了不生效” | 待决策 | 三选项：偏好赢 / config 赢 / 分层；迁移+回滚见 `docs/plans/2026-10-29-suspended-items-plan.md` | 用户选原则 |
| **A-30** | **日志 API 不返回 `notify_event`/`task_context`**，A-6/D-14 无法取数 | 未做 | 暴露清单：`notify_event`、`task_context`；隐藏 `callback_data`/`channel_message_ids`/`actions`/`attachments`；补 1 例 | 第一批 |
| **A-31** | **cookiecutter 模板 hook 已过期，真实 CLI 生成失败** | ✅ **已修（2026-10-30）** | 锚点改到 `registry.py`/`__init__.py`；`__init__` 缩进、`_INDUSTRY_FALLBACK` 单行列表格式修正；策略键存在/general 时跳过；删除零调用的懒加载步骤；**沙箱 e2e 通过**：生成 `MyAdapter`、8 例测试全过、diff 仅 3 处注册行 | 无（已收口） |
| **A-32** | **cookiecutter 把 `myadapter.py` 判为二进制**（binaryornot 特征判定；同目录测试/README 正常） | 已兜底 | `post_gen_project.py` 用 `_CONTEXT`（`cookiecutter|tojson`）+ Jinja2 手动渲染；**属绕开行为**，待 cookiecutter/binaryornot 修复后删除该步 | 触发条件＝升级 cookiecutter 时 |
| **A-33** | **`_get_*_adapter()` 懒加载全库零调用**（A-31 调查发现） | 未修 | 保留现有代码不动（超 A-31 范围）；模板已停止生成新 getter；可整体清理 | 触发条件＝下次清理遗留代码时 |

| **A-18** | **历史文档中的短 hash 引用有失效项**（2026-10-27 全量审计） | ✅ **已修（2026-10-28）** | 对账：36（9 无法解析 + 27 not-in-main）→ 剔除 3 日期串与 1 个仅自引用的 `9982141d` → **32**；git 跟踪 6 文件 19 处：**9 处换现行 hash**（映射表见本节下方 A-18 表）、**10 处标「历史提交已不可考」**；`download-pipeline.md` 用统一说明；`docs/.local` 不修（ignored）。复核：跟踪文件中无未标注的失效 hash | 触发条件＝未来再 rebase 或引用新 hash 时 |
| **A-16** | **根目录 `MagicMock/` 目录由测试副作用生成**：全量跑完必现（历史 76 个） | ✅ **已修（2026-10-27）** | 定位（audit hook 监听 `os.mkdir` + 调用栈）到**两处来源**：① `tests/unit/manager/facade/test_scan_handler.py` 两个 `start_watching` 用例把 `MagicMock` 当 `cfg`；② `tests/cli/test_execution.py` 的 `TestMove` 两个 dry-run 用例把 `MagicMock()` 当 `_make_manager`，其返回值的 `cfg.get` 被当路径。**关键机制**：`MagicMock` 动态带 `__fspath__`，被 `os.PathLike.__subclasshook__` 判为 PathLike，`os.path.normpath(mock)` 会得到 `MagicMock\mock.cfg.get()\<id>` ⇒ 必须在 `get_library_root` 只接受 **str**（不能判 PathLike）。修法：守卫 + 两个文件 4 个用例显式给真实路径/`root_paths`。验证：全量跑完 `MagicMock/` **不再生成** | 无（已收口）；新增测试如再把 mock 当路径，守卫会抛 TypeError 而非建目录 |
| **A-15** | **`nrsis` 站点无 HTTPS（已知事实）**：适配器使用 `http://` 与站点现状一致 | ✅ **已确认，无需行动**（2026-10-25） | 2026-10-25 实测 `http://www.nrsis.org.cn/portal/xxcx/std` → 200；`https://...` → ConnectError（443 拒绝）。**站点无 HTTPS**，当前 HTTP 是唯一可用协议，非本项目配置问题。仅在站点启用 HTTPS 时重新评估（届时把适配器 URL 常量同步切换） | 无（已知事实）；站点协议变更时重新评估 |
| **A-13** | **两套 HTTP 栈**：4 个通知渠道用 `urllib.request`，其余 21 个文件用 `requests` | ✅ **已修（2026-10-26；wechat 保留；三渠道真实发送待验证）** | **状态**：telegram（`256ef97e`）——**实现已提交、mock 通过、真实发送已验证**；dingtalk（`f24cae3f`）、feishu（`806f3d3f`）——**实现已提交、mock 通过、真实发送待凭证**。telegram 连通性已于 2026-10-27 在局域网 Docker 实测（登录 → `/api/notification/test`）：ASCII 消息 `{"ok":true}` 送达；但容器运行的是已发布构建 `140ad243`（v0.151.3），**不含本地 requests 改动** ⇒ 该次验证覆盖的是旧 urllib 实现，新代码真实验证需部署新镜像到验证环境，或提供 bot_token 在本地跑一次；`wechat` **保留 urllib**（`proxy_url` 是项目 config 的可选产品能力、当前未配置，代理链路无回归测试，换库收益低于回归风险）。**验证口径**：mock 断言预期结果（非与 urllib 并行对照）——telegram 覆盖 400/401/404/429/500 + 连接重置/超时；dingtalk 覆盖 5xx/业务 `errcode≠0`/网络异常；feishu 覆盖 `code≠0`/HTTP 非 200/令牌失败/网络异常。**mock 只覆盖逻辑层**（URL/请求体/认证/错误映射/重试计数），**传输层差异**（超时语义、编码处理、重定向细节）由真实发送覆盖——这是真实验证不可省的具体理由。回归样本：`test_notification_combo_patch.py`(7) + `test_notification_favorite_chain.py`(11) 为**跨渠道事件链与错误传播**（含 telegram 400 诊断），feishu 迁移后仍绿 ⇒ 事件链未被破坏。测试重复定义全局检查：**0 处**（原 `test_p0_modules.py` F811 已修，曾静默丢失 3 条）。**telegram 真实验证（2026-10-27 21:53）**：局域网 Docker 新镜像（health version=`9db6842c…`，含 A-13/A-17 运行时改动）经 `/api/notification/test` 发两条：① `A13 ASCII test` → `{"ok":true}`；② `A13 (2026-10-27).`（含 `.`/括号）→ `{"ok":true}`。旧构建（`140ad243`）第②条会 `投递失败`，故可判定 A-17 转义修复已生效、requests 迁移可真实发送；**用户已于 2026-10-27 确认收到两条**。注：部署版本 `9db6842c` 比定版 `0d161bd6` 少两个提交（`6abd0027`/`0d161bd6`），二者仅改测试与债务文档，运行时行为一致。

**真实验证执行**：凭证到位后每渠道发 1 条（谁提供凭证谁发），确认收到即把本行状态改为"已验证"；失败则区分代码/环境问题再修 | 无；**真实验证为独立验收项，不阻塞实现** |
| **A-14** | **`docs/architecture/modules/query.md` 适配器清单逐行数据失真**：只列 8/22 个适配器，表内行数为旧快照（`njbz365` 写 385、实测 149） | ✅ **已修（2026-10-25）** | 整表重算为 22 行（类名 AST 提取、站点取 `get_search_url()` 运行时值、行数=非空行），合计 3,256；头表拆分 3,875 = 3,256 + 619（5 个基础设施文件）；重算命令与口径写入文档；顺带修正 `IsoGovAdapter` 站点（旧表 iso.org → 实际 std.samr.gov.cn）。**另记**：`EnergyAdapter`（`114.251.111.103:18080`）与 `NCHAAdapter`（`bz.ncha.gov.cn:9005`）硬编码非标 IP/端口，站点迁移或 IP 变更时需同步更新 | 下次改适配器或复查规模时按文档命令重算 |

### A-18 历史 hash 映射表（2026-10-28）

**对账**：上一轮"9 无法解析（6 hash 类 + 3 日期串）+ 27 not-in-main = 36"
→ 剔除 3 个日期串（`20260820`/`20260725`/`20260724`，非 commit）与 `9982141d`
（只出现在本条清单与 ignored 的 `docs/.local`，不是文档引用）
→ **本轮 5 个 hash 类缺失 + 27 个 not-in-main = 32**；其中 git 跟踪文件 **6 个、19 处**
（**9 可定位** + **10 不可考**）。

| 旧 hash | 现行 hash | subject（稳定，可用于再次定位） |
|---|---|---|
| `1b2c2a1f` | `feef8f6a` | feat(health): 为两类适配器增加独立的每小时健康检查轮询 |
| `518e5b06` | `12dd027a` | fix(api): 修复查询适配器卡片状态永远显示正常的问题 |
| `df182a3d` | `355f62f5` | fix(db): 将 adapter_state 的 INSERT OR REPLACE 改为安全写法 |
| `317f6975` | `38810e99` | fix: 处理主线修复三项次生问题 |
| `d32ccd0b` | `0de89747` | docs: 新增实现摘要、路线图与文档整理审计报告 |
| `b38c5da7` | `8b56d770` | chore(repo): 归档 78 篇过程稿并清理仓库根目录 |
| `f409ab1e` | `0b13563f` | feat(notify): 新增一键处理管道级终局汇总事件 |
| `acf2a7fd` | `3c71e92a` | ﻿fix(tests): eliminate env pollution from guard-state |
| `cfe1bbc4` | `c564a69c` | refactor(status): B1/5 状态字面量收敛 |

**不可考（10）**：`4bc58444`、`6e473096`、`3d16d662`、`1528176b`、`c574ccda`、`70b631b4`、
`d6a56b11`、`f04f1b92`、`f4f812e7`、`f247cf2e`（`git cat-file` 缺失或对象存在但不在 main，且无同 subject 提交）。

**文档处理**：9 处直接换现行 hash，并在 3 个文件末尾注明"映射见 A-18"；
10 处在原处标"（历史提交已不可考，见 A-18）"，`download-pipeline.md` 用一条统一说明代替逐处标注。
**未处理**：`docs/.local/` 内 **13 处**失效引用暂不修（32 − 19 跟踪 = 13；ignored、不随仓库发布）；若未来纳入仓库，需一并处理。

**subject 核对**：9 个映射逐个比对 `git show -s --format=%s` 旧/新，**9/9 一致**（可达且同一提交）。

**宽模式复核（2026-10-28）**：用 `[0-9a-f]{7,40}`（不要求反引号、含范围写法）重扫跟踪文件，又发现 4 类未标注项并修正：① `ROADMAP.md` 的 `409ab1e`（`f409ab1e` 漏首字母）→ 改 `0b13563f`，并修复同行的 `\x07uto_pipeline_summary` 控制字符；② `archive_migration_protocol.md` 的 `cdb6705`/`be50271`（对象存在但不在 main）→ 标不可考；③ `debt/01` 的 32 位大写字串是**文件内容 MD5**，非提交 hash → 已注明；④ `07-impl-design-A.md` 的 `a1b2c3d4e5f60718` 是 JSON 示例占位 → 已注明。复核后跟踪文件 unannotated=0。

## 三、待裁定项（我已给建议，只需你一句话）

| # | 项目 | 我的建议 | 理由 |
|---|---|---|---|
| **D-1** | **T-16：`docs_sync_check.py` 由 `--strict`（告警期）切 `--strict-block`（阻断期）** | ✅ **已切换（2026-10-18）** | CI `ci.yml` 已改 `--strict-block`；实测发现 `CHANGELOG.md` 由 CI 自动生成、不可能同批提交，故该规则改为 `in_repo=False`（只提示）；到期/回滚说明见 `gates.md` v2.10 |
| **D-2** | **N-b / N-e：通知阶段 2 是否先做"前置确认"只读批；附-2 口径澄清由谁完成** | **建议暂不启动** | 阶段 2（`task_progress` 接通知）与阶段 3 补取证均无业务阻塞，且当前无需求方；维持"触发式" |
| **D-3** | **观察项「主题判定改为事件键优先、关键词兜底」** | **建议保持待排期** | 属设计改进而非缺陷；现有 i18n 契约表兜底已被 `tests/test_notification_aggregator_topic_i18n.py` 锁定 |

## 四、本次（2026-10-16）由我直接裁定关闭的项

| 项目 | 裁定 | 依据 |
|---|---|---|
| 原 §六「**风格项：台账历史条目判断词清理**」（『建议』7 处 /『不必』2 处） | **不处理** | 历史条目是"当时原话"的留痕，改写措辞会削弱可追溯性；且实测该计数（含本条 8/3、本条自身 1/1）与文档自述**精确一致**，不构成缺陷 |
| 原 §六「**R14-5 记载的"状态汇总表"**」 | **确认从未存在** ⇒ 已由主档的「四类状态汇总」替代 | `git log -S "状态汇总表"` 仅 `db71496a`（2026-10-01T13:46:30+08:00）1 次，且只出现在记录文本里，从未作为表存在 |
| 原 §六「**平台侧告警行复核方法写"24 warning"**」 | **更正为 0 warning / 9 notice** | 逐作业拉 check-run annotations：`ef469672`（2026-10-07T14:10:34Z 触发）与 `bc490c28`（2026-10-16T13:40:07Z）均 `warning=0 / notice=9 / failure=0`；24 条是升级前的旧数 |
| 原 §六「**`.doc`（OLE2）行现状写"静默解析为空"**」 | **更正为"已显式告警"** | `pilotstd/announcement/_attachment_parser.py:104-106` 现为 `logger.warning("附件正文解析失败（若为 .doc/OLE2 则正文为空）…")`，改动于 `a0204e3f` **2026-10-01T16:54:08+08:00** |
| 原 §六「**T-38 行写"G-032 现报 8 处"及行号 539/540/577**」 | **更正为 10 处，且原行号已失效** | 实测 `python scripts/check_g_032_doc_health.py` 报 **10 处**；原所指引用已不存在（详见 [04-watch.md](04-watch.md) T-38 行） |
| 原 §六「**`tests/` 受控测试行②"流程补强（未实施）"**」 | **更正为"已由 R16 P0 落地"** | `scripts/check_all.sh:427` 定义 `run_gate_selftests`，`:465`/`:472` 调用 |
| 「**隐式依赖 `cryptography` 未显式声明**」（我于 2026-10-17 曾登记为 A-7） | **撤回该条目**（不成立，不是债） | 我上一轮**漏查**：只 grep 了 `pyproject.toml` 与 `docker/requirements-docker.txt`，而那条"逐文件检查"命令因 PowerShell 语法错误**静默失败**，我据此误判"四个依赖文件均无声明"。实测 `requirements.txt:6` = `cryptography>=48.0.1`（段注释"敏感数据加密"）⇒ **本就是显式依赖**。教训：命令失败时不得依据其输出下结论（R-004 实证优先） |
