# PilotStd 项目规则

## 0. 核心铁律（优先级顺序）

- **安全性**：敏感数据（密码、Token、密钥）禁止硬编码或打印到日志。
- **功能正确性**：代码必须满足业务需求，边界条件处理完整。
- **类型与规范**：通过 Mypy + Ruff 检查，零错误。

当规则冲突时，按此优先级裁决。

---

## 1. 项目架构背景

- 后端：Python 3.12，FastAPI，核心目录 `pilotstd/`、`docker/`
- 前端：Vue 3.5 + TypeScript 6.0 + Vite 8，核心目录 `web/src/`
- 数据库：SQLite (sqlite3)
- 桌面端：PyQt6，核心目录 `pilotstd/ui/`、`desktop/`（打包配置 + 图标资源）

**技术栈：**

- Python：sqlite3, requests, fastapi, pydantic, pyqt6
- Vue：pinia, vue-router, primevue, vue-i18n, vitest
- CI：GitHub Actions, Docker (ghcr.io), PyInstaller

---

## 2. 代码审查硬规则（AI 必须遵守）

### 2.1 工具类优先（防止重复造轮子）

编写任何新函数前，必须在以下目录检索是否存在同名或同功能函数：

- `pilotstd/core/`（通用工具：db、config、file_utils、file_index）
- `pilotstd/query/search_strategy.py`（查询匹配引擎）
- `pilotstd/query/network.py`（HTTP 请求层）
- `pilotstd/query/models.py`（数据模型）
- `pilotstd/query/adapters/`（外部适配器）

### 2.2 Python 导入规范

- 禁止在业务逻辑中裸 `import datetime` 做复杂格式化，优先使用 `search_strategy.ts_to_date()`。
- 所有 `import` 必须放在文件顶部，按 标准库 → 第三方库 → 本地模块 排序。

### 2.3 前端组件复用

- 大于 20 行的重复 UI 逻辑必须抽取为 `web/src/components/` 下的通用组件。

### 2.4 死代码清理

- 死代码检测：
  - Python: `vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=80`
  - TypeScript: `cd web && npx ts-prune --error`
- pre-commit 和 CI 会自动执行上述检测，提交前必须确保两者均通过。
- 文件名包含 `_archived`、`_deprecated`、`_old` 的 Python 文件，严禁在新代码中引用。

---

## 3. 强制防御规则（基于 2026-06-18 审计报告）

### 3.1 前端 API 类型强制约束

- **触发**：编写或修改 `web/src/api/` 下的任何请求函数时。
- **行为**：必须先在 `web/src/types/api.ts` 中定义请求体和响应体的 TypeScript 接口。
- **禁止**：在 `.vue` 组件中直接使用 `axios.get` 或定义局部 `any` 类型变量。必须调用 `api/` 下封装好的函数。
- **提交前**：任何前端代码变更必须通过 `npm run type-check`（即 `vue-tsc --noEmit`）。

### 3.2 数据模型单一真相源（Pydantic v2）

- **核心原则**：`pilotstd/query/models.py` 是标准号查询相关数据的唯一权威定义。
- **绝对禁止**：在 `docker/api/models.py` 中新建与 `QueryResult` 同名的数据类（已删除 QueryResultItem）。
- **强制行为**：API 层必须直接从 Core 层导入数据类，利用 `model_validate(from_attributes=True)` 或直接在路由中返回 Core 对象。
- **例外**：仅当 API 返回聚合统计（如 `{"code": 200, "count": 10}`）且不涉及 Core 实体时，才允许独立定义新模型。

### 3.3 API 文件容量红线

- 任何单个 `web/src/api/*.ts` 文件内的函数数量 **不得超过 8 个**。
- 当新增第 9 个函数时，必须按业务域（auth/query/files/announce/settings/download）拆分。

### 3.4 UI 组件国际化门禁

- **背景**：PrimeVue 4.x Calendar 已废弃，迁移到 DatePicker。必须显式传入 `:locale` 才能汉化。
- **触发**：在任何 `.vue` 或 `.ts` 文件中需要使用日期选择器时。
- **强制行为**：
  - 必须导入并使用项目封装的 `@/components/AppCalendar.vue`，禁止直接从 `primevue/datepicker` 导入。
  - `AppCalendar` 内部已自动注入与界面语言联动的 locale，业务代码无需手动传参。
- **门禁机制**：`.husky/pre-commit` 中已配置 grep 拦截，检测到 `from 'primevue/datepicker'` 直接阻断提交。

### 3.5 文档联动义务（引用）

改代码后必须检查关联文档是否过时，具体规则见 memory 中的 `feedback_linked_cleanup.md` 和 `feedback_document_management_rules.md`。重点：
- `docs/adr/` — 涉及架构决策的任务完成后追加 ADR
- `docs/architecture.md` — 架构策略变更
- `docs/technical-debt.md` / `docs/architecture/technical-debt-registry.md` — 技术债状态变更

### 3.6 支撑层文档防腐烂规则

修改 `docs/guides/`（用户/运维指南）或 `docs/reference/`（规范/参考）下的文档时，**必须**同步更新文件顶部的防腐蚀元数据中的 `Last-Reviewed` 日期为当天：

```
<!-- Meta: Last-Reviewed=YYYY-MM-DD | Review-Cycle=90d | Status=Active -->
```

范式文档（`*-pattern.md` + `cleanup-io-isolation-2.0.md`）属于核心治理层，不受此机制约束。

### 3.7 计划文档生命周期规则

新增的计划与方案文档**必须**存放在 `docs/plans/` 目录下。当计划实施完毕并合入 main 后：
1. 提炼核心决策形成 ADR（存入 `docs/adr/`）
2. 将原计划文件移入 `docs/archive/` 归档
3. **严禁**在 `docs/` 根目录或其他非归档目录下遗留已完成的计划文件

---

## 4. AI 编码流程（强制）

### 4.1 编码前自检（每次 Edit/Write 前必须回答）

- 搜过已有实现吗？ → 在工具类目录中 grep，有则复用，禁止重写。
- 确定改哪层了吗？ → 三端（CLI/WinUI/Docker）通用逻辑必须在 facade/core，不得在各端各自实现。
- 计划批准了吗？ → 如果改动涉及多个文件或跨层，必须先列出修改计划（文件清单 + 函数变更），等待用户确认后再动代码。
- 边界条件考虑了吗？ → 空值、None、0、空列表是否已处理？

答不出 → 不准改，回到步骤 1。

### 4.2 编码后自动自检（AI 每次完成代码编写后必须执行）

- 自动触发 `/self_review`（或手动执行检查命令，见下文）。
- 如果有错误，立即修复并重新检查，直到零错误。
- 仅当所有检查通过后，才向用户输出 "✅ 自检通过，代码已就绪"。
- （推荐）如果修改了核心逻辑或数据模型，运行 `pytest` 确保无回归。
- 检查是否存在以下问题：裸 except、循环内 I/O、关键路径无日志、硬编码常量。如有，立即修复。

**检查命令路径说明：**

- 后端检查（在项目根目录执行）：

```
ruff check pilotstd docker --fix
ruff format pilotstd docker
mypy pilotstd docker --follow-imports=skip
```

- 前端检查（在 `web/` 目录执行）：

```
npm run type-check
```

- Python 死代码检测（在项目根目录执行）：

```
vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=80
```

- TypeScript 死代码检测（在 `web/` 目录执行）：

```
cd web && npx ts-prune --error
```

### 4.3 提交前检查清单

- [ ] 已运行 `/self_review` 并通过。
- [ ] 无 Ruff 错误。
- [ ] 无 Mypy 错误。
- [ ] 前端代码（Vue/TS）已通过 `npm run type-check`。
- [ ] 代码格式正确。
- [ ] 无 `print(stderr)`、`_log()` 等禁止写法。
- [ ] 核心逻辑修改后已运行 `pytest`（推荐）。
- [ ] 无裸 except 或 except Exception 吞异常。
- [ ] 无循环内 I/O 操作。
- [ ] 关键路径有日志记录。
- [ ] 无硬编码常量（魔法数字/字符串）。
- [ ] Python 死代码检测通过（vulture）。
- [ ] TypeScript 死代码检测通过（ts-prune）。

---

## 5. 技术铁律

### 5.1 日志

- 唯一入口：`LoggerManager`。禁止 `_log()`、`print(stderr)`、`print()` 替代 `logger.info()`。
- 格式：`MM-DD HH:MM:SS [级别] TAG 消息`。
- 全量输出：运行时所有字段、状态、上下文全部 INFO 级别输出，禁止选择性丢弃。
- 状态变更必记：配额增减、冷却进入/退出、查询结果等必须 INFO 级别可见。
- 压测：stderr 全量落 `RESULT_DIR/<step>_stderr.log`，WinUI 测试必须 init LoggerManager。

### 5.2 解析器

- 标准号解析唯一入口：`StandardParser.parse()`。禁止任何地方手写正则。

### 5.3 设置键名

- `appearance.*` 统一前缀。WinUI/Web 共用项键名一致，单端特有不动。

### 5.4 代码重复

- 禁止同一功能多份实现。发现已有→立即消除。
- 三端通用逻辑必须在 facade/core，不得在 CLI/WinUI/Docker 各有实现。

### 5.5 数据库

- 查询字段加索引，联合查询加联合索引。

### 5.6 下载

- 先查采标再入队，采标跳过；本地已有版本跳过下载。

### 5.7 版本号

- 唯一来源：`__init__.py`，git tag 同步自动维护。
- 提交前缀：`feat:`→Minor（新功能/重构），`fix:`→Patch（修复）。`chore:`/`refactor:`/`perf:`/`test:` 不升版本。
- 自动化：推送 main 时 release workflow 自动 bump 版本号 → 回写 `__init__.py` → 打 tag → 发 Release。禁止手动打 tag。
- 提交信息单行。

### 5.8 边界条件处理

- 新增函数时，必须显式处理以下情况：空输入、None 输入、空字符串、数值 0、空列表、空字典。
- 如果确实不需要处理某种边界情况，则必须在函数文档字符串中说明理由。
- 禁止假设输入总是有效，必须对关键输入进行防御性检查。

### 5.9 异常处理规范

- 禁止使用裸 `except:` 或 `except Exception` 而不重新抛出或记录日志。
- 必须捕获具体的异常类型（如 `ValueError`、`KeyError`、`requests.Timeout`、`json.JSONDecodeError`）。
- 在 except 块中必须使用 `logger.error()` 记录完整的上下文信息（包括异常类型、发生位置、相关变量值）。
- 只有在确实不需要任何处理的极端情况下，才允许捕获异常并 `pass`，但必须在注释中说明原因。

### 5.10 副作用管理

- 如果函数会修改传入的可变对象（列表、字典）或全局状态，必须在函数文档字符串中显式说明"会修改输入对象"。
- 优先考虑返回新对象而非修改输入对象（不可变风格）。
- 禁止在函数内部意外修改外部变量，所有对外部状态的修改必须是明确的、有意的。

### 5.11 配置与环境变量检查

- 所有从环境变量（`os.getenv`）或配置文件读取的值，必须在初始化时进行有效性检查。
- 示例：`API_URL = os.getenv("API_URL")` 必须跟 `if not API_URL: raise ValueError("API_URL 未设置")`。
- 禁止直接使用未检查的配置值，必须在启动阶段完成所有配置验证。

### 5.12 性能规则

- 在循环体内，禁止执行数据库查询、HTTP 请求、文件读写等 I/O 操作。
- 必须改用批量操作（如 SQL IN 查询、批量 get、批量写入）。
- 如需在循环内执行 I/O，必须在代码审查时说明理由并获得批准。
- 对于可能处理大量数据的函数，应考虑使用生成器或分页。

### 5.13 日志强制要求

- 所有对外提供的公共方法（特别是 API 端点、核心业务逻辑、外部服务调用）必须在入口和出口处记录 INFO 级别日志。
- 日志必须包含入参关键字段和返回值摘要，便于追踪链路。
- 禁止在关键路径上只有 `print()` 或完全无日志。
- 错误日志必须包含完整的堆栈和上下文信息。

### 5.14 禁止硬编码常量

- 所有具有业务含义的数字、字符串、路径等，必须定义为模块级常量或放入配置文件中。
- 常量命名使用大写加下划线（如 `DEFAULT_TIMEOUT = 30`、`MAX_RETRY_COUNT = 3`、`MAX_FILE_SIZE_MB = 10`）。
- 禁止在代码逻辑中直接使用字面量数字或字符串（魔法数字/魔法字符串）。
- 只有 0、1、-1、空字符串、True/False 等明显无歧义的值可以作为例外。

---

## 6. 提交前自检（每次 git commit 前执行）

```
git status                    # 确认变更清单与意图一致
git diff --stat               # 确认变更范围与意图一致
git log --oneline -5          # 确认提交顺序反映实际改动顺序
grep -rn "def _log\b" tests/         # 禁止自造 _log()
grep -rn "print.*stderr" pilotstd/   # 禁止 print(stderr)
grep -rn '"ui\.' pilotstd/ docker/   # 禁止旧键名
```

如果上述 grep 命令命中任何结果，必须替换为 `logger.info()` 或 `logger.error()`，否则禁止提交。

---

## 7. CI/CD 检查说明

- GitHub Actions 会在推送和 PR 时自动运行：
  - Ruff 检查 + 格式化
  - Mypy 类型检查
  - Pytest 单元测试
  - 前端 `vue-tsc` 类型检查
- 本地通过不代表 CI 通过。如果 CI 报错，优先本地复现并修复。
- **Shell 规范**：
  - `ubuntu-latest` runner 默认 shell 为 bash，无需额外设置。
  - `windows-latest` runner 默认 shell 为 PowerShell，**不要用 `defaults.run.shell` 一刀切**。
  - 当 job 中存在混合语法步骤时，每个步骤按其语法显式指定 `shell: pwsh` 或 `shell: bash`。
  - 示例：
    ```yaml
    # PowerShell 语法（Windows runner）
    - name: Build with PyInstaller
      shell: pwsh
      run: |
        $ErrorActionPreference = "Stop"
        Write-Host "Installing..."
    # Bash 语法（Windows runner 上也支持）
    - name: Upload to release
      shell: bash
      run: |
        if [ -f dist.zip ]; then
          gh release upload v1.0 dist.zip
        fi
    ```
  - 新增 workflow/job 时，先确认 `runs-on` 类型和各步骤语法，逐步骤指定正确 shell。
