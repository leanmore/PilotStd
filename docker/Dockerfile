# PilotStd Docker 镜像（多阶段构建）
FROM python:3.12-slim AS builder

WORKDIR /app

# 1. 先复制依赖文件（利用 Docker 缓存层——依赖不变则复用）
COPY requirements.txt .
COPY docker/requirements-docker.txt docker/requirements-docker.txt

# 2. 安装依赖（-r ../requirements.txt 在容器内解析为 /app/requirements.txt）
RUN pip install --no-cache-dir -r docker/requirements-docker.txt --target=/install

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 从构建阶段复制已安装的依赖
COPY --from=builder /install /usr/local/lib/python3.12/site-packages/
# 复制 uvicorn 等可执行文件到 PATH
COPY --from=builder /install/bin /usr/local/bin/

# 3. 注入 PYTHONPATH（--target 安装必须）
ENV PYTHONPATH=/install

# U39: 依赖组合 smoke；失败直接 fail build，不能等运行时才发现
# （cloakbrowser 0.7.2 + playwright 1.64.1；1.65 会移除 _impl._js_handle）
RUN python -c "from cloakbrowser import launch, launch_persistent_context"

# 创建非 root 用户
RUN useradd -m appuser
ENV CLOAKBROWSER_CACHE_DIR=/app/data/cloakbrowser

# 安装 gosu + git（自更新 git pull 方案，参照 MoviePilot）
# libxcb1/libgl1 等为 RapidOCR 依赖的 OpenCV 在 slim 镜像中的运行库
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu git curl libxcb1 libgl1 libglib2.0-0 libsm6 libxext6 fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

# CloakBrowser 使用自带 Chromium；Playwright 兜底路径也需要 Chromium，否则回退必失败。
# 固定浏览器目录到镜像层，避免 runtime 用户读不到 /root/.cache。
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install-deps chromium && rm -rf /var/lib/apt/lists/*
RUN python -m playwright install chromium

COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/cloakbrowser.sh /app/cloakbrowser.sh
RUN chmod +x /app/entrypoint.sh /app/cloakbrowser.sh

# 4. 最后复制业务代码（变更频繁，放最后以利用上层缓存）
COPY pilotstd/ ./pilotstd/
COPY main.py .

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9028/api/health')" || exit 1

# 前端构建产物（由 CI npm run build 生成后 COPY 进镜像）
# FRONTEND_CACHE_BUST 参数用于前端代码变更时强制刷新此层
ARG FRONTEND_CACHE_BUST
ARG APP_VERSION=unknown
ENV APP_VERSION=$APP_VERSION
RUN mkdir -p /app/web/dist
COPY web/dist/ ./web/dist/
# 验证前端文件存在
RUN test -f /app/web/dist/index.html

# 复制 docker 模块（app.py、api/ 等）
COPY docker/ ./docker/

EXPOSE 9028

# entrypoint.sh 内部用 gosu appuser 降权，此处保持 root
ENTRYPOINT ["/app/entrypoint.sh"]
