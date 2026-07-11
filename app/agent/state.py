"""
Agent 状态定义模块。

LangGraph 使用 TypedDict 在节点之间共享状态。本模块定义了数据查询 Agent
在整个工作流流转过程中携带的所有字段，包括用户输入、召回结果、过滤后的
表/指标信息、生成与校验的 SQL，以及执行错误等。
"""
from typing import TypedDict
from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class ColumnInfoState(TypedDict):
    """传递给 LLM 的字段信息（去除了内部 id 等字段，仅保留 LLM 生成 SQL 所需信息）。"""
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    """传递给 LLM 的表信息，columns 为该表下被选中的字段列表。"""
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class MetricInfoState(TypedDict):
    """传递给 LLM 的指标信息。"""
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class DateInfoState(TypedDict):
    """当前日期上下文，用于让 LLM 正确解析“今天/本月/上季度”等时间语义。"""
    date: str
    weekday: str
    quarter: str


class DbInfoState(TypedDict):
    """数据库环境信息，用于约束生成 SQL 的方言与版本。"""
    version: str
    dialect: str


class DataAgentState(TypedDict):
    """
    数据查询 Agent 的完整工作流状态。

    流转过程：
        query -> keywords -> retrieved_* -> table_infos/metric_infos
              -> date_info/db_info -> sql -> error -> (修正后)执行结果

    多轮记忆：
        messages 记录本会话（同一 thread_id）历史轮次的问答摘要，
        由 Checkpointer 按 thread_id 持久化。extract_keywords 节点会读取
        历史消息，将上一轮的 query/sql/结果摘要拼入当前轮上下文，
        使召回与生成能利用多轮对话信息。
    """
    query: str                              # 用户自然语言问题

    keywords: list[str]                     # 抽取/扩展后的检索关键词
    retrieved_column_infos: list[ColumnInfo]   # 从 Qdrant 召回的字段信息
    retrieved_metric_infos: list[MetricInfo]   # 从 Qdrant 召回的指标信息
    retrieved_value_infos: list[ValueInfo]     # 从 ES 召回的字段取值信息

    table_infos: list[TableInfoState]       # 合并并过滤后的表/字段信息（供生成 SQL 使用）
    metric_infos: list[MetricInfoState]     # 过滤后的指标信息（供生成 SQL 使用）

    date_info: DateInfoState                # 当前日期上下文
    db_info: DbInfoState                    # 目标数据库环境上下文

    error: str                              # SQL 校验错误信息（None 表示校验通过）
    sql: str                                # 生成/修正后的 SQL 语句

    messages: list[dict]                    # 多轮对话历史（每轮含 query/sql/result 摘要）
