"""
机场三字码到城市名称映射工具模块

用于将机场三字码（如"TNA"）转换为城市名称（如"济南"）
支持根据城市名/机场名模糊搜索获取对应的三字码

注意：AIRPORT_CODE_TO_CITY 的值与 airport_three_letter_code.json 的 label 保持一致
"""
from typing import List

# 三字码到城市名称的映射（与 airport_three_letter_code.json 的 label 保持一致）
AIRPORT_CODE_TO_CITY = {
    # 北京
    "PEK": "北京首都",
    "PKX": "北京大兴",
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
    "NZL": "扎兰屯",
    "BAV": "包头",
    "HLD": "呼伦贝尔",
    "RHT": "阿拉善右旗",
    "WUA": "乌海",
    "RLK": "巴彦淖尔",
    "AXF": "阿拉善左旗",
    "CIF": "赤峰",
    "NHZ": "满洲里",
    "EJN": "额济纳旗",
    "TGO": "通辽",
    "ERL": "二连浩特",
    "WZQ": "乌拉特中旗",
    "UCB": "乌兰察布",
    "HLH": "乌兰浩特",
    "DSN": "鄂尔多斯",
    "YIE": "阿尔山",
    # 东北 - 辽宁
    "SHE": "沈阳",
    "DLC": "大连",
    "AOG": "鞍山",
    "DDG": "丹东",
    "JNZ": "锦州湾",
    "YKH": "营口",
    "CHG": "朝阳",
    # 东北 - 吉林
    "CGQ": "长春",
    "YNJ": "延吉",
    "NBS": "长白山",
    "TNH": "通化",
    "DBC": "白城",
    "YSQ": "松原",
    # 东北 - 黑龙江
    "HRB": "哈尔滨",
    "JXA": "鸡西",
    "NDG": "齐齐哈尔",
    "OHE": "漠河",
    "MDG": "牡丹江",
    "FYJ": "抚远",
    "JMU": "佳木斯",
    "JSJ": "建三江",
    "DQA": "大庆",
    "DTU": "五大连池",
    "LDS": "伊春",
    "HEK": "黑河",
    # 上海
    "SHA": "上海虹桥",
    "PVG": "上海浦东",
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
    "HEW": "横店",
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
    "KOW": "赣州",
    "JGS": "井冈山",
    "JDZ": "景德镇",
    "SQD": "上饶",
    "YIC": "宜春",
    "JIU": "九江",
    # 福建
    "FOC": "福州",
    "XMN": "厦门",
    "JJN": "泉州",
    "WUS": "武夷山",
    "LCX": "龙岩",
    "SQJ": "三明",
    # 广东
    "CAN": "广州",
    "HUZ": "惠州",
    "SZX": "深圳",
    "FUO": "佛山",
    "ZUH": "珠海",
    "SWA": "揭阳",
    "ZHA": "湛江",
    "HSC": "韶关",
    "MXZ": "梅州",
    # 广西
    "NNG": "南宁",
    "HCJ": "河池",
    "KWL": "桂林",
    "LZH": "柳州",
    "BHY": "北海",
    "WUZ": "梧州",
    "AEB": "百色",
    "YLX": "玉林",
    # 海南
    "HAK": "海口",
    "SYX": "三亚",
    "BAR": "琼海",
    # 河南
    "CGO": "郑州",
    "LYA": "洛阳",
    "NNY": "南阳",
    "XAI": "信阳",
    # 湖南
    "CSX": "长沙",
    "LLF": "永州",
    "DYG": "张家界",
    "HCZ": "郴州",
    "CGD": "常德",
    "HNY": "衡阳",
    "YYA": "岳阳",
    "HJJ": "怀化",
    "WGN": "邵阳",
    # 湖北
    "WUH": "武汉",
    "HPG": "神农架",
    "YIH": "宜昌",
    "XFN": "襄阳",
    "ENH": "恩施",
    "WDS": "十堰",
    "SHS": "荆州",
    "EHU": "鄂州",
    # 重庆
    "CKG": "重庆",
    "WSK": "巫山",
    "CQW": "武隆",
    "JIQ": "黔江",
    "WXN": "万州",
    # 四川
    "CTU": "成都双流",
    "PZI": "攀枝花",
    "GZG": "甘孜",
    "TFU": "成都天府",
    "DCY": "稻城",
    "LZO": "泸州",
    "MIG": "绵阳",
    "GYS": "广元",
    "NAO": "南充",
    "JZH": "九寨沟",
    "XIC": "西昌",
    "BZX": "巴中",
    "YBP": "宜宾",
    "KGT": "康定",
    "DZH": "达州",
    "AHJ": "红原",
    # 云南
    "KMG": "昆明",
    "DIG": "迪庆",
    "LJG": "丽江",
    "SYM": "普洱",
    "JHG": "西双版纳",
    "LNJ": "临沧",
    "LUM": "芒市",
    "ZAT": "昭通",
    "DLU": "大理",
    "WNH": "文山",
    "TCZ": "腾冲",
    "NLH": "宁蒗",
    "BSD": "保山",
    "LFH": "怒江",
    # 贵州
    "KWE": "贵阳",
    "LLB": "荔波",
    "ZYI": "遵义",
    "KJH": "凯里",
    "ACX": "兴义",
    "HZH": "黎平",
    "TEN": "铜仁",
    "BFJ": "毕节",
    "LPF": "六盘水",
    "AVA": "安顺",
    # 西藏
    "LXA": "拉萨",
    "LZY": "林芝",
    "BPX": "昌都",
    "RKZ": "日喀则",
    "NGQ": "阿里",
    # 新疆
    "URC": "乌鲁木齐",
    "TLQ": "吐鲁番",
    "NLT": "那拉提",
    "ZFL": "昭苏",
    "KHG": "喀什",
    "AAT": "阿勒泰",
    "TWC": "图木舒克",
    "ACF": "阿拉尔",
    "KRL": "库尔勒",
    "HMI": "哈密",
    "QSZ": "莎车",
    "YIN": "伊宁",
    "KCA": "库车",
    "FYN": "富蕴",
    "AKU": "阿克苏",
    "BPL": "博乐",
    "SHF": "石河子",
    "HTN": "和田",
    "TCG": "塔城",
    "YTW": "于田",
    "KRY": "克拉玛依",
    "IQM": "且末",
    # 陕西
    "XIY": "西安",
    "UYN": "榆林",
    "HZG": "汉中",
    "ENY": "延安",
    "AKA": "安康",
    "DFA": "商洛",
    # 甘肃
    "LHW": "兰州",
    "IQN": "庆阳",
    "DNH": "敦煌",
    "THQ": "天水",
    "JGN": "嘉峪关",
    "YZY": "张掖",
    "LNL": "陇南",
    "JIC": "金昌",
    "GXH": "甘南",
    # 宁夏
    "INC": "银川",
    "ZHY": "中卫",
    "GYU": "固原",
    # 青海
    "XNN": "西宁",
    "COQ": "格尔木",
    "YUS": "玉树",
    "HXD": "德令哈",
    "GMQ": "果洛",
    "HTT": "花土沟",
    "HBQ": "祁连",
}


def get_city_name_by_code(airport_code: str) -> str:
    """
    根据机场三字码获取城市名称
    
    Args:
        airport_code: 机场三字码，如 "TNA"
    
    Returns:
        城市名称，如 "济南"；如果找不到则返回原三字码
    """
    if not airport_code:
        return ""
    # 转换为大写以确保匹配
    code_upper = airport_code.upper().strip()
    return AIRPORT_CODE_TO_CITY.get(code_upper, airport_code)


def get_code_by_city_name(city_name: str) -> str:
    """
    根据城市名称获取机场三字码（精确匹配）
    
    Args:
        city_name: 城市名称，如 "济南"
    
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


def get_airport_name_by_code(airport_code: str) -> str:
    """
    根据机场三字码获取完整的机场名称
    
    Args:
        airport_code: 机场三字码，如 "TNA"
    
    Returns:
        完整的机场名称，如 "济南遥墙机场"；如果找不到则返回城市名或原三字码
    """
    if not airport_code:
        return ""
    code_upper = airport_code.upper().strip()
    # 先反向查找完整的机场名称
    for name, code in AIRPORT_NAME_TO_CODE.items():
        if code == code_upper:
            return name
    # 如果没找到全称，回退到城市名称
    return AIRPORT_CODE_TO_CITY.get(code_upper, airport_code)


# 完整的机场名称到三字码映射（用于模糊搜索）
# 格式: "完整机场名称": "三字码"
AIRPORT_NAME_TO_CODE = {
    "北京首都机场": "PEK",
    "北京大兴机场": "PKX",
    "天津滨海机场": "TSN",
    "石家庄正定机场": "SJW",
    "唐山三女河机场": "TVS",
    "秦皇岛北戴河机场": "BPE",
    "邯郸机场": "HDG",
    "张家口宁远机场": "ZQZ",
    "承德普宁机场": "CDE",
    "太原武宿机场": "TYN",
    "长治王村机场": "CIH",
    "大同云冈机场": "DAT",
    "临汾乔李机场": "LFQ",
    "运城张孝机场": "YCU",
    "忻州五台山机场": "WUT",
    "吕梁大武机场": "LLV",
    "呼和浩特白塔机场": "HET",
    "锡林浩特机场": "XIL",
    "包头东河机场": "BAV",
    "呼伦贝尔海拉尔机场": "HLD",
    "乌海机场": "WUA",
    "赤峰玉龙机场": "CIF",
    "满洲里西郊机场": "NHZ",
    "通辽机场": "TGO",
    "鄂尔多斯伊金霍洛机场": "DSN",
    "沈阳桃仙机场": "SHE",
    "丹东浪头机场": "DDG",
    "营口兰旗机场": "YKH",
    "鞍山腾鳌机场": "AOG",
    "大连周水子机场": "DLC",
    "长春龙嘉机场": "CGQ",
    "长白山机场": "NBS",
    "延吉朝阳川机场": "YNJ",
    "通化三源浦机场": "TNH",
    "哈尔滨太平机场": "HRB",
    "黑河瑷珲机场": "HEK",
    "齐齐哈尔三家子机场": "NDG",
    "鸡西兴凯湖机场": "JXA",
    "牡丹江海浪机场": "MDG",
    "漠河古莲机场": "OHE",
    "佳木斯东郊机场": "JMU",
    "大庆萨尔图机场": "DQA",
    "上海虹桥机场": "SHA",
    "上海浦东机场": "PVG",
    "南京禄口机场": "NKG",
    "连云港花果山机场": "LYG",
    "无锡苏南硕放机场": "WUX",
    "淮安涟水机场": "HIA",
    "常州奔牛机场": "CZX",
    "镇江大路机场": "AZJ",
    "南通兴东机场": "NTG",
    "盐城南阳机场": "YNZ",
    "扬州泰州机场": "YTY",
    "徐州观音机场": "XUZ",
    "杭州萧山机场": "HGH",
    "温州龙湾机场": "WNZ",
    "宁波栎社机场": "NGB",
    "义乌机场": "YIW",
    "舟山普陀山机场": "HSN",
    "台州路桥机场": "HYN",
    "衢州机场": "JUZ",
    "合肥新桥机场": "HFE",
    "阜阳西关机场": "FUG",
    "黄山屯溪机场": "TXN",
    "安庆天柱山机场": "AQG",
    "芜湖宣城机场": "WHA",
    "池州九华山机场": "JUH",
    "济南遥墙机场": "TNA",
    "青岛胶东机场": "TAO",
    "烟台蓬莱机场": "YNT",
    "东营胜利机场": "DOY",
    "潍坊机场": "WEF",
    "济宁曲阜机场": "JNG",
    "威海大水泊机场": "WEH",
    "日照山字河机场": "RIZ",
    "南昌昌北机场": "KHN",
    "吉安井冈山机场": "JGS",
    "景德镇罗家机场": "JDZ",
    "上饶三清山机场": "SQD",
    "宜春明月山机场": "YIC",
    "九江庐山机场": "JIU",
    "福州长乐机场": "FOC",
    "厦门高崎机场": "XMN",
    "泉州晋江机场": "JJN",
    "南平武夷山机场": "WUS",
    "龙岩冠豸山机场": "LCX",
    "广州白云机场": "CAN",
    "深圳宝安机场": "SZX",
    "珠海金湾机场": "ZUH",
    "揭阳潮汕机场": "SWA",
    "湛江吴川机场": "ZHA",
    "韶关丹霞机场": "HSC",
    "梅州梅县机场": "MXZ",
    "惠州平潭机场": "HUZ",
    "佛山沙堤机场": "FUO",
    "南宁吴圩机场": "NNG",
    "桂林两江机场": "KWL",
    "柳州白莲机场": "LZH",
    "北海福成机场": "BHY",
    "梧州西江机场": "WUZ",
    "百色巴马机场": "AEB",
    "玉林福绵机场": "YLX",
    "河池金城江机场": "HCJ",
    "海口美兰机场": "HAK",
    "三亚凤凰机场": "SYX",
    "郑州新郑机场": "CGO",
    "洛阳北郊机场": "LYA",
    "南阳姜营机场": "NNY",
    "信阳明港机场": "XAI",
    "长沙黄花机场": "CSX",
    "张家界荷花机场": "DYG",
    "常德桃花源机场": "CGD",
    "衡阳南岳机场": "HNY",
    "岳阳三荷机场": "YYA",
    "怀化芷江机场": "HJJ",
    "邵阳武冈市机场": "WGN",
    "永州零陵机场": "LLF",
    "郴州北湖机场": "HCZ",
    "武汉天河机场": "WUH",
    "宜昌三峡机场": "YIH",
    "襄阳刘集机场": "XFN",
    "恩施许家坪机场": "ENH",
    "十堰武当山机场": "WDS",
    "荆州沙市机场": "SHS",
    "鄂州花湖机场": "EHU",
    "重庆江北机场": "CKG",
    "成都双流机场": "CTU",
    "成都天府机场": "TFU",
    "绵阳南郊机场": "MIG",
    "南充高坪机场": "NAO",
    "宜宾五粮液机场": "YBP",
    "达州金垭机场": "DZH",
    "攀枝花保安营机场": "PZI",
    "稻城西丁机场": "DCY",
    "广元盘龙机场": "GYS",
    "巴中恩阳机场": "BZX",
    "甘孜康定机场": "KGT",
    "泸州云龙机场": "LZO",
    "昆明长水机场": "KMG",
    "丽江三义机场": "LJG",
    "西双版纳嘎洒机场": "JHG",
    "大理荒草坝机场": "DLU",
    "腾冲驼峰机场": "TCZ",
    "迪庆香格里拉机场": "DIG",
    "普洱思茅机场": "SYM",
    "临沧博尚机场": "LNJ",
    "昭通机场": "ZAT",
    "贵阳龙洞堡机场": "KWE",
    "遵义新舟机场": "ZYI",
    "铜仁凤凰机场": "TEN",
    "毕节飞雄机场": "BFJ",
    "六盘水月照机场": "LPF",
    "安顺黄果树机场": "AVA",
    "拉萨贡嘎机场": "LXA",
    "林芝米林机场": "LZY",
    "日喀则和平机场": "RKZ",
    "乌鲁木齐地窝堡机场": "URC",
    "喀什机场": "KHG",
    "库尔勒梨城机场": "KRL",
    "伊宁机场": "YIN",
    "阿克苏红旗坡机场": "AKU",
    "和田机场": "HTN",
    "克拉玛依古海机场": "KRY",
    "吐鲁番交河机场": "TLQ",
    "阿勒泰雪都机场": "AAT",
    "哈密伊州机场": "HMI",
    "库车龟兹机场": "KCA",
    "塔城千泉机场": "TCG",
    "于田万方机场": "YTW",
    "阿拉尔塔里木机场": "ACF",
    "西安咸阳机场": "XIY",
    "榆林西沙机场": "UYN",
    "汉中城固机场": "HZG",
    "延安南泥湾机场": "ENY",
    "安康富强机场": "AKA",
    "兰州中川机场": "LHW",
    "敦煌莫高机场": "DNH",
    "嘉峪关机场": "JGN",
    "陇南成县机场": "LNL",
    "庆阳西峰机场": "IQN",
    "天水麦积山机场": "THQ",
    "银川河东机场": "INC",
    "西宁曹家堡机场": "XNN",
}


def search_airport_codes_by_keyword(keyword: str) -> List[str]:
    """
    根据关键字模糊搜索机场三字码
    
    用于目的站查询，用户输入如"西宁"，可以匹配到"西宁曹家堡机场"，返回三字码"XNN"
    
    Args:
        keyword: 搜索关键字，如 "西宁"、"广州"、"首都"
    
    Returns:
        匹配到的三字码列表，如 ["XNN"]、["CAN"]、["PEK"]
        如果没有匹配到则返回空列表
    """
    if not keyword:
        return []
    
    keyword = keyword.strip()
    if not keyword:
        return []
    
    matched_codes = []
    
    # 遍历机场名称映射，进行模糊匹配
    for airport_name, code in AIRPORT_NAME_TO_CODE.items():
        if keyword in airport_name:
            matched_codes.append(code)
    
    return matched_codes

