#!/bin/bash
# PilotStd 更新脚本 v2.1 — 版本比较 + 前端更新 + 依赖编译
# 支持：容器启动时自动检查 + Web 触发一次性更新
# 注意：Docker 镜像不含 .git 目录，git pull 仅在开发/调试容器中生效

set -e

APP_DIR="/app"
DATA_DIR="/app/data"
TEMP_DIR="${DATA_DIR}/temp"
PENDING_FLAG="${TEMP_DIR}/pilotstd.pending_update"
GITHUB_REPO="leanmore/PilotStd"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[UPDATE]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[UPDATE]${NC} $1"; }
log_error() { echo -e "${RED}[UPDATE]${NC} $1"; }

# 1. 读取本地版本
get_local_version() {
    python -c "from pilotstd import __version__; print(__version__)" 2>/dev/null || echo "0.0.0"
}

# 2. 获取远程最新版本（GitHub Release，带超时和错误处理）
get_remote_version() {
    local response
    response=$(curl -sL --connect-timeout 10 "${GITHUB_API}" 2>/dev/null) || true
    if [ -z "$response" ]; then
        log_warn "无法获取远程版本（网络异常或 GitHub API 不可达）"
        return 1
    fi
    echo "$response" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('tag_name',''))" 2>/dev/null || echo ""
}

# 3. 版本比较（返回 0=相等 1=本地更旧 2=本地更新）
compare_versions() {
    local v1="${1#v}"
    local v2="${2#v}"
    if [ "$v1" = "$v2" ]; then
        return 0
    fi
    if [ "$(printf "%s\n%s" "$v1" "$v2" | sort -V | head -n1)" = "$v1" ]; then
        return 1  # v1 < v2
    else
        return 2  # v1 > v2
    fi
}

# 4. 更新后端代码（仅当 .git 目录存在时执行 git pull）
update_backend() {
    log_info "更新后端代码..."
    cd "${APP_DIR}" || return 1

    # Docker 镜像不含 .git 目录，跳过 git 操作
    if [ ! -d "${APP_DIR}/.git" ]; then
        log_info ".git 目录不存在（生产镜像），后端代码随镜像更新，跳过 git pull"
        return 0
    fi

    if ! git diff --quiet 2>/dev/null; then
        log_warn "存在未提交的更改，跳过 git pull"
        return 0
    fi

    if git pull origin main 2>&1; then
        log_info "后端代码已更新"
    else
        log_error "git pull 失败"
        return 1
    fi
}

# 5. 更新前端资源（下载 GitHub Release 中的 dist.zip）
update_frontend() {
    local version="${1}"
    local dist_url="https://github.com/${GITHUB_REPO}/releases/download/${version}/dist.zip"
    local dist_zip="/tmp/pilotstd_dist_${version}.zip"

    log_info "更新前端资源 (${version})..."
    if ! curl -sL --connect-timeout 60 "${dist_url}" -o "${dist_zip}" 2>/dev/null; then
        log_warn "前端 dist.zip 下载失败（Release 可能尚未构建），跳过前端更新"
        rm -f "${dist_zip}"
        return 0
    fi

    mkdir -p "${APP_DIR}/web/dist"
    if unzip -o "${dist_zip}" -d "${APP_DIR}/web/dist/" 2>/dev/null; then
        log_info "前端资源已更新"
        rm -f "${dist_zip}"
    else
        log_warn "前端 dist.zip 解压失败"
        rm -f "${dist_zip}"
        return 1
    fi
}

# 6. 依赖编译（仅当 .git 目录存在时检测变更）
update_dependencies() {
    log_info "检查依赖变更..."
    cd "${APP_DIR}" || return 1

    # 生产镜像不含 .git，无法检测变更
    if [ ! -d "${APP_DIR}/.git" ]; then
        log_info ".git 目录不存在，跳过依赖变更检测"
        return 0
    fi

    if ! git diff HEAD@{1} HEAD --name-only 2>/dev/null | grep -qE "requirements\.in|docker/requirements-docker\.txt"; then
        log_info "依赖无变化"
        return 0
    fi

    log_info "依赖已变更，重新安装..."
    if [ -f "requirements.in" ] && command -v pip-compile >/dev/null 2>&1; then
        log_info "编译 requirements.in → requirements.txt"
        pip-compile requirements.in -o requirements.txt || log_warn "pip-compile 失败，使用现有 requirements.txt"
    fi
    pip install -r docker/requirements-docker.txt
    log_info "依赖安装完成"
}

# 7. 清除 Pending 标记
clear_pending_flag() {
    if [ -f "${PENDING_FLAG}" ]; then
        rm -f "${PENDING_FLAG}"
        log_info "已清除 pending 更新标记"
    fi
}

# 主流程
main() {
    # 确保 temp 目录存在
    mkdir -p "${TEMP_DIR}"

    # 检查是否被显式禁用
    if [ "${PILOTSTD_AUTO_UPDATE}" = "false" ]; then
        log_info "自动更新已禁用 (PILOTSTD_AUTO_UPDATE=false)"
        clear_pending_flag
        return 0
    fi

    # 检查 Web 触发的一次性更新标记
    local triggered_by_web=false
    if [ -f "${PENDING_FLAG}" ]; then
        local flag_mode
        flag_mode=$(tr -d '\r\n' < "${PENDING_FLAG}" | tr '[:upper:]' '[:lower:]')
        if [ "$flag_mode" = "release" ] || [ "$flag_mode" = "true" ]; then
            triggered_by_web=true
            log_info "检测到 Web 触发的更新请求 (mode=${flag_mode})"
        fi
    fi

    log_info "开始检查更新..."

    # 获取版本
    local local_ver
    local_ver=$(get_local_version)
    local remote_ver
    remote_ver=$(get_remote_version) || true

    if [ -z "$remote_ver" ]; then
        log_warn "无法获取远程版本，跳过更新"
        clear_pending_flag
        return 0
    fi

    log_info "本地: ${local_ver}  →  远程: ${remote_ver}"

    # 版本比较
    compare_versions "${local_ver}" "${remote_ver}"
    local cmp_result=$?

    if [ $cmp_result -eq 0 ]; then
        log_info "已是最新版本，无需更新"
        clear_pending_flag
        return 0
    elif [ $cmp_result -eq 1 ]; then
        log_info "发现新版本 ${remote_ver}，开始更新..."

        update_backend
        update_frontend "${remote_ver}" || log_warn "前端更新失败（后端已更新）"
        update_dependencies || log_warn "依赖更新失败（代码已更新）"

        clear_pending_flag
        log_info "✅ 更新完成"

        if [ "$triggered_by_web" = true ]; then
            log_info "Web 触发模式：退出容器，Docker 重启策略将重建容器"
            exit 0
        fi
    else
        log_info "本地版本 ${local_ver} 高于远程 ${remote_ver}（开发模式），跳过更新"
        clear_pending_flag
        return 0
    fi
}

main "$@"
