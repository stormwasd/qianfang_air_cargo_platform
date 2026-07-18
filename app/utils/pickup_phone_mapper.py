"""
提货电话映射工具类
用于从 Excel 文件中加载并查询深航及全国各机场的提货电话。
"""
import os
import pandas as pd
from typing import Dict, List, Optional
import math

class PickupPhoneMapper:
    _instance = None
    
    _shenzhen_air_data: Dict[str, str] = {}
    _shenzhen_air_name_data: Dict[str, str] = {}
    _national_air_data: Dict[str, List[Dict[str, str]]] = {}
    _is_loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PickupPhoneMapper, cls).__new__(cls)
        return cls._instance

    @classmethod
    def load_data(cls):
        """懒加载 Excel 数据到内存中"""
        if cls._is_loaded:
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sz_path = os.path.join(base_dir, "深航提货电话.xlsx")
        national_path = os.path.join(base_dir, "全国民用机场提货电话.xlsx")

        if os.path.exists(sz_path):
            try:
                df_sz = pd.read_excel(sz_path)
                for _, row in df_sz.iterrows():
                    code = str(row.get("城市代码", "")).strip().upper()
                    name = str(row.get("城市中文名", "")).strip()
                    phone = str(row.get("联系电话", "")).strip()
                    if phone and phone != "nan":
                        if code and code != "NAN":
                            cls._shenzhen_air_data[code] = phone
                        if name and name != "NAN":
                            cls._shenzhen_air_name_data[name] = phone
            except Exception as e:
                print(f"Error loading {sz_path}: {e}")

        if os.path.exists(national_path):
            try:
                df_na = pd.read_excel(national_path, header=5)
                if "目的站" in df_na.columns:
                    df_na["目的站"] = df_na["目的站"].ffill()
                    
                    for _, row in df_na.iterrows():
                        dest = str(row.get("目的站", "")).strip()
                        airline_raw = str(row.get("航司", "")).strip()
                        phone = str(row.get("提货电话", "")).strip()
                        
                        if dest and dest != "nan" and phone and phone != "nan":
                            if dest not in cls._national_air_data:
                                cls._national_air_data[dest] = []
                            cls._national_air_data[dest].append({
                                "airline": airline_raw,
                                "phone": phone
                            })
            except Exception as e:
                print(f"Error loading {national_path}: {e}")

        cls._is_loaded = True

    @classmethod
    def get_shenzhen_air_phone(cls, dest_code: str, dest_name: str) -> str:
        """获取深航提货电话"""
        if not cls._is_loaded:
            cls.load_data()
            
        if dest_code:
            code = dest_code.strip().upper()
            if code in cls._shenzhen_air_data:
                return cls._shenzhen_air_data[code]
        if dest_name:
            name = dest_name.strip()
            if name in cls._shenzhen_air_name_data:
                return cls._shenzhen_air_name_data[name]
        return ""

    @classmethod
    def get_national_phone(cls, dest_name: str, airline: str = "") -> str:
        """获取全国民用机场提货电话（如南航、同行等）"""
        if not cls._is_loaded:
            cls.load_data()
            
        if not dest_name:
            return ""
            
        name = dest_name.strip()
        name_without_airport = name.replace("机场", "")
        
        matched_dest = None
        for key in cls._national_air_data.keys():
            if key in name or name in key or key in name_without_airport:
                matched_dest = key
                break
                
        if not matched_dest:
            return ""
            
        records = cls._national_air_data[matched_dest]
        if not records:
            return ""
            
        if len(records) == 1:
            return records[0]["phone"]
            
        if airline:
            airline_key = airline.replace("航", "") 
            for record in records:
                if airline in record["airline"] or airline_key in record["airline"]:
                    return record["phone"]
                    
        for record in records:
            if record["airline"] == "/" or not record["airline"] or record["airline"] == "nan":
                return record["phone"]
                
        return records[0]["phone"]

pickup_phone_mapper = PickupPhoneMapper()
