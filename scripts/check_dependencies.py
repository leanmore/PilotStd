#!/usr/bin/env python3
"""G-008: 依赖完整性检查 — 代码中 import 的第三方库是否在 requirements-docker.txt 中声明"""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Python 标准库（Python 3.12）
STDLIB = {
    "abc",
    "argparse",
    "array",
    "ast",
    "asyncio",
    "base64",
    "binascii",
    "bisect",
    "builtins",
    "bz2",
    "calendar",
    "cgi",
    "cgitb",
    "chunk",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "cProfile",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "distutils",
    "doctest",
    "email",
    "encodings",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "graphlib",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "imaplib",
    "imghdr",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "multiprocessing",
    "netrc",
    "nis",
    "numbers",
    "operator",
    "optparse",
    "os",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pipes",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "posixpath",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "spwd",
    "sqlite3",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "xml",
    "xmlrpc",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
    "zoneinfo",
    "__future__",
    "atexit",
    "pdb",
    "traceback",
    "unittest",
    # 项目内部模块
    "pilotstd",
    "docker",
    "tests",
    "scripts",
}

THIRD_PARTY_REMAP = {
    # pip 包名 vs import 名不一致的映射
    "PIL": "pillow",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "jose": "python-jose",
    "cv2": "opencv-python",
    "dateutil": "python-dateutil",
    "jwt": "pyjwt",
    "pydantic": "pydantic",
    "dotenv": "python-dotenv",
    "apscheduler": "apscheduler",
    "pytz": "pytz",
    "watchdog": "watchdog",
    "websocket": "websocket-client",
}

# GUI 专属依赖：仅在桌面环境中需要，Docker/CI 后端无需安装
GUI_ONLY_DEPS = {"PyQt6", "PyQt6-WebEngine"}


def extract_third_party_imports() -> set[str]:
    """遍历 pilotstd/ 和 docker/ 下的所有 Python 文件，提取第三方库导入名。"""
    imports: set[str] = set()
    for py_file in ROOT_DIR.glob("pilotstd/**/*.py"):
        _collect_imports(py_file, imports)
    for py_file in ROOT_DIR.glob("docker/**/*.py"):
        _collect_imports(py_file, imports)
    return imports


def _collect_imports(py_file: Path, imports: set[str]) -> None:
    """从单个 Python 文件中提取非标准库的 import 语句，追加到 imports 集合。"""
    try:
        content = py_file.read_text(encoding="utf-8")
    except Exception:
        return
    # import xxx / import xxx.yyy
    for m in re.finditer(r"^import\s+([a-zA-Z_][a-zA-Z0-9_]*)", content, re.MULTILINE):
        name = m.group(1)
        if name not in STDLIB:
            imports.add(name)
    # from xxx import yyy
    for m in re.finditer(r"^from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import", content, re.MULTILINE):
        name = m.group(1)
        if name not in STDLIB:
            imports.add(name)


def parse_requirements() -> set[str]:
    """解析 docker/requirements-docker.txt 及其 -r 引用的文件，返回所有声明的包名"""
    deps: set[str] = set()
    req_file = ROOT_DIR / "docker" / "requirements-docker.txt"
    _parse_file(req_file, deps)
    return deps


def _parse_file(filepath: Path, deps: set[str]) -> None:
    """递归解析 requirements 文件（支持 -r 引用）"""
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 处理 -r 引用
        if line.startswith("-r "):
            ref_name = line[3:].strip()
            ref_path = filepath.parent / ref_name
            if ref_path.exists():
                _parse_file(ref_path, deps)
            else:
                print(f"  警告: -r 引用文件不存在: {ref_path}")
            continue
        # 跳过其他特殊标记（-e 等）
        if line.startswith("-"):
            continue
        name = re.split(r"[=<>~]", line)[0].strip().lower()
        name = re.sub(r"\[.*\]", "", name)  # 去除 extras: python-jose[cryptography] → python-jose
        if name:
            deps.add(name)


def main() -> int:
    """入口：比较代码中实际 import 的第三方库与 requirements-docker.txt 声明的差异。"""
    imports = extract_third_party_imports()
    deps = parse_requirements()

    # 过滤 GUI 专属依赖
    imports = {imp for imp in imports if imp not in GUI_ONLY_DEPS}

    # 应用 remap
    resolved_imports: set[str] = set()
    unresolved: list[str] = []
    for imp in sorted(imports):
        if imp in THIRD_PARTY_REMAP:
            resolved_import = THIRD_PARTY_REMAP[imp]
            if resolved_import in deps:
                resolved_imports.add(resolved_import)
            else:
                unresolved.append(imp)
        elif imp in deps:
            resolved_imports.add(imp)
        else:
            unresolved.append(imp)

    if unresolved:
        print("FAIL: 以下依赖在代码中被引用但未在 requirements-docker.txt 中声明:")
        for u in unresolved:
            print(f"  - {u}")
        return 1

    print(f"PASS: 依赖完整性检查通过，共 {len(resolved_imports)} 个第三方依赖已全部声明")
    return 0


if __name__ == "__main__":
    sys.exit(main())
