# 项目结构化知识日志

> 本文档由 Knowledge Trigger 机制自动维护，CI pre-push hook 检查最后更新时间。
> 与 `~/.claude/projects/` 下的 Auto-Memory 相互独立——前者用于团队审计与 CI 检查，后者是 Claude 会话上下文缓存。

---

## Memory 条目模板

所有 Memory 条目使用以下格式：

### [日期] [类别] [标题]
- **类型**：决策 / 范式 / 放弃 / 规范 / 风险
- **内容**：（1-3句话描述核心事实或决策）
- **关联代码**：涉及的文件路径或模块
- **关联文档**：相关的 spec/plan/reference
- **有效期**：永久 / 至YYYY-MM-DD / 条件解除时

---

## 条目列表

### 2026-07-24 范式 五站Playwright侦查方法论
- **类型**：范式
- **内容**：JSL绕过 + XHR捕获范式，适用于剩余站点统一侦查分类
- **关联代码**：playwright_scout/*.py
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久

### 2026-07-24 决策 ADAPTER_TYPE_MAP作为适配器唯一真实来源
- **类型**：决策
- **内容**：消除 _ALL_ADAPTER_NAMES/target_names/前端fullName() 三处硬编码，改为从ADAPTER_TYPE_MAP动态派生 + 适配器模块DISPLAY_NAME自描述
- **关联代码**：docker/api/adapter.py, web/.../AdapterStatusQueryCard.vue, 21个适配器模块
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久

### 2026-07-24 放弃 NHC卫健委WAF阻断
- **类型**：放弃
- **内容**：nhc.gov.cn 站点WAF（Cloudflare + 5秒盾 + 验证码）不可绕过，经多轮测试确认放弃
- **关联代码**：playwright_scout/nhc_scout.py（如有）
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久（除非NHC更换WAF策略）

### 2026-07-24 规范 DISPLAY_NAME常量规范
- **类型**：规范
- **内容**：21个适配器模块均定义DISPLAY_NAME常量（≤50字符），API自动暴露display_name字段
- **关联代码**：21个适配器模块, docker/api/adapter.py
- **关联文档**：docs/superpowers/specs/2026-07-24-adapter-batch-q22-q23-summary.md
- **有效期**：永久

### 2026-07-25 决策 三位一体体系加固
- **类型**：决策
- **内容**：引入 Inline 指令分级、.test_pass 自动化（含 commit_hash 锚点）、Knowledge Trigger 结构化知识日志、进度日志半自动化四项机制
- **关联代码**：CLAUDE.md, tests/conftest.py, scripts/gen_daily_log.py, .claude/memory.md
- **关联文档**：docs/superpowers/specs/2026-07-25-sysfix-trinity-hardening-spec-lite.md
- **有效期**：永久

### 2026-07-25 风险 Mypy 预存类型错误待清理
- **类型**：风险
- **内容**：项目中存在 99 个预存 Mypy 类型错误，分布在 13 个未修改文件中，非 SYSFIX-20260725-001 引入，需独立排期清理
- **关联代码**：涉及 13 个文件（详见 mypy 输出）
- **关联文档**：无
- **有效期**：至清理完成时

### 2026-07-25 经验 KeyError导致的skip隐蔽性
- **类型**：经验
- **内容**：当被测模块在导入或setUp阶段因KeyError崩溃时，pytest将用例归类为skip/error而非fail，且不在失败报告中显式列出。修复此类KeyError后pass增量可能大于原fail数量。验收时若skip下降且grep确认无标记改动，应优先判定为依赖链恢复的良性效应
- **关联代码**：CI-FIX-20260725-002（expire→organize 桶重命名导致的连锁KeyError）
- **关联文档**：无
- **有效期**：永久

### 2026-07-25 经验 xfail时效性与僵尸标记
- **类型**：经验
- **内容**：xfail 标记若在批量修复期间作为临时止血措施添加，其失效条件与原始修复强绑定。后续修复覆盖根因后必须同步清理，否则成为"僵尸标记"掩盖已恢复的测试覆盖。任何 xfail 都应附带"解除条件"注释，或在修复指令中列为必查项
- **关联代码**：CI-FIX-20260725-003 修复项3（test_pipeline_router.py xfail 移除）
- **关联文档**：无
- **有效期**：永久

### 2026-07-25 范式 Skip批量消除的分组验证策略
- **类型**：范式
- **内容**：>10 个同类 skip 的批量修复必须按根因分组、逐组修复+逐组验证，避免批量修改后的交叉污染和定位困难。58 个通知测试按 3 种根因分组验证，验证了该策略的有效性
- **关联代码**：CI-FIX-20260725-003 修复项1（test_notification_e2e.py 58 skip→0）
- **关联文档**：无
- **有效期**：永久

### 2026-07-25 规范 CI质量基线门禁
- **类型**：规范
- **内容**：自 2026-07-25 提交 `87e8737e` 起，所有新 PR 必须满足 Failed=0、Skipped≤6（仅限6个已确认外部依赖）、xfail=0、Passed≥2369。任何回退需附书面说明。批量 skip/xfail 复燃时引用 CI-FIX-003 的分组验证策略和 xfail 时效性原则
- **关联代码**：CI-FIX-20260725-001/002/003 全部改动
- **关联文档**：无
- **有效期**：永久（后续提交可上调 Passed 阈值，其余三项不可放宽）

### 2026-08-17 范式 三级漏斗路由引擎v2.0
- **类型**：范式
- **内容**：查询类型三分支（国内标准号/国际标准号/纯关键词）+ L1精准匹配→L2综合兜底→L3探索层，替代 scorer 扁平评分。L1只做国内精准（assert not is_international），L2按 is_international 一致性区分国内/国际，L3纯关键词探索
- **关联代码**：pilotstd/query/routing/router_v2.py
- **关联文档**：docs/design/site_classification_v1.md
- **有效期**：永久

### 2026-08-17 决策 gongbiaoku数据源限制与mee修正
- **类型**：决策
- **内容**：gongbiaoku 根因类型B（后端无ISO/IEC数据，模糊匹配兜底返回无关国标），search_reliability=medium；mee.supported_types 从 v1.0 的 [HJ,GB] 修正为 [HJ]，GB 是国标查询误路由到 mee 的根因
- **关联代码**：config/site_capabilities.yaml
- **关联文档**：docs/analysis/gongbiaoku_search_audit.md
- **有效期**：永久

### 2026-08-17 决策 灰度开关与正则兼容代号
- **类型**：决策
- **内容**：ROUTING_ENGINE_VERSION 环境变量控制 v1/v2 切换（默认v1）；IntentParser 正则从 (?=\s*\d) 放宽为 {2,6}，因批量路径传入纯代号（GB/T/ISO）无法被原正则识别，会误判为关键词走L3
- **关联代码**：pilotstd/query/engine/_single.py, _routing.py, _mini_bucket.py
- **关联文档**：docs/analysis/v1_vs_v2_routing_comparison.md
- **有效期**：永久（v1 清理后灰度开关可移除）

### 2026-08-17 风险 能力模型数据缺口导致排序退化
- **类型**：风险
- **内容**：20个站点 search_reliability=unknown、全部 historical_hit_rate=0.0，导致 L2/L3 按 reliability、L1 按 hit_rate 排序退化为 YAML 原始顺序。需后续回填 search_reliability 及 per-site 命中数据
- **关联代码**：docs/issues/router_v2_feedback.md
- **关联文档**：docs/issues/router_v2_feedback.md
- **有效期**：至数据回填完成时

### 2026-08-20 范式 CI离线网络硬阻断三层防护
- **类型**：范式
- **内容**：禁止测试真实出网的标准做法：① iptables 自定义链只放行回环/ESTABLISHED/DNS，其余 `-j REJECT --reject-with tcp-reset`（链末必须 REJECT/DROP 终结，跳空链=没阻断）；② 阻断后立即跑 `scripts/check_ci_offline.py` fail-fast；③ conftest 兜底 patch socket 拦截非 localhost connect。阻断必须只包住 pytest 一步，`if: always()` 恢复网络，否则误伤后续 vulture/artifact 等外网步骤
- **关联代码**：.github/workflows/ci.yml, scripts/check_ci_offline.py, tests/conftest.py
- **关联文档**：docs/ci-lessons.md §六
- **有效期**：永久

### 2026-08-20 决策 通知配置数据库权威化（DB 优先，config.json 兜底）
- **类型**：决策
- **内容**：notification.enabled 用户级配置改为 user_preferences 表优先（NotificationManager.__init__ 启动时读 DB 覆盖 config.json；PUT /api/notification/config 双写 DB+config.json；ConfigManager 新增 reload()）。长期目标是将 config.json 用户级配置逐步迁移到数据库。公告分类统计统一口径 COUNT(DISTINCT announce_no)+COUNT(*)，废弃 SUM(standard_count)（N² 膨胀）
- **关联代码**：pilotstd/core/notification/manager.py, pilotstd/core/config/manager.py, docker/api/notification.py, pilotstd/announce/crawler_service.py
- **关联文档**：docs/superpowers/specs/2026-08-19-announce-notification-chain-fix-spec-lite.md
- **有效期**：永久

### 2026-08-20 决策 恢复三个公告死事件（对齐重构前行为）
- **类型**：决策
- **内容**：重构 994ba7fb 后 announcement_fetch_complete/failed/announce_fetch_summary 失去调用点。已恢复：全站失败→announcement_fetch_failed（bypass 实时），有适配器明细→announce_fetch_summary（bypass 实时），手动路径→announcement_fetch_complete；send_event 新增可选 bypass_aggregation 参数（跳过聚合缓冲实时发送）。e2e test_trigger_exists 由正则（EVENT_[A-Z_]+ 模糊匹配伪通过）改为 AST 精确匹配（字面量+events 常量解析）
- **关联代码**：pilotstd/announce/notifier.py, pilotstd/core/notification/manager.py, docker/api/announce.py, tests/test_notification_e2e.py
- **关联文档**：docs/superpowers/specs/2026-08-19-announce-notification-chain-fix-spec-lite.md
- **有效期**：永久

### 2026-08-20 决策 DB 地方标准逻辑代号剥离顺序号（修复归档命名重复）
- **类型**：决策
- **内容**：`_exact_match_db` 原将顺序号编入 logical_code（DB 22/T2883），归档命名时又拼 number 导致 `DB 22T2883 2883-2018` 顺序号重复、且安全文件名（无 /）无法被 parser 再解析。修复：logical_code 仅代号（DB 22/T、DB 50），顺序号独立存 number；`scripts/migrate_unknown_industry.py` 的 recover_logical_code 同步对 DB 结果剥离顺序号。file_index 存量 DB 行已批量 UPDATE 为纯代号。注意：归档安全文件名（DB 22T 2883-2018）仍无法被 parser 直接再解析（DB 正则要求 /T 形态），属已知遗留
- **关联代码**：pilotstd/scan/parser/_exact_matcher.py, pilotstd/scan/parser/_text_cleaner.py, scripts/migrate_unknown_industry.py
- **关联文档**：tests/test_parser.py, tests/test_migrate_unknown_industry.py, tests/stress_selfcheck.py
- **有效期**：永久

### 2026-08-20 范式 合订本残片文件名识别（无～符号）
- **类型**：范式
- **内容**：合订本范围（47008～47010-2010）被误转录为 `47008-1947 010-2010` 形态（编号-假年份 空格 残片-真实年份）时，原有 ～ 截断规则不触发导致年份解析错误（如 1947）。TextCleaner 新增 `_COMBINED_STD_RE` 模式：`(\d{2,5})-(\d{4})\s+(\d{2,5})-(\d{4})` → 取起始编号 + 最后年份，并追加"合订本"标识到 std_name，避免被当作普通单标准
- **关联代码**：pilotstd/scan/parser/_text_cleaner.py
- **关联文档**：tests/test_parser.py::test_combined_standard_without_tilde
- **有效期**：永久

### 2026-08-20 决策 DB 逻辑代号统一无空格（DB22/T）+ 团体标准 T/ 通道
- **类型**：决策
- **内容**：① DB 逻辑代号统一为无空格 `DB22/T`/`DB50`（`_exact_match_db` 输出 f"DB{code}/..."），归档安全名 `DB22T 2883-2018` 才能被 normalize_std_filename 缺斜杠还原（已扩展允许 `DB 22T` 旧形态带空格）→ 扫描→归档→再扫描自洽。file_index 存量 DB 行需 `UPDATE ... SET logical_code=REPLACE(logical_code,'DB ','DB')`。② 新增 `_exact_match_group` 团体标准通道（T/XXX 与无斜杠 TXXX），白名单 `pilotstd/constants/group_std_orgs.py` 空集合透传；无斜杠分支用 code_mapping 防误伤（TSG 等已知代号不被当 T/SG）。③ 已知遗留：公告匹配 `_parse_std_code` 用 parse_std_number 的 code 字段（无斜杠 SHT/DB22T）与 file_index 带斜杠存储不一致，精确等值 SQL 下不兼容，预存问题未修
- **关联代码**：pilotstd/scan/parser/_exact_matcher.py, pilotstd/scan/parser/__init__.py, pilotstd/core/file_utils.py, pilotstd/constants/group_std_orgs.py, scripts/migrate_unknown_industry.py
- **关联文档**：tests/test_parser_roundtrip.py（Round-trip：make_standard_filename→parse 往返一致）
- **有效期**：永久

### 2026-08-20 决策 鉴权 401 与业务 401 响应体判别机制（_isAuthExpired401）
- **类型**：决策
- **内容**：收藏接口 401 根因是 favorites.py 把 get_current_user_id 返回的 user_id 当 username 查表（`WHERE username = ?`），SQLite 永远查不到 → 路由内抛 401"用户不存在"（非中间件鉴权失败）。前端 http.ts 新增 `_isAuthExpired401`：响应体含 `error` 字段或 `detail` 含"未登录/认证失败/会话已过期"→ 判定鉴权 401（清状态+跳登录页）；其余 401（如"用户不存在"）为业务级，不跳转、不弹窗，由业务层展示 detail。配套：断网（ERR_NETWORK）/超时（ECONNABORTED/ETIMEDOUT）由全局拦截器统一提示"网络连接异常/请求超时"（setNetworkErrorNotifier + bootstrap 经 $toast 注入），组件 catch 不重复弹窗；announce.ts 收藏 3 接口移除冗余 skipGlobalAuthRedirect
- **关联代码**：web/src/api/http.ts, web/src/bootstrap/registerHttpHandlers.ts, web/src/composables/useFavorite.ts
- **关联文档**：tests/test_api_favorites_auth.py（反向复现原 401）、web/src/api/__tests__/http.test.ts
- **有效期**：永久

### 2026-08-20 决策 user_id/username 误用根因及同类隐患关联
- **类型**：决策
- **内容**：收藏 401 后端根因：get_current_user_id 返回 user_id（int，JWT sub），favorites.py `_get_user_id` 却按 username 列查询 → 修复为 `WHERE id = ?` 并按主键校验，5 个接口依赖参数同步改名 user_id。**同类隐患**：docker/api/notification.py:28 把 user_id 传给按 username 查询的 get_user_id，查不到时兜底返回 1（多用户场景全部解析为用户 1），已登记 technical-debt.md #9，下次迭代修复。教训：禁止把 get_current_user_id 返回值传给形参名为 username 或按 username 查询的函数（auth.py docstring 已有警示，favorites 是未跟进案例）；另登记 #10：test_api_snapshot.py 模块级 env setdefault 污染 test_docker_auth.py（CI 靠 xdist 规避，本地串行失败）
- **关联代码**：docker/api/favorites.py, docker/api/notification.py, tests/test_api_snapshot.py
- **关联文档**：docs/technical-debt.md（#9/#10）
- **有效期**：永久

### 2026-08-20 决策 Mypy Optional 收敛 + 测试 Fernet 隔离姿势
- **类型**：决策
- **内容**：① **Mypy Optional 收敛模式**：辅助校验函数避免返回 Optional 后在调用点赋值给 int 变量（触发 `Incompatible types in assignment`）——改为函数内部直接 `raise HTTPException(401)`、返回非空 int，调用点免判空（favorites.py `_get_user_id` 5 处调用点据此收敛）。② **放弃"删除真实开发库"方案**：Fernet 防呆测试原方案为删除 `get_db_path()` 残留库，实测 Windows 文件锁下 `os.remove` 失败被吞、真实库含旧密文 → 防呆 RuntimeError 依旧触发，且直接删用户数据有风险；改用 `monkeypatch.setattr("pilotstd.core.config.paths.get_db_path", ...)` 重定向到临时空库走"全新安装"分支（与 test_core_config.py 同模式），零副作用。③ 测试 SQL 与迁移链同步：G-012 Schema 检查按迁移链构建真实结构，测试文件 CREATE TABLE 必须完整复制迁移语句（含默认值/约束），勿手写精简列（会漏 NOT NULL/默认值）
- **关联代码**：docker/api/favorites.py, tests/gui/test_auto_pipeline.py, tests/test_api_favorites_auth.py, tests/test_core_config.py
- **关联文档**：pilotstd/core/db/_migrate_v2_v15.py（announcement_record）、_migrate_v37_plus.py（user_credentials）
- **有效期**：永久

### 2026-08-20 决策 登录页背景图请求解耦：最小字段公开接口 + setup 提前加载
- **类型**：决策
- **内容**：登录页背景图原通过 admin-only 的 GET /api/settings 获取 URL（未登录 401 / 非 admin 403），导致背景图请求延迟到登录后甚至缺失。修复：新增公开接口 GET /api/login-background（AUTH_WHITELIST 放行，仅暴露 appearance.login_bg 单字段，测试断言响应不含其他配置字段）；前端 LoginView 在 `<script setup>` 顶层（早于 onMounted）发起两阶段加载：fetch URL → `new Image()` 预加载 → onload 后才写 bgUrl 应用 CSS background-image；`/login` 路由静态化取消懒加载；API/图片失败或 `file://` 桌面端遗留值 → 默认渐变降级 + console.warn。范式：**公开页面所需的展示配置必须走最小字段公开接口，禁止复用管理员级配置接口，也禁止把管理接口重新加白名单（SEC-001 教训）**
- **关联代码**：docker/api/upload.py, docker/auth.py, web/src/views/LoginView.vue, web/src/router.ts, tests/test_login_background_api.py, web/src/views/LoginView.test.ts
- **关联文档**：docs/superpowers/specs/2026-08-20-login-background-eager-load-spec-lite.md
- **有效期**：永久

### 2026-08-20 教训 测试隔离 fixture 与依赖真实 DB 数据的端点测试冲突
- **类型**：风险
- **内容**：conftest autouse fixture `_isolate_fernet_db` 将 get_db_path 重定向到空临时库后，test_docker_api.py::test_change_password_returns_ok 暴露既有缺陷：路由内 `get_user_by_id(1)` 未 mock、走真实 DB，临时库无种子用户 → 命中"用户不存在"400。修复：API 端点测试必须 mock 全部 DB 协作函数（`docker.api.users.get_user_by_id` 等），不得隐式依赖真实库数据（含 `test_change_password_short_returns_400`——原在旧库下"碰巧通过"，隔离后以错误原因通过，已一并修正为断言真实意图）。教训：**端点单元测试的协作函数一律 mock，禁止依赖 DB 种子数据**
- **关联代码**：tests/test_docker_api.py, tests/conftest.py（_isolate_fernet_db）, docker/api/users.py
- **关联文档**：CHANGELOG.md
- **有效期**：永久
