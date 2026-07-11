"""
FastAPI 依赖注入提供者。

为查询接口提供构造 QueryService 所需的全部 Repository 与 Embedding 模型实例。
各 provider 从对应的客户端管理器单例中获取底层客户端，再包装成 Repository。
MySQL 的 session 通过 async sessionmaker 逐请求创建，保证请求间隔离。
"""
from typing import Annotated
from fastapi.params import Depends
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.els_client_manager import els_client
from app.clients.emb_client_manager import emb_client
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.service.query_service import QueryService


async def get_column_qdrant_repository() -> ColumnQdrantRepository:
    """提供字段向量检索 Repository（基于全局 qdrant 客户端）。"""
    return ColumnQdrantRepository(qdrant_client_manager.client)


async def get_embedding_model() -> HuggingFaceEmbeddings:
    """提供 Embedding 模型实例。"""
    return emb_client.client


async def get_metric_qdrant_repository() -> MetricQdrantRepository:
    """提供指标向量检索 Repository。"""
    return MetricQdrantRepository(qdrant_client_manager.client)


async def get_es_repository() -> ValueEsRepository:
    """提供字段值全文检索 Repository。"""
    return ValueEsRepository(els_client.client)


async def get_meta_session():
    """提供元数据库的异步会话（逐请求）。"""
    async with meta_mysql_client_manager.session_factory() as meta_mysql_session:
        yield meta_mysql_session

async def get_meta_mysql_repository(session:Annotated[AsyncSession,Depends(get_meta_session)]) -> MetaMySqlRepository:
    """提供元数据库 Repository。"""
    return MetaMySqlRepository(session=session)

async def get_dw_session():
    """提供数仓库的异步会话（逐请求）。"""
    async with dw_mysql_client_manager.session_factory() as dw_mysql_session:
        yield dw_mysql_session

async def get_dw_mysql_repository(session:Annotated[AsyncSession,Depends(get_dw_session)]) -> DwMySqlRepository:
    """提供数仓库 Repository。"""
    return DwMySqlRepository(session=session)


async def query_service(
        column_qdrant_repository: Annotated[ColumnQdrantRepository, Depends(get_column_qdrant_repository)],
        embedding_model: Annotated[HuggingFaceEmbeddings, Depends(get_embedding_model)],
        metric_qdrant_repository: Annotated[MetricQdrantRepository, Depends(get_metric_qdrant_repository)],
        es_value_repository: Annotated[ValueEsRepository, Depends(get_es_repository)],
        meta_mysql_repository: Annotated[MetaMySqlRepository, Depends(get_meta_mysql_repository)],
        dw_mysql_repository: Annotated[DwMySqlRepository, Depends(get_dw_mysql_repository)]) -> QueryService:
    """聚合所有 Repository 与 Embedding 模型，构造 QueryService 实例。"""
    return QueryService(column_qdrant_repository=column_qdrant_repository,
                        embedding_model=embedding_model,
                        metric_qdrant_repository=metric_qdrant_repository,
                        es_value_repository=es_value_repository,
                        meta_mysql_repository=meta_mysql_repository,
                        dw_mysql_repository=dw_mysql_repository)
