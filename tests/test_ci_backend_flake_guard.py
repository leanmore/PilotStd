"""NEW-47 静态契约：后端 CI 失败可诊断、可自愈一次，且不掩盖真失败。

背景（2026-11-26）：``test-backend`` 在 PR 上间歇性假红；Actions job 日志 API 404、
check-run 注解常为空 → 只能盲 rerun。本测试锁定 workflow 的四个关键结构：
1. ``Run backend tests`` 必须 ``continue-on-error: true``（否则重试机会不存在）；
2. 必须有 ``Retry failed backend tests once`` 且只在首跑失败时触发；
3. 重试必须**只跑失败用例**（junit 解析出 nodeid），而不是整跑一遍；
4. ``Backend failures summary`` 必须 ``if: always()`` 并写 ``$GITHUB_STEP_SUMMARY``
   （check-run 页面可见，不依赖 actions:read）。
"""

from __future__ import annotations

from pathlib import Path

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _job_text() -> str:
    text = CI.read_text(encoding="utf-8")
    start = text.index("  test-backend:")
    end = text.find("\n  # ═", start)
    return text[start : end if end > 0 else len(text)]


def test_backend_tests_step_tolerates_first_failure() -> None:
    job = _job_text()
    assert "id: backend-tests" in job
    assert "continue-on-error: true" in job


def test_retry_step_only_reruns_failed_tests() -> None:
    job = _job_text()
    assert "Retry failed backend tests once (flake guard)" in job
    assert "steps.backend-tests.outcome == 'failure'" in job
    assert "/tmp/failed_nodes.txt" in job, "重试必须基于 junit 解析出的失败 nodeid"
    assert "if [ ! -s /tmp/failed_nodes.txt ]" in job, "解析不到失败用例时必须显式失败（不掩盖）"


def test_failure_summary_is_always_visible() -> None:
    job = _job_text()
    assert "Backend failures summary" in job
    assert "GITHUB_STEP_SUMMARY" in job, "失败用例必须写入 step summary（check-run 页面可见）"
    # 旧实现是 if: failure()，在「首跑失败但重试通过」的 run 里永远不会执行
    idx = job.index("Backend failures summary")
    block = job[idx : idx + 200]
    assert "if: always()" in block, "summary 必须 always 运行"
