"""CI 版本发布流程的静态契约（2026-11-25 两次真实故障的回归守卫）。

背景（都在生产 CI 上真实发生）：
1. 旧 `version` job 用 `GITHUB_TOKEN` **直推 main**，被 ruleset 拒绝后仍打 tag → 孤儿 tag + 版本号不递增；
2. 修复后首次发布又踩坑：`actions/checkout` 浅克隆下 `origin/main` 远端引用可能不存在，
   「防孤儿 tag」的 `git merge-base --is-ancestor HEAD origin/main` 拿到 unknown revision，
   把**正常发布**判失败 → docker 构建被跳过（无镜像）。

本测试只读 workflow YAML 文本，锁死这两条修复不再回退（CI 无法在单测里真的跑流水线）。
"""

from __future__ import annotations

from pathlib import Path

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _text() -> str:
    return CI.read_text(encoding="utf-8")


def test_version_job_never_pushes_commits_to_main() -> None:
    """`version` job 不得再直推 main（ruleset 要求 PR；旧实现导致孤儿 tag）。"""
    text = _text()
    # 旧的直推实现特征：commit 后 `git push` 到 main
    assert 'git commit -m "chore: bump version' not in text, "version job 不应再提交 bump 到 main"
    assert "- name: Commit version bump" not in text, "旧的 bump 提交步骤应已删除"


def test_tag_step_fetches_origin_main_before_ancestry_check() -> None:
    """打 tag 前必须 fetch origin/main（浅克隆下远端引用可能不存在）。"""
    text = _text()
    assert "git fetch --no-tags origin main:refs/remotes/origin/main" in text, (
        "tag 步骤缺少 fetch origin/main —— 浅克隆下 merge-base 会报 unknown revision"
    )
    assert "refs/remotes/origin/main" in text
    # 判定对象必须是 fetch 后的 refs/remotes/origin/main，而不是裸 origin/main
    assert 'git merge-base --is-ancestor "$HEAD_SHA" refs/remotes/origin/main' in text


def test_version_job_verifies_bumped_version() -> None:
    """version job 必须校验 VERSION 与提交计算值一致（bump 由 PR 内完成）。"""
    text = _text()
    assert "Verify VERSION bumped in PR" in text
    assert "scripts/bump_version.py --check" in text


def test_docker_build_depends_on_version_success() -> None:
    """docker 构建必须依赖 version 成功（版本一致才发镜像）。"""
    text = _text()
    idx = text.index("  docker:")
    segment = text[idx : idx + 400]
    assert "needs: version" in segment

def test_version_bump_gate_runs_only_on_pull_request() -> None:
    """版本号门禁只能挂在 PR 事件。

    push 到 main 时 `before..sha` 范围包含「已合并 PR 的 feat/fix 提交」，若在该事件强制
    「本范围必须改 VERSION」，每次正常 merge 都会被判失败（实测 main ea7b4db6 因此红、
    docker 被跳过）。push 路径由 version job 的 `bump_version.py --check` 校验一致性。
    """
    text = _text()
    idx = text.index("版本号 bump 校验")
    block = text[idx : idx + 500]
    assert "github.event_name == 'pull_request'" in block, "版本门禁缺少 PR 事件限定"


def test_tag_step_configures_committer_identity() -> None:
    """annotated tag 需要 tagger 身份（原 commit 步骤删除后身份配置丢失 → CI 上 tag 失败）。"""
    text = _text()
    idx = text.index("Create and push tag")
    block = text[idx : idx + 900]
    assert "git config user.name" in block, "tag 步骤缺少 committer 身份配置"
    assert "git config user.email" in block

