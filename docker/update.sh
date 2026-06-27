#!/bin/bash
# ============================================================
# PilotStd 自动更新脚本（MoviePilot 模式）
# 检测新版本 → 全量替换代码 → 标记重启 → 退出让 Docker 重建
# ============================================================
set -e

APP_DIR="/app"
DATA_DIR="/app/data"
TEMP_DIR="/app/data/temp"
PENDING_FLAG="/app/data/temp/pilotstd.pending_update"
RESTART_FLAG="/app/data/temp/pilotstd.intentional_restart"
GITHUB_REPO="leanmore/PilotStd"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[UPDATE]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[UPDATE]${NC} $1"; }
log_error() { echo -e "${RED}[UPDATE]${NC} $1"; }

get_local_version() {
    python -c "from pilotstd import __version__; print(__version__)" 2>/dev/null || echo "0.0.0"
}

get_remote_version() {
    local response=$(curl -sL --connect-timeout 10 "${GITHUB_API}")
    if [ -z "$response" ]; then
        echo ""
        return
    fi
    echo "$response" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('tag_name',''))"
}

compare_versions() {
    local v1="${1#v}"
    local v2="${2#v}"
    if [ "$v1" = "$v2" ]; then
        return 0
    fi
    if [ "$(printf "%s\n%s" "$v1" "$v2" | sort -V | head -n1)" = "$v1" ]; then
        return 1  # 需要更新
    else
        return 2  # 本地更新（开发模式）
    fi
}

install_update() {
    local version="$1"
    local tmp_dir=$(mktemp -d)
    local tag="${version}"  # v0.38.0 格式
    local source_url="https://github.com/${GITHUB_REPO}/archive/refs/tags/${tag}.tar.gz"

    log_info "下载后端源码 ${tag}..."
    if ! curl -sL --connect-timeout 60 "${source_url}" | tar xz -C "${tmp_dir}" 2>/dev/null; then
        log_error "后端源码下载失败"
        rm -rf "${tmp_dir}"
        return 1
    fi

    local source_dir="${tmp_dir}/PilotStd-${tag#v}"
    if [ ! -d "${source_dir}" ]; then
        source_dir=$(find "${tmp_dir}" -maxdepth 1 -type d -name "PilotStd-*" | head -n1)
        if [ -z "${source_dir}" ]; then
            log_error "无法找到解压后的源码目录"
            rm -rf "${tmp_dir}"
            return 1
        fi
    fi

    local dist_url="https://github.com/${GITHUB_REPO}/releases/download/${tag}/dist.zip"
    log_info "下载前端资源 ${tag}..."
    if ! curl -sL --connect-timeout 60 "${dist_url}" -o "${tmp_dir}/dist.zip" 2>/dev/null; then
        log_warn "前端资源下载失败（Release 可能尚未构建），继续..."
    fi

    # 备份 data 目录
    if [ -d "${DATA_DIR}" ]; then
        cp -a "${DATA_DIR}" "${tmp_dir}/data_backup"
    fi

    # 全量替换后端代码（保留 entrypoint.sh + update.sh 自身）
    log_info "替换后端代码..."
    rm -rf "${APP_DIR}/pilotstd" "${APP_DIR}/docker" "${APP_DIR}/main.py"
    cp -r "${source_dir}/pilotstd" "${APP_DIR}/pilotstd"
    cp -r "${source_dir}/docker" "${APP_DIR}/docker"
    cp "${source_dir}/main.py" "${APP_DIR}/main.py"
    if [ -f "${source_dir}/pyproject.toml" ]; then
        cp "${source_dir}/pyproject.toml" "${APP_DIR}/pyproject.toml"
    fi
    # 恢复 entrypoint.sh 权限
    chmod +x "${APP_DIR}/docker/update.sh" "${APP_DIR}/entrypoint.sh" 2>/dev/null || true

    # 替换前端资源
    if [ -f "${tmp_dir}/dist.zip" ]; then
        log_info "替换前端资源..."
        mkdir -p "${APP_DIR}/web/dist"
        unzip -o "${tmp_dir}/dist.zip" -d "${APP_DIR}/web/dist/" 2>/dev/null || true
    fi

    # 恢复 data 目录
    if [ -d "${tmp_dir}/data_backup" ]; then
        cp -a "${tmp_dir}/data_backup"/* "${DATA_DIR}/" 2>/dev/null || true
    fi

    # 检查依赖变更
    log_info "检查依赖变更..."
    local old_req="${APP_DIR}/docker/requirements-docker.txt"
    local new_req="${source_dir}/docker/requirements-docker.txt"
    if [ -f "${old_req}" ] && [ -f "${new_req}" ]; then
        if ! cmp -s "${old_req}" "${new_req}"; then
            log_info "依赖变更，重新安装..."
            pip install -r "${new_req}" --quiet
        else
            log_info "依赖无变更，跳过安装"
        fi
    fi

    # 写重启标记
    mkdir -p "${APP_DIR}/data/temp"
    touch "${RESTART_FLAG}"

    rm -rf "${tmp_dir}"
    log_info "✅ 更新完成，即将重启容器..."
    exit 0
}

main() {
    mkdir -p "${TEMP_DIR}"

    local triggered_by_web=false
    if [ -f "${PENDING_FLAG}" ]; then
        triggered_by_web=true
        rm -f "${PENDING_FLAG}"
    fi

    log_info "开始检查更新..."
    local local_ver=$(get_local_version)
    local remote_ver=$(get_remote_version)

    if [ -z "${remote_ver}" ]; then
        log_warn "无法获取远程版本，跳过更新"
        return 0
    fi

    log_info "本地: ${local_ver}  →  远程: ${remote_ver}"

    set +e
    compare_versions "${local_ver}" "${remote_ver}"
    local cmp_result=$?
    set -e

    if [ $cmp_result -eq 0 ]; then
        log_info "已是最新版本，无需更新"
        return 0
    elif [ $cmp_result -eq 2 ]; then
        log_info "本地版本高于远程（开发模式），跳过更新"
        return 0
    fi

    log_info "发现新版本 ${remote_ver}，开始更新..."
    install_update "${remote_ver}"
}

# 支持 source 引入和直接执行两种方式
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
else
    main
fi
