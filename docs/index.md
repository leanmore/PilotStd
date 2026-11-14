# PilotStd 文档索引

> **这是入口**：只列"动手前必读"的 13 份。
> 新人入门：见仓库根的新人入门入口；本索引不重复列 29 份 onboarding 文档。
> 开始任务前先跑 `python scripts/find_docs.py "<关键词>"`，再按命中结果读 1~3 篇。
> 工作流闸门与红线见 AGENTS；详细步骤见 onboarding/00。
> **找全部文档** → [`DOCUMENTATION_MAP.md`](DOCUMENTATION_MAP.md)（2026-11-10 活跃 **155 篇**；MAP 表为 2026-10-24 的 117 篇快照，待全量重建）；
> **看接下来做什么、什么时候做** → [`ROADMAP.md`](ROADMAP.md)。

## 治理文档（docs/governance/）

| 文件 | 内容 | 触发条件 |
|------|------|----------|
| `gates.md` | 门禁规则 G-005~G-054 完整清单 | 涉及门禁配置变更 |

## 参考文档（docs/reference/）

| 文件 | 内容 | 触发条件 |
|------|------|----------|
| `announcement-pipeline.md` | 公告解析入库流程、状态机、字段规范 | 涉及公告解析/入库 |
| `download-pipeline.md` | openstd 下载流程：hcno 权威来源、端点族 `/bzgk/std/*`、完整步骤链、历史事故、防回归测试 | 涉及下载链/下载适配器 |
| `announcement-sources.md` | 公告来源标识映射表 | 涉及公告来源判断 |
| `ui-components.md` | 前端组件规范、状态展示、布局原则 | 涉及前端 UI |
| `coding-standards.md` | Python/TS 编码规范详细版 | 编写新代码时 |
| `pre-commit-checklist.md` | 提交前自检命令清单 | 提交代码前 |
| `health-check.md` | `/api/health` 状态码（200/207/500）、磁盘/调度器心跳/数据库读写指标 | 涉及健康检查/部署排障 |
| `adapter-development.md` | 适配器开发指南、站点架构差异表 | 开发新适配器时 |

## 架构文档

| 文件 | 内容 | 触发条件 |
|------|------|----------|
| `architecture.md` | 架构决策与跨模块契约（Handler/公告模型/回调/状态契约） | 涉及数据库/Schema |
| `ci-lessons.md` | CI/CD 踩坑记录与最佳实践 | 涉及 CI/CD 或门禁 |

## 决策与债务

| 文件 | 内容 | 触发条件 |
|------|------|----------|
| `adr/` | 架构决策记录 | 涉及架构决策 |
| `technical-debt.md` | 技术债登记表 | 涉及技术债 |
| `DECISIONS.md` | 决策记录：决策/理由/被否决方案（唯一真相） | 查历史决策或改判时 |

## 规划

| 文件 | 内容 | 触发条件 |
|------|------|----------|
| `ROADMAP.md` | 路线图：已排期事项、里程碑、未排期清单 | 不确定下一步做什么 / 查排期 |
