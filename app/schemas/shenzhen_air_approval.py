from typing import Optional, List, Union
from pydantic import BaseModel, Field
from datetime import datetime

class ShenzhenAirApprovalBaseItem(BaseModel):
    id: str
    parent_id: Optional[str] = None
    flight_number: Optional[str] = None
    flight_date: Optional[str] = None
    aircraft_type: Optional[str] = None
    departure_time: Optional[str] = None
    routing: Optional[str] = None
    agent: Optional[str] = None
    status: Optional[str] = None
    type: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ShenzhenAirApprovalNarrowItem(ShenzhenAirApprovalBaseItem):
    f_booking: Optional[str] = None
    f_approval: Optional[str] = None
    c_booking: Optional[str] = None
    c_approval: Optional[str] = None
    other_booking: Optional[str] = None
    other_approval: Optional[str] = None
    control: Optional[str] = None
    open_status: Optional[str] = None

class ShenzhenAirApprovalWideItem(ShenzhenAirApprovalBaseItem):
    board_booking: Optional[str] = None
    board_approval: Optional[str] = None
    backup_board: Optional[str] = None
    box_booking: Optional[str] = None
    box_approval: Optional[str] = None
    backup_box: Optional[str] = None

class ShenzhenAirApprovalListResponse(BaseModel):
    total: int
    items: List[Union[ShenzhenAirApprovalNarrowItem, ShenzhenAirApprovalWideItem]]
