# MoviePilot 通知多用户隔离设计调研

## 0. 基本信息

- 源码版本：`9d8014aa23e57fc1c2cded73c0fad648b34ded09`（`--depth 1`）
- clone 时间：2026-11-01 07:48（Asia/Shanghai）
- 源码位置：`C:\Temp\research\MoviePilot`（仓库外，未复制进 PilotStd）
- 分析范围：
  - `app/schemas/message.py`（消息模型）
  - `app/chain/_messaging.py`（通知路由状态机）
  - `app/foundation/identity.py`（系统内部用户）
  - `app/db/adapters/user.py`（用户通知设置/广播目标）
  - `app/application/notification.py`（场景开关）
  - `app/api/endpoints/notification.py`、`app/api/endpoints/message.py`（API 权限）
  - `app/db/models/message.py`（历史表）

---

## 1. 数据结构

通知消息的核心模型是 `Message`（`app/schemas/message.py:264`），关键字段：

```python
channel: Optional[NotificationChannel]
mtype: Optional[MessageType]
userid: Optional[Union[str, int]]      # 用户 ID
username: Optional[Union[str, int]]    # 用户名称（用户路由时作为接收人）
targets: Optional[dict[str, Any]]      # 渠道 -> 目标用户 ID 集合
private_delivery: bool = False         # 必须私聊投递
```

运行时还有一个**不落库**的隔离范围：

```python
_notification_route_scope: Optional[str] = _PrivateAttr(default=None)
def set_notification_route_scope(self, scope): ...
```

解读：

- **scope 不是数据库字段**，只在路由过程中标记本条消息属于 `admin` / `user` / `all`；
- `targets` 是“渠道 → 目标账号集合”的字典，渠道消费者只按目标投递；
- 没有 `admin_only` / `broadcast` 布尔字段；范围由 `NotificationSwitchConf.action` 与路由状态机决定。

历史表 `Message`（`app/db/models/message.py`）有 `userid`、`source`、`channel`、`action` 等列，但没有单独的 `scope`/`targets` 列；`userid` 是消息关联的用户，不是“可见范围”。

---

## 2. 用户隔离机制

### 2.1 投递层：按 `targets` 隔离

`app/chain/_messaging.py:99` 的 `_notification_route_steps` 是同步/异步共用的路由状态机。核心分支：

- `admin`：读取**超管**的通知设置，作为 `targets`；
- `user`：读取**消息关联用户**的设置；设置里没有任何渠道目标时——**直接跳过**，日志“用户 X 未绑定通知渠道，消息不会发送”；
- `all`：读取“广播目标”（见 §4），逐账号补充 `targets`。

也就是说，隔离发生在**投递目标**层，不是靠请求上下文过滤。

### 2.2 权限层：API 只允许用户操作自己的通知身份

`app/api/endpoints/notification.py:25-46`：

```python
def manage_app_notification(request, current_user=Depends(get_current_active_user)):
    if not current_user.notification_identity:
        return ...
    result = NotificationChain().manage_channel(
        channel="AppPush", action=request.action,
        owner=current_user.notification_identity, **params)
```

用户只能管理自己的 AppPush 身份；渠道全局配置端点用 `get_current_active_superuser`（仅管理员）。

### 2.3 历史列表：**全局可见**（重要差异）

`app/api/endpoints/message.py:231-249` 的 `GET /notification` 只校验登录：

```python
async def get_notification_message(_: _SchemaTokenPayload = Depends(verify_token), ...):
    messages = await service.list_notifications(...)
```

`MessageQueryService.list_notifications` → `async_list_sent_by_page` 的 SQL **没有 userid 过滤**。
结论：MoviePilot 的**通知历史是全局的**，多用户隔离只覆盖“投递到谁”，不覆盖“谁能看历史”。
这是与 PilotStd A-21 目标（日志按用户过滤）不同的取舍，不能直接照搬。

---

## 3. 系统任务归属

`app/foundation/identity.py`：

```python
SYSTEM_INTERNAL_USER_ID = "system"

def normalize_internal_user_id(userid):
    if is_internal_user_id(userid):
        return None
    return userid
```

后台任务/agent 会话使用占位 `"system"` 标识自己，但在真正发送通知前被归一化为 `None`，
避免被渠道误认为真实接收人。

`app/chain/_messaging.py:99` 前的 `_notification_route_action`：

```python
if message.userid:
    return None
if not message.mtype:
    return "admin"
return get_notification_switch(message.mtype) or "admin"
```

解读：

- 没有“系统用户收件箱”这种实体；
- 系统任务的消息 `userid=None` → 按**场景开关**路由，缺省 `admin`；
- 占位用户 `"system"` 不会成为接收人，只用于 agent/memory 隔离。

---

## 4. 渠道 ID 绑定与回退

### 4.1 绑定位置

`app/db/adapters/user.py:355-390`：

```python
def get_notification_settings(self, name):
    user = self.get_by_name(name)
    settings = dict(user.settings)          # 每用户一份：telegram/wechat/...
    settings.pop("apppush", None)
    if user.is_active and user.notification_identity:
        settings["apppush"] = user.notification_identity
    return settings
```

- 每个用户的 `settings` 字典按渠道保存自己的目标（chat_id / open_id / webhook 等）；
- `apppush` 不接受客户端设置，由系统分配不可变 `notification_identity` 注入；
- 广播目标只取**启用且 identity 非空**的账号：

```python
select(User.notification_identity).where(User.is_active.is_(True), ...)
```

### 4.2 未绑定时的行为

| 场景 | 行为 |
|---|---|
| 用户存在但该渠道无目标 | **静默跳过**（日志“未绑定通知渠道，消息不会发送”） |
| 用户不存在 | 回退到**管理员**（若管理员尚未收到） |
| 管理员路由但设置为空 | 允许各渠道使用**自身默认目标**（不当作广播） |
| `all` 广播 | 只补 AppPush 的明确 identity，不把缺少目标当无条件下发 |

不是“统一回退默认渠道”，而是按路由类型区分：用户未绑定就跳过，用户不存在才回退管理员。

---

## 5. 事件路径的 user_id 传递

- `post_message(message: Message, ...)` 接收的是**消息对象**，`userid` / `username` 是消息字段；
- 路由状态机对消息做 `deepcopy`，每条路由写入自己的 `targets`，不依赖全局 `current_user`；
- API 层用 `ApiPrincipal`（`app/api/principal.py`）注入 `notification_identity`，但该身份只用于 AppPush 管理，不参与事件路由；
- 并发安全来自“**每条消息携带自己的目标**”，而不是“设置全局 user_id”。

对 PilotStd 的启示：事件发送函数应显式接收 `scope` + `target_user_id`，不能靠 manager 可变属性。

---

## 6. 操作人 vs 管理员 vs 所有人

`app/application/notification.py:56-66`：

```python
def get_notification_switch(mtype):
    for switch in get_service_configs(SystemConfigKey.NotificationSwitchs, NotificationSwitchConf):
        if switch.type == mtype.value:
            return switch.action or "admin"
    return "admin"
```

`NotificationSwitchConf.action` 取值 `all` / `user` / `admin`（可逗号组合，如 `admin,user`）。

路由状态机（`_notification_route_steps`）：

- `admin`：发给超管；
- `user`：发给 `message.username` 对应用户；无绑定跳过；用户不存在回退管理员；
- `all`：广播目标（当前实现是 AppPush 明确 identity）；
- 未配置/未知：默认 `admin`。

因此“只有操作人收到 / 管理员也收到 / 所有人收到”不是事件代码里 if-else 写死，而是**按消息类型配置的路由策略**。

补充：

- “用户 A 触发、通知用户 B”：通过消息的 `username`（接收人）与 `userid`（触发者）分离表达；
- 广播与管理员可见在数据结构上靠 `targets` 与运行时 `scope` 区分，不靠布尔开关；
- 未绑定渠道选择“静默跳过”而非“回退默认”，理由是避免把用户消息误发给管理员/默认群。

---

## 7. 对 PilotStd A-21 第三步的借鉴建议

> 前提差异：MoviePilot 是插件化、多实例、消息对象自带 targets；PilotStd 是单例 `NotificationManager` + SQLite，事件发送走 `send_event`。不能直接抄代码。

### 7.1 事件路径 scope（直接借鉴“显式随消息携带”）

建议给 PilotStd 的事件路径增加一个**显式上下文**，而不是继续用 `manager._user_id`：

```python
@dataclass(frozen=True)
class NotificationContext:
    scope: Literal["user", "admin", "all"]
    user_id: int | None   # scope=user 时必填；admin/all 为 None
```

- `send_event(event, context=...)`：调用方必须显式给出；
- 系统任务传 `scope="admin"`（或 `"all"` 仅在明确广播时）；
- 旧调用可暂时 `context=None` → 默认 `admin`（兼容），但**不再读取 manager 的可变 `_user_id`**；
- 并发安全由“每次调用一个 context”保证，符合 MoviePilot 的“消息自带目标”思路。

### 7.2 系统任务归属（借鉴 `"system"` → None 的归一化）

- 引入 `SYSTEM_USER_ID = 0`（或 `None`）表示“系统任务”，**不落成 user 1**；
- `notification_log.user_id`：系统任务写 `0`（或 NULL）+ `source` 标记，而不是默认 1；
- 路由缺省：系统任务 → `admin`；用户事件 → `user`；
- 这样 A-40（旧数据全归 1）才有明确迁移目标：1 是真实用户，0 是系统。

### 7.3 None 语义（明确“无用户上下文”≠“user 1”）

- `enabled_for(None)` / `is_quiet_hours(None)` 当前按“系统默认”处理，应继续；
- 事件上下文 `None` → 默认 `admin` 路由，不写 user 1；
- 写库时 `user_id` 为 `None` → **0/system**，而不是 `or 1`；
- 与 MoviePilot 一致：系统占位身份在发送前归一化为“无真实接收人”，由路由策略决定管理员。

### 7.4 渠道绑定与回退（部分借鉴）

- PilotStd 已有 `user_credentials`（按用户），方向正确；
- 建议区分：
  - 用户事件 + 用户未绑定 → **跳过**（不打扰管理员）；
  - 系统事件 + 管理员未绑定 → 回退渠道默认配置；
  - 用户不存在 → 管理员（与 MoviePilot 一致）；
- 不要引入 MoviePilot 的 `targets` 字典结构——PilotStd 单渠道单用户，`user_credentials` 足够。

### 7.5 历史列表（不照搬）

MoviePilot 历史全局可见；PilotStd A-21 已经选择“按 user_id 过滤 + admin all=true”，更严格，**保持 PilotStd 的选择**，不要为了对齐 MoviePilot 放宽。

### 7.6 不建议照搬

- 插件模块系统、`targets` 多账号广播、AppPush identity；
- `Message` 巨型模型（PilotStd 的 `NotificationMessage` 更窄）；
- 全局历史不加过滤（与 PilotStd 安全目标相反）。

---

## 8. 未覆盖的部分

- MoviePilot 消息队列的并发锁实现（`messagequeue`）未深入；
- Telegram/钉钉等模块的 per-user 管理配置细节未逐个读；
- 未查 commit 历史解释“为什么历史列表全局可见”（当前代码只能确认事实）；
- 未分析 Web Push / AppPush 的具体投递失败重试。

以上不影响 A-21 第三步的三个设计问题（scope、系统归属、None 语义）的结论。
