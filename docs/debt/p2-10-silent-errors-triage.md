# P2-10 静默吞错 triage（批 1）

> 日期：2026-11-13  
> 基线：HEAD `635e0e93`（批 1 改动前）  
> 门禁：G-050 `scripts/check_g_050_silent_errors.py` + `scripts/silent_errors_baseline.json`  
> 范围：只做**非迁移文件**；迁移文件受 P-106 约束（不改源码），基线只用于阻止新增。

---

## 一、总量与口径

G-050 按 AST 统计三类"失败不可见"：

| 类别 | 定义 | 批 1 前 | 批 1 后 | 批 2 后 |
|---|---|---|---|---|
| `pass` | `except` 体只有 `pass` | 46 | 46 | 46 |
| `return` | `except` 体只有 `return <空/False/None>` | 50 | 49 | 48 |
| `debug` | `except` 体内只有 `logger.debug` | 72 | 70 | 70 |
| **合计** | | **168** | **165** | **164** |

拆分：迁移文件 **40** 条（冻结）、非迁移 **128 → 126** 条。  
批 1 处理 **50** 条（47 条 allowlist + 3 条升级 warning，见第三节）；批 2 处理 **22** 条 scripts（21 allowlist + 1 升可见，见第七节）。

---

## 二、判定规则

- **warning（改代码）**：失败意味着核心承诺被静默破坏、用户配置/数据有丢失风险，或失败后无法自愈且生产日志不可见。要求低频（不会每次请求都刷）。
- **allowlist（保留原级别）**：失败后的回退就是预期行为、无数据丢失、或处于每次调用都执行的热路径（升 warning 会刷屏）。理由必须写进本表；基线本身就是白名单。
- **不允许**：为过门禁而加 `# noqa` / `skipif` / 空 `except` 注释（AGENTS §三.2）。

---

## 三、批 1 清单（50 条）

### 3.1 升级为 warning（3 条，已改）

| 位置 | 类别 | 判定 | 理由 |
|---|---|---|---|
| `docker/_static_token.py:66` `_ensure_static_token_in_db` | debug | **warning** | 静态 API Key 落库失败；若永久失败，`pst_static` Key 静默不可用。原注释写"要留痕"却只在 debug。 |
| `docker/scheduler.py:118` `_prune_old_backups` | return | **warning** | 备份目录不可读 → 保留策略静默失效，备份只增不减会撑满磁盘。 |
| `pilotstd/core/config/manager.py:225` `_load` `.bak` 分支 | debug | **warning** | 主配置损坏 + 写前备份不可用 → 下一步即以默认值覆盖用户配置，是"静默丢配置"的唯一现场。 |

### 3.2 allowlist（47 条，保留原级别）

| 位置 | 类别 | 理由 |
|---|---|---|
| `docker/api/adapter.py:86` | debug | 适配器显示名回退为适配器名；失败仅影响展示文案 |
| `docker/api/organize.py:100` | debug | 清空目录 best-effort；目录非空/占用是常态 |
| `pilotstd/announcement/_circuit_breaker.py:63` | debug | 配置非法 → 默认冻结档位；每次熔断调用都读，升 warning 会刷屏 |
| `pilotstd/announcement/ocr/_pdf_utils.py:56` | debug | 线程优先级属性能优化，失败不影响 OCR 结果 |
| `pilotstd/core/_file_index_query.py:155` | debug | 缓存 JSON 损坏 → 回退重新解析，数据源仍可用 |
| `pilotstd/core/_file_index_query.py:253` | debug | 同上（批量版） |
| `pilotstd/core/_validity_pipeline.py:57` | debug | 只补详情列表名称；有效性判定不受影响（源码注释已裁定） |
| `pilotstd/core/audit.py:84` | debug | `detail` 非法 JSON 时保留原字符串，审计行不丢 |
| `pilotstd/core/cache_manager.py:262` | debug | DB 体积统计探针，失败只影响展示 |
| `pilotstd/core/cache_manager.py:291` | debug | PRAGMA 估算失败 → 用默认估算 |
| `pilotstd/core/cache_manager.py:300` | debug | 行数统计失败 → 跳过该表 |
| `pilotstd/core/cache_manager.py:354` | debug | `cache_config` 读失败 → 用默认值；DB 故障会在别处暴露 |
| `pilotstd/core/cache_manager.py:363` | debug | 同上 |
| `pilotstd/core/cache_manager.py:372` | debug | 同上 |
| `pilotstd/core/config/manager.py:183` | debug | 清理崩溃残留 `.tmp`；失败不影响加载 |
| `pilotstd/core/config/manager.py:230` | debug | 损坏文件改名备份失败；后续仍初始化默认值，主告警已在 `.bak` 分支 |
| `pilotstd/core/config/paths.py:26` | debug | 冻结包目录探测失败 → 回退 `%APPDATA%`，有注释边界 |
| `pilotstd/core/file_index.py:71` | debug | 停止时 `close_all` 失败；进程即将退出 |
| `pilotstd/core/file_index.py:97` | debug | 启动校验延迟查询失败 → 固定 10s |
| `pilotstd/core/file_index.py:122` | pass | GBK 控制台导致日志输出失败；不影响校验结果（已评审） |
| `pilotstd/core/file_utils.py:69` | debug | NFKC 归一化失败 → 保留原名（幂等降级） |
| `pilotstd/core/file_utils.py:270` | debug | 移动失败后的临时目标清理失败；主错误已 `logger.error` |
| `pilotstd/core/file_utils.py:329` | debug | 清理系统垃圾文件失败 → 目录保留 |
| `pilotstd/core/file_utils.py:334` | debug | `rmdir` 失败（非空/占用）→ 目录保留 |
| `pilotstd/core/logger.py:180` | return | 探测控制台流可用性；异常即"不可用" |
| `pilotstd/core/name_resolution.py:83` | return | 列探测失败 → 视为无该列（降级不抛） |
| `pilotstd/core/name_resolution.py:101` | return | 缓存 JSON 非法 → 空名，调用方回退 |
| `pilotstd/core/name_resolution.py:134` | return | 缓存表懒建期查询失败 → 空名 |
| `pilotstd/core/notification/_builders_common.py:58` | return | 发布日期非法 → 不显示生效日 |
| `pilotstd/core/notification/_credentials.py:242` | return | 旧配置回退读取（仅显式迁移用）；失败即"无旧配置" |
| `pilotstd/core/notification/_dispatcher.py:52` | debug | 可见性记录不得影响主流程（源码注释裁定） |
| `pilotstd/core/notification/_links.py:54` | return | 配置桩缺 `get` → 空链接 |
| `pilotstd/core/notification/_policy.py:40` | debug | 策略列坏 JSON → 空列表；每次派发都读，升 warning 会刷屏 |
| `pilotstd/core/notification/channels/base.py:78` | return | `retry after` 解析失败 → 回退固定退避 |
| `pilotstd/core/notification/channels/wechat.py:214` | debug | 错误响应体读取失败的原因已写进可见 `body` |
| `pilotstd/core/notification_aggregator.py:447` | debug | Web 端无 PyQt6 → 直接显示，正常分支 |
| `pilotstd/core/notification_aggregator.py:524` | return | 配置读失败 → 默认开启自动暂停 |
| `pilotstd/core/task/manager.py:52` | debug | `result_json` 半截写入 → 空 dict（数据质量问题） |
| `pilotstd/download/adapters/openstd_download.py:253` | debug | 详情页预访问失败 → 继续验证码链路 |
| `pilotstd/download/adapters/openstd_download.py:277` | debug | 全文页打开失败 → 继续验证码链路 |
| `pilotstd/manager/facade/__init__.py:75` | debug | `standard_info_cache` JSON 非法 → 跳过缓存 |
| `pilotstd/manager/facade/_organize.py:189` | debug | 缓存 `result_json` 非法 → 用文件名派生名称 |
| `pilotstd/manager/facade/_organize.py:191` | debug | 缓存表查询失败 → 用文件名派生名称 |
| `pilotstd/manager/organize/expire.py:57` | debug | 过期目录 `rmdir` 失败（非空/占用） |
| `pilotstd/manager/organize/mirror.py:123` | debug | 清只读失败 → 后续 `move` 失败会被上层记录 |
| `pilotstd/manager/organize/mirror.py:138` | debug | 同上（文件级） |
| `pilotstd/query/__init__.py:64` | return | mock 适配器可选导入 |

---

## 四、代码变更（3 条）

| 文件 | 变更 | 测试 |
|---|---|---|
| `docker/_static_token.py` | `logger.debug` → `logger.warning`，文案注明"下次请求重试" | `tests/test_p2_10_silent_error_triage.py::test_static_token_init_failure_warns` |
| `docker/scheduler.py` | `except OSError: return []` → 先 `logger.warning` 再返回 | `...::test_prune_backup_dir_unreadable_warns` |
| `pilotstd/core/config/manager.py` | `.bak` 回滚失败 `logger.debug` → `logger.warning` | `...::test_corrupt_config_with_unusable_bak_warns` |

新增测试 3 例，`python -m pytest tests/test_p2_10_silent_error_triage.py -q` → 3 passed；  
回归 `tests/unit/core/config` + `tests/test_backup_retention.py` + `tests/test_scheduler_extra.py` → 42 passed。

---

## 五、基线收紧

`scripts/silent_errors_baseline.json` 由 `--emit` 重新生成：批 1 后 `pass 46 / return 49 / debug 70`（168 → 165），批 2 后 `pass 46 / return 48 / debug 70`（165 → 164）。  
`python scripts/check_g_050_silent_errors.py` → PASS。

---

## 六、剩余 28 条（批 4）

| 区域 | 条数 | 说明 |
|---|---|---|
| `pilotstd/ui/` | 28 | Qt 生命周期/事件总线/文件树，多为关闭/销毁路径的 best-effort |

---

## 七、批 2 清单（scripts 22 条；21 allowlist + 1 升可见）

| 位置 | 类别 | 判定 | 理由 |
|---|---|---|---|
| `scripts/check_g_013_test_coverage.py:234` | return | **升可见** | 读 commit message 失败返回 `''` 会让规则 0（fix 必须带测试）失效；改为 stderr `[WARN]` 后仍返回空串 |
| `scripts/fix_relative_imports.py:34` | return | allowlist | 文件不在扫描根内 → `None`（路径判定，非错误） |
| `scripts/fix_relative_imports.py:64` | return | allowlist | 解析失败 → 空集合；语法错误由 ruff 兜底 |
| `scripts/fix_relative_imports.py:98` | return | allowlist | 无法解析相对导入 → `False`（不改写即最安全） |
| `scripts/audit_api_matrix.py:115` | return | allowlist | 非字面量 → `None`（抽取器按"未知"处理，偏保守） |
| `scripts/audit_api_matrix.py:150` | return | allowlist | 白名单文件读不到 → `()`（所有路由按非公开，偏严格） |
| `scripts/check_g_013_test_coverage.py:365` | return | allowlist | 语法错误 → `None`，已注释"交由其他门禁处理" |
| `scripts/check_property_proxy.py:57` | return | allowlist | 非字面量 → 空集合（白名单解析偏严格） |
| `scripts/check_property_proxy.py:73` | return | allowlist | 语法错误 → 空集合（ruff 兜底） |
| `scripts/check_relative_imports.py:63` | return | allowlist | 不在包内 → `None`（路径判定） |
| `scripts/check_relative_imports.py:227` | return | allowlist | 解析失败 → 空集合（ruff 兜底） |
| `scripts/update_status.py:56` | pass | allowlist | 测试 JSON 解析失败 → 回退统计测试文件数（状态生成器，非门禁） |
| `scripts/update_status.py:81` | pass | allowlist | 门禁输出解析失败 → `—`（状态生成器） |
| `scripts/_chain_scan_guards.py:25` | return | allowlist | AST 读不到 → `None`，审计脚本跳过该文件 |
| `scripts/_docs_sync_io.py:196` | return | allowlist | `claude` 不可用 → `False`（有文档说明，走只提示分支） |
| `scripts/_gate_paths.py:47` | return | allowlist | 路径在 root 之外 → `False`（不参与 gitignore 判定） |
| `scripts/check_g_015_relative_imports.py:71` | return | allowlist | `__init__.py` 语法错误 → `False`（ruff 兜底） |
| `scripts/check_g_029_test_coverage.py:50` | return | allowlist | git 失败 → `None`，调用方判 FAIL（与"0 个文件"区分） |
| `scripts/check_i18n_hardcoded_python.py:223` | return | allowlist | 基线 JSON 坏 → 空基线（会让所有命中变"新增"，偏严格） |
| `scripts/check_no_conflict_markers.py:96` | return | allowlist | 二进制/不可读文件跳过（冲突标记只在文本里） |
| `scripts/docs_sync_check.py:423` | pass | allowlist | stdout 重配编码失败 → 忽略（不影响判定） |
| `scripts/find_docs.py:28` | return | allowlist | 读不到文档 → 空串（检索工具，不中断全量） |

**批 2 结论**：scripts 是门禁自身，但这 22 条要么是"读不到 → 保守回退（更严格）"，要么是"语法错误交给 ruff"，没有发现第二处假绿；唯一会让规则失效的 `check_g_013` 已升 `[WARN]`。

---

## 八、批 3 清单（query 19 + wechat_ip 5 + scan 4 = 28 条；全部 allowlist）

判定口径：网络/解析/浏览器回退的失败由**上层结果**（查询命中率、通知、页面状态）暴露，
逐条升 warning 会在批量查询时刷屏；语法/编码错误由 ruff、G-047 兜底。

| 位置 | 类别 | 理由 |
|---|---|---|
| `pilotstd/query/adapters/csres.py:228` | debug | 替代标准网络请求失败 → 本轮无替代信息；路由链继续 |
| `pilotstd/query/adapters/dbba.py:92` | debug | 实施日期解析失败 → 保留原值 |
| `pilotstd/query/adapters/hbba.py:144` | debug | 同上 |
| `pilotstd/query/adapters/hbba.py:192` | debug | 替代标准请求失败 → 本轮无替代信息 |
| `pilotstd/query/adapters/njbz365.py:150` | debug | 同上 |
| `pilotstd/query/adapters/nrsis.py:94` | pass | 编码回退循环：该编码解不开 → 试下一个 |
| `pilotstd/query/adapters/nrsis.py:100` | pass | 同上 |
| `pilotstd/query/adapters/tdpress.py:37` | return | 日期/编码解析失败 → 空串 |
| `pilotstd/query/adapters/ttbz.py:108` | debug | 站点网络异常 → 返回空结果，路由链继续 |
| `pilotstd/query/engine/_batch_dispatcher.py:342` | debug | 指标自增失败，不影响查询 |
| `pilotstd/query/engine/_routing.py:75` | debug | 评分器失败 → 回退硬编码路由（已在 core.md 登记） |
| `pilotstd/query/network.py:123` | debug | 重试期间日志；最终失败由调用方记录 |
| `pilotstd/query/rotator.py:415` | debug | 冷却状态恢复失败 → 跳过，下一轮重建 |
| `pilotstd/query/routing/router_v2_metrics.py:45` | debug | 指标写库失败，不影响路由 |
| `pilotstd/query/routing/router_v2_metrics.py:56` | debug | 指标入队失败，不影响路由 |
| `pilotstd/query/routing/scorer.py:108` | debug | 站点配置覆盖读取失败 → 默认权重（core.md 已登记） |
| `pilotstd/query/search_strategy.py:250` | return | 策略解析失败 → 空串，调用方跳过 |
| `pilotstd/query/search_strategy.py:331` | return | 同上（布尔分支） |
| `pilotstd/query/site_config/_loader.py:49` | return | 站点配置读不到 → 空 dict，用默认 |
| `pilotstd/scan/parser/_exact_matcher.py:54` | return | 值解析失败 → None，按不匹配处理 |
| `pilotstd/scan/parser/_exact_matcher.py:110` | return | 同上 |
| `pilotstd/scan/parser/_number_extractor.py:62` | return | 数字提取失败 → None，交由后续解析器 |
| `pilotstd/scan/watcher.py:71` | debug | 索引写入失败（文件被锁/删除）→ 下次事件重试 |
| `pilotstd/wechat_ip/browser.py:148` | debug | 关闭浏览器失败；进程即将退出 |
| `pilotstd/wechat_ip/browser.py:172` | return | 启动失败 → False，调用方发 security_alert（远程已见） |
| `pilotstd/wechat_ip/browser.py:296` | return | 同上 |
| `pilotstd/wechat_ip/detector.py:32` | return | IP 格式非法 → False（视为未变化） |
| `pilotstd/wechat_ip/detector.py:53` | debug | 单个检测源失败 → 换下一个源 |

**批 3 结论**：28 条全部 allowlist，无代码变更；基线保持 `164`（pass 46 / return 48 / debug 70）。

---

## 九、批 4 清单（`pilotstd/ui/` 28 条；2 条升 warning + 26 条 allowlist）

判定口径（Qt 侧与业务侧不同）：**Qt 对象生命周期竞态（对象已销毁/信号已断开）属预期分支**，
逐条升 warning 会在每次关窗/刷新时刷屏；反过来，**用户主动触发、失败后界面显示"看起来正常"**
的两处必须升 warning。

| 位置 | 类别 | 判定 | 理由 |
|---|---|---|---|
| `pilotstd/ui/core/handlers/_cleanup.py:135` | debug | **warning（已改）** | 用户点"清理空目录"时扫描失败，界面只会显示"没有可清理目录"，看着像成功；低频、非热路径 |
| `pilotstd/ui/pages/rules_page.py:85` | return | **warning + return（已改）** | `sites.rules` JSON 损坏 → 静默按空表展示，用户再保存一次就把坏串覆盖成空表；属"配置静默丢失" |
| `pilotstd/ui/core/event_bus.py:105` | debug | allowlist | `reset()` 期间 `QApplication` 已销毁 → `processEvents` 跳过；teardown 热路径 |
| `pilotstd/ui/core/event_bus.py:150` | debug | allowlist | 退订未注册的回调 = 幂等语义（`list.remove` 抛 ValueError），不是故障 |
| `pilotstd/ui/core/event_bus.py:212` | return | allowlist | 取回调弱引用失败 → `None`（按"已失效"处理，偏保守） |
| `pilotstd/ui/core/event_bus.py:239` | return | allowlist | 判存活失败 → `False`（宁可不投递，不会误投） |
| `pilotstd/ui/core/handlers/_cleanup.py:181` | debug | allowlist | 清只读时逐文件 `chmod` 失败；真正的删除失败由 `rmtree` 分支弹窗提示 |
| `pilotstd/ui/core/handlers/_query.py:117` | return | allowlist | 取 work_table 时 C++ 对象已删 → `False`，调用方随后走重建 |
| `pilotstd/ui/core/handlers/persistence_flow_engine.py:90` | debug | allowlist | 表头 Base64 损坏 → `b""`，只影响列宽恢复，默认值可接受 |
| `pilotstd/ui/core/handlers/scan_flow_engine.py:84` | return | allowlist | 文件名里的顺序号解析失败 → `None`（非标准件是常态，不是错误） |
| `pilotstd/ui/core/handlers/scan_flow_engine.py:134` | return | allowlist | 同上（PDF 头解析分支） |
| `pilotstd/ui/drive_enumerator.py:28` | return | allowlist | `WorkerAborted` = 用户取消，属控制流而非失败 |
| `pilotstd/ui/main_window/_window_lifecycle.py:64` | debug | allowlist | 退出时 DB 备份失败 → 紧接 `shutdown()`，进程即将结束 |
| `pilotstd/ui/main_window/_window_lifecycle.py:68` | debug | allowlist | 退出时 manager 关闭失败；进程退出本身是最终兜底 |
| `pilotstd/ui/main_window/parts/_export_ops.py:44` | debug | allowlist | 导出清单逐条拼路径失败（`os.path.join` 几乎不抛），且导出结果由状态栏数字体现 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py:62` | debug | allowlist | `PyQt6.sip` 不可用 → 跳过失效判断，回退路径 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py:147` | debug | allowlist | 设置文件图标失败 = 外观降级，不影响数据 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py:152` | debug | allowlist | 无权限/被占用的子项跳过（网络盘常见，逐条，升 warning 会刷屏） |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py:154` | debug | allowlist | 同上兜底分支 |
| `pilotstd/ui/main_window/parts/_ui_setup_ops.py:403` | debug | allowlist | 非主线程注册 SIGTERM 抛 ValueError 属预期；主流程仍靠 `aboutToQuit`/`atexit` |
| `pilotstd/ui/qt_lifecycle.py:57` | return | allowlist | 旧版 PyQt6 无 `sip.isdeleted` → 视为存活（回退语义，注释已写明） |
| `pilotstd/ui/qt_lifecycle.py:74` | return | allowlist | `isdeleted` 调用异常 → 视为存活，避免误杀仍可用的对象 |
| `pilotstd/ui/qt_lifecycle.py:83` | debug | allowlist | 孤儿 worker 不在注册表（重复释放）→ 幂等 |
| `pilotstd/ui/qt_lifecycle.py:145` | debug | allowlist | `disconnect` 时已断开/对象已销毁 → 预期 |
| `pilotstd/ui/qt_lifecycle.py:165` | return | allowlist | `worker.wait` 时 C++ 对象已销毁 → 按已停止处理（返回 True 偏保守） |
| `pilotstd/ui/themes.py:290` | debug | allowlist | 非 Windows/无 DWM → 深色标题栏不生效，外观降级 |
| `pilotstd/ui/workers/_common.py:141` | debug | allowlist | `sip` 不可用 → 走回退清理，不阻断关闭 |
| `pilotstd/ui/workers/_common.py:146` | debug | allowlist | 移除日志 handler 失败（重复 close）→ 幂等 |

**批 4 结论**：28 条中 2 条升 warning（均为"用户主动操作 + 失败后界面看起来正常"），26 条 allowlist。
基线 **164 → 162**（pass 46 / return 47 / debug 69）；`scripts/silent_errors_baseline.json` 已同步收紧，
G-050 `PASS`。P2-10 到此**四个批次全部完成**。

---

## 十、基线口径（为什么 162 = 46 + 47 + 69，且没有"第四档"）

> 这一节是为了防止"164→162 到底减了什么"被误读。三档是**AST 形态分类**，不是"修好/没修好"。

| 档 | 判据（`check_g_050_silent_errors.py:105-117`） | 162 中的数量 |
|---|---|---|
| `pass` | `except` 体**只有一条** `pass` | 46 = **迁移 40**（P-106 冻结，不可改源码）+ **非迁移 6**（`core/file_index.py` 1、`query/adapters/nrsis.py` 2、`scripts/docs_sync_check.py` 1、`scripts/update_status.py` 2） |
| `return` | `except` 体**只有一条** `return <空/None/False/0/空容器>` | 47 |
| `debug` | `except` 体内出现 `logger.debug(...)`（可与其他语句共存） | 69 |

**三个必须写死的口径**：

1. **`pass` 不是"测试通过"，是"`except: pass`"**。所以"修好两条应该进 pass"不成立——修好 = 该处不再命中任何一档，直接从基线**移除**（`return`/`debug` 各 −1）。本轮 162 正是这样来的：`_cleanup.py` 的 debug 2→1，`rules_page.py` 的 return 1→0（加 warning 后 handler 体变两条语句，不再是"单语句 return"）。
2. **基线本身就是 allowlist**（脚本 docstring `:126-128` 明写"无需 `# g050-allow` 逐条标注"）。因此不存在"allowlist 是否计入 162"的问题——**162 全部是被冻结的站点**：40 条迁移冻结 + **122 条已 triage 的 allowlist**（批 1 的 47 + 批 2 的 21 + 批 3 的 28 + 批 4 的 26，含少量批间调整）。若把 allowlist 从总数里剔除，`compare()` 会把它当"新增"直接 FAIL，棘轮就失效了。
3. **"修好"与"登记"的差别只体现在基线位置**：修好 ⇒ 该文件该档计数 −1（基线与现状同时下降）；登记 ⇒ 计数不变、理由写进本文件。**本轮 2 条是"修好"**（基线下降），26 条是"登记"（基线不变）。

**口径自证**：`scripts/silent_errors_baseline.json` 新增 `_meta`（total / tiers / migration_frozen / triaged_allowlist / review_due），并由 `tests/test_check_g_050_silent_errors.py::test_baseline_meta_matches_counts` 钉住——改计数不同步 `_meta` 即红。

**复审节奏**：`_meta.review_due = 2027-02-14`（季度）。到期复核两件事：① 122 条 allowlist 里是否已有"上层结果不再暴露"的情形（该升 warning）；② 迁移冻结 40 条是否随 P-106 到期可动。**到期提醒是机制的**：`check_g_050_silent_errors.py` 在 `review_due < today` 时打印 `[WARN] G-050 基线待复审`（软提醒、退出码仍 0），由 `test_review_due_overdue_only_warns` 锁定。


