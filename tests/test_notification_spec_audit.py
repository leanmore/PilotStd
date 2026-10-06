# tests/test_notification_spec_audit.py
"""G-045 **B 类**（渠道派生一致性）的判别力测试。

方法：在 `tmp_path` 下搭一棵**最小假树**，逐项注入一种漂移，断言对应检查**确实阻断**；
再对**真实仓库**跑一次，断言四项全通过。

**判别力关键**：假树里"spec 声明"与"渠道实现"是**两处独立写入**的文件，故 B1 不是
同源验证；B3/B4 同理锚在源码文本/AST 上。若哪天有人把 B 类改回"两个派生视图互相比对"，
注入漂移后本测试会**仍然通过**（因断言是"应阻断"）——故每个用例都**成对**断言
"注入 → 阻断" 与 "未注入 → 通过"。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _frontend_channel_scan import FRONTEND_FILES, found_keys  # noqa: E402
from _notification_spec_audit import (  # noqa: E402
    audit_spec_derivations,
    check_b1,
    check_b2,
    check_b3,
    check_b4,
)

# ── 最小假树的"正确"版本（两个渠道；声明与实现分处不同文件）──────────────────
GOOD_SPEC = '''"""假 spec（测试夹具）。"""

FIELD_TYPES = ("string", "password", "text_password")

CHANNEL_SPECS = (
    ChannelSpec(
        name="alpha",
        module="alpha",
        cls_name="AlphaChannel",
        ctor=("webhook_url",),
        ctor_required=("webhook_url",),
        fields=(
            FieldSpec(name="webhook_url", type="string", password=False, mask=True),
            FieldSpec(name="secret", type="password", password=True, mask=True),
        ),
    ),
    ChannelSpec(
        name="beta",
        module="beta",
        cls_name="BetaChannel",
        ctor=("webhook_url", "secret"),
        ctor_required=("webhook_url",),
        fields=(
            FieldSpec(name="webhook_url", type="string", password=False, mask=True),
            FieldSpec(name="secret", type="password", password=True, mask=True),
        ),
    ),
)
'''

GOOD_CHANNEL_ALPHA = """class AlphaChannel(NotificationChannel):
    pass
"""

GOOD_CHANNEL_BETA = """class BetaChannel(NotificationChannel):
    pass
"""

GOOD_MANAGER = """def _init_channels(self):
    for spec in CHANNEL_SPECS:
        self._channels[spec.name] = CHANNEL_CLASSES[spec.name](*spec.ctor)
"""

GOOD_API = """def test_channel(channel):
    if channel not in CHANNEL_NAMES:
        return {"ok": False}
"""

GOOD_VUE = """const CHANNELS = [
  { key: 'alpha', labelKey: 'notification.channel.alpha' },
  { key: 'beta', labelKey: 'notification.channel.beta' },
]
"""

# 注入用片段（提到模块级以避开 E501 超长行）
ROGUE_CHANNEL = "class RogueChannel(NotificationChannel):\n    pass\n"
SECRET_FIELD = 'FieldSpec(name="secret", type="password", password=True, mask=True),'
DUP_SECRET_FIELD = '            FieldSpec(name="secret", type="string"),'


def build_tree(tmp_path: Path, *, spec: str = GOOD_SPEC, alpha: str = GOOD_CHANNEL_ALPHA,
               beta: str = GOOD_CHANNEL_BETA, manager: str = GOOD_MANAGER,
               api: str = GOOD_API, vue: str | None = None) -> Path:
    """搭一棵最小假树：spec + 两个渠道实现 + 后端三文件 + 前端两文件。

    后端三文件＝`manager.py` + `docker/api/notification.py` + `docker/api/notification_config.py`
    ——后者于 2026-10-03 步 C 拆分后纳入 B3 扫描范围（渠道字面量落点随之迁移）。
    """
    notif = tmp_path / "pilotstd/core/notification"
    (notif / "channels").mkdir(parents=True)
    (notif / "channel_spec.py").write_text(spec, encoding="utf-8")
    (notif / "channels/alpha.py").write_text(alpha, encoding="utf-8")
    (notif / "channels/beta.py").write_text(beta, encoding="utf-8")
    (notif / "manager.py").write_text(manager, encoding="utf-8")
    api_dir = tmp_path / "docker/api"
    api_dir.mkdir(parents=True)
    (api_dir / "notification.py").write_text(api, encoding="utf-8")
    (api_dir / "notification_config.py").write_text(api, encoding="utf-8")
    front = tmp_path / FRONTEND_FILES[0]
    front.parent.mkdir(parents=True)
    front.write_text(vue if vue is not None else GOOD_VUE, encoding="utf-8")
    for rel in FRONTEND_FILES[1:]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// 空文件\n", encoding="utf-8")
    return tmp_path


def test_real_tree_all_passed():
    """真实仓库：B1-B5 应全部通过且无阻断（回归护栏）。

    **2026-10-05（阶段 4 · P6 · 4d 脚本侧）**：B 类由 4 项增至 **5 项**（新增 B5 类别层一致性）。
    """
    blocking, _warnings, states = audit_spec_derivations(ROOT)
    assert blocking == [], f"真实仓库不应有 B 类阻断：{blocking}"
    assert len([k for k in states if k.startswith("B") and "扫描" not in k]) == 5


class TestB1:
    """B1：声明类 vs 源码实际子类。"""

    def test_clean_tree_passes(self, tmp_path):
        blocking, _ = check_b1(build_tree(tmp_path))
        assert blocking == []

    def test_missing_implementation_blocks(self, tmp_path):
        """spec 声明了一个源码里不存在的类 -> 阻断。"""
        tree = build_tree(tmp_path, spec=GOOD_SPEC.replace("BetaChannel", "GhostChannel"))
        blocking, _ = check_b1(tree)
        assert blocking and "GhostChannel" in blocking[0]

    def test_extra_implementation_blocks(self, tmp_path):
        """源码多出一个未声明的子类 -> 阻断（新增渠道忘登记 spec 的场景）。"""
        tree = build_tree(tmp_path, alpha=GOOD_CHANNEL_ALPHA + "\n\n" + ROGUE_CHANNEL)
        blocking, _ = check_b1(tree)
        assert blocking and "RogueChannel" in blocking[0]


class TestB2:
    """B2：spec 自洽性。"""

    def test_clean_tree_passes(self, tmp_path):
        blocking, _ = check_b2(build_tree(tmp_path))
        assert blocking == []

    def test_duplicate_field_blocks(self, tmp_path):
        """同一渠道内字段名重复 -> 阻断（表单会渲染两次同名字段）。"""
        spec = GOOD_SPEC.replace(SECRET_FIELD, SECRET_FIELD + "\n" + DUP_SECRET_FIELD, 1)
        blocking, _ = check_b2(build_tree(tmp_path, spec=spec))
        assert any("重复" in b for b in blocking)

    def test_password_type_mismatch_blocks(self, tmp_path):
        tree = build_tree(tmp_path, spec=GOOD_SPEC.replace(
            'type="password", password=True', 'type="string", password=True'))
        blocking, _ = check_b2(tree)
        assert any("不自洽" in b for b in blocking)

    def test_bad_field_type_blocks(self, tmp_path):
        tree = build_tree(tmp_path, spec=GOOD_SPEC.replace('type="string"', 'type="mystery"'))
        blocking, _ = check_b2(tree)
        assert any("控件形态" in b for b in blocking)

    def test_ctor_referencing_unknown_field_blocks(self, tmp_path):
        tree = build_tree(tmp_path, spec=GOOD_SPEC.replace(
            'ctor=("webhook_url",),\n        ctor_required=("webhook_url",),',
            'ctor=("nonexistent",),\n        ctor_required=("webhook_url",),'))
        blocking, _ = check_b2(tree)
        assert any("ctor" in b for b in blocking)


class TestB3:
    """B3：后端不得残留渠道名字面量比较。"""

    def test_clean_tree_passes(self, tmp_path):
        blocking, _ = check_b3(build_tree(tmp_path))
        assert blocking == []

    def test_manager_channel_literal_blocks(self, tmp_path):
        """把渠道名写回 if/elif -> 阻断（回归到 C1 之前的写法）。"""
        tree = build_tree(tmp_path, manager=(
            'def _init_channels(self):\n    if spec.name == "alpha":\n        pass\n'))
        blocking, _ = check_b3(tree)
        assert blocking and "manager.py" in blocking[0]

    def test_api_channel_tuple_blocks(self, tmp_path):
        """`if channel not in ("alpha","beta")` 这类元组比较 -> 阻断。"""
        tree = build_tree(tmp_path, api=(
            'def test_channel(channel):\n    if channel not in ("alpha", "beta"):\n        return None\n'))
        blocking, _ = check_b3(tree)
        assert blocking and "notification.py" in blocking[0]


class TestB4:
    """B4：前端硬编码棘轮 + 渠道集合一致性。"""
    KEYS = {"alpha", "beta"}

    def test_unknown_frontend_channel_blocks(self, tmp_path):
        tree = build_tree(tmp_path, vue=(
            "const CHANNELS = [\n"
            "  { key: 'alpha', labelKey: 'notification.channel.alpha' },\n"
            "  { key: 'beta', labelKey: 'notification.channel.beta' },\n"
            "  { key: 'gamma', labelKey: 'notification.channel.gamma' },\n"
            "]\n"))
        blocking, _w, _s = check_b4(tree, self.KEYS)
        assert any("未知渠道键" in b for b in blocking)

    def test_frontend_set_mismatch_blocks(self, tmp_path):
        """前端只剩一个渠道（spec 有两个）-> 三层漂移，阻断。"""
        tree = build_tree(tmp_path, vue=(
            "const CHANNELS = [\n"
            "  { key: 'alpha', labelKey: 'notification.channel.alpha' },\n"
            "]\n"))
        blocking, _w, _s = check_b4(tree, self.KEYS)
        assert any("三层漂移" in b for b in blocking)

    def test_status_value_not_mistaken_for_channel(self, tmp_path):
        """块外的 `value: 'success'`（日志状态）不得被误判为未知渠道键。"""
        tree = build_tree(tmp_path, vue=(
            "const CHANNELS = [\n"
            "  { key: 'alpha' },\n"
            "  { key: 'beta' },\n"
            "]\n"
            "const statusOptions = [\n"
            "  { value: 'success' },\n"
            "  { value: 'failed' },\n"
            "]\n"))
        blocking, _w, _s = check_b4(tree, self.KEYS)
        # 该树的合法渠道字面量会命中棘轮（C3 后基线为 0），但**不得**被误判为未知渠道/集合漂移
        assert not any("未知渠道键" in b or "三层漂移" in b for b in blocking)

    def test_any_literal_blocks_when_baseline_zero(self, tmp_path):
        """C3 后基线为 0 ⇒ 全阻断：**任何**残留字面量都当场阻断（不再有存量放过）。"""
        tree = build_tree(tmp_path)
        blocking, _w, _s = check_b4(tree, self.KEYS)
        assert any("> 基线" in b for b in blocking)

    def test_baseline_mechanism_still_warns(self, tmp_path, monkeypatch):
        """棘轮机制本身仍可用：把基线抬到当前行数 ⇒ 只警告不阻断（缓阻断形态保留）。"""
        import _notification_spec_audit as audit

        tree = build_tree(tmp_path)
        monkeypatch.setattr(audit, "FRONTEND_LITERAL_BASELINE", 99)
        blocking, warnings, _s = check_b4(tree, self.KEYS)
        assert [b for b in blocking if "> 基线" in b] == []
        assert warnings and "缓阻断" in warnings[0]

    def test_over_baseline_blocks(self, tmp_path):
        """字面量超过基线（棘轮增量）-> 阻断。"""
        many = "\n".join(f"const c{i} = 'alpha'" for i in range(60))
        tree = build_tree(tmp_path, vue=many + "\n")
        blocking, _w, _s = check_b4(tree, self.KEYS)
        assert any("> 基线" in b for b in blocking)

    def test_i18n_key_alone_is_not_a_literal(self, tmp_path):
        """i18n 键里的渠道名不算硬编码（字符串级剥离，而非整行放行）。"""
        tree = build_tree(tmp_path, vue="const k = 'notification.channel.alpha'\n")
        found = found_keys(tree, sorted(self.KEYS))
        assert "alpha" not in found


def test_gate_exit_code_flips_on_b_class_blocking(monkeypatch):
    """V3 集成：B 类阻断项必须真的让**门禁退出码**变为 1（不只是检查函数返回非空）。"""
    import audit_notification_coverage as gate

    assert gate.main([]) == 0, "真实仓库上门禁应通过"
    monkeypatch.setattr(
        gate, "audit_spec_derivations", lambda root: (["[B1] 注入的假阻断项"], [], {})
    )
    assert gate.main([]) == 1, "注入 B 类阻断后门禁必须以 1 退出（否则 B 类形同虚设）"
