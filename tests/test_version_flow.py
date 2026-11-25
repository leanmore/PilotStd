"""版本号流程（PR 内 bump + CI 校验 + 安全打 tag）的回归测试（2026-11-25）。

背景：main 受 ruleset 保护 → CI 直推 bump 提交被拒 → 旧实现吞掉失败后仍打 tag，
形成孤儿 tag 且 VERSION 永不递增。修复后由 `scripts/bump_version.py` 在 PR 内 bump，
`scripts/check_version_bump.py` 在 CI 校验。本测试锁定：

1. 纯函数：`compute_next` 的 semver 规则（feat/fix/BREAKING/无匹配）；
2. 门禁：范围内有 feat/fix 但未改 VERSION → 退出码 1；改了 VERSION → 0；
3. 无 feature/fix 的范围内不需要 bump。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bump_version  # noqa: E402
import check_version_bump  # noqa: E402


class TestComputeNext:
    def test_feat_bumps_minor(self) -> None:
        assert bump_version.compute_next("1.2.3", ["feat(ui): 新增某控件"]) == "1.3.0"

    def test_fix_bumps_patch(self) -> None:
        assert bump_version.compute_next("1.2.3", ["fix(status): 修过滤器"]) == "1.2.4"

    def test_breaking_bumps_major(self) -> None:
        assert bump_version.compute_next("1.2.3", ["chore: x\n\nBREAKING CHANGE: 重构"]) == "2.0.0"

    def test_no_bump_for_chore_only(self) -> None:
        assert bump_version.compute_next("1.2.3", ["docs: 改文档", "chore: 杂项"]) is None

    def test_bom_prefix_is_stripped(self) -> None:
        # 历史事故：UTF-8 BOM 吞掉 `fix:` 前缀导致版本不升
        assert bump_version.compute_next("1.2.3", ["\ufefffix(x): y"]) == "1.2.4"


class TestCommitTypeRegex:
    def test_matches_feat_and_fix(self) -> None:
        assert check_version_bump.BUMP_TYPES.match("feat: a")
        assert check_version_bump.BUMP_TYPES.match("fix(x): a")
        assert check_version_bump.BUMP_TYPES.match("@ feat: a")

    def test_does_not_match_chore_docs(self) -> None:
        assert not check_version_bump.BUMP_TYPES.match("chore: a")
        assert not check_version_bump.BUMP_TYPES.match("docs: a")
        assert not check_version_bump.BUMP_TYPES.match("refactor: a")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_check(repo: Path, rng: str, out_dir: Path) -> int:
    """用文件重定向跑门禁脚本（受限环境不可用管道），返回退出码。"""
    out = out_dir / "out.txt"
    err = out_dir / "err.txt"
    env = dict(__import__("os").environ)
    env["VERSION_CHECK_ROOT"] = str(repo)
    with out.open("w", encoding="utf-8") as o, err.open("w", encoding="utf-8") as e:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "check_version_bump.py"), "--range", rng],
            cwd=str(repo),
            env=env,
            stdout=o,
            stderr=e,
            timeout=120,
        )
    return proc.returncode


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: init")


def test_check_fails_when_fix_without_version_bump(tmp_path: Path) -> None:
    repo = tmp_path / "r1"
    repo.mkdir()
    _init_repo(repo)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix(core): 修一个缺陷")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    assert _run_check(repo, f"{base}..{head}", tmp_path) == 1


def test_check_passes_when_fix_bumps_version(tmp_path: Path) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    _init_repo(repo)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix(core): 修一个缺陷")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    assert _run_check(repo, f"{base}..{head}", tmp_path) == 0


def test_check_passes_for_docs_only_range(tmp_path: Path) -> None:
    repo = tmp_path / "r3"
    repo.mkdir()
    _init_repo(repo)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    (repo / "doc.md").write_text("d\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs: 只改文档")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
    ).stdout.strip()
    assert _run_check(repo, f"{base}..{head}", tmp_path) == 0

def test_infra_scopes_do_not_require_version_bump(tmp_path) -> None:  # noqa: ANN001
    """``fix(ci|docs|test|build):`` 属基础设施修复，不触发行版本 bump。"""
    repo = tmp_path / "r_infra"
    repo.mkdir()
    _init_repo(repo)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    (repo / "ci.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "fix(ci): 只改流水线")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    assert _run_check(repo, f"{base}..{head}", tmp_path) == 0


def test_ops_scope_does_not_require_bump(tmp_path) -> None:  # noqa: ANN001
    """``feat(ops):`` 属运维/工具链改动（scripts/ops 等），不改变运行时行为，不触发版本 bump。"""
    repo = tmp_path / "r_ops"
    repo.mkdir()
    _init_repo(repo)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    (repo / "probe.py").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat(ops): 新增只读验收脚本")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True).stdout.strip()
    assert _run_check(repo, f"{base}..{head}", tmp_path) == 0
