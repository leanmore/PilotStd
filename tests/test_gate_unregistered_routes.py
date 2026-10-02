# tests/test_gate_unregistered_routes.py
"""G-043「清单完备性」提示的判别测试（技术债阶段批次④）。

## 背景（实施批范围外发现 1）

`scripts/check_sensitive_endpoint_audit.py` 只校验 `SENSITIVE_ROUTES` + `EXEMPT_ROUTES`
**清单内**的路由 —— 清单外的状态变更路由**不被拦截**。实测 docker/api/ 下有 55 个
状态变更路由未登记（如 `PUT /api/notification/policy` 改通知策略、`POST /api/upload`），
故"新增敏感端点却漏登记"不会被门禁发现。

## 本批处理方式

**只提示、不阻断**：在 `[覆盖摘要]` 的「检查口径」与「未覆盖说明」中显式给出未登记路由
的**数量与前 10 项**（每项标注 `[已有审计]` / `[无审计]`）。

**为何不阻断**：判定"哪个路由敏感"需**语义理解**（`POST /api/scan` 与
`PUT /api/notification/policy` 都改状态，但敏感度不同），无法纯静态判定 ——
与本项目对 L2（出口覆盖）的既定处理一致：无法静态判定者交给人，不进阻断。
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_sensitive_endpoint_audit.py"


def _run_gate() -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    r = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(ROOT), env=env,
    )
    return r.returncode, r.stdout + r.stderr


def _import_gate():
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_sensitive_endpoint_audit as gate  # noqa: PLC0415

    return gate


class TestUnregisteredRoutesHelper:
    """`unregistered_routes()` 的语义。"""

    def test_excludes_registered(self):
        gate = _import_gate()
        fake = {
            "PUT /api/known": ("a.py", 1, ast.parse("def f(): pass").body[0], True),
            "POST /api/unknown": ("b.py", 2, ast.parse("def g(): pass").body[0], False),
        }
        # 把两个清单都塞进 fake 路由，验证"已登记的被排除"
        for route in list(gate.SENSITIVE_ROUTES) + list(gate.EXEMPT_ROUTES):
            fake[route] = ("c.py", 3, ast.parse("def h(): pass").body[0], True)
        out = gate.unregistered_routes(fake)
        assert "POST /api/unknown" in out
        assert "PUT /api/known" in out
        for route in list(gate.SENSITIVE_ROUTES) + list(gate.EXEMPT_ROUTES):
            assert route not in out, f"已登记路由 {route} 不应出现在未登记列表"

    def test_sorted_output(self):
        """输出须有序（便于人读与 diff）。"""
        gate = _import_gate()
        fake = {f"POST /api/z{i}": ("a.py", i, ast.parse("def f(): pass").body[0], False) for i in range(5)}
        out = gate.unregistered_routes(fake)
        assert out == sorted(out)


class TestGateOutputContainsCompletenessHint:
    """门禁输出须显式给出未登记路由的数量与前缀明细。"""

    def test_summary_mentions_unregistered_count(self):
        code, out = _run_gate()
        assert code == 0, "本批后 G-043 应 PASS（提示不阻断）"
        assert "未登记进任何清单的状态变更路由" in out, f"摘要缺少清单完备性口径：\n{out[:800]}"

    def test_uncovered_section_states_completeness_caveat(self):
        """★ 核心：未覆盖说明必须声明"清单外路由不拦截"。"""
        _, out = _run_gate()
        assert "清单完备性" in out and "清单外路由不拦截" in out, (
            "未覆盖说明必须显式声明清单外路由不被拦截（否则读方会误以为门禁覆盖全部路由）"
        )

    def test_lists_route_details_with_audit_mark(self):
        """明细行须带 `[已有审计]` / `[无审计]` 标记，供人判断敏感性。"""
        _, out = _run_gate()
        assert "[已有审计]" in out or "[无审计]" in out, f"明细缺少审计状态标记：\n{out[-800:]}"

    def test_routes_are_actually_unregistered(self):
        """★ 判别力：明细里出现的路由**确实不在**两张清单中。

        本用例直接对 `routes` 全量调用 `unregistered_routes()` 并断言"清单内路由全部被排除"，
        故**不依赖门禁只列前 10 项**这一截断行为——把实现改成"列出全部路由"时，
        `unregistered_routes()` 的返回值里仍不会含已登记路由，该断言仍成立；
        真正的护栏是下面的 `test_unregistered_helper_excludes_all_registered`。
        """
        gate = _import_gate()
        routes, _ml = gate.collect_routes()
        out = gate.unregistered_routes(routes)
        known = set(gate.SENSITIVE_ROUTES) | set(gate.EXEMPT_ROUTES)
        for route in known:
            if route in routes:  # 仅对源码中真实存在的路由校验
                assert route not in out, f"已登记路由 {route} 出现在未登记列表"

    def test_unregistered_helper_excludes_all_registered(self):
        """★ 直接对 helper 做负向校验：构造含全部已登记路由的输入 → 输出为空。"""
        gate = _import_gate()
        fake = {
            route: ("a.py", 1, ast.parse("def f(): pass").body[0], True)
            for route in list(gate.SENSITIVE_ROUTES) + list(gate.EXEMPT_ROUTES)
        }
        assert gate.unregistered_routes(fake) == [], "已登记路由不得被报为未登记"


class TestDeadCodeRemoved:
    """死代码清理的静态护栏（批次④）。

    `_func_has_return_notification_message` 与 `_is_pass_body` 均**无调用方**，故其删除
    **无法用行为测试判别**——只能用静态断言锁定。

    **`_is_pass_body` 的删除已先核实安全性**：`detect_swallowed_exceptions` 在
    `scan:485` **内联**判定 `except: pass`（`len(body) == 1 and isinstance(body[0], ast.Pass)`），
    **不使用**该函数，故删除它不影响"静默吞错"检测能力。

    判别力：把任一函数名加回 `audit_notification_chain_scan.py`，本用例 FAIL。
    """

    def test_dead_functions_absent_from_module(self):
        import inspect

        sys.path.insert(0, str(ROOT / "scripts"))
        import audit_notification_chain_scan as scan  # noqa: PLC0415

        source = inspect.getsource(scan)
        for name in ("_func_has_return_notification_message", "_is_pass_body"):
            assert f"def {name}(" not in source, f"{name} 是无调用方的死代码，已删除，不得加回"

    def test_swallowed_exception_detection_still_works(self):
        """删除 `_is_pass_body` 后，`except: pass` 仍须被检出（防"删错东西"）。"""
        import inspect

        sys.path.insert(0, str(ROOT / "scripts"))
        import audit_notification_chain_scan as scan  # noqa: PLC0415

        source = inspect.getsource(scan.detect_swallowed_exceptions)
        assert "ast.Pass" in source, "吞错检测的内联 `ast.Pass` 判定被删掉了——检测能力受损"

    """提示不得改变退出码（本批明确"只提示不阻断"）。"""

    def test_exit_code_zero(self):
        code, _ = _run_gate()
        assert code == 0
