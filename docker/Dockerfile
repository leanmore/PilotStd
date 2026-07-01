# PilotStd Docker 镜像（多阶段构建）
FROM python:3.12-slim AS builder

WORKDIR /app

# 1. 复制依赖文件到同一目录（使 -r requirements-base.txt 引用可解析）
COPY requirements.txt /tmp/requirements-base.txt
COPY docker/requirements-docker.txt /tmp/requirements-docker.txt

# 2. 安装依赖（利用 Docker 缓存层——依赖不变则复用）
RUN pip install --no-cache-dir -r /tmp/requirements-docker.txt --target=/install

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 从构建阶段复制已安装的依赖
COPY --from=builder /install /usr/local/lib/python3.12/site-packages/
# 复制 uvicorn 等可执行文件到 PATH
COPY --from=builder /install/bin /usr/local/bin/

# 3. 注入 PYTHONPATH（--target 安装必须）
ENV PYTHONPATH=/install

# 创建非 root 用户
RUN useradd -m appuser

# 安装 gosu + git（自更新 git pull 方案，参照 MoviePilot）
RUN apt-get update && apt-get install -y --no-install-recommends gosu git curl && \
    rm -rf /var/lib/apt/lists/*

COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 4. 最后复制业务代码（变更频繁，放最后以利用上层缓存）
COPY pilotstd/ ./pilotstd/
COPY main.py .

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9028/api/health')" || exit 1

# 前端构建产物（由 CI npm run build 生成后 COPY 进镜像）
# FRONTEND_CACHE_BUST 参数用于前端代码变更时强制刷新此层
ARG FRONTEND_CACHE_BUST
RUN mkdir -p /app/web/dist
COPY web/dist/ ./web/dist/
# 验证前端文件存在
RUN test -f /app/web/dist/index.html && echo "✅ 前端资源已包含" || echo "⚠️ 前端资源缺失"

# 复制 docker 模块（app.py、api/ 等）
COPY docker/ ./docker/

EXPOSE 9028

# entrypoint.sh 内部用 gosu appuser 降权，此处保持 root
ENTRYPOINT ["/app/entrypoint.sh"]
