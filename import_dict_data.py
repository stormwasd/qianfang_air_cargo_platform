"""
数据字典导入脚本

功能：
- 导入字典类型（DictType）
- 导入字典类型下的所有选项（DictOption）

使用方法：
    python import_dict_data.py <json_file_path>

JSON文件格式示例：
{
    "dict_type": {
        "name": "运价代码",
        "type": "freight_code",
        "status": 1
    },
    "options": [
        {
            "label": "最低运价",
            "value": "M",
            "status": 1
        },
        {
            "label": "最低运价",
            "value": "N",
            "status": 1
        },
        {
            "label": "普通运价",
            "value": "Q",
            "status": 1
        }
    ]
}
"""
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any
from app.database import get_db_context
from app.models.dict_type import DictType
from app.models.dict_option import DictOption
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


def load_json_file(file_path: str) -> Dict[str, Any]:
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"错误：文件不存在 - {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误：JSON格式错误 - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误：读取文件失败 - {e}")
        sys.exit(1)


def validate_data(data: Dict[str, Any]) -> bool:
    """验证数据格式"""
    if "dict_type" not in data:
        print("错误：JSON文件中缺少 'dict_type' 字段")
        return False
    
    dict_type = data["dict_type"]
    required_fields = ["name", "type"]
    for field in required_fields:
        if field not in dict_type:
            print(f"错误：dict_type 中缺少必需字段 '{field}'")
            return False
    
    if "options" not in data:
        print(" 警告：JSON文件中缺少 'options' 字段，将只导入字典类型")
        data["options"] = []
    
    if not isinstance(data["options"], list):
        print("错误：'options' 必须是数组格式")
        return False
    
    for i, option in enumerate(data["options"]):
        if "label" not in option or "value" not in option:
            print(f"错误：options[{i}] 中缺少必需字段 'label' 或 'value'")
            return False
    
    return True


def import_dict_type(db, dict_type_data: Dict[str, Any], update_if_exists: bool = True) -> DictType:
    """导入字典类型"""
    type_identifier = dict_type_data["type"]
    
    existing_type = db.query(DictType).filter(DictType.type == type_identifier).first()
    
    if existing_type:
        if update_if_exists:
            existing_type.name = dict_type_data["name"]
            if "status" in dict_type_data:
                existing_type.status = dict_type_data["status"]
            print(f"更新字典类型：{existing_type.type} ({existing_type.name})")
            return existing_type
        else:
            print(f" 字典类型已存在，跳过：{existing_type.type} ({existing_type.name})")
            return existing_type
    else:
        new_type = DictType(
            name=dict_type_data["name"],
            type=dict_type_data["type"],
            status=dict_type_data.get("status", 1)
        )
        db.add(new_type)
        db.flush()  
        print(f"创建字典类型：{new_type.type} ({new_type.name})")
        return new_type


def import_dict_options(db, dict_type: DictType, options: List[Dict[str, Any]], 
                       update_if_exists: bool = True, clear_existing: bool = False) -> tuple:
    """导入字典选项
    
    Returns:
        (created_count, updated_count, skipped_count)
    """
    if clear_existing:
        deleted_count = db.query(DictOption).filter(
            DictOption.dict_type_id == dict_type.id
        ).delete()
        if deleted_count > 0:
            print(f" 已删除 {deleted_count} 个现有选项")
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for option_data in options:
        label = option_data["label"]
        value = option_data["value"]
        status = option_data.get("status", 1)
        color_type = option_data.get("color_type")  
        
        existing_option = db.query(DictOption).filter(
            DictOption.dict_type_id == dict_type.id,
            DictOption.label == label,
            DictOption.value == value
        ).first()
        
        if existing_option:
            if update_if_exists:
                existing_option.status = status
                if color_type is not None:
                    existing_option.color_type = color_type
                updated_count += 1
                print(f"  更新选项：{label} = {value}")
            else:
                skipped_count += 1
                print(f"   跳过已存在选项：{label} = {value}")
        else:
            new_option = DictOption(
                dict_type_id=dict_type.id,
                label=label,
                value=value,
                status=status,
                color_type=color_type
            )
            db.add(new_option)
            created_count += 1
            print(f"  创建选项：{label} = {value}")
    
    return created_count, updated_count, skipped_count


def main():
    parser = argparse.ArgumentParser(
        description="数据字典导入脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
JSON文件格式示例：
{
    "dict_type": {
        "name": "运价代码",
        "type": "freight_code",
        "status": 1
    },
    "options": [
        {
            "label": "最低运价",
            "value": "M",
            "status": 1
        },
        {
            "label": "最低运价",
            "value": "N",
            "status": 1
        }
    ]
}
        """
    )
    parser.add_argument(
        "json_file",
        type=str,
        help="JSON数据文件路径"
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="如果数据已存在，不更新，直接跳过"
    )
    parser.add_argument(
        "--clear-options",
        action="store_true",
        help="导入前先删除该字典类型下的所有现有选项（谨慎使用）"
    )
    
    args = parser.parse_args()
    
    file_path = Path(args.json_file)
    if not file_path.exists():
        print(f"错误：文件不存在 - {args.json_file}")
        sys.exit(1)
    
    print(f"加载文件：{args.json_file}")
    data = load_json_file(str(file_path))
    
    print("验证数据格式...")
    if not validate_data(data):
        sys.exit(1)
    print("数据格式验证通过")
    
    print("\n开始导入数据...")
    update_if_exists = not args.no_update
    
    try:
        with get_db_context() as db:
            print("\n导入字典类型...")
            dict_type = import_dict_type(db, data["dict_type"], update_if_exists=update_if_exists)
            
            if data.get("options"):
                print(f"\n导入字典选项（共 {len(data['options'])} 个）...")
                created, updated, skipped = import_dict_options(
                    db,
                    dict_type,
                    data["options"],
                    update_if_exists=update_if_exists,
                    clear_existing=args.clear_options
                )
                
                print(f"\n导入统计：")
                print(f"  - 创建：{created} 个")
                print(f"  - 更新：{updated} 个")
                print(f"  - 跳过：{skipped} 个")
            else:
                print("\n 没有选项需要导入")
            
            print("\n导入完成！")
    
    except Exception as e:
        print(f"\n导入失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

