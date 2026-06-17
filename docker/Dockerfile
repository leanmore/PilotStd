# PilotStd Docker 镜像（多阶段构建）
FROM python:3.12-slim AS builder

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY docker/requirements-docker.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --target=/install

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 从构建阶段复制已安装的依赖
COPY --from=builder /install /usr/local/lib/python3.12/site-packages/
# 复制 uvicorn 等可执行文件到 PATH
COPY --from=builder /install/bin /usr/local/bin/

# 创建非 root 用户
RUN useradd -m appuser

# 安装 gosu + docker CLI（用于自更新 API 执行 docker pull/restart）
RUN apt-get update && apt-get install -y --no-install-recommends gosu curl && \
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && \
    sh /tmp/get-docker.sh --version 27.0.3 2>/dev/null || true && \
    rm -f /tmp/get-docker.sh && \
    rm -rf /var/lib/apt/lists/*

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 复制源码
COPY pilotstd/ ./pilotstd/
COPY main.py .

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9028/api/health')" || exit 1

# 前端构建产物（若未构建则创建空目录占位，后续 Task 5/19 构建后填充）
RUN mkdir -p /app/web/dist
COPY web/dist/ /app/web/dist/

# 复制 docker 模块（app.py、api/ 等）
COPY docker/ ./docker/

EXPOSE 9028

# entrypoint.sh 内部用 gosu appuser 降权，此处保持 root
ENTRYPOINT ["/entrypoint.sh"]
