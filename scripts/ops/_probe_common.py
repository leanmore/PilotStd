#!/usr/bin/env python3
"""部署验证只读探测的共享层：凭据读取、HTTP 客户端、结果汇总与退出码语义。

设计要点（与仓库既有门禁脚本同一风格：中文 docstring + argparse + 明确退出码 + 失败不静默）：

  * **只读**：写方法（`POST` / `PUT` / `PATCH` / `DELETE`）默认被 `WriteBlockedError` 拦截；
    仅放行两个**不修改业务数据**的例外——登录换会话（`POST /api/login`）与只读 SQL 查询端点
    （`POST /query`，调用处强制校验语句必须是 `SELECT` / `PRAGMA` 且只允许单条）。放行表是
    白名单常量 `WRITE_ALLOWLIST`，新增例外必须在评审里写清「为什么它不改数据」。
  * **凭据**：`config/docker_creds.json` 含中文注释，**按行正则提取**，禁止整体 `json.loads`
    （`AGENTS.md` 明确要求）；任何输出都经 `mask_secret()` 脱敏，禁止打印密码/令牌。
  * **退出码**：0 全部通过；1 有失败项或「必跑项无法验证」；2 环境不可达（不计失败）。
  * `--json` 只向 stdout 输出单一 JSON 对象，便于 CI 消费；人读文本在非 `--json` 模式输出。

三档判定（`Check.status`）：
  * `pass` 通过；`fail` 明确不通过（阻断）；`unverified` 探测条件不足**无法验证**（不假装通过）；
  * `skip` 本环境不适用（不阻断）。`tier` 区分 `required`（阻断上线）与 `advisory`（诊断）。
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CREDS = ROOT / "config" / "docker_creds.json"
DEFAULT_BASE_URL = "http://192.168.1.18:9028"
# 探测脚本是命令行工具：日志直接打到 `stderr`，不用 `print`（G-005 口径）
logger = logging.getLogger("pilotstd.ops.probe")

# 退出码语义（与 `scripts/check_all.sh` 的 0/1 口径一致，新增 2 表示环境不可达）
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_UNREACHABLE = 2

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_UNVERIFIED = "unverified"
STATUS_SKIP = "skip"

TIER_REQUIRED = "required"
TIER_ADVISORY = "advisory"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# 服务端对密钥字段的回显掩码（与 `pilotstd/core/notification/_credentials.py` 的
# MASKED_VALUE / MASKED_VALUES 同口径；探测侧只做展示归一，不复用其加密逻辑）
MASKED_VALUE = "***"
MASKED_VALUES = {"***", "•••", "******", "MASKED_", "**********"}

# 写方法白名单：键是 (方法, 路径)，值是「为什么它不改业务数据」的理由（打印在阻断日志里）。
# 放行面必须极小；`POST /query` 由 `_assert_read_only_sql()` 在发送前逐条校验语句类型。
WRITE_ALLOWLIST: dict[tuple[str, str], str] = {
    ("POST", "/api/login"): "登录换取会话 cookie，只创建会话，不改业务数据",
    ("POST", "/query"): "只读 SQL 查询端点（强制单条 SELECT/PRAGMA）",
}

# 只读 SQL 的首关键字白名单
_READ_ONLY_SQL_KEYWORDS = ("SELECT", "PRAGMA", "EXPLAIN")
# 外部服务「只读 POST」白名单：键是 URL 前缀，值是「为什么它不改数据」的理由。
# 飞书取 tenant_access_token 只有 POST 形态，但它只签发令牌、不发消息、不改任何业务状态，
# 故单独放行；新增条目必须在评审里写清理由（与 WRITE_ALLOWLIST 同口径）。
EXTERNAL_READONLY_POST: dict[str, str] = {
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal": (
        "飞书 tenant_access_token：只签发令牌，不发消息、不改业务数据"
    ),
}
# 凭据文件里需要的字段（键名 → 正则捕获组），按行提取而不是整体解析 JSON
_CRED_FIELDS = ("base_url", "username", "password", "api_token")


class EnvironmentUnreachable(RuntimeError):
    """环境不可达（连接失败/超时）：退出码 2，**不计为探测失败**。"""


class WriteBlockedError(RuntimeError):
    """非白名单写方法被拦截：只读探测不得修改任何数据。"""


class AuthError(RuntimeError):
    """鉴权失败（401/403）：无法完成需要登录的探测，按「无法验证」处理并给出所需条件。"""


def mask_secret(value: str, keep: int = 2) -> str:
    """把密钥/令牌脱敏为 `ab***` 形式；空值原样返回空串。

    只保留前 `keep` 个字符用于人工核对来源（例如区分不同环境的凭据），其余一律替换为星号。
    若入参本身就是服务端掩码（`***` 等），直接归一为 `***`，避免出现 `*****` 这种歧义形态。
    """
    text = str(value or "")
    if not text:
        return ""
    if text in MASKED_VALUES:
        return MASKED_VALUE
    if len(text) <= keep:
        return MASKED_VALUE
    return text[:keep] + "***"


def _decode_creds_text(raw: bytes) -> str:
    """解码凭据文件：先按 `UTF-8`，失败再按 `GB18030`（历史文件带 GBK 注释）。"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # 仓库 `AGENTS.md`：该文件历史上含 GBK 注释，必须容错而不是直接崩
        return raw.decode("gb18030", errors="replace")


def _extract_cred(text: str, key: str) -> str:
    """按行正则提取单个字段值（不解析整体 JSON，避免注释导致解析失败）。"""
    match = re.search(r'"' + re.escape(key) + r'"\s*:\s*"([^"]*)"', text)
    return match.group(1) if match else ""


@dataclass
class Creds:
    """从凭据文件提取出的访问信息；`source` 记录来源路径，便于排查用了哪份凭据。"""

    base_url: str = ""
    username: str = ""
    password: str = ""
    api_token: str = ""
    source: str = ""

    def describe(self) -> str:
        """返回可直接打印的摘要（密码/令牌已脱敏）。"""
        return (
            f"凭据来源 {self.source or '未使用'}："
            f"base_url={self.base_url or '空'} "
            f"user={self.username or '空'} "
            f"password={mask_secret(self.password) or '空'} "
            f"api_token={mask_secret(self.api_token) or '空'}"
        )


def read_creds(path: Path | str | None = None) -> Creds:
    """读取 `config/docker_creds.json`（按行正则），返回 `Creds`；文件缺失返回空值。

    刻意**不做**整体 `json.loads`：该文件含中文注释，历史上解析失败过（`AGENTS.md` §一）。
    """
    target = Path(path) if path else DEFAULT_CREDS
    if not target.exists():
        return Creds(source=f"{target}（不存在）")
    text = _decode_creds_text(target.read_bytes())
    values = {key: _extract_cred(text, key) for key in _CRED_FIELDS}
    return Creds(source=str(target), **values)


def _assert_read_only_sql(sql: str) -> str:
    """校验只读 SQL：只允许单条 `SELECT` / `PRAGMA` / `EXPLAIN`，禁止多语句与写关键字。

    这是 `POST /query` 放行的唯一安全边界——探测脚本永远不该能借它写库。
    """
    text = str(sql or "").strip()
    if not text:
        raise WriteBlockedError("只读 SQL 校验失败：语句为空")
    head = text.split(None, 1)[0].upper()
    if head not in _READ_ONLY_SQL_KEYWORDS:
        raise WriteBlockedError(f"只读 SQL 校验失败：只允许 {_READ_ONLY_SQL_KEYWORDS}，实际 {head}")
    # 去掉结尾分号后不得再出现分号（多语句可借机夹带写操作）
    if ";" in text.rstrip(";"):
        raise WriteBlockedError("只读 SQL 校验失败：不允许一次提交多条语句")
    for keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "VACUUM"):
        if re.search(r"\b" + keyword + r"\b", text, re.IGNORECASE):
            raise WriteBlockedError(f"只读 SQL 校验失败：命中写关键字 {keyword}")
    return text


@dataclass
class ProbeOptions:
    """一次探测运行的公共参数（各 probe 的 `run()` 接收它，测试可直接构造）。"""

    base_url: str = DEFAULT_BASE_URL
    timeout: float = 10.0
    max_items: int = 20
    strict: bool = False
    include_advisory: bool = True
    # 允许把「渠道未启用且未配置」降级为诊断项：本部署确实不用该渠道时用它，
    # 默认关闭（未配置的必跑项一律算「无法验证」，不假装通过）。
    allow_unconfigured_channels: bool = False


class HttpClient:
    """极简只读 HTTP 客户端：唯一出口 `request()`，所有写方法在此处被拦截并记账。

    `session` 可注入（测试用假会话），因此本类不依赖真实网络；`calls` 记录全部
    `(方法, 路径)` 调用序列，测试据此断言「没有发出写请求」。
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        session: Any | None = None,
        creds: Creds | None = None,
    ) -> None:
        """构造客户端；`base_url` 末尾斜杠会被去掉，避免拼出双斜杠路径。"""
        self.base_url = str(base_url or "").rstrip("/")
        self.timeout = float(timeout)
        self.session = session if session is not None else requests.Session()
        self.creds = creds or Creds()
        self.calls: list[tuple[str, str]] = []
        self.logged_in = False

    # ── 出口与只读闸门 ──────────────────────────────────────

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """发送一次请求；非白名单写方法抛 `WriteBlockedError`（在发请求之前）。

        网络层异常统一转换为 `EnvironmentUnreachable`，并带上可读原因（不吞异常）。
        """
        verb = str(method or "GET").upper()
        if verb not in SAFE_METHODS:
            reason = WRITE_ALLOWLIST.get((verb, path))
            if reason is None:
                raise WriteBlockedError(
                    f"只读探测禁止 {verb} {path}（未在 WRITE_ALLOWLIST 中登记理由）"
                )
            if verb == "POST" and path == "/query":
                body = kwargs.get("json") or {}
                _assert_read_only_sql(str(body.get("sql") or ""))
        kwargs.setdefault("timeout", self.timeout)
        url = self.base_url + path
        self.calls.append((verb, path))
        try:
            return self.session.request(verb, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            # 连接失败/超时属于「环境不可达」，按退出码 2 处理，不伪装成探测失败
            raise EnvironmentUnreachable(
                f"环境不可达：{verb} {self.base_url}{path} 失败：{type(exc).__name__}: {exc}"
            ) from exc

    def get(self, path: str, **kwargs: Any) -> Any:
        """GET 快捷方式（只读）。"""
        return self.request("GET", path, **kwargs)

    def options(self, path: str, **kwargs: Any) -> Any:
        """OPTIONS 快捷方式：用于判断路由是否存在而不触发任何业务动作。"""
        return self.request("OPTIONS", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        """POST 快捷方式；仅白名单路径可用，其余立即抛 `WriteBlockedError`。"""
        return self.request("POST", path, **kwargs)

    # ── 便捷读取 ────────────────────────────────────────────

    def get_json(self, path: str, **kwargs: Any) -> tuple[int, Any]:
        """GET 并解析 JSON，返回 `(状态码, 载荷)`；解析失败返回 `(状态码, None)` 且不静默。

        非 2xx 时载荷为 `None`，由调用方按状态码判定（404/403 各有明确含义）。
        """
        response = self.get(path, **kwargs)
        return response.status_code, _safe_json(response)

    def csrf_headers(self) -> dict[str, str]:
        """从会话 cookie 取 CSRF 令牌并组装请求头（无令牌时返回空字典）。"""
        cookies = getattr(self.session, "cookies", None)
        token = ""
        if cookies is not None:
            token = str(cookies.get("csrf_token") or "")
        return {"X-CSRF-Token": token} if token else {}

    # ── 鉴权 ────────────────────────────────────────────────

    def login(self) -> tuple[int, str]:
        """用凭据文件里的账号密码登录，返回 `(状态码, 说明)`；失败不抛异常。

        登录是**唯一**允许的非只读语义请求（只创建会话），见 `WRITE_ALLOWLIST`。
        """
        if not (self.creds.username and self.creds.password):
            return 0, "凭据文件缺少 username/password，无法登录"
        response = self.post(
            "/api/login",
            data={"username": self.creds.username, "password": self.creds.password},
        )
        payload = _safe_json(response) or {}
        role = str(payload.get("role") or "")
        if response.status_code == 200 and payload.get("ok") is True:
            self.logged_in = True
            return 200, f"登录成功（用户 {payload.get('username') or '?'}，角色 {role or '?'}）"
        return response.status_code, f"登录失败：HTTP {response.status_code}，响应 {_brief(response)}"

    def require_admin(self) -> str:
        """确保已登录且角色为 `admin`，返回说明；否则抛 `AuthError`（调用方转「无法验证」）。"""
        status, detail = self.login()
        if status == 200 and "admin" in detail:
            return detail
        if status == 200:
            raise AuthError(f"{detail}；本探测需要 admin 角色")
        raise AuthError(detail)

    def write_calls(self) -> list[tuple[str, str]]:
        """返回本次运行实际发出的写方法调用（用于测试与报告自证只读）。"""
        return [(verb, path) for verb, path in self.calls if verb not in SAFE_METHODS]


class ExternalProbe:
    """外部服务（飞书/企微/Telegram）只读连通性探测：与 `HttpClient` 同一套只读闸门。

    与 `HttpClient` 的区别：目标不是 PilotStd 服务而是第三方 API，故单独一个出口，
    但仍复用 `EXTERNAL_READONLY_POST` 白名单与 `EnvironmentUnreachable` 语义。
    """

    def __init__(self, timeout: float = 10.0, session: Any | None = None) -> None:
        """构造外部探测客户端；`session` 可注入假会话（测试不联网）。"""
        self.timeout = float(timeout)
        self.session = session if session is not None else requests.Session()
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """发送外部请求；非白名单写方法抛 `WriteBlockedError`，网络异常转 `EnvironmentUnreachable`。"""
        verb = str(method or "GET").upper()
        if verb not in SAFE_METHODS and url not in EXTERNAL_READONLY_POST:
            raise WriteBlockedError(f"外部探测禁止 {verb} {url}（未登记只读理由）")
        kwargs.setdefault("timeout", self.timeout)
        self.calls.append((verb, url))
        try:
            return self.session.request(verb, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise EnvironmentUnreachable(
                f"{verb} {url} 失败：{type(exc).__name__}: {exc}"
            ) from exc

    def write_calls(self) -> list[tuple[str, str]]:
        """返回实际发出的写方法调用（测试据此断言「没有真的发消息」）。"""
        return [(verb, url) for verb, url in self.calls if verb not in SAFE_METHODS]


def _safe_json(response: Any) -> Any:
    """尽力解析响应 JSON；解析失败**留痕后**返回 `None`（不静默吞错，G-050 口径）。

    非 JSON 响应（例如 SPA 回退的 `index.html`）不是错误，交由调用方按状态码判定；
    但解析失败本身仍要记一条 WARNING，否则「服务端返回了 HTML 而不是 JSON」会被当成正常。
    """
    content_type = str(getattr(response, "headers", {}).get("content-type", ""))
    if "json" not in content_type.lower():
        logger.warning("响应不是 JSON（content-type=%r），按无载荷处理", content_type or "空")
        return None
    try:
        return response.json()
    except ValueError as exc:
        logger.warning("响应声明 JSON 但解析失败：%s", exc)
        return None


def _brief(response: Any, limit: int = 160) -> str:
    """截断响应文本，避免把整页 HTML 打到报告里。"""
    text = str(getattr(response, "text", "") or "").replace("\n", " ")
    return text[:limit]


@dataclass
class Check:
    """单条探测结论：名称、等级（必跑/诊断）、状态、人读说明与结构化证据。"""

    name: str
    tier: str
    status: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """转成可 JSON 序列化的字典（`evidence` 里禁止出现密钥，调用方负责脱敏）。"""
        return {
            "name": self.name,
            "tier": self.tier,
            "status": self.status,
            "detail": self.detail,
            "evidence": self.evidence,
        }


class Report:
    """一个 probe 的结果集合：负责汇总、渲染与退出码计算。"""

    def __init__(self, probe: str, base_url: str = "") -> None:
        """创建空报告；`probe` 是脚本标识（如 `health`），用于分组展示。"""
        self.probe = probe
        self.base_url = base_url
        self.checks: list[Check] = []
        self.unreachable_reason = ""

    def add(
        self,
        name: str,
        state: str,
        detail: str = "",
        tier: str = TIER_REQUIRED,
        **evidence: Any,
    ) -> Check:
        """追加一条结论并返回它（便于就地断言）；`evidence` 作为关键字参数传入。

        注意第二个形参叫 `state` 而不是 `status`：证据里经常要放 `status=...`（服务端返回的
        状态字段），同名会撞参数。
        """
        check = Check(name=name, tier=tier, status=state, detail=detail, evidence=dict(evidence))
        self.checks.append(check)
        return check

    def count(self, status: str) -> int:
        """统计某状态的条数。"""
        return sum(1 for check in self.checks if check.status == status)

    def blocking(self, strict: bool = False) -> list[Check]:
        """返回阻断项：必跑项失败/无法验证，`strict` 时诊断项失败也算阻断。"""
        result: list[Check] = []
        for check in self.checks:
            if check.status == STATUS_FAIL and (check.tier == TIER_REQUIRED or strict):
                result.append(check)
            elif check.status == STATUS_UNVERIFIED and check.tier == TIER_REQUIRED:
                result.append(check)
        return result

    def exit_code(self, strict: bool = False) -> int:
        """按阻断项计算退出码：有阻断 → 1；全部通过 → 0；环境不可达由调用方转 2。"""
        return EXIT_FAIL if self.blocking(strict) else EXIT_OK

    def as_dict(self, strict: bool = False) -> dict[str, Any]:
        """转成 JSON 结构；`exit_code` 与 `unreachable` 一并给出，便于 CI 直接消费。"""
        return {
            "probe": self.probe,
            "base_url": self.base_url,
            "unreachable": self.unreachable_reason,
            "exit_code": self.exit_code(strict),
            "counts": {
                STATUS_PASS: self.count(STATUS_PASS),
                STATUS_FAIL: self.count(STATUS_FAIL),
                STATUS_UNVERIFIED: self.count(STATUS_UNVERIFIED),
                STATUS_SKIP: self.count(STATUS_SKIP),
            },
            "checks": [check.as_dict() for check in self.checks],
        }

    def render(self, title: str = "") -> None:
        """把结论打印成人读表格（每行一条，含等级与证据摘要）。"""
        if title:
            print(f"=== {title} ===")
        for check in self.checks:
            tier = "必跑" if check.tier == TIER_REQUIRED else "诊断"
            print(f"[{check.status.upper():10s}] [{tier}] {check.name:32s} {check.detail}")
        if self.unreachable_reason:
            print(f"[UNREACHABLE] {self.unreachable_reason}")
        counts = (
            f"通过 {self.count(STATUS_PASS)} / 失败 {self.count(STATUS_FAIL)} / "
            f"无法验证 {self.count(STATUS_UNVERIFIED)} / 不适用 {self.count(STATUS_SKIP)}"
        )
        print(f"--- {self.probe}: {counts}")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """给子脚本统一加参数：`--base-url` / `--timeout` / `--creds` / `--json` / `--strict`。"""
    parser.add_argument(
        "--base-url",
        default="",
        help=f"被测服务地址（默认取凭据文件的 base_url，再退回 {DEFAULT_BASE_URL}）",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="单请求超时秒数（默认 10）")
    parser.add_argument("--creds", default=str(DEFAULT_CREDS), help="凭据文件路径")
    parser.add_argument("--json", action="store_true", help="只向 stdout 输出 JSON（CI 消费）")
    parser.add_argument("--strict", action="store_true", help="诊断项失败也计为阻断（默认否）")


def resolve_base_url(cli_value: str, creds: Creds) -> str:
    """确定被测地址：命令行 > 凭据文件 > 内置默认值；统一去掉末尾斜杠。"""
    for candidate in (cli_value, creds.base_url, DEFAULT_BASE_URL):
        if candidate and str(candidate).strip():
            return str(candidate).strip().rstrip("/")
    return DEFAULT_BASE_URL


def build_client(args: argparse.Namespace, session: Any | None = None) -> HttpClient:
    """按命令行参数构造 `HttpClient`（凭据已读入但**不打印**）。"""
    creds = read_creds(args.creds)
    base_url = resolve_base_url(getattr(args, "base_url", ""), creds)
    return HttpClient(base_url, timeout=args.timeout, session=session, creds=creds)


def finish(report: Report, args: argparse.Namespace, title: str = "") -> int:
    """统一收尾：按 `--json` 输出并返回退出码（供各 probe 的 `main()` 直接 `return`）。"""
    strict = bool(getattr(args, "strict", False))
    if getattr(args, "json", False):
        print(json.dumps(report.as_dict(strict), ensure_ascii=False, indent=2))
    else:
        report.render(title or f"{report.probe} 探测 @ {report.base_url}")
        code = report.exit_code(strict)
        print(f"退出码 {code}（0 通过 / 1 有失败或必跑项无法验证 / 2 环境不可达）")
    return report.exit_code(strict)


def stdout_utf8() -> None:
    """Windows 控制台默认编码无法输出部分中文/符号，统一切到 `UTF-8`（失败不致命）。"""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
