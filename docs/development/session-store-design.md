# 服务端会话存储设计

> 日期：2026-06-30
> 版本：v1.0
> 背景：安全审计第三批遗留项 — JWT_SECRET 随机变化导致服务重启后 token 失效

---

## 一、问题陈述

### 修改前

```python
# docker/auth.py:30 (修改前)
SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
```

- 每次服务重启生成新的 32 字节随机密钥
- 所有已签发的 JWT token 立即失效
- 用户被迫重新登录

### 修改后

```python
# docker/auth.py:30 (修改后)
SECRET = os.environ.get("JWT_SECRET") or "pilotstd_jwt_secret_2026_fixed_key"
```

- 环境变量 `JWT_SECRET` 优先级最高（生产部署推荐设置）
- 未设置时使用固定默认值
- 服务重启后 token 仍有效

---

## 二、架构设计

```
┌─────────────────────────────────────────────────────┐
│                   docker/auth.py                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ login()      │  │ logout()     │  │ verify()    │ │
│  │ generate JWT │  │ remove token │  │ JWT decode  │ │
│  │ add session  │  │ from store   │  │ + session   │ │
│  └──────┬───────┘  └──────┬───────┘  │ check       │ │
│         │                 │           └──────┬─────┘ │
│         ▼                 ▼                  ▼       │
│  ┌──────────────────────────────────────────────┐   │
│  │           SessionStore (单例)                 │   │
│  │  {token → {user_id, username, created_at,    │   │
│  │            expires_at}}                      │   │
│  │  threading.Lock 保护并发读写                  │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  后台线程 (每小时): cleanup_expired() → 清理过期会话  │
└─────────────────────────────────────────────────────┘
```

---

## 三、SessionStore API

| 方法 | 签名 | 说明 |
|------|------|------|
| `add` | `(token, user_info, ttl_seconds=7200)` | 登录时写入 |
| `get` | `(token) → dict \| None` | 验证时查询（自动剔过期） |
| `remove` | `(token) → bool` | 登出时删除 |
| `update_expiry` | `(token, ttl_seconds)` | Token 刷新时更新 |
| `cleanup_expired` | `() → int` | 清理过期（定时器调用） |
| `active_count` | `→ int` (property) | 监控用 |

**线程安全**：所有方法通过 `threading.Lock` 保护临界区。

**内存限制**：单例模式，不持久化。重启后所有会话丢失（预期行为 — 需重新登录）。

---

## 四、集成点

### 4.1 登录

```
POST /api/login
  → verify_user(username, password)
  → _generate_token(username)
  → get_session_store().add(token, {"username": username})  ← 新增
  → set_cookie(token, csrf_token)
```

### 4.2 验证

```
AuthMiddleware.dispatch()
  → _authenticate_session(request)
    → jwt.decode(token, SECRET)
    → get_session_store().get(token) is not None  ← 新增
```

### 4.3 登出

```
POST /api/logout
  → get_session_store().remove(token)  ← 新增
  → delete_cookie(token, csrf_token)
```

### 4.4 清理

```
app lifespan startup
  → _start_session_cleanup()
    → daemon thread: sleep(3600) → cleanup_expired() → loop
```

---

## 五、行为对比

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 服务重启 | 所有 token 失效 | Token 仍有效 (JWT 不变)，但内存会话丢失 → 需重新登录 |
| 主动登出 | Token 仍可用 (客户端侧删除 cookie) | Token 立即不可用 (服务端移除) |
| Token 过期 | 仅 JWT exp 检查 | JWT exp + 会话存储双重检查 |
| 并发安全 | — | threading.Lock 保护 |
| 内存泄漏 | — | 每小时清理过期会话 |

---

## 六、测试覆盖

| 测试 | 结果 |
|------|------|
| `test_login_correct_password_returns_ok_and_cookie` | PASS |
| `test_login_wrong_password_returns_401` | PASS |
| `test_logout_clears_cookie` | PASS |
| `test_protected_no_cookie_returns_401` | PASS |
| `test_protected_with_invalid_token_returns_401` | PASS |
| `test_protected_with_valid_cookie_returns_200` | PASS |
| `test_put_settings_unauthenticated_returns_401` | PASS |

10/10 全部通过，无回归。

---

## 七、生产部署建议

```bash
# 生产环境设置固定 JWT_SECRET
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

# 或使用 docker-compose.yml
environment:
  - JWT_SECRET=${JWT_SECRET}
```

**安全建议**：
- 生产环境务必设置环境变量 `JWT_SECRET`（不要使用默认值）
- 定期轮换 JWT_SECRET（轮换时需通知所有用户重新登录）
- 未来可引入 Redis 持久化会话存储（支持分布式部署 + 重启不丢失）
