# PilotStd 门禁索引

> 版本：v1.0
> 生效日期：2026-06-29
> 维护人：项目治理顾问（参谋）

---

## 一、门禁总览

共 **14 道门禁**，分为三类：

| 类别 | 数量 | 门禁编号 |
|------|------|---------|
| 已存在（本次未修改） | 8 | GATE-01 ~ GATE-08 |
| 已修复 | 2 | GATE-04, GATE-09 |
| 本次新增 | 4 | GATE-11, GATE-12, GATE-13, GATE-14 |

---

## 二、门禁清单

### GATE-01：白名单路径检查

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_01_allowed_paths.py` |
| 守护能力 | 路径白名单（`path_guard.py`） |
| 所在分层 | Core 层 |
| 检查内容 | 修改 `path_guard.py` 时，确认 `/inbox` 和 `/standards` 在白名单中 |
| 触发方式 | pre-commit（修改 path_guard.py 时） |
| 状态 | 存在 |

### GATE-02：日志标签完整性

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_02_log_tags.py` |
| 守护能力 | 日志标签（`logger.py` 的 `_TAG_MAP`） |
| 所在分层 | Core 层 |
| 检查内容 | 修改 `logger.py` 的 `_TAG_MAP` 时，确认 `[PROGRESS]` 等标签不受影响 |
| 触发方式 | pre-commit（修改 logger.py 时） |
| 状态 | 存在 |

### GATE-03：敏感字段掩码

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_03_sensitive_fields.py` |
| 守护能力 | 敏感字段掩码（`settings.py`） |
| 所在分层 | Core 层 |
| 检查内容 | 新增 OCR 敏感字段时，同步添加到 `settings.py` 掩码列表 |
| 触发方式 | pre-commit（修改 settings.py 时） |
| 状态 | 存在 |

### GATE-04：API 路由文档完整性

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_04_api_docs.py` |
| 守护能力 | API 路由文档（所有 API 端点） |
| 所在分层 | API 层 |
| 检查内容 | 新增或修改 API 端点时，同步更新能力登记簿 |
| 触发方式 | pre-commit（修改 `docker/api/` 时） |
| 状态 | 已修复 |

### GATE-05：适配器列表一致性

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_05_adapters.py` |
| 守护能力 | 适配器列表（`_ALL_ADAPTER_NAMES`） |
| 所在分层 | Manager 层 / 业务层 |
| 检查内容 | 修改 `_ALL_ADAPTER_NAMES` 时，同步更新 `capabilities_registry.md` |
| 触发方式 | pre-commit（修改适配器相关文件时） |
| 状态 | 存在 |

### GATE-06：Docker 挂载黑名单

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_06_docker_mounts.py` |
| 守护能力 | Docker 挂载配置（`docker-compose.yml`） |
| 所在分层 | 基础设施层（部署配置） |
| 检查内容 | 修改 `docker-compose.yml` 时，确认未挂载 `/app` 目录 |
| 触发方式 | pre-commit（修改 docker-compose.yml 时） |
| 状态 | 存在 |

### GATE-07a：Python 死代码检测

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_07a_vulture.py` |
| 守护能力 | 全局 Python 代码质量（防止死代码残留） |
| 所在分层 | 全部 Python 层 |
| 检查内容 | 检测未使用的函数、类、变量 |
| 触发方式 | pre-commit + CI（修改 Python 文件时） |
| 状态 | 存在 |

### GATE-07b：TypeScript 死代码检测

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_07b_ts_prune.py` |
| 守护能力 | 全局前端代码质量（防止死代码残留） |
| 所在分层 | Web 端特有层 |
| 检查内容 | 检测未使用的 TypeScript 导出 |
| 触发方式 | pre-commit + CI（修改前端文件时） |
| 状态 | 存在 |

### GATE-08：依赖完整性检查

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_08_dependencies.py` |
| 守护能力 | 依赖管理（`requirements.txt` / `package.json`） |
| 所在分层 | 基础设施层 |
| 检查内容 | 确认依赖变更时无冲突或遗漏 |
| 触发方式 | CI（test-backend job） |
| 状态 | 存在 |

### GATE-09：CHANGELOG 版本一致性

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_09_changelog_version.py` |
| 守护能力 | 版本号同步（`__init__.py` / `CHANGELOG.md`） |
| 所在分层 | 基础设施层 |
| 检查内容 | 确认 `__init__.py` 和 `CHANGELOG.md` 版本号一致 |
| 触发方式 | CI（test-backend job） |
| 状态 | 已修复（`bump_version.py` 增加自动同步） |

### GATE-10：UI 敏感字段保护

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_10_ui_sensitive_fields.py` |
| 守护能力 | UI 敏感字段（前端表单） |
| 所在分层 | Web 端特有层 |
| 检查内容 | 确认敏感字段在前端使用掩码控件 |
| 触发方式 | CI（test-frontend job） |
| 状态 | 存在 |

### GATE-11：禁止硬编码 admin

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_11_no_hardcoded_admin.py` |
| 守护能力 | 代码规范（禁止硬编码 `admin` 字符串） |
| 所在分层 | Web 端特有层 + 共享层 |
| 检查内容 | 检测 `admin`、`管理员`、`administrator` 等硬编码，排除注释和文档 |
| 触发方式 | pre-commit（修改 `.vue`/`.ts`/`.js` 时） |
| 状态 | 新增 |

### GATE-12：Vue defineOptions 检查

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_12_define_options.py` |
| 守护能力 | Vue 组件规范（`defineOptions` 声明） |
| 所在分层 | Web 端特有层 |
| 检查内容 | 检测所有 `<script setup>` 组件是否声明 `defineOptions({ name: 'FileName' })` |
| 触发方式 | pre-commit（修改 `.vue` 时） |
| 状态 | 新增 |

### GATE-13：禁止硬编码超级用户

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_13_no_hardcoded_superuser.py` |
| 守护能力 | 安全规范（禁止硬编码超级用户标识） |
| 所在分层 | 所有层 |
| 检查内容 | 检测 `SUPERUSER_USERNAME = 'admin'`、`username === 'admin'` 等硬编码 |
| 触发方式 | pre-commit（修改代码时） |
| 状态 | 新增 |

### GATE-14：OCR 敏感字段掩码一致性

| 属性 | 内容 |
|------|------|
| 脚本路径 | `scripts/check_gate_14_ocr_mask_consistency.py` |
| 守护能力 | OCR 敏感字段（设置页掩码） |
| 所在分层 | Web 端特有层 |
| 检查内容 | 检查 OCR Tab 中 6 个敏感字段是否一致使用原生 `<input type="password">` |
| 触发方式 | pre-commit（修改 `SettingsView.vue` 时） |
| 状态 | 新增 |

---

## 三、能力与门禁映射表

| 能力 | 守护门禁 |
|------|---------|
| 路径白名单（path_guard.py） | GATE-01 |
| 日志标签（logger.py） | GATE-02 |
| 敏感字段掩码（settings.py） | GATE-03, GATE-14 |
| API 路由文档 | GATE-04 |
| 适配器列表（_ALL_ADAPTER_NAMES） | GATE-05 |
| Docker 挂载配置 | GATE-06 |
| Python 代码质量 | GATE-07a |
| TypeScript 代码质量 | GATE-07b |
| 依赖管理 | GATE-08 |
| 版本号同步 | GATE-09 |
| UI 敏感字段 | GATE-10 |
| 硬编码规范 | GATE-11, GATE-13 |
| Vue 组件规范 | GATE-12 |
| OCR 掩码一致性 | GATE-14 |

---

## 四、门禁执行方式

| 执行方式 | 门禁 |
|---------|------|
| Pre-commit hooks（本地） | GATE-01, GATE-02, GATE-03, GATE-04, GATE-05, GATE-06, GATE-07a, GATE-07b, GATE-11, GATE-12, GATE-13, GATE-14 |
| CI（test-backend job） | GATE-08, GATE-09 |
| CI（test-frontend job） | GATE-10 |
| 手动运行 | 全部门禁 |

---

## 五、新增门禁流程

1. 创建 `scripts/check_gate_XX.py`
2. 在 `.pre-commit-config.yaml` 中添加 hook 配置
3. 更新本索引文档
4. 在 CI 配置中添加执行（如需要）
5. 更新能力登记簿，关联新门禁
