"""tests/test_check_g_050_continue_break.py — G-050 识别 `except: continue|break`（2026-11-23）。

背景（06-full-inventory NEW-01）：G-050 原实现只认单语句 `pass` 与空 `return`，
**不认 `except: continue` / `except: break`**。但 `continue` 比 `pass` 更隐蔽 ——
它看起来像正常循环控制流，实际是"出错就跳过、什么都不说"。实测全仓 26 处这类吞错
完全不受棘轮保护。

本测试锁住四条边界：
  1. `except: continue` 必须被识别（原实现漏判）
  2. `except: break` 必须被识别（原实现漏判）
  3. **多语句 handler**（如先 log 再 continue）不算静默吞错（避免误报）
  4. 已有口径（pass / 空 return / logger.debug）不被破坏
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "check_g_050_silent_errors.py"


def _load():
    """以文件路径加载门禁模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location("check_g_050_silent_errors", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _write(repo: Path, rel: str, code: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")


def test_except_continue_is_detected(tmp_path):
    """`except: continue` 必须计入 continue 档（原实现漏判）。"""
    _write(
        tmp_path,
        "pilotstd/loop_continue.py",
        """
def f(items):
    for x in items:
        try:
            g(x)
        except ValueError:
            continue
""",
    )
    counts = m.scan(tmp_path)
    assert counts["continue"].get("pilotstd/loop_continue.py") == 1


def test_except_break_is_detected(tmp_path):
    """`except: break` 必须计入 break 档（原实现漏判）。"""
    _write(
        tmp_path,
        "pilotstd/loop_break.py",
        """
def f(items):
    for x in items:
        try:
            g(x)
        except OSError:
            break
""",
    )
    counts = m.scan(tmp_path)
    assert counts["break"].get("pilotstd/loop_break.py") == 1


def test_multi_statement_handler_not_counted(tmp_path):
    """多语句 handler（先 log 再 continue）不算静默吞错 —— 避免误报。"""
    _write(
        tmp_path,
        "pilotstd/loop_logged.py",
        """
def f(items):
    for x in items:
        try:
            g(x)
        except ValueError:
            logger.warning("skip %s", x)
            continue
""",
    )
    counts = m.scan(tmp_path)
    assert "pilotstd/loop_logged.py" not in counts["continue"]
    assert "pilotstd/loop_logged.py" not in counts["break"]


def test_existing_kinds_still_work(tmp_path):
    """已有口径不被破坏：pass / 空 return / logger.debug 仍然识别。"""
    _write(
        tmp_path,
        "pilotstd/legacy.py",
        """
def a():
    try:
        x()
    except Exception:
        pass

def b():
    try:
        y()
    except Exception:
        return None

def c():
    try:
        z()
    except Exception:
        logger.debug("detail")
""",
    )
    counts = m.scan(tmp_path)
    assert counts["pass"].get("pilotstd/legacy.py") == 1
    assert counts["return"].get("pilotstd/legacy.py") == 1
    assert counts["debug"].get("pilotstd/legacy.py") == 1
