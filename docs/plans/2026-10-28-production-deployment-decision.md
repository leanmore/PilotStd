# 生产部署决策页（2026-10-28）

> **用途**：给用户一次看清"部署什么版本、风险、不部署的已知 bug、怎么回滚"。
> **结论未定**：部署是用户的决定，本页只提供依据。

## 一、候选版本

- **最低包含**：`de8a689c`（A-20 静音时段修复 + `/test` level 白名单）；建议取部署时 `main` HEAD（含后续 docs 提交，不影响运行时）。
- **当前生产/验证环境**：`140ad243`（v0.151.3，旧 urllib 实现）→ 验证环境已单独升到 `9db6842c`（仅验证用）。
- **构建要求**：`docker build --build-arg APP_VERSION=$(git rev-parse --short HEAD)`；否则 `/api/health` 显示 `unknown`。

## 二、这批改动包含什么

| 提交 | 内容 | 风险等级 |
|---|---|---|
| `256ef97e` / `f24cae3f` / `806f3d3f` | 通知三渠道 urllib → requests（telegram/dingtalk/feishu） | 中：仅在真实发送路径；已验证 telegram，dingtalk/feishu 待凭证 |
| `1c536ee0` | 无 blocks 消息的 MarkdownV2 转义修复（A-17） | 低：修复 400 失败 |
| `915b3f0f` 等 | A-16 路径类型守卫（防垃圾目录） | 低 |
| `9ab006ff` / `70c3725a` | 解析失败日志四段化（A-9） | 低：仅日志格式 |
| `05ae773d` | 设置页 Tab data-tab（A-10） | 低：前端定位方式 |
| `7bde4efb` | 静音时段写服务端 config（A-20） | 低：新增端点；全局语义 |
| `de8a689c` | `/api/notification/test` 支持 `level`（仅 info/warning） | 低：新增可选字段，默认行为不变 |

## 三、风险与回滚

| 风险 | 说明 | 回滚 |
|---|---|---|
| requests 迁移行为差异 | 超时语义/编码/重定向细节与 urllib 不同；telegram 已真实发送验证，dingtalk/feishu 未验证 | 回退镜像到 `140ad243`；数据卷 `./data`/`./logs` 不受影响 |
| 新端点写 config.json | `PUT /api/notification/quiet-hours` 会改全局静音配置 | 回退镜像即可；config 值可手工恢复 |
| 全局静音语义 | 当前实现是**全局**静音，不是按用户（A-21 立项） | 无数据迁移，改回开关即恢复 |

**回滚命令**：把 `docker-compose.verify.yml` 的 image 指回旧 tag，`docker compose ... up -d --no-build --force-recreate`；或直接 `docker run` 旧镜像。

## 四、不部署的已知 bug

1. **A-17（已在候选版修复）**：无 blocks 消息含 `.`/括号时 Telegram 返回 400，影响"测试发送"和聚合兜底；旧版本表现为 `{"ok":false,"error":"投递失败"}`。
2. **A-20（已在候选版修复）**：UI 静音时段开关不生效（只写用户偏好，服务端读 config.json）。
3. 其余债务（A-18/A-19/A-21/A-22 等）不影响运行时正确性。

## 五、部署步骤

```bash
git pull
git log --oneline -1                      # 确认包含 7bde4efb
docker build -f docker/Dockerfile \
  --build-arg APP_VERSION=$(git rev-parse --short HEAD) \
  -t pilotstd:deploy-$(git rev-parse --short HEAD) .
cat > docker-compose.verify.yml <<EOF
services:
  pilotstd:
    image: pilotstd:deploy-$(git rev-parse --short HEAD)
EOF
docker compose -f docker-compose.yml -f docker-compose.verify.yml up -d --no-build --force-recreate
curl -s http://127.0.0.1:9028/api/health
```

## 六、选项与建议

| 选项 | 代价 | 建议 |
|---|---|---|
| A. 现在部署候选版 | 一次重启；dingtalk/feishu 未真实验证 | 可接受，风险主要在未验证渠道 |
| B. 等 S5 发版（minor）一起 | 多等一轮；S5 依赖 S4 验收 | **推荐**：发版流程自带回归与版本号 |
| C. 暂不部署 | 保留 A-17/A-20 已知缺陷 | 仅当近期不用通知测试发送/静音时可行 |

**选定（2026-10-28）：B** —— 随 S5 发版一起部署。理由：避免两次重启；S5 自带回归门槛；Q7 仍挂起，但作为"已知未验项"写入发版说明，不阻塞部署；Q6 数据层已验，N1 待用户配置窗口。

## 七、部署事实（2026-10-28）
- 验证环境已部署 `9c23a940`（CI bump v0.154.0；包含 A-20、level 白名单与 `test-event`）。
- `/api/health` version 与 tag 一致；`b72b3415:CHANGELOG.md` 已含 v0.153.0（CI 自动生成）。CI 证据：`0cf16f34` 的 run **13/13 success**；`b72b3415` 只是版本 bump（仅 CHANGELOG/VERSION/__init__.py，7 行）⇒ 代码等价于 13/13 的构建。

## 八、验证环境部署核验（2026-10-29，`0e09e030`）
- `quiet_hours` 只读字段：`enabled=false, start=22:00, end=07:00`（接口实测）✅
- A-26 当日查询：`start=end=2026-10-29` 返回 57 条 ✅
- P-11 前端修复：设置页静音显示「未启用」，与服务端一致 ✅
- F-6 文案：提交 `d3da3dc8` 已在镜像内（ancestry 通过）；触发需改密码，**未做运行时触发**，以本地构建器渲染为据。
