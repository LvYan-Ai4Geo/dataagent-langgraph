"""
查询接口的请求/响应数据模型。
"""
from pydantic import BaseModel


class QuerySchema(BaseModel):
    """查询请求体。

    - query: 用户的自然语言问题
    - thread_id: 会话标识，用于启用 LangGraph 短期会话记忆。
      同一 thread_id 的多次请求会基于历史 state 累积上下文，支持多轮对话。
      为空时后端会临时生成一个（视为无历史的单次会话）。
    """
    query: str
    thread_id: str | None = None
