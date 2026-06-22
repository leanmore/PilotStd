#!/usr/bin/env bash
# scripts/extract_capabilities.sh — 从 Python 文件中提取非功能性能力清单
#
# 用法:
#     bash scripts/extract_capabilities.sh <Python文件路径>
#     bash scripts/extract_capabilities.sh tests/stress_driver.py
#
# 输出: Markdown 表格（类型 | 名称 | 位置），可直接粘贴到能力登记簿。

set -euo pipefail

FILE="$1"

if [ ! -f "$FILE" ]; then
    echo "❌ 文件不存在: $FILE" >&2
    exit 1
fi

# 转为绝对路径（跨平台兼容）
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) ABS_FILE="$(cd "$(dirname "$FILE")" && pwd -W)/$(basename "$FILE")" ;;
    *) ABS_FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")" ;;
esac

echo "## Capability Extraction: \`$FILE\`"
echo ""
echo "| 类型 | 名称 | 位置 |"
echo "|------|------|------|"

python -c "
import ast
import os
import sys

file_path = r'$ABS_FILE'
if not os.path.exists(file_path):
    # Fallback: try relative path from project root
    alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), r'$FILE')
    if os.path.exists(alt):
        file_path = alt
    else:
        print(f'| error | 文件无法读取 | {file_path} |')
        sys.exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    source = f.read()

try:
    tree = ast.parse(source)
except SyntaxError as e:
    print(f'| error | 语法error | {e} |')
    sys.exit(1)

lines = source.split('\n')

# 辅助：查找行号
def find_lineno(code_str, start_line=1):
    for i, line in enumerate(lines[start_line-1:], start=start_line):
        if code_str in line:
            return i
    return start_line

# 1. 顶层结构：class 和 def
for node in ast.iter_child_nodes(tree):
    if isinstance(node, ast.ClassDef):
        name = node.name
        lineno = node.lineno
        print(f'| class | \`{name}\` | \`$FILE:{lineno}\` |')
    elif isinstance(node, ast.FunctionDef):
        name = node.name
        lineno = node.lineno
        # 跳过私有双下划线方法
        if not name.startswith('__'):
            print(f'| function | \`{name}\` | \`$FILE:{lineno}\` |')

# 2. daemon-thread：遍历所有 Call 节点
class ThreadVisitor(ast.NodeVisitor):
    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            full = ''
            if isinstance(node.func.value, ast.Name):
                full = node.func.value.id + '.' + node.func.attr
            elif isinstance(node.func.value, ast.Attribute):
                full = self._get_attr_path(node.func.value) + '.' + node.func.attr
            if full in ('threading.Thread', 'threading.Timer'):
                lineno = node.lineno
                target = ''
                for kw in node.keywords:
                    if kw.arg == 'target':
                        if isinstance(kw.value, ast.Name):
                            target = kw.value.id
                        elif isinstance(kw.value, ast.Attribute):
                            target = self._get_attr_path(kw.value)
                label = f'Thread(target={target})' if target else 'Thread()'
                print(f'| daemon-thread | \`{label}\` | \`$FILE:{lineno}\` |')
            elif full == 'concurrent.futures.ThreadPoolExecutor':
                lineno = node.lineno
                print(f'| thread-pool | \`ThreadPoolExecutor()\` | \`$FILE:{lineno}\` |')
        elif isinstance(node.func, ast.Name):
            if node.func.id == 'QTimer':
                lineno = node.lineno
                print(f'| timer | \`QTimer()\` | \`$FILE:{lineno}\` |')
        self.generic_visit(node)

    def _get_attr_path(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attr_path(node.value) + '.' + node.attr
        return '?'

ThreadVisitor().visit(tree)

# 3. observability-log：遍历所有 Constant/JoinedStr 节点
class LogVisitor(ast.NodeVisitor):
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self._check_str(node.value, node.lineno)
        self.generic_visit(node)

    def visit_JoinedStr(self, node):
        # f-string: 提取静态部分
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                parts.append(val.value)
        combined = ''.join(parts)
        self._check_str(combined, node.lineno)
        self.generic_visit(node)

    def _check_str(self, s, lineno):
        markers = ['[PROGRESS]', '[HEARTBEAT]', '[STATS]', '[BUCKET]',
                   '[FUNNEL]', '[TIMELINE]', '[BASELINE]', '[CACHE]',
                   '[QUOTA]', '[SCORE]', '[ROTATOR]', '[COOLDOWN]',
                   '[OVERFLOW]', '[WATER]', '[CHAIN]', '[PENDING]',
                   '[RECOVERY]', '[CSRES]']
        for m in markers:
            if m in s:
                print(f'| observability-log | \`{m}\` | \`$FILE:{lineno}\` |')

LogVisitor().visit(tree)

# 4. 事件与生命周期
class EventVisitor(ast.NodeVisitor):
    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            full = ''
            if isinstance(node.func.value, ast.Name):
                full = node.func.value.id + '.' + node.func.attr
            elif isinstance(node.func.value, ast.Attribute):
                full = self._get_attr_path(node.func.value) + '.' + node.func.attr
            if full in ('threading.Event',):
                lineno = node.lineno
                print(f'| sync-event | \`threading.Event()\` | \`$FILE:{lineno}\` |')
            elif full == 'threading.Lock':
                lineno = node.lineno
                print(f'| sync-lock | \`threading.Lock()\` | \`$FILE:{lineno}\` |')
        elif isinstance(node.func, ast.Name):
            if node.func.id == 'atexit.register':
                lineno = node.lineno
                print(f'| atexit-cleanup | \`atexit.register()\` | \`$FILE:{lineno}\` |')
        self.generic_visit(node)

    def _get_attr_path(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attr_path(node.value) + '.' + node.attr
        return '?'

EventVisitor().visit(tree)
" 2>&1

echo ""
echo "✅ 提取完成"
