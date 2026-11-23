"""
代理管理接口
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.core.response import success_response, ResponseModel
from app.database import get_db
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

from app.models.agent import Agent
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentQuery
)

router = APIRouter()

def _format_agent_response(agent: Agent) -> dict:
    return {
        "id": str(agent.id),
        "agent_code": agent.agent_code,
        "agent_type": agent.agent_type,
        "agent_name": agent.agent_name,
        "contact_person": agent.contact_person,
        "contact_phone": agent.contact_phone,
        "document_fee": agent.document_fee,
        "settlement_method": agent.settlement_method,
        "creator_id": str(agent.creator_id),
        "creator_name": agent.creator_name,
        "created_at": format_datetime_china(agent.created_at),
        "updated_at": format_datetime_china(agent.updated_at)
    }

@router.post("", summary="新增代理", response_model=ResponseModel[AgentResponse])
async def create_agent(
    agent_in: AgentCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """新增代理"""
    agent_code = agent_in.agent_code
    if not agent_code:
        latest_agent = db.query(Agent).filter(Agent.agent_code.like("KCYS%")).order_by(Agent.agent_code.desc()).first()
        if latest_agent and latest_agent.agent_code:
            try:
                num = int(latest_agent.agent_code[4:])
                agent_code = f"KCYS{(num + 1):03d}"
            except ValueError:
                agent_code = "KCYS001"
        else:
            agent_code = "KCYS001"

    new_agent = Agent(
        agent_code=agent_code,
        agent_type=agent_in.agent_type,
        agent_name=agent_in.agent_name,
        contact_person=agent_in.contact_person,
        contact_phone=agent_in.contact_phone,
        document_fee=agent_in.document_fee,
        settlement_method=agent_in.settlement_method,
        creator_id=current_user.id,
        creator_name=current_user.name
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    
    return success_response(data=_format_agent_response(new_agent), msg="代理创建成功")


@router.put("/{agent_id}", summary="编辑代理", response_model=ResponseModel[AgentResponse])
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """编辑代理"""
    agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
    if not agent:
        raise NotFoundException("代理不存在")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)
            
    db.commit()
    db.refresh(agent)
    
    return success_response(data=_format_agent_response(agent), msg="代理更新成功")


@router.get("/{agent_id}", summary="获取代理详情", response_model=ResponseModel[AgentResponse])
async def get_agent(
    agent_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取代理详情"""
    agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
    if not agent:
        raise NotFoundException("代理不存在")
    
    return success_response(data=_format_agent_response(agent), msg="查询成功")


@router.delete("/{agent_id}", summary="删除代理", response_model=ResponseModel[Any])
async def delete_agent(
    agent_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除代理"""
    agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
    if not agent:
        raise NotFoundException("代理不存在")
        
    db.delete(agent)
    db.commit()
    
    return success_response(msg="代理删除成功")


@router.get("", summary="获取代理列表", response_model=ResponseModel[AgentListResponse])
async def get_agent_list(
    query: AgentQuery = Depends(),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取代理列表"""
    query_obj = db.query(Agent)
    
    if query.agent_name:
        query_obj = query_obj.filter(Agent.agent_name.like(f"%{query.agent_name}%"))
        
    if query.agent_type is not None:
        query_obj = query_obj.filter(Agent.agent_type == query.agent_type)
    
    total = query_obj.count()
    
    offset = (query.page - 1) * query.pageSize
    agents = query_obj.order_by(Agent.created_at.desc(), Agent.id.desc()).offset(offset).limit(query.pageSize).all()
    
    items = [_format_agent_response(a) for a in agents]
    
    return success_response(data={"total": total, "items": items}, msg="查询成功")
