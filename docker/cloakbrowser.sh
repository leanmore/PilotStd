#!/bin/bash
# CloakBrowser 内核预装与缓存目录管理。
# 启动时调用；安装失败只告警，不阻止主服务启动，首次使用时再明确报错。

CLOAKBROWSER_CACHE_DIR="${CLOAKBROWSER_CACHE_DIR:-/app/data/cloakbrowser}"
export CLOAKBROWSER_CACHE_DIR

cloakbrowser_ready() {
    [ -n "${CLOAKBROWSER_CACHE_DIR}" ] || return 1
    CLOAKBROWSER_CACHE_DIR="${CLOAKBROWSER_CACHE_DIR}" python - <<'PY' >/dev/null 2>&1
import os
from cloakbrowser import binary_info
info = binary_info()
path = str(info.get("binary_path") or "")
raise SystemExit(0 if info.get("installed") and path and os.access(path, os.X_OK) else 1)
PY
}

prepare_cloakbrowser_cache() {
    mkdir -p "${CLOAKBROWSER_CACHE_DIR}" || {
        echo "[WARN] 无法创建 CloakBrowser 缓存目录: ${CLOAKBROWSER_CACHE_DIR}"
        return 0
    }
    if [ "${PUID:-}" != "0" ]; then
        chown -R appuser:appuser "${CLOAKBROWSER_CACHE_DIR}" 2>/dev/null || true
    fi
}

install_cloakbrowser_kernel() {
    if [ -z "${CLOAKBROWSER_LICENSE_KEY:-}" ]; then
        echo "[WARN] CLOAKBROWSER_LICENSE_KEY 未设置，跳过 CloakBrowser 内核预装；可信 IP 自动更新会失败"
        return 0
    fi
    echo "[INFO] 检查 CloakBrowser 内核: ${CLOAKBROWSER_CACHE_DIR}"
    if cloakbrowser_ready; then
        echo "[INFO] CloakBrowser 内核已就绪"
        return 0
    fi
    echo "[INFO] 首次安装 CloakBrowser 内核（约 200MB，需要联网）..."
    if [ "${PUID:-}" = "0" ]; then
        CLOAKBROWSER_CACHE_DIR="${CLOAKBROWSER_CACHE_DIR}" python -m cloakbrowser install
    else
        CLOAKBROWSER_CACHE_DIR="${CLOAKBROWSER_CACHE_DIR}" \
            gosu appuser python -m cloakbrowser install
    fi
    if cloakbrowser_ready; then
        echo "[INFO] CloakBrowser 内核安装完成"
    else
        echo "[WARN] CloakBrowser 内核安装失败；首次使用时会再次报错并通知"
    fi
}
