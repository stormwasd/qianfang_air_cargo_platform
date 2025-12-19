# 千方航空物流平台

## 项目简介

千方航空物流平台后端服务，基于 FastAPI 框架开发。

## 技术栈

- Python 3.8+
- FastAPI
- SQLAlchemy
- MySQL
- JWT 认证
- Bcrypt 密码加密

## 项目结构

```
qianfang_air_cargo_platform/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── config.py            # 配置文件
│   ├── database.py          # 数据库连接
│   ├── models/              # 数据库模型
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # API路由
│   ├── core/                # 核心功能
│   └── utils/               # 工具函数
├── requirements.txt
├── README.md
└── API_DOCS.md
```

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

编辑 `app/config.py` 文件，修改数据库连接配置：

```python
MYSQL_HOST: str = "localhost"
MYSQL_PORT: int = 3306
MYSQL_USER: str = "root"
MYSQL_PASSWORD: str = "password"
MYSQL_DATABASE: str = "qianfang_air_cargo"
```

### 3. 初始化数据库

```bash
python init_db.py
```

### 4. 运行服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，访问：
- API文档：http://localhost:8000/docs
- 备用文档：http://localhost:8000/redoc

## 功能模块

- 用户认证：登录、JWT token管理
- 用户中心：查看用户信息、重置密码
- 账号管理：新增、查看、启用/停用、更新密码、删除账号
- 部门管理：新建、查看部门
- 客户管理：新增、查询客户信息
- 业务参数管理：初始化配置、查看和更新配置

## 权限说明

- **管理员**：拥有所有权限，可以管理账号、部门等
- **运单管理**：运单相关权限
- **订舱管理**：订舱相关权限
- **结算单管理**：结算单相关权限

## 注意事项

1. 生产环境需要修改 `config.py` 中的 `SECRET_KEY`
2. 数据库连接池配置可根据实际需求调整
3. 所有需要管理员权限的接口都会进行权限验证

