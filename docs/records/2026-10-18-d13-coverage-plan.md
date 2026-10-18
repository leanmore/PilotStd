# D-13 覆盖率补测计划（2026-10-18 排期）

> 结论：**今天开始，不再挂在 backlog**；不阻塞 v0.142.1 部署，覆盖补测与线上观察并行。
> 目标：把 `pilotstd/scan`、`docker/api` 从“函数级低覆盖”提升到可持续水平，
> 并用 CI 棘轮防止回退。

## 一、基线事实（实测）

| 范围 | 文件 | 函数数 | 当前已知 |
|---|---:|---:|---|
| `pilotstd/scan` | 17 | 73 | 行覆盖 **81.5%**（缺 46 行，2026-10-17 报告）；函数级 44% 为旧审计口径 |
| `docker/api` | 46 | 199 | 函数级 **43%**（85/196，2026-10-17 审计）；端点级零覆盖已清零 |
| 测试总量 | 410 个测试文件 | — | `tests/gui` 与部分 Windows 专属不在 CI backend |

> 注意：D-13 的“44%/43%”是静态口径（函数是否在 tests 中出现），不是 `coverage.py` 行覆盖；
> 第一阶段先统一为 `coverage.py` 可复现口径，避免继续拿两个口径混着说。

## 二、排期与工时

| 阶段 | 时间 | 工时 | 内容 | 验收 |
|---|---|---:|---|---|
| P0 基线 | 10/18（今天） | 3h | 跑 `--cov=pilotstd.scan --cov=docker.api`，产出“文件 × 行/函数”缺口表；脚本 `scripts/check_d13_coverage.py`（先 report-only） | 缺口表入 `docs/records/`，可复现 |
| P1 scan | 10/19–10/20 | 8h | 补 `watcher/edition_detect/lang_detect/filename_normalizer` + parser 边界（缺 46 行优先） | 行 ≥90%，函数 ≥80% |
| P2 api 核心 | 10/21–10/27 | 12h | `scan/query/download/archive/settings/system/tasks/notification*` 的错误分支与权限分支 | 函数 ≥55% |
| P3 api 其余 | 10/28–11/03 | 10h | 剩余模块按缺口排序，1–2 文件/批 | 函数 ≥70%，端点错误分支有覆盖 |
| P4 收口 | 11/04–11/05 | 3h | CI 棘轮切硬阈值；完成记录 | 回归即红灯，文档留痕 |
| **合计** | **约 3 周** | **约 36h** | 每批 1–2h，独立 `test(d13): ...` 提交 | — |

## 三、执行方式（防“又挂起来”）

1. **每周至少 2 个批次**，每批一个独立 commit（`test(d13): <模块> 覆盖`），提交信息附本批覆盖率增量。
2. 每批只补测试；若测试暴露产品缺陷，**单独** `fix(...)` 提交，不混在补测里。
3. 先按“缺行数/风险”排序，不按文件名字母序；高风险错误分支优先于纯工具函数。
4. CI 先 report-only；达到 P2/P3 阈值后切换为硬门禁，阈值只升不降。
5. 不在补测中改业务行为；需要 mock 的外部依赖统一放 `tests/conftest.py` 或本地 fixture。

## 四、第一批具体清单（P0/P1）

- P0：`coverage run` 全量 backend，生成 `docs/records/d13-baseline-<date>.md`；
  统计每个函数的 `executed/missed`，标出 0 命中函数。
- P1：`pilotstd/scan/watcher.py`（138 行）、`scanner.py`（165 行）、
  `edition_detect.py`（56 行）、`lang_detect.py`（29 行）、`filename_normalizer.py`（58 行）；
  重点：空目录、权限失败、异常编码、文件名边界、watcher 事件去抖。
- P1 完成后回填本文件“实际 vs 计划”差异表。

## 五、与部署的关系

- 本计划**不修改生产代码**（除非测试暴露缺陷，另行修复）；
- v0.142.1 可立即部署，线上观察一周与 P1/P2 并行；
- 若观察期发现需要回滚，补测分支不受影响。

## 六、完成定义（DoD）

- `pilotstd/scan`：行覆盖 ≥90%，函数 ≥80%；
- `docker/api`：函数 ≥70%，所有路由至少一个成功 + 一个失败/权限分支；
- CI `check_d13_coverage.py` 硬门禁生效；
- 本文档“实际 vs 计划”表填完，D-13 从长期项移入已收口记录。
