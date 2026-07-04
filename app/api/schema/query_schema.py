"""
查询接口的请求/响应数据模型。
"""
from pydantic import BaseModel


class QuerySchema(BaseModel):
    """查询请求体：仅包含一个 query 字段，即用户的自然语言问题。"""
    query:str
