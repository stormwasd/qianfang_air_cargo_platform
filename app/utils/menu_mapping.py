"""
权限到菜单的映射关系
定义每个权限对应的菜单结构（简化版：只保留父子关系）
"""
from typing import List, Dict, Any
from app.config import settings

# 菜单项类型定义（简化版：只有name和children）
MenuType = Dict[str, Any]

# 管理员权限代码
ADMIN_PERMISSION_CODE = "admin"
# 管理员权限名称（向后兼容）
ADMIN_PERMISSION_NAME = settings.PERMISSIONS.get(ADMIN_PERMISSION_CODE, "管理员")

# 所有菜单项的基础定义（简化版）
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

# 单个权限对应的菜单映射（简化版：只保留name和children）
PERMISSION_MENU_MAP: Dict[str, List[MenuType]] = {
    # 管理员权限（支持代码和名称）
    ADMIN_PERMISSION_CODE: ALL_MENUS,
    ADMIN_PERMISSION_NAME: ALL_MENUS,
    
    # 运单管理权限（支持代码和名称）
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
    "运单管理": [  # 向后兼容：保留权限名称作为key
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
    
    # 订舱管理权限（支持代码和名称）
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
    "订舱管理": [  # 向后兼容：保留权限名称作为key
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
    
    # 结算单管理权限（支持代码和名称）
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
    "结算单管理": [  # 向后兼容：保留权限名称作为key
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
    
    # 如果包含管理员权限，直接返回所有菜单（支持代码和名称）
    if ADMIN_PERMISSION_CODE in permissions or ADMIN_PERMISSION_NAME in permissions:
        return ALL_MENUS.copy()
    
    # 用于存储合并后的菜单，key为菜单的name
    merged_menus: Dict[str, MenuType] = {}
    
    # 遍历每个权限，合并菜单
    for permission in permissions:
        # 尝试直接查找
        if permission not in PERMISSION_MENU_MAP:
            # 如果是权限代码，尝试转换为名称查找
            if permission in settings.PERMISSION_CODES:
                permission_name = settings.PERMISSIONS.get(permission)
                if permission_name and permission_name in PERMISSION_MENU_MAP:
                    permission = permission_name
                else:
                    continue
            # 如果是权限名称，尝试转换为代码查找
            elif permission in settings.PERMISSION_NAMES:
                # 已经尝试过名称，跳过
                continue
            else:
                continue
        
        permission_menus = PERMISSION_MENU_MAP[permission]
        
        for menu in permission_menus:
            menu_name = menu["name"]
            
            if menu_name not in merged_menus:
                # 新菜单，直接添加
                merged_menus[menu_name] = {
                    "name": menu_name,
                    "children": menu.get("children", []).copy()
                }
            else:
                # 菜单已存在，需要合并children
                existing_menu = merged_menus[menu_name]
                existing_children = existing_menu.get("children", [])
                new_children = menu.get("children", [])
                
                # 用于存储已存在的子菜单name，避免重复
                existing_child_names = {child["name"] for child in existing_children}
                
                # 合并children，去重
                for new_child in new_children:
                    child_name = new_child["name"]
                    if child_name not in existing_child_names:
                        existing_children.append({"name": child_name})
                        existing_child_names.add(child_name)
                
                existing_menu["children"] = existing_children
    
    # 转换为列表
    return list(merged_menus.values())
