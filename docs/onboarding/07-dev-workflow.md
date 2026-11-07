# 07 · 开发工作流：环境、测试、门禁、提交

> 本文件面向准备改代码的新员工。  
> 先记住：**这个项目的规则不是“建议”，是执行约束**；入口是根目录 `AGENTS.md`。

---

## 一、四个环境（先分清）

| 环境 | 代码 | 后端 | 触发场景 | 行为 |
|---|---|---|---|---|
| **开发** | 本地最新 | 本地/Mock | 写代码/改功能/调样式 | 默认环境，数据不可靠 |
| **验证** | 本地新代码 + Vite | 局域网 Docker 真实 API | 验证/数据不对/字段不显示 | 修复后首选验证 |
| **复现** | Git 旧 commit | 同一 Docker API | 以前正常/突然坏了 | 控制变量排查回归 |
| **生产** | 已发布 | Docker + 真实数据 | 生产/线上 | **红线：禁止直接操作** |

标准路径：

```text
复现（确认边界）→ 验证（定位根因）→ 开发（修复）→ 验证（确认）→ 生产（部署）
```

---

## 二、本地准备

### 1. Python

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dev.txt
```

### 2. 前端

```bash
cd web
pnpm install
```

Windows 如果 `pnpm` 被 PowerShell ExecutionPolicy 拦截，用 `pnpm.cmd`。

### 3. 环境变量

- `.env`：本地/Docker 连接信息；
- Docker 凭证：`config/docker_creds.json`（含 GBK 注释，不要直接 JSON 解析）；
- 不要把真实密码提交到仓库。

---

## 三、测试命令

### 后端

```bash
# 全量（排除 GUI）
python -m pytest tests/ -k "not gui"

# 单文件
python -m pytest tests/unit/manager/organize/test_organizer.py -q

# 集成
python -m pytest tests/integration/test_monitor_archive_e2e.py -q

# 下载适配器
python -m pytest tests/download/adapters/test_openstd_download.py -q
```

### 前端四件套（改 `web/` 必跑）

```bash
cd web
pnpm run type-check
pnpm run lint
pnpm test
pnpm run build
```

Windows：

```bash
pnpm.cmd run type-check
pnpm.cmd run lint
pnpm.cmd test
pnpm.cmd run build
```

### 其他

```bash
python scripts/fix_relative_imports.py
python scripts/check_g_031_docs_sync.py
```

### CI / 发布 / 备份（2026-11-07 核实）

| 项 | 事实 |
|---|---|
| CI 作业 | 14 个：lint-fast、test-backend、test-gui-coverage、e2e-coverage、security-scan、test-frontend、test-e2e、frontend-e2e、test-gui-unit、repo-compliance、version、docker、exe 等 |
| 后端 CI | 先跑 schema/依赖/离线门禁，再跑 3000+ 测试；含覆盖率、治理文档、死代码、G-008/009/010/011/025/028/039/051/052 |
| 前端 CI | type-check → lint → vitest → build；另含 i18n、G-018/027/040/043/044/045/046/047 |
| 本地门禁 | `bash scripts/check_all.sh --fast/--docs/--deep/--guards`；具体门禁见 `docs/governance/gates.md` |
| Docker 镜像 | `docker/Dockerfile` 多阶段构建；非 root `appuser`；`HEALTHCHECK /api/health`；前端 `web/dist` 必须存在 |
| 备份 | `POST /api/backup/create`，admin-only；备份在 `data/backups/`；**没有恢复 API**，恢复是停服务后手工替换 |
| 版本 | 以 `/api/health` 的 `version` 为准；不要看本地 tag |

**注意**：CI 的“后端测试”不是 `tests/` 全量 GUI；GUI 在 xvfb/Windows 作业单独跑。不要用“本地 pytest 全绿”推断 CI 全绿。

---

## 四、测试分层：改哪里，跑哪里

| 改动 | 必跑 |
|---|---|
| 解析器 | `tests/test_scanner.py` + 解析相关 |
| 归档/Word | `tests/unit/manager/organize/test_organizer.py` |
| 监控 | `tests/integration/test_monitor_archive_e2e.py` |
| 查询/路由 | `tests/test_query_*` / `tests/unit/.../query*` |
| 下载适配器 | `tests/download/adapters/*` |
| 通知聚合 | `tests/test_aggregate_buffer.py` + `tests/test_notification_*` |
| Web API | `tests/test_docker_api.py` |
| Web UI | `web/src/**/*.test.ts` + 四件套 |
| DB/迁移 | `tests/test_migrations_full.py`、迁移校验测试 |

**原则**：逻辑/算法/数据处理变更先写失败测试，再写实现；GUI/配置/文档可跳过。

---

## 五、AGENTS 规则摘要（必须遵守）

根目录 `AGENTS.md` 是完整规则。新员工先记住这些：

### 1. 先搜再动（R-001）

- 新增函数/常量/模块前先 `grep`，确认无重复；
- 分配编号（T-xx/G-0xx/vNN/ADR-0xx）前先查占用，不得复用；
- 修复不是债务，不要给已闭环修复套债务编号。

### 2. 精准修改（R-002）

- 只改目标范围；
- 不顺手改格式/注释/相邻代码；
- `git diff` 每行能追溯到用户要求。

### 3. 删除必扫（R-003）

- 删除公共 API 前 grep 全库（含测试/归档）；
- `ruff` / `vulture` / `ts-prune` 零残留。

### 4. 实证优先（R-004）

- “完成/通过”前必须跑过验证命令、看输出；
- 真实数据采样 ≥3 条；
- 禁止凭记忆/推断下结论。

### 5. 先析再答（R-005）

- 收到问题→查代码/文档→附证据→结论。

### 6. 不明即问（R-007）

- 指令有歧义/缺上下文，先列不确定点，不脑补。

### 7. 先批后做（R-012）

- 功能开发前出 1–2 方案，等用户批准；
- 未批准不进实现。

### 8. 提交规范（R-014）

- Conventional Commits；
- 按逻辑分组；
- 未经用户同意不推送；
- 临时文件写在仓库外（R-010）。

### 9. 文档联动（R-006）

- 改数据库/Schema/API/公告/下载链等，按 `AGENTS.md` §8.1/§8.2 同步文档；
- 涉及 `pilotstd/core/`、`docker/api/`、ADR、治理文档时，提交前跑：

```bash
python scripts/generate_capabilities.py
```

并把 `capabilities_registry.md` 纳入同一 commit。

---

## 六、版本号与发布

- 版本号由 CI 自动生成，**不要手工改**；
- `.github/workflows/ci.yml` 的 `version` 作业取最新 tag；
- `scripts/version.py` 按 commit message 定级：
  - `BREAKING CHANGE` → major
  - `feat:` → minor
  - `fix:` → patch
- 写入 `pilotstd/__init__.py` 的 `__version__`；
- 镜像由 bump 之后的提交构建，镜像 sha 与 tag 不一致属设计内行为；
- **部署版本一律以 `/api/health` 返回的 `version` 为准**，本地 tag/`VERSION` 不作证据。

---

## 七、提交前自检

```text
[ ] 只改目标范围
[ ] 没有 TODO/FIXME/stub
[ ] 相关测试跑过
[ ] 前端改动跑了四件套
[ ] 文档需要同步的已同步
[ ] 需要 capabilities 的已生成
[ ] 没有临时文件/密码/密钥进入 git
```

提交信息示例：

```text
fix(monitor): _on_file 补上归档并按真实归档结果计数

- ...
- 验证：...
```

---

## 八、调试工作流

### 1. 先看日志

```text
logs/app.log
```

关键字：

```text
[ERROR] / [WARNING]
解析失败
SQL执行失败
UNIQUE constraint failed
database is locked
PermissionError
Telegram HTTP 429
```

### 2. 再看数据库

- `file_index`：文件有没有入库；
- `standard_validity`：状态/检查时间；
- `notification_log`：通知有没有发/为什么失败；
- `pipeline_runs`：Web 五段式卡在哪。

### 3. 再看 API

- `/api/health`；
- `/api/monitor/status`；
- `/api/stats`；
- `/api/notification/logs`。

### 4. 最后才改代码

- 先复现；
- 再验证；
- 再开发；
- 再验证；
- 再提交。

---

## 九、常见开发坑

| 坑 | 说明 |
|---|---|
| 直接改 `pilotstd/core/` 不看文档 | 可能触发 G-031/G-037 文档同步门禁 |
| 前端只跑 build 不跑 test | 组件测试可能红 |
| 用本地 tag 判断部署版本 | 必须以 `/api/health` 为准 |
| 在仓库根目录建临时文件 | `git add -A` 会误提交；用 `$env:TEMP` |
| 忽略 `AGENTS.md` 的环境红线 | 生产禁止直接改代码/UPDATE/重启测试 |
| 改公共 API 不 grep | 可能破坏其他入口 |

---

## 十、自检

1. 四个环境分别是什么？生产红线是什么？
2. 改 `web/` 要跑哪四条命令？
3. 改归档要跑哪个测试文件？
4. 为什么不能手工改版本号？
5. 哪些改动需要跑 `generate_capabilities.py`？
6. 提交前必须检查什么？

参考答案见 [`10-assessment.md`](10-assessment.md)。
