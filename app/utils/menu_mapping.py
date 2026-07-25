"""
权限到菜单的映射关系
定义每个权限（一级菜单）对应的菜单结构，支持多层级（一、二、三级）菜单
"""
import copy
from typing import List, Dict, Any
from app.config import settings

MenuType = Dict[str, Any]

ADMIN_PERMISSION_CODE = "admin"
ADMIN_PERMISSION_NAME = settings.PERMISSIONS.get(ADMIN_PERMISSION_CODE, "管理员")

ALL_MENUS: List[MenuType] = [
    {
        "name": "主单管理",
        "children": [
            {"name": "运单管理"},
            {"name": "订舱管理"},
            {"name": "托运书管理"}
        ]
    },
    {
        "name": "单号库",
        "children": [
            {"name": "单号库总览"}
        ]
    },
    {
        "name": "机器人管理",
        "children": [
            {"name": "机器人列表"}
        ]
    },
    {
        "name": "客户管理",
        "children": [
            {"name": "客户管理列表"}
        ]
    },
    {
        "name": "账号管理",
        "children": [
            {"name": "用户列表"},
            {"name": "部门管理"}
        ]
    },
    {
        "name": "系统管理",
        "children": [
            {"name": "数据字典"},
            {"name": "参数配置"}
        ]
    },
    {
        "name": "代理管理",
        "children": [
            {"name": "承运代理管理"},
            {"name": "提货单位管理"},
            {"name": "派送单位管理"}
        ]
    },
    {
        "name": "财务管理",
        "children": [
            {"name": "财务单据审核"},
            {"name": "应收对账"},
            {"name": "应付对账"}
        ]
    },
    {
        "name": "智能跟单",
        "children": [
            {
                "name": "订舱批复跟踪",
                "children": [
                    {"name": "深圳航空"},
                    {"name": "南方航空"}
                ]
            },
            {
                "name": "出港跟踪",
                "children": [
                    {"name": "深圳航空"},
                    {"name": "南方航空"}
                ]
            }
        ]
    },
    {
        "name": "运单单据审核",
        "children": [
            {"name": "汽运单据审核"},
            {
                "name": "空运单据审核",
                "children": [
                    {"name": "深圳航空"},
                    {"name": "南方航空"},
                    {"name": "同行空运代理"}
                ]
            }
        ]
    },
    {
        "name": "公司信息",
        "children": []
    }
]

_menu_by_name: Dict[str, MenuType] = {menu["name"]: menu for menu in ALL_MENUS}

PERMISSION_MENU_MAP: Dict[str, List[MenuType]] = {
    ADMIN_PERMISSION_CODE: ALL_MENUS,
    
    # 按照 11 个一级菜单规范代码映射
    "waybill": [_menu_by_name["主单管理"]],
    "bill": [_menu_by_name["单号库"]],
    "robot": [_menu_by_name["机器人管理"]],
    "customer": [_menu_by_name["客户管理"]],
    "account": [_menu_by_name["账号管理"]],
    "system": [_menu_by_name["系统管理"]],
    "agent": [_menu_by_name["代理管理"]],
    "finance": [_menu_by_name["财务管理"]],
    "smart_tracking": [_menu_by_name["智能跟单"]],
    "waybill_audit": [_menu_by_name["运单单据审核"]],
    "company_info": [_menu_by_name["公司信息"]],
}


def _merge_menu_children(target_children: List[MenuType], source_children: List[MenuType]) -> List[MenuType]:
    """递归合并多层级菜单项"""
    child_map = {child["name"]: child for child in target_children}
    for source_child in source_children:
        c_name = source_child["name"]
        if c_name not in child_map:
            copied_child = copy.deepcopy(source_child)
            target_children.append(copied_child)
            child_map[c_name] = copied_child
        else:
            if "children" in source_child and source_child["children"]:
                if "children" not in child_map[c_name] or not child_map[c_name]["children"]:
                    child_map[c_name]["children"] = copy.deepcopy(source_child["children"])
                else:
                    _merge_menu_children(child_map[c_name]["children"], source_child["children"])
    return target_children


def generate_menus_by_permissions(permissions: List[str]) -> List[MenuType]:
    """
    根据用户权限生成菜单列表
    支持按一级菜单权限合并，自动去重，保留二、三级子菜单结构
    
    Args:
        permissions: 用户权限列表（权限代码）
        
    Returns:
        合并后的菜单列表
    """
    if not permissions:
        return []
    
    if ADMIN_PERMISSION_CODE in permissions:
        return copy.deepcopy(ALL_MENUS)
    
    merged_menus: Dict[str, MenuType] = {}
    
    for permission in permissions:
        if permission not in PERMISSION_MENU_MAP:
            continue
        
        permission_menus = PERMISSION_MENU_MAP[permission]
        
        for menu in permission_menus:
            menu_name = menu["name"]
            if menu_name not in merged_menus:
                merged_menus[menu_name] = copy.deepcopy(menu)
            else:
                existing_menu = merged_menus[menu_name]
                if "children" in menu and menu["children"]:
                    if "children" not in existing_menu or not existing_menu["children"]:
                        existing_menu["children"] = copy.deepcopy(menu["children"])
                    else:
                        _merge_menu_children(existing_menu["children"], menu["children"])
    
    return list(merged_menus.values())

