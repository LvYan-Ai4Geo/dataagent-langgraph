"""SQLAlchemy ORM 声明式基类，所有元数据库 ORM 模型继承自此 Base。"""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
