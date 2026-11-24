# 三方向最终状态与交接（2026-11-25）

> 本文档回答一个问题：**现在还剩什么、卡在谁身上、怎么继续**。
> 依据均为仓库内可核对的事实（文件、门禁、CI），不依赖对话记忆。

---

## 一、方向 A：微交互全量统一 —— ✅ 完成

| 验收点 | 证据 |
|---|---|
| `AppToast` 统一封装 | `web/src/composables/useAppToast.ts`；全站 **20 个文件 / 49 处**调用，无裸 `toast.add(...)` 残留 |
| `AppLoading`（含骨架屏） | `web/src/components/ui/AppLoading.vue`；**10 个文件**使用（skeleton variant 用于表格/卡片首屏） |
| 门禁升 error | `web/eslint.config.js`：`custom/no-raw-toast: 'error'`、`custom/no-raw-table: 'error'`（测试/生成目录显式关闭） |
| 页面过渡动画 | 统一于 `web/src/styles/` 的 `--transition` 令牌与 `PageContainer` 过渡 |
| 验证 | 前端四件套全绿（149 文件 / 1284 例；覆盖率 lines **85.98%**） |

## 二、方向 B：部署验证包圆 —— ✅ 完成

| 验收点 | 证据 |
|---|---|
| 只读探测脚本 | `scripts/ops/`：`probe_all.py`（一键全量）、`probe_batch1.py`、`probe_pending_paths.py`（mark_missing 路径）、`probe_credentials.py`（飞书/企微凭证）、`probe_db_counts.py`（统计表对账）、`probe_health.py`、`_probe_common.py` |
| 一键自检指南 | `docs/ops/deploy-selfcheck.md`（275 行：5 分钟上手 / 退出码三档 / 必跑项 / 只读保证 / 失败排查 / 人工验收清单 11 项 / 写库迁移需授权） |
| 实测记录 | 同文档 §九：2026-11-23 对 `http://192.168.1.18:9028` 实测；批次 1 = 10 通过 / 0 失败 |
| 只读保证 | 全部探测仅 GET/HEAD；写库迁移单列为「需授权」章节 |

## 三、方向 C：技术债全量清算 —— 68/106（38 项外部阻塞）

### 3.1 已完成（可核对）
- 8 个批次中 **8 批均已推进**：批次 8「资源泄漏 + 测试」11/11 ✅（含本轮 NEW-44 归零）。
- **NEW-44 前端测试缺口归零**：84 → 0（补 55 文件 / 344 例；余 9 个文件为纯类型 ×5、独立 node-test 运行器 ×1、测试基建 ×3，已在清单注明理由）。
- 棘轮收紧（本轮）：G-050 静默吞错基线 **191 → 179**；G-010 警告档 `_organize.py` 446→436；
  web 覆盖率阈值 **lines 48.07→85.5 / stmts 44.11→83.2 / branch 32.12→75.3 / funcs 23.42→73.2**；
  G-054 单文件基线 `taskPipeline.ts` 87.5→100。

### 3.2 剩余 38 项按阻塞类型（**都不是"没做"，是"做不了"**）

| 类型 | 数量 | 阻塞在哪 | 解除条件 |
|---|---|---|---|
| 人工验收 | 22 | 需在浏览器/真实环境点开确认（清单在 `docs/ops/deploy-selfcheck.md` §七-A） | 你或运维执行 11 项人工验收 |
| 生产库写操作 | 3（G-28/33/35） | 红线：不得未经授权 UPDATE 生产库 | 维护窗口 + 授权（runbook 已给） |
| 部署后取数 | 3（G-03/A-40/A-46） | 依赖新镜像上线后的真实数据 | PR 合并 → 部署 → 取数 |
| 产品决策 | 1（A-52） | 视觉收敛方向需产品确认 | 你拍板 |
| 触发型终态 | 9（批次 4） | 已确认「等触发再处理」，无当前动作 | 事件触发时 |

### 3.3 关键卡点：**代码都在分支上，不在生产**

- 分支 `feat/debt-cleanup-round2` 领先 `main` **41 个提交**，CI 全绿；
- 部署实例 `/api/health` 仍为 `0e92e5d2`（上次合并）；
- 也就是说：方向 A/B/C 的**全部改动、P2 的 5 个适配器修复、web 的 12 个缺陷修复**都还没进生产。

## 四、附加任务包（P2）状态

| 项 | 状态 |
|---|---|
| 重庆 `cqis` 适配器（DB50 权威 + 全文 PDF） | ✅ `df6f6a7c` |
| API Webstore 适配器（Coveo + token 自愈） | ✅ `2f84d1ce` |
| ASME 适配器（designator 归一化） | ✅ `d820298c` |
| ttbz 按号查询恒 0 条（**生产级缺陷**） | ✅ `f140ad49` |
| energy 三处结构缺陷 | ✅ `f140ad49` |
| 福建标准信息网 | ⛔ BLOCKED（站点全端口 TCP 过滤，ICMP 通；需网络放开后复测） |
| 路由「注册了但不可达」系统性缺陷 | ✅ `64a6a2f2`（`T/` / `NB/T` / 14+ 斜杠变体） |

**P2 额外产出**：新增/修好 **7 个数据源**（cqis / api_webstore / asme / ttbz / energy + 路由修复让既有站点可达）。

## 五、下一步（按依赖排序）

1. **合并 PR #27**（唯一解锁项）：合并 → CI 构建镜像 → 你拉取重启 → 跑 `python scripts/ops/probe_all.py` 完成验收。
2. **维护窗口**：跑 C3 状态枚举归一 + 存量清洗（runbook 见 `docs/ops/deploy-selfcheck.md` §七-B）。
3. **人工验收 11 项**（清单 §七-A）。
4. 产品决策：A-52 视觉收敛、C2 状态三分类口径、P2 省份粒度路由、POST 检索口径。

## 六、如何自证（不信任本文档时）

```bash
# 门禁全量
bash scripts/check_all.sh --fast --guards --local
# 前端四件套
cd web && pnpm.cmd run type-check && pnpm.cmd run lint && pnpm.cmd test && pnpm.cmd run build
# 后端全量
python -m pytest tests -q
# 部署自检（需新镜像上线后）
python scripts/ops/probe_all.py
```
