"""静态接口令牌管理（从 docker/auth.py 拆出，G-010 规模控制）。

原 docker/auth.py 有效代码行 490，距 G-010 的 500 行阻断线仅 10 行；
本模块承接「令牌生成 / 落库 / 回写 .env」这段自洽逻辑，函数体逐字节未改，
auth.py 通过再导入保持 `from .auth import get_static_token` 的既有调用方不变。
"""

import hashlib
import logging
import os
import secrets

logger = logging.getLogger(__name__)

# 静态接口令牌：优先取环境变量 PILOTSTD_API_TOKEN，未设置则自动生成随机令牌。
# 进程级缓存（模块变量）——令牌刷新后同一进程内立即生效，不必重启容器。
_STATIC_API_TOKEN = os.environ.get("PILOTSTD_API_TOKEN") or secrets.token_hex(32)
_STATIC_TOKEN_INITIALIZED = False


def _ensure_static_token_in_db():
    """确保静态令牌在 api_keys 表中存在且有效（幂等）。

    每次应用启动时调用——若 PILOTSTD_API_TOKEN 已设置且与 DB 中一致则跳过，
    否则创建/更新一条 key_id='pst_static' 的记录。
    """
    global _STATIC_TOKEN_INITIALIZED
    if _STATIC_TOKEN_INITIALIZED:
        return
    # 令牌只以「哈希」入库存 api_keys：明文仅存在于内存与 .env，避免库被读走即泄露
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database

        db = Database(get_db_path())
        db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL,
                description TEXT DEFAULT '',
                scopes TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                last_used_at TEXT
            )
        """)
        key_hash = hashlib.sha256(_STATIC_API_TOKEN.encode()).hexdigest()
        existing = db.fetchone("SELECT key_hash FROM api_keys WHERE key_id = 'pst_static'")
        if existing:
            if existing["key_hash"] != key_hash:
                db.execute(
                    "UPDATE api_keys SET key_hash=?, is_active=1 WHERE key_id='pst_static'",
                    (key_hash,),
                )
        else:
            db.execute(
                "INSERT INTO api_keys (key_id, key_hash, description, scopes, is_active)"
                " VALUES ('pst_static', ?, 'static-token-from-env', '[\"query:read\", \"announce:read\"]', 1)",
                (key_hash,),
            )
        db.close()
        _STATIC_TOKEN_INITIALIZED = True
    except Exception:
        pass  # 首次启动时 DB 可能尚未初始化，后续请求重试


def get_static_token() -> str:
    """返回当前静态令牌值（供 settings API 读取）。"""
    return _STATIC_API_TOKEN


def refresh_static_token() -> tuple[str, bool]:
    """重新生成静态令牌，更新内存缓存 + 数据库 + 环境变量。

    返回 ``(新令牌, 数据库是否同步成功)``。刷新后旧令牌立即失效。

    裁决 D-5（2026-09-26）：原实现写库失败静默 ``pass``，会出现"内存/环境变量里是
    新令牌、数据库里仍是旧哈希"的不一致状态，且调用方无从得知——新令牌在下一次
    校验时失效却没有任何线索。改为显式返回同步结果，由调用方决定如何暴露。
    """
    global _STATIC_API_TOKEN, _STATIC_TOKEN_INITIALIZED
    # 局部再导入标准库：与既有实现保持一致（函数体逐字节搬移，不改行为）
    import hashlib as _hashlib
    import secrets as _secrets

    new_token = _secrets.token_hex(32)
    new_hash = _hashlib.sha256(new_token.encode()).hexdigest()
    _STATIC_API_TOKEN = new_token
    os.environ["PILOTSTD_API_TOKEN"] = new_token
    # 同步写库：请求校验走 api_keys 表，只改内存不会让新令牌生效
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database

        db = Database(get_db_path())
        existing = db.fetchone("SELECT key_hash FROM api_keys WHERE key_id = 'pst_static'")
        if existing:
            db.execute(
                "UPDATE api_keys SET key_hash=?, is_active=1 WHERE key_id='pst_static'",
                (new_hash,),
            )
        else:
            db.execute(
                "INSERT INTO api_keys (key_id, key_hash, description, scopes, is_active)"
                " VALUES ('pst_static', ?, 'static-token-from-env',"
                ' \'["query:read", "announce:read"]\', 1)',
                (new_hash,),
            )
        db.close()
        db_synced = True
    except Exception:
        # 显式返回失败而非静默吞错：校验走 api_keys 表，同步失败会让新令牌在
        # 重启后失效，必须让调用方与用户都可见（裁决 D-5）。
        db_synced = False
        logger.warning("静态令牌写库失败，内存与数据库可能不一致", exc_info=True)
    # 回写.文件，确保重启后令牌不丢失
    _dotenv_path = os.path.join(os.path.dirname(__file__) or ".", "..", ".env")
    try:
        if os.path.exists(_dotenv_path):
            with open(_dotenv_path, "r", encoding="utf-8") as _f:
                _lines = _f.readlines()
        else:
            _lines = []
        with open(_dotenv_path, "w", encoding="utf-8") as _f:
            _written = False
            for _line in _lines:
                if _line.startswith("PILOTSTD_API_TOKEN="):
                    _f.write(f"PILOTSTD_API_TOKEN={new_token}\n")
                    _written = True
                else:
                    _f.write(_line)
            if not _written:
                _f.write(f"\nPILOTSTD_API_TOKEN={new_token}\n")
    except OSError:
        logger.warning("静态令牌回写 .env 失败，重启后令牌可能回退", exc_info=True)
    return new_token, db_synced
