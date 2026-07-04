"""
Agent 运行时上下文（依赖注入容器）。

LangGraph 的 context_schema 机制允许在图执行期间向所有节点注入共享的依赖对象，
而不必将这些对象塞进可变的 state 中。本 DataAgentContext 即承载了各节点所需的
Repository 与 Embedding 模型实例，由调用方（如 QueryService）在调用 graph.astream
时通过 context= 参数传入。
"""
from dataclasses import dataclass

from langchain_huggingface import HuggingFaceEmbeddings

from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


@dataclass
class DataAgentContext():
    """各节点共享的运行时依赖（Repository 与 Embedding 模型）。"""
    column_qdrant_repository: ColumnQdrantRepository    # 字段向量检索（Qdrant）
    embedding_model: HuggingFaceEmbeddings              # 文本向量化模型（BGE）
    metric_qdrant_repository: MetricQdrantRepository    # 指标向量检索（Qdrant）
    es_value_repository: ValueEsRepository              # 字段值全文检索（Elasticsearch）
    meta_mysql_repository: MetaMySqlRepository          # 元数据库读写（表/字段/指标元信息）
    dw_mysql_repository: DwMySqlRepository              # 数仓库读写（SQL 校验与执行）
