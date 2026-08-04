# 模块：项目/核心/_工具脚本
# 29:统一导出文件名生成—批次固定时间戳+18名称
import datetime


def generate_export_batch_timestamp() -> str:
    """每次新批次开始时调用，返回固定时间戳字符串。"""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def get_export_filename(translated_name: str, timestamp: str, ext: str = ".csv") -> str:
    """生成导出文件名。空格自动替换为下划线，确保跨平台兼容。"""
    safe_name = translated_name.replace(" ", "_")
    return f"{safe_name}_{timestamp}{ext}"
