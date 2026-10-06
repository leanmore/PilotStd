"""P3 脱敏器单测（`pilotstd/core/notification/_redact.py`）。

判据全部是**性质断言**（脱敏后不含敏感片段），而非逐字比对掩码形态——
这样换一种等价的掩码写法不会误红，而"漏掉某类敏感信息"必然红。
"""

from __future__ import annotations

from pilotstd.core.notification._redact import redact_message


def test_url_query_and_fragment_are_removed() -> None:
    """带签名/会话参数的下载 URL ⇒ 只留 scheme://host/path。"""
    raw = "下载失败: https://example.com/dl/file.pdf?token=abcd1234&session=xyz#part1"
    out = redact_message(raw)
    assert "token=" not in out and "session=" not in out and "#part1" not in out
    assert "https://example.com/dl/file.pdf" in out


def test_absolute_paths_keep_only_tail() -> None:
    """Windows 与 POSIX 绝对路径都只保留末段（不泄露服务器目录结构）。"""
    win = redact_message(r"归档失败: C:\Users\alice\standards\GB1234.pdf 不存在")
    assert "C:\\" not in win and "alice" not in win
    assert "GB1234.pdf" in win

    posix = redact_message("规范化失败: /srv/pilotstd/data/incoming/GB9999.docx 解析异常")
    assert "/srv/pilotstd" not in posix
    assert "GB9999.docx" in posix


def test_long_tokens_and_hex_are_masked() -> None:
    """令牌样长串与长十六进制 ⇒ 一律掩码（不断言具体掩码字符，避免绑定实现）。"""
    token = "A" * 40
    hexish = "0123456789abcdef0123456789abcdef"
    out = redact_message(f"鉴权失败 token={token} id={hexish}")
    assert token not in out and hexish not in out


def test_email_and_phone_are_masked() -> None:
    """邮箱保留首字符与域名；大陆手机号整段掩码。"""
    out = redact_message("联系 alice@example.com 或 13800138000 处理")
    assert "alice@example.com" not in out
    assert "@example.com" in out
    assert "13800138000" not in out


def test_truncated_to_limit_with_ellipsis() -> None:
    """超长文本按上限截断并加省略号（默认 120，与 4 列口径一致）。

    注意用**短词重复**构造长文本：`"x" * 500` 会被"长令牌"规则先掩码成 `***`
    （首轮就踩到——这本身也证明令牌规则生效），那样测的就不是截断分支了。
    """
    out = redact_message("解析失败 " * 60)
    assert len(out) <= 121
    assert out.endswith("…")


def test_never_raises_and_handles_non_string() -> None:
    """非字符串/空值 ⇒ 空串（永不抛：失败明细是排障信息，不能因为格式脏而炸掉接口）。"""
    assert redact_message(None) == ""
    assert redact_message(123) == ""
    assert redact_message("   ") == ""
    assert redact_message({"a": 1}) == ""


def test_plain_text_passes_through() -> None:
    """无敏感片段的普通文本保持原样（不做无谓改写）。"""
    assert redact_message("源文件不存在") == "源文件不存在"
    assert redact_message("HTTP 404 Not Found") == "HTTP 404 Not Found"
