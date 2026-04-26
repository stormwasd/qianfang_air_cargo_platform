# ============================================================
# 千方航空物流平台 - Docker 镜像构建文件
# 基于 Python 3.11 slim，包含中文字体支持（PDF 生成需要）
# ============================================================

FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
# - gcc + default-libmysqlclient-dev: MySQL 客户端编译依赖
# - fonts-wqy-zenhei: 中文字体（reportlab 生成 PDF 时需要）
# - tzdata: 时区数据
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    fonts-wqy-zenhei \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 预创建 generated_files 目录（运行时通过 volume 挂载覆盖）
RUN mkdir -p /app/generated_files

# 暴露服务端口
EXPOSE 8000

# 启动命令
# --workers 可根据服务器 CPU 核心数调整
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
