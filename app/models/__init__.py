from app.models.user import User
from app.models.department import Department
from app.models.customer import Customer
from app.models.config import BusinessConfig
from app.models.waybill import Waybill
from app.models.booking import Booking
from app.models.user_department import user_department  # 确保关联表被导入

__all__ = ["User", "Department", "Customer", "BusinessConfig", "Waybill", "Booking"]

