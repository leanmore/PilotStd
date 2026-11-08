# 通知系统设计（索引）

> 本文是索引页。通知系统设计的 9 份原文已归档；本页不重复设计内容，只做导航。
> 后续若需合并为一篇完整设计文档，另立任务（见文末）。

## 一、决策结论（唯一权威）

- 决策记录：`docs/DECISIONS.md`（D-01～D-18，通知架构相关）
- 实现摘要：`docs/reference/implementation-digest.md`
- 通知事件字典：`docs/notification_event_dictionary.md`
- 通知覆盖度基线：`docs/governance/notification_coverage.md`

## 二、设计原文（已归档）

归档目录：`docs/.local/archive/2026-11-08/docs/plans/`（保持原相对路径，便于按原文件名检索）

| 系列 | 文件（归档相对路径） | 原始主题 |
|---|---|---|
| redesign | `notification-redesign/00-README.md` | 索引 + 结论速览 + 裁决 |
| redesign | `notification-redesign/02-目标架构.md` | 三层分离、消息模型 +12 字段、Task 模型、渠道能力矩阵 |
| redesign | `notification-redesign/03-实施路径.md` | 六阶段、NOTIFY_REDESIGN_STAGE 一键回滚 |
| system-design | `notification-system-design/00-framework.md` | 36 个用户时刻、11 项待裁决 |
| system-design | `notification-system-design/02-framework-update.md` | 裁决录入、分档策略、阶段 3 重定义 |
| system-design | `notification-system-design/06-spec-and-phasing.md` | SSOT 16 字段、通道 11→2、三步收敛 |
| system-design | `notification-system-design/07-impl-design-A.md` | channel_spec / FieldSpec 字段清单、G-045 校验 |
| system-design | `notification-system-design/08-统筹日程.md` | 依赖图、关键路径、逐项待办 |
| 独立稿 | `notification-refactor-design.md` | i18n / 模板 / 文案 / 覆盖度 / 聚合 五痛点 |

> 采用“保持原相对路径”而非扁平化：`docs/governance/gates.md` 等既有文档按原文件名引用 `notification-refactor-design.md`，扁平化会让 G-032 交叉引用检查产生新增 warning。

## 三、后续合并计划（未执行）

- 当前状态：只归档，未合并
- 触发条件：有维护窗口时，另立任务以 `notification-redesign/02-目标架构.md` 为底稿合并为本文
- 合并时需处理的差异：三套系列的口径冲突（以 `docs/DECISIONS.md` 与 `docs/records/2026-10-24-notification-phase2-decisions.md` 为裁决依据）

## 四、边界说明

- 本页不承载设计细节；任何设计细节以归档原文为准
- 本页不承诺合并时间；合并前，9 份原文是唯一设计依据
