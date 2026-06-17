# pilotstd/core/file_utils.py — 文件工具：路径截断、安全移动/复制、文件名清理
# safe_move 改为先复制到临时文件再原子替换，防止跨文件系统移动中断导致数据丢失

import os
import re
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Windows 路径上限 260 字符，保留 20 字符给系统追加的后缀（如 ".tmp"、"(1)"）
MAX_PATH_LENGTH = 240


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符（Windows），不去除 Unicode 中文。"""
    forbidden = r'[<>:"/\\|?*]'
    return re.sub(forbidden, "", name).strip()


# 文件名中的垃圾推广后缀关键词——匹配到则截断丢弃
GARBAGE_SUFFIX_KEYWORDS = [
    "海川化工论坛", "原创力文档", "道客巴巴", "豆丁网", "百度文库",
    "人人文库", "淘豆网", "文档之家", "文档分享", "免费文档",
    "下载中心", "资料共享", "maxwid", "doc88", "docin",
]


def normalize_std_filename(filename: str) -> str:
    """文件名前置清洗，全链路统一入口。

    按顺序执行：Unicode 斜杠归一化 → 全角转半角 → 缺斜杠还原 →
    方括号/特殊符号清理 → 垃圾后缀截断 → 多余空格压缩。
    返回清洗后的文件名字符串（不含扩展名处理，由调用方负责）。
    """
    # 1. Unicode 斜杠 → ASCII /
    for ch in ('∕', '／', '⁄'):
        filename = filename.replace(ch, '/')

    # 2. 全角转半角（NFKC 归一化：全角字母/数字/符号 → 半角）
    import unicodedata
    filename = unicodedata.normalize('NFKC', filename)

    # 3. 缺斜杠还原（SHT→SH/T, GBT→GB/T, DB22T→DB22/T 等）
    #    在步骤1之后执行：如果文件名本来就有 /T，步骤1 已处理，此正则不会误匹配
    filename = re.sub(r'^(DB\d{2,4})([TZ])(?=\s*\d)', r'\1/\2', filename)
    filename = re.sub(r'^(GB)([TZ])(?=\s*\d)', r'\1/\2', filename)
    filename = re.sub(r'^(SH|NB|HG|JB|SY|YB|AQ|CJ|JG|JT|SC|LY|NY|QB|SN|WB|WS|WW|YY|ZB)([TZ])(?=\s*\d)', r'\1/\2', filename)

    # 4. 方括号/特殊符号 → 空格（保留（）用于语言标签检测）
    filename = re.sub(r'[\[\]【】]', ' ', filename)

    # 5. 垃圾后缀截断：匹配 [-_]关键词 模式，截断丢弃
    for kw in GARBAGE_SUFFIX_KEYWORDS:
        pattern = re.compile(r'[\s\-_]+' + re.escape(kw) + r'.*$', re.IGNORECASE)
        filename = pattern.sub('', filename)

    # 6. 多余空格压缩
    filename = re.sub(r'\s+', ' ', filename).strip()

    return filename


def safe_code_for_filename(logical_code: str) -> str:
    """将逻辑文件代号转为 Windows 安全文件名形式（去除 /）。"""
    code = logical_code.replace("/", "")
    return code


def truncate_path(root_dir: str, folder: str, filename: str) -> str:
    """若完整路径超过 MAX_PATH_LENGTH，截断文件名中的名称部分，保留编号和扩展名。"""
    full = os.path.join(root_dir, folder, filename)
    if len(full) <= MAX_PATH_LENGTH:
        return full

    base, ext = os.path.splitext(filename)
    reserve = len(root_dir) + len(folder) + len(ext) + len("...") + 2
    available = MAX_PATH_LENGTH - reserve
    if available < 10:
        available = 10
    truncated_name = base[:available] + "..." + ext
    return os.path.join(root_dir, folder, truncated_name)


def hash_file_content(path: str) -> str:
    """计算文件内容指纹用于去重比对。

    策略：≤1MB 全量哈希，>1MB 采样（前 1MB + 末 64KB + 文件大小）。
    文件大小参与哈希可区分类似前缀但后续内容不同的文件。
    扫描器与文件索引共享此函数，保证去重一致性。
    """
    import hashlib
    file_size = os.path.getsize(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if file_size <= 1024 * 1024:
            # 小文件：全量哈希
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        else:
            # 大文件：前 1MB + 末 64KB
            h.update(f.read(1024 * 1024))
            f.seek(-65536, os.SEEK_END)
            h.update(f.read(65536))
    h.update(str(file_size).encode())
    return h.hexdigest()


def _sha256_file(path: str) -> str:
    """计算文件 SHA-256，用于内容去重比对。
    保留旧名向后兼容，实际委托 hash_file_content()。
    """
    return hash_file_content(path)


def safe_move(src: str, dst: str, on_exists: str = "skip") -> bool:
    """安全移动文件：先复制到目标临时文件，再原子替换，最后删源文件。

    跨文件系统时 shutil.move 实际是"复制+删除"，非原子操作；
    改为 copy2 → .tmp → os.replace → 删源，任何一步失败都不会丢数据。

    on_exists:
        "skip" — 目标已存在时比 SHA-256：相同跳过，不同追加序号 (2)/(3)/...
        "overwrite" — 目标已存在则覆盖
    """
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            if on_exists == "overwrite":
                os.remove(dst)
            else:
                # 先比文件大小：大小不同则内容必然不同，跳过昂贵的全文件哈希
                if os.path.isfile(src) and os.path.isfile(dst):
                    if os.path.getsize(src) == os.path.getsize(dst):
                        if _sha256_file(src) == _sha256_file(dst):
                            logger.debug("目标已存在且内容相同，跳过: %s", dst)
                            return False
                # 内容不同或无法比对 → 追加序号
                base, ext = os.path.splitext(dst)
                for n in range(2, 100):
                    alt = f"{base} ({n}){ext}"
                    if not os.path.exists(alt):
                        dst = alt
                        break
                else:
                    logger.warning("无法生成唯一文件名(已达99): %s", dst)
                    return False
                logger.info("目标已存在但内容不同，改用: %s", dst)
        # 清除只读属性（跨盘符移动时只读文件会导致删除步骤失败）
        if os.path.isfile(src):
            import stat
            os.chmod(src, stat.S_IWRITE)
        # 复制到临时文件，完成后原子替换
        tmp_dst = dst + ".tmp"
        shutil.copy2(src, tmp_dst)
        os.replace(tmp_dst, dst)
        # 目标写入成功后才删除源文件
        os.remove(src)
        logger.info("移动成功: %s -> %s", src, dst)
        return True
    except OSError as e:
        # 清理可能残留的临时文件
        tmp_dst = dst + ".tmp"
        if os.path.exists(tmp_dst):
            try:
                os.remove(tmp_dst)
            except OSError:
                pass
        logger.error("移动失败: %s -> %s, 原因: %s", src, dst, e)
        return False


def safe_copy(src: str, dst: str) -> bool:
    """安全复制文件：自动创建目标目录，目标已存在则跳过。"""
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            logger.warning("目标已存在，跳过复制: %s", dst)
            return False
        shutil.copy2(src, dst)
        logger.info("复制成功: %s -> %s", src, dst)
        return True
    except OSError as e:
        logger.error("复制失败: %s -> %s, 原因: %s", src, dst, e)
        return False


def ensure_long_path(path: str) -> str:
    r"""Windows 长路径支持：添加 \\?\ 前缀（已有则跳过）。非 Windows 原样返回。"""
    if os.name == 'nt' and path and not path.startswith('\\\\?\\'):
        return '\\\\?\\' + os.path.abspath(path)
    return path


def strip_long_path(path: str) -> str:
    """去掉 Windows \\\\?\\ 长路径前缀（已有则去掉，没有则原样返回）。非 Windows 不作处理。"""
    if os.name == 'nt':
        _prefix = '\\\\?\\'
        if path.startswith(_prefix):
            return path[4:].lstrip('\\')
    return path


# 系统垃圾文件：目录中仅有这些文件时视为空目录，一并清理
_JUNK_FILES = frozenset({"Thumbs.db", "sync.ffs_db", "desktop.ini"})


def remove_empty_dirs(root: str) -> int:
    """自底向上删除所有空子目录，返回删除数量。不删除 root 本身。
    含系统垃圾文件（Thumbs.db/~$锁文件等）的目录也视为空目录处理。
    """
    # Windows 长路径支持
    if os.name == 'nt' and not root.startswith('\\\\?\\'):
        root = '\\\\?\\' + os.path.abspath(root)
    deleted = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if dirpath == root:
            continue
        # 过滤系统垃圾，仅余有效文件才判断是否为空
        real_files = [f for f in filenames
                      if f not in _JUNK_FILES and not f.startswith('~$')]
        if not real_files and not dirnames:
            # 先删除目录中的系统垃圾文件，再删目录
            for f in filenames:
                try:
                    os.remove(os.path.join(dirpath, f))
                except OSError:
                    pass
            try:
                os.rmdir(dirpath)
                deleted += 1
            except OSError:
                pass
    return deleted


def ensure_dir(path: str) -> str:
    """确保目录存在，返回规范化路径。"""
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def make_standard_filename(logical_code: str, number: int, year: int,
                           std_name: str = "", part: Optional[int] = None,
                           ext: str = ".pdf", num_suffix: str = "",
                           language: str = "", num_prefix: str = "",
                           file_kind: str = "") -> str:
    """根据标准信息生成规范文件名：{代号} {编号}[.{部分号}]-{年份} {名称}[ 语言][ file_kind].<ext>
    num_prefix 为罗马数字时直接作为编号显示，多字母前缀时加空格（如 'Spec 6D'）。"""
    win_code = safe_code_for_filename(logical_code)
    part_str = f".{part}" if part else ""
    name_part = f" {std_name}" if std_name else ""
    lang_part = f"({language})" if language else ""
    kind_part = f" {file_kind}" if file_kind else ""
    # 罗马数字前缀：直接用罗马数字替代阿拉伯数字
    if num_prefix and all(c in 'IVXLCDM' for c in num_prefix.upper()):
        num_str = f"{num_prefix}{num_suffix}"
    elif num_prefix and len(num_prefix) > 1 and num_prefix.isalpha():
        num_str = f"{num_prefix} {number}{num_suffix}"
    elif num_prefix:
        num_str = f"{num_prefix}{number}{num_suffix}"
    else:
        num_str = f"{number}{num_suffix}"
    return f"{win_code} {num_str}{part_str}-{year}{name_part}{lang_part}{kind_part}{ext}"
