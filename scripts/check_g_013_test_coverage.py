#!/usr/bin/env python3
"""
G-013: 测试覆盖率伴随检查门禁 (Test Coverage Accompaniment Gate)

核心能力:
- 基于 AST Diff 的语义级变更检测（免疫注释/格式/局部变量重命名干扰）
- 递归结构哈希精准识别逻辑变更
- 多级回退测试文件映射
- 私有函数启发式升级判定（超长/含异常/含IO → 阻断）
- Bug Fix commit message 强制测试检查
- 安全 Git 交互与性能保护
"""

import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# U34：变更范围获取失败必须 FAIL（旧行为是把「拿不到」当成「没有变更」→ 假绿）
from _gate_git import ChangeScope, ChangeSetUnavailable, content_or_exit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# ============================================================================ 分隔
# 配置常量
# ============================================================================ 分隔

# 业务代码目录（用于过滤哪些文件需要检查）
BUSINESS_DIRS = [
    "manager",
    "organizer",
    "download",
    "query",
    "tasks",
    "monitor",
    "wechat_ip",
    "announcement",
    "core",
    "i18n",
    "docker",
    "scan",
]

# 抽象语法树解析超时（秒）
AST_PARSE_TIMEOUT_SEC = 3.0

# 私有函数升级为阻断的阈值：函数体行数超过此值
PRIVATE_FUNC_BODY_LINE_THRESHOLD = 50

# 缺陷修复关键字正则
BUGFIX_PATTERN = re.compile(r'\b(fix|bugfix|hotfix|bug)\b', re.IGNORECASE)


def is_test_file(path: str) -> bool:
    """判断路径是否位于 `tests/`（规则 0 的"带测试"判据）。

    原实现用 `'test' in path.lower()`，把 `scripts/check_g_013_test_coverage.py`
    这类**文件名含 test 的生产脚本**当成测试变更 ⇒ 规则 0 被架空（2026-10-17 实测）。
    """
    normalized = path.replace('\\', '/').lower()
    if normalized.startswith('tests/') or '/tests/' in normalized:
        return True
    # 前端测试：web/src/**/*.test.ts（A-19/B5）。此前只认 tests/，导致前端修复
    # 带 .test.ts 也被判定“无测试变更”，只能改用 chore 提交（语义失真）。
    return bool(re.search(r'(^|/)web/src/.*\.test\.(ts|tsx|js|jsx)$', normalized))

# 输入输出调用检测正则（比集合成员检查更精确）
IO_PATTERN = re.compile(
    r'\b(open|connect|execute|fetchall|fetchone|'
    r'requests\.get|requests\.post|requests\.put|requests\.delete|'
    r'httpx|aiohttp|urllib|socket)\b'
)


# ============================================================================ 分隔
# 抽象语法树工具函数
# ============================================================================ 分隔

def _hash_node(node: ast.AST) -> str:
    """
    递归计算 AST 节点的结构哈希。
    忽略行号、列号、上下文等位置信息，仅保留语义结构。
    局部变量重命名不会影响哈希值（因为 Name.id 在非 name 字段中被跳过）。
    """
    hasher = hashlib.md5()
    hasher.update(type(node).__name__.encode())

    for field, value in ast.iter_fields(node):
        # 跳过位置信息和上下文
        if field in ('lineno', 'col_offset', 'end_lineno', 'end_col_offset', 'ctx'):
            continue

        if isinstance(value, ast.AST):
            hasher.update(_hash_node(value).encode())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ast.AST):
                    hasher.update(_hash_node(item).encode())
                elif isinstance(item, str):
                    hasher.update(item.encode())
                else:
                    # 非抽象语法树/类型也参与哈希（如数字字面量）
                    hasher.update(str(item).encode())
        elif isinstance(value, str):
            # 仅函数名/类名参与哈希；其他字符串（如变量名、文档字符串）不参与
            if field == 'name':
                hasher.update(value.encode())
        elif isinstance(value, (int, float, bool)):
            hasher.update(str(value).encode())
        elif value is None:
            hasher.update(b'None')
        else:
            hasher.update(str(value).encode())

    return hasher.hexdigest()


def _extract_api_signatures(tree: ast.Module) -> Dict[str, dict]:
    """
    提取文件中所有函数/类的特征签名。
    返回 {name: {'type': 'public'|'private', 'args': [...], 'decorators': [...],
                 'body_hash': str, 'line_count': int, 'has_exception': bool, 'has_io': bool}}
    """
    apis = {}
    exception_node_types = (ast.Try, ast.Raise, ast.ExceptHandler)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        name = node.name
        is_private = name.startswith('_') and not name.startswith('__')
        api_type = 'private' if is_private else 'public'

        # 提取参数列表（没有，跳过）
        args = []
        if hasattr(node, 'args') and node.args is not None:
            args = [arg.arg for arg in node.args.args]

        # 提取装饰器
        decorators = []
        if hasattr(node, 'decorator_list'):
            for d in node.decorator_list:
                try:
                    decorators.append(ast.unparse(d))
                except Exception:
                    decorators.append(type(d).__name__)

        # 计算结构哈希
        body_hash = _hash_node(node)

        # 统计行数
        line_count = getattr(node, 'end_lineno', 0) - getattr(node, 'lineno', 0) + 1

        # 检测是否包含异常处理或外部输入输出
        has_exception = False
        has_io = False
        for child in ast.walk(node):
            if isinstance(child, exception_node_types):
                has_exception = True
            if isinstance(child, ast.Call):
                func_name = ''
                if isinstance(child.func, ast.Name):
                    func_name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    try:
                        func_name = ast.unparse(child.func)
                    except Exception as e:
                        print(f"[WARN] AST 解析失败，跳过该调用的 IO 判定: {e}", file=sys.stderr)
                # 使用正则精确匹配输入输出调用
                if IO_PATTERN.search(func_name):
                    has_io = True

        apis[name] = {
            'type': api_type,
            'args': args,
            'decorators': decorators,
            'body_hash': body_hash,
            'line_count': line_count,
            'has_exception': has_exception,
            'has_io': has_io,
        }

    return apis


# ============================================================================ 分隔
# 版本控制安全交互
# ============================================================================ 分隔

def get_content_at(filepath: str, ref: str) -> Optional[str]:
    """取文件在 git ref 中的内容。

    返回：存在 → 内容（可为空串文件）；该 ref 中不存在 → `''`（合法）；
    **git 不可用 → `None`**（调用方须按「范围不可知」→ exit 2，不得当成「文件不存在」）。
    `ref` 由调用方决定（本地 `HEAD`；`--range` 用 merge-base）。
    """
    try:
        result = subprocess.run(
            ['git', 'show', f'{ref}:{filepath}'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', check=False, timeout=10
        )
        if result.returncode == 0:
            return result.stdout or ''
        return ''
    except Exception as e:
        print(f"[WARN] git show 失败: {ref}:{filepath}: {e}", file=sys.stderr)
        return None


def get_commit_message(msg_file: Optional[str] = None) -> str:
    """获取**待提交**消息（`msg_file`）或最近一次 commit message。

    显式传入 `msg_file`（commit-msg 钩子的 `$1`）时读该文件；否则读 `git log -1`。
    **不再默认读 `.git/COMMIT_EDITMSG`**：pre-commit 阶段 git 尚未写入本次消息，
    该文件仍是**上一次**提交的留言 ⇒ 会把上一条 `fix:` 误判成本条（2026-10-17 实测：
    一条纯 docs 提交被前一条 `fix(gate):` 的 message 拦住）。规则 0 因此改由
    `.husky/commit-msg` 用 `--commit-msg-file "$1"` 执行，pre-commit 传 `--no-commit-msg`。
    """
    try:
        if msg_file:
            with open(msg_file, encoding='utf-8') as f:
                return f.read()
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%s%n%b'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', check=False, timeout=10
        )
        return (result.stdout or '') if result.returncode == 0 else ''
    except Exception as e:  # noqa: BLE001 - 空消息会让"fix 必须带测试"规则失效，必须留痕
        print(f"[WARN] 读取 commit message 失败，按空消息处理: {e}", file=sys.stderr); return ''  # noqa: E702


def get_changed_files() -> List[str]:
    """
    获取本次变更的文件列表。
    仅包含已暂存（staged）和已跟踪的工作区变更，不包含未跟踪文件。

    Raises:
        ChangeSetUnavailable: git 不可用，或所有来源都拿不到结果。
            此时门禁必须 FAIL——「拿不到变更范围」不等于「没有变更」，
            静默 PASS 会让本次及之后所有提交都失去该维度保护（U34 假绿修复）。
    """
    scope = ChangeScope(ROOT, timeout=10)
    files = set()
    for args in (
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
        ['git', 'diff', '--name-only', '--diff-filter=ACMR'],
    ):
        stdout = scope.query(args)
        if stdout:
            files.update(stdout.strip().splitlines())

    # 注意：不包含未跟踪文件（---）
    # 未跟踪文件不应触发门禁，只有被后才进入暂存区检查
    scope.require("本次变更文件范围")
    scope.report_partial()
    return [f for f in files if f]


def resolve_range_base(base: str, head: str) -> str:
    """把 `<base>...<head>` 解析成「merge-base」，作为基线内容来源。

    直接用 `base` 会比 `git diff base...head`（三点）多算「base 自己前进的部分」；
    取 merge-base 与三点 diff 的口径严格一致。

    Raises:
        ChangeSetUnavailable: merge-base 求不出（无共同祖先 / ref 不存在 / git 不可用）。
    """
    scope = ChangeScope(ROOT, timeout=10)
    stdout = scope.query(['git', 'merge-base', base, head])
    if stdout is None:
        scope.require(f"变更范围基线 {base}...{head}")  # 抛错（exit 2）
    merged = (stdout or '').strip()
    if not merged:
        raise ChangeSetUnavailable(f"无法求出 {base}...{head} 的 merge-base")
    return merged


def get_changed_files_for_range(base: str, head: str) -> List[str]:
    """获取 `base..head` 范围内的变更文件（CI 形态；点号范围由调用方先解成 merge-base）。

    Raises:
        ChangeSetUnavailable: 范围不可知（git 不可用 / ref 不存在）。
    """
    scope = ChangeScope(ROOT, timeout=10)
    stdout = scope.query(
        ['git', 'diff', '--name-only', '--diff-filter=ACMR', f'{base}..{head}']
    )
    scope.require(f"变更范围 {base}..{head}")
    scope.report_partial()
    return [f for f in (stdout or '').strip().splitlines() if f]


def is_business_file(filepath: str) -> bool:
    """判断是否为需要检查的业务代码文件。

    2026-10-17 修正（体检 D-6 的深层缺陷）：原实现把 git 路径的**第一段**与
    `BUSINESS_DIRS` 比较，而仓库内路径是 `pilotstd/manager/...` ⇒ 第一段恒为
    `pilotstd` ⇒ **`pilotstd/` 下所有业务代码从未被检查过**（只有顶层目录如
    `scripts/`、`docker/` 才可能命中）。现按 `pilotstd/<子目录>` 取第二段。
    """
    if not filepath.endswith('.py'):
        return False

    # 排除测试文件本身
    if 'test_' in Path(filepath).stem or filepath.startswith('tests/'):
        return False

    # 排除____脚本（纯导出）
    if Path(filepath).name == '__init__.py':
        return False

    # 必须在业务目录下（pilotstd/<dir>/… 或顶层 <dir>/…）
    parts = Path(filepath).parts
    if not parts:
        return False
    if len(parts) > 1 and parts[0] == 'pilotstd':
        return parts[1] in BUSINESS_DIRS
    return parts[0] in BUSINESS_DIRS


# ============================================================================ 分隔
# 测试文件映射
# ============================================================================ 分隔

# 判据：**tests/ 下任一测试变更**（不再按路径精确映射）。
# 为什么不精确映射：实测近 60 次提交里 `tests/<父目录>/test_<文件名>.py` 命中 **0/16**
# （docker 0/60），文件名启发式仅 3/16——本仓库测试按"功能"命名而非按模块命名
# （如 test_channels_retry_foundation.py 一次覆盖 5 个渠道文件），精确映射必然常红。
# 粗判据下 14/16 通过，剩余 2 例是"改了公开 API 却完全没动测试"的真阳性。
# 体检 D-6，2026-10-17。
def has_test_sync(changed_files: List[str]) -> bool:
    """业务代码变更是否伴随 `tests/` 下的任何测试变更。"""
    return any(is_test_file(f) for f in changed_files)


# ============================================================================ 分隔
# 核心变更检测
# ============================================================================ 分隔

def has_functional_change(old_content: str, new_content: str) -> Dict[str, dict]:
    """
    对比新旧 AST，返回发生变更的 API 信息字典。
    key=API名称, value={'type': 'public'|'private', 'change_reason': str, ...}
    """
    result = {}

    def safe_parse(content: str) -> Optional[ast.Module]:
        """安全解析 Python 源码为 AST，超时或语法错误返回 None。"""
        if not content.strip():
            return None
        try:
            start = time.monotonic()
            tree = ast.parse(content)
            elapsed = time.monotonic() - start
            if elapsed > AST_PARSE_TIMEOUT_SEC:
                print(f"[WARN] AST 解析超时 ({elapsed:.1f}s)，跳过该文件", file=sys.stderr)
                return None
            return tree
        except SyntaxError:
            return None  # 语法错误交由其他门禁处理

    old_tree = safe_parse(old_content)
    new_tree = safe_parse(new_content)

    # 新文件场景：所有接口都是新增
    if old_tree is None and new_tree is not None:
        new_apis = _extract_api_signatures(new_tree)
        for name, info in new_apis.items():
            info['change_reason'] = 'new_file'
            result[name] = info
        return result

    # 两棵树都无效 → 无功能变更
    if old_tree is None or new_tree is None:
        return result

    old_apis = _extract_api_signatures(old_tree)
    new_apis = _extract_api_signatures(new_tree)

    # 新增接口
    for name, info in new_apis.items():
        if name not in old_apis:
            info['change_reason'] = 'added'
            result[name] = info

    # 删除接口→降级为警告级别（强制标记为，由后续逻辑处理为警告）
    for name, info in old_apis.items():
        if name not in new_apis:
            info['change_reason'] = 'deleted'
            info['type'] = 'private'
            result[name] = info

    # 修改接口
    for name, new_info in new_apis.items():
        if name in old_apis:
            old_info = old_apis[name]
            reasons = []
            if new_info['args'] != old_info['args']:
                reasons.append('signature_changed')
            if new_info['decorators'] != old_info['decorators']:
                reasons.append('decorator_changed')
            if new_info['body_hash'] != old_info['body_hash']:
                reasons.append('logic_changed')

            if reasons:
                new_info['change_reason'] = ','.join(reasons)
                result[name] = new_info

    return result


def _should_upgrade_private_to_block(info: dict) -> bool:
    """
    私有函数启发式升级判定：
    满足任一条件时，从 WARNING 升级为 BLOCK。
    """
    if info.get('line_count', 0) > PRIVATE_FUNC_BODY_LINE_THRESHOLD:
        return True
    if info.get('has_exception', False):
        return True
    if info.get('has_io', False):
        return True
    return False


# ============================================================================ 分隔
# 主检查逻辑
# ============================================================================ 分隔

def _check_bugfix_rule(changed_files: List[str], commit_msg: str) -> tuple[bool, List[str]]:
    """规则 0：`fix`/`bugfix`/`hotfix` 提交必须带 `tests/` 下的变更。

    返回 ``(is_bugfix, errors)``。单独成函数是为了让 `run_check()` 守住 G-010 的
    80 有效行上限（2026-10-17 接线 commit-msg 后实测 84 行被拦）。
    """
    is_bugfix = bool(BUGFIX_PATTERN.search(commit_msg))
    has_test_change = any(is_test_file(f) for f in changed_files)
    if is_bugfix and not has_test_change:
        return is_bugfix, [
            "[TEST-BLOCK] Bug 修复必须伴随测试用例的新增或修改 "
            "(commit message 包含 fix/bugfix/hotfix，但未检测到测试文件变更)"
        ]
    return is_bugfix, []


def _load_pair(biz_file: str, old_ref: str, new_ref: Optional[str], warnings: list) -> Optional[tuple]:
    """读取比对所需的「基线 / head」内容；读不到时记 warning 并返回 None。"""
    old_content = content_or_exit(get_content_at(biz_file, old_ref), biz_file, old_ref)
    if new_ref is None:
        try:
            with open(biz_file, 'r', encoding='utf-8') as fh:
                return old_content, fh.read()
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"[TEST-WARN] 无法读取文件 {biz_file}: {e}")
            return None
    new_content = content_or_exit(get_content_at(biz_file, new_ref), biz_file, new_ref)
    if not new_content:
        # head 侧为空 = 文件被删除；ast.parse("") 返回 None，无法参与比对，至少留痕。
        warnings.append(f"[TEST-WARN] {biz_file} 在 {new_ref} 中不存在（疑删除），未做 AST 比对")
        return None
    return old_content, new_content


def _check_biz_file(
    biz_file: str, old_ref: str, new_ref: Optional[str], test_changed: bool
) -> tuple:
    """检查单个业务文件，返回 (errors, warnings)。"""
    local_warnings: list = []
    pair = _load_pair(biz_file, old_ref, new_ref, local_warnings)
    if pair is None:
        return [], local_warnings
    changed_apis = has_functional_change(*pair)
    if not changed_apis:
        return [], local_warnings

    errors: list = []
    for api_name, info in changed_apis.items():
        api_type = info['type']
        reason = info['change_reason']
        # 删除接口已降级为，此处会进入警告流程
        if api_type == 'public':
            if not test_changed:
                errors.append(
                    f"[TEST-BLOCK] {biz_file} :: {api_name}() "
                    f"发生了功能变更 ({reason})，"
                    f"但未检测到对应测试文件变更。期望修改: tests/ 下任一测试文件"
                )
        else:  # private
            if _should_upgrade_private_to_block(info):
                if not test_changed:
                    errors.append(
                        f"[TEST-BLOCK] {biz_file} :: {api_name}() "
                        f"(私有) 发生了高风险变更 ({reason}, "
                        f"lines={info.get('line_count')}, "
                        f"exception={info.get('has_exception')}, "
                        f"io={info.get('has_io')})，需补充测试。"
                        f"期望修改: tests/ 下任一测试文件"
                    )
            elif not test_changed:
                local_warnings.append(
                    f"[TEST-WARN] {biz_file} :: {api_name}() "
                    f"(私有) 发生了变更 ({reason})，建议补充测试。"
                )
    return errors, local_warnings


def run_check(
    changed_files: Optional[List[str]] = None,
    commit_msg: Optional[str] = None,
    check_bugfix: bool = True,
    bugfix_only: bool = False,
    old_ref: str = 'HEAD',
    new_ref: Optional[str] = None,
) -> dict:
    """
    执行 G-013 门禁检查。
    返回 {'passed': bool, 'errors': [...], 'warnings': [...]}

    `check_bugfix=False`：跳过规则 0（pre-commit 阶段拿不到待提交消息时使用）。
    `bugfix_only=True`：只跑规则 0（commit-msg 钩子使用，测试联动由 pre-commit 负责）。
    `old_ref`/`new_ref`：内容来源。默认 `HEAD` + 工作区（本地暂存/工作区口径）；
    `--range` 模式传 merge-base + 范围右端 ref（CI 中工作区等于 HEAD，用默认值会恒无变更）。
    """
    if changed_files is None:
        changed_files = get_changed_files()
    if commit_msg is None:
        commit_msg = get_commit_message()
    commit_msg = commit_msg or ''

    errors = []
    warnings = []

    # 规则0:缺陷修复强制要求测试
    is_bugfix = False
    if check_bugfix or bugfix_only:
        is_bugfix, bugfix_errors = _check_bugfix_rule(changed_files, commit_msg)
        errors.extend(bugfix_errors)
        if bugfix_only:
            return {
                'passed': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'files_checked': 0,
                'is_bugfix': is_bugfix,
            }

    # --- 规则 1: 业务代码变更检查 ---
    biz_files = [f for f in changed_files if is_business_file(f)]

    test_changed = has_test_sync(changed_files)
    for biz_file in biz_files:
        file_errors, file_warnings = _check_biz_file(biz_file, old_ref, new_ref, test_changed)
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    passed = len(errors) == 0
    return {
        'passed': passed,
        'errors': errors,
        'warnings': warnings,
        'files_checked': len(biz_files),
        'is_bugfix': is_bugfix,
    }


# ============================================================================ 分隔
# 命令行入口
# ============================================================================ 分隔

def _parse_range_arg(argv: List[str]) -> Optional[tuple]:
    """解析 `--range BASE...HEAD`（兼容两点写法）。返回 (base, head) 或 None。

    Raises:
        ValueError: 缺参数 / 格式非法。CLI 侧据此 exit 2。
    """
    if '--range' not in argv:
        return None
    idx = argv.index('--range')
    if idx + 1 >= len(argv) or argv[idx + 1].startswith('--'):
        raise ValueError("--range 缺少参数（需形如 origin/main...HEAD）")
    spec = argv[idx + 1]
    for sep in ('...', '..'):
        if sep in spec:
            base, head = spec.split(sep, 1)
            if base and head:
                return base, head
    raise ValueError(f"--range 格式非法: {spec}（需形如 BASE...HEAD）")


def main():
    """CLI 入口：支持 --json / --commit-msg-file / --no-commit-msg / --bugfix-only / --range。"""
    output_format = 'json' if '--json' in sys.argv else 'text'

    msg_file = None
    if '--commit-msg-file' in sys.argv:
        idx = sys.argv.index('--commit-msg-file')
        if idx + 1 >= len(sys.argv):
            print("[FAIL] --commit-msg-file 缺少参数（消息文件路径）", file=sys.stderr)
            sys.exit(2)
        msg_file = sys.argv[idx + 1]

    check_bugfix = '--no-commit-msg' not in sys.argv
    bugfix_only = '--bugfix-only' in sys.argv

    try:
        range_spec = _parse_range_arg(sys.argv)
    except ValueError as exc:
        print(f"[FAIL] G-013: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        if range_spec is not None:
            base, head = range_spec
            # 三点范围取 merge-base 作基线，与 `git diff A...B` 口径一致
            merged = resolve_range_base(base, head)
            changed = get_changed_files_for_range(merged, head)
            result = run_check(
                changed_files=changed,
                commit_msg=get_commit_message(msg_file),
                check_bugfix=check_bugfix,
                bugfix_only=bugfix_only,
                old_ref=merged,
                new_ref=head,
            )
        else:
            result = run_check(
                commit_msg=get_commit_message(msg_file),
                check_bugfix=check_bugfix,
                bugfix_only=bugfix_only,
            )
    except ChangeSetUnavailable as exc:
        print(f"[FAIL] G-013: 无法获取变更文件范围 — {exc}", file=sys.stderr)
        print(
            "       门禁不允许在「变更范围不可知」时静默跳过（会造成假绿）。"
            "请检查 git 是否可用、仓库是否完整。",
            file=sys.stderr,
        )
        sys.exit(2)

    if output_format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result['warnings']:
            for w in result['warnings']:
                print(w, file=sys.stderr)
        if result['errors']:
            for e in result['errors']:
                print(e, file=sys.stderr)
            print(f"\n[FAIL] G-013 门禁未通过: {len(result['errors'])} 个阻断问题", file=sys.stderr)
        else:
            print(f"[PASS] G-013 门禁通过 (检查了 {result['files_checked']} 个业务文件)")

    sys.exit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
