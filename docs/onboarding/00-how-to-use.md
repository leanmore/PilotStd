# 00 · 怎么用这套认知文档

> 目标：不靠“记忆”，靠**入口 + 路由 + 检索**。  
> 这套文档不是让模型一次背完，而是让每次任务都能快速找到依据。

---

## 一、开始任何非 trivial 任务前，走三步

### 第一步：先看入口

读 [`README.md`](README.md) 的文档地图，知道这次问题大概属于哪一类。

### 第二步：按关键词检索

```bash
python scripts/find_docs.py "通知 未读 聚合"
python scripts/find_docs.py "monitor 空目录 归档"
python scripts/find_docs.py "validity 畸形键 过期"
```

脚本会返回最相关的 1~8 篇文档和命中的标题，不读取代码、不联网、不修改文件。

### 第三步：在分析/修复前引用依据

至少打开命中结果中的 1~3 篇，确认：

- 这是设计边界，还是缺口；
- 有没有已知修复记录；
- 有没有对应测试/迁移/部署限制。

交付时写明：

```text
已查阅：docs/onboarding/26-fix-dossiers.md（D-04）、08-known-boundaries.md（#17）
```

---

## 二、按问题类型查文档

| 你遇到的是 | 先读 |
|---|---|
| 新人整体了解项目 | [`README.md`](README.md)、[`01-positioning.md`](01-positioning.md) |
| 文件从进来到归档的完整路径 | [`02-file-journey.md`](02-file-journey.md) |
| Web / Win / CLI / Docker 的架构差异 | [`03-architecture.md`](03-architecture.md)、[`19-web-win-inventory.md`](19-web-win-inventory.md) |
| 数据库表、字段、迁移 | [`04-data-model.md`](04-data-model.md)、[`18-schema-migrations.md`](18-schema-migrations.md) |
| 不知道代码从哪看起 | [`05-code-map.md`](05-code-map.md) |
| 部署、健康检查、备份、回滚 | [`06-runtime-ops.md`](06-runtime-ops.md)、[`28-a-completion-and-deploy.md`](28-a-completion-and-deploy.md) |
| 提交、CI、门禁、四件套 | [`07-dev-workflow.md`](07-dev-workflow.md) |
| 这是不是 bug / 当前边界 | [`08-known-boundaries.md`](08-known-boundaries.md) |
| 有效性、过期、废止、检查队列 | [`17-validity-state-machine.md`](17-validity-state-machine.md)、[`12-data-repair-plan.md`](12-data-repair-plan.md) |
| 查询适配器、站点差异、hcno | [`15-query-adapter-matrix.md`](15-query-adapter-matrix.md)、[`03-architecture.md`](03-architecture.md) |
| 通知事件、渠道、聚合、未读数 | [`16-notification-matrix.md`](16-notification-matrix.md)、[`21-notification-builders.md`](21-notification-builders.md) |
| Web / Win 的按钮和动作 | [`24-ui-action-matrix.md`](24-ui-action-matrix.md) |
| 公告抓取、解析、OCR | [`22-announcement-deep-dive.md`](22-announcement-deep-dive.md) |
| 收藏、待确认、任务、上传、导出 | [`23-peripheral-features.md`](23-peripheral-features.md) |
| 某个问题修到哪一步了 | [`25-fix-readiness.md`](25-fix-readiness.md)、[`26-fix-dossiers.md`](26-fix-dossiers.md) |
| 最近改了什么、怎么回滚 | [`27-implementation-log.md`](27-implementation-log.md) |
| 术语看不懂 | [`glossary.md`](glossary.md) |

---

## 三、几条不要违反的用法

1. **不要只搜代码，不查台账**：代码只回答“现在怎么跑”，文档回答“为什么这样、哪里不能动”。
2. **不要把所有文档一次性塞进上下文**：先检索，再精读命中的 1~3 篇。
3. **不要把“当前边界”当 bug 修**：先看 `08-known-boundaries.md` 的类型列。
4. **不要把“修过”当“已部署”**：部署状态一律看 `/api/health` 的 version / schema_version。
5. **修完必须回写**：实现记录写 `27`，边界状态写 `08`，dossier 状态写 `26`。

---

## 四、一句话

> 不靠模型“记得”，靠仓库里**固定的入口、检索脚本、引用习惯**。
