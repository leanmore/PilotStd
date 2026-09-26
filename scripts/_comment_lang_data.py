#!/usr/bin/env python3
# fmt: off
"""G-012 注释检查的静态数据表（从 check_g_012_comment_density.py 拆出）。

拆出原因（G-010 文件规模治理）：检查脚本本身已达 457 有效行进入警告区，
而其中近 200 行是「中文注释白名单 / 术语对照表」这类纯数据——它们只被读取、
不含任何判定逻辑，外移后检查行为逐字节不变，也让我方检查脚本的改动面更小。

维护提示：本文件只放数据，不放函数；新增白名单词条时在 LANG_WHITELIST 内追加，
并把「为什么必须豁免」写成行尾注释，否则下一个人无法判断该词是否可删。
"""

import re

# 程序静态分析工具指令前缀，这些必须保留英文原文才能生效
TOOL_DIRECTIVES = (
    'type:',        # mypy / pyright
    'noqa',         # flake8 / ruff
    'ruff:',        # ruff
    'pylint:',      # pylint
    'fmt:',         # black / yapf
    'isort:',       # isort
    'pragma:',      # coverage
    'TODO',         # 开发待办标记（含 TODO(P2) 等结构化前缀）
)

# 中文注释中不可避免的技术标识符白名单（类名/模块名/接口路径/协议缩写等）
# 这些词在中文注释中出现时不应触发 LANG 警告，因为翻译会降低可读性
LANG_WHITELIST = {
    # ── 项目核心术语 ──
    'user_preferences', 'user_layouts', 'user_settings', 'user_preference',
    'preferences', 'preference_key', 'preference_value', 'layout:dashboard',
    # ── 通用标识符 ──
    'key', 'val', 'msg', 'cfg', 'db', 'env', 'std', 'src', 'tmp', 'str', 'int',
    'lock', '_lock', 'join',
    # ── 标准库/内置 ──
    'sys.path', 'sqlite3', 'argparse',
    # ── 框架/库 ──
    'StandardManager', 'BlockingQueuedConnection', 'QApplication',
    'clean_announcement_content', 'extract_content',
    # ── 认证/协议 ──
    'JWT', 'sub', 'pst_', 'csrf_token', 'X-CSRF-Token',
    # ── 后端模块名 ──
    'user_service', 'get_current_user_id', 'get_user_id', 'get_user_by_id',
    'UserPreferenceManager', 'UserService',
    # ── 通用技术缩写 ──
    'API', 'DB', 'I/O', 'KV', 'SQL', 'JSON', 'URL', 'HTML', 'CSS', 'GC',
    'HTTP', 'RESTful', 'CSRF', 'UI', 'CLI', 'OK', 'CI',
    # ── 前端框架术语 ──
    'Pinia', 'Vue', 'TS', 'JS', 'DOM', 'SCSS',
    # ── 项目特定路径 ──
    '/api/user/', '/api/', 'layout', 'settings', 'tests/test_e2e_adapters.py',
    # ── 装饰器/注解 ──
    '@require_role', '@router', '@migration',
    # ── 权限/安全 ──
    'admin', 'require_role', 'require_admin',
    'ShellExecuteW', 'runas', 'UAC', 'exe', 'bat', 'Program', 'Files',
    'BeautifulSoup', 'Tag', 'no', 'redef', 'blocks',
    # ── 版本/标记 ──
    'v49', 'v48', 'DEPRECATED', 'noqa', 'E402',
    # ── 标记语言 ──
    '<p>', '</p>', 'extract_content',
    # ── 历史遗留警告清零（中文注释混技术标识符）──
    'v50', '_migrate_v50.py', 'G-010',  # migrations.py:582
    'announcement_record', 'std_name',  # validity_checker.py:187
    'create_default_sites', 'config.json',  # scorer.py:112 / site_config.py:458
    'SiteState',  # site_config.py:458
    'os.access', 'Windows',  # update_download.py:49
    # ── 路由引擎 v2.0 标识符（router_v2.py 中文注释引用）──
    # 标准代号（领域知识不可翻译）
    'GB', 'DB', 'ISO', 'IEC', 'EN',
    # 层级与路由概念
    'L1', 'L2', 'L3', 'reliability', 'low_confidence_exploration',
    'consume', 'decision', 'decisions', 'intent',
    # 能力模型字段与文件名
    'site_capabilities.yaml', 'capabilities', 'industries', 'level1', 'level2',
    'is_international', 'is_keyword_query', 'industry', 'key', 'SiteCapability', 'RouteChain',
    # 布尔/空值/评级
    'None', 'True', 'False', 'ID', 'high', 'medium', 'low', 'unknown',
    # 文件与版本
    'scorer.py', 'scorer', 'YAML', 'config', 'v2', 'v2.0',
    # 并发与文档（阶段三引入）
    'Worker', 'Markdown',
    # 埋点与日志（阶段四引入）
    'v1', 'JSONL', 'logs', 'put', 'flush',
    # ── 其他 ──
    'publish', 'deliver', 'cleanup', 'docstring', 'LANG',
    # ── 2026-08-21 门禁警告清零（G-012 LANG）──
    # 日志/文件/路径标识符
    'app.log', 'app.log.N', 'lines_estimate', 'realpath', 'offset', 'limit',
    'grep', 'STATUS.md', 'coverage-report.md', '/standards', 'check_all.sh',
    '--deep', 'tests/scripts/', '.py', 'UTF-8',
    # 认证/安全/网络
    'SEC-001', 'AuthMiddleware', 'user_id', 'Depends', '_get_user_id',
    'GET', 'TLS', 'SSL', 'UA', 'curl', 'subprocess', 'requests',
    'miit', 'energy', 'verify', 'main',
    # 前端/配置
    'appearance', 'login_bg', 'Web', 'router',
    # 引擎/模块/变量
    'importlib', 'step_results', 'std_type', 'check_filtered',
    'search_url', 'SEARCH_URL', 'API_URL', 'base_url', 'BaseAdapter',
    'num_prefix', 'number', 'status', 'files', 'level',
    # 标准代号/迁移
    'TCIESC', 'T/CIESC', 'T{org}', 'TSG', 'v52', '_migrate_v52.py',
    'router_v2.py', 'Fernet', 'gAAAAA',
    # 模板/工具
    'Jinja2', 'cookiecutter', 'pre-commit', 'mypy', 'from . import x',
    # 2026-08-21 复核补漏（白名单首轮遗漏）
    'IP', '4xx', '5xx', 'G-012', 'gitignored', 'ruff', 'E501',
    # 2026-08-21 二次补漏（检查器新增注释引用）
    'python', 'bash', 'INFO',
    # 2026-08-25 专项清理（50 条语言警告清零，全库审计）
    # ── 项目缺陷/任务编码（代码绑定，来源见各文件违规行）──
    'P1-2', 'P1-4', 'P2-2', 'P2-3', 'O-3', 'O-4', 'D-1', 'D-3', 'D-4',
    'F-03', '3-A', '3-C3', '3-C5',
    # ── 代码标识符/配置键 ──
    'standard_type', 'user_credentials', 'CredentialHelper', '_init_channels',
    '_cred_helper', 'corpid', 'agentid', 'corpsecret', 'webhook_url',
    'running', 'useFavorite', 'done', 'pending', 'downloading', 'archiving',
    'abandoned', 'retry_count', 'download_to_inbox', 'csres', 'FastAPI',
    'Query', 'appdata',
    # ── 审计脚本模式片段（审计脚本文档）──
    'EVENT_XXX', 'ALL_EVENTS', 'Assign', 'AnnAssign', 'EventDef', 'EVENT_X',
    'bypass_aggregation', 'data.get', 'field_var', 'Name', 'if not',
    '1a', '1b', '2b',
    # ── CLI/路径/文件 ──
    '--module', '--json', 'scripts/', '/lite', 'AGENTS.md', '.ts', '.vue',
    # ── 协议/技术缩写（与 API/SQL 同类）──
    'CQS', 'INSERT OR REPLACE', 'UPDATE', 'AST', 'stderr',
}

# 编译正则：匹配白名单中的词（按长度降序，确保长词优先匹配）
_LANG_WHITELIST_PATTERN = re.compile(
    '|'.join(re.escape(w) for w in sorted(LANG_WHITELIST, key=len, reverse=True))
)


# 常见英文技术术语 → 中文对照表（用于自动修复）
TERM_TRANSLATIONS: list[tuple[str, str]] = [
    # 通用
    ("AST", "抽象语法树"), ("IO", "输入输出"), ("API", "接口"), ("CLI", "命令行"),
    ("GUI", "图形界面"), ("SQL", "数据库查询"), ("DB", "数据库"), ("UI", "用户界面"),
    ("PDF", "便携文档"), ("OCR", "文字识别"), ("JWT", "令牌"), ("CSRF", "跨站伪造防护"),
    ("HTTP", "网络"), ("URL", "链接"), ("JSON", "数据"), ("HTML", "网页"),
    ("CSS", "样式"), ("JS", "脚本"), ("TS", "类型脚本"), ("ENV", "环境"),
    ("Git", "版本控制"), ("CI", "持续集成"), ("CD", "持续部署"), ("PR", "合并请求"),
    ("ADR", "架构决策"), ("MVP", "最小可行"), ("POC", "概念验证"),
    # 程序相关
    ("Python", "程序"), ("Qt", "界面框架"), ("PyQt", "界面框架"),
    ("StringIO", "文本流"), ("docstring", "文档字符串"), ("superuser", "超级用户"),
    ("fallback", "回退"), ("timeout", "超时"), ("retry", "重试"),
    ("cooldown", "冷却"), ("rotator", "轮转器"), ("rotator", "轮转器"),
    ("watcher", "监控器"), ("scanner", "扫描器"), ("observer", "观察者"),
    ("parser", "解析器"), ("matcher", "匹配器"), ("detector", "检测器"),
    ("builder", "构建器"), ("mover", "移动器"), ("mixin", "混入"),
    ("handler", "处理器"), ("engine", "引擎"), ("factory", "工厂"),
    ("adapter", "适配器"), ("manager", "管理器"), ("service", "服务"),
    ("scheduler", "调度器"), ("notifier", "通知器"), ("renderer", "渲染器"),
    ("runner", "运行器"), ("checker", "检查器"), ("cleaner", "清理器"),
    ("extractor", "提取器"), ("validator", "校验器"), ("normalizer", "规范化器"),
    ("dispatcher", "分发器"), ("persistence", "持久化"), ("serialize", "序列化"),
    ("deserialize", "反序列化"), ("migrate", "迁移"), ("upsert", "插入或更新"),
    ("fetch", "抓取"), ("crawl", "爬取"), ("download", "下载"),
    ("upload", "上传"), ("scan", "扫描"), ("query", "查询"),
    ("archive", "归档"), ("organize", "归类"), ("classifier", "分类器"),
    ("aggregator", "聚合器"), ("buffer", "缓冲区"), ("callback", "回调"),
    ("hash", "哈希"), ("cache", "缓存"), ("proxy", "代理"),
    ("lock", "锁"), ("mutex", "互斥"), ("thread", "线程"), ("process", "进程"),
    ("worker", "工作者"), ("daemon", "守护"), ("heartbeat", "心跳"),
    ("pool", "池"), ("queue", "队列"), ("stack", "栈"), ("fifo", "先进先出"),
    ("schema", "表结构"), ("migration", "迁移"), ("checksum", "校验和"),
    ("index", "索引"), ("trigger", "触发器"), ("view", "视图"),
    ("fixture", "测试夹具"), ("mock", "模拟"), ("stub", "桩"),
    ("patch", "补丁"), ("assert", "断言"), ("setup", "初始化"),
    ("teardown", "清理"), ("benchmark", "基准"), ("profile", "分析"),
    # 文件/路径
    ("cookiecutter", "模板引擎"), ("pilotstd", "项目"),
    ("docker", "容器"), ("src", "源码"), ("tests", "测试"),
    ("main", "入口"), ("core", "核心"), ("config", "配置"),
    ("utils", "工具"), ("models", "模型"), ("constants", "常量"),
    ("fixtures", "夹具"), ("adapters", "适配器"), ("handlers", "处理器"),
    ("engines", "引擎"), ("workers", "工作者"), ("pages", "页面"),
    ("widgets", "组件"), ("templates", "模板"), ("hooks", "钩子"),
    ("commands", "命令"), ("channels", "渠道"), ("rules", "规则"),
    ("facade", "门面"), ("pipeline", "流水线"), ("routing", "路由"),
    # 数据库
    ("sqlite", "数据库"), ("postgres", "数据库"), ("mysql", "数据库"),
    ("redis", "缓存"), ("mongodb", "数据库"),
    ("SELECT", "查询"), ("INSERT", "插入"), ("UPDATE", "更新"),
    ("DELETE", "删除"), ("DROP", "删除"), ("CREATE", "创建"),
    ("ALTER", "修改"), ("TABLE", "表"), ("FROM", "从"),
    ("WHERE", "条件"), ("LIMIT", "限制"), ("OFFSET", "偏移"),
    ("JOIN", "连接"), ("ORDER", "排序"), ("GROUP", "分组"),
    ("COUNT", "计数"), ("MAX", "最大"), ("MIN", "最小"),
    # 网络
    ("requests", "请求"), ("httpx", "网络"), ("aiohttp", "异步网络"),
    ("urllib", "网络库"), ("socket", "套接字"),
    ("API Key", "接口密钥"), ("Token", "令牌"), ("Secret", "密钥"),
    ("Password", "密码"), ("Username", "用户名"),
    # 通知
    ("Telegram", "电报"), ("DingTalk", "钉钉"), ("Feishu", "飞书"),
    ("WeChat", "微信"), ("Slack", "消息"),
    # 其他
    ("Bug Fix", "缺陷修复"), ("hotfix", "热修复"), ("bugfix", "缺陷修复"),
    ("Phase", "阶段"), ("Step", "步骤"), ("NOTE", "注意"),
    ("TODO", "待办"), ("FIXME", "待修复"), ("HACK", "临时方案"),
    ("XXX", "待定"), ("WIP", "进行中"), ("TBD", "待确定"),
    ("N/A", "不适用"), ("OK", "通过"), ("FAIL", "失败"),
    ("PASS", "通过"), ("ERROR", "错误"), ("WARN", "警告"),
    ("INFO", "信息"), ("DEBUG", "调试"), ("TRACE", "追踪"),
    ("v0.", "版本零"), ("v1.", "版本一"), ("v2.", "版本二"), ("v3.", "版本三"),
    ("v4.", "版本四"), ("v5.", "版本五"),
    # 文件扩展名
    (".py", "脚本"), (".js", "脚本"), (".ts", "脚本"), (".vue", "组件"),
    (".json", "数据"), (".yaml", "配置"), (".yml", "配置"), (".toml", "配置"),
    (".cfg", "配置"), (".ini", "配置"), (".md", "文档"), (".txt", "文本"),
    (".pdf", "文档"), (".doc", "文档"), (".docx", "文档"), (".csv", "表格"),
    (".sql", "数据库"), (".sh", "脚本"), (".bat", "脚本"), (".ps1", "脚本"),
    (".exe", "可执行文件"), (".dll", "库文件"),
]
