# ADR-012: 多用户基础架构改造（A3 迁移）

> 日期：2026-08-21
> 状态：✅ Accepted（已实施，归档）
> 来源：迁移自 Claude Code 计划 `~/.claude/plans/playful-finding-lemur.md`（v3.0 单实例版·终稿）

---

## 背景

PilotStd 原为单管理员模式：`require_admin` 检查 `username == SUPERUSER_USERNAME` 环境变量，设置页整体对 admin 可见。需改造为多用户模式：所有已登录用户可见设置页，Tab 按 scope 分级过滤，同时补齐注册、审计、ContextVar 基础设施。

## 决策（7 阶段）

1. **设置页可见性 + Tab scope 元数据**：新增 `GET /api/settings/metadata` 返回 Tab scope 定义，三级 scope：`user` / `system-read` / `system-admin`；前端按 scope 过滤 Tab
2. **ContextVar 用户身份传播 + ConfigService**：`pilotstd/core/context.py` 用 `contextvars.ContextVar` 传播当前用户；`ConfigService` 单例区分系统配置与用户偏好（前缀校验，拒绝 `system.`/`auth.`/`role.` 写入）
3. **audit_logs 表**：独立审计日志表（v45 迁移），`write_audit`/`read_audit` helper
4. **默认偏好迁移**（v46）：为现有用户幂等插入默认偏好（`ui.theme=light`, `ui.lang=zh-CN`）
5. **注册 + JWT 增强**：`POST /api/auth/register`（bcrypt + 自动登录）；JWT payload 从 `{sub, iat, exp}` 扩展为 `{sub, user_id, role, iat, exp}`
6. **@require_role("admin") 装饰器**：替换 `require_admin`，拒绝时写 `ACCESS_DENIED` 审计；关键写操作（put_settings/add_user/delete_user）接入审计
7. **验收**：ContextVar 清理、require_role 拒绝+审计、pref key 校验、audit 序列化往返集成测试

## 红线约束（不可违反）

- 无 `tenant_id`、无 `tenants` 表、无 TenantDBRouter（保持单实例）
- 密码不入 `user_preferences`
- ContextVar 必须 try/finally 清理
- `@require_role` 拒绝时写审计
- `user_preferences` key 前缀保护
- `audit_logs.detail` 用 JSON TEXT 兼容
- Tab order 步长 100
- 注册自动登录

## 实施证据

- `pilotstd/core/context.py`（26 行）、`pilotstd/core/audit.py`（71 行）、`pilotstd/core/config/service.py` 存在
- `docker/api/settings.py` L69 有 `GET /api/settings/metadata`
- `docker/auth.py` L197 有 `require_role` 装饰器
- `web/src/views/RegisterView.vue` 存在
- migrations.py 含 v45（audit_logs）、v46（默认偏好）；schema 已演进至 v52（`CURRENT_SCHEMA_VERSION = 52`）
- git log `83fdf800 feat(stage5): registration with rate-limit + JWT sub=str(user_id) + httpOnly cookie`

## 后续演进（超出原计划范围）

- 注册接口补充限流（rate-limit）
- JWT 采用 `sub=str(user_id)` + httpOnly cookie
- schema 后续演进至 v52（user_favorites 兜底补 publish_date 等）
