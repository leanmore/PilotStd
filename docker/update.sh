#!/bin/bash
# 参照 MoviePilot 的 mp_update.sh
# 拉取最新代码并重启应用进程，不重启容器

set -e

echo "[UPDATE] 开始更新..."

# 切换到应用目录
cd /app || exit 1

# 检查是否有未提交的更改
if ! git diff --quiet; then
    echo "[UPDATE] 警告: 存在未提交的更改，跳过更新"
    exit 0
fi

# 拉取最新代码
echo "[UPDATE] 正在拉取最新代码..."
if git pull origin main 2>&1; then
    echo "[UPDATE] 代码拉取成功"
else
    echo "[UPDATE] 代码拉取失败，继续启动现有版本"
    exit 0
fi

# 检查 requirements.txt 是否有变更，如有则重新安装依赖
if git diff HEAD@{1} HEAD --name-only 2>/dev/null | grep -q "requirements.txt"; then
    echo "[UPDATE] 检测到依赖变更，重新安装..."
    pip install -r docker/requirements-docker.txt
fi

# 重启应用进程（不重启容器）
echo "[UPDATE] 正在重启应用服务..."
pkill -f "uvicorn" || true

echo "[UPDATE] 更新完成"
