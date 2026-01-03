"""
业务参数配置相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime


class BusinessConfigCreate(BaseModel):
    """
    创建业务参数配置schema
    
    数据结构说明：
    config_data 是一个四层嵌套的字典结构（所有键名使用英文，遵循snake_case命名规范）：
    第一层：航司代码（如："shenzhen_air"、"china_southern_air"）
    第二层：业务类型（如："booking"、"document"、"print"、"booking_and_create"）
    第三层：参数组代码（如："shenzhen_air_login"、"business_default"等）
    第四层：参数项（键值对，值为字符串，特殊说明：printer_config 是数组类型，支持配置多个打印机）
    
    示例结构：
    {
      "shenzhen_air": {
        "booking": {
          "shenzhen_air_login": {
            "system_url": "",
            "system_account": "",
            "login_password": ""
          },
          "business_default": {
            "origin_station": "",
            "shipper_info": "",
            "freight_code": "",
            "cargo_code": "",
            "package": "",
            "cargo_name": ""
          }
        },
        "document": {
          "domestic_cargo_checklist": {
            "shipper_or_agent": "",
            "shipper_or_agent_seal": ""
          },
          "domestic_cargo_detail": {},
          "emergency_lithium_battery": {
            "emergency_contact": "",
            "emergency_phone_24h": ""
          },
          "shenzhen_airport_security_declaration": {
            "shipper_seal": ""
          },
          "packaging_spec_part2_battery_checklist": {
            "consignor_agent": "",
            "consignor_agent_checker_signature": ""
          }
        },
        "print": {
          "printer_config": [
            {
              "document_type": "",
              "printer_name": ""
            }
          ]
        }
      },
      "china_southern_air": {
        "booking_and_create": {
          "china_southern_air_login": {
            "system_url": "",
            "system_account": "",
            "login_password": ""
          },
          "tangi_login": {
            "app_name": "",
            "system_account": "",
            "login_password": ""
          },
          "business_default": {
            "origin_station": "",
            "booking_remark": "",
            "cargo_code": "",
            "cargo_type": "",
            "package": "",
            "special_cargo_code": "",
            "agent_checker_name": "",
            "agent_consignor_name": "",
            "order_contact_name": ""
          }
        },
        "print": {
          "printer_config": [
            {
              "document_type": "",
              "printer_name": ""
            }
          ]
        }
      }
    }
    """
    config_data: Dict[str, Any] = Field(
        ..., 
        description="配置数据，四层嵌套字典结构：航司代码 -> 业务类型 -> 参数组代码 -> 参数项（所有键名使用英文，遵循snake_case命名规范）"
    )


class BusinessConfigResponse(BaseModel):
    """业务参数配置响应schema"""
    id: str  # ID以字符串形式返回
    config_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

