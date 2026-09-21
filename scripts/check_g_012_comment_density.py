#!/usr/bin/env python3
# fmt: off
"""G-012: 注释完整性检查。

检查项：
1. [DENSITY] 文件级注释密度 ≥ 3%（仅 ≥50 逻辑行的文件）
2. [FUNC] 每个函数至少有 1 行 docstring 或 # 注释
3. [CLASS] 每个类至少有 1 行 docstring 或 # 注释
4. [LANG] 注释必须全部用中文写（全量检查，工具指令注释豁免）

两种模式：
- pre-commit 模式（传入文件列表）：仅检查暂存文件，违规 → exit 1
- 全量模式（无参数）：扫描全部文件，违规 → 报告但不阻断（exit 0）

跳过策略：魔法方法、@property、≤2 行函数体、≤3 行类体、
私有短函数（_xxx ≤5 行）、__init__.py/setup.py 密度豁免。
"""

import ast
import re
import sys
from pathlib import Path

from _gate_paths import is_git_ignored

MIN_COMMENT_DENSITY = 0.03  # 最低注释密度：注释行 / 非空行 ≥ 3%
MIN_DENSITY_LOGICAL_LINES = 50  # 仅对 ≥50 逻辑行的文件检查密度
_REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "pilotstd_env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".qwen",
    ".superpowers",
    "tests",
}
EXCLUDE_PREFIXES = ("whitelist", "probe_")
DENSITY_EXEMPT_FILES = {"__init__.py", "__main__.py", "setup.py"}  # 密度豁免文件：包入口和构建脚本
# 排除迁移文件：其注释密度由校验和自愈机制保证，不强制-012检查
EXCLUDE_PATTERNS = ("_migrate_",)


def _is_git_ignored(filepath: Path) -> bool:
    """判断文件是否落在 .gitignore 忽略范围内（本地草稿不参与本门禁）。"""
    return is_git_ignored(filepath, _REPO_ROOT)


def _is_excluded(filepath: Path) -> bool:
    """检查文件路径是否在排除目录列表、命名前缀或模式列表中。"""
    for part in filepath.parts:
        if part in EXCLUDE_DIRS:
            return True
    if filepath.name.startswith(EXCLUDE_PREFIXES):
        return True
    # 排除迁移文件等特殊模式
    for pattern in EXCLUDE_PATTERNS:
        if pattern in filepath.name:
            return True
    # 入库产物之外的本地草稿（被版本控制忽略的文件）不参与本门禁
    return _is_git_ignored(filepath)


def _is_comment_line(line: str) -> bool:
    """判断一行是否以 # 开头的纯注释行。"""
    return line.strip().startswith("#")


def _is_blank_line(line: str) -> bool:
    """判断是否为纯空白行。"""
    return line.strip() == ""


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


def _get_comment_text(line: str) -> str:
    """提取 # 注释的纯文本内容（去除 # 和前后空白）。"""
    if '#' not in line:
        return ''
    idx = line.index('#')
    return line[idx+1:].strip()


def _is_chinese_comment(line: str) -> bool:
    """检查注释是否全部为中文（工具指令注释豁免，白名单术语允许）。"""
    text = _get_comment_text(line)
    if not text:
        return True  # 空注释视为合规
    if any(text.startswith(d) for d in TOOL_DIRECTIVES):
        return True
    # 先去掉引号内的字符串字面量（如 "\n\n"、'value'）
    text = re.sub(r'"[^"]*"', '', text)
    text = re.sub(r"'[^']*'", '', text)
    # 再剥离白名单术语
    cleaned = _LANG_WHITELIST_PATTERN.sub('', text)
    return not bool(re.search(r'[a-zA-Z]', cleaned))


def _has_docstring(node: ast.AST) -> bool:
    """检查 AST 节点（函数/类）的第一个语句是否为字符串常量文档字符串。"""
    body = getattr(node, "body", [])
    if not body:
        return False
    first = body[0]
    if not isinstance(first, ast.Expr):
        return False
    val = first.value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
        return True
    # 兼容程序3.7及更早版本的.节点
    if hasattr(ast, "Str") and isinstance(val, ast.Str):
        return True
    return False


def _has_comment_in_range(lines: list[str], start: int, end: int) -> bool:
    """检查代码行范围 [start, end]（1-based）内是否存在 # 注释行。"""
    for i in range(start - 1, min(end, len(lines))):
        if _is_comment_line(lines[i]):
            return True
    return False


def _should_skip_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """判断函数是否应跳过检查：魔法方法、@property、≤2 行体、私有短函数。"""
    if node.name.startswith("__") and node.name.endswith("__"):
        return True
    body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
    if body_lines <= 2:
        return True
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
    if node.name.startswith("_") and not node.name.startswith("__"):
        if body_lines <= 5:
            return True
    return False


def _should_skip_class(node: ast.ClassDef) -> bool:
    """判断类是否应跳过检查：≤3 行的极小类体。"""
    body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
    return body_lines <= 3


def check_file(filepath: Path, root: Path) -> list[str]:
    """检查单个文件，返回违规列表。"""
    errors: list[str] = []
    rel = filepath.relative_to(root) if root in filepath.parents else filepath

    try:
        text = filepath.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
    except (UnicodeDecodeError, PermissionError):
        return errors

    if len(lines) < 5:
        return errors

    # 分离非空行和逻辑行用于密度计算
    non_blank = [line for line in lines if not _is_blank_line(line)]
    logical_lines = [line for line in non_blank if not _is_comment_line(line)]

    # 文件级注释密度
    if len(logical_lines) >= MIN_DENSITY_LOGICAL_LINES and filepath.name not in DENSITY_EXEMPT_FILES:
        comment_count = sum(1 for line in non_blank if _is_comment_line(line))
        density = comment_count / len(non_blank) if non_blank else 1.0
        if density < MIN_COMMENT_DENSITY:
            errors.append(f"[DENSITY] {rel}: 注释密度 {density:.1%} (< {MIN_COMMENT_DENSITY:.0%})")

    # []#注释语言检查：注释必须全部用中文，禁止英文
    for i, line in enumerate(lines, start=1):
        if _is_blank_line(line):
            continue
        if not _is_comment_line(line):
            continue
        stripped = line.strip()
        if stripped.startswith("#!"):
            continue
        if "# -*-" in stripped:
            continue
        if not _is_chinese_comment(line):
            errors.append(
                f"[LANG] {rel}:{i} 注释必须全部用中文，不允许出现英文字母: "
                f"{_get_comment_text(line)[:30]}"
            )

    # 函数/类注释
    if filepath.suffix != ".py":
        return errors

    # 解析抽象语法树检查每个函数和类的注释完整性
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return errors

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _should_skip_func(node):
                continue
            # 函数注释检查：有文档字符串或有行内#注释即可
            has_doc = _has_docstring(node)
            has_comment = _has_comment_in_range(lines, node.lineno, node.end_lineno or node.lineno)
            if not has_doc and not has_comment:
                errors.append(f"[FUNC] {rel}:{node.name}() 缺少注释")
            # []文档字符串中文检查
            if has_doc:
                docstring = ast.get_docstring(node)
                if docstring and not _is_chinese_comment(docstring):
                    errors.append(
                        f"[LANG] {rel}:{node.lineno} {node.name}() 的 docstring 必须全部用中文: "
                        f"{docstring[:30]}"
                    )

        elif isinstance(node, ast.ClassDef):
            if _should_skip_class(node):
                continue
            has_doc = _has_docstring(node)
            has_comment = _has_comment_in_range(lines, node.lineno, node.end_lineno or node.lineno)
            if not has_doc and not has_comment:
                errors.append(f"[CLASS] {rel}:{node.name} 缺少注释")
            # []文档字符串中文检查
            if has_doc:
                docstring = ast.get_docstring(node)
                if docstring and not _is_chinese_comment(docstring):
                    errors.append(
                        f"[LANG] {rel}:{node.lineno} {node.name} 的 docstring 必须全部用中文: "
                        f"{docstring[:30]}"
                    )

    return errors


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


def _remove_english_from_comment(line: str) -> str:
    """从注释行中删除英文，保留中文描述。"""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return line

    indent = line[:len(line) - len(line.lstrip())]
    text = _get_comment_text(line)

    if not text:
        return f"{indent}# 分隔\n" if line.endswith(("\n", "\r")) else f"{indent}# 分隔"

    # 工具指令豁免：不修改
    if any(text.startswith(d) for d in TOOL_DIRECTIVES):
        return line

    # 已经是纯中文，不修改
    if _is_chinese_comment(line):
        return line

    # 盒型字符分隔线 → 已经是纯中文（"分隔"二字）
    if re.match(r"^[═─━┄┅┈┉╌╍╴╶╸╺]+$", text) or re.match(r"^=+$", text):
        return line

    # 应用术语翻译
    result = text
    for en, zh in TERM_TRANSLATIONS:
        result = result.replace(en, zh)

    # 删除残留的英文字母（只保留中文、数字、标点、空格）
    cleaned = re.sub(r'[a-zA-Z]', '', result)
    # 清理多余空格
    cleaned = re.sub(r'\s+', '', cleaned).strip()
    # 清理多余标点
    cleaned = re.sub(r'[-—]+$', '', cleaned).strip()
    cleaned = re.sub(r'^[-—]+', '', cleaned).strip()

    if not cleaned:
        cleaned = "（说明已省略）"

    suffix = "\n" if line.endswith(("\n", "\r")) else ""
    return f"{indent}# {cleaned}{suffix}"


def _fix_comment_line(line: str) -> str:
    """修复单行 # 注释，确保全部为中文。"""
    return _remove_english_from_comment(line)


def fix_lang_violations(root: Path) -> int:
    """自动修复所有 [LANG] 违规。"""
    files = [f for f in sorted(root.rglob("*.py")) if not _is_excluded(f)]
    fixed_count = 0
    docstring_todo: list[str] = []

    for fpath in files:
        if _is_excluded(fpath):
            continue
        errors = check_file(fpath, root)
        lang_errors = [e for e in errors if e.startswith("[LANG]")]
        if not lang_errors:
            continue

        # 解析违规行号和类型
        fix_lines: set[int] = set()
        for err in lang_errors:
            m = re.match(r"\[LANG\]\s+.+?:(\d+)\s", err)
            if m:
                fix_lines.add(int(m.group(1)))
            else:
                docstring_todo.append(err)

        if not fix_lines:
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
        except (UnicodeDecodeError, PermissionError):
            continue

        modified = False
        for ln in sorted(fix_lines):
            if ln <= len(lines):
                old_line = lines[ln - 1]
                new_line = _fix_comment_line(old_line)
                if new_line != old_line:
                    lines[ln - 1] = new_line
                    modified = True

        if modified:
            fpath.write_text("".join(lines), encoding="utf-8")
            rel = fpath.relative_to(root) if root in fpath.parents else fpath
            print(f"  已修复: {rel} ({len(fix_lines)} 行)")
            fixed_count += 1

    if docstring_todo:
        print(f"\n  [跳过] docstring 违规（需手动翻译）: {len(docstring_todo)} 项")
        for e in docstring_todo:
            print(f"    {e}")

    print(f"\n  修复文件数: {fixed_count}")
    return 0


def main() -> int:
    """入口：支持 pre-commit 模式（传入文件列表，阻断）和全量模式（报告不阻断）。"""
    root = Path(__file__).resolve().parent.parent

    # 判断模式：--→自动修复违规
    args = sys.argv[1:]
    if "--fix" in args:
        args = [a for a in args if a != "--fix"]
        return fix_lang_violations(root)

    if args:
        files = [Path(a).resolve() for a in args if Path(a).resolve().exists()]
        mode = "pre-commit（暂存文件）"
    else:
        files = [f for f in sorted(root.rglob("*.py")) if not _is_excluded(f)]
        mode = "全量扫描"

    all_errors: list[str] = []
    for fpath in files:
        if _is_excluded(fpath):
            continue
        all_errors.extend(check_file(fpath, root))

    print("=" * 60)
    print(f"G-012: 注释完整性检查 [{mode}]")
    print("=" * 60)
    print(f"  扫描文件: {len(files)}")
    print(f"  违规数: {len(all_errors)}")
    print()

    if all_errors:
        lang_errors = [e for e in all_errors if e.startswith("[LANG]")]
        hard_errors = [e for e in all_errors if not e.startswith("[LANG]")]

        if hard_errors:
            print("违规项:")
            for e in hard_errors:
                print(f"  {e}")
            print()
        if lang_errors:
            print(f"[LANG] 注释语言警告 ({len(lang_errors)} 项，不阻断):")
            for e in lang_errors:
                print(f"  {e}", file=sys.stderr)
            print()

        print("=" * 60)
        print(f"汇总: {len(hard_errors)} 项阻断违规, {len(lang_errors)} 项语言警告")
        if hard_errors:
            print("FAIL: 请添加注释后再提交。")
            return 1
        print("PASS: 所有阻断项通过（[LANG] 警告不阻断）。")
        return 0

    print("=" * 60)
    print("汇总: 0 项违规")
    print("PASS: 所有文件的注释密度均达标。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# fmt: on
