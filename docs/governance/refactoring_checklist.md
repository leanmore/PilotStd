# 重构检查清单

> 任何涉及文件重命名、模块拆分合并、架构升级的开发任务，必须按本清单逐项执行。
> 本清单与 `capabilities_registry.md` 联动，不可跳过。

---

## 一、重构前

### 1.1 能力提取

- [ ] 读取 `docs/governance/capabilities_registry.md`，检索目标模块的所有已登记能力。
- [ ] 运行能力扫描脚本（待阶段二生成）：
  ```bash
  python scripts/extract_capabilities.py <目标文件或目录>
  ```
  - 若脚本尚未就绪，手动逐行审查目标代码，搜索以下模式：
    - `threading.Thread` / `threading.Timer` / `daemon=True`
    - `threading.Event` / `threading.Lock`
    - `[PROGRESS]` / `[HEARTBEAT]` / `[STATS]` 等结构化日志
    - `atexit.register` / `signal.signal`
    - `CacheRepository` / `@lru_cache` / 缓存容器
    - `QTimer` / `QThread`（GUI 端）
- [ ] 将发现的未登记能力补充到登记簿（标注 `active`，注明发现日期）。

### 1.2 影响评估

- [ ] 列出所有调用方（grep 目标模块的 import / 函数调用）。
- [ ] 确认是否有外部系统依赖这些能力（如 CI 解析日志格式、监控面板读取指标）。
- [ ] 评估每种能力迁移的难度：低（直接复制）/ 中（需适配新接口）/ 高（架构变更）。

### 1.3 归档预检（仅当涉及 `git mv` 归档时）

- [ ] 确认旧文件路径和目标归档路径。
- [ ] 生成归档文件的能力清单（作为 PR 描述附件）。
- [ ] 确认每种能力的迁移目标位置已确定。

---

## 二、重构中

### 2.1 逐项迁移

- [ ] 按 `capabilities_registry.md` 中的清单逐项迁移。每迁移一项，勾选并记录：
  - 迁移前位置（文件:行号）
  - 迁移后位置（文件:行号）
  - 是否需要适配（是/否，若是则简述改动）

### 2.2 放弃决策

- [ ] 若某项能力决定不迁移，必须：
  - 更新 `capabilities_registry.md`，状态改为 `deprecated`
  - 在登记簿备注栏注明放弃理由（如"架构不再需要""已被 X 替代""优先级过低"）
  - 在 PR 描述中列出所有放弃项

### 2.3 格式与契约

- [ ] 结构化日志格式若需变更，必须同步更新 `stress_driver.py` 中的正则解析器。
- [ ] 线程命名保持一致性（如 `scheduler-heartbeat`、`progress-heartbeat`）。
- [ ] 所有新线程必须设置 `daemon=True`（除非需要优雅退出）。

---

## 三、重构后

### 3.1 验证

- [ ] 运行能力验证脚本（待阶段二实现）：
  ```bash
  python tests/test_observability.py --check-all
  ```
- [ ] 若脚本尚未就绪，手动验证：
  - 启动应用，触发相关功能，检查日志中是否包含预期的结构化标记。
  - 运行 `stress_driver.py --source <小数据集> --yes`，确认解析器未报错。
- [ ] 运行现有测试套件，确认零回归：
  ```bash
  pytest tests/ -x --timeout=120
  ```

### 3.2 登记簿更新

- [ ] 将迁移完成的能力状态从 `migrating` 改为 `active`。
- [ ] 更新能力所在位置（文件:行号）以反映新代码。
- [ ] 若旧文件已删除，从登记簿中移除对应的旧位置条目。

### 3.2.1 CI 流水线验证

- [ ] CI 流水线中的观测能力自检已通过（`python tests/test_observability.py --check-all` 零 FAIL）
- [ ] 若登记簿中存在 `migrating` 条目，`scripts/check_no_migrating.sh` 会阻断合并，请确保迁移完成后再合并

### 3.3 PR 描述

- [ ] 附上"能力迁移状态表"：

  | 能力名称 | 迁移前 | 迁移后 | 状态 |
  |---------|--------|--------|------|
  | ProgressReporter | stress_01_pipeline.py:86 | stress_driver.py:N | ✅ 已迁移 |
  | heartbeat() | stress_01_pipeline.py:139 | — | ❌ 已放弃（理由：driver 已有 _progress_watchdog） |

### 3.4 提交规范

- [ ] Commit message 格式：
  ```
  refactor(<模块>): <简述>

  已迁移能力：ProgressReporter, heartbeat
  已放弃能力：<无>
  ```

---

## 四、归档文件处理（特殊章节）

当使用 `git mv` 将活跃文件归档为 `*_archived.py` 时，以下步骤为**强制项**：

### 4.1 归档前

- [ ] 运行 `python scripts/extract_capabilities.py <待归档文件>`（占位，待阶段二）
- [ ] 手动审查待归档文件的每一处后台线程、日志标记、缓存操作
- [ ] 生成"归档能力清单"并添加到 PR 描述

### 4.2 归档中

- [ ] **禁止**在能力迁移完成前执行 `git mv`
- [ ] 先在新位置实现等价能力，验证通过
- [ ] 再执行 `git mv old.py old_archived.py`

### 4.3 归档后

- [ ] 更新 `capabilities_registry.md` 中该文件所有能力的实现位置
- [ ] 运行全量压测验证新位置的能力正常工作
- [ ] Commit message 必须包含：
  ```
  已迁移能力：X, Y（归档文件 → 新文件）
  已放弃能力：A（理由：...）
  ```

### 4.4 强制红线

- ⛔ **禁止**在未生成能力清单的情况下执行 `git mv` 归档。
- ⛔ **禁止**归档 commit 的 message 中缺少"已迁移能力"或"已放弃能力"声明。
- ⛔ **禁止**登记簿在归档后仍指向已不存在的旧代码位置。

---

## 五、反面案例速查

| 事件 | 日期 | 丢失能力 | 根因 |
|------|------|---------|------|
| `stress_01_pipeline.py` → `_archived.py` | 2026-06-10 | `ProgressReporter` + `heartbeat()` | 新建 `stress_driver.py` 时未对照能力清单迁移；归档时未审查旧文件能力 |
| 进度汇报缺失发现 | 2026-06-22 | 同上 | 压测运行中用户发现无定时进度输出，追溯确认 12 天前已丢失 |

**教训**：如果当时有这份检查清单，"重构前"第 1 步就会要求在登记簿中记录旧文件的 `ProgressReporter` 和 `heartbeat()` 能力，"重构中"第 1 步会要求逐项迁移。缺失不会被遗漏 12 天。
