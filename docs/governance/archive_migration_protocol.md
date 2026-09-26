# 归档迁移协议

> 定义 `git mv` 归档活跃代码文件的标准流程。目标：**零能力静默丢失**。
> 关联文档：[能力登记簿](capabilities_registry.md) | [拆分经验与拆分前检查项](../guides/refactoring-lessons.md)

---

## 一、强制 5 步标准流程

### 步骤 1：提取（Extract）

**动作**：审查待归档文件，提取所有非功能性能力。

**方法**：
- 运行自动化扫描（待阶段二生成）：
  ```bash
  python scripts/extract_capabilities.py <待归档文件>
  ```
- 若脚本未就绪，手动搜索以下模式：
  - `threading.Thread` / `threading.Timer` / `daemon=True`
  - `threading.Event` / `threading.Lock`
  - `[PROGRESS]` / `[HEARTBEAT]` / `[STATS]` 等结构化日志
  - `atexit.register` / `signal.signal`
  - `CacheRepository` / 缓存容器 / `use_cache`
  - `QTimer` / `QThread`

**产出**：待归档文件的能力清单列表。

### 步骤 2：清单（Inventory）

**动作**：将提取的能力逐条登记到 `capabilities_registry.md`。

**要求**：
- 每条记录包含：模块路径、能力名称、描述、实现位置（文件:行号）、类型、必需性、登记日期。
- 状态标记为 `migrating`（表示该能力有一个活跃的迁移任务）。
- 在备注栏注明目标迁移位置（若已确定）。

**产出**：登记簿中新增的 `migrating` 条目。

### 步骤 3：迁移或放弃（Migrate or Abandon）

**动作**：对清单中每条能力执行迁移或明确放弃。

**迁移路径**：
- 若目标位置已存在等价能力 → 验证等价性 → 放弃旧实现 → 更新登记簿。
- 若目标位置不存在等价能力 → 在新位置实现 → 验证 → 更新登记簿。

**放弃路径**：
- 必须在登记簿中标注 `deprecated` 状态。
- 必须在 commit message 中声明"已放弃能力：X（理由：...）"。
- 理由必须具体（如"架构从子进程改为直接调用，ProgressReporter 的回调模式不再适用"），禁止"不需要了"等模糊表述。

### 步骤 4：更新登记簿（Update Registry）

**动作**：所有能力迁移或放弃完成后，更新 `capabilities_registry.md`。

**要求**：
- 已迁移：状态从 `migrating` → `active`，更新实现位置为新的文件:行号。
- 已放弃：状态从 `migrating` → `deprecated`，备注放弃理由和日期。
- 删除旧位置的登记条目（若旧文件已不存在）。

### 步骤 5：提交（Commit）

**动作**：按规范格式提交。

**强制格式**：
```
refactor(<模块>): <简述>

已迁移能力：<能力A>（<旧文件> → <新文件>），<能力B>（...）
已放弃能力：<能力C>（理由：<具体原因>）
```

**禁止的 commit message 示例**：
- ❌ `refactor: 旧脚本归档`（缺少能力迁移声明）
- ❌ `feat: 压力测试方案v4.1+驱动器+归档`（未提及丢失/放弃的能力）
- ❌ `chore: archive old scripts`（英文 + 无能力声明）

---

## 二、反面案例：`stress_01_pipeline.py` 静默丢失事件

### 时间线

| 日期 | 事件 | 关键 commit |
|------|------|------------|
| 2026-05-31 | `ProgressReporter` 类 + `heartbeat()` 函数实现于 `stress_01_pipeline.py:86-158`。功能：每 30s 或每 50 条输出查询进度（速率/ETA/内存/冷却状态），下载/归档阶段有心跳线程防卡死假象。 | `cdb6705` |
| 2026-06-10 | v4.1 重构：新建 `stress_driver.py`（405 行），`git mv stress_01_pipeline.py stress_01_pipeline_archived.py`。新 driver 采用子进程架构，旧脚本中直接调用 Manager API 的模式被替换。 | `be50271` |
| 2026-06-10 | `ProgressReporter` 和 `heartbeat()` **未迁移**至 `stress_driver.py`。归档 commit message 未提及能力迁移。登记簿不存在（尚未建立）。 | — |
| 2026-06-12 | 代码审查标记"压测最终查询进度不可恢复"为未修复（`code_review_fixes_20260612.md:32`），但审查关注的是崩溃恢复，未发现心跳线程丢失。 | — |
| 2026-06-22 | 用户执行全量压测，发现查询阶段无定时进度输出。追溯 git log 确认 `cdb6705` 实现 → `be50271` 归档丢失。 | 当前会话 |

### 丢失的能力清单

| 能力 | 旧位置 | 功能 | 当前状态 |
|------|--------|------|---------|
| `ProgressReporter` 类 | `stress_01_pipeline_archived.py:86-133` | 每 30s 或每 50 条输出进度：速率、ETA、内存、冷却 | **migrating**（待迁移至 `stress_driver.py`） |
| `heartbeat()` 通用心跳函数 | `stress_01_pipeline_archived.py:139-158` | 返回 `(start, stop)` 闭包，后台线程定时输出心跳日志 | **migrating**（待评估：`stress_driver.py` 的 `_progress_watchdog` 覆盖了卡死检测但缺少主动心跳） |

### 根因分析

```
实现(05-31) ──→ 重构(06-10) ──→ 代码审查未发现(06-12) ──→ 用户发现(06-22)
                    │
                    ├── 未生成旧文件能力清单
                    ├── 未评估新架构需要哪些等价能力
                    ├── commit message 未声明迁移/放弃
                    └── 无登记簿可供对照
```

12 天的静默期根源是**缺少强制流程**。如果归档前执行了能力提取步骤，就不会遗漏。

### 若当时有此协议

1. **步骤 1**：审查 `stress_01_pipeline.py`，提取 `ProgressReporter`（行 86）和 `heartbeat()`（行 139）。
2. **步骤 2**：登记到 `capabilities_registry.md`，状态 `migrating`，目标 `stress_driver.py`。
3. **步骤 3**：评估迁移：
   - `ProgressReporter`：旧实现依赖 `progress_callback` 签名（`current, total`），新 driver 通过解析子进程 stderr 获取进度。需重新设计等价的定时汇总输出。→ 标记为"需适配"。
   - `heartbeat()`：新 driver 已有 `read_stream` 线程，可在其中检测子进程输出活跃度。→ 标记为"已有等价能力（_progress_watchdog）"。
4. **步骤 4**：更新登记簿。
5. **步骤 5**：提交：
   ```
   refactor(tests): 压力测试 v4.1 重构

   已迁移能力：无（子进程架构需重新设计）
   已放弃能力：ProgressReporter（理由：子进程架构下 progress_callback 不可用，待在新 driver 中实现定时汇总）
   已保留能力：heartbeat → _progress_watchdog（等价替代）
   ```

   即使放弃，也**有记录、有理由、可追溯**。

---

## 三、强制项与建议项

### 强制项（不可跳过）

| # | 事项 | 检查点 |
|---|------|--------|
| F1 | 归档前必须生成待归档文件的能力清单 | 步骤 1-2 |
| F2 | 每条能力必须有明确的迁移或放弃决策 | 步骤 3 |
| F3 | 放弃能力必须在 commit message 中声明并附理由 | 步骤 5 |
| F4 | 归档 commit message 必须包含"已迁移能力"或"已放弃能力"段落 | 步骤 5 |
| F5 | 登记簿必须在归档后更新，旧文件条目不得指向不存在的代码 | 步骤 4 |

### 建议项（推荐执行）

| # | 事项 | 说明 |
|---|------|------|
| R1 | 使用 `scripts/extract_capabilities.py` 自动化提取（待阶段二） | 减少人工遗漏 |
| R2 | PR 描述附"能力迁移状态表" | 方便 reviewer 对照检查 |
| R3 | 归档前在旧文件中加 `# ARCHIVED: 能力已迁移至 <新文件>` 注释 | 方便未来考古 |
| R4 | 归档后运行全量压测 | 验证新位置的观测日志正常输出 |

---

## 四、红线（违反即回退）

- ⛔ 未生成能力清单 → 禁止 `git mv` 归档。
- ⛔ commit message 缺少"已迁移能力"/"已放弃能力"声明 → 禁止合并。
- ⛔ 登记簿在归档 commit 后仍指向已删除的旧代码 → 禁止标记任务完成。
