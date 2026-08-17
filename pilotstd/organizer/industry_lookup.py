# 模块：项目/归类/_脚本
# 行业代号 → 行业名称映射（依据附录一）

import os

# 基础代号 → 行业名称
INDUSTRY_MAP: dict[str, str] = {
    "AQ": "安全生产",
    "BB": "包装",
    "CB": "船舶",
    "CH": "测绘",
    "CJ": "城镇建设",
    "CY": "新闻出版",
    "DA": "档案",
    "DB": "地震",
    "DL": "电力",
    "DY": "电影",
    "DZ": "地质矿产",
    "EJ": "核工业",
    "FZ": "纺织",
    "GA": "公共安全",
    "GC": "国家物资储备",
    "GF": "国防工业",
    "GH": "供销合作",
    "GM": "国密",
    "GY": "广播电影电视",
    "HB": "航空",
    "HG": "化工",
    "HJ": "环境保护",
    "HS": "海关",
    "HY": "海洋",
    "JB": "机械",
    "JC": "建材",
    "JG": "建筑工程",
    "JR": "金融",
    "JS": "机关事务",
    "JT": "交通",
    "JY": "教育",
    "KA": "矿山安全",
    "LB": "旅游",
    "LD": "劳动和劳动安全",
    "LS": "粮食",
    "LY": "林业",
    "MH": "民用航空",
    "MR": "市场监管",
    "MT": "煤炭",
    "MZ": "民政",
    "NB": "能源",
    "NY": "农业",
    "QB": "轻工",
    "QC": "汽车",
    "QJ": "航天",
    "QX": "气象",
    "RB": "认证认可",
    "RF": "人民防空",
    "SB": "国内贸易",
    "SC": "水产",
    "SF": "司法",
    "SH": "石油化工",
    "SJ": "电子",
    "SL": "水利",
    "SN": "出入境检验检疫",
    "SW": "税务",
    "SY": "石油天然气",
    "TB": "铁路运输",
    "TD": "土地管理",
    "TY": "体育",
    "WB": "物资管理",
    "WH": "文化",
    "WJ": "兵工民品",
    "WM": "外经贸",
    "WS": "卫生",
    "WW": "文物保护",
    "XB": "稀土",
    "XF": "消防救援",
    "YB": "黑色冶金",
    "YC": "烟草",
    "YD": "通信",
    "YJ": "减灾救灾与综合性应急管理",
    "YS": "有色金属",
    "YY": "医药",
    "YZ": "邮政",
    "ZY": "中医药",
    # 补充行业标准（附录一未列但实际存在）
    "JGJ": "建筑工程",
    "JJF": "国家计量技术规范",
    "JJG": "国家计量检定规程",
    "TSG": "特种设备安全技术规范",
    "SHS": "石油化工设备维护检修规程",
    "JBZQ": "机械部重型机械企业标准",  # 已作废，改为 JB/T
    "NBSHT": "能源行业石油化工标准",  # NB/SH/T 组合前缀
    "HT": "化工/环保行业标准",  # 历史代号，现多转为行业标准
    "SHB": "石油化工行业标准",  # 历史石化部标准
    "SHJ": "旧版石化行业标准",  # 已废止，被 SH/SH/T 系列替代
    "WORD": "企业标准",  # 文件名含"WORD"字样，非独立标准代号
    "SG": "企业标准",  # 企业代号
    # 国际标准
    "ISO": "国际标准化组织",
    "IEC": "国际电工委员会",
    "ITU": "国际电信联盟",
    "CAC": "国际食品法典委员会",
    "WHO": "世界卫生组织",
    # 主要发达国家标准
    "ANSI": "美国国家标准学会",
    "ASME": "美国机械工程师学会",
    "ASTM": "美国材料与试验协会",
    "API": "美国石油学会",
    "UL": "美国保险商实验室",
    "MIL": "美国军用标准",
    "DIN": "德国标准化学会",
    "BS": "英国标准",
    "JIS": "日本工业标准",
    "GOST": "俄罗斯国家标准",
    # 区域性标准及其他
    "EN": "欧洲标准",
    "CSA": "加拿大标准协会",
    "NF": "法国标准",
    "MSS": "美国阀门及管件工业协会",
    "AWWA": "美国水工协会",
}

# 国家标准（无行业归属）
NATIONAL_CODES = {"GB", "GSB"}

# 国际/国外标准（无国内行业归属，目录名直接使用代号+组织名）
FOREIGN_CODES = {
    "ISO",
    "IEC",
    "ITU",
    "CAC",
    "WHO",
    "ANSI",
    "ASME",
    "ASTM",
    "API",
    "UL",
    "MIL",
    "DIN",
    "BS",
    "JIS",
    "GOST",
    "EN",
    "CSA",
    "NF",
    "MSS",
    "AWWA",
}

# 地方标准：数据库+行政区划代码→省级行政区名称（依据/2260）
_DB_PROVINCE_MAP = {
    "11": "北京",
    "12": "天津",
    "13": "河北",
    "14": "山西",
    "15": "内蒙古",
    "21": "辽宁",
    "22": "吉林",
    "23": "黑龙江",
    "31": "上海",
    "32": "江苏",
    "33": "浙江",
    "34": "安徽",
    "35": "福建",
    "36": "江西",
    "37": "山东",
    "41": "河南",
    "42": "湖北",
    "43": "湖南",
    "44": "广东",
    "45": "广西",
    "46": "海南",
    "50": "重庆",
    "51": "四川",
    "52": "贵州",
    "53": "云南",
    "54": "西藏",
    "61": "陕西",
    "62": "甘肃",
    "63": "青海",
    "64": "宁夏",
    "65": "新疆",
    "71": "台湾",
    "81": "香港",
    "82": "澳门",
}


def _extract_db_code(logical_code: str) -> str:
    """从地方标准逻辑代号中提取行政区划数字部分。DB 50/T → 50, DB3501 → 3501。"""
    import re

    m = re.match(r"^DB\s?(\d{2,4})", logical_code)
    return m.group(1) if m else ""


def is_db_code(logical_code: str) -> bool:
    """判断是否为地方标准代号（DB + 2~4位数字，可选 /T）。"""
    import re

    return bool(re.match(r"^DB\s?\d{2,4}(?:\s\d+)?(?:/T\d*)?$", logical_code))


def get_db_region(logical_code: str) -> str:
    """根据地方标准代号返回省级行政区名称。DB3501/T → 福建, DB11 → 北京。"""
    import re

    m = re.match(r"^DB\s?(\d{2})", logical_code)
    if m:
        return _DB_PROVINCE_MAP.get(m.group(1), "地方标准")
    return "地方标准"


def build_code_mapping() -> dict[str, str]:
    """为 StandardParser 生成 Windows 兼容代号 → 逻辑代号映射表。

    规则（spec 7.4）：
    - 推荐性标准: {代号}T → {代号}/T（如 GBT→GB/T, SHT→SH/T）
    - 强制性/其他标准: {代号} → {代号}（如 GB→GB）
    - 指导性技术文件: GBZ→GB/Z
    """
    mapping: dict[str, str] = {}
    for code in sorted(INDUSTRY_MAP):
        if code in FOREIGN_CODES:
            mapping[code] = code  # 国际标准无 /T 变体
        else:
            mapping[code] = code
            mapping[f"{code}T"] = f"{code}/T"
    mapping["GB"] = "GB"
    mapping["GBT"] = "GB/T"
    mapping["GBZ"] = "GB/Z"
    mapping["GSB"] = "GSB"
    # 地方标准：数据库+省级行政区划代码（市级由数据库正则运行时匹配）
    for province_code in _DB_PROVINCE_MAP:
        mapping[f"DB{province_code}"] = f"DB{province_code}"
        mapping[f"DB{province_code}T"] = f"DB{province_code}/T"
    return mapping


def get_base_code(logical_code: str) -> str:
    """从逻辑文件代号中提取基础代号。GB/T → GB, SH/T → SH, BS EN → BS"""
    base = logical_code.split("/")[0]
    # 历史变体统一归入主代号
    if base in ("SHB", "SHJ", "SHS"):
        return "SH"
    # 多段前缀：→,→
    if " " in base:
        first = base.split()[0]
        if first in FOREIGN_CODES:
            return first
    # 字母串复合前缀：→,→
    # 遍历已知代号，取最长前缀匹配（最具体的基础代号）
    best = None
    for code in INDUSTRY_MAP:
        if base.startswith(code) and len(code) < len(base):
            if best is None or len(code) > len(best):
                best = code
    if best:
        return best
    return base


def get_industry_name(base_code: str) -> str:
    """根据基础代号获取行业/组织名称。"""
    if not base_code:
        return "未分类"
    if base_code in NATIONAL_CODES:
        return "国家标准"
    if base_code in FOREIGN_CODES:
        return INDUSTRY_MAP.get(base_code, f"国外标准({base_code})")
    return INDUSTRY_MAP.get(base_code, f"未知行业({base_code})")


def get_folder_name(logical_code: str) -> str:
    """根据逻辑文件代号生成第二层目录名。国际标准直接使用代号，国内标准追加行业名。
    地方标准（DB + 数字）统一放入 DB 地方标准/省份 子目录。"""
    if not logical_code:
        return "未分类"
    # 地方标准:数据库11→数据库地方标准/北京11,数据库3501/→数据库地方标准/福建3501
    if is_db_code(logical_code):
        region = get_db_region(logical_code)
        code = _extract_db_code(logical_code)
        return f"DB 地方标准{os.sep}{region} {code}"
    base = get_base_code(logical_code)
    if base in FOREIGN_CODES:
        return f"{base} {INDUSTRY_MAP.get(base, '国外标准')}"
    name = get_industry_name(base)
    return f"{base} {name}"
