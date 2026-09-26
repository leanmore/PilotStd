# 模块：项目/查询/适配器/_共享_SSL 脚本
"""查询适配器共享的 SSL context（进程级单例，避免重复加载 CA 证书包）。

**为什么需要这个模块**（2026-09-26 实测）：httpx 在 `verify=True`（默认）时会为
**每一个** `Client` 调 `ssl.create_default_context()` → `load_verify_locations()`
重新解析加载整份 CA 包；本机单次构造 `httpx.Client(verify=True)` 中位 **1.295s**，
其中 96.5% 花在 `load_verify_locations`。`pilotstd/query/adapters/` 下 12 个适配器
逐个构造 Client，其中 **9 个**走默认校验分支 → `StandardManager()` 每次构造白付
≈6.7s（实测中位，改前），而生产侧有 **12 处** `StandardManager()` 构造点，交互型操作
（点一次查询/收藏）会直接卡住界面（技术债 #22）。

**做法：只共享 SSL context，不共享 httpx.Client。** Client 带会话状态（cookie、
连接池、代理配置），多适配器共用会串会话；而 context 是无状态的可复用对象，httpx 的
`_config.create_ssl_context()` 对 `isinstance(verify, ssl.SSLContext)` 直接 return，
因此传 context 后既不新建 context 也不加载 CA（实测单次构造 1.295s → 0.001s）。

**分档**：默认校验的 9 处传本 context；`energy.py` / `sppt.py` / `sppt_local.py`
三处是自签名站点，**有意** `verify=False`（httpx 该分支本就不加载 CA），保持原样。

**不要**改成共享 `httpx.Client`，也不要给 `verify=False` 的站点传本 context
（那会把它们的自签名豁免改成强制校验，直接连不上）。
"""

import ssl
import threading

# 进程级单例 + 锁：证书包加载昂贵（本机实测 ≈1.3s），加锁保证并发首次调用也只加载一次
_CONTEXT: ssl.SSLContext | None = None
_LOCK = threading.Lock()


def default_ssl_context() -> ssl.SSLContext:
    """返回进程级共享的默认校验 SSL context（首次调用时才加载 CA，之后零成本复用）。"""
    global _CONTEXT
    if _CONTEXT is None:
        with _LOCK:
            if _CONTEXT is None:
                _CONTEXT = ssl.create_default_context()
    return _CONTEXT
