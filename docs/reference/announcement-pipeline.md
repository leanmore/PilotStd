# 公告解析入库流程

## 流程概览

| 阶段 | 输入 | 处理 | 输出 |
|------|------|------|------|
| 采集 | 原始公告文件（PDF/DOCX） | 文件监控服务检测新文件 | 文件路径入队 |
| 解析 | 文件路径 | Parser 提取正文、元数据 | 结构化数据 |
| 清洗 | 结构化数据 | Service 层状态机处理 | 清洗后数据 |
| 入库 | 清洗后数据 | 写入 SQLite | announcement_record 记录 |

## 状态机流转

| 当前状态 | 触发事件 | 目标状态 | 说明 |
|----------|----------|----------|------|
| pending | 文件检测 | parsing | 开始解析 |
| parsing | 解析成功 | parsed | 正文提取完成 |
| parsing | 解析失败 | failed | 记录错误日志 |
| parsed | 清洗完成 | cleaned | Service 层处理完毕 |
| failed | 重试 | parsing | 重新解析 |

## 关键字段规范

| 字段 | 类型 | 说明 |
|------|------|------|
| source_type | TEXT | 来源标识，映射表见 `announcement-sources.md` |
| parse_status | TEXT | pending / parsing / parsed / cleaned / failed |
| row_index | INTEGER | 原始文件中的行号索引 |
| created_at | TEXT | ISO 8601 格式 |
| updated_at | TEXT | ISO 8601 格式，每次更新自动刷新 |

## 约束

- Parser 层只做正文提取，禁止包含业务逻辑
- 清洗逻辑统一在 Service 层的状态机中完成
- 日期字段必须使用 ISO 8601 格式，禁止使用其他格式
