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
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional


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
]

# AST 解析超时（秒）
AST_PARSE_TIMEOUT_SEC = 3.0

# 私有函数升级为阻断的阈值：函数体行数超过此值
PRIVATE_FUNC_BODY_LINE_THRESHOLD = 50

# Bug Fix 关键字正则
BUGFIX_PATTERN = re.compile(r'\b(fix|bugfix|hotfix|bug)\b', re.IGNORECASE)

# IO 调用检测正则（比集合成员检查更精确）
IO_PATTERN = re.compile(
    r'\b(open|connect|execute|fetchall|fetchone|'
    r'requests\.get|requests\.post|requests\.put|requests\.delete|'
    r'httpx|aiohttp|urllib|socket)\b'
)


# ============================================================================ 分隔
# AST 工具函数
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
                    # 非 AST/str 类型也参与哈希（如数字字面量）
                    hasher.update(str(item).encode())
        elif isinstance(value, str):
            # 仅函数名/类名参与 hash；其他字符串（如变量名、docstring）不参与
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

        # 提取参数列表（ClassDef 没有 args，跳过）
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

        # 计算 body 结构哈希
        body_hash = _hash_node(node)

        # 统计行数
        line_count = getattr(node, 'end_lineno', 0) - getattr(node, 'lineno', 0) + 1

        # 检测是否包含异常处理或外部 IO
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
                    except Exception:
                        pass
                # 使用正则精确匹配 IO 调用
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
# Git 安全交互
# ============================================================================ 分隔

def get_old_content(filepath: str) -> str:
    """安全获取文件在 HEAD 中的内容。新文件或 git 不可用时返回空字符串。"""
    try:
        result = subprocess.run(
            ['git', 'show', f'HEAD:{filepath}'],
            capture_output=True, text=True, check=False, timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        return ''
    except Exception:
        return ''


def get_commit_message() -> str:
    """获取当前暂存区或最近一次 commit message。"""
    try:
        # 优先读取暂存区的 commit message（amend / commit --edit 场景）
        msg_file = '.git/COMMIT_EDITMSG'
        if os.path.exists(msg_file):
            with open(msg_file, 'r', encoding='utf-8') as f:
                return f.read()
        # 回退到 HEAD commit message
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%s%n%b'],
            capture_output=True, text=True, check=False, timeout=10
        )
        return result.stdout if result.returncode == 0 else ''
    except Exception:
        return ''


def get_changed_files() -> List[str]:
    """
    获取本次变更的文件列表。
    仅包含已暂存（staged）和已跟踪的工作区变更，不包含未跟踪文件。
    """
    files = set()
    try:
        # 暂存区变更
        r1 = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
            capture_output=True, text=True, check=False, timeout=10
        )
        if r1.returncode == 0:
            files.update(r1.stdout.strip().splitlines())

        # 已跟踪的工作区变更
        r2 = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=ACMR'],
            capture_output=True, text=True, check=False, timeout=10
        )
        if r2.returncode == 0:
            files.update(r2.stdout.strip().splitlines())

        # 注意：不包含未跟踪文件（git ls-files --others）
        # 未跟踪文件不应触发门禁，只有被 git add 后才进入暂存区检查
    except Exception:
        pass
    return [f for f in files if f]


def is_business_file(filepath: str) -> bool:
    """判断是否为需要检查的业务代码文件"""
    if not filepath.endswith('.py'):
        return False

    # 排除测试文件本身
    if 'test_' in Path(filepath).stem or filepath.startswith('tests/'):
        return False

    # 排除 __init__.py（纯导出）
    if Path(filepath).name == '__init__.py':
        return False

    # 必须在业务目录下
    parts = Path(filepath).parts
    if not parts:
        return False
    return parts[0] in BUSINESS_DIRS


# ============================================================================ 分隔
# 测试文件映射
# ============================================================================ 分隔

def get_expected_test_files(business_file: str) -> List[str]:
    """
    多级回退映射：根据业务文件路径推测可能的测试文件路径。
    按优先级排序，只要任一候选被修改即视为通过。
    """
    base = Path(business_file)
    stem = base.stem
    parent = base.parent
    clean_stem = stem.lstrip('_')

    candidates = [
        f"tests/{parent}/test_{clean_stem}.py",
        f"tests/unit/{parent}/test_{clean_stem}.py",
        f"tests/{parent}/test_{clean_stem}_handler.py",
        f"tests/unit/{parent}/test_{clean_stem}_handler.py",
        f"tests/test_{clean_stem}.py",
    ]

    # 去掉可能的 src/ 或 app/ 前缀，再映射到 tests/
    clean_parent = str(parent)
    for prefix in ['src/', 'app/']:
        if clean_parent.startswith(prefix):
            clean_parent = clean_parent[len(prefix):]
            candidates.append(f"tests/{clean_parent}/test_{clean_stem}.py")
            candidates.append(f"tests/unit/{clean_parent}/test_{clean_stem}.py")
            break

    # 去重保序
    seen = set()
    result = []
    for c in candidates:
        normalized = str(Path(c))
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


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

    # 新文件场景：所有 API 都是新增
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

    # 新增 API
    for name, info in new_apis.items():
        if name not in old_apis:
            info['change_reason'] = 'added'
            result[name] = info

    # 删除 API → 降级为警告级别（强制标记为 private，由后续逻辑处理为 WARNING）
    for name, info in old_apis.items():
        if name not in new_apis:
            info['change_reason'] = 'deleted'
            info['type'] = 'private'
            result[name] = info

    # 修改 API
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

def run_check(changed_files: Optional[List[str]] = None, commit_msg: Optional[str] = None) -> dict:
    """
    执行 G-013 门禁检查。
    返回 {'passed': bool, 'errors': [...], 'warnings': [...]}
    """
    if changed_files is None:
        changed_files = get_changed_files()
    if commit_msg is None:
        commit_msg = get_commit_message()

    errors = []
    warnings = []

    # --- 规则 0: Bug Fix 强制要求测试 ---
    is_bugfix = bool(BUGFIX_PATTERN.search(commit_msg))
    has_test_change = any('test' in f.lower() for f in changed_files)
    if is_bugfix and not has_test_change:
        errors.append(
            "[TEST-BLOCK] Bug 修复必须伴随测试用例的新增或修改 "
            "(commit message 包含 fix/bugfix/hotfix，但未检测到测试文件变更)"
        )

    # --- 规则 1: 业务代码变更检查 ---
    biz_files = [f for f in changed_files if is_business_file(f)]

    for biz_file in biz_files:
        old_content = get_old_content(biz_file)
        try:
            with open(biz_file, 'r', encoding='utf-8') as fh:
                new_content = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"[TEST-WARN] 无法读取文件 {biz_file}: {e}")
            continue

        changed_apis = has_functional_change(old_content, new_content)
        if not changed_apis:
            continue

        expected_tests = get_expected_test_files(biz_file)
        test_changed = any(t in changed_files for t in expected_tests)

        for api_name, info in changed_apis.items():
            api_type = info['type']
            reason = info['change_reason']

            # 删除 API 已降级为 private，此处会进入警告流程
            if api_type == 'public':
                if not test_changed:
                    errors.append(
                        f"[TEST-BLOCK] {biz_file} :: {api_name}() "
                        f"发生了功能变更 ({reason})，"
                        f"但未检测到对应测试文件变更。期望修改: {expected_tests}"
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
                            f"期望修改: {expected_tests}"
                        )
                else:
                    if not test_changed:
                        warnings.append(
                            f"[TEST-WARN] {biz_file} :: {api_name}() "
                            f"(私有) 发生了变更 ({reason})，建议补充测试。"
                        )

    passed = len(errors) == 0
    return {
        'passed': passed,
        'errors': errors,
        'warnings': warnings,
        'files_checked': len(biz_files),
        'is_bugfix': is_bugfix,
    }


# ============================================================================ 分隔
# CLI 入口
# ============================================================================ 分隔

def main():
    """CLI 入口：支持 --json 输出格式。"""
    output_format = 'text'
    if '--json' in sys.argv:
        output_format = 'json'

    result = run_check()

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
