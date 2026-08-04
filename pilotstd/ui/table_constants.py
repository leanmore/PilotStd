# 模块：项目//_常量脚本
# 工作表列定义常量（从_混入脚本提取，_混入脚本即将删除）

WORK_COLUMNS = [
    "序号",
    "工作状态",
    "标准编号",
    "标准名称",
    "生效状态",
    "替代标准",
    "发布日期",
    "实施日期",
    "发布部门",
    "采标",
]
WORK_COLUMN_KEYS = [
    "col_seq",
    "col_work_status",
    "col_std_number",
    "col_std_name",
    "col_effect_status",
    "col_replaces",
    "col_publish_date",
    "col_impl_date",
    "col_responsible_dept",
    "col_adopted",
]
TOGGLEABLE_COLS = [4, 5, 6, 7, 8, 9]
