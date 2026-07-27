# 系统配置说明

> 最后更新：2026-07-27

## config.json 完整 Schema [src: `pilotstd/core/config/defaults.py:6-108`]

配置文件路径：`{DATA_DIR}/config.json`（点分隔 JSON，由 [pilotstd/core/config/manager.py](pilotstd/core/config/manager.py) 管理）

### 存储配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `storage.root_dir` | string | `~/标准` | 标准库根目录 |
| `storage.expire_folder` | string | `过期作废` | 过期标准文件夹名 |
| `storage.inbox_dir` | string | `/inbox` | 下载暂存目录 |
| `storage.mirror_skipped_dirs` | bool | true | 镜像跳过的目录结构 |

### 扫描配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `scan.extensions` | list | `[.pdf,.doc,.docx,.txt]` | 支持的文件扩展名 |
| `scan.skip_folders` | list | 6项 | 跳过的文件夹名 |
| `scan.exclude_patterns` | list | 6项 | 文件名排除关键词 |

### 查询配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query.site_order` | list | `[]` | 用户自定义适配器优先级 |
| `query.use_cache` | bool | true | 启用查询结果缓存 |
| `network.proxy` | string | `""` | HTTP 代理地址 |
| `network.timeout` | int | 30 | 网络请求超时(秒) |

### 公告配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `announcement.enabled` | bool | false | 启用公告自动抓取 |
| `query.announcement_url` | string | `http://localhost:9028` | 公告 API 地址 |
| `query.announcement_api_key` | string | `""` | 公告 API 密钥 |

### 时效性检查配置 [src: `defaults.py:92-102`]

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `validity.first_weekday` | int | 1 | 首次执行周几(1=周一, 7=周日) |
| `validity.execute_time` | string | `"03:00"` | 执行时间(HH:MM) |
| `validity.total_weeks` | int | 4 | 总周期(周), ≥4 |
| `validity.frequency_weeks` | int | 1 | 执行频率(周), ≥1 |
| `validity.batch_size` | int | 50 | 单批大小(条/批) |
| `validity.batch_interval` | int | 5 | 批间隔(秒) |
| `validity.check_ratio` | int | 25 | 检查比例(%) |

### 执行联动公式

```
execution_count = total_weeks / frequency_weeks  # 必须 >= 4
coverage_per_execution = 100 / execution_count    # 每次覆盖 %
interval_days = (total_weeks * 7) / execution_count

# 示例：total_weeks=4, frequency_weeks=1
# → 4 次执行，每次覆盖 25%，间隔 7 天
```

**前后端双重校验**：execution_count < 4 时前端保存按钮禁用 + API 返回 400。

### 适配器熔断配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `adapter.circuit_breaker.failure_threshold` | int | 3 | 连续错误触发熔断 |
| `adapter.circuit_breaker.freeze_durations` | list | `[30,120,360,720]` | 四次渐进式冻结(min) |
| `adapter.circuit_breaker.reset_window_hours` | int | 24 | 统计窗口(小时) |

### 通知配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `notification.enabled` | bool | false | 全局通知开关 |
| `notification.log_retention_days` | int | 30 | 日志保留天数 |
| `notification.aggregate_enabled` | bool | true | 同类消息合并 |
| `notification.aggregate_window_seconds` | int | 5 | 合并窗口(秒) |
| `notification.quiet_hours_enabled` | bool | false | 静音时段开关 |
| `notification.quiet_hours_start` | string | `"22:00"` | 静音开始 |
| `notification.quiet_hours_end` | string | `"07:00"` | 静音结束 |

## 环境变量

| 变量名 | 作用 | 必填 | 默认值 | 覆盖优先级 |
|--------|------|------|--------|-----------|
| `DATA_DIR` | 数据目录 | 否 | `/app/data` | > config.json 路径前缀 |
| `ARCHIVE_COOLDOWN_DAYS` | 归档冷却期 | 否 | 28 | 直接使用，不经过 config.json |
| `ARCHIVE_MAX_RETRIES` | 最大重试次数 | 否 | 7 | 直接使用 |

> **注意**：适配器配额不支持环境变量覆盖。配额通过 Web API `PUT /api/settings/sites/{name}` [src: `docker/api/settings.py:188-234`] 热更新。

## 适配器配额配置

默认值定义在 [src: `pilotstd/query/site_config.py:8-87`]，每个站点三项可配参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_requests` | 200 | 每轮冷却前最大请求数 |
| `daily_limit` | 800 | 每日最大请求数（次日 00:00 重置） |
| `cooldown_seconds` | 600 | 冷却时长(秒) |

**调整方法**：
1. 通过 API：`PUT /api/settings/sites/{name}` JSON body: `{"daily_limit": 1000, "cooldown_seconds": 300}`
2. 编辑 `config.json`：`"query.sites.{name}.daily_limit"` 路径

**生效时机**：API 调用后立即热生效（`SiteRotator._sites` 内存更新 + 持久化）。无需重启。

**特殊站点配额**：

| 站点 | daily_limit | max_requests | cooldown | 备注 |
|------|-------------|-------------|----------|------|
| csres | 200 | 50 | 600s + 24h硬冷 | 最低日配额 |
| energy | 100 | 30 | 2s | 纯IP站点，配额最低 |
| cssn | 1000 | 100 | 1s | 日配额最高 |
| jjg | 1000 | 100 | 1s | 配额最高 |
