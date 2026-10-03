# tests/test_channel_spec.py
"""`channel_spec` 契约测试——渠道声明的自洽性与跨层一致性。

设计依据：docs/plans/notification-system-design/07-impl-design-A.md
- 本文件的断言**不重复 spec 的派生结果**（那会恒真），而是锚定：
  ① spec 自身的结构约束；② spec 与**字面量基线**的比对；③ spec 与外部事实的比对。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification.channel_spec import (  # noqa: E402
    CHANNEL_NAMES,
    CHANNEL_SPECS,
    FIELD_TYPES,
    masked_field_names,
    spec_for,
)

# 字面量基线（独立于 spec，用于检出 spec 内容的静默变更）
EXPECTED_FIELD_NAMES = {
    "wechat": {"webhook_url", "corpid", "agentid", "corpsecret", "proxy_url"},
    "dingtalk": {"webhook_url", "secret"},
    "feishu": {"webhook_url", "secret"},
    "telegram": {"bot_token", "chat_id"},
}
EXPECTED_CTOR = {
    "wechat": ("webhook_url",),
    "dingtalk": ("webhook_url", "secret"),
    "feishu": ("webhook_url", "secret"),
    "telegram": ("bot_token", "chat_id"),
}
EXPECTED_MASKED = {"webhook_url", "bot_token", "secret", "corpsecret"}


class TestSpecSelfConsistency(unittest.TestCase):
    """spec 自身的结构约束（唯一来源内部必须自洽）。"""

    def test_channel_names_derived_from_specs(self):
        """`CHANNEL_NAMES` 必须与声明的渠道名集合一致，且无重复。"""
        names = [s.name for s in CHANNEL_SPECS]
        self.assertEqual(len(names), len(set(names)), "渠道名不得重复")
        self.assertEqual(tuple(names), CHANNEL_NAMES)

    def test_field_names_unique_per_channel(self):
        """每个渠道的字段名不得重复（重复会让表单渲染两次同名字段）。"""
        for spec in CHANNEL_SPECS:
            names = [f.name for f in spec.fields]
            self.assertEqual(len(names), len(set(names)), f"{spec.name} 字段名重复")
            self.assertTrue(names, f"{spec.name} 字段集不得为空")

    def test_field_types_are_known(self):
        """字段控件形态必须取自闭集。"""
        for spec in CHANNEL_SPECS:
            for f in spec.fields:
                self.assertIn(f.type, FIELD_TYPES, f"{spec.name}.{f.name} 类型非法")

    def test_password_flag_matches_type(self):
        """`password` 必须与 `type` 自洽（避免两个字段各自漂移）。"""
        for spec in CHANNEL_SPECS:
            for f in spec.fields:
                expect = f.type in ("password", "text_password")
                self.assertEqual(f.password, expect, f"{spec.name}.{f.name} password 与 type 不一致")

    def test_ctor_refs_exist_in_fields(self):
        """构造参数与构造守卫必须引用真实存在的字段。"""
        for spec in CHANNEL_SPECS:
            names = {f.name for f in spec.fields}
            self.assertTrue(set(spec.ctor) <= names, f"{spec.name} ctor 引用了未声明字段")
            self.assertTrue(set(spec.ctor_required) <= set(spec.ctor), f"{spec.name} 守卫不在 ctor 内")

    def test_status_rule_branches_reference_real_fields(self):
        """状态判定的分支必须引用真实字段，且必须有兜底文案键。"""
        for spec in CHANNEL_SPECS:
            names = {f.name for f in spec.fields}
            self.assertTrue(spec.status_rule.branches, f"{spec.name} 缺少状态分支")
            for br in spec.status_rule.branches:
                self.assertTrue(set(br.all_of) <= names, f"{spec.name} 状态分支引用未声明字段")
            self.assertTrue(spec.status_rule.fallback_key)


class TestSpecLiteralBaseline(unittest.TestCase):
    """spec 与**字面量基线**的比对（spec 内容被静默改动即 FAIL）。"""

    def test_field_names_match_baseline(self):
        """字段集合必须等于基线（补齐 5 个字段后的既定形态）。"""
        for spec in CHANNEL_SPECS:
            got = {f.name for f in spec.fields}
            self.assertEqual(got, EXPECTED_FIELD_NAMES[spec.name], spec.name)

    def test_ctor_matches_baseline(self):
        """构造形态必须等于基线（R6 忠实保留既有调用形态）。"""
        for spec in CHANNEL_SPECS:
            self.assertEqual(spec.ctor, EXPECTED_CTOR[spec.name], spec.name)

    def test_masked_fields_match_baseline(self):
        """掩码字段集合必须等于既有硬编码四项（安全面零变更）。"""
        self.assertEqual(set(masked_field_names()), EXPECTED_MASKED)

    def test_mask_and_password_are_independent(self):
        """`mask` 与 `password` 不是同一集合——`webhook_url` 掩码但用明文控件。"""
        webhook = spec_for("wechat").fields[0]
        self.assertEqual(webhook.name, "webhook_url")
        self.assertTrue(webhook.mask, "webhook_url 必须在 API 响应中掩码")
        self.assertFalse(webhook.password, "webhook_url 的输入控件是明文 InputText")
        corpsecret = spec_for("wechat").fields[3]
        self.assertEqual(corpsecret.name, "corpsecret")
        self.assertTrue(corpsecret.mask)
        self.assertTrue(corpsecret.password)
        self.assertEqual(corpsecret.type, "text_password", "企微 corpsecret 是第三种控件形态")

    def test_english_labels_kept_english(self):
        """决策者裁决 N6：4 处标签保持英文字面量，不走 i18n 键。"""
        for ch, fname, literal in (
            ("wechat", "webhook_url", "Webhook URL"),
            ("dingtalk", "webhook_url", "Webhook URL"),
            ("feishu", "webhook_url", "Webhook URL"),
            ("telegram", "bot_token", "Bot Token"),
            ("telegram", "chat_id", "Chat ID"),
        ):
            f = next(x for x in spec_for(ch).fields if x.name == fname)
            self.assertEqual(f.label_key, "", f"{ch}.{fname} 不应有 i18n 键")
            self.assertEqual(f.label, literal, f"{ch}.{fname} 文案必须保持英文")


class TestLegacySchemaDerivation(unittest.TestCase):
    """`get_config_schema()` 由 spec 派生后的形状（兼容既有 ABC 契约）。"""

    def _labeler(self, key: str) -> str:
        return f"<{key}>"

    def test_schema_keys_equal_spec_fields(self):
        """schema 键集合必须等于 spec 字段集合（补齐 5 字段后的一致性）。"""
        from pilotstd.core.notification.channel_spec import legacy_schema

        for spec in CHANNEL_SPECS:
            keys = set(legacy_schema(spec, self._labeler))
            self.assertEqual(keys, {f.name for f in spec.fields}, spec.name)

    def test_schema_uses_password_as_secret_flag(self):
        """兼容形状的 `secret` 键取值为 `password`（控件形态），不是 `mask`。"""
        from pilotstd.core.notification.channel_spec import legacy_schema

        for spec in CHANNEL_SPECS:
            schema = legacy_schema(spec, self._labeler)
            for f in spec.fields:
                self.assertEqual(schema[f.name]["secret"], f.password, f"{spec.name}.{f.name}")

    def test_schema_required_matches_spec(self):
        """兼容形状的 `required` 必须与 spec 一致（含 wechat.webhook_url 的修正）。"""
        from pilotstd.core.notification.channel_spec import legacy_schema

        schema = legacy_schema(spec_for("wechat"), self._labeler)
        self.assertFalse(schema["webhook_url"]["required"], "企微 webhook_url 与自建应用二选一，非必填")
        self.assertTrue(legacy_schema(spec_for("telegram"), self._labeler)["bot_token"]["required"])


if __name__ == "__main__":
    unittest.main()
