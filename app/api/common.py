"""
公共功能接口
"""
import os
import shutil
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from app.core.response import success_response, ResponseModel
from app.api.deps import get_current_active_user

router = APIRouter()

# 上传根目录配置
UPLOAD_DIR = "static/uploads"

@router.post("/upload", summary="通用文件上传", response_model=ResponseModel[dict])
async def upload_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_active_user)
):
    """
    通用文件上传接口
    
    将文件保存在服务器本地，按月份分目录存储，并返回可访问的相对 URL。
    - 返回 `url` 字段形如：`/static/uploads/202607/uuid-filename.png`
    """
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")

    # 根据年月分目录存放
    current_month = datetime.now().strftime("%Y%m")
    save_dir = os.path.join(UPLOAD_DIR, current_month)
    os.makedirs(save_dir, exist_ok=True)
    
    # 防止文件名冲突，使用 uuid 加上原文件名后缀
    original_filename = file.filename or "unknown_file"
    file_ext = os.path.splitext(original_filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    
    file_path = os.path.join(save_dir, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"文件保存失败: {str(e)}")
    finally:
        file.file.close()
        
    # 构建相对 URL
    file_url = f"/{UPLOAD_DIR}/{current_month}/{unique_filename}"
    
    return success_response(
        data={
            "url": file_url,
            "filename": original_filename
        },
        msg="文件上传成功"
    )
