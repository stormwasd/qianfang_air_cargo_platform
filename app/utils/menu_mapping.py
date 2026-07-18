"""
权限到菜单的映射关系
定义每个权限对应的菜单结构（简化版：只保留父子关系）
"""
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
            {"name": "订舱管理"}
        ]
    },
    {
        "name": "结算单管理",
        "children": [
            {"name": "结算单管理"}
        ]
    },
    {
        "name": "客户管理",
        "children": [
            {"name": "客户管理"}
        ]
    },
    {
        "name": "单号管理",
        "children": [
            {"name": "单号管理"}
        ]
    },
    {
        "name": "机器人管理",
        "children": [
            {"name": "机器人管理"}
        ]
    },
    {
        "name": "系统管理",
        "children": [
            {"name": "业务参数管理"}
        ]
    },
    {
        "name": "账号管理",
        "children": [
            {"name": "账号管理"},
            {"name": "部门管理"}
        ]
    },
    {
        "name": "用户中心",
        "children": [
            {"name": "用户中心"}
        ]
    },
]

PERMISSION_MENU_MAP: Dict[str, List[MenuType]] = {
    ADMIN_PERMISSION_CODE: ALL_MENUS,
    ADMIN_PERMISSION_NAME: ALL_MENUS,
    
    "waybill": [
        {
            "name": "主单管理",
            "children": [
                {"name": "运单管理"}
            ]
        },
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    "运单管理": [  
        {
            "name": "主单管理",
            "children": [
                {"name": "运单管理"}
            ]
        },
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    
    "booking": [
        {
            "name": "主单管理",
            "children": [
                {"name": "订舱管理"}
            ]
        },
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    "订舱管理": [  
        {
            "name": "主单管理",
            "children": [
                {"name": "订舱管理"}
            ]
        },
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    
    "settlement": [
        {
            "name": "结算单管理",
            "children": [
                {"name": "结算单管理"}
            ]
        },
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    "结算单管理": [  
        {
            "name": "结算单管理",
            "children": [
                {"name": "结算单管理"}
            ]
        },
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    
    "customer": [
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    "客户管理": [  
        {
            "name": "客户管理",
            "children": [
                {"name": "客户管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    
    "bill": [
        {
            "name": "单号管理",
            "children": [
                {"name": "单号管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    "单号管理": [  
        {
            "name": "单号管理",
            "children": [
                {"name": "单号管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    
    "robot": [
        {
            "name": "机器人管理",
            "children": [
                {"name": "机器人管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
    "机器人管理": [  
        {
            "name": "机器人管理",
            "children": [
                {"name": "机器人管理"}
            ]
        },
        {
            "name": "用户中心",
            "children": [
                {"name": "用户中心"}
            ]
        },
    ],
}


def generate_menus_by_permissions(permissions: List[str]) -> List[MenuType]:
    """
    根据用户权限生成菜单列表（简化版：只保留name和children）
    支持多权限合并，自动去重
    
    Args:
        permissions: 用户权限列表（权限代码）
        
    Returns:
        合并后的菜单列表（简化版：只有name和children字段）
    """
    if not permissions:
        return []
    
    if ADMIN_PERMISSION_CODE in permissions or ADMIN_PERMISSION_NAME in permissions:
        return ALL_MENUS.copy()
    
    merged_menus: Dict[str, MenuType] = {}
    
    for permission in permissions:
        if permission not in PERMISSION_MENU_MAP:
            if permission in settings.PERMISSION_CODES:
                permission_name = settings.PERMISSIONS.get(permission)
                if permission_name and permission_name in PERMISSION_MENU_MAP:
                    permission = permission_name
                else:
                    continue
            elif permission in settings.PERMISSION_NAMES:
                continue
            else:
                continue
        
        permission_menus = PERMISSION_MENU_MAP[permission]
        
        for menu in permission_menus:
            menu_name = menu["name"]
            
            if menu_name not in merged_menus:
                merged_menus[menu_name] = {
                    "name": menu_name,
                    "children": menu.get("children", []).copy()
                }
            else:
                existing_menu = merged_menus[menu_name]
                existing_children = existing_menu.get("children", [])
                new_children = menu.get("children", [])
                
                existing_child_names = {child["name"] for child in existing_children}
                
                for new_child in new_children:
                    child_name = new_child["name"]
                    if child_name not in existing_child_names:
                        existing_children.append({"name": child_name})
                        existing_child_names.add(child_name)
                
                existing_menu["children"] = existing_children
    
    return list(merged_menus.values())
