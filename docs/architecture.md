# 架构决策记录

## Handler 组合模式（2026-07-11）

### 背景

项目早期大量使用 Mixin 混入类来实现代码复用，导致：
- **多重继承链复杂**：`MainWindow` 继承 28 个 Mixin，MRO 难以追踪
- **隐式依赖**：Mixin 之间通过 `self` 隐式调用对方方法，耦合度高
- **测试困难**：混入类无法独立测试，必须创建完整继承链实例
- **命名冲突**：多个 Mixin 定义同名方法，MRO 决定谁生效，行为不透明

### 决策

全面消除 Mixin 多重继承，改用 **Handler 组合模式**：

```
旧：class MainWindow(MixinA, MixinB, MixinC, QMainWindow):
         def setup(self):
             self.do_stuff()  # 来自哪个 Mixin？

新：class MainWindow(QMainWindow):
        def __init__(self):
            self._handler_a = HandlerA(...)
            self._handler_b = HandlerB(...)

        def setup(self):
            self._handler_a.do_stuff()
            self._handler_b.do_stuff()
```

Handler 通过构造函数显式注入依赖，所有方法通过 `self._handler` 调用，不存在 MRO 歧义。

### 范围

| 模块 | 原 Mixin 数 | 新 Handler 数 | 文件 |
|------|------------|--------------|------|
| `manager/facade/` | 7 | 7 | `manager/facade/_*.py` |
| `query/engine/` | 6 | 6 | `query/engine/_*.py` |
| `scan/parser/` | 1 | 5 | `scan/parser/_*_handler.py` |
| `ui/` | 28 | 14 | `ui/core/handlers/_*.py` |
| **合计** | **42** | **32** | — |

### 无 Mixin 例外

保留一处 MRO 用法（不涉及多重继承），视为无 Mixin：

- `StandardParser` — 匹配通道委托给 `ExactMatcher`（组合注入），辅助方法为 staticmethod 绑定
- `ParserCore` — 5 个 Handler 的组合容器，纯委托代理

### 验收标准

- Mypy 零错误
- Ruff 零错误
- 后端测试 763 passed，0 failed
- 相对导入 619 有效，0 失效

### 参考

- [Composition over inheritance](https://en.wikipedia.org/wiki/Composition_over_inheritance)
- [Mixin 的反模式讨论](https://www.artima.com/articles/mixins-and-traits)

---

## Handler 层治理策略（2026-07-16）

> **完整决策记录**：[ADR-002](adr/ADR-002-handler-governance.md) — Handler 层混合策略治理

混合策略 D：Top 3 高流量 Handler 全量重构 + P5 高密度 Handler 纯逻辑提取 + 剩余 12 个 Handler E2E 兜底。

核心原则：Engine 零 Qt 依赖、默认值集中管理、I/O 隔离、Handler 薄包装层。

### 重构模式

五个范式文档覆盖所有提取场景：

| 范式 | 文档 | 代表 Engine | 核心约束 |
|------|------|------------|---------|
| 序列化/反序列化 | [persistence-engine-pattern.md](guides/persistence-engine-pattern.md) | PersistenceFlowEngine | 零 Qt，成对 serialize/deserialize |
| 配置管理 | [settings-io-engine-pattern.md](guides/settings-io-engine-pattern.md) | SettingsConfigIOEngine | 默认值集中管理，严格类型检查 |
| I/O 隔离 1.0 | [download-flow-engine-pattern.md](guides/download-flow-engine-pattern.md) | DownloadFlowEngine | 零 I/O，显式时间注入 |
| I/O 隔离 2.0 | [cleanup-io-isolation-2.0.md](guides/cleanup-io-isolation-2.0.md) | CleanupFlowEngine | 目录树 dict 化，遍历与分析分离 |
| 数据分组 | [query-summary-engine-pattern.md](guides/query-summary-engine-pattern.md) | QuerySummaryFlowEngine | 状态映射常量，安全字符串转换 |

**核心原则（所有 Engine 通用）**：
- Engine 零 Qt 依赖：禁止 `from PyQt6` / `import PyQt6`
- 默认值集中管理：类常量 `DEFAULT_*`，Handler 禁止硬编码
- I/O 隔离：文件读取/目录扫描由 Handler 完成，Engine 只接收内存数据
- Handler 薄包装层：每个方法不超过 5 行逻辑（读控件 → 调 Engine → 写存储）

### 测试分层与门禁

> **详细规范**：[ADR-002](adr/ADR-002-handler-governance.md) 测试分层与门禁规则章节

- E2E 测试（qtbot，真实 QApplication）验证 Handler 薄包装层行为不变
- Engine 单元测试（纯 pytest，零 Qt）覆盖率 100%，验证纯逻辑正确性
- 门禁：E2E 全绿 + 单元全绿 + Engine 覆盖率 ≥ 85% + Ruff/Mypy 零错误

### 遗留工作

| 优先级 | 工作项 | 预估 | 说明 | 状态 |
|--------|-------|------|------|:--:|
| ~~P1~~ | ~~剩余 Handler 纯逻辑提取~~ | 1.5 人日 | AutoFlowEngine + ScanFlowEngine + AnnounceFlowEngine 已提取（3 Engine / 65 测试） | ✅ 已完成（2026-07-16） |
| ~~P1~~ | ~~`_auto.py` 全链路集成测试~~ | 0.5 人日 | test_auto_pipeline.py 已补充 query/download/archive 阶段字段存在性检查 | ✅ 已完成（2026-07-16） |
| ~~P2~~ | ~~技术债务清理~~ | 1 人日 | DriveEnumerator 线程安全、LogHandler atexit 冲突 | ✅ 已清理（2026-07-16） |
| ~~P3~~ | ~~跨 Handler 回调升级事件总线~~ | 2 人日 | 信号/槽 → 统一事件中心 | ✅ 已完成（P9 EventBus） |
| ~~P2~~ | ~~9f9bd828 双轨残留清理~~ | 1.25 人日 | Phase 1+2：15 死文件 / 20 幽灵测试 / -3323 行 / handlers/ -67% | ✅ 已完成（2026-08-02） |

### 死代码清理记录（2026-08-02）

**Phase 1**（cfb166f）：A+B+D 组 — 实例化但零调用 / 从未实例化 / 传递性孤立
- 删除 8 Handler：FileDialog / Export / Theme / UISetup / Dialog / Table / FileTree / _UISetupLayoutMixin
- 删除 6 E2E skip 测试
- 同步清理 _core.py 4 个死 init 方法 + test_ui_core.py 5 个死测试

**Phase 2**（978a5d9）：C 组 FlowEngine + _table_helper
- 删除 5 FlowEngine：toolbar / file_tree / dialog / table / table_helper
- 删除 _table_helper.py（296 行，从未生产实例化）
- 删除 9 幽灵测试：5 个 FlowEngine 测试 + 3 个 table_helper 测试 + 1 个 E2E skip

**现状**：handlers/ 21→7 实际使用类（+14 FlowEngine），总文件 48→28。

### 决策记录

| 编号 | 日期 | 决策 | ADR | 变更范围 |
|------|------|------|-----|---------|
| P5-1 | 2026-07-16 | 序列化/反序列化薄层模式 | [ADR-003](adr/ADR-003-persistence-pattern.md) | `_persistence.py` → `persistence_flow_engine.py` |
| P5-2 | 2026-07-16 | 默认值集中管理 + 4 组对称 load/save | — | `_settings_io.py` → `settings_io_flow_engine.py` |
| P5-3 | 2026-07-16 | I/O 隔离 1.0 + 显式时间注入 | [ADR-004](adr/ADR-004-io-isolation.md) | `_download.py` → `download_flow_engine.py` |
| P5-4 | 2026-07-16 | I/O 隔离 2.0 + 目录树 dict 化 | [ADR-004](adr/ADR-004-io-isolation.md) | `_cleanup.py` → `cleanup_flow_engine.py` |
| P5-5 | 2026-07-16 | 数据分组 + 状态映射常量 | — | `_query_summary.py` → `query_summary_flow_engine.py` |
| P5-B1 | 2026-07-16 | 对话框任务注册纯逻辑提取 | — | `_dialog.py` → `dialog_flow_engine.py` |
| P5-B2 | 2026-07-16 | 批量提取 _table_helper/_table/_project | — | 3 个 Handler → 3 个 FlowEngine |
| P6 | 2026-07-16 | _auto.py 全链路集成测试 | — | 2 个 E2E 测试，旧 skip 占位移除 |
| P9 | 2026-07-16 | EventBus 事件总线重构 | [ADR-005](adr/ADR-005-event-bus.md) | 5 Handler 迁移 + _core.py 构造函数注入模式 |
| — | 2026-08-04 | Mixin 重构 16→1（Handler 组合运动收尾） | [ADR-010](adr/ADR-010-mixin-refactor.md)（🗄 Deprecated） | 15 个 Mixin 消除，仅保留 _WindowLifecycleMixin |

### 纯 UI 编排文件策略（2026-07-16 确认）

> **完整决策记录**：[ADR-006](adr/ADR-006-ui-hold-strategy.md) — 纯 UI 编排文件维持策略

`_settings`、`_theme`、`_file_tree`、`_export`、`_file_dialog` 五个 Handler 经审查确认为纯 Qt 控件构建 + UI 编排，不含可提取的业务逻辑。**停止底层拆解**，不再创建 Engine，仅通过 E2E 测试兜底行为底线。

### 事件总线重构（2026-07-16）

> **完整决策记录**：[ADR-005](adr/ADR-005-event-bus.md) — EventBus 事件总线重构

引入单例 `EventBus`（`pilotstd/ui/core/event_bus.py`），提供 `subscribe`/`unsubscribe`/`publish` API。5 个 Handler（scan/query/download/archive/auto）已完成迁移，13 个集成测试覆盖。向后兼容：原有回调/信号连接完整保留，事件发布为追加行为。

### 模块结构详解

各核心模块的架构分析文档（Mixin→Handler 重构后的包结构）：

- [Manager 模块](modules/manager.md) — 业务门面层结构
- [Parser 模块](modules/parser.md) — 标准号解析器架构
- [Query 模块](modules/query.md) — 查询引擎架构
- [Scan 模块](modules/scan.md) — 文件扫描架构
- [UI 模块](modules/ui.md) — PyQt6 桌面端组件结构

### 治理体系总览

完整的三位一体治理体系（测试 + 门禁 + 文档）状态，参见 [治理体系技术规范](../governance/trinity-technical-spec-v2.md)（历史快照：[治理体系总览（ARCHIVED）](../governance-overview.md)）。

---

## 公告数据模型（2026-07-16）

### 双表现状

公告模块存在两个表，生命周期不同：

| 表名 | 创建版本 | 写入时机 | 当前状态 |
|------|---------|---------|---------|
| `announcement_record` | v15 | **运行时持续写入**（matcher.py 每次提取公告时 INSERT） | 活跃，包含全部公告数据 |
| `announcements` | v36 | **仅 v36 迁移时写入一次** | 停滞，v36 之后的新公告不在此表 |

### 查询路由

| API 端点 | 查询表 | 说明 |
|----------|--------|------|
| `GET /api/announce/results` | `announcement_record` | 公告列表（列表页） |
| `GET /api/announcements/{announce_no}` | `announcement_record` | 公告详情（2026-07-16 修复，原查 `announcements` 导致新公告 404） |
| `POST /api/announcements/{announce_no}/parse` | `announcement_record` | 附件解析触发 |
| `GET /api/announcements/{announce_no}/parse-status` | `announcement_record` | 解析状态查询 |

### 已知限制

- `announcement_record` 不含 `source_url` 和 `attachment_url` 列，详情页暂无法显示原文链接和附件下载
- `announcements` 表保留但不再写入，可作为历史数据快照参考
- 未来如需支持附件功能，建议在 `announcement_record` 中添加 `source_url` 和 `attachment_url` 列，并在 matcher.py 写入时同步填充

### 收藏与归档（Phase 4a）

收藏功能于 v36 引入，2026-07-20 重构为收藏与下载解耦架构（[[ADR-007]]）。

**`user_favorites` 表结构**（v36 创建，v36+ 扩展）：

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 主键 |
| `user_id` | INTEGER FK | 用户外键 |
| `record_id` | INTEGER FK | 标准记录外键 |
| `status` | TEXT | pending/downloading/archiving/done/failed/abandoned |
| `local_path` | TEXT | 归档文件路径 |
| `error_message` | TEXT | 失败原因 |
| `publish_date` | TEXT | 标准发布日期（用于冷却期计算） |
| `last_archive_attempt` | TEXT | 最近一次归档尝试时间 |
| `archive_retry_count` | INTEGER | 重试计数（默认 0） |

> **v52 兜底迁移**（2026-08-21）：部分生产库在 v36 的列补全逻辑（`publish_date` 等）落地前已记录 v36 迁移，导致 `publish_date` 列从未创建，`POST /api/favorites` 收藏时 INSERT 报 `table user_favorites has no column named publish_date` → 接口 500。v52 迁移（`pilotstd/core/db/_migrate_v52.py`）幂等补列：列缺失时 `ALTER TABLE ... ADD COLUMN publish_date TEXT`，不设默认值（`publish_date` 语义为标准的发布日期，允许 NULL 表示无冷却期限制）。

**API 端点**：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/favorites` | POST | 创建收藏（仅记录关系，不触发下载） |
| `/api/favorites` | GET | 收藏列表 |
| `/api/favorites/{record_id}/status` | GET | 状态查询（含 in_cooldown/abandoned） |
| `/api/favorites/{record_id}` | DELETE | 取消收藏 |

**归档流程**：定时任务 `auto_archive_retry`（每天 04:00）扫描 pending/failed 记录，冷却期满后逐条调用 `download_to_inbox`，最多重试 7 次，超过则标记 abandoned 并通知用户。

### 参考

- 修复提交：`bb270717` — 公告详情页查 announcement_record
- 迁移脚本：`pilotstd/core/db/_migrate_v31_plus.py` v36 announcements 表创建

#### 迁移校验机制

- **设计目标**：防止迁移脚本被意外修改，同时避免注释/空行变更造成误报
- **实现方案**：`_norm_source()` 剥离 `#` 注释和空行后计算 SHA-256（`_norm_checksum()`），仅保留代码逻辑行参与校验
- **自愈能力**：当仅注释/空行变化时，自动更新数据库中的 checksum 记录（三级比较：标准化匹配 → 原始匹配自动更新 → 真实变更阻断）
- **阻断条件**：真实 DDL 变更（新增表/字段/索引等）触发 `DatabaseError`
- **🚫 铁律（Immutable Migrations）**：迁移版本一经发布/执行即不可变——任何 Schema 变更必须新增版本号，**严禁修改已执行的旧迁移脚本**（修改会被自愈路径跳过重放，形成"checksum 匹配但实际缺列"的幽灵问题）。详见 [迁移文档 — 迁移不可变铁律](migrations/README.md)

---

## 相关文档

- [ADR 目录](adr/README.md) — 10 个架构决策记录（2026-08-19 更新：ADR-001~010）
- [技术债登记](../technical-debt.md) — 已清理 / 待处理 / 维持现状
- [技术债登记簿](technical-debt-registry.md) — 已跳过测试 + 已接受设计决策
- [范式文档](../guides/) — 5 个 Engine 重构范式
