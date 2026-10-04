# 鉴权状态与常量（步：自 auth.py 拆出，G-010 余量恢复）
"""鉴权模块的**共享状态与常量**：JWT 密钥、Cookie/CSRF/接口密钥 Header 名、速率限制状态、
白名单、接口密钥校验。

**为何独立成模块**：中间件（`auth_middleware.py`）需要这些状态，而 `auth.py` 又要再导出
中间件——若状态留在 `auth.py` 会形成**循环导入**。状态独立后三方单向依赖：
`auth.py` → `auth_state`，`auth_middleware` → `auth_state`。
"""

import hashlib
import logging
import os
import secrets
import threading
from collections import defaultdict
from pathlib import Path

from pilotstd.i18n import t

logger = logging.getLogger(__name__)


def _load_or_create_secret() -> str:
    """取 JWT 密钥：环境变量 > 落盘文件 > 新生成并落盘。

    原实现未设环境变量时每次进程启动随机（容器重启即全员掉线）；决策 #6 由"固定/随机二选一"
    改为落盘复用（`DATA_DIR/.jwt_secret`，权限 600），两头问题一并消除。
    落盘失败降级为进程内随机（只告警，不阻断启动）。
    """
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        return env_secret

    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    secret_file = Path(data_dir) / ".jwt_secret"
    try:
        if secret_file.exists():
            saved = secret_file.read_text(encoding="utf-8").strip()
            if saved:
                return saved
    except OSError:
        logger.warning(t("auth.log.secret_read_failed"), exc_info=True)

    generated = secrets.token_urlsafe(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(generated, encoding="utf-8")
        os.chmod(secret_file, 0o600)
        logger.info(t("auth.log.secret_generated").format(path=secret_file))
    except OSError:
        logger.warning(t("auth.log.secret_persist_failed"), exc_info=True)
    return generated


SECRET = _load_or_create_secret()

# 应用启动时确保用户表存在

TOKEN_EXPIRE_HOURS = 2  # jwt 过期时间（小时），可通过 TOKEN_EXPIRE_HOURS 环境变量覆盖
COOKIE_NAME = "pilotstd_token"
CSRF_HEADER = "X-CSRF-Token"
API_TOKEN_HEADER = "X-API-KEY"  # 静态令牌 Header（参考 MoviePilot）





AUTH_WHITELIST: list[tuple[str, set[str]]] = [
    ("/api/login", set()),
    ("/api/logout", set()),
    ("/api/health", set()),
    ("/api/system/version", {"GET"}),
    ("/api/logs", {"GET"}),
    # 登录页背景图 URL（公开接口）：仅暴露 appearance.login_bg 单字段，替代
    # 仅管理员的 GET /api/settings 在未登录态下的 401 拦截问题
    ("/api/login-background", set()),
    ("/api/backgrounds", set()),
    ("/assets", set()),
    # B2b-1：渠道回调端点。免鉴权是**有意**的（渠道服务器无法持我方会话），
    # 唯一安全边界是逐渠道自实现验签 + 幂等 + 服务端角色授权（见 core/notification/callback*.py）。
    ("/api/notification/callback", set()),
]


# 接口全局速率限制：{:[,...]}，=用户名或
_api_rate_limit: dict[str, list[float]] = defaultdict(list)
_api_rate_lock = threading.Lock()  # 保护 _api_rate_limit 并发读写
API_RATE_LIMIT = 1000  # 每分钟最多 1000 次请求（压测放宽）
API_RATE_WINDOW = 60  # 窗口 60 秒


def verify_api_key(token: str) -> dict | None:
    """验证 API Key。返回 {key_id, scopes} 或 None。
    token 以 "pst_" 开头，提取后 SHA256 哈希查表，验证 is_active=1。
    """
    if not token.startswith("pst_"):
        return None
    actual_token = token[4:]  # 去掉 "pst_" 前缀后做 SHA256 哈希
    key_hash = hashlib.sha256(actual_token.encode()).hexdigest()
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    db = Database(get_db_path())
    row = db.fetchone(
        "SELECT key_id, scopes FROM api_keys WHERE key_hash = ? AND is_active = 1",
        (key_hash,),
    )
    if row is None:
        return None
    # 更新__
    db.execute(
        "UPDATE api_keys SET last_used_at = datetime('now', 'localtime') WHERE key_hash = ?",
        (key_hash,),
    )
    try:
        import json

        scopes = json.loads(row["scopes"]) if row["scopes"] else []
    except (json.JSONDecodeError, TypeError):
        scopes = []
    return {"key_id": row["key_id"], "scopes": scopes}


