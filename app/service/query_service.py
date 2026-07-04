"""
查询服务（QueryService）。

作为 API 层与 Agent 层之间的桥梁：接收用户自然语言问题，构造 Agent 运行所需的
状态（DataAgentState）与上下文（DataAgentContext），驱动 LangGraph 工作流执行，
并将图执行过程中各节点通过 stream_writer 写出的进度/结果，以 SSE 数据帧形式
流式返回给前端。
"""
import json

from envs.image_main.Lib.urllib import error
from langchain_huggingface import HuggingFaceEmbeddings
from sentry_sdk.consts import FALSE_VALUES

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    def __init__(self,column_qdrant_repository:ColumnQdrantRepository,
                 embedding_model:HuggingFaceEmbeddings,
                 metric_qdrant_repository:MetricQdrantRepository,
                 es_value_repository:ValueEsRepository,
                 meta_mysql_repository:MetaMySqlRepository,
                 dw_mysql_repository:DwMySqlRepository,
                 ):
        # 持有 Agent 执行所需的全部 Repository 与 Embedding 模型
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_model = embedding_model
        self.metric_qdrant_repository = metric_qdrant_repository
        self.es_value_repository = es_value_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository


    async def query(self,query:str):
        """
        执行自然语言查询并以 SSE 流式返回结果。

        :param query: 用户自然语言问题
        :yield: 形如 "data: {...}\n\n" 的 SSE 数据帧
        图以 stream_mode='custom' 运行，各节点通过 runtime.stream_writer 写出的
        字典会作为 chunk 产出，这里将其序列化为 SSE 帧。
        """
        # 构造初始状态（仅含用户问题）与运行时上下文（注入各依赖）
        state = DataAgentState(query=query)
        context = DataAgentContext(column_qdrant_repository=self.column_qdrant_repository,
                                   embedding_model=self.embedding_model,
                                   metric_qdrant_repository=self.metric_qdrant_repository,
                                   es_value_repository=self.es_value_repository,
                                   meta_mysql_repository=self.meta_mysql_repository,
                                   dw_mysql_repository=self.dw_mysql_repository)

        try:
            # 流式驱动图执行，逐个产出节点进度/结果
            async for chunk in graph.astream(input=state,
                                             context=context,
                                             stream_mode='custom'):
                yield f'data: {json.dumps(chunk,ensure_ascii=False,default=str)}\n\n'

        except Exception as e:
            # 执行过程中抛出的异常以错误帧返回，避免连接中断
            error = {'type': 'error', 'message': str(e)}
            yield f"data: {json.dumps(error,ensure_ascii=False,default=str)}\n\n"
