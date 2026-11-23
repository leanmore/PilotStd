"""tests/test_csp_no_unsafe_eval.py — CSP 不得含 'unsafe-eval'（NEW-42，2026-11-23）。

背景：`docker/middleware.py` 的 CSP 原含 `script-src 'self' 'unsafe-eval'`，
注释理由是「PrimeVue + Vue 运行时需要 eval」。但本项目是 Vue 3 + Vite，
模板在**构建期预编译**成 render 函数，生产包不需要 `new Function` / `eval`。

实测（2026-11-23，`pnpm run build` 后 38 个 dist js 文件）：
    grep -c "new Function(" → 0

故移除 `'unsafe-eval'`：既不影响运行时，又消除「同源 SVG 上传 + unsafe-eval」
组合下的存储型 XSS 放大面（NEW-06）。

本测试锁住两条：
  1. CSP 头里没有 'unsafe-eval'
  2. 其余关键指令仍在（default-src / script-src / style-src / connect-src），
     防止有人为了过测试把整条 CSP 删掉
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docker" / "middleware.py"


def _source() -> str:
    return SRC.read_text(encoding="utf-8")


def test_no_unsafe_eval_in_csp():
    """CSP 指令块里不得包含 'unsafe-eval'。

    注意：docstring 里会引用 `'unsafe-eval'` 作为"已移除项"的说明，
    故只检查 CSP 指令块（从 Content-Security-Policy 到闭合 `)`），不扫全文。
    """
    src = _source()
    start = src.find("Content-Security-Policy")
    assert start > 0, "找不到 CSP 头定义"
    end = src.find(")", start)
    block = src[start:end]
    assert "'unsafe-eval'" not in block, "CSP 指令块不应再含 'unsafe-eval'（Vue 3 预编译不需要）"


def test_csp_keeps_essential_directives():
    """关键指令必须保留（防止为过测试删整条 CSP）。"""
    src = _source()
    for directive in ("default-src 'self'", "script-src 'self'", "style-src", "connect-src 'self'"):
        assert directive in src, f"CSP 缺少关键指令: {directive}"


def test_unsafe_inline_only_in_style_src():
    """'unsafe-inline' 只应出现在 style-src（script 侧不允许）。"""
    src = _source()
    # 取 CSP 字符串块（从 Content-Security-Policy 到下一个 )）
    start = src.find("Content-Security-Policy")
    assert start > 0
    end = src.find(")", start)
    block = src[start:end]
    assert "'unsafe-inline'" in block, "style-src 仍需要 unsafe-inline（Vue scoped style）"
    # 校验它只在 style-src 行
    for line in block.split("\n"):
        if "'unsafe-inline'" in line:
            assert "style-src" in line, f"unsafe-inline 出现在非 style-src 指令: {line.strip()}"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
