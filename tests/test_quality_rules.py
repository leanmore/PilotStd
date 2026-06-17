# tests/test_quality_rules.py
# 质量检查规则集成测试——验证所有规则可加载且正常运行

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all_rules_loadable():
    """验证所有8条规则能被运行器发现和加载"""
    from scripts.quality.runner import _discover_rules
    rules = _discover_rules()
    assert len(rules) >= 8, f"期望 >=8 条规则，实际发现 {len(rules)}"
    names = {r.name for r in rules}
    expected = {"dup_impl", "bypass_facade", "duplicate_code_block",
                "data_stage_field", "data_recompute", "raw_logger",
                "hardcoded_zh", "print_stderr"}
    missing = expected - names
    assert not missing, f"缺失规则: {missing}"


def test_all_rules_run_without_crash():
    """验证每条规则在真实项目上运行不崩溃"""
    from scripts.quality.runner import _discover_rules
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rule in _discover_rules():
        violations = rule.check(project_root)
        assert isinstance(violations, list), \
            f"规则 {rule.name} 应返回 list，实际返回 {type(violations)}"
        for v in violations:
            assert v.rule, f"违规记录缺少 rule 字段"
            assert v.file, f"违规记录缺少 file 字段"
            assert v.message, f"违规记录缺少 message 字段"


def test_dup_impl_production_clean():
    """验证 dup_impl 运行正常——生产代码应无未豁免的重复（当前已全修复）"""
    from scripts.quality.rules.dup_impl import DupImplRule
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rule = DupImplRule()
    violations = rule.check(project_root)
    prod = [v for v in violations if not v.file.startswith("tests")]
    # 生产代码违规已全部修复或加入白名单
    assert len(prod) == 0, \
        f"生产代码应无未豁免重复，实际 {len(prod)} 条: {[v.message[:60] for v in prod]}"


def test_raw_logger_finds_logging_getLogger():
    """验证 raw_logger 检测直接使用 logging.getLogger"""
    from scripts.quality.rules.raw_logger import RawLoggerRule
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rule = RawLoggerRule()
    violations = rule.check(project_root)
    assert isinstance(violations, list)
    # 检查违规结构
    for v in violations:
        assert "logging" in v.message.lower() or "LoggerManager" in v.suggestion
