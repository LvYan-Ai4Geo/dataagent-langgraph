"""
FastAPI 生命周期管理。

在应用启动时初始化所有外部客户端（Qdrant / Embedding / ES / MySQL 元数据库 /
MySQL 数仓库），在应用关闭时释放连接。通过 lifespan 上下文管理器挂载到
FastAPI 实例上，确保资源随应用生命周期正确管理。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.clients.els_client_manager import els_client
from app.clients.emb_client_manager import emb_client
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager


@asynccontextmanager
async def lifespan(app:FastAPI):
    # 启动：初始化所有客户端连接
    qdrant_client_manager.init_client()
    emb_client.init()
    els_client.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    yield
    # 关闭：释放所有客户端连接
    await qdrant_client_manager.close()
    await els_client.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
