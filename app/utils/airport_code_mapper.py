"""
机场三字码到城市简称映射工具模块

用于将机场三字码（如"TNA"）转换为城市简称（如"济南"）
"""

# 三字码到城市简称的映射
AIRPORT_CODE_TO_CITY = {
    # 北京
    "PEK": "首都",
    "PKX": "大兴",
    # 华北地区
    "TSN": "天津",
    "SJW": "石家庄",
    "TVS": "唐山",
    "BPE": "秦皇岛",
    "HDG": "邯郸",
    "ZQZ": "张家口",
    "CDE": "承德",
    # 山西
    "TYN": "太原",
    "CIH": "长治",
    "DAT": "大同",
    "LFQ": "临汾",
    "YCU": "运城",
    "WUT": "忻州",
    "LLV": "吕梁",
    # 内蒙古
    "HET": "呼和浩特",
    "XIL": "锡林浩特",
    "BAV": "包头",
    "HLD": "海拉尔",
    "WUA": "乌海",
    "CIF": "赤峰",
    "NHZ": "满洲里",
    "TGO": "通辽",
    "DSN": "鄂尔多斯",
    # 东北地区
    "SHE": "沈阳",
    "DDG": "丹东",
    "YKH": "营口",
    "AOG": "鞍山",
    "DLC": "大连",
    "CGQ": "长春",
    "NBS": "长白山",
    "YNJ": "延吉",
    "TNH": "通化",
    "HRB": "哈尔滨",
    "HEK": "黑河",
    "NDG": "齐齐哈尔",
    "JXA": "鸡西",
    "MDG": "牡丹江",
    "OHE": "漠河",
    "JMU": "佳木斯",
    "DQA": "大庆",
    # 上海
    "SHA": "虹桥",
    "PVG": "浦东",
    # 江苏
    "NKG": "南京",
    "LYG": "连云港",
    "WUX": "无锡",
    "HIA": "淮安",
    "CZX": "常州",
    "AZJ": "镇江",
    "NTG": "南通",
    "YNZ": "盐城",
    "YTY": "扬州",
    "XUZ": "徐州",
    # 浙江
    "HGH": "杭州",
    "WNZ": "温州",
    "NGB": "宁波",
    "YIW": "义乌",
    "HSN": "舟山",
    "HYN": "台州",
    "JUZ": "衢州",
    # 安徽
    "HFE": "合肥",
    "FUG": "阜阳",
    "TXN": "黄山",
    "AQG": "安庆",
    "WHA": "芜湖",
    "JUH": "池州",
    # 山东
    "TNA": "济南",
    "TAO": "青岛",
    "YNT": "烟台",
    "DOY": "东营",
    "WEF": "潍坊",
    "JNG": "济宁",
    "WEH": "威海",
    "RIZ": "日照",
    # 江西
    "KHN": "南昌",
    "JGS": "吉安",
    "JDZ": "景德镇",
    "SQD": "上饶",
    "YIC": "宜春",
    "JIU": "九江",
    # 福建
    "FOC": "福州",
    "XMN": "厦门",
    "JJN": "晋江",
    "WUS": "武夷山",
    "LCX": "龙岩",
    # 广东
    "CAN": "广州",
    "SZX": "深圳",
    "ZUH": "珠海",
    "SWA": "揭阳",
    "ZHA": "湛江",
    "HSC": "韶关",
    "MXZ": "梅州",
    "HUZ": "惠州",
    "FUO": "佛山",
    # 广西
    "NNG": "南宁",
    "KWL": "桂林",
    "LZH": "柳州",
    "BHY": "北海",
    "WUZ": "梧州",
    "AEB": "百色",
    "YLX": "玉林",
    "HCJ": "河池",
    # 海南
    "HAK": "海口",
    "SYX": "三亚",
    # 河南
    "CGO": "郑州",
    "LYA": "洛阳",
    "NNY": "南阳",
    "XAI": "信阳",
    # 湖南
    "CSX": "长沙",
    "DYG": "张家界",
    "CGD": "常德",
    "HNY": "衡阳",
    "YYA": "岳阳",
    "HJJ": "怀化",
    "WGN": "邵阳",
    "LLF": "永州",
    "HCZ": "郴州",
    # 湖北
    "WUH": "武汉",
    "YIH": "宜昌",
    "XFN": "襄阳",
    "ENH": "恩施",
    "WDS": "十堰",
    "SHS": "荆州",
    "EHU": "鄂州",
    # 重庆
    "CKG": "重庆",
    # 四川
    "CTU": "成都双流",
    "TFU": "成都天府",
    "MIG": "绵阳",
    "NAO": "南充",
    "YBP": "宜宾",
    "DZH": "达州",
    "PZI": "攀枝花",
    "DCY": "稻城",
    "GYS": "广元",
    "BZX": "巴中",
    "KGT": "甘孜",
    "LZO": "泸州",
    # 云南
    "KMG": "昆明",
    "LJG": "丽江",
    "JHG": "西双版纳",
    "DLU": "大理",
    "TCZ": "腾冲",
    "DIG": "香格里拉",
    "SYM": "普洱",
    "LNJ": "临沧",
    "ZAT": "邵通",
    # 贵州
    "KWE": "贵阳",
    "ZYI": "遵义",
    "TEN": "铜仁",
    "BFJ": "毕节",
    "LPF": "六盘水",
    "AVA": "安顺",
    # 西藏
    "LXA": "拉萨",
    "LZY": "林芝",
    "RKZ": "日喀则",
    # 新疆
    "URC": "乌鲁木齐",
    "KHG": "喀什",
    "KRL": "库尔勒",
    "YIN": "伊宁",
    "AKU": "阿克苏",
    "HTN": "和田",
    "KRY": "克拉玛依",
    "TLQ": "吐鲁番",
    "AAT": "阿勒泰",
    "HMI": "哈密",
    "KCA": "库车",
    "TCG": "塔城",
    "YTW": "于田",
    "ACF": "阿拉尔",
    # 陕西
    "XIY": "西安",
    "UYN": "榆林",
    "HZG": "汉中",
    "ENY": "延安",
    "AKA": "安康",
    # 甘肃
    "LHW": "兰州",
    "DNH": "敦煌",
    "JGN": "嘉峪关",
    "LNL": "陇南",
    "IQN": "庆阳",
    "THQ": "天水",
    # 宁夏
    "INC": "银川",
    # 青海
    "XNN": "西宁",
}


def get_city_name_by_code(airport_code: str) -> str:
    """
    根据机场三字码获取城市简称
    
    Args:
        airport_code: 机场三字码，如 "TNA"
    
    Returns:
        城市简称，如 "济南"；如果找不到则返回原三字码
    """
    if not airport_code:
        return ""
    # 转换为大写以确保匹配
    code_upper = airport_code.upper().strip()
    return AIRPORT_CODE_TO_CITY.get(code_upper, airport_code)


def get_code_by_city_name(city_name: str) -> str:
    """
    根据城市简称获取机场三字码
    
    Args:
        city_name: 城市简称，如 "济南"
    
    Returns:
        机场三字码，如 "TNA"；如果找不到则返回空字符串
    """
    if not city_name:
        return ""
    # 反向查找
    for code, city in AIRPORT_CODE_TO_CITY.items():
        if city == city_name.strip():
            return code
    return ""

