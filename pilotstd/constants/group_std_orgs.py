# 模块：项目/常量/团体标准组织代码白名单
"""团体标准组织代码白名单（T/XXX 中的 XXX）。

初始为空集合（透传模式）：所有 T/XXX 均被 _exact_match_group 解析，不产生 warning。
初始化方式（可选）：应用启动或首次使用时，从 file_index 已有 T/% 记录提取组织代码：
    SELECT DISTINCT logical_code FROM file_index WHERE logical_code LIKE 'T/%'
    将 "T/XXX" 的 XXX 部分加入本集合。
若无法查询数据库，保持空集合即可（透传模式兜底）。
"""

group_std_orgs: set[str] = set()
