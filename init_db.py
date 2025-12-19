"""
数据库初始化脚本
"""
from app.database import engine, Base
from app.models import User, Department, Customer, BusinessConfig
from app.core.security import get_password_hash
from app.utils.helpers import format_permissions_to_json


def init_database():
    """初始化数据库"""
    print("开始创建数据库表...")
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成！")
    
    # 检查是否已有管理员账号
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        admin_user = db.query(User).filter(User.phone == "13800000000").first()
        if not admin_user:
            print("创建默认管理员账号...")
            # 创建默认部门
            admin_dept = Department(name="系统管理部")
            db.add(admin_dept)
            db.flush()
            
            # 创建默认管理员账号
            admin_user = User(
                phone="13800000000",
                password_hash=get_password_hash("admin123456"),
                name="系统管理员",
                department_id=admin_dept.id,
                permissions=format_permissions_to_json(["管理员"]),
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("默认管理员账号创建成功！")
            print("手机号: 13800000000")
            print("密码: admin123456")
        else:
            print("默认管理员账号已存在，跳过创建")
    except Exception as e:
        db.rollback()
        print(f"创建默认账号时出错: {e}")
    finally:
        db.close()
    
    print("数据库初始化完成！")


if __name__ == "__main__":
    init_database()

