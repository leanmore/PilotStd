<!-- Meta: Last-Reviewed=2026-07-16 | Review-Cycle=90d | Status=Active -->
# PilotStd Docker 使用指南

**日期**: 2026-05-29 | **版本**: v1.0
**适用**: 群晖 DSM 7.2+ (Container Manager, Docker Engine 24.0.2) / 其他支持 Docker Compose 的 Linux 系统

---

## 零、两种部署方式

| 方式 | 适用场景 | 需要 |
|------|------|------|
| **A: 使用预构建镜像（推荐）** | 只想用，不想构建 | 只需 `docker-compose.yml` + `.env` |
| **B: 本地构建** | 修改了代码，需要自定义 | 完整项目文件 |

---

## 一、方式 A：预构建镜像

### A.1 获取 docker-compose.yml

复制 [docker-compose.example.yml](docker-compose.example.yml) → 改名为 `docker-compose.yml`。

将 `build:` 段替换为 `image:`：

```yaml
services:
  pilotstd:
    image: ghcr.io/<你的GitHub用户名>/pilotstd:latest
    # build:  ← 删掉或注释掉
    #   context: .
    #   dockerfile: Dockerfile
    container_name: pilotstd
    # ... 其余不变
```

### A.2 配置 `.env`

同 [2.1](#21-配置环境变量)。

### A.3 拉取并启动

```bash
docker compose pull
docker compose up -d
```

### A.4 更新

```bash
docker compose pull
docker compose up -d
```

> ⚠️ 首次拉取需要 GitHub 登录。在群晖上执行 `echo $CR_PAT | docker login ghcr.io -u <用户名> --password-stdin`，其中 `CR_PAT` 是 GitHub Personal Access Token（权限勾选 `read:packages`）。

---

## 二、方式 B：本地构建

### 1.1 安装 Docker

群晖：套件中心 → 搜索"Container Manager" → 安装（DSM 7.2+ 自带，Docker Engine 24.0.2，内置 `docker compose` 命令）。旧版 DSM 7.1 的"Docker"套件为 Engine 20.10，需升级。

其他 Linux：
```bash
curl -fsSL https://get.docker.com | sh
```

验证：
```bash
docker --version          # 应 >= 20.10
docker compose version    # 应显示 Compose V2
```

### 1.2 规划目录

在群晖 File Station 中创建以下目录：

```
/volume1/docker/pilotstd/       ← 工作目录（docker-compose.yml 放这里）
├── data/                        ← 配置文件 + 数据库（自动创建）
├── logs/                        ← 应用日志（自动创建）
├── downloads/                   ← 下载临时文件（自动创建）
/volume1/standards/              ← 标准库输出（你的归档目的地）
/volume1/media/                  ← 扫描源（你自己收集的标准文件目录）
```

> 💡 路径可以自定义。只需在 `docker-compose.yml` 中修改 `volumes` 映射和 `.env` 中的变量。

### 1.3 获取文件

将以下文件复制到群晖的 `/volume1/docker/pilotstd/`：

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 镜像构建 |
| `docker-compose.yml` | 服务编排（可复制 `docs/reference/docker-compose.example.yml` 改名为 `docker-compose.yml`） |
| `.dockerignore` | 排除无用文件 |
| `entrypoint.sh` | 容器入口脚本 |
| `app.py`, `auth.py`, `scheduler.py` | FastAPI 模块 |
| `api/` 目录（含 9 个 `.py`） | API 路由 |
| `pilotstd/` 目录（整个） | 核心模块 |
| `main.py` | 入口 |
| `web/dist/` 目录 | 前端构建产物 |
| `requirements.txt` | Python 依赖清单 |

方式一：开发机直接复制：
```bash
# 在你的 Windows 上
scp -r d:\PilotStd\docker your-nas-user@nas-ip:/volume1/docker/pilotstd/
scp d:\PilotStd\.dockerignore your-nas-user@nas-ip:/volume1/docker/pilotstd/
```

方式二：通过群晖 File Station 上传。

最终目录结构（docker-compose.yml 与 Dockerfile 同级）：
```
/volume1/docker/pilotstd/
├── docker-compose.yml    ← docker-compose.example.yml 改名
├── Dockerfile
├── .dockerignore
├── entrypoint.sh
├── .env                  ← 环境变量（可选，密码放这里更安全）
├── app.py
├── auth.py
├── scheduler.py
├── api/
│   ├── __init__.py
│   ├── scan.py
│   ├── query.py
│   ├── download.py
│   ├── organize.py
│   ├── announce.py
│   ├── pending.py
│   ├── settings.py
│   └── stats.py
├── requirements.txt
├── main.py
├── pilotstd/             ← 从项目根目录复制整个 pilotstd/
├── web/dist/             ← 前端构建产物
├── data/                 ← 自动创建
├── logs/                 ← 自动创建
└── downloads/            ← 自动创建
```

> ⚠️ 如果 `web/dist/` 不存在，需要先在开发机上 `cd web && npm run build`，然后把 `web/dist/` 复制过去。

---

### 2.4 配置环境变量

在 `/volume1/docker/pilotstd/` 下创建 `.env` 文件：

```bash
# NAS 用户权限（SSH 进群晖执行 id -u 和 id -g 查看）
PUID=1026
PGID=100

# 路径
STANDARD_ROOT=/volume1/standards
SCAN_SOURCE=/volume1/media

# 安全（必改！）
ADMIN_PASSWORD=your_strong_password
JWT_SECRET=your_random_secret

# 时区
TZ=Asia/Shanghai
```

### 2.5 启动

> `docker-compose.example.yml` 中 `context: .` 表示 Dockerfile 与本文件在同一目录。

SSH 进入群晖或使用终端：
```bash
cd /volume1/docker/pilotstd
docker compose up -d
```

等待构建（首次约 3-5 分钟，取决于网络）。构建完成后：
```bash
docker compose logs -f   # 查看日志，按 Ctrl+C 退出
```

### 2.6 访问

浏览器打开 `http://<NAS-IP>:9028`，输入 `.env` 中设置的 `ADMIN_PASSWORD`。

---

## 三、首次使用（两种方式通用）

### 3.1 配置扫描源

登录后 → 设置 → 存储：

- 输出目录（标准库存放位置）：填入 `/standards`
- 扫描源目录：下拉选择 `/media`

### 3.2 手动扫描测试

首页 → [手动扫描] → 选 `/media` → 等待完成。

或左侧导航 → 扫描 → 选择路径 → 点击扫描。

### 3.3 设置定时任务

设置 → 定时任务：

| 任务 | cron | 开关 |
|------|------|:--:|
| 自动扫描 | `0 3 * * *`（每天凌晨3点） | 建议开启 |
| 自动查询 | `0 5 * * *`（每天凌晨5点） | 建议开启 |
| 自动公告 | `0 1 * * *`（每天凌晨1点） | 可选 |

开启后无需手动操作——标准库自动保持最新。

---

## 四、日常运维

### 4.1 查看日志

```bash
docker compose logs --tail=100 pilotstd
```

或在群晖 Container Manager → 容器 → pilotstd → 日志。

### 4.2 重启

```bash
cd /volume1/docker/pilotstd
docker compose restart
```

### 4.3 更新

```bash
cd /volume1/docker/pilotstd
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 4.4 备份

需备份的文件：
- `data/pilotstd.db` — SQLite 数据库（核心）
- `data/config.json` — 配置文件
- `.env` — 环境变量

```bash
# 在群晖上定期执行
cp /volume1/docker/pilotstd/data/pilotstd.db /volume1/backup/pilotstd_$(date +%Y%m%d).db
```

---

## 五、故障排查

### 无法访问 9028 端口

```bash
# 检查容器是否运行
docker compose ps
# 应显示 pilotstd Up

# 检查端口
netstat -tlnp | grep 9028
```

群晖可能拦截非标准端口。Container Manager → 容器 → pilotstd → 详情 → 端口设置 → 确认映射正确。

### 扫描不到文件

1. 确认 `SCAN_SOURCE` 的路径在 Docker 挂载中
2. 确认文件扩展名在设置→扫描→支持的扩展名列表中
3. 确认 `PUID`/`PGID` 和 NAS 文件权限一致

### 查询失败 / 网络超时

容器需要访问外部网站。确认群晖网络设置中 DNS 正常：
```bash
docker exec pilotstd ping -c 2 njbz365.cn
```

### 密码忘记

修改 `.env` 中的 `ADMIN_PASSWORD`，重启容器：
```bash
docker compose down && docker compose up -d
```

---

## 六、端口自定义

若 9028 被占用，修改端口映射。编辑 `docker-compose.yml`：
```yaml
ports:
  - "9028:9028"   # 改前面的数字即可，如 9999:9028
```
重启生效。访问 `http://<NAS-IP>:9999`。
