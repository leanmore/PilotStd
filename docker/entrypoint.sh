#!/bin/bash
set -e

# ── 安全凭证初始化 ──────────────────────────────────────────
# 若未设置 JWT_SECRET / ADMIN_USERNAME / ADMIN_PASSWORD，自动生成随机值并输出到 stdout
CRED_MARKER="/app/data/.credentials_generated"

if [ -z "$JWT_SECRET" ] || [ -z "$ADMIN_USERNAME" ] || [ -z "$ADMIN_PASSWORD" ]; then
    if [ ! -f "$CRED_MARKER" ]; then
        # 仅首次启动时生成并打印（之后可从 docker logs 获取）
        if [ -z "$JWT_SECRET" ]; then
            JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
            export JWT_SECRET
        fi
        if [ -z "$ADMIN_USERNAME" ]; then
            ADMIN_USERNAME="admin"
            export ADMIN_USERNAME
        fi
        if [ -z "$ADMIN_PASSWORD" ]; then
            ADMIN_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(12))")
            export ADMIN_PASSWORD
        fi
        echo "============================================================"
        echo "  PilotStd 首次启动 — 已自动生成安全凭证"
        echo "  ADMIN_USERNAME: $ADMIN_USERNAME"
        echo "  ADMIN_PASSWORD: $ADMIN_PASSWORD"
        echo "  JWT_SECRET: $JWT_SECRET"
        echo "  请妥善保存。也可通过环境变量自行设置："
        echo "    docker run -e ADMIN_USERNAME=xxx -e ADMIN_PASSWORD=xxx ..."
        echo "============================================================"
        # 凭证生成成功后才写标记文件（防止生成失败导致标记残留）
        mkdir -p /app/data
        touch "$CRED_MARKER"
    else
        # 非首次但环境变量仍为空：复用之前生成的（从标记文件恢复）
        # 标记文件存在说明之前生成过，这里无法恢复明文值，
        # 因此若用户未设置环境变量且标记文件存在，用固定占位符通过启动检查
        # 实际生产部署应在首次获取凭证后通过环境变量传入
        echo "[WARNING] 凭证标记文件存在但环境变量未设置，使用标记文件占位"
        if [ -z "$JWT_SECRET" ]; then
            export JWT_SECRET="placeholder_restart_with_env"
        fi
        if [ -z "$ADMIN_USERNAME" ]; then
            export ADMIN_USERNAME="admin"
        fi
        if [ -z "$ADMIN_PASSWORD" ]; then
            export ADMIN_PASSWORD="placeholder_restart_with_env"
        fi
    fi
fi

# ── 超级用户初始化（参照 MoviePilot）──────────────────────
# 首次启动自动创建/更新超级用户，标记文件防止重复初始化
INIT_MARKER="/app/data/.superuser_initialized"
SUPERUSER="${SUPERUSER:-admin}"

if [ ! -f "$INIT_MARKER" ]; then
    echo "[INIT] 首次启动，初始化超级用户..."

    if [ -n "${SUPERUSER_PASSWORD}" ]; then
        python -c "
import sqlite3, hashlib
conn = sqlite3.connect('/app/data/pilotstd.db')
users = conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('$SUPERUSER',)).fetchone()[0]
if users == 0:
    conn.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)',
                 ('$SUPERUSER', hashlib.sha256('$SUPERUSER_PASSWORD'.encode()).hexdigest()))
else:
    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?',
                 (hashlib.sha256('$SUPERUSER_PASSWORD'.encode()).hexdigest(), '$SUPERUSER'))
conn.commit()
"
        echo "[INIT] 超级用户 $SUPERUSER 密码已通过环境变量设置"
    else
        RANDOM_PASS=$(openssl rand -base64 16 | tr -d 'O0l1+/=' | head -c 16)
        python -c "
import sqlite3, hashlib
conn = sqlite3.connect('/app/data/pilotstd.db')
users = conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('$SUPERUSER',)).fetchone()[0]
if users == 0:
    conn.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)',
                 ('$SUPERUSER', hashlib.sha256('$RANDOM_PASS'.encode()).hexdigest()))
else:
    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?',
                 (hashlib.sha256('$RANDOM_PASS'.encode()).hexdigest(), '$SUPERUSER'))
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

# ── 自动更新（参照 MoviePilot）──────────────────────────────
# PILOTSTD_AUTO_UPDATE=true 时执行 update.sh（git pull + 重启进程）
if [ "${PILOTSTD_AUTO_UPDATE}" = "true" ] || [ "${PILOTSTD_AUTO_UPDATE}" = "release" ]; then
    echo "[AUTO-UPDATE] 自动更新已开启，执行更新脚本..."
    chmod +x /app/docker/update.sh 2>/dev/null || true
    /app/docker/update.sh
else
    echo "[AUTO-UPDATE] 自动更新未开启 (PILOTSTD_AUTO_UPDATE=${PILOTSTD_AUTO_UPDATE:-未设置})"
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

# 权限处理：PUID=0 表示以 root 运行，跳过 chown 和 gosu；否则降权到 appuser
if [ "$PUID" = "0" ]; then
    # root 模式：直接启动，不降权（宿主机目录权限由 root 兜底）
    exec uvicorn docker.app:app --host 0.0.0.0 --port 9028
else
    chown -R appuser:appuser /app/data /app/logs /app/downloads /standards /inbox
    exec gosu appuser uvicorn docker.app:app --host 0.0.0.0 --port 9028
fi
