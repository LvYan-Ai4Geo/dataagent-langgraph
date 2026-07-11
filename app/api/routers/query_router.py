"""
查询路由。

对外暴露 POST /api/query 接口，接收用户自然语言问题，通过 QueryService
驱动 LangGraph 工作流，并以 Server-Sent Events (SSE) 流式返回各节点执行进度
与最终 SQL 执行结果。请求体携带 thread_id 时启用短期会话记忆（多轮对话）。
"""
from typing import Annotated
from fastapi import APIRouter
from fastapi.params import Depends
from starlette.responses import StreamingResponse
from app.api.dependencies import query_service

from app.api.schema.query_schema import QuerySchema
from app.service.query_service import QueryService

query_router = APIRouter()



@query_router.post('/api/query')
async def query_handler(query:QuerySchema,query_service:Annotated[QueryService,Depends(query_service)]):
    """
    处理自然语言查询请求。

    :param query: 请求体，包含 query 字段（用户自然语言问题）与可选 thread_id（会话标识）
    :param query_service: 通过依赖注入获得的 QueryService
    :return: 以 text/event_stream 形式流式返回图执行过程中的进度与结果
    """
    return StreamingResponse(query_service.query(query=query.query, thread_id=query.thread_id),media_type='text/event_stream')
