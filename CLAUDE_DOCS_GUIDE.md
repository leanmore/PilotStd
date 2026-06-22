# 文档联动更新规则（强制）

本文件定义 Claude Code 执行任务时必须同步更新的治理文档。

## 更新触发映射表
| 当执行... | 必须更新... | 更新方式 |
|---|---|---|
| 修改代码 / 修复 Bug | `STATUS.md` | 更新“当前状态”和“最后操作”章节 |
| 新增/修改压测用例 | `capabilities_registry.md` | 在对应模块下新增/修改条目 |
| 修改迁移/重构流程 | `archive_migration_protocol.md` | 同步更新步骤描述 |
| 完成一个里程碑任务 | `ANNOUNCEMENT.txt` | 追加一行更新日志 |
| 项目根路径/启动方式变化 | `README.md` | 更新“快速开始”或“部署”章节 |
| 完成一轮重构 | `refactoring_checklist.md` | 勾选对应的完成项 |

## 执行流程
1. 开始任务前：读取 `STATUS.md`（恢复上下文）
2. 任务执行中：按需查询 `capabilities_registry.md` 或 `archive_migration_protocol.md`
3. 任务完成后：根据上表更新对应文档，并向决策者报告变更摘要