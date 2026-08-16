# 轮转日志访问端点 — spec-lite

## 用户指令摘要

在 docker/api/logs.py 新增两个只读端点：`GET /api/logs/rotated`（列出轮转日志文件）和 `GET /api/logs/rotated/{filename}`（分页+搜索读取内容），解决当前只能读 app.log、无法访问 app.log.1~10 轮转文件的问题。

## 采纳的关键设计决策

1. 文件名白名单正则 `^app\.log(\.\d+)?$`，不匹配直接 400，杜绝路径遍历。
2. realpath 校验：拼接路径后 `os.path.realpath` 必须落在日志目录内，否则 403。
3. 鉴权复用 `@require_role("admin")`，与现有 /api/logs 一致。
4. 列表端点结果缓存 60 秒，lines_estimate 用文件大小/平均行长估算（不实际计数）。
5. 内容读取流式逐行（无 grep 纯分页；有 grep 用 deque 滑动窗口取前后 context），不整文件载入。

## 识别到的风险点及与现有架构的冲突

1. `_get_log_dir()` 开发环境返回 `<项目根>/logs`，测试需 monkeypatch 到临时目录。
2. 正则 `^app\.log(\.\d+)?$` 会匹配当前 app.log（非轮转），列表端点需决定是否排除当前文件。
3. grep+context 与 offset/limit 的语义叠加需明确（结果集再切分）。
4. RotatingFileHandler backupCount=10，轮转文件名固定 app.log.N。

## 验证方式

- pytest 新测试文件 tests/test_logs_rotated.py，覆盖：列表、分页、grep+context、非法文件名 400/403、未鉴权 403、空文件/不存在。
- 现有 /api/logs 测试无回归。
- 跑门禁 ruff/mypy。
