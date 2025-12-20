"""
权限到菜单的映射关系
定义每个权限对应的菜单结构
"""
from typing import List, Dict, Any

# 菜单项类型定义
MenuType = Dict[str, Any]

# 管理员权限标识
ADMIN_PERMISSION = "管理员"

# 所有菜单项的基础定义
ALL_MENUS: List[MenuType] = [
    {
        "name": "MainOrder",
        "path": "/main-order",
        "meta": {
            "title": "主单管理",
            "order": 1,
        },
        "children": [
            {
                "name": "Waybill",
                "path": "/main-order/waybill",
                "component": "/main-order/waybill/index",
                "meta": {
                    "title": "运单管理",
                },
            },
            {
                "name": "Booking",
                "path": "/main-order/booking",
                "component": "/main-order/booking/index",
                "meta": {
                    "title": "订舱管理",
                },
            },
        ],
    },
    {
        "name": "Settlement",
        "path": "/settlement",
        "meta": {
            "title": "结算单管理",
            "order": 2,
        },
        "children": [
            {
                "name": "SettlementManage",
                "path": "/settlement/manage",
                "component": "/settlement/manage/index",
                "meta": {
                    "title": "结算单管理",
                },
            },
        ],
    },
    {
        "name": "Customer",
        "path": "/customer",
        "meta": {
            "title": "客户管理",
            "order": 3,
        },
        "children": [
            {
                "name": "CustomerManage",
                "path": "/customer/manage",
                "component": "/customer/manage/index",
                "meta": {
                    "title": "客户管理",
                },
            },
        ],
    },
    {
        "name": "System",
        "path": "/system",
        "meta": {
            "title": "系统管理",
            "order": 4,
        },
        "children": [
            {
                "name": "BusinessConfig",
                "path": "/system/business-config",
                "component": "/system/business-config/index",
                "meta": {
                    "title": "业务参数管理",
                },
            },
        ],
    },
    {
        "name": "Account",
        "path": "/account",
        "meta": {
            "title": "账号管理",
            "order": 5,
        },
        "children": [
            {
                "name": "AccountManage",
                "path": "/account/manage",
                "component": "/account/manage/index",
                "meta": {
                    "title": "账号管理",
                },
            },
            {
                "name": "Department",
                "path": "/account/department",
                "component": "/account/department/index",
                "meta": {
                    "title": "部门管理",
                },
            },
        ],
    },
    {
        "name": "UserCenter",
        "path": "/user-center",
        "meta": {
            "title": "用户中心",
            "order": 6,
        },
        "children": [
            {
                "name": "UserCenterPage",
                "path": "/user-center/index",
                "component": "/user-center/index",
                "meta": {
                    "title": "用户中心",
                },
            },
        ],
    },
]

# 单个权限对应的菜单映射
PERMISSION_MENU_MAP: Dict[str, List[MenuType]] = {
    ADMIN_PERMISSION: ALL_MENUS,  # 管理员拥有所有菜单
    
    "运单管理": [
        {
            "name": "MainOrder",
            "path": "/main-order",
            "meta": {
                "title": "主单管理",
                "order": 1,
            },
            "children": [
                {
                    "name": "Waybill",
                    "path": "/main-order/waybill",
                    "component": "/main-order/waybill/index",
                    "meta": {
                        "title": "运单管理",
                    },
                },
            ],
        },
        {
            "name": "Customer",
            "path": "/customer",
            "meta": {
                "title": "客户管理",
                "order": 3,
            },
            "children": [
                {
                    "name": "CustomerManage",
                    "path": "/customer/manage",
                    "component": "/customer/manage/index",
                    "meta": {
                        "title": "客户管理",
                    },
                },
            ],
        },
        {
            "name": "System",
            "path": "/system",
            "meta": {
                "title": "系统管理",
                "order": 4,
            },
            "children": [
                {
                    "name": "BusinessConfig",
                    "path": "/system/business-config",
                    "component": "/system/business-config/index",
                    "meta": {
                        "title": "业务参数管理",
                    },
                },
            ],
        },
        {
            "name": "UserCenter",
            "path": "/user-center",
            "meta": {
                "title": "用户中心",
                "order": 6,
            },
            "children": [
                {
                    "name": "UserCenterPage",
                    "path": "/user-center/index",
                    "component": "/user-center/index",
                    "meta": {
                        "title": "用户中心",
                    },
                },
            ],
        },
    ],
    
    "订舱管理": [
        {
            "name": "MainOrder",
            "path": "/main-order",
            "meta": {
                "title": "主单管理",
                "order": 1,
            },
            "children": [
                {
                    "name": "Booking",
                    "path": "/main-order/booking",
                    "component": "/main-order/booking/index",
                    "meta": {
                        "title": "订舱管理",
                    },
                },
            ],
        },
        {
            "name": "Customer",
            "path": "/customer",
            "meta": {
                "title": "客户管理",
                "order": 3,
            },
            "children": [
                {
                    "name": "CustomerManage",
                    "path": "/customer/manage",
                    "component": "/customer/manage/index",
                    "meta": {
                        "title": "客户管理",
                    },
                },
            ],
        },
        {
            "name": "System",
            "path": "/system",
            "meta": {
                "title": "系统管理",
                "order": 4,
            },
            "children": [
                {
                    "name": "BusinessConfig",
                    "path": "/system/business-config",
                    "component": "/system/business-config/index",
                    "meta": {
                        "title": "业务参数管理",
                    },
                },
            ],
        },
        {
            "name": "UserCenter",
            "path": "/user-center",
            "meta": {
                "title": "用户中心",
                "order": 6,
            },
            "children": [
                {
                    "name": "UserCenterPage",
                    "path": "/user-center/index",
                    "component": "/user-center/index",
                    "meta": {
                        "title": "用户中心",
                    },
                },
            ],
        },
    ],
    
    "结算单管理": [
        {
            "name": "Settlement",
            "path": "/settlement",
            "meta": {
                "title": "结算单管理",
                "order": 2,
            },
            "children": [
                {
                    "name": "SettlementManage",
                    "path": "/settlement/manage",
                    "component": "/settlement/manage/index",
                    "meta": {
                        "title": "结算单管理",
                    },
                },
            ],
        },
        {
            "name": "Customer",
            "path": "/customer",
            "meta": {
                "title": "客户管理",
                "order": 3,
            },
            "children": [
                {
                    "name": "CustomerManage",
                    "path": "/customer/manage",
                    "component": "/customer/manage/index",
                    "meta": {
                        "title": "客户管理",
                    },
                },
            ],
        },
        {
            "name": "System",
            "path": "/system",
            "meta": {
                "title": "系统管理",
                "order": 4,
            },
            "children": [
                {
                    "name": "BusinessConfig",
                    "path": "/system/business-config",
                    "component": "/system/business-config/index",
                    "meta": {
                        "title": "业务参数管理",
                    },
                },
            ],
        },
        {
            "name": "UserCenter",
            "path": "/user-center",
            "meta": {
                "title": "用户中心",
                "order": 6,
            },
            "children": [
                {
                    "name": "UserCenterPage",
                    "path": "/user-center/index",
                    "component": "/user-center/index",
                    "meta": {
                        "title": "用户中心",
                    },
                },
            ],
        },
    ],
}


def generate_menus_by_permissions(permissions: List[str]) -> List[MenuType]:
    """
    根据用户权限生成菜单列表
    支持多权限合并，自动去重
    
    Args:
        permissions: 用户权限列表
        
    Returns:
        合并后的菜单列表，按order排序
    """
    if not permissions:
        return []
    
    # 如果包含管理员权限，直接返回所有菜单
    if ADMIN_PERMISSION in permissions:
        return sorted(ALL_MENUS, key=lambda x: x["meta"].get("order", 999))
    
    # 用于存储合并后的菜单，key为菜单的path
    merged_menus: Dict[str, MenuType] = {}
    
    # 遍历每个权限，合并菜单
    for permission in permissions:
        if permission not in PERMISSION_MENU_MAP:
            continue
        
        permission_menus = PERMISSION_MENU_MAP[permission]
        
        for menu in permission_menus:
            menu_path = menu["path"]
            
            if menu_path not in merged_menus:
                # 新菜单，直接添加
                merged_menus[menu_path] = menu.copy()
                # 深拷贝children，避免引用问题
                if "children" in merged_menus[menu_path]:
                    merged_menus[menu_path]["children"] = merged_menus[menu_path]["children"].copy()
            else:
                # 菜单已存在，需要合并children
                existing_menu = merged_menus[menu_path]
                existing_children = existing_menu.get("children", [])
                new_children = menu.get("children", [])
                
                # 用于存储已存在的子菜单path，避免重复
                existing_child_paths = {child["path"] for child in existing_children}
                
                # 合并children，去重
                for new_child in new_children:
                    if new_child["path"] not in existing_child_paths:
                        existing_children.append(new_child.copy())
                        existing_child_paths.add(new_child["path"])
                
                existing_menu["children"] = existing_children
    
    # 转换为列表并按order排序
    result = list(merged_menus.values())
    result.sort(key=lambda x: x["meta"].get("order", 999))
    
    return result

