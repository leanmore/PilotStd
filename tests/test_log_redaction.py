"""E1：日志不得输出密码/Token/API Key/Webhook 的值（静态文案允许）。"""

import ast
from pathlib import Path

ROOTS = [Path("docker/api"), Path("pilotstd/announcement"), Path("docker/auth.py")]
KEYWORDS = ("password", "token", "secret", "api_key", "apikey", "webhook", "authorization")


def _dangerous(arg, text: str) -> bool:
    snippet = (ast.get_source_segment(text, arg) or "").lower()
    if not any(k in snippet for k in KEYWORDS):
        return False
    # 纯静态文案（不含插值/变量）不算泄露
    return not isinstance(arg, ast.Constant)


def test_no_sensitive_values_in_logs():
    hits = []
    for root in ROOTS:
        paths = [root] if root.is_file() else list(root.rglob("*.py"))
        for p in paths:
            text = p.read_text(encoding="utf-8")
            tree = ast.parse(text)
            for n in ast.walk(tree):
                if isinstance(n, ast.Call):
                    is_log = isinstance(n.func, ast.Attribute) and n.func.attr in {
                        "debug", "info", "warning", "error", "exception", "critical"
                    }
                    is_print = isinstance(n.func, ast.Name) and n.func.id == "print"
                    if not (is_log or is_print):
                        continue
                    for a in n.args:
                        if _dangerous(a, text):
                            hits.append(f"{p}:{n.lineno}")
    assert hits == [], f"疑似敏感日志：{hits}"
