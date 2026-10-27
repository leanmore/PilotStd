# 技术债 · 可修复、尚未修复

> 本文件是 `docs/technical-debt.md` 四分类之一：**未修**（正式债 + 可动作项 + 待裁定项）。
> 判据：**有明确动作可做**、且尚未做完。做完即移入 [01-archive-closed.md](01-archive-closed.md)；
> 定性为"不做/不划算"则移入 [02-accepted.md](02-accepted.md)；修完但需盯一段时间则进 [04-watch.md](04-watch.md)。
> **最后核实：2026-10-16**（每条都注明核实方式与时间戳）。
> 回主档：[technical-debt.md](../technical-debt.md)

---

## 一、正式存续债（3 条）

| # | 项目 | 状态 | 现状（实测） | 下一步动作 | 触发条件 |
|---|---|---|---|---|---|
| **T-40** | V6 wechat 真发未取证 | `观察中`（用户 2026-10-17 裁定：**后续再说**） | 本地 `data/config.json` 的 `notification.channels.wechat` = `{"enabled": true, "webhook_url": ""}`（2026-10-16T22:07 实测）⇒ 非部署环境无法真发；渠道契约/错误映射/签名/i18n 单测已覆盖 | 部署环境补一次真发取证（会真的发一条消息到企微） | 用户择期（本轮不做） |
| **T-42** | 渠道调用频率限制未逐家实现 | `基座已具备`（2026-10-17） | 实测（2026-10-16）：限流/退避**只长在 telegram**（27 处命中），`dingtalk` 1、`feishu` 1、`wechat` 4、`base.py` **0** ⇒ 一次 429/抖动只有 telegram 退避重试，其余三家当场丢通知。**2026-10-17 已修**：重试/退避提升为渠道基座 `base._with_retry`（统一 3 次、退避 (2,4)、服务端 `retry after` 优先且截顶 60s、429/5xx 与限流关键词兜底、错误 120s 去重），**四家渠道全部接入**（提交 `191b7259`，2026-10-17T06:19:36+08:00；测试 195 passed） | **残留**：各渠道限流的**具体错误码未逐家取证**（钉钉官方文档 JS 渲染取不到正文；飞书/企微未逐码核对）⇒ 现用 `looks_rate_limited` 关键词兜底，取证到 `errcode`/`code` 后改为**按码判定** | 取到任一家官方限流码时 |
| **T-43** | 企微回调（XML+MsgSignature+AES）未实现 | `已实现·待取证`（2026-10-17 更新） | 原 `pilotstd/core/notification/callback.py` 对 wechat 一律 501（注释自述"能力调查缺口未取证"）。**已由 `bc3b4822` 落地**：`wechat_crypto.py`（SHA1 验签 + AES-256-CBC 解密，常量时间比较）、`callback.py`/`callback_service.py` 企微分支并入既有幂等/授权出口、`docker/api/notification_callback.py` 的 GET 回明文 `echostr`、POST 回明文 `success`（原 501）；测试三组 **56 例**（crypto 28 / 服务 16 / 端点 12） | **残留取证**：部署后取一次真实回调报文，确认 `EventKey`/`TaskId`/`FromUserName` 字段假设；`WechatChannel.capabilities().supports_callback` 仍为 `False`（语义是"我方下发消息带可回调按钮"，需前端联动，单独立批） | 部署环境收到首条企微回调时 |

## 二、可动作项（有明确动作，按"值不值得现在做"排序）

| # | 项目 | 状态 | 现在能做什么 | 触发条件 / 备注 |
|---|---|---|---|---|
| **A-1** | **P7-12：`docker/api/tasks.py:138` 越过 DAO 直调私有 `mgr.task_queue._persist(task)`** | ✅ **已修（2026-10-18）** | `TaskQueue.persist()` 公共入口已加，`docker/api/tasks.py` 改调用它；测试断言 `persist` 被调且 `_persist` 不再被 API 触碰 | **无前置条件，可随时做**（`docs/plans/notification-redesign/10-阶段2投影入口调查.md:72` 明写"不得因 P4b 收尾而勾销"） |
| **A-2** | **G-049 防膨胀门禁只覆盖 `manager.py`**（`scripts/check_g_049_manager_size.py:18` 的 `TARGET`） | ✅ **已修（2026-10-18）** | `TARGETS` 扩展为 manager.py + 6 个通知热点文件，上限=当前有效行+约 5% 余量；`*_data.py` 静态规格表不纳入（避免每加渠道就红）。测试 `tests/test_check_g_049_notification_sizes.py`（3 例） | 触发条件＝通知模块再出现单文件膨胀 |
| **A-3** | **`channel_spec.schema ↔ get_config_schema()` 互证门禁缺失**（现只有字段级断言 `tests/test_channel_spec.py:72-119`） | 未修（可选） | 加一条"声明 ↔ 实现"一致性门禁 | 触发条件＝渠道字段再次漂移 |
| **A-5** | **cookiecutter 真实 CLI 端到端未入 CI** | 观察 | 模板改动涉及 hooks 时补一条真实 CLI 用例（渲染/编译/零字面量已由 jinja2 用例覆盖） | 触发条件＝hooks 变更或脚手架被频繁使用 |
| **A-6** | **`known-issues.md` 第 4 项：Telegram 429 的 55.6% 未复测** | 观察 | 部署后取 `GET /api/notification/logs` 的 success/failed 分布 + 容器日志 429 计数，给出改善证据 | 触发条件＝下次通知量统计复核 |
| **A-9** | **解析失败日志格式未统一**（`pilotstd/scan/parser/__init__.py:200` 的 `TODO(P2)`） | 未修 | 统一为"路径/类型/错误/详情"四段，牵动日志断言测试，需单独一批 | 触发条件＝下次动解析器日志或排障困难 |
| **A-10** | **设置页 Tab 定位依赖 DOM 顺序**（`web/src/views/settings/constants.ts:4` 的 `TODO(P2-FOLLOWUP)`） | 未修 | 改为 `data-tab` 名称定位，消除对子元素顺序的依赖 | 触发条件＝设置页 Tab 结构再调整 |
| **A-11** | **两条自定义 eslint 规则"已定义但未执行"**（`web/eslint.config.js` 把 `custom/no-raw-i18n-key`、`custom/no-sensitive-persist` 设为 error，但 package.json 无 lint 脚本、CI 无 eslint 步骤） | ✅ **已修（2026-10-25）** | `package.json` 新增 `lint: eslint src`；CI `test-frontend` 在 type-check 后执行 `pnpm run lint`。前置的 56 条 `no-raw-i18n-key` 命中经核查**全为误报**（存键定义，消费处 `t()`），已通过规则重构清零（`96f04c40`，7 个 RuleTester 用例）；`no-sensitive-persist` 仍为 0 命中。当前 `eslint src` = 0 errors / 281 warnings。**保留的"调用参数对象"报告形态当前生产命中 0 条**（是预防未来新增，不是"还有已知违规未处理"）；`npm/pnpm test` 自 2026-06-17 初始提交即在（42 个 `.test.ts`），A3/A4 曾漏跑、已补并写入 AGENTS §十 | 无（已收口）；后续新增违规由 CI 阻断 |
| **A-12** | **6 个适配器的 `_search` 无直接测试**（`ccsn`/`sppt`/`sppt_local`/`jtst`/`mee`/`nrsis`；`tests/` 中 grep 零命中） | ✅ **已修（2026-10-25）** | `test_adapter_search_delegation.py` 覆盖 6 类委托与边界；`test_query_standards.py` 覆盖 6 个适配器的正常 + 非 200 + 传输异常 + 解析层空结果（23 用例，respx/responses 按测试隔离），**并断言实际发出的 method/path/query（POST 含 body）**。历史口径：A-12a（`b44cd533`）的 mock 为 `url__regex=".*"`，只验证了解析层对 fixture 的处理，**请求构造层未被验证**；该缺口在合并版（`c262900c`）收紧 mock 后才覆盖。**遗留观察**：`nrsis` 走 `http://`（`http://www.nrsis.org.cn/portal/xxcx/std`），2026-10-25 实测 HTTP 200、HTTPS 443 拒绝 ⇒ 站点本身无 HTTPS，适配器与站点一致，非明文降级缺陷 | 触发条件＝站点协议变更或新增适配器时 |
| **A-18** | **历史文档中的短 hash 引用有失效项**（2026-10-27 全量审计）：`docs/` 65 个文件、234 个 hash；**9 个无法解析**（含日期串如 `20260820` 与真缺失如 `6e473096`）、**27 个不在 main 历史**（集中在 ADR-013、`archive/项目进度日志.md`、`debt/01-archive-closed.md`、`testing/下载适配器测试方案.md`） | 未修（历史层） | 本轮 6 份重点文档（DECISIONS/PITFALLS/debt/03/core.md/digest/AGENTS）18 个 hash 全部有效；失效项属**更早的历史重写**遗留，不影响当前决策/踩坑记录。修法：逐条对照 `git log --all` 找等价提交改短 hash，找不到的标注"历史提交已不可考"；或统一改为描述性引用（版本/日期）不再引用 hash | 触发条件＝再整理历史文档或有人按 hash 追溯时 |
| **A-16** | **根目录 `MagicMock/` 目录由测试副作用生成**：全量跑完必现（历史 76 个） | ✅ **已修（2026-10-27）** | 定位（audit hook 监听 `os.mkdir` + 调用栈）到**两处来源**：① `tests/unit/manager/facade/test_scan_handler.py` 两个 `start_watching` 用例把 `MagicMock` 当 `cfg`；② `tests/cli/test_execution.py` 的 `TestMove` 两个 dry-run 用例把 `MagicMock()` 当 `_make_manager`，其返回值的 `cfg.get` 被当路径。**关键机制**：`MagicMock` 动态带 `__fspath__`，被 `os.PathLike.__subclasshook__` 判为 PathLike，`os.path.normpath(mock)` 会得到 `MagicMock\mock.cfg.get()\<id>` ⇒ 必须在 `get_library_root` 只接受 **str**（不能判 PathLike）。修法：守卫 + 两个文件 4 个用例显式给真实路径/`root_paths`。验证：全量跑完 `MagicMock/` **不再生成** | 无（已收口）；新增测试如再把 mock 当路径，守卫会抛 TypeError 而非建目录 |
| **A-15** | **`nrsis` 站点无 HTTPS（已知事实）**：适配器使用 `http://` 与站点现状一致 | ✅ **已确认，无需行动**（2026-10-25） | 2026-10-25 实测 `http://www.nrsis.org.cn/portal/xxcx/std` → 200；`https://...` → ConnectError（443 拒绝）。**站点无 HTTPS**，当前 HTTP 是唯一可用协议，非本项目配置问题。仅在站点启用 HTTPS 时重新评估（届时把适配器 URL 常量同步切换） | 无（已知事实）；站点协议变更时重新评估 |
| **A-13** | **两套 HTTP 栈**：4 个通知渠道用 `urllib.request`，其余 21 个文件用 `requests` | ✅ **已修（2026-10-26；wechat 保留；三渠道真实发送待验证）** | **状态**：telegram（`256ef97e`）、dingtalk（`f24cae3f`）、feishu（`806f3d3f`）——**实现已提交、mock 通过、真实发送待验证**。telegram 连通性已于 2026-10-27 在局域网 Docker 实测（登录 → `/api/notification/test`）：ASCII 消息 `{"ok":true}` 送达；但容器运行的是已发布构建 `140ad243`（v0.151.3），**不含本地 requests 改动** ⇒ 该次验证覆盖的是旧 urllib 实现，新代码真实验证需部署新镜像到验证环境，或提供 bot_token 在本地跑一次；`wechat` **保留 urllib**（`proxy_url` 是项目 config 的可选产品能力、当前未配置，代理链路无回归测试，换库收益低于回归风险）。**验证口径**：mock 断言预期结果（非与 urllib 并行对照）——telegram 覆盖 400/401/404/429/500 + 连接重置/超时；dingtalk 覆盖 5xx/业务 `errcode≠0`/网络异常；feishu 覆盖 `code≠0`/HTTP 非 200/令牌失败/网络异常。**mock 只覆盖逻辑层**（URL/请求体/认证/错误映射/重试计数），**传输层差异**（超时语义、编码处理、重定向细节）由真实发送覆盖——这是真实验证不可省的具体理由。回归样本：`test_notification_combo_patch.py`(7) + `test_notification_favorite_chain.py`(11) 为**跨渠道事件链与错误传播**（含 telegram 400 诊断），feishu 迁移后仍绿 ⇒ 事件链未被破坏。测试重复定义全局检查：**0 处**（原 `test_p0_modules.py` F811 已修，曾静默丢失 3 条）。**真实验证执行**：凭证到位后每渠道发 1 条（谁提供凭证谁发），确认收到即把本行状态改为"已验证"；失败则区分代码/环境问题再修 | 无；**真实验证为独立验收项，不阻塞实现** |
| **A-14** | **`docs/architecture/modules/query.md` 适配器清单逐行数据失真**：只列 8/22 个适配器，表内行数为旧快照（`njbz365` 写 385、实测 149） | ✅ **已修（2026-10-25）** | 整表重算为 22 行（类名 AST 提取、站点取 `get_search_url()` 运行时值、行数=非空行），合计 3,256；头表拆分 3,875 = 3,256 + 619（5 个基础设施文件）；重算命令与口径写入文档；顺带修正 `IsoGovAdapter` 站点（旧表 iso.org → 实际 std.samr.gov.cn）。**另记**：`EnergyAdapter`（`114.251.111.103:18080`）与 `NCHAAdapter`（`bz.ncha.gov.cn:9005`）硬编码非标 IP/端口，站点迁移或 IP 变更时需同步更新 | 下次改适配器或复查规模时按文档命令重算 |

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
