# CloakBrowser Key 申请教程

> 适用：PilotStd Docker 部署，`cloakbrowser==0.7.1`。  
> 用途：可信 IP 自动更新。没有 key 不影响系统其它功能，只影响该功能。

## 1. Key 是什么

CloakBrowser 从 0.7 开始，每次启动浏览器都需要一个 license key。

- 免费 key：一个邮箱申请，默认 **1 个并发会话**；
- 付费 key：多并发/更高额度；
- key 不是 PilotStd 的 API Key，也不是 `pst_` 开头的系统令牌；
- key 只用于 CloakBrowser，不需要发给别人。

## 2. 申请免费 Key

1. 打开官方免费申请页：

   <https://cloakbrowser.dev/free>

2. 输入你的邮箱；
3. 按页面提示确认邮箱；
4. 页面或邮件会给出一个 key，通常以 `cb_` 开头；
5. 复制保存，不要截图发群、不要提交到 Git。

> 如果页面打不开，也可以在有终端的机器上运行：
>
> ```bash
> python -m cloakbrowser login
> ```
>
> 按提示用邮箱获取 key。

## 3. 填到 PilotStd 的 `.env`

在 NAS 的 `.env` 文件里增加一行：

```text
CLOAKBROWSER_LICENSE_KEY=cb_你的key
```

注意：

- 等号两边不要加空格；
- 不要加引号；
- 不要把 `.env` 提交到 Git；
- 不要把 key 写进 `docker-compose.yml` 或代码。

## 4. 重建并启动容器

```bash
docker compose build --no-cache
docker compose up -d
```

容器启动时会：

1. 检查 `/app/data/cloakbrowser`；
2. 如果没有内核，执行 `python -m cloakbrowser install`；
3. 首次下载约 200MB，需要 NAS 能访问外网；
4. 安装失败只告警，不阻止主服务启动；首次使用时会再报错并通知。

## 5. 验证 Key 是否生效

进入容器：

```bash
docker exec -it pilotstd python -m cloakbrowser info
```

重点看：

- `License tier` 不是 `none`；
- `Binary installed` 为可用；
- 没有 `invalid` / `expired` 提示。

也可以看启动日志：

```bash
docker logs pilotstd 2>&1 | grep -i cloakbrowser
```

正常会看到类似：

```text
[INFO] 检查 CloakBrowser 内核: /app/data/cloakbrowser
[INFO] CloakBrowser 内核已就绪
```

## 6. 常见错误

| 现象 | 原因 | 处理 |
|---|---|---|
| `CLOAKBROWSER_LICENSE_KEY 未设置` | `.env` 没填或没重启 | 填 key 后重建/重启 |
| `invalid license` | key 复制错/失效 | 重新申请或检查是否多复制字符 |
| `session limit reached` | 免费 key 同时开了多个会话 | 关闭其它 CloakBrowser 进程，或升级 key |
| `kernel is not installed` | 首次下载失败/无外网 | 看日志，手动执行 `python -m cloakbrowser install` |
| `license server unreachable` | NAS 访问不了 license 服务 | 检查 DNS/代理；稍后重试 |
| 首次使用很慢 | 正在下载约 200MB 内核 | 等待，或提前在启动阶段装好 |

## 7. 安全建议

- key 只放在 `.env`，不要写进仓库；
- 不要截图 key 发到公开群；
- 多人共用一套部署时，建议用独立的 key；
- 如果 key 泄漏，去 CloakBrowser 后台/重新登录轮换；
- `./data/cloakbrowser` 是内核缓存，不是 key 文件，但也不要随意公开。

## 8. 相关配置

```text
CLOAKBROWSER_LICENSE_KEY=cb_xxx
CLOAKBROWSER_CACHE_DIR=/app/data/cloakbrowser
```

- `CLOAKBROWSER_CACHE_DIR` 默认就是 `/app/data/cloakbrowser`；
- 缓存在 `./data` 卷内，备份 `data` 时会一起保留；
- 删除该目录后，下次启动会重新下载内核。
