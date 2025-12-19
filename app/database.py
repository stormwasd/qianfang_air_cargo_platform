"""
数据库连接和会话管理
使用SQLAlchemy 2.0
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from contextlib import contextmanager
from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 基础模型类"""
    pass


# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # 连接前检查连接是否有效
    echo=settings.DEBUG,  # 根据配置决定是否输出SQL
    future=True,  # 使用SQLAlchemy 2.0风格
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True  # 使用SQLAlchemy 2.0风格
)


def get_db() -> Session:
    """
    获取数据库会话（依赖注入）
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    获取数据库会话上下文管理器
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

