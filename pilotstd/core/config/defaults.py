# 模块：项目/核心/配置/脚本
# 出厂默认值常量—从配置脚本拆分

import os

from pilotstd.core.notification.event_spec import EVENT_SPECS

FACTORY_DEFAULTS = {
    "appearance.theme": "经典白",
    "appearance.language": "zh_CN",
    "appearance.column_visibility": [True] * 9,
    "appearance.icon_theme": "default",
    "appearance.skip_welcome": False,
    "appearance.hyphen_style": True,
    "storage.root_dir": os.path.expanduser("~/标准"),
    "storage.expire_folder": "过期作废",
    "storage.downloads_dir": None,
    "storage.inbox_dir": "/inbox",
    "storage.mirror_skipped_dirs": True,
    "storage.mirror_fallback": True,
    "organize.auto_clean_source": False,
    "network.proxy": "",
    "network.ua_rotation": True,
    "network.timeout": 30,
    "query.site_order": [],
    "query.use_cache": True,
    "query.use_announcement_match": False,
    "query.announcement_url": "http://localhost:9028",
    "query.announcement_api_key": "",
    "scan.skip_folders": [
        "过期作废",
        "征求意见稿",
        "培训课件",
        "建设项目过程资料及交工资料标准",
        "吊车性能",
        "标准图集",
    ],
    "scan.exclude_patterns": [
        "征求意见稿",
        "培训课件",
        "建设项目过程资料及交工资料标准",
        "吊车性能",
        "标准图集",
    ],
    "scan.extensions": [".pdf", ".doc", ".docx", ".txt"],
    "announcement.enabled": False,
    "ocr.provider": "",
    "ocr.baidu_api_key": "",
    "ocr.baidu_secret_key": "",
    "ocr.tencent_secret_id": "",
    "ocr.tencent_secret_key": "",
    "ocr.aliyun_access_key_id": "",
    "ocr.aliyun_access_key_secret": "",
    "file.clear_readonly": True,
    "watchdog.enabled": False,
    "notification.enabled": False,
    # W2 分流开关：桌面端是否把业务事件弹成托盘气泡（关闭即回退到"本端无可见信号"）
    "notification.windows_tray_events": True,
    # W3 分档节流开关：托盘事件是否遵守"长阶段 60 秒/主题"（关闭即回退为不节流）
    "notification.windows_tray_throttle": True,
    "notification.channels.wechat.enabled": True,
    "notification.channels.wechat.webhook_url": "",
    "notification.channels.telegram.enabled": False,
    "notification.channels.telegram.bot_token": "",
    "notification.channels.telegram.chat_id": "",
    "notification.channels.feishu.enabled": False,
    "notification.channels.feishu.webhook_url": "",
    # 通知订阅规则由**事件规格派生**（2026-10-03 步 B 第三步）：键集等于带默认渠道的事件；
    # 其中「收藏告终汇总」与「通知投递失败告警」两项为最高优先级
    # （终态告终提示 / 通知系统自身故障的唯一出口）。
    **{f"notification.rules.{s.key}": list(s.default_channels) for s in EVENT_SPECS if s.default_channels},
    # 通知日志清理
    "notification.log_retention_days": 30,
    "notification.log_cleanup_interval_hours": 24,
    # 服务端聚合（同类消息合并，防通知刷屏）
    "notification.aggregate_enabled": True,
    # 注：窗口按"交互型通知要快"取小值；批量链路（收藏下载链）的刷屏改在源头
    # 解决——链路按批汇总为 1 条，不再逐条发"开始/失败/完成"通知
    # （2026-09-21 实测：逐条发导致 1119 条通知中 622 条被电报接口以 429 拒绝）
    "notification.aggregate_window_seconds": 5,
    "notification.aggregate_max_events": 50,
    # 投递健康度告警（P0）：通知系统自己坏掉时，必须有人被告知。
    # 生产实测：32 天内 629 条发送失败（54.8%），其中连续 7 天每天失败 25~151 条，
    # 全程无人知晓——而这正是"收藏集中失败"的窗口。
    "notification.delivery_health_enabled": True,
    # 连败阈值：渠道彻底不通（如 token 失效、网络断）时最先触发
    "notification.delivery_health_consecutive_threshold": 5,
    # 失败率阈值：渠道"在丢消息"（如限流）时触发；须先攒够样本数以免冷启动误报
    "notification.delivery_health_rate_threshold": 0.5,
    "notification.delivery_health_min_samples": 10,
    "notification.delivery_health_window_seconds": 3600,
    # 同一渠道同原因的告警最小间隔，避免风暴
    "notification.delivery_health_alert_cooldown_seconds": 3600,
    # __默认值由.通过_类型脚本派生，
    # 此处留空由管理器层在读取时做回退，用户可通过配置脚本覆盖
    # 静音时段
    "notification.quiet_hours_enabled": False,
    "notification.quiet_hours_start": "22:00",
    "notification.quiet_hours_end": "07:00",
    "adapter.circuit_breaker.failure_threshold": 3,
    "adapter.circuit_breaker.freeze_durations": [30, 120, 360, 720],
    "adapter.circuit_breaker.reset_window_hours": 24,
    "validity.first_execution": None,
    "validity.total_weeks": 4,
    "validity.frequency_weeks": 1,  # ✅ #43: 执行频率（周），≥1
    "validity.first_weekday": 1,  # ✅ #43: 首次执行周几（1=周一, 7=周日）
    "validity.execute_time": "03:00",  # ✅ #43: 首次执行时间（HH:MM），调度器使用
    "validity.next_run": None,
    "validity.checked_count": 0,
    "validity.round_completed": False,
    "validity.batch_size": 50,
    "validity.batch_interval": 5,
    "validity.check_ratio": 25,
    # ── 已废弃字段（兼容旧前端）──
    "validity.frequency": "weekly",  # @deprecated 已废弃，用 frequency_weeks 替代
    "validity.update_interval": 28,  # @deprecated 已废弃，用 total_weeks 替代
    # ──阶段4:日期提醒──
    "tasks.date_reminder_enabled": False,
    "tasks.date_reminder_cron": "0 2 * * *",
    "tasks.auto_archive_retry_enabled": True,
    "tasks.auto_archive_retry_cron": "0 4 * * *",
    # ── 下载节奏（手动批量下载与收藏下载链共用；暂不暴露到网页/桌面界面）──
    "download.batch_size": 10,  # 每批条数，批间长休息
    "download.long_rest": 15.0,  # 批间冷却秒数
    "download.max_workers": 2,  # 批内并发上限
    "download.max_retries": 2,  # 网络失败重试轮数（引擎层）
    "download.min_delay": 1.0,  # 请求间随机延迟下限（秒）
    "download.max_delay": 3.0,  # 请求间随机延迟上限（秒）
}
