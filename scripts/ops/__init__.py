"""部署验证只读探测脚本包（`scripts/ops/`）。

模块职责：
  * `_probe_common`：凭据读取、只读 HTTP 客户端、结果汇总与退出码语义；
  * `probe_health`：版本 / schema / 服务健康；
  * `probe_pending_paths`：`mark_missing` 路径映射 + `/inbox` 挂载 + 端点存在性；
  * `probe_credentials`：通知渠道凭证齐全性 + 连通性（不发消息）；
  * `probe_db_counts`：统计表对账（只读 SQL）；
  * `probe_all`：一键跑全部并汇总。

用法见 `docs/ops/deploy-selfcheck.md`。所有脚本只读，退出码 0/1/2 见各模块 docstring。
"""

from __future__ import annotations

__all__: list[str] = []
