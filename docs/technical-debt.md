# 技术债登记

> 版本：v1.25.0
> 更新日期：2026-09-27
> 2026-09-27 **第十二轮 R12-4a：T-32 关闭（L1 触发式纳入 .pyi/.pyw）+ R4 探针工作流立项**。**T-32 修复**：`scripts/check_all.sh` 的 L1 触发式 `^scripts/|`+`\.py$` → **`^scripts/|\.py[wi]?$`**（并同步 WARN/日志文案与注释）；**受控验证**：暂存 `pilotstd/_t32_probe.pyi`（142 字符行）→ L1 **如期触发**并 `❌ [FAIL] L1 ruff check`（`E501 Line too long (142 > 120)`，EXIT=1），而修复前同一探针可正常提交（见 7.18）→ **T-32 ✅ CLOSED**，由「六、观察项」移入「一、已清理」。**R4 立项**：新增独立工作流 `.github/workflows/gui-race-probe.yml`（`workflow_dispatch` 专用，不与 ci.yml 常态流水线混跑）——在 **windows-latest + Python 3.12 + PyQt6==6.11.2**（与 `test-gui-unit` 同口径）下循环跑 `tests/gui/test_event_bus_integration.py`，用于取得 #34 的实证：**修复前捕获 access violation／修复后证明 N 次 0 崩溃**。**R2 代码（静止协议）在本批工作区已完成、随 R12-4b 提交**，故本批先以“修复前”状态派发探针取基线。
> 2026-09-27 **第十二轮 R12-3b：方案 C 受控失败实证 + G 第 3 个数据点 + ⚠️ #34 哨兵触发**。**① 方案 C 受控失败（PR #8，一次性分支，main 未受影响）**：注入 `pilotstd/_r12_3_probe.pyi`（142 字符行）→ run `36310949966` **总时长 19.0s**（基线 828s，**−97.7%**）：`lint-fast` failure（16.0s，日志 `E501 Line too long (142 > 120)`），**下游 12 个作业全部 skipped**；实验后 PR 关闭、分支（远端+本地）删除、工作区 clean。**② G 第 3 个数据点**：R12-3 的 run `36310444541` **首个作业启动 +16.0s**（lint-fast）——**原始值超 ≤10s 阈值**；分析见 7.18（同 ref 的 R12-2b 被本次推送取消、runner 分配 + 门控后的指标语义变化）。**③ 方案 C 绿灯代价实测**：快闸启动 +16.0s、时长 14.0s，下游首个作业 +32.0s（门控放行后）→ 绿灯路径 +≈30s。**④ ⚠️ #34 复发（T-26 哨兵触发）**：同一 run 的 `test-gui-unit` 在 `test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe FAILED` 后报 `Windows fatal exception: access violation`（与历史两次逐行同构）→ 按 T-26 预先约定「**再复发 ≥1 次 → 当轮必须做 R2 + R4**」，**哨兵现已触发**，R2（`reset()` 静止协议）+ R4（CI 环境对齐复现）为第十二轮强制项（计划见 7.18）；该 run 的 failure 与 R12-3 改动无关（快闸与其余 9 个下游作业均 success）。
> 2026-09-27 **第十二轮 R12-3：方案 C 落地（lint-fast 快闸 + 下游重作业 `needs` 门控）**。**改动**：`.github/workflows/ci.yml` 新增 **`lint-fast`** 作业（checkout(fetch-depth 1) → setup-python → `pip install ruff mypy` → `python scripts/check_g_038_legacy_errors.py`，命令与范围**零改动**），并给 **9 个下游作业**加 `needs` 门控（`test-backend`／`test-gui-coverage`（保留原 `test-backend` 依赖）／`e2e-coverage`／`security-scan`／`test-frontend`／`test-e2e`／`frontend-e2e`（保留原 `test-frontend` 依赖）／`test-gui-unit`／`repo-compliance`）；`version`（原 `needs` 8 作业）与 `docker`／`exe` 由此**传递性**被门控。**预期收益**：lint 失败时下游**根本不启动**，失败 run 时长 828s → ~30~60s；绿灯路径代价 ≈ +20s（快闸自身时长）。**受控失败实验（本批）**：在一次性分支用 `.pyi` 长行（ruff 会检查 `.pyi`，而本地 L1 触发式 `^scripts/|`+`\.py$` **漏 `.pyi`** → 无需 `--no-verify` 即可提交，实验干净）验证「① 快闸快速失败；② 下游未触发；③ 主分支不受影响」，结果见 R12-3b 批次；同时把该 L1 触发缺口登记为观察项 **T-32**。
> 2026-09-27 **第十二轮 R12-2b：T-28 完整落地（`-rs` 覆盖全部 pytest 调用）+ G 首个数据点入账**。**补充改动**：按用户要求把 `-rs` 从 `test-backend` 扩到**全部 5 处 pytest 调用**——`test-backend`（`tests/`）、`test-gui-coverage`（`tests/gui/`，xvfb 包裹）、`e2e-coverage`（`tests/e2e/`）、Windows GUI E2E（`tests/gui/ -m e2e`）、`test-gui-unit`（`tests/gui/ tests/test_regression_architecture.py`）；复核脚本列出 5/5 均含 `-rs`（YAML 经 PyYAML 解析）。**G 首个数据点（R12-2 推送后实测）**：R12-2 的 run `36309693229` 作业启动延迟 **中位 +2.0s**（2.0~4.0，n=7），**同一时间窗对照**旧组 run `36309485009`（R12-1）**中位 +198s**（197~257）——对照组正是旧模型的排队行为。**T-28 标记 ✅ CLOSED** 并移入「一、已清理」。**路线确认**：R12-3＝方案 C（lint-fast + `needs` 门控），D/E 挂后待 G+C 稳定。
> 2026-09-27 **第十二轮 R12-2：方案 G 落地（并发组按 ref 拆分 + cancel-in-progress）+ T-28 修复**。**改动（仅 CI 配置，检查逻辑零变更）**：① `.github/workflows/ci.yml` 的 `concurrency` 由 `group: ci-cd` + `cancel-in-progress: false` 改为 `group: ci-cd-${{ github.ref }}` + `cancel-in-progress: true`；② `test-backend` 的 pytest 命令加 `-rs`（跳过明细进 CI 日志，可被 `tests/skip_census.py` 解析）。**依据**：R12-1 归因（78 run：33% 的 run 被前一 run 挡住、等待中位 ≈300s；run 中位 828s）。**预期**：同一 ref 内新推送取消被取代的旧 run → 排队≈0；分支/PR 推送不再与 main 争同一槽位。**首个数据点**（推送后实测）与后续 3 次观察记入 R12-3 批次；若 3 次观察的“作业启动延迟”中位 ≤10s，则 G 判定生效，再启动方案 C。
> 2026-09-27 **第十二轮 R12-1：候选池立项 + T-30 排队归因（纯只读取数，未改 CI）**。**候选池**：用户批准 P0~P6 优先级，登记于新增「〇 · **0.2 第十二轮候选池**」。**T-30 归因（78 个 run 全量 + 10 个 run 关键路径，见 7.15）**：① **自串行**——`concurrency: group: ci-cd` + `cancel-in-progress: false` 使 **26/78 = 33%** 的 run 在创建时被前一个 run 挡住，等待 1~1340s（被挡样本中位 ≈300s）；② **runner 分配不是瓶颈**——未被挡时作业启动仅 **+3s**；③ **真正把等待放大的是一次 run 太长**——run 总时长中位 **828s（13.8 min）**，关键路径＝`test-gui-unit` **467s** → `version` 8s → `docker`/`exe` ≈176s；④ **「bump 提交额外 run」假设被证伪**——自动 bump 提交由 `GITHUB_TOKEN` 推送，**不触发任何 workflow**（78 个 run 中 bump 类型 **0** 个）→ 新观察项 **T-31**。**方案对比（A~F）已入 7.15**，推荐「**单并发组改按 ref + `cancel-in-progress: true`**」（1 行，消除 33% 自串行等待且分支推送不再阻塞 main）＋（第二批）缩短关键路径；**待用户选型后进 R12-2 落地**。
> 2026-09-27 **第十一轮 R11-5：T-24 L3 落地（CI 红灯暴露时间实测）**。**改动**：`.github/workflows/ci.yml` 的 `repo-compliance` 作业里，把 `G-038 — 历史遗留错误清零（Ruff+Mypy+裸noqa）`**由末位前移到最前端**（紧跟 checkout）——检查逻辑、命令、范围一字未改，纯步骤顺序调整。**数据（11 次 run 实测，见 7.14）**：该步骤原在作业内 **+13s** 完成（其前面 10 个步骤合计仅 ~3s），前移后 ≈ **+12s** → **顺序收益约 1s**；对照组 `test-backend` 的 Ruff 步骤作业内 **+30~34s**（其前置 `Install dependencies` 独占 23~29s）。**关键结论（原假设需更正）**：真正主导“红灯暴露时间”的是 **runner 排队**——11 次 run 的作业启动时刻相对 run 开始为 **中位 154s、最长 471s**（源于全局并发组 `ci-cd` + `cancel-in-progress: false` 使连续推送串行），而三次 E501 事故 run 的 lint 红灯其实在作业内 **+12~14s** 就已由 `repo-compliance` 的 G-038 报出（`test-backend` 的 Ruff 晚 22~24s）——“等 3 分钟”是排队，不是步骤顺序。故 L3 的实质收益＝让 lint 成为作业内**首个**信号；真正的杠杆（并发组按 ref 拆分／给下游重作业加 `needs` 门控）登记为新观察项 **T-30**，挂第十二轮由用户裁定。**同批入账**：**T-20 关闭（✅ CLOSED，用户裁定方案 A）**、新增 **T-29**（8 处永久 `@pytest.mark.skip`，可偿还候选，挂第十二轮）、T-28 维持挂窗。连带 `docs/governance/gates.md` v1.44 + `README.md` 索引 + 能力矩阵重生成。
> 2026-09-27 **第十一轮 R11-4：T-20 实测与 fixture 基线（口径更正）**。**实测三口径**：① **静态**——`tests/` 的 `self.skipTest` **60 处 / 10 文件**（T-20 原登记值，其中 43 处是`Fixture not found` 守卫）；② **本地运行期**——全量非 GUI 套件 **14 skipped**（网络 6／依赖 5／其他 2／平台 1）；③ **CI 运行期**——run `36306309371` 的 `test-backend` = **44 skipped**（断网 + `_CI` 双因素）。**结论（T-20 原判据被否定）**：43 个 fixture 守卫依赖的 **15 个 fixture 文件全部已入库**，运行期**一次也不触发** → 「因缺 fixture 而跳过」= **0 处**；「60 处会让跳过数长期偏高」是把**静态调用点**当成了运行期跳过数（口径错误，已在 T-20 行更正）。**交付物（仅新增，未改既有测试逻辑）**：`tests/fixture_baseline.py`（fixture 基线登记表 15 项 + 守卫覆盖率判定）、`tests/skip_census.py`（运行期/静态双口径普查工具，把 `pytest -rs` 输出按 fixture／random／platform／network／dependency／other 分类）、配套受控测试 **10 例**。**剩余可治理候选**：8 处 `@pytest.mark.skip`（`test_query_subsystem_snapshot.py` ×4 与 `test_batch_query… dispatch` ×4，理由为“依赖 HTTP／ThreadPoolExecutor／daemon 线程”），属可偿还候选而非环境依赖 → 连同新发现的 T-28 一并挂第十二轮，T-20 终局方案待用户裁定。
> 2026-09-27 **第十一轮 R11-3b：T-25 补丁之二——遗漏补修 + 浅克隆根因**。**① 自曝遗漏**：R11-3 首次提交（`30de04e4`）时 `ci.yml` 的 YAML 修改**因编辑工具在 CRLF 文件上锚点失配而未落盘**（改用补丁脚本重做时只覆盖了两个 .py，漏了 YAML）；CI 日志立刻自证——run `36306033918` 的步骤环境仍为 `DOCS_SYNC_RANGE: 409a5be1…92..`（右端为空）。**② 第二层根因**：回退候选 `origin/main...HEAD` 在推送 main 时因 `origin/main == HEAD` **恒空**。**③ 第三层根因（本轮新查明）**：同一作业更早的 `check-repo-compliance.sh` 执行 `git fetch origin main --depth=1`，**在 tip 建立浅边界**（`.git/shallow`）→ `HEAD~1` 不可用（实测 `fatal: Needed a single revision`）、`git log -n2` 只剩 1 条 → 兜底范围 `HEAD~1..HEAD` 也失效。**修复**：`.github/workflows/ci.yml` 右端改 `${{ github.sha }}`（通用上下文，push 时即本次推送 tip）；`check-repo-compliance.sh` 去掉 `--depth=1`（不再截断历史，行为等价——checkout 本已 `fetch-depth: 0`）；两个脚本新增 `_is_shallow_clone()`——浅克隆下必须声明“历史被截断”，而不是谎称“该范围无变更”。**验证（本地按 actions/checkout 流程端到端复刻浅克隆）**：右端为空 → 输出带浅克隆提示；**显式完整范围 → 真实评估 8 个文件**（证明修复在浅克隆下同样有效）；受控测试 **23 passed**（新增 4 例浅克隆断言）。**连带发现（第六个 CI 盲区同族）**：`check-repo-compliance.sh` 的“新增文件”检查在推送 main 时 `origin/<base>..HEAD` **恒空** → 白名单/黑名单判定从未生效 → 已登记「六、观察项」**T-27**，挂第十二轮。
> 2026-09-27 **第十一轮 R11-3：T-25 补丁——CI 范围取值陷阱（第五个 CI 盲区实证）**——R11-2 收尾核对 CI 证据时发现的直接续修。**根因**：`.github/workflows/ci.yml` 的 `Docs sync check` 步骤写的是 `DOCS_SYNC_RANGE: ${{ github.event.before }}..${{ github.event.sha }}`，而 **push 事件载荷里没有 `event.sha` 字段**（正确为通用上下文 `github.sha`，push 时即本次推送 tip；push 专有字段是 `github.event.after`）→ 右端展开为空 → `DOCS_SYNC_RANGE=<before>..` 被两个脚本判为非法 → 回退 `origin/main...HEAD` → 推送到 main 时 `origin/main` 与 `HEAD` 同一提交、diff 恒空 → **步骤仍旧空转**（GitHub 在步骤日志里直接打印该变量：run `36304263963` = `DOCS_SYNC_RANGE: 27a39d6102c4d076a05f960100668acc08ef9c93..`，左端正确、**右端为空**）——即 T-25 此前属“接线对了但范围算错”的半修。**修复**：① `.github/workflows/ci.yml` 右端改 `${{ github.sha }}`；② `scripts/check_docs_sync.py` 与 `scripts/docs_sync_check.py` 的回退链新增“**候选必须确实含变更文件**”校验（严格模式生效，非严格模式保持旧行为以免本地误抓历史提交去改文档）——空 diff 的候选继续回退到 `HEAD~1..HEAD`，全部为空时以“该范围无变更”显式说明收场，**绝不静默 PASS**；`--range` 硬指定不受该过滤影响。**受控验证**：右端为空 → 两脚本均回退 `HEAD~1..HEAD` 并输出真实判定（此前为“无变更文件／跳过”）；`--range` 仍被尊重；真实未同步范围 → `WARN(告警期)` + EXIT=0。**反证**：新增 11 例受控测试（`tests/test_check_docs_sync.py` 6 例 + `tests/test_docs_sync_check.py` 5 例），对修复前脚本跑 **6 failed**、修复后 **19 passed**。**T-16 观察计时器再次归零**（自 R11-3 起重新计时——前 6 次因 CI 跑的是形近脚本而无效，R11-1 之后那 1 次因范围恒空而无效）。**批次重排**：R11-4 = T-20（测试 fixture 基线）、R11-5 = T-24 L3。连带 `docs/governance/gates.md` **v1.41** + `README.md` 索引 + 能力矩阵重生成。
> 2026-09-27 **第十一轮 R11-2：三债终局裁定（#31／#32／#34）**——本轮**只出裁定书、不做全量偿还**，已逐条写入「二、剩余台账」对应行（四要素：现状量化／偿还方案+成本／转已接受的代价／终局结论）。**判决**：**#31 → [挂窗第十二轮]**（>1 commit 且连锁风险高：`_load()` 的“构造即写回”契约被 `tests/test_core_config.py:333-340` 依赖、P3 引入跨进程锁语义；“只做 P1 缓存”的 1-commit 方案经评估因缺失效通知而被否决）；**#32 → [挂窗第十二轮起分阶段偿还]**（四阶段路线图：A 枚举落地 → B 后端收敛 → C API 契约层+落库迁移 → D 测试收敛，合计 7~12 commit／跨 ≥3 轮，A 阶段须第十二轮完成）；**#34 → [转已接受+代价]**（R1 落地后 14 个 run 的 `test-gui-unit` 14／14 success，满足本行预先约定的接受判据；同时声明该样本在 ≈1／40 基率下零复发概率 ≈70%、不足以证明根因消除，**哨兵＝复发 ≥1 次即当轮做 R2+R4**）。**同批数据更正**：#32 的容器定义点由“7 处”更正为 **9 处／5 个名字**（原探针未解包 `frozenset(...)`，漏计 EXPIRED_STATUSES／_EXCLUDED_FROM_OVERRIDE）；#31 单位成本本轮复测 4.28／4.27／4.28 ms（每次恰 1.00 构造 + 1.00 save）；#34 新增 R1 后 14 run 全绿数据点与统计效力声明。连带 `docs/governance/gates.md` **v1.40** + `docs/governance/README.md` 索引版本 + 能力矩阵重生成；「六、观察项」新增 **T-26**（#34 复发哨兵）；「七、操作记录」新增 **7.10**（裁定取数方式）。
> 2026-09-27 **第十一轮 R11-1（T-25 接线修复）**：开轮侦察发现 CI 的 `Docs sync check` 步骤跑的是**形近脚本** `scripts/check_docs_sync.py`（而非第十轮实现严格模式的 `scripts/docs_sync_check.py`），且前者当时只做 `origin/<base>..HEAD`（推送 main 时恒空）→ **步骤长期空转、恒 `PASS: 无变更文件`**；后果：T-16 的 6 次告警期观察**全部无效**（第四个 CI 盲区实证）。**修复**：`ci.yml` 该步骤**依次跑两个脚本**（`set -e`）；`check_docs_sync.py` 补齐范围回退链与**告警期语义**（未同步只 `WARN(告警期) … 未阻断（exit 0）`，绝不静默 PASS；`--strict-block` 才 exit 1），并修其 GBK 控制台 `UnicodeEncodeError` 假性 exit 1；主簿新增 **T-25**、T-16 行注明**计时归零重置**（自 R11-1 起重新计时）。
> 2026-09-27 第十轮 **收尾之二（CI 事故修复 + T-24 登记）**：① **CI 事故**：`scripts/update_docs.archived.py`（T-15 归档件）头部 4 行超 ruff `line-length=120`（E501）→ `test-backend`（Ruff check blocking）与 `repo-compliance`（G-038）双双失败并连带 skipped 4 个 job（run `36300484047`/`36301031251`/`36301267833`），已由 `fed654ea` 修复（run `36301687032` **全绿 12/12**）；② **T-24 登记（用户裁定：分层落地）**——**L1 ✅** `--fast` 下暂存含 `scripts/` 或 `*.py` 时自动增跑 ruff+mypy（G-038 同口径，<5s，工具缺失降级 WARN）；**L2 ✅** 新增 `--with-lint` 强制增跑；**L3 挂第十一轮**（G-038 的 ruff/mypy 提前到 CI `repo-compliance` 最前端，红灯 1 分钟内暴露）；③ 受控反证：注入一条 150 字符行 → L1 复现 CI 同款 `E501` 并 `FAIL`（EXIT=1）；④ 连带 `gates.md` v1.38、`README.md` 索引、能力矩阵。
> 2026-09-27 第十轮 **收尾（T-23 裁定入账）**：新增「七、操作记录 **7.9**」——「三-B、i18n key 一致性检查」标签**经评估保留不收敛**（功能性子节，非结构性空档；与已收敛的「六-B」→「六」性质不同），附四条裁定理由。**本轮状态：CLOSED**（T-01~T-22 全部销项；T-23 已裁定并补记）。
> 2026-09-27 第十轮 **第五批：章节编号收敛 + 本轮收尾入账（T-22 + T-14/T-15/T-16/T-17/T-19/T-20/T-21）**——① **编号收敛**：「六-B、观察项」→ **「六、观察项」**、「八、操作记录」→ **「七、操作记录」**（含其 `8.x` → `7.x` 八个子节），全库引用同步（`gates.md` v1.31/v1.33 行、归档存根去向表、`docs/ci-lessons.md`），历史提及一律加「编号收敛前为…」限定；② **已清理补登 4 项**：T-14（删死脚本 `check_docs_sync.sh`）、T-15（归档 `update_docs.py`）、T-17（G-032/G-033 排除归档件）、T-19（删两个空章节）——按用户裁定用「根因 + 处置 + 验证 commit」三要素，不填窗口/代价；③ **观察项新增 3 条**：T-16（`docs_sync_check` 严格模式告警期 → 阻断条件与切换方式）、T-20（`self.skipTest` 60 处 → 挂第十一轮）、T-21（本地 vitest 偶发 exit=1 → 挂起观察）；④ 连带 `docs/governance/gates.md` **v1.36**、`README.md` 索引版本、能力矩阵重生成。
> **本文件为技术债唯一数据源（SSOT）**：旧簿 `architecture/technical-debt-registry.md` 已于 2026-09-27 废止并归档为
> [`technical-debt-registry.archived.md`](architecture/technical-debt-registry.archived.md)（仅存归档说明，内容不再维护）；
> 其有价值内容已并入本文件（已跳过测试明细 → 「四」；已接受决策 → 「五」#6/#7/#8；历史条目 → 「一」「六」）。
> 2026-09-27 第十轮 **第四批：P1 清理（T-19 空章节删除 + T-14 废弃死脚本）**——① **删除两个空章节**：「六、待决策」「七、清理项」的唯一内容已于同轮移入「五、已接受的设计决策 · 归档并入」与「一、已清理」；**「六-B、观察项」标签当批刻意保留不改名**（被 `gates.md` v1.31 行、归档存根与本文件共 11 处历史引用）；**该标签已在同轮第五批（T-22）统一收敛为「六、观察项」**（连同「八、操作记录」→「七、操作记录」及其 `8.x` → `7.x` 子节）。② **删除 `scripts/check_docs_sync.sh`**：其自述"渐进式部署，仅提醒不阻断"、全库无任何调用点（`git grep check_docs_sync` 排除自身后 0 命中），功能已被 CI 侧的 `docs_sync_check.py` 覆盖；连带清理 `gates.md` v1.31 行里对它的反引号引用（避免 G-032 交叉引用告警）。③ 连带 `docs/governance/gates.md` **v1.33**、`docs/governance/README.md` 索引版本、能力矩阵重生成。
> 2026-09-27 第十轮（架构优化与债务清算轮）**第三批：代码层 TODO 登记 + 门禁幽灵路径（T-12/T-13）**——① **`AppLayout.vue` 空列表兜底分支与过期 TODO 已删除**（探针实测真实 router：21 条记录 / `showInSidebar` 11 条；`navItems` role 空·guest·未知 → 10 项、user·admin → 11 项 **恒非空**；全库无 `addRoute`），同步修 `AppLayout.test.ts` fixture（原 fixture 无 `showInSidebar` 标记，项数实来自被删兜底），G-010 `AppLayout.vue` **434 → 420**；② **`Tech-Debt #8` 编号悬空补登**（真实指向 `docs/investigations/aura-token-sync-feasibility.md`，落地 `d38e88b1`；与主簿 `TD-8`（测试跳过项）撞号已在此说明）；③ 代码层另 2 类 TODO 入「六、观察项」（`_attachment_parser.py:104` 的 `.doc`/OLE2 `TODO(P2)`、`HomeView.vue:17` 的 grid-layout-plus workaround）；④ **门禁幽灵路径清理**：`scripts/check_g_030_tech_debt.py` 的 `DEBT_REGISTER_PATHS` 删除从未存在过的 `docs/governance/tech-debt-register.md`（保留 `docs/technical-debt.md`），同批更新 `docs/governance/gates.md`（v1.32）+ `docs/governance/README.md` 索引版本 + 重生成能力矩阵（G-031 联动）。
> 2026-09-27 第十轮（架构优化与债务清算轮）**第二批：过期数据与口径刷新（T-07~T-11 + T-18）**——① #11 的 `NotificationConfig.vue` 425 → **438**（批 1 i18n 化所致）；② #32 前端比较点 **9 → 13 处**并刷新全部行号（补登 `WechatTrustIP.vue:229-230`）；③ 「五」#3 警告区"8 个/最高 487" → **3 个 / 最高 438 / 阻断档 0**，并与 #11 去重（指向 #11）；④ 「四」更正"7 个 Handler E2E 已删除"的失实表述（实测 `tests/gui/` 现存 11 个 `test_e2e_*.py`、其中 2 个带 `@pytest.mark.skip`，CI 用 `--ignore-glob` 排除），并补登本节口径下漏登的环境依赖跳过点（`test_manager`×5、`test_file_utils`×3、`gui/test_file_tree`、`unit/.../test_mirror`、`test_i18n_key_count`、`stress_winui`）+ 按机制给出全库跳过点总量（**102 处**）；⑤ 「三、维持现状」行数列标注**物理行/有效行**双口径（426/371、142/109、263/209、143/116、51/39）；⑥ #27 行内未转义 `\|\|` 加转义，消除表格列错位。所有数字均为 2026-09-27 探针实测。
> 2026-09-27 第十轮（架构优化与债务清算轮）开轮：**① 轮次口径立项**（见「〇、0.1」，取代此前无锚点的"第 N 轮"表述）；**② 唯一数据源确立**——旧簿废止归档、有价值内容并入本文件、`scripts/docs_sync_check.py` 的 Handler/Mixin 联动目标重指本文件（原指向旧簿）。归档判定：旧簿「六、G-010 警告基线（9 文件）」等数字已过期（实测警告档仅 3 个），直接废弃；其余按"有价值即并入、过期即废弃"逐节处理。
> 2026-09-27 新登记 **#32（可偿还）后端状态值用中文，前端硬编码中文做比较**——阻碍 i18n 真正完成 + 同一语义两种口径。实测：后端生产代码 **248 处**中文状态字面量（50 文件，9 个值）、测试 **456 处**（65 文件 / 277 个测试函数）、**7 处**重复状态集合定义（无统一枚举）；`废止`（查询/待确认链路）与 `已废止`（统计链路）并存，前端 `PendingView.vue:62-63`（行号已于第二批 T-08 刷新，原记 60-61）还在比较后端**从不返回**的 `'Active'`/`'Withdrawn'`。窗口 **最迟第十轮（架构优化轮）· 待用户确认**（与 #31 同窗）；只登记，未修。
> 2026-09-27 新登记 **#31（可偿还）ConfigManager 多实例交错写 + 查询热路径高频 IO**——每实例一把锁（无文件锁/无单例）、`_load()` 每次无条件 `save()`、`scorer.get_profile()` 每次评分都新建实例；实测一次 mock 查询（4 条目）触发 **126 次构造 + ≈126 次写盘**，且该段无停止检查点（与 2026-09-26 的 CI GUI abort 直接相关）。窗口 **最迟第十轮（架构优化轮）· 待用户确认**；只登记，未修。
> 2026-09-26 收尾轮（monitor 计数误导）：**TD-30（原 #30）已清理**——`pilotstd/monitor/scheduler.py::_on_file` 此前只调 `scan_directory`（仅解析文件名、不搬文件、不写 `file_index`）却照记 `success`：`monitor.auto_archive` 开关与「文件就绪后触发自动归档」的注释**从未有过实现**（`git log -S 'archive_standards' -- pilotstd/monitor/scheduler.py` 为空）。现补上归档（复用统一入口 `archive_standards`，非第二套实现）并改按**真实归档结果**计数（`moved>0` 才记成功；解析不出或归档报错记失败；一条没搬不计成败）；与 TD-28 零重叠（延迟回调先判 `os.path.exists`，链路已搬走的文件根本不会触发回调）。验证：单元 6 例 + 集成真跑 4 例，`git stash` 反证 **8 failed**；至此「一、已清理」共 15 行。**#17a 残留（单条请求/大文件 IO 不可中断）转 ✅ 已接受（ROI 判断）**——本轮补齐逐层实测上界、"取消延迟不累加"的机制依据、7 处穿透成本（估 150–300 行）与两处真无上界的实情（`resp.content` 的空闲超时、`safe_move` 的复制/哈希无超时），该行在「六」内闭环；TD-30 的转义名残留同步闭环（B-1：`_safe_filename` 把 `/` 改为删除而非转义，含 `/` 的 code 往返还原 124/124、0 撞名）——**技术债文档至此零残留**。
> 2026-09-26 第八轮（四线并行）：① **#11 G-010 警告区治理执行完毕**——警告区 **8 → 3**、最高有效行 **487 → 438**（拆 5 个文件，见本条台账）；② **#15 通知聚合器实例不共享** 转最终判断；③ **#16 两个死列** 删除（新增 v60 迁移）；④ **#19 `/api/favorites/{id}/status` 端点存废** 按 `[STATUS_API]` 日志实测 UA 分布定案。各线独立分支、独立提交、独立验证。
> 2026-09-26 第七轮（两条线并行：前端 CI 缺陷 + #17a 到期偿还）：
> ① **前端 CI 缺陷已修**（非"偶发"）：`primevue/tablist/index.mjs:48-53` 在 `mounted()` 排的 150ms ink-bar 定时器无句柄、`unmounted` 不清理，测试文件在 150ms 内结束时回调落在 jsdom 全局被摘除之后 → `ReferenceError: HTMLElement is not defined`（unhandled → `Tests 230 passed` + `Errors 1 error` + exit 1）。修法：`web/src/test-setup.ts` 接管 `setTimeout` 登记未触发句柄，文件级 `afterAll` 清理；连跑 10 次 `Errors 0 / exit 0`。详见「七、操作记录 7.6」。
> ② **#17a 已偿还并移入「一、已清理」**（TD-23）：8 处停止入口对应 7 类 worker 全部加中断检查点（抛 `WorkerAborted` 终止底层流，而非仅跳过信号发射）；中断延迟实测 scan 14ms / query 6ms / 暂停中 query 60ms / DriveEnumerator 54ms（修复前四者均 ~5s 超时 + 保活计数 +1）。残留的单条网络阻塞窗口登记为「六、观察项」。
> 2026-09-26 第六轮（技术债收尾：验证 → 消除 → 记录）：① **#18 巡检改走公开 API 复核**——`GET /api/favorites/export?format=json` 无分页截断（导出行数 105 == 库内行数 105），A/B/C 三组的 `user_favorites` 维度可本地算得全 0；`favorite_downloads`/`announcement_record`/`download_queue` 三表列**未在任何公开端点暴露**（`favorites.py:341-346` 只给 4 个下载字段），其维度仍经 `POST /query` 取证，结果同为 0。② **#11 紧急项已还**：`scripts/check_g_012_sql_schema.py` 有效行 **497 → 139**（拆出 `scripts/_sql_schema_parser.py`），`docker/auth.py` **490 → 394**（拆出 `docker/_static_token.py`）；G-010 警告区 **10 → 8**，最高 487。③ **#15 现状更新**（`StandardManager()` 构造点实测 **9 处**）。④ **#21 新登记**；`docs/deployment/README.md` 过时内容已更新。⑤ 第五节 5 条已接受设计补齐审计轨迹。
> 2026-09-25 勘误与收尾：**#18 只读巡检已通过 `POST /query` API 实际执行完毕**（A/B 两组共 8 项全 0、C 组 0 行）——上一轮把它标为"环境不可达"是**错的**：`admin_db.py` 的表白名单只作用于 `DROP TABLE`，SELECT 不受限制（第三轮"该表不在白名单→只能容器内 SQL"同样不成立）。据此补记「七、操作记录」的执行通道对比，并新增一条待决策：该端点对管理员等同全库读写。
> 2026-09-25 第五轮（逐条验证 + 分类还债）：**逐条查代码验证 #11~#20**（证据见各条），其中 **#13/#14/#20 直接修复并移入「已清理」**，**#17 拆成 17a（可偿还）/17b（技术无解）**，**#11/#15 归入 ROI 判断**并写明最终判断轮次；**#16 死列 → 清理项**、**#19 残留 → 待决策**、**#18 SQL → 操作记录**（不再混在台账里）。第五节 5 条已接受设计补「不还的代价」。
> 2026-09-25 登记规则修正：每笔债必须写全 **根因 / 现状 / 偿还窗口 / 不还的代价**；窗口必须是具体轮次，不接受"等复评条件"或无期限挂账。

---

## 〇、登记规则与分类标准（2026-09-25 起生效）

每笔技术债**必须写全四项**，缺一项视为登记无效：

| 字段 | 要求 |
|---|---|
| **根因** | 为什么会变成这样（可追溯到代码/数据/流程），不接受"历史遗留"这类空话 |
| **现状** | 今天实测到什么（附证据/命令/行号），影响面到哪里 |
| **偿还窗口** | **具体轮次**或"最迟第 N 轮"；触发式提前条件（如门禁阻断、error 级告警）可另附 |
| **不还的代价** | 用户/项目会具体损失什么（中断、脏数据、无法运维、返工成本） |

**分类标准**（每条债必须落在其中一类）：

| 分类 | 判定标准 | 处理 |
|---|---|---|
| **可偿还** | 能用代码/配置/数据解决 | 写具体轮次，到期必还 |
| **技术无解** | 受限于语言/框架/外部系统，改代码解决不了 | 写明"已接受" + 具体技术限制 + 代价，**不挂窗口** |
| **ROI 判断** | 技术上能做但收益低于成本 | 写明"最迟第 N 轮做最终判断：要么还，要么正式转已接受并关闭" |
| **环境依赖** | 依赖外部环境，代码侧无解 | 保留在「四、已跳过测试」 |

配套约束：①不接受"等复评条件"作唯一期限；②不接受"无用户投诉"作拖延理由；③已关闭项也要写清代价；④每轮做残留审查；⑤「一、已清理」「三、维持现状」「四、已跳过测试」「五、已接受的设计决策」不适用偿还窗口。

### 0.1 轮次口径（2026-09-27 定义，取代此前的"第 N 轮"模糊表述）

| 项 | 定义 |
|---|---|
| **当前轮次** | **第十一轮 —— 债务终局裁定轮**（R11-1 T-25 接线修复 → R11-2 #31／#32／#34 终局裁定 → **R11-3／R11-3b T-25 补丁：CI 范围取值陷阱（第五个 CI 盲区）+ 浅克隆根因** → R11-4 T-20 测试 fixture 基线 → R11-5 T-24 L3（G-038 前移））；上一轮为**第十轮 —— 架构优化与债务清算轮**（专项清理历史技术债／优化底层架构／完善治理门禁） |
| **起算点** | 自 **v0.110.0**（i18n 批 0 启动）起算，至所有 **P0/P1 债务清零或降级**为止 |
| **三债终局裁定（第十一轮 R11-2 完成）** | **#31 → [挂窗第十二轮]**（锚定 v0.119.x → v0.120.0）；**#32 → [挂窗第十二轮起分阶段偿还]**（A 阶段须第十二轮落地，B~D 跨轮推进）；**#34 → [转已接受+代价]**（保留 R1；哨兵＝复发 ≥1 次即当轮做 R2+R4，见「六、观察项」T-26）。原窗口“最迟第十轮”已到期——本轮**只出裁定书**，判决、量化与代价见「二、剩余台账」各行裁定书 |
| **后续规则** | 轮次一律按**季度**或**大版本号**（如 `v0.120.0`）划分，并写明具体版本号或时间窗口；**禁止再使用"第 N 轮"这类无锚点表述**。存量条文中已写的"最迟第 N 轮"按上表映射到第十轮 |

> 说明：本口径生效前登记的"最迟第 N 轮"窗口按上表统一解释；此后新登记的债务**必须**写具体版本号或季度窗口，否则视为登记无效（§〇 四项要求之一）。

### 0.2 第十二轮候选池（2026-09-27 用户批准，按优先级）

| 优先级 | 项 | 预估成本 | 备注 | 登记位置 |
|---|---|---|---|---|
| **P0** | **T-30** CI 排队瓶颈 | 3~5 commit | 真正杠杆；需设计并发组拆分策略 + `needs` 门控方案（R12-1 归因数据 + A~F 对比已交付；**R12-2 已落地方案 G**（按 ref 分组 + cancel-in-progress），数据点 **+2.0s／+7.0s**（同窗对照旧组 +198s）；**R12-3 已落地方案 C**（lint-fast + 9 作业 needs 门控），数据点 3＝+16.0s（超 ≤10s，原因见 7.18）；**收口判定待用户裁定**；D/E 挂后） | 本节 · 六、观察项 T-30 |
| **P1** | **T-29** 8 处永久 skip | ≤2 commit | 可偿还候选；`test_query_subsystem_snapshot.py` ×4 + `tests/unit/query/engine/test_batch_dispatch.py` ×4 | 六、观察项 T-29 |
| **P2** | **T-28** CI pytest 缺 `-rs` | 1 commit | **✅ CLOSED（R12-2／R12-2b）**：`-rs` 覆盖全部 5 处 pytest 调用，CI 日志实证 44 条跳过明细 | 六、观察项 T-28 |
| **P3** | **T-27** 新增文件检查盲区 | 1~2 commit | T-25／T-26 同族（范围恒空 → 假绿）；修法类似 | 六、观察项 T-27（T-32 已 CLOSED，见「一、已清理」） |
| **P4** | **#32** 中文状态值分阶段偿还 | 7~12 commit | 四阶段路线图已就绪；视第十二轮容量决定是否启动 A 阶段 | 二、剩余台账 #32 |
| **P5** | **#31** ConfigManager 交错写 | 3~5 commit | 锚定 `v0.120.0`；需跨进程锁设计 | 二、剩余台账 #31 |
| **P6** | **#34** EventBus 竞态 R2+R4 | 2~3 commit | **⚠️ 哨兵已触发（R12-3 的 run `36310444541`，access violation 复发）→ R2+R4 升为第十二轮强制项** | 二、剩余台账 #34（裁定：转已接受+哨兵） |

> 排期口径：P0 起每批一次独立提交（`--fast --guards --local` + `--deep` 双跑后推送）；**候选池本身不设窗口**——它与各条目的自有窗口（P4/P5 锚定 `v0.120.0`、P6 为触发式）并行生效。


---

## 一、已清理

| 项目 | 说明 | 修复日期 |
|------|------|---------|
| DriveEnumerator 死代码 | `_file_tree.py` 内联副本删除，统一引用 `pilotstd/ui/drive_enumerator.py` 正本 | 2026-07-16 |
| LogHandler atexit 冲突 | `flush_logs()` + `app.aboutToQuit` 注册，Qt 析构前安全关闭 logging | 2026-07-16 |
| 跨 Handler 回调升级事件总线 | EventBus 单例 + 5 Handler 迁移（scan/query/download/archive/auto），13 个集成测试 | 2026-07-16 |
| 剩余 Handler 纯逻辑提取 | AutoFlowEngine（build_summary_stats）+ ScanFlowEngine（5 方法）+ AnnounceFlowEngine（3 方法），65 测试 | 2026-07-16 |
| _auto.py 全链路阶段验证 | test_auto_pipeline.py 补充 query/download/archive 阶段字段存在性断言 | 2026-07-16 |
| PriorityConfigManager 死代码（O-6） | `pilotstd/core/config/priority.py` 零生产引用（仅测试），删除模块 + 测试；`STANDARD_ROOT` 环境变量能力已由 `ConfigManager.__init__` 原生覆盖，不丢功能 | 2026-08-24 |
| TD-1 system.py F821 | 原 #1（登记 2026-07-24）：`docker/api/system.py:131` `Undefined name 'Any'`，缺 `from typing import Any`。`4bfb8078` 补充导入；2026-08-25 实测 `ruff check docker/api/system.py` 通过 | 2026-07-25 |
| TD-2 Mixin 类型标注 | 原 #2：13 文件 Mypy `[attr-defined]` 92 处。parser 已重构拆分（`_exact.py`→`_exact_matcher.py` 等）；2026-08-25 实测 attr-defined = 0 | 2026-08-25（审计确认） |
| TD-3 i18n key 一致性自动化检查 | 原 #3：`scripts/check_i18n_key_count.py`（顶层 key 对齐 + WARN 50 / FAIL 60）接入 CI，配套 `tests/test_i18n_key_count.py`（11 用例） | 2026-07-29 |
| TD-4 test_login_correct_password_returns_ok_and_cookie | 原 #4：xdist cookie 竞态。`81652b6d` 加 `@pytest.mark.xdist_group("auth")` | 2026-08-15 |
| TD-5 test_download_by_numbers_delegates | 原 #5：mock 目标错误。`c5e1c824` 修正为 `_core.scheduled_svc` | 2026-08-15 |
| TD-6 test_do_request_timeout_retries | 原 #6：mock 命中 token 流程致 call_count 漂移。`a720030a` 标记 `_initialized` 跳过 token 获取 | 2026-08-15 |
| TD-7 test_01_overflow_concurrent | 原 #7：bucket 并发 + config.json 锁竞态。`eddc02bf` 加 `@pytest.mark.xdist_group("bucket_stress")` | 2026-08-15 |
| TD-8 test_04_large_batch_sub_buckets | 原 #8：同 TD-7。`eddc02bf` 同上 | 2026-08-15 |
| TD-9 notification.py user_id 误用 | 原 #9：`_get_user_id` 把 token 的 user_id 传给按 username 查询的函数，多用户场景静默折叠为 user 1。`bd34a226` 重写：形参改 `user_id` + 主键校验 + 未知用户显式 401；新增 401 分支与集成测试 | 2026-08-25 |
| TD-10 test_api_snapshot.py 环境污染 | 原 #10：模块级 `os.environ.setdefault` 永不恢复，污染后续模块。`07786678` 改 env fixture（save/restore/pop）+ `acf2a7fd` 收敛 10 个同值家族；关门验证 `tests/ --ignore=tests/gui/` 4084 passed / 0 failed | 2026-08-25 |
| TD-16 `/status` 旧键兼容层 | 原 #16（登记 2026-09-21）：删除 5 个旧键（`local_path`/`error_message`/`in_cooldown`/`abandoned`/`archive_retry_count`）+ 连带删除 `_COOLDOWN_DAYS`/`LEFT JOIN`；前端删除唯一调用方 `getFavoriteStatus`。验证：键集合契约测试 2 例、ruff/mypy 全绿、现场 v0.110.0 实测 7→8 键且旧键 0 个。**残留已移出**：两列死列 → 见「七、清理项」 | 2026-09-25 |
| **TD-13** G-031 缺口：`pilotstd/core/` 无文档联动映射 | 原 #13（登记 2026-09-13）。**修复（2026-09-25）**：`DOC_SYNC_MAP` 补 `("pilotstd/core/", "docs/architecture/modules/core.md", "block")`。**验证**：①映射自检 11 条、死映射 0；②受控功能测试——仅暂存 `pilotstd/core/audit.py` 一处改动 → G-031 **FAIL** 并提示"`docs/architecture/modules/core.md` 未同步更新"，证明映射真实生效（改完还原探针）；③**连带修复 core.md 本身过时**（修复过程中发现）：`CURRENT_SCHEMA_VERSION` 已 59（原文写 v53）、`.py` 文件 70 个（原文写 50+）、补 `config/service.py` 与 notification 新增子文件、门禁编号 G-032→**G-031** | 2026-09-25 |
| **TD-14** G-031 缺口：`pilotstd/announcement/` 无文档联动映射 | 原 #14（登记 2026-09-13）。**修复（2026-09-25）**：补 `("pilotstd/announcement/", "docs/reference/announcement-pipeline.md", "block")`（该文档正是 AGENTS §8.2 指定的回写目标，且其"采集/解析/清洗/入库"流程与 `pilotstd/announcement/`（base/engine/matcher/monitor/adapters/ocr）覆盖面一致）。验证：同 TD-13 的映射自检（11 条 0 死映射） | 2026-09-25 |
| **TD-18** 8 条收藏无队列行 + 36 行 `standard_number` NULL | 原 #18。**修复（2026-09-25 现场）**：补建 8 行队列（`INSERT rowcount=8`、`missing=0`、全 `pending`）+ 纠正 36 行 NULL（`uf updated=36`、`uf_null_after=0`、`fd_unknown_after=0`）+ 显示层改"未加入队列" + 导出加 `COALESCE(f.standard_number, r.standard_number, '')`。现场复核：导出 105 条 0 空值、页面 8 条"已入队"。**只读巡检已完成（2026-09-25，经 `POST /query` API 执行）**：A 组 4 项（uf/fd 标准号与名称空值、`UNKNOWN_*`）全 0；B 组 4 项（四表 `standard_type` 空值）全 0；C 组去重基线 0 行 → **无其他同源回填缺口，本条彻底关闭**。**勘误**：第三轮曾判断"`favorite_downloads` 不在 admin SQL 白名单 → 只能容器内 SQL 修复"，经查 `admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**，SELECT 不受表限制 → 该判断不成立（数据修复本可经 API 完成）；SQL 与巡检语句留档见「七、操作记录」。**2026-09-26 公开端点复核（第六轮）**：`GET /api/favorites/export?format=json` 返回 **105 行 == 库内 `user_favorites` 行数**（接口 SQL 无 LIMIT/分页，`favorites.py:453-470`）→ 全量性成立；本地分组算得 A 组 `uf_std_no_null/empty = 0`、`uf_std_name_null/empty = 0`（键名 `std_name`，来自 `announcement_record`）、`uf_std_no_UNKNOWN_ = 0`；B 组 `uf_std_type_empty = 0`（105 条全 `NationalStd`）；C 组 105 组、**重复组 0**。`favorite_downloads`/`announcement_record`/`download_queue` 三表列**未在任何公开端点暴露**（`_DOWNLOAD_FIELDS` 只有 status/error/last_attempt/updated_at），其维度仍经 `POST /query` 取证：fd 标准号/名称空值、`UNKNOWN_*`、fd/ar/dq 分类空值**全 0** | 2026-09-25 |
| **TD-23** 原 #17a —— worker 阻塞点可中断上限 | 原 #17a（登记 2026-09-23，偿还窗口"最迟第六轮"，第七轮补还）。**根因**：停止信号只让回调"闭嘴"（`if self._stopped: return`），底层 `manager.*_stream()` 循环并不知道要停，仍会跑完全部条目 → `stop_worker_gracefully()` 等满 timeout → 只能保活（#17b 已接受的代价）。**改动**：① `pilotstd/ui/workers/_common.py` 新增 `WorkerAborted` + `check_stop()`（`stop()` 或 `requestInterruption()` 置位即抛）+ `wait_pause_or_abort()`（暂停等待改 200ms 切片，原无超时 `wait()` 在暂停中必然卡死）；② 7 类 worker 的逐条回调（scan/query/download/archive/normalize/announce/auto）全部改为"在检查点抛异常终止流"，而非仅跳过发射；`AutoWorker` 四阶段回调共用同一组检查点（原为无任何停止检查的 lambda）；`ArchiveWorker` 的磁盘预扫描循环、`DriveEnumerator` 的逐盘循环也加检查点；③ 各 worker 增加 `except WorkerAborted` 分支（不误报 error 信号），`finally` 的收尾信号加 `isInterruptionRequested()` 守卫；④ `WorkerAborted` **刻意继承 `BaseException`**——服务层有"单条失败继续跑"的兜底（`manager/facade/_organize.py:106-123` 把 `on_result` 包在 `try/except Exception` 内），继承 `Exception` 会被吞掉导致中断失效；已加专门回归用例（`_ExceptionSwallowingMgr` + `test_abort_survives_service_layer_except_exception`）。`AutoWorker._emit_scan_batch` 同步改为"停止即抛"契约，`tests/gui/test_coverage_workers.py::test_emit_scan_batch_when_stopped` 由"断言不发射"更新为"断言抛 WorkerAborted"（删方法时漏扫测试导致全量 GUI 首轮 2 failed，已修）。<br>**验证（量化验收）**：假 stream（20000 条 × 10ms，不中断需 200s）逐条回调，中途 `stop_worker_gracefully(timeout_ms=5000)`——**修复后**：scan **14ms**（0.3% 预算）、query **6ms**（0.1%）、暂停中 query **60ms**（1.2%）、DriveEnumerator **54ms**（1.1%），四者 `退出=True`、保活计数增量 **0**、残留 **0**；**修复前对照**（`git stash` 掉改动）：四者分别 **5035 / 5009 / 5010 / 5055ms**、`退出=False`、保活计数各 **+1**，并触发 error 级"疑似卡死线程"告警（累计超时 4）。单测：`tests/gui/test_worker_lifecycle.py` 新增 4 例（scan/query 参数化、暂停可中断、盘符枚举）→ 该文件 10 passed。窗口达标情况见「六、观察项」（单条网络请求/大文件 IO 内部仍不可中断，受既有 timeout 约束）。 | 2026-09-26 |
| **TD-22** G-010 高危文件拆解（#11 紧急项） | 编号说明：台账 **#21** 已占给"下载链验证码"，故本条取 TD-22。<br>**A**：`scripts/check_g_012_sql_schema.py` 有效行 **497 → 139**——SQL 文本解析层（`SQL_KEYWORDS`/`PYTHON_BUILTINS`/`_SQL_FUNCTIONS` + 13 个纯函数）整体搬到新模块 `scripts/_sql_schema_parser.py`（470 行 / 370 有效行），脚本以 `from _sql_schema_parser import ...` 复用。<br>**B**：`docker/auth.py` 有效行 **490 → 394**——静态令牌管理（`_STATIC_API_TOKEN`/`_STATIC_TOKEN_INITIALIZED` + `_ensure_static_token_in_db`/`get_static_token`/`refresh_static_token`）搬到 `docker/_static_token.py`（125 行 / 105 有效行）。调用方：auth.py 只 import 其仍内部使用的 `_ensure_static_token_in_db`；唯一外部调用方 `docker/api/settings.py:13` 改为直接 `from .._static_token import get_static_token, refresh_static_token`（**仓内全量 grep 确认无第二处引用**）。曾试"在 auth.py 冗余别名再导出"，但 ruff isort 会把纯再导出拆成 3 条 import（+2 行、且更难看），故改为直接引用新模块。<br>**搬移方式**：程序化按行区间提取（`C:\Temp\pilotstd-probe\split_g012.py` / `split_auth.py`），函数体逐字节未改，仅新增模块 docstring 与 4 条中文说明注释。<br>**验证**：①`python scripts/check_g_012_sql_schema.py` 前后自身输出**逐行一致**（清洗 shell 噪声后各 36 行，diff 为空）且 PASS（0 处不一致 / 73 条 SQL）；②G-010 警告区 **10 → 8**，最高 487，无文件 ≥490（auth.py 已退出警告区）；③ruff 全绿；④mypy `docker/` 单目录错误数前后同为 5（源文件 47→48）——注意 G-038 的**合并口径**（`pilotstd/ docker/` 一起跑）实测 `Success: no issues found in 385 source files`；⑤`tests/test_core.py` 107 passed、auth 相关 6 文件 **73 passed**；⑥`check_all.sh --fast --guards --local` EXIT=0 / 0 FAIL。（过程中唯一回归：新模块注释密度 1.9% < 3% 触发 G-012 注释密度 FAIL → 补"为什么"注释后 PASS） | 2026-09-26 |
| **TD-16 残留** `user_favorites` 两列死列 | 原 #16 残留（登记 2026-09-25）：`archive_retry_count` / `last_archive_attempt` 的唯一读取方是 `/api/favorites/{record_id}/status` 的 5 个旧响应键，随 #16 删除后零读取（`pilotstd/` + `docker/` grep 排除 `_migrate_*` 后 0 命中），但受 P-106（已执行迁移源码不可变）约束不能改 v52/v59 就地删列，故挂到清理项。**修复（2026-09-26）**：新增 v60 迁移 `pilotstd/core/db/_migrate_v60_drop_favorite_retry_columns.py` 幂等 `ALTER TABLE user_favorites DROP COLUMN`（先读 `PRAGMA table_info`，表不存在/列不存在均安全跳过；删列本身失败时降级为 WARNING——两列零读取方，留下的代价只是 schema 未收敛，而抛异常会让 `_run_migrations()` 直接阻断应用启动），`CURRENT_SCHEMA_VERSION` 59 → 60。**验证**：①**真库级**（`sqlite 3.50.4`，脚本 `C:\Temp\td16_v60_verify\verify_v60_real_sqlite.py`，4 段全 PASS）——v59 形态库（2 行数据 + `idx_user_favorites_user_id/status/record_id`）迁移后两列消失、行数与其余列值**逐值不变**、三索引保留；二次打开 + 直接重复调用迁移函数零副作用；无 `user_favorites` 表的库打开不抛异常；全新建库跑完 v0→v60 链无两列；②`tests/test_migrate_v60.py` **10 passed**（含"生产代码零引用"回归护栏与降级路径用例），`tests/test_migrate_v59.py`+`tests/test_migrations_full.py` **101 passed**（v59 语义不变）；③`check_schema_consistency` **EXTRA=0 / MISSING=0**（同步清理 3 处镜像生产的测试 fixture，两处历史 fixture 改由等价 `ALTER` 构造）；④`ruff` / `mypy` 全绿 | 2026-09-26 |
| **TD-19** `/status` 两态不可区分 | 原 #19。**修复（方案②，2026-09-25）**：保留端点 + 新增 `favorited: bool`（三态可辨）+ `[STATUS_API] ua/referer/path` 防御性日志（脱敏、无查询参数）。现场 v0.110.0 实测：有队列行 8 键 `favorited=true`、补建行 8 键 `favorited=true`、未收藏 4 键 `favorited=false`；日志实测 `ua=[redacted]`（敏感词整段脱敏）且无 `?`。**端点存废复评已移入「六、待决策」**（最终决定见 **TD-24**，端点已删除） | 2026-09-25 |
| **TD-24** `/api/favorites/{record_id}/status` 端点删除（#19 最终决定） | 原 #19 残留（「六、待决策」第一行，最迟第七轮）。**决定：删除**——现场日志实测**零仓外调用方**。**取证**（只读，2026-09-26）：镜像 v0.110.2；`GET /api/admin/logs/app`（admin，`docker/api/logs.py:106-122`）+ `GET /api/logs/rotated/{f}`（admin，`docker/api/logs.py:284-298`，分页读全）共读 **48428 行**，覆盖 `app.log.10` 起 **2026-09-02 11:00 → 2026-09-26 15:36**（连续无空洞）；`[STATUS_API]` 命中 **7 次**，全部落在 **2026-09-25 21:48:46～21:49:23** 同一窗口 → **UA 分布：`python-requests/2.34.0` 3、`PilotStdProbe/1.0` 2、`[redacted]` 2；referer：`http://192.168.1.18:9028/favorites` 4、`-` 3；path 全为 `/api/favorites/*/status`**。三类 UA 全为本项目自己的排查探针（`[redacted]` 是 2026-09-25 脱敏验证用 curl 探针，命中 `_SENSITIVE_MARKERS` 被整段替换），**无 curl（非探针）/扫描器/未知 UA**。**对照实证**：现场对该端点发 **1 次只读 GET**（UA `TD19-Control-Probe/1.0`）→ 200 且 app.log 中 `[STATUS_API]` 计数 7 → **8**，证明"日志机制真的生效"，即上述零命中不是日志失效造成的假阴性。**改动**：删路由 `docker/api/favorites.py`（原 222 行）+ 防御性日志辅助代码（`_log_status_api_call`/`_sanitize_header`/`_SENSITIVE_MARKERS`）+ 未再使用的 `Request` 导入；删契约测试 3 类 12 例与仅其使用的 `_FakeRequest`/`_fakeURL`/`_fake_request` 替身；`web/src/api/announce.ts` 清掉 #16 遗留的说明注释；`docs/architecture.md` 端点表删该行、v59 注记标注端点已删；`docs/testing/known-issues.md` #6 状态改「已关闭」。**证据局限**：轮转上限 10 个文件，`2026-09-02` 之前的日志已轮转丢失；窗口内有 11 天空档（`app.log.8` 起于 09-10 11:26，前一段未覆盖）——但 `[STATUS_API]` 日志自 2026-09-25 才随 v0.110.0 上线，窗口完整覆盖其全部存在期，故空档不影响结论。**残留（不擅自改，单独报告）**：`pilotstd/core/db/_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 仍称"两列的读取方是收藏状态接口"——该 docstring **在 `norm_checksum` 覆盖范围内**（实测 `raw != norm`），改动会触发 `DatabaseError: 迁移 v59 的脚本逻辑已变更`（`_migration_checksum.py:109-115`），受 P-106 约束不可改 | 2026-09-26 |
| **TD-25** 查询适配器重复加载证书包（原 #22） | **修复（2026-09-26）**：新增 `pilotstd/query/adapters/_shared_ssl.py`（进程级单例 `default_ssl_context()`，加锁保证首次只加载一次）；9 个默认校验的适配器改为 `httpx.Client(verify=default_ssl_context(), ...)`；`energy` / `sppt` / `sppt_local` 三处自签名站点**保持 `verify=False`** 不动。**根因**：httpx 对 `verify=True`（默认）的**每个** Client 都调 `ssl.create_default_context()` → `load_verify_locations()` 重新解析加载整份证书包（本机单次 ≈1.3s，cProfile 占 96.5%）。**验证**：`StandardManager()` 构造中位 **6.742s → 0.036s**（各 5 次；改后 min 0.035s，首次 0.233s 为一次性证书包加载，目标 <1.0s 达成）；查询适配器相关 8 个测试文件 **270 passed**；ruff/mypy（390 files）全绿；`check_all.sh --fast --guards --local` EXIT=0；文档同步：`docs/architecture/modules/query.md` 新增「HTTP 客户端与 SSL 复用」节（G-031 block 映射） | 2026-09-26 |
| **TD-26** 下载链无读者文档 + G-031 缺口（原 #24） | 原 #24（登记 2026-09-26，偿还窗口"最迟第十轮"）。**根因**：① `docs/` 下无描述 openstd 下载流程的现行文档——#21 修复（`532d994f` + `62fba6ef`）的三个变化点（hcno 权威来源＝openstd 搜索页、端点族 `/bzgk/std/*`、新增「全文下载页」`showGb?type=download`）只存在于代码 docstring 与台账 #21 行；② G-031 的 `DOC_SYNC_MAP` 不含 `pilotstd/download/`，该目录改动**不触发**文档同步检查。<br>**修复（2026-09-26）**：① 新建 `docs/reference/download-pipeline.md`——hcno 权威来源（搜索页逐行 `showInfo('<hcno>')`；**禁用 std_gov 的 pid**，实测 `newGbInfo?hcno=<pid>` 与空/损坏 hcno 响应**逐字节相同**，sha1 `b93e289a82d884a4`、18610 字节）、端点族 `/bzgk/std/*`（旧路径 301 → `requests` 对 POST 的 301 **退化为 GET、body 丢失** → `verifyCode` 恒被拒）、完整步骤链（详情页 → 全文下载页 → `gc` → OCR → `verifyCode` → `viewGb`，含代码行号）、`_VIEW_ROUNDS = 2` 的轮次语义（只在"验证码通过但 viewGb 取到 0 字节"时用第二轮；OCR 失败不消耗轮次）、历史事故与防回归测试清单；② `DOC_SYNC_MAP` 补 `("pilotstd/download/", "docs/reference/download-pipeline.md", "block")`（映射 11 → 12，无死映射）；③ 更正三处陈旧描述——`docs/testing/下载适配器测试方案.md`（头改 openstd + `/bzgk/std/*`；删掉**不存在**的 `tests/manual_test_download.py`（`Test-Path` = False，随 `3d16d662` 删除）改为 `pytest tests/download/adapters/test_openstd_download.py` + 手工核对清单）、`docs/testing/testing-baseline.md:37/59`（"待 P4 步骤1 / 方案锁定（待实现）"→ 已实现，依据 `openstd_download.py:175-256`）、`docs/guides/人工测试方案.md:127`（"日志为 `viewGb`（非旧 `showGb`）"→ 先走 `showGb` 全文下载页再 `viewGb` 取文件）。<br>**验证**：① **受控功能测试**（TD-13 同款）——仅暂存 `pilotstd/download/adapters/openstd_download.py` 末尾一行临时注释 → `python scripts/check_g_031_docs_sync.py` **FAIL**：`[G-031] FAIL: pilotstd/download/ 已变更，但 docs/reference/download-pipeline.md 未同步更新`、`EXIT=1`；`git restore --staged` + 还原文件后 `git status` 干净、脚本回到 `PASS: 无变更文件` / `EXIT=0`；② `python -m pytest tests/download/adapters/test_openstd_download.py -q` = **43 passed**（含 `test_query_result_pid_is_not_used_as_hcno` / `test_search_row_number_must_match` / `TestEndpointPathGuard` 三个契约测试）；③ 连带同步 `docs/governance/gates.md`（新增 v1.19 版本行 + G-031 映射条目 + 11→12 计数）与 `docs/governance/README.md`（gates.md 状态 v1.18→v1.19），并重跑 `scripts/generate_capabilities.py`；④ `ruff` / `mypy` / `check_all.sh --fast --guards --local` 全绿。**残留（不擅自改）**：`docs/governance/gates.md:234` 的 v1.16/v1.15 两行版本历史挤在同一行（缺一个行首 `|`，属既有格式缺陷，与本次改动无关） | 2026-09-26 |
| **TD-27** 迁移 checksum 自愈判定使 P-106 失效（原 #28） | **修复（2026-09-26）**：`pilotstd/core/db/_migration_checksum.py` 的自愈判定由「**当前源码** `raw != norm`」改为「**存储值 == 当前 raw**」——只有库内存的正是当前 raw 哈希（历史 raw 口径、源码未变）才 WARNING + 自愈为标准值，其余一律视为真实源码变更 → `DatabaseError` 阻断启动。**改前行为**：`norm_source()` 去缩进使任何带缩进函数恒有 `raw != norm`（实测 **59/59**）→ **任何**不匹配（含真实逻辑改动）都静默自愈、只记 WARNING，抛错分支不可达（P-106 名义生效、实际失效）。**改后行为**：① 存储值 == 标准化值 → 通过（注释/空行变化不改变标准化值——实测对注入 `#` 注释不敏感）；② 存储值 == 当前 raw → 自愈（WARNING + UPDATE）；③ 其余 → **DatabaseError 阻断启动**。**可达性证据（永久保留）**：新增 `tests/test_migration_checksum_guard.py` **6 例**，其中 `test_logic_change_raises_database_error` 断言「库内是旧逻辑的标准化哈希 + 当前源码逻辑已变」必抛错；实测原始 traceback：`DatabaseError: 迁移 v1 的脚本逻辑已变更，checksum 不匹配` @ `_migration_checksum.py:121`。`tests/test_core.py` 两条旧测试同步改写（`test_checksum_mismatch_auto_heals` → `test_checksum_legacy_raw_hash_auto_heals`，因为旧断言固化的正是本债的错误行为；`test_checksum_real_change_raises` **去掉 mock**，改用真实迁移直接触发）。**验证**：迁移+守卫相关 5 个测试文件 **222 passed**；ruff 全绿；mypy `Success: 390 files`；门禁 EXIT=0。 | 2026-09-26 |
| **TD-28** 收藏链归档期依赖周期机制 → 必然「归档超时」（原 #29） | **修复（2026-09-26）**：`pilotstd/tasks/favorite_download.py` 新增 `_archive_inbox_file()`——下载落 inbox 后**由链路自己**按**规范标准号**解析 → 交给 `archive_standards`（organizer 搬文件进标准库并 upsert `file_index`）→ 再走原有索引轮询复核；超时文案改为「文件未被归档器登记进索引（+ 归档错误原文）」。**根因（比登记时更严重）**：**没有任何调度会归档 inbox**——`auto_scan` 只 UPDATE `standards` 表（不碰 inbox）；monitor 的 `_on_file` 只调 `scan_directory`（仅解析文件名、不搬文件、不写 `file_index`，却照计 success 计数，现场 `processed_today=6 / success_today=6` 即由此而来；该计数误导与缺失归档已由 **TD-30** 修复）→ 因此等多久都不可能成功（候选「延长窗口/调调度顺序」均被证伪）。**关键口径坑**：不能用被 `_safe_filename` 转义过的 inbox 文件名解析——实测 `GB_T 5613-2026_x.pdf` → `logical_code='GB'`，而规范口径是 `'GB/T'`；用错会让「归档写入口径」与「链路查询口径」不一致、永远查不到。**改前行为**：下载成功也必然在 +60 秒判 failed（现场 6/6 复现：`收藏归档超时: favorite_id=2/1/4/3/5/106`，各在对应下载时刻 +60s）。**改后行为**：归档同步完成 → 索引命中即 `done`（不再依赖周期机制）。**验证**：① 单元 4 例（归档被调用且 `source_path` 指向 inbox 文件 / 归档异常与标准号不可解析时原因进 `error_message` / 索引已有则跳过下载与归档）；② **集成真跑端到端**（真实下载引擎 → 真 inbox → 真归档搬库 → 真 `FileIndexRepository` → 真 `_find_in_file_index` 命中 → `done`、`local_path` 指向库内、inbox 清空）；③ 契约测试固定解析口径（含「用转义文件名会退化成 GB」的反证）；④ 相关 5 个测试文件 **101 passed**；ruff/mypy 全绿；门禁 EXIT=0。**现场闭环待下次部署**（本轮按指示只做本地验证）。 | 2026-09-26 |
| **TD-29** 收藏下载链 GB 类成功率 0（`verifyCode` 恒被拒，原 #21） | **修复（2026-09-26）**：① 下载链三处流程修正（`532d994f` + `62fba6ef`）——hcno 权威来源改为从 openstd **搜索页**按标准号逐行解析（**禁用** `std_gov` 的 pid）、端点族 `/bzgk/gb/*` → `/bzgk/std/*`（旧路径 301 使 POST 退化 GET、body 丢失）、新增「全文下载页」步骤（`showGb?type=download`；缺该步时 `viewGb` 返回 200 但 0 字节）；② 归档环节见 **TD-28**。**现场验证（v0.111.2 / `ba3cb65b`，解冻后临时以 `* * * * *` 触发一轮）**：下载 **6/6 成功**——`verifyCode 结果: success` ×6（另 1 次 error 后第 2 次尝试成功）、`viewGb 第1轮取到全文` ×6、字节数 251074 / 528280 / 483415 / 470971 / 381418 / 376488、hcno 全为**搜索页实时解析值**（如 GB/T 2970-2026 `44C04018C3C0E40BE28E19DA0510F24B`，与 09-26 04:00 失败时不同）；全日志 **0 次** `301` / 缺 `showGb` / `0 字节` 痕迹 → 本条原始症状「`verifyCode` 恒被拒、成功率 0」**不再成立**。**遗留**：当时 6/6 在 +60 秒归档超时（已由 TD-28 修复并本地真跑验证；其**现场闭环待下次部署后确认**）。 | 2026-09-26 |
| **TD-30** monitor `_on_file` 从不归档却照记「成功」（原 #30） | **修复（2026-09-26）**：`pilotstd/monitor/scheduler.py::_on_file` 补上归档并改按**真实归档结果**计数——解析（`scan_directory`）→ 交**统一归档入口** `archive_standards(scanned, word_source_root=<inbox 目录>)` → `moved>0` 才记 `success`；解析不出标准号或归档器报 `failed>0` 记 `failed`；一条都没搬（源已不在/目标已存在/条目待确认）**不计成败**；`success` 不再是"文件名解析出来了"。<br>**根因（两条并存，代码实测）**：① **归档从未实现**——配置项 `monitor.auto_archive`（默认 `true`，`monitor/config.py:15` 且 `set_config` 可写）、类注释「文件就绪后触发自动归档」（`scheduler.py:54`）、日志「自动归档已禁用，跳过」三处都在描述归档，但函数体只调 `scan_directory`（**仅解析文件名**：`manager/facade/_scan.py:31-96` 不搬文件、不写 `file_index`）；`git log -S 'archive_standards' -- pilotstd/monitor/scheduler.py` **输出为空** → 自模块引入（`a11a23c7`）起从未调用过归档。② **计数语义错**——`success` 在"解析到 ≥1 条"时 +1，而前端把它显示为「成功」（`web/src/components/FileMonitor.vue:153` `{{ processed_today }} (成功 {{ success_today }} / 失败 {{ failed_today }})`）→ 面板谎报健康。<br>**现场证据**：`processed_today=6 / success_today=6`，而 6 个文件全在 inbox、`file_index` 一条都没有（这正是 TD-28 现场 6/6「归档超时」的同一时段）——"看板健康、实际什么都没入库"。<br>**与 TD-28 不重叠（实测依据）**：`handler.py:54-61` 的延迟回调在 5 秒稳定期后**先判 `os.path.exists(path)`**，而收藏链在下载返回后**立即**归档 → 文件已被链路搬走时回调根本不会触发；故 monitor 只在"文件 5 秒后仍留在 inbox"时动作，即链路归档失败或**手工投放**的场景，链路正常路径下零重叠（链路失败时反而成为兜底）。<br>**验证**：① 单元 6 例（真归档→`success`；一条没搬→**不记** `success`；解析不出→`failed` 且不调归档；归档器报 `failed>0`→`failed`；`word_source_root` == inbox 目录；归档抛异常→`failed`）；② **集成真跑 4 例**（真遍历目录 + 真 `StandardParser` + 真搬文件 + 真 `FileIndexRepository`：合规文件**真的**离开 inbox 且索引可查、源根参数正确、不合规文件留在 inbox 且记 `failed`、`auto_archive=false` 时连计数都不动）；③ **反证**（`git stash` 掉 scheduler 改动跑同一批用例）**8 failed** —— 用例确实钉住新行为而非空转；④ monitor 相关 3 个测试文件 **56 passed**；ruff / G-010 / G-012 / mypy（390 files）全绿。<br>**登记说明**：本条此前只在报告里口头提过（"`_on_file` 忽略 `auto_archive`"），**从未写入台账**（「六、观察项」5 行中无此行）；本次按用户指示正式编号补登。<br>**残留（✅ 已闭环 2026-09-26，B-1）**：原残留是「monitor 只有**文件名**可用，而被 `_safe_filename` 转义过的文件名会解析成另一个 `logical_code`（实测 `GB_T 5613-2026_000002.pdf` → `'GB'`，规范口径 `'GB/T'`）→ monitor 归档**收藏链遗留件**时索引写在 `GB` 键下、链路的 `GB/T` 查询仍查不到」。**修法（改生产者而非消费者）**：`pilotstd/tasks/favorite_download.py::_safe_filename` 把 `/` 由**转义为 `_`** 改为**直接删除**（其余非法字符 `\:*?"<>|` 仍转义），于是 `GB/T 5613-2026` → `GBT 5613-2026_000002.pdf`，而解析器的 code 映射表本就认识 `GBT→GB/T`、`GBZ→GB/Z`。**为何不在 monitor 侧补解析**：monitor 手里只有文件名，任何修补都是"猜哪个 `_` 原本是 `/`"的启发式且只修一家；改生产者后所有解析方（monitor、organizer 的 Word 重解析、人眼看 inbox）同时受益。**全量验证（真实 `_safe_filename` + 真实 parser）**：`code_mapping` 中含 `/` 的 code **124 个**——改后**往返还原 124/124**、去 `/` 后与其他 code **0 撞名**；改前为 **0/124**（`git stash` 反证同时使 3 个用例 FAILED）。边界：`GB/Z 184.1-2026`（分部号）、`GB 18047-2026`（本就无 `/`）、`JB/T` 均正确。新增契约测试 `tests/test_favorite_download.py::TestSafeFilenameRoundTrip`（3 例，数据驱动覆盖全部含 `/` 的 code，含"映射表含 `/` 的 code 少于 100 即失效"的护栏）；连带更新 3 处断言（`tests/unit/test_tasks.py:275/279`、`tests/test_favorite_download.py:37`）。验证：聚焦 75 passed；全量后端回归 + 门禁 + ruff + mypy 见提交说明。 | 2026-09-26 |
| **TD-20** `auto_archive_retry` 在 UI 不可改、不可触发 | 原 #20（登记 2026-09-25）。**修复（2026-09-25）**：①`docker/api/settings.py` 抽出 `_SCHEDULED_JOBS`（5 项，与 `scheduler.start_scheduler()` 一一对应）并补 `auto_archive_retry`；②缺键时用**当前配置值**兜底（防前端漏发把链路静默禁用）；③`SettingsTabSchedule.vue` 增加"收藏下载链（自动归档重试）"开关 + cron 输入 + 提示。**同轮自查补漏④**：`GET /api/settings` 原先不返回 `auto_archive_retry_*`——写侧可选、读侧缺失，前端只能拿组件默认值显示，保存时又把该默认值回写，用户改过的值（如 `0 6 * * *`）会被静默改回 `0 4 * * *`；已在读侧补齐两键，并加"读侧键必须与 `_SCHEDULED_JOBS` 对称 + 必须返回存值而非默认值"两例反证测试。**⑤**再补 `pilotstd/core/config/settings_schema.py` 两条 `SettingDef`（`tasks.auto_archive_retry_enabled/cron`）：e2e 字段一致性测试要求 GET 的键必须被前端 Schema 覆盖或进白名单，不注册则 `test_settings_e2e_consistency.py::test_no_unexpected_backend_only_keys` FAILED（实测）。验证：`tests/test_settings_scheduler_sync.py`（**7 passed**：任务表覆盖、scheduler 差异声明、改 cron 真重排、缺键沿用配置、health 默认值不坏、读侧键对称、读侧返回存值）——后两例在补④前用 `git stash` 实测 **2 failed**、补后 PASSED，"scheduler 差异声明"一例用注入假任务实测 FAILED；`SettingsTabSchedule.test.ts`（3 passed：字段存在、保存随载荷提交、加载回填）；`test_docker_api.py -k settings` 2 passed；`test_settings_auth/e2e_consistency/manager` 合计 21 passed；`SettingsView.test.ts` 6 passed。**现场实证（v0.110.0 / `22d4d90b`，修复前镜像）**：`GET /api/settings` 的 `tasks` 实测 8 键、缺 `auto_archive_retry_*`；同镜像 `GET /api/scheduler/status` 显示该任务已注册（next_run 04:00）；对照组 `date_reminder_cron` 现场值 `0 8 * * *` ≠ Schema 默认 `0 2 * * *` → 用户确实会改这些值，读侧缺键＝改过的值会被静默覆盖（不是理论风险）。**⑥契约细化**：现场 `GET /api/scheduler/status` 共 **6** 个 cron 任务（多一个 `auto_backup`），故 ① 里"与 scheduler 注册表一一对应"的说法不准确——`_SCHEDULED_JOBS` 只覆盖**用户可管**的 5 项，`auto_backup`（固定周日备份、无 UI 开关）为**有意排除**；新增 `test_scheduler_jobs_not_in_settings_are_intentional`：**AST 解析** `docker/scheduler.py::start_scheduler()` 的注册表，断言"未暴露的差异集合 == {auto_backup}"（注入 `fake_probe_job` 实测 **FAILED**、撤销后 PASSED）——旧测试只比对写死名单，scheduler 新增任务也不会失败，改后"漏登记"与"有意排除"才真正分得开。**部署状态（2026-09-26 00:00 实测）**：修复已随镜像 **v0.110.2** 发布（CI 全绿：`version`/`docker` job 均 success，bump 提交 `2719691b`），但**现场 `192.168.1.18:9028` 仍为 v0.110.0 / `22d4d90b`（读侧 8 键）**——该主机不会自动拉取（`docker/api/system.py:152` 的 `POST /api/system/update` 是管理员手动触发的 pull + compose 重建，无定时任务），故"读侧 8→10 键"需**部署后**复核。**✅ 部署后复核通过（2026-09-26 09:32 实测，v0.110.2 / `c421c572`）**：`/api/system/version`=0.110.2、`/api/health` build=`c421c572`；`GET /api/settings` 的 `tasks` **10 键、缺键 0**，`auto_archive_retry_enabled=True` / `cron='0 4 * * *'` 与 `/api/scheduler/status`（next_run 2026-09-27 04:00）一致——读写两侧闭环。**UI 现场复核（Playwright，v0.110.2）**：设置页「定时任务」出现"收藏下载链（自动归档重试）"行、开关为开、cron 输入框 `0 4 * * *`，且页面回填值 == 后端 `GET /api/settings` 值（截图留档 `C:\Temp\pilotstd-probe\shots\settings-schedule.png`，探针不入库）。**残留**：无"立即执行一次"按钮 → 记为可选增强（临时把 cron 改成 `* * * * *` 即可触发，等价覆盖），不进台账 | 2026-09-25 |
| **T-20（原「六、观察项」）`tests/` 运行期 `self.skipTest` 口径更正并关闭** | **R11-4 实测证伪原假设**：T-20 原登记「60 处 skipTest，语义多为 Fixture not found」被当作“运行期跳过数偏高”；实测 ① 43 个 fixture 守卫依赖的 **15 个 fixture 文件全部已入库**（`tests/fixtures/`）→ 运行期**一次也不触发**，「因缺 fixture 而跳过」= **0 处**；② 运行期真实跳过＝**本地 14 / CI 44**（静态 60 只是调用点）。**交付（仅新增，未改既有测试逻辑）**：`tests/fixture_baseline.py`（fixture 基线登记 15 项 + 守卫覆盖率判定）、`tests/skip_census.py`（运行期／静态双口径普查工具）、受控测试 10 例。**终局（用户裁定方案 A）：✅ CLOSED**——“补最小 fixture 基线”的目标已达成（0/43 需治理），继续挂窗无意义；其剩余可治理项拆为新债务 **T-29**。 | 2026-09-27 |
| **T-28（原「六、观察项」）CI 的 pytest 未开 `-rs` → 跳过明细不可得** | **R12-2 / R12-2b 修复（2026-09-27）**：`-rs` 从 `test-backend` 扩到**全部 5 处 pytest 调用**（`tests/`、`tests/gui/`（xvfb）、`tests/e2e/`、Windows GUI E2E `tests/gui/`（参数 `-m e2e`）、test-gui-unit（`tests/gui/` 与 `tests/test_regression_architecture.py`））；复核脚本列出 **5/5 均含 `-rs`**（YAML 经 PyYAML 解析）。**CI 实证**：R12-2 的 `test-backend` 日志输出 **44 条** `SKIPPED [n] path:line: reason` 明细（此前只有汇总行 `44 skipped`），与 R12-1 归因的“CI 44 skipped”完全吻合；汇总 `4007 passed, 44 skipped, 22 warnings in 130.38s`。**口径**：xdist（`-n auto`）下各 worker 各自打印短摘要、汇总可能分段，机器可读清单用 `tests/skip_census.py <日志> --json` 解析（R11-4 交付）。**终局：✅ CLOSED**（用户裁定：1 行修复、与 T-30 同批）。 | 2026-09-27 |
| **T-32（原「六、观察项」）本地 L1 快检触发式漏 `.pyi`** | **R12-4a 修复（2026-09-27）**：`scripts/check_all.sh:303` 的触发式由 `^scripts/` 或 `.py$` 改为 **`^scripts/` 或 `.py[wi]?$`**（覆盖 `.py`／`.pyi`／`.pyw`），同步更新跳过/命中提示文案与注释。**受控验证（双向）**：① 修复后暂存 `pilotstd/_t32_probe.pyi`（142 字符行）→ L1 **触发** → `E501 Line too long (142 > 120)` → `❌ [FAIL] L1 ruff check`、EXIT=1；② 修复前同一探针**可正常提交**（R12-3b 的受控失败实验即借该缺口做到“不绕过钩子”，见 7.18）。**终局：✅ CLOSED**（用户裁定：一行修复、与 R12-4 合并）。 | 2026-09-27 |


| `test_migration_runs_pending` patch 路径错误（旧簿「三、已知问题」#5 并入） | 旧簿记载：断言原先 patch 了错误的符号路径，已修正为 `database.CURRENT_SCHEMA_VERSION`。**2026-09-27 并入时复核**：现由模块级导入取真值（`tests/test_core.py:179` `from pilotstd.core.db import CURRENT_SCHEMA_VERSION`），与记载一致 | 2026-06-30（2026-09-27 自旧簿并入） |
| PyInstaller `--noconsole sys.stderr=None` 兜底（旧簿「三、已知问题」#16 并入） | 旧簿记载：`_SafeStream` 于 2026-07-09 禁用、改用原生 stderr。**2026-09-27 并入时复核**：全库 `git grep _SafeStream` 命中 **0 处代码**（仅旧簿文本残留），确认已回退 | 2026-07-09（2026-09-27 自旧簿并入并复核） |
| AppLayout.vue「空列表兜底」分支 + 其过期 TODO（#49 收尾，T-12） | **根因**：`navItems` 改为「从路由 meta 动态生成」（#49）后，仍保留一段"meta 派生列表为空时返回硬编码 10 项"的兜底，其 TODO 原文 `// TODO: Remove fallback after #49 verification - deadline 2026-08-09`（**登记到期已过 49 天**）。**实测（2026-09-27，临时 vitest 探针用真实 `router`，探针已删）**：`router.getRoutes()` 共 **21** 条记录、其中 `showInSidebar` = **11** 条；`navItems` 在 role 空 / `guest` / `unknown-role` 下 **10 项**（`/settings` 因 `permission:'user'` 被过滤）、在 `user` / `admin` 下 **11 项** → **恒非空**；另全库 `git grep addRoute` **0 命中**（纯静态路由，不存在"后加路由把列表变空"的路径）。**处置**：删除兜底分支与过期 TODO，原位写明复核结论与实测数据；同步修 `AppLayout.test.ts` 的 fixture——原 fixture 的 8 条路由**无任何 `showInSidebar` 标记**，其项数实际来自这段被删的兜底，现按真实 `router.ts` 的 meta 形态构造（含 `titleKey` / `sidebarOrder` / `permission:'user'`）。**验证**：`src/components/AppLayout.test.ts` **3 passed**；`vue-tsc` 0 错误；前端全量测试见本轮报告；G-010 `AppLayout.vue` 有效行 **434 → 420**（仍 >400，警告档个数不变） | 2026-09-27 |
| **Tech-Debt #8**（Aura text/content token 运行时同步）——代码注释编号悬空/冲突补登（T-12） | **根因**：代码注释引用 `Tech-Debt #8`（`web/src/composables/useThemeSync.ts:3/46/83/104`、`web/src/theme/aura-token-map.ts:2/29/53`，含 `hotfix(tech-debt#8)` 字样），而**主簿中长期无对应条目**——主簿 `TD-8` 是另一个主题（`test_04_large_batch_sub_buckets`，测试跳过类），两套编号撞号且互不指向。**真实指向（2026-09-27 定位）**：`docs/investigations/aura-token-sync-feasibility.md`，其标题即《Aura Token 运行时同步可行性报告（Tech-Debt #8 · P0 调研）》，内含 P0（版本策略/Token 解析链/运行时 API 边界，Playwright 实证）→ P1（映射表范围 + 组件作用域 token 实测）→ P2（运行时注入机制，"连续切换 10 次 light↔dark 无残留"验证表）三阶段结论；落地提交 `d38e88b1 fix(theme): sync Aura text/content tokens per theme (tech-debt #8 P2)` 及其后续 hotfix（`f307535a`/`7b43fd93`）。**处置**：本行即为其在主簿的正式登记（**不改代码注释**——该编号在代码与调研报告间是自洽的，缺的只是主簿这一环；编号冲突在此明确说明）；此后全库检索 `Tech-Debt #8` 可在主簿命中 | 2026-09-27（补登） |
| mypy `--no-verify` 豁免策略（旧簿「四、Mypy 豁免项」并入，**并入即作废**） | 旧簿策略原文："mypy 错误不阻断 pre-commit（使用 `--no-verify`），CI 中仍运行 mypy 但标记为 non-blocking"。该策略与现行 **G-038 历史遗留错误清零**（`scripts/check_g_038_legacy_errors.py`，判据＝"存在任何未修复的历史遗留错误"）及 **P-104**（门禁不绕过：禁止 `noqa`/`skipif`/`continue-on-error`）**直接冲突** → 策略作废；`attr-defined` 已于 2026-08-25 实测清零（旧簿同记 244→0） | 2026-09-27（自旧簿并入并判定作废） |
| 死脚本 `scripts/check_docs_sync.sh`（T-14 补登） | **根因**：自述"渐进式部署，仅提醒不阻断"，且**全库 0 调用点**（`git grep check_docs_sync` 排除自身后无命中；不在 `.husky/pre-commit`、`check_all.sh` 任何模式、CI 任何步骤）——其"源路径 → 需更新文档"提醒映射已被 CI 侧 `docs_sync_check.py` 覆盖。**处置**：`git rm`（119 行）；`gates.md` v1.31 行内对它的反引号引用同步去除。**验证**：`check_all.sh --fast --guards --local` EXIT=0；G-032 保持 13 warning 无新增 | 2026-09-27（`2014219d`） |
| `scripts/update_docs.py` 整脚本（T-15 补登） | **根因**：全库 0 调用点，五个功能均已被取代——测试数同步 → `scripts/generate_status_metrics.py`（STATUS.md AUTO-METRICS 区块）+ G-032 维度4；聚合器描述 → `pilotstd/core/notification/aggregate_buffer.py` 常量 + `docs/architecture/modules/core.md`（G-031）；技术债条目 → **T-02 已惰性化**；模块清单 → 目标文档自身 2026-08-19 即 ARCHIVED，现由 `docs/architecture/modules/*` + G-030/G-031/G-037 承担；自动 `git add` → 废弃。**处置**：`git mv` 为 `scripts/update_docs.archived.py`（**保留参考实现**），头部注释列出各函数现行承担者与历史取回方式；连带更正 2 处过时指针（`docs/DOCUMENTATION_MAP.md`、`docs/archive/specs/模块与功能清单.md` 头部）。**验证**：门禁 EXIT=0；三个改动脚本 `ast.parse` 语法 OK | 2026-09-27（`e94f8ddb`） |
| 归档件参与新鲜度 / 架构变更检查（T-17 补登） | **根因**（预防性）：`*.archived.md` / `*.archived.py` 停止维护——其 mtime 必然落后于新鲜度上限、内部链接可能指向历史路径，G-032 维度2/3 与 G-033 的架构变更判定对它们只会产生无行动价值的噪音。**处置**：`check_g_032_doc_health.py`（维度2 人工层新鲜度 + 维度3 交叉引用）与 `check_g_033_adr_integrity.py`（架构变更文件列表）新增统一 `is_archived()` 并接入。**验证（受控反证）**：`is_architecture_change("docs/architecture/technical-debt-registry.archived.md")=True` 且 `is_archived(...)=True` → 计入 **False**；对照组 `docs/architecture/modules/core.md` 与 `scripts/check_g_032_doc_health.py` 均计入 **True**（**未过度排除**）；门禁 EXIT=0、G-032 13 warning | 2026-09-27（`e94f8ddb`） |
| 技术债文档两个空章节「六、待决策」「七、清理项」（T-19 补登） | **根因**：两节唯一内容已于同轮移入「五、已接受的设计决策 · 归档并入」与「一、已清理」，保留空标题无信息价值。**处置**：删除两节；**当批刻意保留「六-B、观察项」标签**以免打断 11 处历史引用，该标签已在本批（T-22）统一收敛为「六、观察项」。**验证**：门禁 EXIT=0；章节结构复核（〇/一/二/三/三-B/四/五/六/七） | 2026-09-27（`2014219d` + 本批 `T-22`） |

### 归档并入（原格式，表头沿用原表，行文本原文未改）

来源「二、剩余台账」：

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|---|---|---|---|---|---|
| 11 | **ROI 判断** | G-010 警告区文件（拆分收益低于成本） | 见下方"现状"列出的 **3** 个文件 | ✅ 已偿还（第八轮执行完毕） | **根因**：历史累积复杂度进入 400-500 行警告区；集中拆分 ROI 低于组件碎片化风险。**现状（2026-09-26 第八轮实测 `check_g_010_code_size.py`）**：警告区 **8 个 → 3 个**，**最高有效行 487 → 438**（全部 < 450，距 500 阻断线余 **62** 行，无阻断风险）。本轮拆掉 5 个文件（原文件 → 新模块，均为逐字节搬移 + 调用点/文档同步）：`docker/api/announce_detail.py` **454 → 372**（拆出 `_announce_detail_parse.py` 92 行）；`scripts/check_g_012_comment_density.py` **457 → 311**（拆出 `_comment_lang_data.py` 159 行，仅搬数据表、逻辑零改动，用同一份 464 文件清单对照跑出**逐行一致**的 80 行输出）；`pilotstd/core/notification/_builders_batch.py` **477 → 287**（拆出 `_builders_task_results.py` 205 行，切口处 AST 实测无共享模块级符号 → 无反向依赖）；`pilotstd/core/notification/manager.py` **487 → 383**（拆出 `_manager_ops.py` 136 有效行的组合式 `NotificationOps`；首版用 Mixin 被 `tests/test_architecture_mixin_guard.py` 拦下——该守护测试禁止新增 Mixin、指定 Composition，随后改为 `self.ops.*` 并同步 7 处外部调用点）；`web/src/views/AnnounceDetail.vue` **487 → 314**（拆出 composable `useAnnounceDetail.ts` 234 行，模板/样式未改）。剩余 3 个：`pilotstd/core/db/_migrate_v16_v49.py:438`、`web/src/components/AppLayout.vue:420`（2026-09-27 删兜底分支后 434 → 420，仍 >400）、`web/src/components/NotificationConfig.vue:438`（2026-09-27 复核实测：后者由批 1 i18n 化增至 **438**，原文记 425 已过期）。**验证**：ruff 全绿；mypy 合并口径 `Success: 388 source files`；后端 270+333 tests、前端 231 tests 全过；`vue-tsc --noEmit` 零错误；每批 `check_all.sh --fast --guards --local` EXIT=0；G-031 连带文档（core.md / gates.md / README.md）与能力矩阵均已同步。**偿还窗口**：**不适用（已偿还）**。**触发式规则保留**：任一文件触及 **490** 行 → 当轮必拆；新文件新写入即受 500 行阻断档约束。**不还的代价（已消除）**：原先 5 个文件距阻断线最窄仅 13 行，任何小改动都可能撞线导致 CI 阻断；现最窄余 62 行。| 2026-08-23 |

来源「六、观察项」：

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| 拆出新模块时注释密度被稀释（G-012 ≥3%） | 2026-09-26 第八轮 #11 拆解时实测 | **根因**：拆出去的往往正好是“纯数据表/纯函数”块，说明性注释留在原文件，新模块只剩代码 → 密度天然偏低。**现状**：本轮 `_builders_task_results.py` 首版 **2.38%** 被 G-012 拦下、`pilotstd/query/adapters/gongbiaoku.py` 因拆分新增 2 行代码由 3.70% 跌到 **2.99%** 被拦（补一条注释后回到 3.70%）；TD-22 时 `_sql_schema_parser.py` 是 **1.9%**——**同一个坑第三次踩**，且都在“拆完、跑门禁”之后才暴露，等于白跑一轮。 | **✅ 已落实（2026-09-26）**：拆分清单已补一步“新模块注释密度预估”——落点 `docs/guides/refactoring-lessons.md`「五、拆分前检查项」§1（含三次实测数据表、G-012 判据口径、G-010 拆分证据与 500 行阻断档）。动手前先按 `注释行 / 非空行 ≥ 3%` 估算，不足就在新模块头部写清“拆出原因 + 分组依据”（既过门禁又是有用信息）；本项为流程改进，一次到位，**不挂偿还窗口**。**代价**：每次拆分多花约 1 分钟估算，换来少一轮返工。 |
| #23 合并前侦察未覆盖全组合（**✅ 已落实 2026-09-26**） | 2026-09-26 第八轮四分支合并时 | **根因**：合并前只做了相邻对侦察（3×4、2×1）与“各分支 × main”侦察，**漏了 3×1** —— `docs/architecture/modules/core.md` 里分支3 改 Schema 版本行、分支1 改子模块数行，两行相邻，该冲突因此未被预见，触发安全阀中止一轮。**现状**：这类冲突**不能用“取一边”解决**——两侧数值都不对（子模块数 70 / 72，实测 **73**），必须实测后重算，属需要外部事实的冲突。 | **处置（已落实）**：规则已写入 `docs/governance/development-flow.md` **§8「多分支合并流程：全组合冲突侦察」**（含规则、理由、`git merge-tree` 用法、输出要求、本轮 3×1 案例）；本条由「观察项」转为**已固化的流程规则**，不再依赖记忆。原规则内容：合并前侦察**必须覆盖全部 N×(N-1)/2 组合**（本轮 N=4 → 6 对），并在报告里逐对列出冲突文件；本项为流程改进，一次到位，**不挂窗口**。**代价**：每轮多跑几条 `git merge-tree`（秒级），换来不因未预见冲突而中止、不把“取一边”当成万能解法。 |
| #27 gates.md 版本历史两行挤在同一物理行（观察项） | 2026-09-26 第八轮文档核查时发现（**既有缺陷，非本轮引入**） | **根因**（2026-09-26 两次独立实测更正）：`docs/governance/gates.md` 版本历史表里 v1.16 与 v1.15 两个版本行被写在**同一个物理行**上——拼接处是**相邻的两个管道符 `\|\|`（字符索引 470/471），缺的是换行符**，而不是缺行首 `|`（两个 `|` 都在）；该行为单行 879 字符。**现状**（2026-09-26 实测）：缺陷在 **L235**（本轮 v1.19 加行前为 L234）；只影响该表这两行的渲染（被当成同一行多出的单元格），表内其余版本行均正常；内容无丢失、无歧义。 | **处置**：**✅ 已修复（2026-09-26，v1.20）**：两行已拆开、内容一字未改（拆后 v1.16 → L236 / 471 字符、v1.15 → L237 / 408 字符，两段拼接仍为原 879 字符，仅补入一个换行）；原位置实测 `gates.md:235`，拆后行号因同批新增 v1.20 行整体下移 1。**代价**：无。 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（只放"未清"的债）

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|------|------|------|------|--------------------------------------|---------|
| 31 | **可偿还** | ConfigManager 多实例交错写 + 查询热路径高频 IO | `pilotstd/core/config/manager.py:19-29`（`__init__` 每实例一把锁）、`:148-172`（`_load` 末尾无条件 `save()`）；`pilotstd/query/routing/scorer.py:82-96`（`get_profile` 每次新建 `ConfigManager`）；热路径调用链 `query/engine/_batch.py:75/128/149 → _batch_dispatcher.py:168 _bucket_items → _routing.py:218 _bucket_key → _routing.py:53 _resolve_base_route → scorer.py:226 get_priority_chain → scorer.py:154 score_adapter → scorer.py:96 get_profile` | ⏳ 挂窗**第十二轮**（R11-2 已裁定，见本行裁定书） | **根因**：① **锁是实例级的**——`ConfigManager.__init__` 里 `self._lock = threading.Lock()`，**没有文件锁、没有进程级单例**，两个实例可同时对同一 `config.json` 走"写 `.tmp` → `os.replace`"，属 last-writer-wins；② **每次构造都写盘**——`_load()` 在配置文件已存在时执行 `populate_defaults(FACTORY_DEFAULTS)` + `_migrate_ui_keys(self)` 后**无条件 `self.save()`**（`:170-172`），即"构造一次 = 读一次 + 写一次"；③ **热路径每次评分都构造**——`scorer.get_profile()` 内 `cfg = ConfigManager()`（无缓存），而它被 `score_adapter → get_priority_chain` 在**每条条目 × 每个候选适配器**上调用。<br>**现状（2026-09-27 探针实测，探针不入库）**：一次 mock 查询（4 条已解析条目、单 mock 适配器）——`scorer.get_profile()` **126 次**、`score_adapter()` **126 次**、`ConfigManager.__init__` 总计 **141 次**、`save()` 总计 **151 次**；对照（同文件不发起查询的测试）仅 **9 / 16 次** → 热路径占 **≈126 次构造 + ≈126 次写盘**（≈31.5 次/条目）。该路径**无任何停止检查点**（`_bucket_items`/`_routing`/`scorer` 全程无 `check_stop`），因此与 2026-09-26 的 CI GUI abort 直接相关：`test-gui-coverage` 的 faulthandler 转储里，被 GC 析构的孤儿 `QueryWorker` 正停在这一段（`scorer.get_profile → manager.py:98 save` 的重试 `time.sleep`）——即"高频 IO 既放大竞态窗口，又在配置文件目录被删除时进入重试循环"。<br>**修复方向**（未实施）：① 进程级单例/缓存（`get_profile` 复用同一实例，或由 `StandardManager` 注入）；② `_load()` 不再无条件写回（dirty 标记，仅实际变更时 `save()`）；③ 跨实例/跨进程文件锁（`os.replace` 前加锁）。<br>**偿还窗口**：**最迟第十轮（架构优化轮）**——本次仅登记，**待用户确认**该窗口。<br>**不还的代价**：① **并发丢配置**：用户刚改的站点限额 / OCR 凭据 / 开关可能被另一个实例的整份写回静默覆盖（last-writer-wins），且无日志痕迹；② **热路径 N 次文件 IO**：单次查询 ≈126 次"读+写 config.json"，查询变慢、磁盘抖动，在覆盖率插桩与慢盘（容器 overlay / 网络盘）上被进一步放大；③ **取消延迟窗口被拉长**：该段无检查点，取消要等整段跑完（与 #17a 残留同源）。<br>**R11-2 裁定书（第十一轮，2026-09-27；本轮只出裁定书，不动代码）**：<br>**① 现状量化（本轮复测，探针不入库）**：a) **单位成本**——`scorer.get_profile("std_gov")` 单次 **4.28 ／ 4.27 ／ 4.28 ms**（三次各 100 次调用的均值；同批首次 4.65 ms、更早冷启动样本 5.65 ms，一律以三次复测为准），每次调用**恰 1.00 次 `ConfigManager()` 构造 + 1.00 次 `save()`**（构造计数与真实 `save()` 计数分别打点，二者相等）；单次构造冷样本 23.6~26.4 ms（含 `_get_fernet` 防呆查库）。<br>b) **单查询量级**——`tests/test_query.py::TestQueryEngine::test_parallel_batch_query`（5 条已解析条目、2 个 mock 适配器）实测 `scorer.get_profile()` **126 次** = `score_adapter()` 126 次、`ConfigManager.__init__` 总计 **133 次**、`save()` 总计 **135 次**（本行原记"126 次构造/写盘"即此数据点，本轮复现一致）；对照同文件不发起批量查询的 `test_single_query_found` 仅 **21 ／ 25 ／ 26 次**。→ 热路径 ≈ **126 次构造 + 126 次写盘 ≈ 0.54 s／查询**，`config.json` 实测 4220 B → 单查询无谓覆盖写 ≈ **519 KiB**。<br>c) **沉淀面**——生产 `ConfigManager(` 构造点 **21 处**（`pilotstd/` 16 + `docker/` 5：`query/routing/scorer.py:96`、`docker/scheduler.py:135/281/340/367`、`core/notification_aggregator.py:106/127/260`、`core/validity_checker.py:79`、`manager/facade/_base.py:148` 等）；测试引用 **31 文件 ／ 104 行**。d) 三处结构缺陷原样：`manager.py:27`（实例级锁）、`manager.py:148-172`（`_load()` 末尾无条件 `save()`）、`scorer.py:96`（每次新建）。<br>**② 偿还方案与成本（本轮评估，未实施）**：可切三个独立提交——P1 `scorer.get_profile` 复用／注入实例（`scorer.py` + 调用方）；P2 `_load()` 改 dirty 标记（`manager.py` + `migrate.py::_migrate_ui_keys` 须回报"是否改动"）；P3 `save()` 的 `os.replace` 前加跨实例／跨进程文件锁。**成本判定：>1 commit 且连锁风险高**——P2 直接冲击"构造即写回"契约：`tests/test_core_config.py:333-340` 注释明写"ConfigManager 初始化会 save() → `_get_fernet` 防呆检查查询全局 DB"，测试须 patch 到临时空库才能构造，31 文件 ／ 104 处引用需逐个核验"构造后磁盘内容"类断言；P3 引入跨进程锁语义（`docker/scheduler.py` 与 GUI 同机并存）。**另评估并否决"只做 P1 缓存"的 1-commit 方案**：热路径零构造可省 ≈0.54 s／查询，但被缓存实例读不到其他实例（GUI 设置页 `core/config/service.py:43`）写入的配置 → 改设置后优先级链陈旧，须配套失效通知才正确，**不满足"≤1 commit 且无连锁风险"**，故本轮不顺手做。<br>**③ 转已接受的代价（若后续选择接受，量化）**：并发 last-writer-wins 静默丢配置（用户改的站点限额／OCR 凭据／开关可能被整份写回覆盖，且无日志痕迹）；单查询 ≈0.54 s + 519 KiB 无谓写盘（慢盘／覆盖率插桩下放大）；该段无 `check_stop`，取消延迟被拉长（与 #17a 残留同源）。<br>**④ 终局结论：[挂窗第十二轮]**（锚定 `v0.119.x → v0.120.0` 区间；本轮不动代码）。第十二轮必须二选一收口——按 P1→P2→P3 分期偿还（每期独立提交、独立门禁），或转「已接受」并按 ③ 写明代价。**逾期不再顺延**：该窗口自第十轮起已过期一轮，本轮已记账，**第十二轮为最终期限**。 | 2026-09-27 |
| 32 | **可偿还** | 后端状态值用中文，前端硬编码中文做比较 | 前端比较点（**13 处**，2026-09-27 实测；自批 0 起加 `i18n-allow`）：`web/src/views/PendingView.vue:62/63/64`、`web/src/views/StandardsStatusView.vue:64/65/66`（筛选 `value`）+ `:70/71/72`（颜色判定）、`web/src/views/QueryHistory.vue:42-43`、`web/src/components/WechatTrustIP.vue:172-173` + `:229-230`（批 2 新发现并加豁免）、`web/src/api/http.ts:158-159`（原文记 9 处/行号 `PendingView:60-62`、`StandardsStatusView:66-68`、`QueryHistory:40`、`WechatTrustIP:168` 均已过期，且漏登 `WechatTrustIP:229-230`）；后端产出点：DB 默认值 `pilotstd/core/db/_migrate_v2_v15.py:22/47`（`status TEXT NOT NULL DEFAULT '现行'`）、公告匹配 `pilotstd/announcement/matcher.py:220/223/225`、时效检查 `pilotstd/core/validity_checker.py:97/205/231/234`、查询适配器 14 个（`pilotstd/query/adapters/`）+ 归一化表 `pilotstd/query/search_strategy.py:195-205`、统计 `pilotstd/manager/standard_service.py:20-25/70-72`、索引统计 `pilotstd/core/_file_index_query.py:81`、管道路由 `pilotstd/pipeline/router.py:173/187`、微信 IP 哨兵 `pilotstd/manager/wechat_ip_service.py:144`；对外 API：`docker/api/standards.py:17`（`_VALID_STATUSES = (现行, 已废止, 未知)`）、`docker/api/pending.py:35`、`docker/api/query.py:78` | ⏳ 挂窗**第十二轮**（R11-2 已裁定，见本行裁定书） | **根因**：① 状态是**自由字符串**，无枚举/无常量表——值由适配器、公告匹配器、时效检查器、DB 默认值四处**各自独立**产生；② 前端只能硬编码中文与之比较（**13 处**，2026-09-27 实测；原文记 9 处），一旦这些文案被翻译，比较立即失效；③ 统计链路把 `废止` + `被代替` 合成 `已废止`（`standard_service.py:70-72`），而查询链路直接透传 `废止` → **同一语义两种拼写**；④ 哨兵值混入数据字段——`wechat_ip_service.py:144` 用 `"未知"` 表示「当前无公网 IP」，前端必须比较这个中文哨兵才能决定标签颜色。<br>**现状（2026-09-27 实测；口径＝用 `tokenize` 排除注释与 docstring 后，只数「内容恰为状态值之一」的字符串字面量，探针不入库）**：① 后端生产代码（`pilotstd/` + `docker/`）**248 处 / 50 文件**，值分布：现行 60、废止 57、已废止 27、被代替 26、未知 26、即将实施 21、作废 19、待确认 7、过期 5；② 测试 **456 处 / 65 文件 / 277 个测试函数**（最多 `tests/test_validity_checker_full.py` 55 处、`tests/test_query.py` 28 处、`tests/test_standard_service.py` 27 处）；③ **无统一枚举**：重复定义 **7 处**、**4 种不同写法**（`_EXPIRE_STATUSES` ×5：`manager/classifier.py:26`、`manager/facade/_organize.py:186`、`facade/_query.py:33`、`facade/_query_subsystem.py:48`、`organizer/mover.py:35`；`ABOLISHED_STATUS_TOKENS` ×1：`core/notification/_format_utils.py:10`；`_VALID_STATUSES` ×1：`docker/api/standards.py:17`），差异在是否含「过期」；④ **口径不一致实测**：`废止`（查询/待确认链路）vs `已废止`（时效检查 + 统计链路）、`未知` vs `待确认`；⑤ **前端死分支**：`PendingView.vue:60-61` 比较的 `'Active'` / `'Withdrawn'` 后端**从不返回**——后端只有反向归一化（`search_strategy.py:203/205` 把上游英文译成中文）。<br>**偿还窗口**：**最迟第十轮（架构优化轮）· 待用户确认**（与 #31 同窗——同为后端契约/结构级改动，需与其他破坏性改动同批排期）。<br>**不还的代价**：① **i18n 永远无法收口**——英文界面下前端仍在用中文值做判定，这 9 处只能永久挂在 `i18n-allow` 上（批 0 已如此处理），i18n 专项的"清零"目标结构性不可达；② **口径不一致直接产生状态判定 bug**——同一标准在不同页面可能被判成不同状态（`废止`/`已废止` 由两条链路产出）；③ **后端契约不稳定**——中文值改动会**静默**破坏前端（无类型/编译期保护），而 248 处产出点 + 456 处测试断言意味着改动成本随时间**单调上升**；④ 中文值**已落库**（`file_index.status DEFAULT '现行'`），数据量增长后迁移成本只增不减。<br>**修复方向（未实施）**：后端统一英文枚举（`active` / `upcoming` / `withdrawn` / `superseded` / `expired` / `pending` / `unknown`），落库改英文并加迁移脚本；对外 API 只输出枚举；前端做「枚举 → i18n key」映射（三语文案走 `web/src/locales/`），展示层不再出现字面量。<br>**R11-2 裁定书（第十一轮，2026-09-27；本轮只出裁定书，禁止代码变更）**：<br>**① 现状量化（本轮复测）**：生产 **248 处 ／ 50 文件**、测试 **456 处 ／ 65 文件**（tokenize 口径复跑一致，值分布 现行 60 ／ 废止 57 ／ 已废止 27 ／ 被代替 26 ／ 未知 26 ／ 即将实施 21 ／ 作废 19 ／ 待确认 7 ／ 过期 5）；前端比较点 **13 处**（带 `i18n-allow` 豁免）。**容器定义点本轮更正为 9 处 ／ 5 个名字**（旧记"7 处"偏低：原探针未解包 `frozenset(...)` 漏计 2 处）——`_EXPIRE_STATUSES` ×5（`manager/classifier.py:26` 4 值、`manager/facade/_organize.py:186` 5 值、`manager/facade/_query.py:33` 4 值、`manager/facade/_query_subsystem.py:48` 4 值、`organizer/mover.py:35` 5 值）、`ABOLISHED_STATUS_TOKENS` ×1（`core/notification/_format_utils.py:10`，5 值）、`EXPIRED_STATUSES` ×1（`ui/core/handlers/auto_flow_engine.py:18`，3 值）、`_EXCLUDED_FROM_OVERRIDE` ×1（`ui/core/handlers/query_flow_engine.py:30`，4 值）、`_VALID_STATUSES` ×1（`docker/api/standards.py:17`，3 值）→ 同一"废止／过期"语义 **5 种写法、值集 3~5 个不等**。<br>**② 偿还路线图（四阶段，每阶段独立可停、独立提交）**：<br>**A 阶段（枚举落地，不改调用方）**——范围：新建 `pilotstd/core/status.py`（`Status` 枚举 + `废止`→`已废止` 别名归一 + 9 值↔英文 key 双向映射），把上述 9 处容器定义改为引用它（**容器取值不变**，零行为变化）。依赖：无。验收：新增 `tests/unit/core/test_status.py`（9 值全量 round-trip、别名等价、与 9 处旧容器取值集合逐一等价断言）；`check_all.sh --fast --guards --local` 与 `--deep` 全绿；生产字面量数仍为 248（证明零行为变化）。规模 1~2 commit。<br>**B 阶段（后端收敛）**——范围：逐模块把 248 处字面量改为枚举引用：先 `pilotstd/query/adapters/` 14 个适配器 + `query/search_strategy.py:195-205` 归一化表，再 `manager/standard_service.py:20-25/70-72` 统计口径，再 `core/validity_checker.py` ／ `announcement/matcher.py` ／ `pipeline/router.py`；**对外 API 输出仍为中文**（避免同批破坏前端 13 处比较点）。依赖：A。验收：每批 diff 只替换字面量、无逻辑改动；`pytest tests/ -k "query or validity or standard or adapter"` 全绿；G-040 零新增；生产字面量计数逐批下降并登记（目标 ≤20）。规模 3~5 commit。<br>**C 阶段（API 契约层 + 落库迁移）**——范围：`docker/api/standards.py:17` 的 `_VALID_STATUSES` 由枚举派生，`docker/api/pending.py:35`、`docker/api/query.py:78` 同步；DB 默认值 `core/db/_migrate_v2_v15.py:22/47` 的中文值加显式迁移脚本与版本记录（**不改写历史迁移函数源码**，遵循 P-106）；前端 13 处比较点改"枚举→i18n key"映射，展示层不再出现字面量。依赖：B。验收：新增状态取值契约测试（取值集合、`废止`／`已废止` 归一后一致）；`check_i18n_key_count.py` 三语叶子键对齐 PASS；前端 `npm run test` 全绿且 `i18n-allow` 豁免 13 → 0（若保留须逐条写明理由）。规模 1~2 commit。<br>**D 阶段（测试收敛）**——范围：456 处测试字面量改为枚举／常量，**保留 ≥3 处"直写字面量"用例**作为真实数据回归哨兵。依赖：C。验收：测试字面量 ≤50；`pytest tests/` 全绿；覆盖率不低于基线。规模 2~3 commit。<br>**路线图合计 7~12 commit、跨 ≥3 轮；A 阶段为纯增量，可先单独落地。**<br>**③ 转已接受的代价（若选择不再偿还，量化）**：i18n 结构性无法收口（13 处前端中文比较点永久挂在 `i18n-allow` 上，i18n 专项"清零"目标不可达）；`废止`／`已废止` 双拼写使同一标准跨页判定不一致（统计链路 `manager/standard_service.py:70-72` 与查询链路出口不同）；248 + 456 处产出点无类型保护，改文案静默破坏前端；中文值已落库（`file_index.status DEFAULT '现行'`），迁移成本随时间单调上升。<br>**④ 终局结论：[挂窗第十二轮起分阶段偿还]**——**A 阶段须在第十二轮（锚定 `v0.119.x → v0.120.0`）落地**；B~D 允许跨轮推进，但每轮至少推进一步并在本行登记进度。若第十二轮结束时 A 仍未落地，则本项**当轮直接转「已接受」并按 ③ 关闭**，不得第三次顺延。 | 2026-09-27 |
| 34 | **可偿还** | EventBus 单例 `reset()` 在非主线程未完全退出时销毁 QObject → Windows 原生访问违例（CI `test-gui-unit` 间歇红） | fixture：`tests/gui/test_event_bus_integration.py:28-68`（`_reset_event_bus` / `_wait_for_threads`）；被测代码：`pilotstd/ui/core/event_bus.py:57-88`（`reset()`，崩溃点 `:64` `QMutexLocker`）；受影响 CI job：`test-gui-unit` → step `Run GUI unit tests` | ✅ 已接受（第十一轮 R11-2 裁定：保留 R1；哨兵＝复发 ≥1 次即当轮翻案，见本行裁定书 ③c 与「六、观察项」T-26） | **根因（机制未实证，以下为推断）**：`reset()` 的 `QMutexLocker(cls._lock)` 进入处崩溃，而该行本身不做任何 Qt 对象操作 → 更像"**堆已被破坏**"而非锁本身错误。最贴合现有注释与代码的路径：teardown 的"等非主线程退出"用的是 `threading.enumerate()` 启发式，**看不到 Qt 内部线程 / QThreadPool**，2.0s 到期后仍继续 `reset()` → `cls._instance = None` 销毁那个 `QObject` 单例，而其它线程可能仍在 `publish()`（`QMetaObject.invokeMethod` + `Q_ARG(object, …)`）或已排队的 `deliver` 中引用它 → 原生层 use-after-free。**关键证据（faulthandler 转储，两次逐行同构）**：`Windows fatal exception: access violation` → `pilotstd/ui/core/event_bus.py:64 in reset` → `tests/gui/test_event_bus_integration.py:44 in _reset_event_bus` → `_pytest/fixtures.py:1014 _teardown_yield_fixture`（即**崩溃在 teardown 的 reset，不是用例断言**），且两次都紧跟 `TestThreadSafety::test_publish_from_worker_thread PASSED` 之后约 2.1s、都报在 `test_concurrent_subscribe FAILED`。<br>**现状（2026-09-27 实测）**：① **复发 3 次**——`fc51a6f3`（2026-08-05 `reset() 同步屏障防止测试竞态`）→ `47709e48`（2026-08-25 `serialize EventBus tests via xdist group & wait threads before reset (CI Access Violation)`）→ **2026-09-26、2026-09-27 各复发一次**，历史两次修复**都是测试侧序列化/等待，未触根因**；② **频率 ≈1/40**（API 统计最近 40 次 run：全绿 31、`test-gui-unit` 单独失败 2 次、其余为 `test-gui-coverage` 5 次与 `test-frontend` 2 次）；③ **本地未复现**——`python -m pytest tests/gui/test_event_bus_integration.py` 连跑 6 次全 13 passed / EXIT=0，全量 `tests/gui/ tests/test_regression_architecture.py`（CI 同口径，`PILOTSTD_GUI_TEST=1`）**997 passed / EXIT=0**；④ **环境差异**（可能是不复现的原因）：本地 Python 3.14.2 + PyQt6 6.11.0 / Qt 6.11.0；CI Python 3.12.10 + PyQt6 6.11.0 / **Qt 6.11.2** / sip 13.12.0；⑤ 证据局限：崩溃是原生层，Python 侧只剩 faulthandler 栈，**无更细的时序证据**（"堆已破坏"无法从 Python 侧进一步证实）。**run 链接**：`36218068788`（2026-09-26，sha `cdc308f3`，**批 6 之前**）、`36293074107`（2026-09-27，sha `71e70054`）。**R1 后首个 CI 数据点（2026-09-27）**：run `36294447160`（sha `e31615a7`）**全绿、12/12 job success**——`test-gui-unit` success，且上一轮被连带跳过的 `test-gui-coverage` / `version` / `docker` / `exe` 均**真实执行并通过**；该数据点仅证明**本轮未触发**，不构成根除（观察延续到第十轮判断）。<br>**修复方向**：**R1（已做，`c78cbd89`）**测试侧兜底——teardown 等待上限 2s → **5s**、补 `QThreadPool.globalInstance().waitForDone(2000)` 与主线程 `processEvents()`，且**到期未静止就不再 `reset()`**（把清理留给下一次 setup），直接掐掉"竞态窗口内销毁 QObject"这条路径；**R2（未做）**根因侧——`reset()` 加"静止协议"（`_resetting` 期间 `publish()` 直接返回、`BlockingQueuedConnection` 仅在主线程调用时使用、单例销毁改 `deleteLater()` 或延迟到 in-flight publish 结束）；**R4（未做）**对齐 CI 环境复现（装 Python 3.12 + Qt 6.11.2，循环跑 `tests/gui/` 统计频率）把推断升级为实证。<br>**偿还窗口**：① **R1 已还（2026-09-27）**；② **第十轮（架构优化轮）做最终判断**——若 R1 落地后到该轮之间 CI **零复发** → 保留 R1 并转「已接受（ROI 判断）」；**触发式提前**：期间**再复发 ≥1 次** → **当轮必须做 R2 + R4**，不得再用测试侧序列化搪塞。<br>**不还的代价**：① CI 间歇红率 ≈1/40，每次都要人工拉日志甄别；② **单次代价远大于 1/40**——一次 GUI 抖动会**连带阻塞** `test-gui-coverage` / `version` / `docker` / `exe` 四个 job（2026-09-27 实测即如此：该 4 个 job 全部 skipped），即踩一次就推迟一次发布；③ 历史两次"修复"均未触根因，同类复发会持续消耗排查时间（本次定位耗时即为实例）。<br>**R11-2 裁定书（第十一轮，2026-09-27）**：<br>**① 现状量化（本轮取数，GitHub API 全量 73 run）**：`test-gui-unit` 历史失败 **3 次**——`3298b530`（2026-09-13，run `34740071019`）、`cdc308f3`（2026-09-26，run `36218068788`）、`71e70054`（2026-09-27，run `36293074107`）。**R1（`c78cbd89`，2026-09-27T04:26:43Z）之后共 14 个 run：`test-gui-unit` 14／14 success**（其中 11 个 run 12／12 job 全绿；另 3 个 run `e94f8ddb`／`73a35ed5`／`f1e55d4a` 因第十轮 E501 事故被 ruff 拦下、连带 skipped 4 个 job，但 `test-gui-unit` 本身 success）。连带阻塞实测：09-26 那次 `test-gui-unit` 失败 → `version`／`docker`／`exe` **3 个 job skipped**；09-27 那次（与 `test-backend` 同批失败）→ `test-gui-coverage`／`version`／`docker`／`exe` **4 个 job skipped**。**统计效力声明**：历史基率 ≈1/40（2.5%），在 1/40 基率下"连续 14 次零复发"的概率 ≈70% → **14／14 不足以证明根因消除**，只满足本行预先约定的接受判据（"R1 落地后到该轮零复发 → 保留 R1 并转已接受（ROI 判断）"）。<br>**② 偿还方案与成本（未做的 R2／R4）**：R2 根因侧——`reset()` 加静止协议（`_resetting` 期间 `publish()` 直接返回、单例销毁改 `deleteLater()` 或延迟到 in-flight publish 结束），需改 `pilotstd/ui/core/event_bus.py:57-88` 并核验 `tests/gui/` 全部事件总线用例（13+ 例），估 1~2 commit；R4 环境对齐——CI 装 Python 3.12 + Qt 6.11.2 循环跑 `tests/gui/` 把推断升级为实证，需改 `.github/workflows/ci.yml` 并占用 CI 时长，且本地无 Qt 6.11.2（装环境 ≥1 轮）。合计 **>1 commit**，且 R2 触及发布／订阅公共路径（`publish`／`deliver` 语义变更），**不满足"≤1 commit 且无连锁风险"**，故本轮不顺手做。<br>**③ 转已接受的代价（量化）**：a) **残余风险未消除**——14／14 的样本量不足以排除 2.5% 基率，最坏情形仍会间歇红，而一次 GUI 抖动即连带阻塞 3~4 个下游 job（`test-gui-coverage`／`version`／`docker`／`exe`，本轮实测数据见 ①），踩一次推迟一次发布；b) **R1 属测试侧兜底**（teardown 等待 2s → 5s + `QThreadPool.globalInstance().waitForDone(2000)` + 主线程 `processEvents()`，且**到期未静止就不 `reset()`**）——残余表现为"该次清理被推迟到下一次 setup"；若未来出现**跨用例状态串味**（而不是单个用例自身断言失败），即为该兜底失效信号，须回到 R2；c) **哨兵（保留有效）**：**再复发 ≥1 次 → 当轮必须做 R2 + R4**；每轮复核"R1 之后的 run 统计"（本轮数据点 = 14 run／14 success／0 复发）。<br>**④ 终局结论：[转已接受+代价]**——保留 R1，不再投入 R2／R4，按 ③ 记账；哨兵（复发 ≥1 次即当轮翻案）写入「六、观察项」继续有效。本行**仍留在「二、剩余台账」作为裁定书载体**，不再作为待偿还项排期。 | 2026-09-27 |

> **2026-09-27 结构重整**：已闭环的 **#11**（✅ 已偿还）移入「一、已清理 · 归档并入」；**#15 / 17b**（✅ 已接受）移入「五、已接受的设计决策 · 归档并入」。本节现只列**未清**项（#31 / #32 / #34）。
>
> **2026-09-27 裁定补记（第十一轮 R11-2）**：三行均已写入**裁定书**（现状量化／偿还方案+成本／转已接受的代价／终局结论）。**#31 / #32 仍属未清**（[挂窗第十二轮]／[挂窗第十二轮起分阶段偿还]）；**#34 已裁定为 [转已接受+代价]**——按用户指定“裁定书载体＝本节对应条目”而**仍列在本节**（不迁往「五」），其复发哨兵另登记于「六、观察项」**T-26**。

---

## 三、维持现状（E2E 兜底，不再拆解）

以下文件经审查为纯 Qt 控件构建，无可提取业务逻辑。**停止底层拆解**，仅通过 E2E 测试覆盖：

| 文件 | 物理行数 / 有效行数 | 内容特征 | 策略 |
|------|------|---------|------|
| `pilotstd/ui/core/handlers/_settings.py` | 426 / 371 | QTabWidget/QGroupBox/QFormLayout 构建 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_theme_ops.py` | 142 / 109 | QIcon/QTranslator/QStyleSheet 管理 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py` | 263 / 209 | QTreeWidget+QMenu+QThread 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_export_ops.py` | 143 / 116 | QFileDialog+QTextEdit+QTableWidget 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_dialog_ops.py` | 51 / 39 | QFileDialog 封装，零业务逻辑 | E2E 兜底 |

> **2026-09-27 口径标注（T-11）**：原表"行数"列填的是**物理行数**（426/142/263/143/51），而「五 #5」同一批文件填的是**有效行数**（371/109/209/116/39，G-010 口径）——两处**都正确但口径不同**，此前未标注导致并列看似矛盾。本表改为两口径并列（2026-09-27 实测值），「五 #5」仍用有效行数。

**策略**：关注增量——未来若沉淀复杂业务逻辑（如动态对比度计算、复杂联动校验），再考虑局部提取。

**2026-08-25 审计**：原 `_theme.py`/`_file_tree.py`/`_export.py`/`_file_dialog.py` 已随 Handler 重构删除（`d1c12253` 创建 `main_window/parts/*_ops.py` 等价物，`cfb166fe` 清理旧文件），`_settings.py` 361→426 行；策略不变。

---

## 三-B、i18n key 一致性检查（TD-3 详情）

> 状态：✅ 已实施（2026-07-29）——`scripts/check_i18n_key_count.py` 落地并接入 CI（ci.yml `i18n key count & alignment check` step，WARN 50 / FAIL 60）。本节保留为方案说明与历史记录。

- **触发阈值**：单个 locale 文件的顶层 key 数量 ≥ 60（当前 3 文件顶层 key 各 15 个，脚本 WARN_THRESHOLD=50 / FAIL_THRESHOLD=60）
- **推荐工具**（按优先级）：`i18n-check`（vue-i18n 专用 CLI）→ `vue-i18n-extract`（从源码提取缺失 key）→ 自研脚本（遍历 JSON key 树做 diff）
- **当前卡点**：自动化检查已落地（对齐检测 + 数量阈值），PR 模板中的人工项保留为兜底
- **实施注意事项**：需排除 `home.pending` vs `nav.pending` 这类同名不同层级 key；按完整路径 diff；zh-TW.json 与 zh-CN.json 结构一致可作对齐参照

---

## 四、已跳过测试（分类：环境依赖）

> 2026-09-27：旧簿「一、已跳过的测试（13 条登记）」已**逐条并入**下表（旧簿归档为 `architecture/technical-debt-registry.archived.md`，不再维护）。
> 下表为旧簿 **2026-09-21 快照**逐字保留；其中"已删除"类条目的**实测更正**与"未登记跳过点补登"在本轮 Commit 3（T-10）执行，届时本表将刷新为实测口径。

| # | 测试 | 文件:行号 | 原因 | 分类 | 处理方式 |
|---|------|-----------|------|------|---------|
| 1 | `test_gb_exact_match` | `test_e2e_adapters.py:42`（TestE2EStdGov，原 :28） | 外部 API (std_gov) 返回空 `match_status` | E2E 网络依赖 | 2026-06-30 添加 `@unittest.skip`（现 :40-41 为 `skipIf(_CI)` + `skip`） |
| 2 | `test_hg_exact_match` | `test_e2e_adapters.py:118`（TestE2EHbba，原 :103） | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest`（:97 `skipIf(_CI)`） |
| 3 | `test_cold_start_pending` | `test_e2e_adapters.py`（原 :239，已不存在） | ahbz 未登录状态 | E2E 认证依赖 | 2026-08-25 审计：测试已删除；TestE2EAhbz（:234）重构为 `test_gb_exact_match`/`test_sh_exact_match`/`test_iso_exact_match`，`skipIf(_CI)` 网络防护保留 |
| 4 | `test_sh_exact_match` | `test_e2e_adapters.py:104`（TestE2EHbba，原 :300） | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest`（:97 `skipIf(_CI)`） |
| 5 | `test_split_pdf_pages` | `test_ocr_fallback.py:38`（fixture skip）/ `:56`（def，原 :39） | 无可用 OCR provider | 环境依赖 | `pytest.skip` 在 setup/fixture 中（非函数内） |
| 6 | (sparse file) | `test_scanner.py:502`（原 :472） | 系统不支持此场景文件 | 平台依赖 | 原有 `self.skipTest` |
| 7 | `test_e2e_dialog` | `tests/gui/test_e2e_dialog.py`（旧簿记"已删除"） | DialogHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除（Handler/Mixin dual-track 清理），由单元测试间接覆盖 |
| 8 | `test_e2e_file_tree` | `tests/gui/test_e2e_file_tree.py`（旧簿记"已删除"） | FileTreeHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除，文件树操作由 `test_file_tree.py` 覆盖 |
| 9 | `test_e2e_settings` | `tests/gui/test_e2e_settings.py`（旧簿记"已删除"，**实测文件仍在且有 `@pytest.mark.skip`**） | SettingsHandler 由 SettingsDialog 独立创建 | 架构重构 | 旧簿记为历史条目；实测更正见 T-10 |
| 10 | `test_e2e_table` | `tests/gui/test_e2e_table.py`（旧簿记"已删除"） | TableHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除，表格操作由 `test_table.py` 覆盖 |
| 11 | `test_e2e_settings_io` | `tests/gui/test_e2e_settings_io.py`（旧簿记"已删除"，**实测文件仍在且有 `@pytest.mark.skip`**） | SettingsConfigIO 是 SettingsHandler 内部组件 | 架构重构 | 旧簿记为历史条目；实测更正见 T-10 |
| 12 | `test_e2e_theme` | `tests/gui/test_e2e_theme.py`（旧簿记"已删除"） | ThemeHandler 纯 Qt 控件操作 | 架构重构 | `cfb166fe` 删除，应用主题由 MainWindow 初始化路径覆盖 |
| 13 | `test_e2e_table_helper` | `tests/gui/test_e2e_table_helper.py`（旧簿记"已删除"） | TableHelperHandler 不在 MainWindowCore 中 | 架构重构 | 旧簿记为历史条目，表格操作由 `test_table.py` 覆盖 |

**旧簿处理策略（逐字保留）**：#1~#6（外部 API/环境依赖）E2E 测试保留在本地开发时手动运行，CI 环境自动跳过。#7~#13（架构重构）旧簿称对应测试文件均已不存在：其中 #7/#8/#10/#12（dialog/file_tree/table/theme）由 `cfb166fe`（Handler/Mixin dual-track 清理，删 8 个死 Handler/Mixin 文件 + `tests/gui/test_e2e_*.py` 6 个测试）删除；#9/#11/#13（settings/settings_io/table_helper）旧簿称不在删除集合中、为历史条目。功能均由对应单元测试间接覆盖。

**2026-09-27 实测更正（T-10）——"已删除"的表述不准确**：`tests/gui/` 现存 **11 个 `test_e2e_*.py`**（`test_e2e_announce/auto/cleanup/download/persistence/project/query/query_summary/scan/settings/settings_io`），并非"均已删除"；其中 **2 个**带无条件跳过标记——`tests/gui/test_e2e_settings.py:19`、`tests/gui/test_e2e_settings_io.py:17` 的 `@pytest.mark.skip`。CI 的 GUI job 是用 `--ignore-glob="*test_e2e*.py"` **排除**它们，而不是因为文件不存在。上表 #3 的"测试已不存在"同样需以此为口径理解（`test_e2e_adapters.py` 该用例本体已删）。

**2026-09-27 实测（跳过点总量与机制分类，全库 `tests/` 扫描）**：跳过标记共 **102 处**，按机制分布如下——本节只**逐条登记"环境依赖"类**（条件跳过中与外部站点/平台/CI 环境相关者），其余运行期跳过属"本地 fixture 未就绪"的运行期防护，仅给总量与代表文件，不逐条登记（不属技术债）：

| 机制 | 处数 | 文件数 | 性质 / 是否逐条登记 |
|---|---|---|---|
| `@unittest.skipIf(_CI, …)` | 18 | 7 | **环境依赖（CI 无外网）** → 属本节口径（网络类 E2E） |
| `@pytest.mark.skipif(…)` | 10 | 4 | **环境依赖（平台/长路径）** → 属本节口径 |
| `@pytest.mark.skip`（无条件） | 10 | 4 | 架构重构类（含 2 个 `tests/gui/test_e2e_*.py`）+ 单测快照类（`tests/unit/…`，`依赖 HTTP/线程` 的原因写在 reason 里） |
| `@unittest.skip`（无条件） | 1 | 1 | `test_e2e_adapters.py:41`（外部 API 不稳定） |
| `pytest.skip()`（运行期） | 3 | 3 | 运行期防护：`test_ocr_fallback.py:39`（无 OCR provider，**属本节口径**）、`test_i18n_key_count.py:27`（脚本缺失时整模块跳过）、`stress_winui.py:107`（需外部驱动传参） |
| `self.skipTest()`（运行期） | 60 | 10 | **运行期防护**：多为适配器/查询测试的 `Fixture not found`（本地未跑 Task 0 采集 fixture），非环境依赖债务 |
| **合计** | **102** | — | — |

**本节"环境依赖"口径下、原文漏登的跳过点（2026-09-27 实测，逐条补登）**：

| 文件:行号 | 机制 | 原因 |
|---|---|---|
| `tests/test_manager.py:96` / `:114` / `:132` / `:244` / `:375` | `@pytest.mark.skipif(os.environ.get("CI") == "true", reason="离线 CI 环境无外部网络…")` | 需真实外网，CI 跳过（本地/集成环境运行） |
| `tests/test_file_utils.py:62` / `:77` | `skipif(sys.platform != "win32")` | Windows 长路径特性，仅 Windows 适用 |
| `tests/test_file_utils.py:249` | `skipif(sys.platform != "win32")` | 文件移动权限行为在 Linux 下不同 |
| `tests/gui/test_file_tree.py:31` | `skipif(sys.platform != "win32")` | Windows-only：需多盘符 |
| `tests/unit/manager/organize/test_mirror.py:166` | `skipif(sys.platform != "win32")` | 长路径前缀 `\\?\` 仅 Windows 支持 |
| `tests/test_i18n_key_count.py:27` | `pytest.skip(..., allow_module_level=True)` | 门禁脚本缺失时整模块跳过（防御性） |
| `tests/stress_winui.py:107` | `pytest.skip(...)` | 需 `stress_driver.py` 传入 `--source --step1 --step2` |

**分类说明**：以上均为**环境依赖**（外部站点不可达 / 缺少 OCR provider / 平台不支持 sparse file 或长路径 / CI 无外网），代码侧无解，因此保留在本节、不挂偿还窗口。运行期 `self.skipTest()` 的 60 处（10 文件）**不属**本类——其语义是"本地 fixture 未采集，本次跳过该断言"，在具备 fixture 的环境会真实执行。

---

## 五、已接受的设计决策（8 条，每条含不还的代价）

> 2026-09-27：旧簿「二、已接受的设计决策」8 条已并入——其中 #1~#5 与本表原有 5 条同源（不重复），**#6 JWT_SECRET 固定默认值**、**#7 内存会话存储（无持久化）** 为本表原先缺失者，已补为下表 **#6/#7**；
> 旧簿「三、已知问题」#6 **WebSocket 广播无用户级路由** 属"已接受"性质，补为下表 **#8**；旧簿 #8（`__init_tr` 命名）为"已修复"，属「一、已清理」性质，不计入本表。

| # | 决策 | 日期 | 依据 / 根因 | 现状（实测） | 不还的代价（已接受） |
|---|------|------|-------------|--------------|----------------------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | 邮件投递依赖外部 SMTP 凭据与可达性，维护成本高于收益；当时 4 个 IM/Push 渠道已覆盖全部使用场景 | `pilotstd/core/notification/channels/` 仅 `wechat/feishu/dingtalk/telegram` + `base.py`，**无邮件实现**（2026-09-26 实测） | 无法用邮件接收通知；若将来只有邮件可达（如服务器所在网络屏蔽 IM 渠道），通知会全部落空——届时应重新评估解除黑名单 |
| 2 | 静态 API 令牌不支持过期 / 无 TTL | 2026-06-25 / 2026-07-16 确认 | 令牌由环境变量注入、供仓外脚本调用，加 TTL 会引入"脚本半夜失效"的运维面 | 无外部 API 调用场景；令牌落库存哈希（本轮拆出 `docker/_static_token.py`，`api_keys.key_id='pst_static'`） | 令牌一旦泄露即**永久有效**，无法通过过期收敛风险；当前无外部 API 调用场景，代价暂不可见，但一旦对外开放需先补 TTL/轮换 |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 一次性拆分 400+ 行文件会引入大面积行为风险；按"触及即拆 + 到期必拆"分批 | **2026-09-27 复核实测**（`check_g_010_code_size.py`）：警告档（>400 且 ≤500）**3 个**、阻断档（>500）**0 个**，最高有效行 **438**（`pilotstd/core/db/_migrate_v16_v49.py` 438 / `web/src/components/AppLayout.vue` **420**（同日删兜底分支后 434→420）/ `web/src/components/NotificationConfig.vue` 438）；第八轮已拆 5 个文件（`check_g_012_sql_schema.py` 497→139、`docker/auth.py` 490→394 等）。原文记"降至 8 个、剩余最高 487"已过期 | 警告区文件长期存在，有一次性阻断 CI 的风险（500 行硬线）；**明细与偿还窗口见台账 #11**（本行不重复登记） |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | 单文件 >500 行阻断 G-010，且大文件难以定位；Mixin 组合可在不改变对外 API 的前提下切分 | 已产出 12 个 `*_ops.py`（main_window/parts 等）+ 3 个 `_builders_*.py`（notification）；本轮另新增 `_sql_schema_parser.py` / `_static_token.py` 两个"逻辑层"模块 | 拆分后的 Mixin 组合增加一层间接（读代码需跳转 `_xxx_ops.py`），且 `super()`/MRO 顺序成为隐式契约；换来的是单文件可控，代价可接受 |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | 这 5 个文件只做控件构建与信号接线，无业务算法，拆解收益低于碎片化成本 | 实测有效行：`_settings.py` 371、`_file_tree_ops.py` 209、`_export_ops.py` 116、`_theme_ops.py` 109、`_file_dialog_ops.py` 39（均 <400，不进警告区） | 只靠 E2E 兜底、无单元测试；若内部沉淀出业务逻辑而未被发现，回归只能靠 E2E 抓，代价是缺陷定位更慢 |
| 6 | JWT_SECRET 固定默认值（不设环境变量则进程内随机） | 2026-06-30（2026-09-27 自旧簿并入） | 令牌签发密钥由环境变量注入，服务重启后 token 不一定失效；环境变量覆盖有最高优先级 | **实测**：`docker/auth.py:39` `SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(32)` —— **未设环境变量时每次进程启动随机生成密钥**（重启即全体会话失效）；设了则长期固定 | 显式设置 `JWT_SECRET` 时密钥泄露无法靠重启收敛（须手动轮换环境变量）；不设置时反而更安全，但每次重启强制重新登录——两种取舍都已接受 |
| 7 | 内存会话存储（无持久化） | 2026-06-30（2026-09-27 自旧簿并入） | 简单够用；重启后需重新登录是预期行为 | **实测**：`docker/session_store.py` 存在，会话仅存于进程内存 | 进程/容器重启即全体掉线需重新登录；多副本部署无法共享会话（横向扩容前必须先引入 Redis 等外部会话存储） |
| 8 | WebSocket 广播无用户级路由（广播到所有连接） | 2026-06-25（2026-09-27 自旧簿并入） | 当前为单用户部署，全局广播够用 | **实测**：`pilotstd/core/notification/manager.py:88` `__init__(config, db, user_id, ws_broadcast=None)`、`:114` `self._ws_broadcast = ws_broadcast` —— 管理器只**保存**调用方注入的广播回调，仓内未见按 `user_id` 过滤广播的代码 | 多用户场景下通知会投递到所有在线连接（当前单用户无实际暴露）；一旦多租户/多账号上线，必须先补按 `user_id` 路由，否则存在通知越权可见风险 |

### 归档并入（原格式，表头沿用原表，行文本原文未改）

来源「二、剩余台账」：

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|---|---|---|---|---|---|
| 15 | **ROI 判断** | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`core/notification/manager.py:118-135`（`_aggregate_enabled` 为真时在实例内新建）；管理器创建点：`core/notification/manager.py:87`（`NotificationManager.__init__`）；门面创建点：`manager/facade/_base.py:87`（`BaseFacade.__init__`）→ `:250`（`_init_services` 内新建）、`:271`（`_init_notification` 配置变更重建，调用方 `docker/api/notification.py:133`）；**`StandardManager()` 构造点本轮 AST 重测 = 生产 12 处 + 测试 22 处**：`docker/manager.py:16`、`cli/commands/_shared.py:19`、`core/task_status.py:76`、`monitor/scheduler.py:146`、`services/favorite_chain_processor.py:164/307`、`tasks/date_reminder.py:141`、`tasks/favorite_download.py:137/165/194/306`、`ui/main_window/parts/_actions_ops.py:49`；测试 `tests/test_manager.py`（20 处）、`tests/test_scanner.py:576`、`tests/test_e2e_adapters.py:277` | ✅ 已接受（本轮正式关闭） | **根因**——聚合器生命周期绑在门面上，不是"忘了单例"：`NotificationManager.__init__` 按 `_aggregate_enabled`（`core/config/defaults.py:79` 默认 true）在实例内新建 `NotificationAggregator`（`manager.py:128`），并把 `self._send_now`（绑定方法）作为回调传入；`StandardManager()` 每次都在 `_base.py:250` 新建 `NotificationManager`，故聚合器**每构造一个门面就多一个**。**现状**（本轮实测，代码树 = `62fba6ef`）：① 构造点口径由上一轮的 9 处更正为**生产 12 处 / 测试 22 处**（AST 遍历 `Call.func.id=='StandardManager'`，口径含 `docker/` 与 `cli/`）；② 逐条通知路径**仍在**（上一轮"已消除"的说法需修正）——`tasks/favorite_download.py:282` 的 `notify=False` 只在**批量链路**（`docker/app.py:160` → `services/favorite_chain_processor.py:320 process_chain(notify_per_record=False)`）由源头抑制为"每次运行 1 条汇总"，但 `services/favorite_chain_processor.py:307 _notify_abandoned` 是**无条件逐条**发（`notify` 闸只作用于 `:249` 那处），`favorite_download.py:306` 的独立 `StandardManager()` 每次下载也照建；③ 探针实测（临时探针已删）：连建 2 个 `StandardManager`，`m1.notification_mgr.aggregator is m2...` = **False**，3 次逐条 `send_event` 后**每个实例缓冲恒为 1 条**且无跨实例合并；同一个共享聚合器入队 3 条则缓冲深度 3、`shutdown()` 时 flush **1 次**（成对验证）。**偿还窗口**：**不适用（已接受）**。**不还的代价**（已接受，量化）：① 聚合失效的实测代价≈**0**——生产链路源头按批汇总（一次运行 1 条汇总），Web/定时侧本就持有长生命周期门面（`docker/manager.py:12` 进程级单例；`monitor/scheduler.py:142` `self._mgr` 缓存），仅"每条 abandoned/每次下载失败"这类低频通知退化为**延迟 window（默认 5s，`defaults.py:83`）+ 渠道请求各 1 次**；② "构造开销"经本轮实测**最轻**：`NotificationManager()` 构造（含凭据迁移 + 渠道初始化 + 聚合器）中位 **0.62 ms**（n=5：0.58/0.60/0.62/0.64/0.76，`aggregate_enabled=true`），即每次通知多 ~0.6 ms；门面构造的大头不在聚合器——`StandardManager()` 单次 **8.17 s（中位）**，`cProfile` 显示 **8.18 s / 8.27 s（98.9%）** 落在 `ssl.create_default_context → load_verify_locations`（9 个查询适配器各建一个 httpx client；本机实测裸 `httpx.Client()` ≈ **810 ms**、裸 `ssl.create_default_context()` ≈ **52 ms**），与本条无关，属另一条待登记线索；③ 因此**不还的代价 = 上述 ~5 s 通知延迟 + 每事件 ~0.6 ms + 未来交互型高频通知的限流余量**（历史上 Telegram 429 的 56% 拒收由逐条发送触发，已由源头按批汇总消除，本条不再重复计）。**为何不做单例化（代码级理由）**：聚合器的 `sender_func` 捕获的是**首个入队管理器的** `_send_now` → 闭包其 `_db`/`_ws_broadcast`/`_user_id`/`_channels`；共享聚合器会让"最后入队者"决定全部缓冲消息的收件身份（跨库写 `notification_log`、跨用户发消息）；且缓冲分组键只有 `event_type`（`aggregate_buffer.py:65` `_buffers`），**没有按 `user_id` 分桶**，共享即把不同用户的消息合并成 1 条——这是当前结构刻意避开的用户绑定洞。共享整个管理器又新增状态竞争面：`_init_notification`（`_base.py:271`，`docker/api/notification.py:133` 调用，`tests/test_notification_api.py:86/107` 断言）要求配置变更后拿到**新**管理器，单例后已绑定旧单例的代码读不到新配置。**代价**：12 处生产构造点（8 文件）+ ≥3 个测试文件、22 处测试构造需改，且新引入跨库绑定 + 跨用户合并两类正确性问题。**结论**：**不改**——实测收益≈0、成本高且会引入更严重的正确性洞；未来若出现交互型高频通知，正确方向是核心库层继续不做进程级可变全局，由应用层持有门面生命周期（复用 `docker/manager.py:12` 的应用级门面）让交互路径共享，而非把用户绑定绑在首个入队者身上。 | 2026-09-21 |
| 17b | **技术无解** | 卡死线程无法安全终止 | CPython / Qt 层面 | ✅ 已接受 | **根因**：CPython **没有**安全强杀线程的机制（`PyThreadState` 清理、GIL、锁状态无法安全回滚）；`QThread.terminate()` 是唯一 API，但会在持锁/写文件时中断线程，造成数据损坏与析构期崩溃（正是 CI `test-gui-coverage` 失败的原因，`54bd565d` 已全部移除）。**现状**：7+1 处调用点统一走"断信号 → 置停止标志 → `requestInterruption()` → `wait()` → 超时保活"，无任何 `terminate()`。**偿还窗口**：**不适用（技术无解，已接受）**——只能保活等待或人工重启容器。**不还的代价**（已接受）：卡死线程在进程退出前不释放其连接/句柄/线程栈；若发生在下载/归档链路，需要人工重启容器才能恢复，且日志里只留线索（已由 17a 的计数与 error 升级提供）。 | 2026-09-25 |

来源「六、待决策」：

| 项 | 来源 | 现状 | 决策依据 | 最迟 |
|---|---|---|---|---|
| `POST /query`（admin SQL 端点）权限边界过宽 | 2026-09-25 巡检时实测；2026-09-26 第九轮机制复核 + 只读探针实测 | **端点**：`docker/api/admin_db.py:180-182`（router 无 prefix，`docker/app.py:317` 也无 prefix 挂载 → 真实路径就是 `POST /query`；审计标签 `/api/admin/db/query` 是错误字符串，`:176`/`:253`）。**鉴权**：只有 `@require_role(ADMIN_ROLE)`（`:181`）；`/query` 不在 `/api/` 下，被 `docker/auth.py:336-338` 白名单放行 → **完全不经鉴权中间件**：无会话存储校验（`auth.py:407`）、无 CSRF 校验（`auth.py:410-414`）、无 Origin/Referer 校验（`auth.py:387-397`），因此登出/改角色都不撤销。静态 API Key 通道对本端点**无效**。**表白名单**：`_ALLOWED_TABLES`（`:25-34` = standards/favorites/notification_log/task_execution_history/users/user_preferences）**只**在 `DROP TABLE` 分支被引用（`:110-116`，全库 grep 零其他引用点），且名单里的 `users` 反而被允许删除；名单里的 `favorites` 是**不存在的表**（实际是 `user_favorites`，`pilotstd/core/db/_migrate_v31_plus.py:207`）→ 真收藏表不受保护。**读**：SELECT 无任何表/列限制（可 `PRAGMA table_list` 枚举全库 schema）；`LIMIT 1001` 包装（`:126-128`/`:216-217`）只在语句里没写 LIMIT 时生效，截断判定在 `:244-248`。**写**：INSERT 无约束；UPDATE/DELETE 仅要求含 WHERE（`:119-121`，`WHERE 1=1` 即算通过）；CREATE/ALTER 无约束；仅 `DROP DATABASE` 硬拒（`:106-107`），多语句由 sqlite3 单语句限制兜住。**审计**：只落 `audit_logs` 表（`pilotstd/core/audit.py:26-51`），detail 含 **SQL 全文 + params**（`:251-261`），但 `user_id` **恒为 NULL**（中间件在白名单分支 `docker/auth.py:424-425` 提前 return，从未注入 ContextVar）→ **有 SQL、无操作人**；`admin_db.py` 除 `:21` 未使用的 module logger 外无任何日志调用，故 **app.log 零痕迹**（D2 取证结论） | **决定：① 维持现状 —— ✅ 已接受并关闭**（2026-09-26 第九轮）。**接受理由**：① 这是本仓唯一"免 SSH 的运维通道"，且是现场文档明写的既定通道——部署验证 `SELECT MAX(version) FROM _schema_version` 注明"无专门端点，用管理员 SQL 端点"（`docs/deployment/README.md:74-79`/`:101`）；2026-09-25 的补建与纠错（`INSERT rowcount=8` + `UPDATE 36 行`）就是靠它完成（本文档 `:231-250`）；只读巡检中三张未公开表的维度也只能靠它（本文档 `:210-214`/`:262`，公开端点确实不暴露——`docker/api/favorites.py:252-257` 的 `_DOWNLOAD_FIELDS` 只有 4 列，导出 SQL `:364-374` 不含 `favorite_downloads.standard_no`/`announcement_record.standard_type`/`download_queue.*`）。② 选项②按原措辞收益与成本不成比例：SELECT 限 6 张白名单表会**直接打断上面的部署验证步骤**（`_schema_version`/`user_favorites`/`favorite_downloads`/`announcement_record`/`download_queue` 全不在名单内），而名单里的 `users` 又**保留了口令哈希的读取**，安全收益只剩"写"这一半；并且实测证明拦截必须是"**正向仅允许 SELECT**"——黑名单式"禁 INSERT/UPDATE/DELETE"会漏掉 `ATTACH DATABASE`/`VACUUM INTO`/`PRAGMA`/`CREATE`/`ALTER`。③ 管理员对同一库本就有等价能力：容器内 `python -m sqlite3` 可用（本文档 `:188`）且运维者有宿主权限，收紧只抬高本仓运维成本，不改变有宿主权限者的能力边界。**不还的代价（写实）**：**一份有效 admin JWT 泄漏 = 内网内全库读写 + 容器文件系统任意写**——可 `SELECT password_hash, salt FROM users` 离线爆破、`UPDATE users SET role='admin'`、`DELETE ... WHERE 1=1` 批量删、`VACUUM INTO` 导出全库副本、`ATTACH`/`CREATE` 落文件；且**登出或改角色都不撤销**，暴露窗口 = JWT 有效期 **2 小时**（`docker/auth.py:44`）；事后**无法归因**（`audit_logs.user_id` 恒 NULL、app.log 零痕迹）。**已生效的缓解**：仅内网监听、cookie `httponly`+`samesite=strict`（`docker/auth.py:234-241`）、无 CORS 中间件（跨站脚本过不了 `application/json` 预检）、未设 `JWT_SECRET` 时重启即轮换密钥（`docker/entrypoint.sh:6-9`）。**若将来重开**：按"正向仅允许 SELECT + 补全真实全表名单 + 单独开只读端点 + 修审计归因"另立方案并先获批（R-012） | ✅ 已接受并关闭（2026-09-26 第九轮；依据：只读探针 5 组实测 + 仓内 grep 零生产调用方 + **现场 `audit_logs` 只读取证**（该端点不写 app.log，唯一留痕是审计表；2026-09-26 经 `POST /query` 只读查得）：`DB_QUERY` **247 条**、跨度 **2026-08-06 02:14 → 2026-09-26 11:26**、分布 9 天（09-13 64 / 09-26 63 / 08-22 45 / 08-29 33 / 08-06 23 / 08-23 20 …）；SQL 形态**全部为本仓运维/调查类**（`notification_log` 计数、`user_preferences` upsert、`sqlite_master` 读 schema、`standard_info_cache`、`_schema_version`、`user_favorites` 状态统计、`task_execution_history`）；真实写操作仅 3 条 DELETE（2026-08-29 02:37 清理测试收藏 id=37 及其队列行）与 `INSERT OR REPLACE user_preferences`，**无 ATTACH / VACUUM / DROP 的真实调用**（早先形态计数是探针自身 SQL 文本的自匹配，非真实调用）；`user_id` **247/247 全为 NULL** → 有 SQL、无操作人，无法归因到具体调用方，但**无任何外部/异常形态痕迹**） |

来源「六、观察项」：

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| 单条网络请求/大文件 IO 内部仍不可中断（#17a 后残留） | 2026-09-26 #17a 偿还时实测 | **根因**：worker 侧检查点只能落在"处理单元之间"（回调/循环体）；`requests` 的单次 `send()` 与 `resp.content` 整块读取无法从外部打断，要中断必须把网络层改为"分块读 + 每块查停止标志"，并把停止标志从 UI worker 一路传到适配器/会话层。**现状**：单条不可中断窗口 = 该请求的超时值——查询/公告 `network.DEFAULT_TIMEOUT = 15s`（`pilotstd/query/network.py:17`）、下载 `viewGb` 显式 `timeout=120`（`pilotstd/download/adapters/openstd_download.py:262`，旧登记写 `:114` 是请求头所在行，勘误）、SQLite `busy_timeout=5000ms`（`pilotstd/core/db/database.py:200/211`）。即：worker 现在能在"下一条"立刻停（实测 6–60ms），但若正卡在一条请求里，最坏仍要等该请求超时 | **✅ 已接受（ROI 判断，2026-09-26 收尾轮闭环）**。**实测上界（逐层）**：查询 `safe_request` 单次 `session.request(timeout=…)` 15s（`query/network.py:114`）；下载前置请求 30s×3（搜索页 `openstd_download.py:141` / 详情页 `:196` / 全文下载页 `:218`）、验证码 15s×2（`img` `:325` / `verifyCode` `:374`）、`viewGb` **120s**（`:262`）；SQLite 锁 5s；每请求前随机延迟 ≤3s（`download.max_delay`）。**取消延迟不累加**：`check_stop` 的检查点落在 `on_result`/`on_progress`（`ui/workers/download.py:52/62`），而请求超时会让 `adapter.download` 直接返回 → 当轮即抛 `WorkerAborted` 退出；故最坏 = **当前在途请求的剩余超时**（查询 ≤15s、下载 ≤120s），不是各请求相加。**穿透成本（为何不做）**：需 7 处传停止标志——① `ui/workers/download.py` 造 abort 回调；② 门面 `manager/facade/_download.py:89 download_stream`；③ 引擎 `download_single`/`download_batch`/`fetch_bytes`（另含 `run_paced_batches:301` 的 15s 批间睡眠、`_execute_retry_batch:186` 的 2s/4s 退避）；④ 适配器基类 + `openstd_download.py:262-278` 改 `iter_content` 分块读并逐块检查；⑤ 查询侧 `query/network.py::safe_request`（**10 个查询适配器共用**）；⑥ `core/file_utils.py:168 safe_move` 分块复制；⑦ 测试 + G-031 文档同步（`docs/reference/download-pipeline.md`、`docs/architecture/modules/query.md`）。估算 **150–300 行**，远超"<100 行可控"阈值，且要动 10 个适配器共用的网络层。**两处确无时间上界的实情（更正旧表述"都有明确上界"）**：① `viewGb` 用 `resp.content` 整块读（`:278`），`timeout=120` 是**空闲**超时（urllib3 按 socket 读操作计时），慢速滴流可把总时长拖到无界；② `safe_move` 的 `shutil.copy2`（`file_utils.py:208`）与目标同名时的**两次**全文件 `sha256`（`:187`）均无超时，随文件大小线性增长（标准 PDF ≤1MB → 毫秒级；把大体积 Word/模板镜像到慢速网络盘才会变分钟级）。**接受理由**：上界虽非严格（滴流/大文件两例），但**都不是永久卡死**——超时或读完即当轮退出，无连接/句柄泄漏（requests 异常路径关闭 socket），无状态损坏、无脏数据。**不还的代价（已接受，量化）**：极端情况（站点半死不活）下用户点"取消"后，查询最坏等 **15s**、下载最坏等 **120s** 才退出，期间表现为"界面已取消但线程仍在"，不再触发保活/疑似卡死告警；大文件归档复制期间取消需等本次复制完成（与文件大小成正比）。**本条闭环。** |
| `_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 过时 | 2026-09-26 第八轮 #19 删端点时发现 | **根因**：该 docstring 写“两列的读取方是收藏状态接口（`docker/api/favorites.py` 的 `get_favorite_status`）”，而 `GET /api/favorites/{id}/status` 已于 #19 删除；两列本身也已被 v60（`_migrate_v60_drop_favorite_retry_columns.py`）`DROP COLUMN` 删除 → 该描述**双重过时**。**现状（2026-09-26 只读实测）**：`norm_source()`（`pilotstd/core/db/_migration_checksum.py:42-59`）只丢弃空行、以 `#` 开头的注释行、以及行首缩进；docstring 是字符串字面量，**整段保留在 checksum 输入内**——同一函数只改 docstring 一个字，`compute_checksum`（`:33-39`）与 `norm_checksum`（`:62-69`）**均变化** → “改注释不改 checksum”不成立。**同时更正原登记的两处推断**：① 原证据 `compute_checksum != norm_checksum` 与 docstring 无关——`norm_source` 每行都做 `line.strip()`（缩进被移除），故 `MIGRATIONS` 全部 **59/59** 个迁移函数 `raw != norm` 恒成立；② 原称“改动会触发 `:109-115` 的 `DatabaseError` → 生产库直接打不开”**未复现**：`:96` 的自愈分支必然命中，实际后果是**告警日志 + 运行时静默 `UPDATE _schema_version.checksum`**；`:109-115` 抛错分支只在 `tests/test_core.py:351-373` 用 mock 令两者相等时可达。 | ✅ **已决定（不改）**：docstring 确实过时，但它在 checksum 输入范围内，改动会让每台已执行过 v59 的库在下次打开时静默改写 `_schema_version.checksum`（P-106 禁止手动同步该值），为一行注释换来对生产库的无谓写入与校验状态漂移，收益 < 成本。**不挂窗口**：若未来 v59 因其他原因必须动（或该 checksum 机制被修正），顺手把 docstring 改为“两列当前无读取方且已于 v60 删除（原读取方 `/api/favorites/{id}/status` 已于 #19 删除）”。**代价**：仅阅读迁移源码的人会被这句过时描述误导，不影响运行。 |

---

## 六、观察项（不属"债"，登记待观察）

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| #33 TaskView.vue 距 G-010 警告线仅 1 行（观察项） | 2026-09-27 批 3 i18n 化后 `check_g_010_code_size.py` 实测 | **现状**：`web/src/views/TaskView.vue` 有效行 **397 → 399**（批 3 i18n 化：`import { useI18n }` + `const { t } = useI18n()` 各 +1），距 G-010 警告线（**>400**）**仅 1 行**。G-010 为两档制——**>400 仅警告、>500 才阻断**，故越线**不阻断 CI**；但越线后此后每次改动都会带一条警告，稀释警告信噪比。**位置**：`web/src/views/TaskView.vue`（有效行 399）。 | **处置**：**下次动该文件时顺手拆分**（局部重构即可，不需专项、**不挂窗口**；候选切口：模板里的"任务历史 + 历史详情"块可拆为子组件）。**代价**：暂不处理时，若某次改动越线，仅多一条 G-010 警告（不阻断），但会让"警告区"多一个长期住户。 |
| `tests/` 受控测试不在本地门禁路径 → 改门禁脚本/基线时无法被拦住（观察项） | 2026-09-27 批 6 推送后 CI `test-backend` 失败时定位 | **根因**：`scripts/check_all.sh` 只有 `run_docs()` 才调 `pytest`（`check_all.sh:144`，且 `--ignore=tests/gui/`）——**`--fast` 与 `--deep` 都不跑 pytest**；pre-commit 钩子（`.husky/pre-commit`）只跑 `--fast --guards --local`；只有 CI 的 `test-backend` job 才跑 `tests/`（`python -m pytest tests/ -q --tb=short -n auto -p no:pytest-qt … --ignore=tests/gui/`）。于是"改门禁脚本/基线"这类改动的**受控测试**（`tests/test_check_i18n_hardcoded.py`）在本地**结构上不可能被触发**。**现状**：批 6 把 G-040 存量基线从 16 条清零为 0 条（只剩表头），`tests/test_check_i18n_hardcoded.py:245` 的 `assert baseline, "基线文件缺失或为空"` 断言"基线非空"这一**隐含前提**被打破 → CI `test-backend` 失败（run `36293074107`：`1 failed, 3972 passed`），**而本地 `check_all.sh --fast --guards --local` 连跑两次全绿**（G-040 只跑门禁脚本本体，不跑其受控测试）。本地确定性复现方式：`python -m pytest tests/test_check_i18n_hardcoded.py -x -q` → `1 failed, 18 passed`。 | **处置**：① 该用例已改为"断言**基线文件存在**（允许为空）+ 空基线时 `beyond` 捕获全部"，并补 1 条回归用例证明"空基线 ≠ 门禁失效"（任务 A，`49748c19`，现 **20 passed**）；② **流程补强（未实施，本任务明确不改脚本）**——下次改门禁脚本或基线时，本地自查清单追加 `python -m pytest tests/test_check_i18n_hardcoded.py -q`；或评估让 `check_all.sh` 检测到 `scripts/i18n_hardcoded_baseline.txt` 变更时自动跑该受控测试（属门禁变更，需单独决策，届时会连带 G-031 文档同步）。**不挂窗口**。**代价**：自动化落地前，每次改门禁/基线都靠人工记住这条自查，漏掉就红一次 CI 并浪费一轮排查（本次即为实例：从推送→拉日志→定位→修复多花一轮）。 |
| `pilotstd/query/engine/_batch.py` 溢出回收逻辑部分内联（旧簿「三、已知问题」#3 并入） | 旧簿 2026-06-30 登记（严重度低，部分缓解） | **旧簿原文**：溢出处理已委托 `_overflow`；`query_batch_parsed` 已废弃；关联的纯逻辑提取已完成——AutoFlowEngine（7 测试）+ ScanFlowEngine（31）+ AnnounceFlowEngine（20），共 3 Engine / 58 单元测试，2026-07-16 标记完成。**2026-09-27 并入时复核**：`_batch.py:22 from ._overflow import OverflowHandler`、`:55 self._overflow = overflow` —— 委托关系仍成立；`query_batch_parsed` 在 `_batch.py` 内已无引用 | **✅ 无新增行动（并入留痕）**：属"部分缓解"的历史记录，现存代码即委托实现；保留在此以便将来再动 `_batch.py` 时对照。代价：无（**不挂窗口**） |
| 数据库迁移链顺序依赖（v7 需 `file_index` 表先存在）（旧簿「三、已知问题」#4 并入） | 旧簿 2026-06-30 登记（严重度低，已缓解） | **旧簿原文**：已添加 `try/except` 守卫。**2026-09-27 并入时复核**：`file_index` 由迁移链自身创建（`pilotstd/core/db/_migrate_v2_v15.py:15 _migrate_v2_add_file_index`），后续迁移按 `CURRENT_SCHEMA_VERSION` 顺序执行 → 该依赖是**链内固有顺序**，不再是外部风险；未逐一定位旧簿所称的 `try/except` 守卫点（无行动项，不为此投入） | **✅ 无新增行动（并入留痕）**：迁移顺序由链保证；保留记录以免将来重排迁移顺序时踩坑。代价：无（**不挂窗口**） |
| `pilotstd/announcement/_attachment_parser.py:104` 的 `TODO(P2)`：`.doc`（OLE2）不被支持（T-12 登记） | 2026-09-27 代码层 TODO 盘点（全库仅 3 类真实 TODO，另 2 类见下与「一、已清理」） | **现状**：注释原文——`# TODO(P2): .doc（OLE2）格式 python-docx 不支持，需另寻解析器（如 antiword/textract）或显式跳过标记`；其所在 `except` 分支只做 `logger.debug("DOCX 解析失败: %s", e)` 后 **返回空串**（`:105-107`）→ 公告附件若是 `.doc`（OLE2），正文会被**静默解析为空**（无用户可见提示） | **处置**：登记为观察项，**不挂窗口**（无用户反馈、无数据支撑 `.doc` 附件占比）。**触发条件**：出现 `.doc` 附件解析需求时，按"引入 `antiword`/`textract` 解析器"或"界面显式标注不支持"二选一评估。**代价**：该类附件正文静默缺失，需人工察觉 |
| `web/src/views/HomeView.vue:17` 的 grid-layout-plus workaround（T-12 登记） | 2026-09-27 代码层 TODO 盘点 | **现状**：`:13-17` 注释记录——库内微任务调度器（he/Ze）与 Vue 响应式队列不同步，动态切换 `isDraggable` 时 GridItem 的 interact.js 拖拽监听器不重绑；现以 `layout.value = [...layout.value]` 克隆数组强制 GridItem 重新挂载绕过（`watch(() => appStore.dashboardLocked, …)`）。依赖版本 `web/package.json:22` `"grid-layout-plus": "^1.1.1"`；本轮**未做升级动作**，故 workaround 是否仍必需**未复评** | **处置**：保留 workaround，登记为观察项；**触发条件**：升级 `grid-layout-plus` 时复评（删克隆 → 浏览器实测锁定/解锁后拖拽是否仍生效）。**不挂窗口**。**代价**：每次锁定切换多一次数组克隆 + GridItem 重挂载（可忽略）；风险是库升级后行为变化时，workaround 可能掩盖新问题 |

| `docs_sync_check.py` 严格模式：当前为**告警期**（T-16 登记） | 2026-09-27 深挖 + 修复（`bf1a8521`） | **根因（四重失效，实测）**：① **8 条触发规则全部是死代码**——`_match_trigger_rules` 用字典字面量做 arity 分派（`{3: fn(a,b,c), 2: fn(a,b), 1: fn(a)}.get(n)`），Python 先求值三个调用 → 每次都有 TypeError 被 `except` 吞掉（对照实验：旧写法 8/8 规则异常；新写法 `feat:/fix:` 与源码变更两条正常触发）；② 只读 `git diff --cached`（CI 全新检出恒空 → "无暂存区变更，跳过"）；③ `main()` 所有路径 `return 0`（**永不阻断**）；④ 设计动作是调用 `claude` CLI 自动改写文档（`AUTO_FIX_DOCS` 默认 true）。**现状**：已修复 arity 分派 + 新增变更来源回退链（`--range` → `DOCS_SYNC_RANGE` → `--base`/`BASE_BRANCH` → 暂存区 → `origin/main...HEAD` → `HEAD~1..HEAD`；三点范围与全 0 SHA 正确处理）+ `--strict`（只判定、**不改文档**，强制 `auto_fix=False` 满足 CI 离线前提）；CI 步骤 `Docs sync check` 改为 `--strict` + `AUTO_FIX_DOCS=false` + `DOCS_SYNC_RANGE=before..sha`。**实测**：`--strict --range 5b859064..71e70054` 报出未同批更新的 `CHANGELOG.md` 且 **EXIT=0**；同范围 `--strict-block` **EXIT=1**。 | **处置（告警期，暂不阻断）**：**切换阻断的条件 = 连续 3~5 次提交误报为 0**（**计时自 R11-3 重新开始**——两次归零：第十轮的 6 次「告警期观察」因 CI 步骤实际跑的是形近脚本 `check_docs_sync.py` 而**全部无效**；R11-1 之后那 1 次（run `36304263963`）因 `DOCS_SYNC_RANGE` 右端为空、范围恒空而无效——两次都见 T-25 与其 R11-3 补丁）。**首个有效数据点＝R11-3（run `36306309371`，2026-09-27）：范围正确解析 `30de04e4..6434578c`、报出 2 项真实未同步（`docs/development.md` 工作流规则 + `CHANGELOG.md` feat/fix 规则）、误报 0 → 累计 **1／3~5**（用户 2026-09-27 批准记入）**；**切换方式 = 把 `.github/workflows/ci.yml` 的 `Docs sync check` 步骤中 `--strict` 改为 `--strict-block`（一行，两个脚本各自切换）**，此后未同批更新入库文档即 exit 1。**代价（告警期）**：规则义务面较宽（`feat:/fix:` → `CHANGELOG.md`；任意源码变更 → `STATUS.md`；Handler/Mixin 类增删 → `architecture.md` + 本主簿；`.py` 增删 → 模块清单；workflow → `development.md`），阻断期开启后每次提交需同批更新对应文档；观察期内只打印不拦。 |
| 本地 `vitest run` 偶发「汇总全绿但 exit=1」（T-21 登记） | 2026-09-27 两次实测（批 6 一次、Commit 4 前一次） | **现状**：两次均为 `Tests 297 passed (297)` 而进程 **exit=1**；第一次仅保留输出尾部（未捕获完整日志），第二次立即重跑并捕获全量输出 = **exit 0 且无 `Unhandled`/`Errors` 段**，随后累计 **5 次连跑全绿**。**CI 未受影响**：`test-frontend` 在最近多次推送均 success。 | **处置（决策：挂起观察）**：**不挂窗口**；**触发条件 = 再次出现时立即保存完整 stdout/stderr**（`npx vitest run *> log.txt 2>&1`）以便定位（候选原因：teardown 未处理错误 / 下游管道提前关闭）。**代价**：偶发红灯需人工复跑甄别（本地≈2/12 次全量运行，CI 侧 0 次）。 |
| `.py` 变更的快速 lint 未覆盖 → 本地全绿、CI 连红三次（T-24 登记） | 2026-09-27 第十轮 CI 事故复盘 + 用户裁定（分层落地） | **根因**：ruff/mypy 只在 `check_all.sh --deep` 与 CI 中执行，**不在 pre-commit 的 `--fast` 口径内**，且各机 PATH 不保证存在 → 归档件超宽行（E501：362 / 256 / 201 / 185 字符）未被本地拦住；CI `test-backend`（Ruff check blocking）与 `repo-compliance`（G-038）双双失败，**连带 skipped `docker`/`exe`/`version`/`test-gui-coverage`**（run `36300484047`、`36301031251`、`36301267833`；已于 `fed654ea` 修复，run `36301687032` 全绿 12/12）。**现状（分层）**：**L1 ✅ 已落地**——`--fast` 下若暂存变更含 `scripts/` 或 `*.py`，自动增跑 `ruff check pilotstd/ docker/ tests/ scripts/` + `mypy pilotstd/ docker/`（与 G-038 同口径，<5s）；工具缺失**降级 WARN 不阻断**（沿既有理由：各机 PATH 不一致）。**L2 ✅ 已落地**——新增 `--with-lint` 显式强制增跑（不依赖暂存区）。**L3 ✅ 已落地（R11-5，2026-09-27）**——`.github/workflows/ci.yml` 的 `repo-compliance` 作业里 `G-038` 步骤**由末位前移到最前端**（紧跟 checkout；命令/范围/逻辑零改动）。**实测数据（11 次 run，见「七、操作记录 7.14」）**：该步骤原在作业内 **+13s** 完成（前面 10 个步骤合计仅 ~3s）、前移后 ≈ **+12s** → **顺序收益约 1s**；对照组 `test-backend` 的 Ruff 步骤作业内 +30~34s。**结论更正**：红灯暴露时间由 **runner 排队**主导（11 次 run 作业启动中位 **154s**、最长 **471s**；源于全局并发组 `ci-cd` 串行），而非步骤顺序——三次 E501 事故 run（`73a35ed5`／`f1e55d4a`／`e94f8ddb`）的 lint 红灯本就在作业内 +12~14s 报出；故 L3 的实质收益是“让 lint 成为作业内首个信号”，真正的杠杆登记为 **T-30**（并发组按 ref 拆分／下游重作业 `needs` 门控）挂第十二轮。 | **窗口：已收口（L1/L2 第十轮落地、L3 R11-5 落地）**；后续效率优化转入 T-30。**L1/L2 已于第十轮落地**（commit `T-24` 批次）。**代价**：① 有 `.py`/`scripts/` 变更时 `--fast` 由 <10s 增至约 13~15s；② 未装 ruff/mypy 的机器只见 WARN、仍可能漏到 CI（缓解：本机已装 ruff 0.15.17 + mypy 2.1.0，PATH 目录 `%APPDATA%\Python\Python314\Scripts`）；③ L3 落地需重排 CI job 依赖，属门禁结构变更。 |

| **CI 的 `Docs sync check` 步骤跑错脚本（形近名）→ 步骤长期空转（T-25 登记）** | 2026-09-27 第十一轮开轮侦察（拉 6 次 run 的 `repo-compliance` 日志与 `ci.yml` 逐字比对） | **根因（双重空转）**：① 第十轮把 `ci.yml` 该步骤写成 `python scripts/check_docs_sync.py --strict`，而 `--range/--strict` 的实现全在 **`scripts/docs_sync_check.py`**（两脚本仅差 `check_` 前缀）→ **CI 从未执行过严格模式**；② 被实际执行的 `check_docs_sync.py`（5 条「核心模块 → 架构文档」映射）当时只做 `git diff --name-only origin/<base>..HEAD`——**推送到 main 时 `origin/main` 与 `HEAD` 相同、浅克隆下甚至取不到** → 恒 `[docs-compliance] PASS: 无变更文件`、**恒 `exit 0`**。**证据**：6/6 run 该步骤 `success`，日志只有一行 `[docs-compliance] PASS: 无变更文件`（如 run `36301687032` 第 223 行）；`git grep docs-compliance` 仅命中 `check_docs_sync.py`。**后果**：T-16 的「告警期观察」6 次**全部无效**（观察对象是空转脚本）；这是**第四个 CI 盲区实证**（前三个：G-040 受控测试不在本地路径、ruff/mypy 不在 `--fast`、`tests/` 受控测试路径缺口）。**现状（R11-1 已修）**：`ci.yml` 该步骤**依次跑两个脚本**（`set -e`）——`docs_sync_check.py --strict` + `check_docs_sync.py --strict`；后者补齐**范围回退链**（`--range` → `DOCS_SYNC_RANGE` → `--base`/`BASE_BRANCH`（`origin/<base>...HEAD`）→ `origin/main...HEAD` → `HEAD~1..HEAD`；三点范围与全 0 SHA 正确处理）与**告警期语义**（未同步时打印 `[docs-compliance] WARN(告警期) … **未阻断**（exit 0）`，**绝不静默 PASS**；`--strict-block` 才 `exit 1`）。**受控验证**：`--range a7225689^..a7225689`（历史提交：改了 `pilotstd/ui/` 未同步 `ui.md`）→ 告警期 WARN + **EXIT=0**；`--strict-block` **EXIT=1**；无标志（历史行为）**EXIT=1**；干净范围 PASS + EXIT=0。**另修脚本自身缺陷**：Windows GBK 控制台打印 `❌` 抛 `UnicodeEncodeError` → **假性 exit 1**（本该 exit 0 的告警期），已补 `sys.stdout.reconfigure(encoding="utf-8")`（与同目录其他门禁一致）。 | **窗口：第十一轮已修（R11-1）**；**T-16 观察计时器归零重置**——前 6 次无效，自 R11-1 起重新计时（连续 3~5 次误报为 0 且 WARN 语义确认后，把两个脚本的 `--strict` 改为 `--strict-block`）。**代价**：CI 该步骤 +1~2s（多跑一脚本）；两形近脚本并存仍是长期隐患（建议第十二轮评估合并/改名）。<br>**R11-3 补丁（2026-09-27，第五个 CI 盲区：范围取值陷阱）**：上述修复落地后步骤**仍在空转**——`DOCS_SYNC_RANGE` 原写成 `${{ github.event.before }}..${{ github.event.sha }}`，而 **push 载荷没有 `event.sha` 字段**（应为通用上下文 `github.sha`；push 专有字段为 `github.event.after`）→ 右端空 → 候选非法 → 回退 `origin/main...HEAD` → 推送到 main 时 `origin/main == HEAD`、diff 恒空 → `PASS: 无变更文件`。**实证**：GitHub 在步骤日志里直接打印该变量，run `36304263963`（`b2a8717c`）为 `DOCS_SYNC_RANGE: 27a39d6102c4d076a05f960100668acc08ef9c93..`（左端正确、**右端为空**）；本地以同形态复现出与 CI **逐字相同**的 `变更来源: origin/main...HEAD（BASE_BRANCH=main）｜模式: 告警期` + `PASS: 无变更文件`。**修复**：① `.github/workflows/ci.yml` 右端改 `${{ github.sha }}`；② 两脚本回退链加“**diff 非空**”校验（严格模式）——空 diff 的候选继续回退到 `HEAD~1..HEAD`，全部为空时以“该范围无变更”显式说明收场（绝不静默 PASS）；`--range` 硬指定不受过滤；非严格模式保持旧行为（避免本地误抓历史提交触发自动改文档）。**受控测试**：新增 11 例（`tests/test_check_docs_sync.py` 6 + `tests/test_docs_sync_check.py` 5），修复前 **6 failed**、修复后 **19 passed**。**T-16 计时器再次归零**（自 R11-3 起重新计时）。**编号说明**：本条作为 T-25 的补丁延续、不新开编号（`T-26` 已用于 #34 复发哨兵）。<br>**R11-3b 补丁之二（2026-09-27）**：R11-3 首次提交**遗漏了 YAML 修改**（编辑工具在 CRLF 文件上锚点失配，重做时的补丁脚本只覆盖两个 .py）——CI 日志自证 run `36306033918` 仍为 `DOCS_SYNC_RANGE: 409a5be1…92..`；本批补齐。并查明**第二、三层根因**：② `origin/main...HEAD` 在推送 main 时恒空（`origin/main == HEAD`，与是否浅克隆无关）；③ 同作业更早的 `check-repo-compliance.sh` 用 `git fetch origin main --depth=1` **在 tip 建立浅边界** → `HEAD~1` 不可用（实测 `fatal: Needed a single revision`）、`git log -n2` 只剩 1 条 → 兜底 `HEAD~1..HEAD` 亦失效。**修复**：`ci.yml` 右端 → `${{ github.sha }}`；`check-repo-compliance.sh` 去掉 `--depth=1`；两脚本新增 `_is_shallow_clone()`（浅克隆下声明“历史被截断”，不得谎称“该范围无变更”）。**浅克隆端到端复刻**（探针不入库）：右端为空 → 带浅克隆提示；**显式完整范围 → 真实评估 8 个文件**；受控测试 **23 passed**（含 4 例浅克隆断言）。 |
| **#34 复发哨兵：R1 之后 `test-gui-unit` 零复发的持续观察（T-26 登记）** | 2026-09-27 第十一轮 R11-2 裁定 #34 时设立 | **背景**：#34（EventBus `reset()` 竞态 → Windows 原生访问违例）已裁定 **[转已接受+代价]**——保留 R1（teardown 等待 2s → 5s + `QThreadPool.globalInstance().waitForDone(2000)` + 主线程 `processEvents()`，到期未静止就不 `reset()`），不再投入 R2（`reset()` 静止协议）／R4（CI 装 Python 3.12 + Qt 6.11.2 复现）。**现状（2026-09-27 实测）**：GitHub API 全量 **73 run**，`test-gui-unit` 失败 **3 次**（`3298b530` 2026-09-13、`cdc308f3` 2026-09-26、`71e70054` 2026-09-27）；**R1（`c78cbd89`，2026-09-27T04:26:43Z）之后 14 个 run 全部 success（14／14）**。**统计效力**：历史基率 ≈1／40（2.5%），14 次零复发的概率 ≈70% → 不足以证明根因消除。 | **处置（哨兵，保留有效）**：**每轮复核“R1 之后的 run 统计”并登记数据点**；**触发条件＝再复发 ≥1 次 → 当轮必须做 R2 + R4**（不得再用测试侧序列化／等待搪塞）。**不挂窗口**（已接受项的伴生监控）。**代价**：① 残余间歇红风险——一次抖动即连带阻塞 3~4 个下游 job（`test-gui-coverage`／`version`／`docker`／`exe`）；② R1 属测试侧兜底，若出现**跨用例状态串味**（而非单个用例自身断言失败）即视为兜底失效信号。<br>**⚠️ 哨兵已触发（2026-09-27，R12-3 的 run `36310444541`）**：`test-gui-unit`（job `108595281670`）的 `Run GUI unit tests` 步骤失败——`tests/gui/test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe FAILED` 紧跟 `Windows fatal exception: access violation`（进程 exit 1），与 #34 行的历史两次**逐行同构**（同一测试、同一异常、R1 仍在位）。**按本行预先约定「再复发 ≥1 次 → 当轮必须做 R2 + R4」，R2/R4 自本批起为第十二轮强制项**（不得再用测试侧序列化／等待搪塞）：**R2**＝`event_bus.reset()` 静止协议（`_resetting` 期间 `publish()` 直接返回、单例销毁改 `deleteLater()` 或延迟到 in-flight publish 结束）；**R4**＝CI 环境对齐（装 Python 3.12 + Qt 6.11.2 循环跑 `tests/gui/` 把推断升为实证）。**观察数据**：R1 落地后至本次复发前的窗口为 **14 run 零复发 + 本次 1 次复发**（此前基线 ≈1/40）。 |
| **`check-repo-compliance.sh` 的「新增文件」检查在推送 main 时恒空（假绿，第六个 CI 盲区同族；T-27 登记）** | 2026-09-27 R11-3b 排查浅克隆副作用时实测 | **根因**：`.github/scripts/check-repo-compliance.sh:9-11` 先 `git fetch origin "$BASE_BRANCH" --depth=1`（在 tip 建立浅边界），再用 `git diff --name-only --diff-filter=A "origin/${BASE_BRANCH}..HEAD"` 取“本次新增文件”——**推送到 main 时 `origin/main` 与 `HEAD` 指向同一提交** → diff 恒空 → 恒打印 `PASS: 无新增文件`（CI 日志实证：run `36304263963`、`36306033918` 该步骤均只有这一行）→ 白名单／黑名单／根目录可疑文件等判定**从未在推送路径上生效**；该 fetch 的浅边界还连带让 docs-sync 的 `HEAD~1..HEAD` 兜底失效（已由 R11-3b 去掉 `--depth=1`）。**现状**：浅边界已消除（`--depth=1` 已删），但“范围恒空”**未解**——正确范围应为 `github.event.before..github.sha`（与 T-25 同一手法）。 | **处置**：登记为观察项，**挂第十二轮**（候选修法：把 `before..sha` 作为环境变量传入该脚本并改 `git diff --diff-filter=A "$RANGE"`；验收＝受控反证“注入一个黑名单新文件必 FAIL”）。**代价**：推送路径上“新增违规文件”无门禁拦截（本地 pre-commit 亦无此检查），只能靠人工或事后发现。 |
| **8 处永久 `@pytest.mark.skip`：facade 快照与批调度入口零测试覆盖（T-29 登记）** | 2026-09-27 R11-4 运行期跳过普查（T-20 关闭时拆出） | **现状**：`tests/unit/manager/facade/test_query_subsystem_snapshot.py` ×4（理由：依赖 HTTP 请求（requests.get）／依赖 HTTP + query_engine 降级／修改 5+ core 状态 + 通知发送／query() 入口聚合）与 `tests/unit/query/engine/test_batch_dispatch.py` ×4（理由：需要 ThreadPoolExecutor + 真实组件／需要 mini_bucket 真实交互／_init_batch_state 创建 daemon 线程／依赖 _init_batch_state）是**无条件跳过**（非环境判断），即这 4 个入口（facade 查询子系统快照聚合、批调度 `_init_batch_state`）当前**零单元测试覆盖**；本地运行期 14 跳过中占 8 处（普查分类：network 6／dependency 5／other 2／platform 1，其中这 8 处横跨 network 2 + dependency 4 + other 2）。 | **处置**：**挂第十二轮**（可偿还候选，**预估 ≤2 commit**）——二选一：① 用 `responses`/`respx`（CI 已安装）或 monkeypatch 替掉真实 HTTP、用假 bucket 替掉 ThreadPoolExecutor，把这 8 处改为可运行用例；② 若判定价值不足，则删除用例并在此写明“已接受：入口由 E2E／集成兜底”。**代价**：不还则回归只能靠集成/E2E，改 `_init_batch_state`／facade 快照聚合时无单元级失败信号。 |
| **CI 红灯暴露时间被 runner 排队主导（全局并发组串行）＋ 下游重作业未做 lint 门控（T-30 登记）** | 2026-09-27 R11-5 实测 11 次 run（`.github/workflows/ci.yml` 的 `concurrency: group: ci-cd` + `cancel-in-progress: false`） | **现状（实测，见 7.14）**：11 次 run 的**作业启动时刻**相对 run 开始为 **中位 154s、最长 471s**（连续推送时后一个 run 必须等前一个跑完）；而作业内 lint 红灯仅需 **+12~14s**（`repo-compliance` 的 G-038）。即“红灯 3 分钟才暴露”的观感来自**排队**，与步骤顺序无关。另：`test-backend`／`test-gui-*`／`e2e-*` 等重作业**没有** `needs: repo-compliance`，lint 失败时它们仍会跑完（实测 `test-backend` 作业内 94~133s 的 pytest 照跑），浪费 2~5 分钟机时。 | **处置**：登记为观察项，**挂第十二轮**（候选修法：① 并发组按 ref 拆分 `ci-cd-${{ github.ref }}` 或对非 main 推送启用 `cancel-in-progress`；② 给下游重作业加 `needs: [repo-compliance]`，或单独拆一个 `lint-fast` 作业作前置门控——收益＝lint 失败时下游根本不启动）。**不挂空窗的代价**：每次推送若撞上排队，红灯反馈延迟 2~8 分钟；lint 失败时下游 4~5 个作业仍白跑（机时 + CI 分钟消耗）。<br>**R12-1 归因结论（2026-09-27，78 run 全量 + 10 run 关键路径，见 7.15）**：① **自串行**——本仓库的 `concurrency: group: ci-cd` + `cancel-in-progress: false` 让连续推送排队：**26/78 = 33%** 的 run 创建时被前一个 run 挡住，等待 1~1340s（被挡样本中位 ≈300s）；② **runner 分配不是瓶颈**（未被挡时作业启动 +3s）；③ **放大因子是单次 run 太长**——run 中位 **828s**，关键路径 `test-gui-unit` **467s** → `version` 8s → `docker`/`exe` ≈176s；④ 「bump 提交产生额外 run」**已证伪**（`GITHUB_TOKEN` 推送不触发 workflow，78 run 中 bump 类型 0 个，另见 T-31）。**方案对比 A~F** 见 7.15，推荐「单并发组改按 ref + `cancel-in-progress: true`」（1 行）＋（第二批）缩短关键路径。**处置：挂第十二轮 P0，待用户选型后进 R12-2。**<br>**R12-2 落地（2026-09-27）**：按用户选型落 **方案 G**——`concurrency.group` 改 `ci-cd-${{ github.ref }}`、`cancel-in-progress: true`（1 处配置，检查逻辑零变更）。**生效机制**：① 新推送进入**同 ref 组**并取消该组内被取代的旧 run → 不再等待前一个 run 跑完；② 分支/PR 推送改用自己的组，**不再占用 main 的槽位**（旧配置是全局单组，三者共享）。**观察口径**：以“作业启动延迟”（`job.started_at − run.run_started_at`）为指标，基线＝未排队样本 **+3s**、被挡样本中位 **≈300s**；连续 3 次 run 中位 ≤10s 即判定生效，随后进 R12-3（方案 C：lint-fast + `needs` 门控）或 D/E（缩短关键路径）。<br>**首个数据点（R12-2 推送后实测，2026-09-27）**：R12-2 的 run `36309693229`（组 `ci-cd-refs/heads/main`）作业启动延迟 **中位 +2.0s**（2.0／2.0／2.0／2.0／3.0／3.0／4.0，n=7）；**同时间窗对照**：旧组 run `36309485009`（R12-1，组 `ci-cd`，当时与 R11-5 的 run 串行）作业启动延迟 **中位 +198s**（197~257）——对照组即旧模型行为；而 R12-2 的 run 在旧组仍有 run 在飞的情况下**即时启动**，证明按 ref 分组已把两者解耦。**判定：G 生效（+2.0s ≤ 目标 10s）**，待再观察 2 次 run 的排队指标。**路线确认（用户 2026-09-27 裁定）**：R12-2＝G + T-28（已落地）；**R12-3＝方案 C**（lint-fast + `needs` 门控，失败 run 828s → ~60s）；**D/E（缩短关键路径）挂后**，待 G+C 稳定后再立专项。<br>**R12-3 阶段二落地（2026-09-27）**：按裁定落 **方案 C**——新增 `lint-fast` 作业（G-038 ruff+mypy+裸noqa，**命令/范围零改动**）并作为 **9 个下游作业**的 `needs` 门控（`version`／`docker`／`exe` 传递性门控）。**判定口径**：受控失败时①`lint-fast` 快速失败（≈20~40s）；②下游作业状态为 **skipped**（未被触发）；③失败 run 时长 ≈ 快闸时长（目标 ≤60s，基线 828s）。**绿灯路径**：+≈20s（快闸串行在前）。**G 第一阶段收口条件**：第 3 个 run 的作业启动延迟中位 ≤10s（前两次 +2.0s／+7.0s），达标即宣告 G 成功、T-30 第一阶段关闭，仅余方案 D／E（缩短关键路径）作为独立专项。<br>**R12-3b 实测（2026-09-27）**：① **第 3 个数据点**——R12-3 的 run `36310444541` 首个作业（`lint-fast`）启动 **+16.0s**，**原始值超 ≤10s 阈值**；同窗旧组对照（R12-1 `36309485009`）+198s。② **取消语义再现**：R12-2（`46a4a67f`）被 R12-2b 取消、R12-2b（`7c478c6f`）被 R12-3 取消（同 ref 组），而**旧组** R12-1 success 未被影响；取消后其内容由下一次 run 覆盖验证。③ **方案 C 绿灯代价**：`lint-fast` 启动 +16.0s、时长 14.0s，下游首个作业 +32.0s。**收口判定**：队列效应已消除（新组 2~16s vs 旧组 197~257s），但第 3 个数据点原始值 16.0s 未达 ≤10s——**是否宣告 G 第一阶段收口由用户裁定**（建议按“队列效应消除”收口，并把指标改为“首个作业启动延迟 ≤20s 且旧组同窗对照 ≥100s”，理由：门控落地后该指标已含 runner 分配与快闸时长两层，不再是纯队列量）。 |
| **自动 `chore: bump version` 提交不触发任何 CI（T-31 登记）** | 2026-09-27 R12-1 排队归因取数时发现（原假设“bump 提交会产生额外 run”被证伪） | **现状**：`version` 作业用 `GITHUB_TOKEN` 推送 bump 提交，而 GitHub 规定**用 `GITHUB_TOKEN` 的推送不触发 workflow** → 78 个 run 中 head 为 bump 提交的**0 个**；即 bump 内容（版本号写入 `pilotstd/__init__.py`、`CHANGELOG.md` 等）**没有独立 CI 验证**，靠**下一次推送**的 `test-backend` 里 `G-009 — Check CHANGELOG version consistency` 兜底。**影响（正面与负面）**：正面＝不额外占用 CI 与排队（T-30 归因因此少一源）；负面＝若某次 bump 写坏而此后长期无推送，问题会静默滞留。 | **处置**：登记为观察项，**暂不动作、不挂窗口**（兜底已存在且 bump 由版本脚本生成、内容确定性高）。**触发条件**：出现“版本号/CHANGELOG 不一致”类事故时，评估给 bump 提交加显式验证或改用 PAT 触发。**代价**：极端情况下 bump 错误可静默到下一位开发者推送。 |

> **2026-09-27 结构重整**：已闭环的 5 行按归属移出——「单条网络请求/大文件 IO 不可中断」（✅ 已接受）与「`_migrate_v59_…` docstring 过时」（✅ 已决定不改）→「五、已接受的设计决策 · 归档并入」；「拆出新模块时注释密度被稀释」（✅ 已落实）、「#23 合并前侦察未覆盖全组合」（✅ 已落实）、「#27 gates.md 版本历史两行挤在同一物理行」（✅ 已修复）→「一、已清理 · 归档并入」。本节现只保留**仍未闭环**的观察项。 **2026-09-27（R11-5）补记**：**T-20 已 ✅ CLOSED**（R11-4 实测证伪原假设 + 交付基线/普查工具），按本节规则移入「一、已清理」；其剩余可治理项拆为 **T-29**（8 处永久 `mark.skip`，挂第十二轮）。 **2026-09-27（R12-2b）补记**：**T-28 亦 ✅ CLOSED**（`-rs` 已覆盖全部 5 处 pytest 调用，CI 日志实证 44 条跳过明细），同样移入「一、已清理」。 **2026-09-27（R12-4a）补记**：**T-32 亦 ✅ CLOSED**（L1 触发式已覆盖 `.pyi/.pyw`，双向受控验证通过），同样移入「一、已清理」。

---

## 七、操作记录（一次性数据操作 + 留档 SQL + 只读巡检）

### 7.1 执行通道（2026-09-25 实测修正）

| 通道 | 是否可用 | 依据 |
|---|---|---|
| `POST /query`（admin SQL 端点） | ✅ **可用，且首选** | 路由无 prefix，真实路径就是 **`POST /query`**（审计里写的 `/api/admin/db/query` 只是标签字符串）。`admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**；SELECT 自动包 `LIMIT 1001`，INSERT/UPDATE/DELETE 分别受"WHERE 必需"等约束 → **普通读写不受表白名单限制**，无需 SSH/容器执行 |
| 容器内 `python -m sqlite3` | ✅ 可用（备选） | 容器**无 `sqlite3` CLI**（`Dockerfile:30` 只装 gosu/git/curl）；需以 `appuser` 执行（`Dockerfile:27` + `entrypoint.sh:151-152` `gosu appuser`），避免 root 写库改 WAL/SHM 属主 |

### 7.2 只读巡检（已执行，2026-09-25）

经 `POST /query` 执行三组 SQL，结果**全部符合期望**：

| 组 | 检查项 | 期望 | 实测 |
|---|---|---|---|
| A | `uf_std_no_null` / `fd_std_no_null` / `fd_std_no_unknown` / `fd_std_name_null` | 0 | **0 / 0 / 0 / 0** |
| B | `uf/fd/ar/dq` 四表 `standard_type` 空值 | 0 | **0 / 0 / 0 / 0** |
| C | 同用户同标准号同分类重复收藏分组 | 0 行 | **0 行** |

附带验证：`SELECT COUNT(*) FROM favorite_downloads` → 105（证明 SELECT 不受表白名单限制）。
SQL 原文：

```sql
-- A) 标准号/名称完整性
SELECT 'uf_std_no_null'          AS check_name, COUNT(*) FROM user_favorites    WHERE standard_number IS NULL OR TRIM(standard_number) = ''
UNION ALL SELECT 'fd_std_no_null',    COUNT(*) FROM favorite_downloads WHERE standard_no   IS NULL OR TRIM(standard_no)   = ''
UNION ALL SELECT 'fd_std_no_unknown', COUNT(*) FROM favorite_downloads WHERE standard_no   GLOB 'UNKNOWN_*'
UNION ALL SELECT 'fd_std_name_null',  COUNT(*) FROM favorite_downloads WHERE standard_name IS NULL OR TRIM(standard_name) = '';

-- B) 分类列（v57 四表统一补列）是否存在未回填
SELECT 'uf_std_type_empty' AS check_name, COUNT(*) FROM user_favorites      WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'fd_std_type_empty',     COUNT(*) FROM favorite_downloads  WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'ar_std_type_empty',     COUNT(*) FROM announcement_record WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'dq_std_type_empty',     COUNT(*) FROM download_queue      WHERE standard_type IS NULL OR TRIM(standard_type) = '';

-- C) 标准级去重基线：同用户同标准号同分类重复收藏（期望 0 行）
SELECT user_id, standard_number, standard_type, COUNT(*) AS c
FROM user_favorites GROUP BY user_id, standard_number, standard_type HAVING c > 1;
```

调用方式（管理员会话 + CSRF 头）：

```bash
curl -s -X POST http://<nas>:9028/query \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" \
  -b "pilotstd_token=$TOKEN; csrf_token=$CSRF" \
  -d '{"sql":"SELECT COUNT(*) AS n FROM favorite_downloads"}'
```

### 7.3 一次性补建（已执行，2026-09-25，v0.109.4）

```sql
-- 幂等补建队列行（NOT EXISTS 去重；模板已修正为多一层 r.standard_number 回退）
INSERT INTO favorite_downloads
  (favorite_id, user_id, record_id, status, standard_no, standard_name, standard_type,
   retry_count, created_at, updated_at)
SELECT f.id, f.user_id, f.record_id, 'pending',
       COALESCE(NULLIF(TRIM(f.standard_number), ''), r.standard_number, 'UNKNOWN_' || f.record_id),
       COALESCE(r.std_name, '未知标准'),
       COALESCE(f.standard_type, 'Unknown'),
       0, datetime('now'), datetime('now')
FROM user_favorites f
LEFT JOIN announcement_record r ON r.id = f.record_id
WHERE NOT EXISTS (SELECT 1 FROM favorite_downloads fd WHERE fd.favorite_id = f.id);
```

**实际执行结果**：`INSERT rowcount=8` → `missing=0` → 8 行全 `pending`（GB/T 2970-2026 / GB/T 5613-2026 / GB/T 7607-2026 / GB/T 13237-2026 / GB/T 7597-2026 / GB/Z 184.1-2026 / GB/T 8335-2026 / GB/T 8336-2026）→ 分布 `abandoned 96 / failed 1 / pending 8`；同批纠正 `user_favorites.standard_number` 36 行 NULL（`uf updated=36`、`fd updated=8`、`uf_null_after=0`、`fd_unknown_after=0`）。

**模板修正教训**：原模板只写 `COALESCE(f.standard_number, 'UNKNOWN_' || f.record_id)`，而 v57 给 `user_favorites` 只加列不回填 → 历史行为 NULL → 现场产出 8 行 `UNKNOWN_<record_id>`。**正确写法必须多一层回退到 `announcement_record.standard_number`**（上方已修正）。

### 7.4 巡检走公开端点复核（已执行，2026-09-26，第六轮）

目的：确认 #18 三组巡检**不必依赖 admin SQL 端点**即可复现（能走公开 API 的就不该要求人执行 SQL）。

| 口径 | 公开端点可行性（实测） |
|---|---|
| 全量性前提 | `GET /api/favorites/export?format=json` → **105 行 == 库内 `user_favorites` 105 行**；接口 SQL（`favorites.py:453-470`）只有 `WHERE f.user_id = ?` + `ORDER BY`，**无 LIMIT/分页** → 全量成立，可用于本地算基线 |
| A 组（标准号/名称） | ✅ `user_favorites` 维度可算：`standard_number`=0 空、`std_name`（键名，来源 `announcement_record`）=0 空、`UNKNOWN_*`=0；❌ `favorite_downloads.standard_no/standard_name` **公开端点未暴露**（`_DOWNLOAD_FIELDS` 仅 4 列，`favorites.py:341-346`） |
| B 组（分类列未回填） | ✅ `user_favorites.standard_type` 可算：0 空（105 条全 `NationalStd`）；❌ `favorite_downloads` / `announcement_record` / `download_queue` 的分类列未暴露 |
| C 组（去重基线） | ✅ 可算：按 `(standard_number, standard_type)` 分组 = 105 组、**重复组 0**（本用户全量数据） |
| 未暴露维度 | 经 `POST /query`（同为 API）复核：`fd_std_no_null=0`、`fd_std_no_UNKNOWN=0`、`fd_std_name_null=0`、`fd_std_type_empty=0`、`ar_std_type_empty=0`、`dq_std_type_empty=0` |

探针（不入库）：`C:\Temp\pilotstd-probe\probe_a1_export_checks.py`。

### 7.5 部署后现场复核（已执行，2026-09-26，v0.110.2）

| 复核项 | 结果 |
|---|---|
| 版本 | `/api/system/version` = `0.110.2`（tag `v0.110.2`、image `ghcr.io/leanmore/pilotstd:v0.110.2`）；`/api/health` 返回的 version = 构建 sha `c421c572` |
| TD-20 读侧 | `GET /api/settings` 的 `tasks` **10 键、缺键 0**；`auto_archive_retry_enabled=True` / `auto_archive_retry_cron='0 4 * * *'` |
| 与调度器一致 | `GET /api/scheduler/status` 中 `auto_archive_retry` next_run `2026-09-27T04:00+08:00`（cron 与读侧一致） |
| UI 新任务行 | Playwright 现场：设置页「定时任务」出现"收藏下载链（自动归档重试）"、开关为开、cron 输入框 `0 4 * * *`、页面回填值 == 后端值；截图 `C:\Temp\pilotstd-probe\shots\settings-schedule.png` |
| 部署方式 | 人工部署（该主机不自动拉取；更新开关见 `docker/api/system.py:152` `POST /api/system/update`），部署后 `/api/health` 构建 sha 由 `22d4d90b` → `c421c572` |

探针（不入库）：`probe_td20_readside.py`、`verify_settings_ui.cjs`。

### 7.6 前端 CI 缺陷修复（已执行，2026-09-26，第七轮）

| 项 | 内容 |
|---|---|
| 现象 | CI run `36209088436`（提交 `4ca2c061`，纯 docs、0 个 `web/` 文件）：`Test Files 35 passed / Tests 230 passed` 却 `Errors 1 error` + exit 1，`test-frontend` 的 "Run tests" 步失败（46s），其后 `version`/`docker`/`exe` 全部 skipped（**不发版、不出镜像**） |
| 根因 | `primevue/tablist/index.mjs:48-53` 在 `mounted()` 排 `setTimeout(() => { updateInkBar(); bindInkBarObserver() }, 150)`，**不保存句柄、`unmounted` 也不清理**；测试文件在 150ms 内结束时，vitest 先摘掉 jsdom 全局再执行回调 → `@primeuix/utils` 的 `t instanceof HTMLElement`（`dist/dom/index.mjs`）抛 `ReferenceError: HTMLElement is not defined`（unhandled error → `Errors 1 error`） |
| 环境事实 | 测试环境 = **jsdom**（`web/vite.config.ts:50`），setupFiles = `web/src/test-setup.ts`（`:53`） |
| 复现 | 受控复现（fake timers 捕获真实 150ms 定时器 → 摘除 `globalThis.HTMLElement`/`window` → `vi.runAllTimers()`）：得到与 CI **完全一致**的 `HTMLElement is not defined`，栈含 `updateInkBar`/`tablist`。自然竞态在本机复现不出：jsdom 下 FavoritesView 挂载 ~440ms > 150ms，定时器总在环境内先跑完（轻量 Tabs 对照组同样 0 error）——即"本机绿、CI 红"的成因 |
| 候选否证 | 候选 1（`defineProperty(configurable:false)` 锁定）→ 全量套件 **34 errors**、报 `TypeError: Cannot delete property 'HTMLElement' of #<Object>`（vitest teardown 用 `delete` 摘全局）→ 有害，弃；候选 2（`afterEach` 补回）→ 全局是在 afterEach **之后**的 teardown 阶段被摘，结构上无效，弃；空壳类兜底 → `instanceof` 恒 false、`getOuterWidth` 静默返回 0（更隐蔽），禁用 |
| 修法 | `web/src/test-setup.ts` 接管 `setTimeout`：登记未触发句柄，文件级 `afterAll` 一并 clear 并还原真实实现（回调根本不会执行；不用 fake timers、不用 sleep）。`web/src/views/FavoritesView.test.ts` 增确定性守卫（断言接管层能登记与清理真实定时器） |
| 全库扫描 | 仅 `FavoritesView.vue` 与 `dashboard/widgets/RecentAnnounceCard.vue` 使用 Tabs/TabList；后者在 `views/__tests__/HomeView.test.ts:37` 被 `vi.mock` 整体替换 → 不实例化 TabList、无定时器 → 无风险 |
| 验证 | 全量 1 次 + 连跑 10 次：每次 `Errors 0 / exit 0`，`35 files / 231 passed`（230 + 新增守卫 1 例）；`vue-tsc --noEmit` exit 0 |

### 7.7 #17a 量化验收实测（已执行，2026-09-26）

| 路径 | 修复后退出耗时 | 占 5000ms 预算 | 修复前对照（`git stash` 掉改动） |
|---|---|---|---|
| ScanWorker（流进行中） | **14ms** | 0.3% | 5035ms、退出=False、保活 +1 |
| QueryWorker（流进行中） | **6ms** | 0.1% | 5009ms、退出=False、保活 +1 |
| QueryWorker（暂停中） | **60ms** | 1.2% | 5010ms、退出=False、保活 +1 |
| DriveEnumerator | **54ms** | 1.1% | 5055ms、退出=False、保活 +1 |

假 stream 为 20000 条 × 10ms（不中断需 ~200s）；修复后底层流在 12–14 条处被终止，`orphan_timeout_total()` 增量 0、保活残留 0。测量脚本（不入库）：`C:\Temp\pilotstd-probe\measure_worker_abort.py`。

### 7.8 #17a 首次上 CI 失败与加固（2026-09-26）

| 项 | 内容 |
|---|---|
| 现象 | 推送 `cdc308f3` 后 `test-gui-unit` 失败，**耗时 8.2 分钟**（同树前两次成功运行均为 18 分钟）→ 进程在套件中途终止，未打印 pytest 汇总；`version`/`docker`/`exe` 连带 skipped |
| 本机复现 | 用 CI 同款命令（`pytest tests/gui/ tests/test_regression_architecture.py --cov=pilotstd/ui/core/handlers/ --ignore-glob="*test_e2e*.py"` + `PILOTSTD_GUI_TEST=1`）本机 **990 passed / 覆盖率 68.71%**，不复现；本地全量两轮均 1000 passed |
| 根因（判定） | 新用例的**绝对毫秒阈值**（`elapsed_ms < 500`）在 CI 的 coverage 插桩 + 慢 runner 下会偶发失败；而断言在 `isFinished()`/收尾之前抛出 → 局部变量 `worker`（仍在运行的 QThread）随帧释放被 GC → Qt 触发 `QThread: Destroyed while thread is still running` 并 **qFatal 终止进程** → 套件中途死亡（正是 8.2 分钟无汇总的形态） |
| 加固 | ① `_stop_and_measure()` 在 `finally` 中无条件 `worker.wait(timeout_ms)`：断言失败也先把线程收干净，杜绝"运行中被析构"；② 绝对毫秒阈值全部放宽为 `2000–3000ms` 量级（真正的验收线仍是"≤80% timeout"，即 4000ms）；③ `mgr.started.wait(5.0)` → `20.0`（CI 冷启动慢） |
| 教训 | 线程类测试的收尾必须与断言解耦（先 join 再断言或 finally join）；跨环境验收线用相对预算而非绝对毫秒 |

### 7.9 T-23：「三-B」标签经评估保留（已裁定，2026-09-27）

**裁定：保留现状，不收敛**——「三-B、i18n key 一致性检查」是**功能性子节**（描述一个具体检查项的补充说明），与「六-B、观察项」（**结构性容器**，本轮已收敛为「六」）**性质不同**；本轮 T-22 编号收敛的目标是消除**结构性空档**（六-B → 八），「三-B」不存在空档问题。

| # | 裁定理由 |
|---|---|
| 1 | 「三-B」是功能性子节标签（一条具体检查项的补充说明），与「六-B」这类结构性容器的性质不同 |
| 2 | 强行改为「三」会与父章节「三、门禁规则清单」的平级子节产生语义混淆——它不是一个独立的门禁规则 |
| 3 | 本轮编号收敛的目标是消除结构性空档（六-B → 八），「三-B」不存在空档问题 |
| 4 | 若未来 i18n 检查升级为独立门禁规则，再自然提升为「三-x」即可 |

**处置**：不动作（无代码/文档结构变更）；本条为**已裁定**记录，**不挂窗口**。

### 7.10 #31／#32／#34 三债终局裁定（已裁定，2026-09-27，第十一轮 R11-2）

**本轮定位**：用户指定“本轮只出裁定书，不做全量偿还”。三份裁定书已逐条写入「二、剩余台账」对应行，四要素齐备（现状量化／偿还方案+成本／转已接受的代价／终局结论），判决均落在三选一（[本轮偿还] / [挂窗第N轮] / [转已接受+代价]）。

| 项 | 终局结论 | 关键判据（2026-09-27 本轮实测） | 后续动作 |
|---|---|---|---|
| **#31** ConfigManager 多实例交错写 + 热路径高频 IO | **[挂窗第十二轮]** | `get_profile()` 单次 **4.28／4.27／4.28 ms**，每次恰 **1.00 次构造 + 1.00 次 save**；单查询 126 次 → **≈0.54 s + 519 KiB 写盘**；沉淀面＝生产构造点 21 处 + 测试 31 文件／104 行；P2 冲击“构造即写回”契约（`tests/test_core_config.py:333-340`）；“只做 P1 缓存”因需配置失效通知而被否决 | 第十二轮按 P1→P2→P3 分期偿还，或转已接受并按裁定书 ③ 记账 |
| **#32** 后端状态值用中文 + 前端硬编码比较 | **[挂窗第十二轮起分阶段偿还]** | 生产 **248 处／50 文件**、测试 **456 处／65 文件**；容器定义点 **9 处／5 个名字**（更正旧记“7 处”）；四阶段路线图合计 **7~12 commit** | A 阶段（新建 pilotstd/core/status.py 枚举模块）须第十二轮完成；未动即当轮转已接受 |
| **#34** EventBus reset 竞态 → CI `test-gui-unit` 间歇红 | **[转已接受+代价]** | R1 之后 **14 run／`test-gui-unit` 14-14 success**；该样本在 ≈1／40 基率下零复发概率 ≈70%（不足以否认基率） | 保留 R1；哨兵登记为「六、观察项」T-26（复发 ≥1 次 → 当轮做 R2+R4） |

**取数方式（探针一律不入库，存于仓库外临时目录）**：
1. **#34 走 GitHub Actions API**——`/actions/runs` 取全量 73 run（3 页），逐 run 读 `/jobs` 判 `test-gui-unit` 结论与 skipped 明细；R1 分界取提交 `c78cbd89` 的提交时间（2026-09-27T04:26:43Z）。
2. **#31 走运行时打点 + pytest 插件探针**——包装 `ConfigManager.__init__` 与 `ConfigManager.save` 计数、`scorer.get_profile()` 计时 3×100 次；另以 `-p cfgcount2` 插件跑单个查询用例（`tests/test_query.py` 的 `TestQueryEngine::test_parallel_batch_query`）统计单查询的构造／写盘／`get_profile` 次数（复现上一轮的 126 次数据点）。
3. **#32 走 AST + tokenize 口径复跑**——字符串字面量“内容恰为 9 个状态值之一”（排除注释／docstring）计生产 248／测试 456；容器定义点改用**解包 `frozenset(...)` 的 AST 探针**（这是旧记“7 处”漏计 2 处的原因）。

**本轮未产生任何代码／测试变更**（用户明确禁止 #32 产出代码变更，且 #31／#34 经评估均超“≤1 commit 且无连锁风险”阈值，一律挂窗）。

### 7.11 R11-3：CI 范围取值陷阱的取证与修复（已执行，2026-09-27，第十一轮）

**触发**：R11-2 收尾核对 R11-1 修复在 CI 的实际效果时发现——步骤虽已跑对脚本，但**变更范围恒空**，仍在空转。

| 步 | 取证动作（可复现） | 结果 |
|---|---|---|
| 1 | GitHub API 读 run `36304263963` 的 `repo-compliance` 作业（job `108577660279`） | step 6 `Docs sync check` = **success**——与修复前的空转**不可区分** |
| 2 | 取该作业日志（`curl -H "Authorization: Bearer …" …/actions/jobs/108577660279/logs`） | `AUTO_FIX_DOCS: false`；**`DOCS_SYNC_RANGE: 27a39d6102c4d076a05f960100668acc08ef9c93..`（右端为空）**；`[docs-compliance] 变更来源: origin/main...HEAD（BASE_BRANCH=main）｜模式: 告警期`；`PASS: 无变更文件` |
| 3 | 根因判定 | push 载荷无 `event.sha` 字段（应为 `github.sha`）→ `DOCS_SYNC_RANGE=<before>..` 右端空 → 脚本判该候选非法 → 回退 `origin/main...HEAD`；推送到 main 时 `origin/main == HEAD` → diff 恒空 |
| 4 | 本地同形态复现 | `DOCS_SYNC_RANGE='27a39d61..' BASE_BRANCH=main python scripts/check_docs_sync.py --strict` → 与 CI **逐字相同**的两行输出 |
| 5 | 修复后同形态 | `变更来源: HEAD~1..HEAD（HEAD~1..HEAD）｜模式: 告警期` + `PASS: 所有核心模块变更已同步文档`（真实判定，不再“无变更文件”） |
| 6 | 真实未同步场景 | `--range 27a39d61..b2a8717c`（该范围改了工作流文件）→ 正确报出 `docs/development.md` 未同步（触发规则：CI/CD 工作流变更）+ CHANGELOG.md，**EXIT=0**（告警期） |
| 7 | 反证 | 新增 11 例受控测试，对**修复前**脚本跑 **6 failed / 13 passed**；修复后 **19 passed** |

**修复内容**：`.github/workflows/ci.yml` 的 `DOCS_SYNC_RANGE` 右端 `github.event.sha` → `github.sha`；`scripts/check_docs_sync.py` 与 `scripts/docs_sync_check.py` 的回退链新增“候选必须确实含变更文件”校验（严格模式生效），全部候选为空时打印显式原因。**未产生任何功能代码变更**（仅门禁脚本与 CI 接线）。

**推送后应观察到（预测验证）**：该 run 的 `Docs sync check` 步骤须打印真实的 `WARN(告警期)`（本批改了工作流文件却未同批更新 `docs/development.md`），彻底破除“空转即 PASS”的假绿。


### 7.12 R11-3b：遗漏补修与浅克隆根因（已执行，2026-09-27，第十一轮）

**① 自曝的遗漏**：R11-3 首次提交（`30de04e4`）**只落盘了两个脚本与文档，`ci.yml` 的 YAML 修改丢失**——起因是编辑工具在 CRLF 文件上锚点失配报错，改用 Python 补丁脚本重做时只写了两个 `.py`。CI 立即自证：run `36306033918` 的 `Docs sync check` 步骤环境仍为 `DOCS_SYNC_RANGE: 409a5be18435bfc5a50aede873513a54ee0a0492..`（右端仍为空）。**教训**：改多文件时应对每个目标逐一确认"已真正落盘"（`git diff --stat` 复核），而不是依赖改完即推。

**② 三层根因（全部有证据）**：

| 层 | 事实 | 证据 |
|---|---|---|
| 第一层 | push 载荷没有 `event.sha` 字段 → 右端展开为空 → 该候选被脚本判为非法 | run `36304263963` 的步骤环境：`DOCS_SYNC_RANGE: 27a39d61…93..` |
| 第二层 | 回退候选 `origin/main...HEAD` 在推送到 main 时恒空（`origin/main == HEAD`） | run `36306033918` 日志：`变更来源: origin/main...HEAD（BASE_BRANCH=main，该范围无变更）` |
| 第三层 | 同一作业更早的 `check-repo-compliance.sh` 执行 `git fetch origin main --depth=1` → **在 tip 建立浅边界** → `HEAD~1` 不可用、`git log -n2` 只剩 1 条 → 兜底 `HEAD~1..HEAD` 也失效 | 本地按 actions/checkout 流程复刻（见③）：`.git/shallow` 出现、`git rev-parse HEAD~1` = `fatal: Needed a single revision`、`git diff origin/main...HEAD` = 0 文件 |

**③ 本地端到端复刻浅克隆（探针不入库，位于仓库外临时目录）**：`git init` → `git fetch --no-tags --prune --no-recurse-submodules origin '+refs/heads/*:refs/remotes/origin/*'`（模拟 `fetch-depth: 0`）→ `git checkout -B main refs/remotes/origin/main` → `git fetch origin main --depth=1`（模拟 `check-repo-compliance.sh`）→ 复刻出的现象与 CI 完全一致。

| 复刻场景 | 修复前 | 修复后（本批） |
|---|---|---|
| 浅克隆 + 右端为空（原始事故形态） | `变更来源: origin/main...HEAD` → `PASS: 无变更文件` | 回退失败但**显式说明**：`（BASE_BRANCH=main，该范围无变更（提示：仓库为浅克隆，HEAD~1 等历史范围不可用））` |
| 浅克隆 + 显式完整范围 `409a5be1..30de04e4`（= `ci.yml` 修复后的形态） | 未被使用（右端为空） | **真实评估 8 个文件**：`变更来源: 409a5be1..30de04e4（环境变量 DOCS_SYNC_RANGE）` + `PASS: 所有核心模块变更已同步文档` |

**④ 修复清单**：`.github/workflows/ci.yml` 右端 `github.event.sha` → `github.sha`；`.github/scripts/check-repo-compliance.sh` 去掉 `--depth=1`；`scripts/check_docs_sync.py` 与 `scripts/docs_sync_check.py` 新增 `_is_shallow_clone()` 说明与 4 例受控断言（合计 **23 passed**）。

**⑤ 连带发现**：`check-repo-compliance.sh` 的“新增文件”检查在推送 main 时 `origin/<base>..HEAD` 恒空 → 白名单／黑名单判定从未生效（第六个 CI 盲区同族）→ 登记「六、观察项」**T-27**，挂第十二轮。


### 7.13 R11-4：T-20 跳过普查与 fixture 基线（已执行，2026-09-27，第十一轮）

**任务口径**：为「60 处 `self.skipTest`」补最小 fixture 基线，识别可治理部分；不做全量治理、不改既有测试逻辑。

**① 三口径实测**：

| 口径 | 方法 | 结果 |
|---|---|---|
| 静态调用点 | AST 扫描 `tests/**/test_*.py` | `self.skipTest` **60 处 / 10 文件**（43 处为 `Fixture not found` 守卫）；`pytest.skip()` 2、`@pytest.mark.skip` 10、`@pytest.mark.skipif` 10、`@unittest.skipIf/skipUnless` 17 |
| 本地运行期 | `python -m pytest tests/ -q -rs --ignore=tests/gui/` | **4290 passed / 14 skipped**（含 R11-4 新增 10 例；分类：网络 6／依赖 5／其他 2／平台 1） |
| CI 运行期 | run `36306309371` 的 `test-backend` 日志 | **3997 passed / 44 skipped**（CI 断网 + `_CI` 跳过；CI 未开 `-rs`，明细不可得 → 见 T-28） |

**② 逐文件实测（7 个 fixture 文件 + 3 个其余文件）**：

| 文件 | 静态守卫 | 运行期跳过 | 说明 |
|---|---|---|---|
| `tests/test_adapters.py` | 25 | 0 | 25 处全为 fixture 守卫，fixture 在库 → 全部真实执行 |
| `tests/test_e2e_adapters.py` | 15 | 4（本地） | 站点状态驱动（无响应/未收录）；CI 另有类级 `@unittest.skipIf(_CI)` |
| `tests/test_energy.py` | 4 | 0 | fixture 在库 |
| `tests/test_ncha.py` | 4 | 0 | fixture 在库 |
| `tests/test_cssn.py` | 3 | 0 | fixture 在库 |
| `tests/test_gongbiaoku.py` | 3 | 0 | fixture 在库 |
| `tests/test_miit.py` | 2 | 0 | fixture 在库 |
| `tests/test_tdpress.py` | 2 | 0 | fixture 在库 |
| `tests/test_scanner.py` | 1 | 1 | 平台／文件系统能力（超长文件名） |
| `tests/test_mock_pipeline.py` | 1 | 0 | mock 随机兜底（未触发） |
| 其他（不在 T-20 原口径内） | — | 9 | `test_ocr_fallback` 1（provider）+ `test_query_subsystem_snapshot` 4 + `test_batch_dispatch` 4（均为 `@pytest.mark.skip`） |

**③ 结论**：**因缺 fixture 而跳过 = 0 处**——43 个守卫依赖的 15 个 fixture 文件全部已入库（`tests/fixtures/`，登记见 `tests/fixture_baseline.py`），运行期一次也不触发。
T-20 原表述「60 处会让跳过数长期偏高」是**静态口径误用**，已更正。真正剩余的可治理候选是 **8 处 `@pytest.mark.skip`**（依赖真实 HTTP／ThreadPoolExecutor／daemon 线程），属可偿还；其余 6 处为环境依赖（网络/平台），按 §〇 归「环境依赖」。

**④ 交付物（仅新增，未改既有测试逻辑）**：

| 文件 | 作用 | 覆盖 |
|---|---|---|
| `tests/fixture_baseline.py` | fixture 基线登记（15 项）＋ `missing_fixtures()`／`uncovered_guards()`／`baseline_report()` | 登记表覆盖全部 7 个有守卫的文件 |
| `tests/skip_census.py` | 运行期／静态双口径普查：解析 `pytest -rs` → 分类（fixture／random／platform／network／dependency／other），支持 `--json`／`--static` | — |
| `tests/test_fixture_baseline.py` | 5 例：fixture 就位、无缺失、守卫全覆盖、静态基线数一致（43／7）、登记 ⊇ 守卫文件 | 受控 |
| `tests/test_skip_census.py` | 5 例：分类六类、`-rs` 解析与 `[n]` 展开、非跳过行忽略、按文件汇总、静态口径 60 一致 | 受控 |

**⑤ 复现命令**：
```
python -m pytest tests/ -q -rs --ignore=tests/gui/ > skip.txt 2>&1
python tests/skip_census.py skip.txt              # 运行期分类报告
python tests/skip_census.py --static --json        # 静态口径清单
python tests/fixture_baseline.py                   # fixture 基线汇总
```


### 7.14 R11-5：CI 红灯暴露时间实测与 T-24 L3 落地（已执行，2026-09-27，第十一轮）

**① 11 次 run 耗时统计（GitHub Actions API：run `run_started_at` → 作业/步骤 `started_at`／`completed_at`）**

| # | run（sha） | 结论 | 排队：作业启动（相对 run 开始） | `repo-compliance` G-038 作业内完成 | `test-backend` Ruff 作业内完成 |
|---|---|---|---|---|---|
| 1 | `6434578c` | success | +302s | +15s | +30s |
| 2 | `30de04e4` | success | +3s | +13s | +43s |
| 3 | `409a5be1` | success | +3s | +14s | +46s |
| 4 | `b2a8717c` | success | +3s | +8s | +46s |
| 5 | `e1b75246` | success | +3s | +12s | +42s |
| 6 | `fed654ea` | success | +154s | +14s | +38s |
| 7 | `f1e55d4a` | **failure**（E501） | +188s | +14s | +36s |
| 8 | `73a35ed5` | **failure**（E501） | +93s | +12s | +36s |
| 9 | `e94f8ddb` | **failure**（E501） | +288s | +14s | +36s |
| 10 | `bf1a8521` | success | +471s | +10s | +40s |
| 11 | `2014219d` | success | +234s | +12s | +38s |

**中位值**：排队 **154s**；`repo-compliance` G-038 作业内完成 **+13s**（步骤自身耗时中位 9s）；`test-backend` Ruff 作业内完成 **+38s**。

**② 逐步骤对照（run `36308445948` / `7086ef0c`，排队仅 3s 的样本）**

| 作业 | 步骤（关键） | 作业内完成 | 耗时 |
|---|---|---|---|
| `repo-compliance` | checkout | +2s | 1s |
| `repo-compliance` | 前 10 个检查（compliance/bash、G-026/029、Docs sync、Capabilities、G-030/032/033/037）**合计** | +3s | ≤1s each |
| `repo-compliance` | **G-038（ruff+mypy）**（前移前位于末位） | **+13s** | 10s |
| `test-backend` | Setup Python | +4s | 2s |
| `test-backend` | **Install dependencies** | +33s | **29s** |
| `test-backend` | **Ruff check（G-038）** | **+34s** | 1s |

→ 前移后 G-038 紧跟 checkout（+2s）执行，作业内完成 ≈ **+12s**（收益 ≈ **1s**）；`test-backend` 的 Ruff 受 `Install dependencies` 独占 29s 拖累，作业内 **+34s**。

**③ 实施**：`.github/workflows/ci.yml` 的 `repo-compliance` 作业中，把 `G-038 — 历史遗留错误清零（Ruff+Mypy+裸noqa）` 步骤由**末位移到 checkout 之后第一位**（检查命令、范围、逻辑零改动；由 PyYAML 解析复核步骤顺序：checkout → G-038 → compliance → …）。

**④ 结论与更正**：T-24 L3 原表述假设“ruff 红灯要等 ~3 min（test-backend 报错）”。实测表明：**lint 红灯本就在作业内 +12~14s 由 `repo-compliance` 的 G-038 报出**（三次 E501 事故 run 均是如此），
“3 分钟”来自 **runner 排队**（11 次中位 154s）而非步骤顺序；故 L3 的实质收益＝让 lint 成为作业内**首个**信号（顺序收益 ~1s）。真正的杠杆（并发组按 ref 拆分／下游重作业 `needs` 门控）已登记 **T-30**。

**⑤ 复现命令**（探针不入库，存仓库外）：
```
python <probe>/r11_5_timing.py     # 11 次 run 的排队与步骤完成时刻表
python <probe>/r11_5_steps.py      # 单个 run 的逐步耗时（repo-compliance / test-backend 对照）
python -c "import yaml;d=yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8'));print([s.get('name') for s in d['jobs']['repo-compliance']['steps']])"
```


### 7.15 R12-1：T-30 排队归因取数与方案对比（已执行，2026-09-27，第十二轮；只读，未改 CI）

**① 三源归因（GitHub Actions API 全量 78 个 run）**

| 源 | 判据 | 实测 | 结论 |
|---|---|---|---|
| **自串行（并发组）** | 某 run 创建时，是否有更早的 run `updated_at > created_at` | **26/78 = 33%** 被挡住；等待 1／1／1／1／13／73／90／129／153／186／231／247／286／300／321／332／470／653／678／699／705／1132／1179／1211／1216／1340 s（被挡样本中位 ≈300s） | **主因**（由本仓库 `concurrency: group: ci-cd` + `cancel-in-progress: false` 造成） |
| **runner 分配** | 未被挡 run 的作业启动时刻 | **+3s**（多次一致） | 不是瓶颈 |
| **bump 额外 run** | head 为 `chore: bump version` 的 run 数 | **0 个**（`GITHUB_TOKEN` 推送不触发 workflow） | 假设证伪 → 登记 T-31 |

**② 关键路径（最近 10 个已完成 run 的逐作业时长，中位）**

| 作业 | 中位时长 | 说明 |
|---|---|---|
| **`test-gui-unit`** | **467s** | **关键路径第一名**；`version`／`docker`／`exe` 都要等它 |
| `test-gui-coverage` | 215s | 依赖 test-backend 的覆盖率产物 |
| `test-backend` | 184s | 含 94~133s 的 pytest |
| `exe` | 176s | 需 `version` 的产物 |
| `test-e2e` | 103s | — |
| `docker` | 93s | 需 `version` 的产物 |
| `frontend-e2e` | 79s | Playwright |
| `test-frontend` | 55s | — |
| `e2e-coverage` | 45s | — |
| `security-scan` | 35s | — |
| `repo-compliance` | 16s | 已含前移后的 G-038 |
| `version` | 8s | 等全部测试作业 |

run 总时长中位 **828s**；关键路径 ≈ `test-gui-unit` 467s → `version` 8s → `docker`/`exe` ≈176s。

**③ 方案对比（A~F，均待用户选型；R12-1 不落地任何一条）**

| 方案 | 机制 | 依据实测的预期效果 | 风险 | 成本 |
|---|---|---|---|---|
| **A 并发组按 ref 拆分** | `group: ci-cd-${{ github.ref }}` | 同 ref 的 run 并行 → 33% 的等待消失；**CI 分钟近翻倍** | 中高：`version` bump／`docker`/`exe` tag 竞态需额外设计 | 2~3 commit |
| **B 取消旧 run** | 保留单组 + `cancel-in-progress: true` | 新推送立即开始（等待≈0），但被取消 run **无完整验证** | 中：连续推送时前一次验证被腰斩 | 1 行 + 1 run 观察 |
| **G（推荐）按 ref 单组 + 取消**（A∩B 的最小版） | `group: ci-cd-${{ github.ref }}` + `cancel-in-progress: true` | 消除 33% 自串行等待；**分支推送不再阻塞 main**（现状是全局组共享）；同 ref 只保留最新 run | 低-中：被打断的 main run 无完整结论（其提交会被下一次 run 覆盖验证） | 1~2 commit |
| **C lint-fast 门控** | 新增轻量 lint 作业 + 重作业 `needs` | 失败 run 时长 828s → ~60s；成功路径 +~15s 串行 | 低 | 1~2 commit |
| **D 缩短 `test-gui-unit`（467s）** | 拆分／并行／减覆盖率开销 | run 总时长 ≈828 → ~610s（−26%），排队上限同步下降 | 中：GUI 测试拆分曾与 #34 抖动同源，须谨慎 | 2~4 commit |
| **E `docker`/`exe` 与测试并行** | 只让**发布**依赖测试，构建与测试重叠 | run 总时长 ≈828 → ~500s（−40%） | 中：构建与版本号时序需重设计 | 2~4 commit |
| **F 接受 + 流程约定** | 推送前确认上一个 run 已结束 | 等待消失，但每批节奏被 run 时长（≈14 min）限制 | 低 | 0 |

**④ 推荐路线**：R12-2 先落 **G**（1~2 commit，收益最大/风险最低）并观察 3 次 run 的排队指标；R12-3 视情况落 **C**（与 P2 的 T-28 同批）；**D/E** 作为“缩短关键路径”专项，在 G 的效果数据出来后再评估（避免同时动队列与关键路径导致归因不清）。

**⑤ 复现命令**（探针不入库，存仓库外）
```
python <probe>/r12_1_queue.py      # 全量 run 的三源归因（自串行/时长/提交类型）
python <probe>/r12_1_critical.py   # 最近 10 个 run 的逐作业时长与关键路径
```


### 7.16 R12-2：方案 G + T-28 落地（已执行，2026-09-27，第十二轮）

**① 改动清单（仅 CI 配置，检查逻辑零变更）**

| 文件 | 位置 | 改动 |
|---|---|---|
| `.github/workflows/ci.yml` | 顶层 `concurrency` | `group: ci-cd` → **`ci-cd-${{ github.ref }}`**；`cancel-in-progress: false` → **`true`**（方案 G） |
| `.github/workflows/ci.yml` | `test-backend` → `Run backend tests` | pytest 命令加 **`-rs`**（T-28：跳过明细进日志） |

**② 生效机制与代价**

| 维度 | 旧（全局单组 + 不取消） | 新（按 ref 单组 + 取消） |
|---|---|---|
| 同 ref 连续推送 | 后一个 run **排队等前一个跑完**（实测被挡中位 ≈300s、最长 1340s） | 新 run **取消**该组内旧 run 并立即开跑（排队≈0） |
| 分支/PR 推送 | 与 main **共用** `ci-cd` 槽位 → 互相阻塞 | 各自 `ci-cd-refs/heads/<branch>` / `ci-cd-refs/pull/<n>/merge`，互不阻塞 |
| 代价 | 无 | **被取消的旧 run 无完整结论**（其提交内容会被下一次 run 的检出覆盖验证）；本仓库 bump 提交由 `GITHUB_TOKEN` 推送、不触发 workflow（T-31），故无额外冲突面 |

**③ 观察口径（判定是否生效）**：指标＝**作业启动延迟** ＝ `job.started_at − run.run_started_at`。

| 基线（R12-1 实测，78 run） | 目标 |
|---|---|
| 未被挡样本 **+3s**；被挡样本中位 **≈300s**（26/78 = 33% 的 run 被挡） | 连续 3 次 run 的中位作业启动延迟 **≤10s** |

**④ 首个数据点**：R12-2 推送后按上述口径实测，数值记入 R12-3 批次（同批记录 3 次观察）。**方法**：
```
python -c "…读取 runs?per_page=N，对目标 run 取 jobs，算 job.started_at − run.run_started_at 的中位…"
# 或复用探针：<probe>/r12_1_queue.py（三源归因） / r12_1_critical.py（关键路径）
```



**⑤ 首个数据点与同窗对照（R12-2 推送后实测，2026-09-27）**

| run | 并发组 | sha | 作业启动延迟（`job.started_at − run.run_started_at`） |
|---|---|---|---|
| **R12-2** `36309693229` | **`ci-cd-refs/heads/main`（新）** | `46a4a67f` | **中位 +2.0s**（2.0／2.0／2.0／2.0／3.0／3.0／4.0，n=7） |
| R12-1 `36309485009`（同窗对照） | `ci-cd`（旧，与 R11-5 的 run 串行） | `5e34f862` | **中位 +198s**（197~257） |

基线（R12-1 的 78 run 统计）：未被挡 +3s、被挡中位 ≈300s、被挡比例 33%。→ **G 生效**（+2.0s ≤ 目标 10s）；对照组 +198s 即旧模型行为。
**附带事实**：R12-1 的 run 因组名不同**未被取消**，其验证完整保留。

**⑥ T-28 的 CI 实证（同一 run）**：`test-backend` 日志含 **44 条** `SKIPPED [n] path:line: reason`（此前只有汇总行），首 12 条均为 `tests/test_e2e_adapters.py` 的「CI 环境跳过网络依赖测试」（类级 `@unittest.skipIf(_CI)`），与 R12-1 归因吻合；汇总 `4007 passed, 44 skipped, 22 warnings, 4 subtests passed in 130.38s`。
**R12-2b 补充**：`-rs` 由 1 处扩到**全部 5 处** pytest 调用（复核脚本 5/5 ✓）。

### 7.17 R12-3：方案 C（lint-fast 门控）落地与受控失败实验（已执行，2026-09-27，第十二轮）

**① 改动（`.github/workflows/ci.yml`，仅作业结构与 `needs`）**

| 项 | 内容 |
|---|---|
| 新增作业 | **`lint-fast`**：checkout（`fetch-depth: 1`）→ `setup-python`（3.12 + pip cache）→ `pip install ruff mypy` → `python scripts/check_g_038_legacy_errors.py` |
| 下游门控（9 个） | `test-backend`、`test-gui-coverage`（`needs: [lint-fast, test-backend]`）、`e2e-coverage`（原 `needs: []`）、`security-scan`、`test-frontend`、`test-e2e`、`frontend-e2e`（`needs: [lint-fast, test-frontend]`）、`test-gui-unit`、`repo-compliance` |
| 传递性门控 | `version`（原 `needs` 8 作业）→ `docker`／`exe`（`needs: version`）：`lint-fast` 失败 → 上游 skipped → 三者 skipped |
| 未改动 | G-038 脚本与 ruff/mypy 范围、`repo-compliance` 内的同名步骤（**保留**作纵深防御）、任何测试逻辑 |

**② 预期与判定口径（受控失败）**

| 判据 | 目标 | 基线（失败 run） |
|---|---|---|
| `lint-fast` 失败耗时 | ≈20~40s | — |
| 下游作业状态 | **skipped**（未触发） | 全部真实执行 |
| 失败 run 总时长 | **≤60s** | **828s**（中位） |

**③ 受控失败实验设计（无需 `--no-verify`）**

实测确认：`ruff check pilotstd/` 与 `check_g_038_legacy_errors.py` **都会检查 `.pyi`**（长行判 E501），而本地 pre-commit 的 L1 触发式 `^scripts/|`+`\\.py$` **漏 `.pyi`** → 因此可在**一次性分支**上提交 `pilotstd/_r12_3_probe.pyi`（142 字符注释行）而**不绕过任何钩子**：
  · 分支组名 `ci-cd-refs/heads/probe/r12-3-lint-gate`（按 ref 分组后**与 main 完全隔离**，不干扰主线）；
  · 观察点：① `lint-fast` 结论与耗时；② 其余 12 个作业是否全部 skipped；③ run 总时长；
  · 实验后立即删除远端与本地分支，主分支不受影响（该缺口另登记 **T-32**）。

**④ 其余观察数据（R12-3 主分支推送后实测）**：第 3 个 run 的作业启动延迟（G 的第一阶段收口判据）与实验结果一并记入 R12-3b 批次。

### 7.18 R12-3b：方案 C 受控失败实证、G 数据点 3 与 #34 哨兵触发（已执行，2026-09-27，第十二轮）

**① 受控失败实验（目标：验证「快闸快速失败 + 下游不启动 + 修复后全绿」）**

| 步 | 动作 | 结果 |
|---|---|---|
| 1 | 一次性分支 `probe/r12-3-lint-gate` 注入 `pilotstd/_r12_3_probe.pyi`（142 字符行）并提交 | 提交**未绕过钩子**（L1 触发式漏 `.pyi`，见 T-32）；分支推送**未产生 run**——因 `.github/workflows/ci.yml` 的 `on.push.branches: [main]` 只对 main 生效 |
| 2 | 改为 **PR #8**（`pull_request` 事件）触发 | run `36310949966`，head `4bc58444` |
| 3 | 观察 | **run 结论 failure，总时长 19.0s**（基线 828s，**−97.7%**）；`lint-fast` **failure，时长 16.0s**；日志 `❌ G-038 … Ruff 检查失败：E501 Line too long (142 > 120)`；**下游 12 个作业全部 skipped**（test-backend／test-gui-unit／test-frontend／test-e2e／frontend-e2e／repo-compliance／e2e-coverage／security-scan／test-gui-coverage／version／docker／exe） |
| 4 | 清理 | PR #8 关闭、远端与本地分支删除、`git status` clean、**main 未受影响**；修复路径＝删除探针文件（PR 关闭即等价），主分支无需“修复提交” |

**判定**：① 快闸快速失败 ✅（16s）；② 下游未被触发 ✅（12/12 skipped）；③ 失败 run 总时长 19.0s ≤ 60s 目标 ✅（−97.7%）。**唯一未满足**：指令中的“修复后重推全绿”在 main 侧被 **#34 复发**（见 ④）打断——与本方案无关。

**② G 第 3 个数据点（R12-3 的 run `36310444541`，2026-09-27T09:46:37Z）**

| 作业 | 启动（相对 run） | 时长 | 结论 |
|---|---|---|---|
| `lint-fast (G-038)` | **+16.0s** | 14.0s | success |
| 下游 8 个（test-backend／e2e-coverage／repo-compliance／test-e2e／test-frontend／test-gui-unit／security-scan／frontend-e2e） | +32.0~89.0s | — | 6 success／**test-gui-unit failure**／test-gui-coverage +216.0s |
| `version`／`docker`／`exe` | +442.0s | — | skipped |

**分析（16.0s 的构成与阈值语义）**：
  · 该 run 创建时**同 ref 的 R12-2b 正在飞**（09:39:52 起）→ 被本次推送**取消**（`7c478c6f` 结论＝cancelled，实证取消语义）；同时 runner 需为新年 job 分配机器 → **首个作业启动 = 分配延迟 + 门控前开销**，不再是纯“并发组排队”。
  · 门控落地后，**下游作业的启动时刻由 `lint-fast` 完成时间决定**（+32.0s），「所有作业同时起跑」的旧指标语义已改变。
  · 与旧模型对比：旧组同窗对照 R12-1 `36309485009` = **+198s**（被挡），R12-1 的 78 run 统计被挡中位 **≈300s** → 队列效应确已消除。
  **结论建议**：G 按“**队列效应消除**”收口（指标改写为“首个作业启动延迟 ≤20s 且旧组同窗对照 ≥100s”），或再取一次空闲窗口的测量；**采纳与否待用户裁定**。

**③ 方案 C 的绿灯代价（实测）**：`lint-fast` 启动 +16.0s、时长 14.0s → 下游首个作业 **+32.0s**；即绿灯路径新增 ≈ **28~32s**（原估 +20s）。

**④ ⚠️ #34 哨兵触发（T-26）**

| 项 | 内容 |
|---|---|
| run / job | `36310444541`（sha `85fa65f0`）／`test-gui-unit` job `108595281670` |
| 失败步骤 | `Run GUI unit tests`（第 5 步 failure；`Tests passed — checking coverage thresholds` 被 skipped） |
| 日志指纹 | `tests/gui/test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe FAILED` → `Windows fatal exception: access violation` → exit 1（09:50:54Z） |
| 与历史对比 | 与 #34 行记录的两次**逐行同构**（同一测试、同一异常）；R1（teardown 等待 5s + `waitForDone` + 到期不 reset）**仍在位却未拦住** |
| 触发规则 | T-26 预先约定「再复发 ≥1 次 → 当轮必须做 R2 + R4」→ **R2/R4 为第十二轮强制项** |
| R2 计划 | `reset()` 静止协议：`_resetting` 期间 `publish()` 直接返回；单例销毁改 `deleteLater()` 或延迟到 in-flight publish 结束；`pilotstd/ui/core/event_bus.py:57-88` + `tests/gui/test_event_bus_integration.py` 覆盖 |
| R4 计划 | CI/本地环境对齐：装 Python 3.12 + Qt 6.11.2，循环跑 `tests/gui/` 统计频率，把“堆已破坏”的推断升为实证 |
| 影响 | 该 run 结论 failure（连带 `version`／`docker`／`exe` skipped）；与本批 CI 改动**无关**（快闸与其余 9 个下游作业均 success） |

**⑤ 复现命令**（探针不入库）
```
python <probe>/r12_3_full.py      # 单个 run 的完整时序（首个作业启动/快闸时长/下游启动/总时长）
python <probe>/r12_3_probe_pr.py  # 受控失败实验（建 PR → 观察 → 关闭 PR + 删分支）
python <probe>/r12_3_gui_diag.py  # test-gui-unit 失败诊断（步骤 + 日志指纹）
```

### 7.19 R12-4：R2 静止协议、R4 环境对齐实证与 T-32 关闭（第十二轮）

**① T-32（L1 触发式漏 `.pyi`）——双向受控验证**

| 方向 | 动作 | 结果 |
|---|---|---|
| 修复前 | 暂存/提交 `pilotstd/_r12_3_probe.pyi`（142 字符行） | L1 未触发 → 提交成功（R12-3b 借此做到“不绕过钩子”的受控失败实验） |
| 修复后 | 暂存 `pilotstd/_t32_probe.pyi`（142 字符行）后跑 `--fast --guards --local` | L1 **触发**：`📋 暂存 .py/.pyi/.pyw/scripts 变更：pilotstd/_t32_probe.pyi` → `E501 Line too long (142 > 120)` → `❌ [FAIL] L1 ruff check`，**EXIT=1** |

改动：`scripts/check_all.sh` 触发式 `grep -E '^scripts/|\.py$'` → **`grep -E '^scripts/|\.py[wi]?$'`**（+ 文案/注释同步）。**T-32 ✅ CLOSED。**

**② R4：CI 同口径环境下的循环复现探针**

新增独立工作流 `.github/workflows/gui-race-probe.yml`（**仅 `workflow_dispatch`**）：

| 项 | 内容 |
|---|---|
| 环境 | `windows-latest` + **Python 3.12** + `desktop/requirements-win.txt` + `requirements-dev.txt` + **`PyQt6==6.11.2` / `PyQt6-Qt6==6.11.2`**（与 `test-gui-unit` 同口径）；启动时打印 python/Qt/PyQt 指纹 |
| 循环 | `python -m pytest tests/gui/test_event_bus_integration.py -q --timeout=120 --timeout_method=thread`，迭代次数由输入 `loops` 决定（默认 30） |
| 产物 | 每次迭代打印 `=== iteration i / N ===` 与退出码；结尾 `=== RESULT: loops=N failures=M ===`，M>0 即 `exit 1` |
| 为什么独立文件 | `workflow_dispatch` 会执行该文件内**全部**作业——放进 `ci.yml` 会让每次探针连带跑完整 14 作业流水线，既慢又污染归因 |
| 触发方式 | `gh workflow run gui-race-probe.yml -f loops=50` 或 Actions UI |

**③ R2：静止协议（代码随 R12-4b 提交）**——`pilotstd/ui/core/event_bus.py`：

| 步 | 机制 | 目的 |
|---|---|---|
| ① 关门 | 类级 `_resetting=True` + 实例级 `_accepting=False` + 清空订阅者 | `publish()` 在 reset 窗口/退役实例上**无副作用直接返回**（不入队、不抛异常）；`subscribe`/`unsubscribe` 同样门控 |
| ② 有界排空 | 实例属本线程 → `processEvents()` 跑完已排队 deliver；**不再用无界 `BlockingQueuedConnection`** | 实测（R12-4 冒烟用例）无界阻塞在“实例线程亲和性无事件循环”时会永久挂住 teardown |
| ③ 延迟销毁 | `deleteLater()` | 不在此刻同步析构 QObject，切断 use-after-free 窗口 |
| ④ 复位 | 清 `_resetting` | 保证后续 publish 正常 |
| 附加 | `publish()` 的**入队动作移入临界区** | reset() 拿到锁即意味没有 in-flight publish 正在入队（“确保 in-flight publish 结束”） |
| 附带 | `deliver()` 对退役实例直接丢弃 | 门闸兜底，安全性不依赖排空 |

新增受控用例 6 例（`TestResetQuiescenceProtocol`）：门闸复位／退役实例 publish no-op／reset 窗口内 publish no-op／窗口内 subscribe no-op／reset 后得到全新实例／**多线程 publish 与 reset 并发不抛异常**（该用例正是暴露“无界阻塞会挂住”的那一例）。
**本地实测**：`tests/gui/test_event_bus_integration.py` → **19 passed in 101s**（含原 13 例 + 新 6 例，其中 CI 曾失败的 `TestThreadSafety::test_concurrent_subscribe` 通过）。

**④ 取证数据**：R4 探针的“修复前／修复后”两次派发结果与本地 20 轮循环结果记入 R12-4b 批次。

