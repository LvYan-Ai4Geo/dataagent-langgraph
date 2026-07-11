"""
LangGraph 工作流定义模块。

本模块负责构建“数据查询 Agent”的核心编排图：
    1. 从用户自然语言问题中抽取关键词；
    2. 并行地从 Qdrant / Elasticsearch / Qdrant 中召回 字段、字段值、指标 信息；
    3. 合并召回结果，并补全关联表、主外键等元信息；
    4. 由 LLM 过滤出真正需要的指标与表字段；
    5. 注入当前日期、数据库方言等额外上下文；
    6. 由 LLM 生成 SQL；
    7. 在数仓中校验 SQL；
       - 校验通过 → 直接执行；
       - 校验失败 → 由 LLM 根据错误信息修正后再次执行；
    8. 执行 SQL 并返回结果。

整个图通过 `DataAgentContext`（依赖注入）向各节点提供 Repository 与 Embedding 模型，
通过 `DataAgentState`（TypedDict）在节点间传递状态。
"""
import asyncio
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extract_context import add_extract_context
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.run_sql import run_sql
from app.agent.nodes.validate_sql import validate_sql
from app.agent.state import DataAgentState
from app.clients.els_client_manager import els_client
from app.clients.emb_client_manager import emb_client
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

# 1. 创建状态图：state_schema 定义节点间传递的状态，context_schema 定义依赖注入的运行时上下文
graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 2. 添加节点：每个节点对应工作流中的一个处理步骤
graph_builder.add_node('extract_keywords', extract_keywords)      # 关键词抽取
graph_builder.add_node('recall_column', recall_column)            # 字段向量召回
graph_builder.add_node('recall_metric', recall_metric)            # 指标向量召回
graph_builder.add_node('recall_value', recall_value)              # 字段值全文召回
graph_builder.add_node('merge_retrieved_info', merge_retrieved_info)  # 合并召回结果
graph_builder.add_node('filter_metric', filter_metric)            # 指标过滤
graph_builder.add_node('filter_table', filter_table)              # 表/字段过滤
graph_builder.add_node('add_extract_context', add_extract_context)  # 注入日期/数据库上下文
graph_builder.add_node('generate_sql', generate_sql)              # 生成 SQL
graph_builder.add_node('validate_sql', validate_sql)              # 校验 SQL
graph_builder.add_node('correct_sql', correct_sql)                # 修正 SQL
graph_builder.add_node('run_sql', run_sql)                        # 执行 SQL

# 3. 添加边：定义节点之间的执行顺序
graph_builder.add_edge(START, 'extract_keywords')
# 关键词抽取后，三个召回节点并行执行（LangGraph 会在所有入边完成后触发目标节点）
graph_builder.add_edge('extract_keywords', 'recall_column')
graph_builder.add_edge('extract_keywords', 'recall_value')
graph_builder.add_edge('extract_keywords', 'recall_metric')
# 三个召回结果都到达后，进入合并节点
graph_builder.add_edge('recall_column', 'merge_retrieved_info')
graph_builder.add_edge('recall_value', 'merge_retrieved_info')
graph_builder.add_edge('recall_metric', 'merge_retrieved_info')
# 合并后并行过滤指标与表
graph_builder.add_edge('merge_retrieved_info', 'filter_metric')
graph_builder.add_edge('merge_retrieved_info', 'filter_table')
# 过滤完成后注入额外上下文，再生成 SQL
graph_builder.add_edge('filter_metric', 'add_extract_context')
graph_builder.add_edge('filter_table', 'add_extract_context')
graph_builder.add_edge('add_extract_context', 'generate_sql')
graph_builder.add_edge('generate_sql', 'validate_sql')

# 条件边：根据校验结果决定走向
#   - state['error'] is None  表示校验通过 -> 执行 SQL
#   - state['error'] 不为 None 表示校验失败 -> 进入修正节点
graph_builder.add_conditional_edges(source='validate_sql',
                                    path=lambda state: 'correct_sql' if state['error'] is not None else 'run_sql',
                                    path_map={'run_sql': 'run_sql', 'correct_sql': 'correct_sql'})
# 修正后再次执行
graph_builder.add_edge('correct_sql', 'run_sql')
graph_builder.add_edge('run_sql', END)

# 4. 编图：将上述定义编译为可执行的图实例
#    传入 InMemorySaver 作为 checkpointer，实现短期会话记忆：
#    调用方在 graph.astream 时通过 config={"configurable": {"thread_id": ...}}
#    指定会话标识，同一 thread_id 的多次调用会基于历史 state 累积上下文，
#    从而支持多轮对话（如“再按性别细分”“改成环比”等追问）。
memory = InMemorySaver()
graph = graph_builder.compile(checkpointer=memory)
# print(graph.get_graph().draw_mermaid())

if __name__ == '__main__':
    async def test():
        # 初始化各类客户端（Qdrant / Embedding / ES / MySQL 元数据库 / MySQL 数仓库）
        qdrant_client_manager.init_client()
        emb_client.init()
        els_client.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

        # 打开会话并构造各 Repository，再组装成运行时上下文
        async with meta_mysql_client_manager.session_factory() as meta_mysql_session,dw_mysql_client_manager.session_factory() as dw_mysql_session:
            column_qdrant_repository = ColumnQdrantRepository(client=qdrant_client_manager.client)
            metric_qdrant_repository = MetricQdrantRepository(client=qdrant_client_manager.client)
            es_value_repository = ValueEsRepository(client=els_client.client)
            meta_mysql_repository = MetaMySqlRepository(session=meta_mysql_session)
            dw_mysql_repository = DwMySqlRepository(session=dw_mysql_session)

            # 构造初始状态（仅含用户问题与 error 占位）
            state = DataAgentState(query='统计华北地区中男生的销售总额', error=None)
            context = DataAgentContext(column_qdrant_repository=column_qdrant_repository,
                                       embedding_model=emb_client.client,
                                       metric_qdrant_repository=metric_qdrant_repository,
                                       es_value_repository=es_value_repository,
                                       meta_mysql_repository=meta_mysql_repository,
                                       dw_mysql_repository=dw_mysql_repository)

            # 携带 thread_id 运行图，启用短期会话记忆：
            #   同一 thread_id 的后续调用会基于历史 state 继续累积上下文。
            config = {"configurable": {"thread_id": "test-thread-1"}}
            async for chunk in graph.astream(input=state,
                                             context=context,
                                             config=config,
                                             stream_mode='custom'):
                print(chunk)

        # 关闭所有客户端连接
        await qdrant_client_manager.close()
        await els_client.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()


    asyncio.run(test())
