#!/bin/bash
set -e

# ── JWT_SECRET 初始化 ────────────────────────────────────────
# 若未设置 JWT_SECRET，自动生成随机值
if [ -z "$JWT_SECRET" ]; then
    JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
    export JWT_SECRET
    echo "[INIT] JWT_SECRET 已自动生成"
fi

# PUID/PGID: 修正 appuser 的 UID/GID 匹配 NAS 文件权限
if [ -n "$PUID" ] && [ "$PUID" != "0" ]; then
    usermod -u "$PUID" appuser 2>/dev/null || true
fi
if [ -n "$PGID" ] && [ "$PGID" != "0" ]; then
    groupmod -g "$PGID" appuser 2>/dev/null || true
fi

# UMASK: 设置文件创建权限掩码（默认 022，NAS 环境常用 000）
if [ -n "$UMASK" ]; then
    umask "$UMASK"
fi

# 确保持久化目录存在
mkdir -p /app/data /app/logs /app/downloads

# 确保 DB 文件存在并可打开（防止空volume/损坏DB导致启动crash loop）
# 注意：此段以 root 运行，若创建了 DB 文件则需在 chown 之前完成
python -c "
import os, sys, shutil
from datetime import datetime
db_path = '/app/data/pilotstd.db'
if not os.path.exists(db_path):
    print('[entrypoint] DB 不存在，将自动初始化')
else:
    # DB 文件存在但可能损坏 → 备份后重建
    try:
        f = open(db_path, 'rb')
        header = f.read(16)
        f.close()
        if header[:15] != b'SQLite format 3':
            raise OSError('无效的文件头')
    except Exception as e:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        bk = f'/app/data/pilotstd_corrupted_{ts}.db'
        shutil.move(db_path, bk)
        print(f'[entrypoint] DB 已损坏，备份至 {bk}，将重建空库')
sys.path.insert(0, '/app')
from pilotstd.core.db import Database
try:
    db = Database(db_path)
    ver = db.schema_version
    print(f'[entrypoint] DB schema v{ver} OK')
except Exception as e:
    print(f'[entrypoint] DB 初始化警告: {e}（继续启动）')
"

# ── 初始 API Key 自动生成 ─────────────────────────────────────
# 首次启动时自动创建一个默认 API Key，打印到控制台（可通过 docker logs 查看）
python -c "
import hashlib, json, os, secrets, sys
sys.path.insert(0, '/app')
from pilotstd.core.db import Database
db = Database('/app/data/pilotstd.db')
existing = db.fetchone(\"SELECT id FROM api_keys WHERE key_id = 'default'\")
if existing is None:
    raw_key = 'pst_' + secrets.token_urlsafe(24)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db.execute(
        'INSERT INTO api_keys (key_id, key_hash, description, scopes) VALUES (?, ?, ?, ?)',
        ('default', key_hash, '初始默认 Key', json.dumps(['query:read'])),
    )
    print('============================================================')
    print('  初始 API Key 已生成（仅显示一次，请妥善保存）')
    print('  Key ID: default')
    print(f'  Raw Key: {raw_key}')
    print('  使用方式: Authorization: Bearer <raw_key>')
    print('============================================================')
else:
    print('[entrypoint] 初始 API Key 已存在，跳过生成')
"

# ── 超级用户初始化（参照 MoviePilot）──────────────────────
# 必须在 DB 迁移之后执行（users 表已创建）
INIT_MARKER="/app/data/.superuser_initialized"
if [ -z "$SUPERUSER" ]; then
    echo "[INIT] 错误: SUPERUSER 环境变量未设置，拒绝启动"
    exit 1
fi

if [ ! -f "$INIT_MARKER" ]; then
    echo "[INIT] 首次启动，初始化超级用户..."

    if [ -n "${SUPERUSER_PASSWORD}" ]; then
        _PASS="${SUPERUSER_PASSWORD}"
        python -c "
import sqlite3, hashlib, secrets
conn = sqlite3.connect('/app/data/pilotstd.db')
salt = secrets.token_hex(16)
pw = hashlib.pbkdf2_hmac('sha256', '$_PASS'.encode(), salt.encode(), 100000).hex()
users = conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('$SUPERUSER',)).fetchone()[0]
if users == 0:
    conn.execute('INSERT INTO users (username, password_hash, salt, role, must_change_password) VALUES (?, ?, ?, "user", 1)',
                 ('$SUPERUSER', pw, salt))
else:
    conn.execute('UPDATE users SET password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?',
                 (pw, salt, '$SUPERUSER'))
conn.commit()
"
        echo "[INIT] 超级用户 $SUPERUSER 密码已通过环境变量设置"
    else
        RANDOM_PASS=$(openssl rand -base64 16 | tr -d 'O0l1+/=' | head -c 16)
        python -c "
import sqlite3, hashlib, secrets
conn = sqlite3.connect('/app/data/pilotstd.db')
salt = secrets.token_hex(16)
pw = hashlib.pbkdf2_hmac('sha256', '$RANDOM_PASS'.encode(), salt.encode(), 100000).hex()
users = conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('$SUPERUSER',)).fetchone()[0]
if users == 0:
    conn.execute('INSERT INTO users (username, password_hash, salt, role, must_change_password) VALUES (?, ?, ?, "user", 1)',
                 ('$SUPERUSER', pw, salt))
else:
    conn.execute('UPDATE users SET password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?',
                 (pw, salt, '$SUPERUSER'))
conn.commit()
"
        echo "[INIT] ============================================"
        echo "[INIT] 超级用户: $SUPERUSER"
        echo "[INIT] 初始密码: $RANDOM_PASS"
        echo "[INIT] 请登录后立即修改！"
        echo "[INIT] ============================================"
    fi

    touch "$INIT_MARKER"
    echo "[INIT] 超级用户初始化完成"
else
    echo "[INIT] 超级用户已初始化，跳过"
fi

# 权限处理：PUID=0 表示以 root 运行，跳过 chown 和 gosu；否则降权到 appuser
if [ "$PUID" = "0" ]; then
    # root 模式：直接启动，不降权（宿主机目录权限由 root 兜底）
    exec uvicorn docker.app:app --host 0.0.0.0 --port 9028
else
    chown -R appuser:appuser /app/data /app/logs /app/downloads /standards /inbox
    exec gosu appuser uvicorn docker.app:app --host 0.0.0.0 --port 9028
fi
