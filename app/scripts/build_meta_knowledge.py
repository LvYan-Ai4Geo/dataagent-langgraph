"""
元知识库构建脚本（离线一次性执行）。

用法：
    python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml

该脚本初始化所有客户端，构造 MetaKnowledgeService，根据传入的 meta_config.yaml
完成表/字段/指标元信息同步、Qdrant 向量索引建立、ES 全文索引建立，
是 Agent 在线查询能够正确召回的前提。
"""
import argparse
import asyncio
from pathlib import Path

from app.clients.els_client_manager import els_client
from app.clients.emb_client_manager import emb_client
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.service.meta_knowledge_service import MetaKnowledgeService


async def build(config_path:Path):
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init_client()
    emb_client.init()
    els_client.init()


    async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:

        # 1. repository层持有session，完成数据的底层读写
        meta_mysql_repository = MetaMySqlRepository(meta_session)
        dw_mysql_repository = DwMySqlRepository(dw_session)
        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
        value_es_repository = ValueEsRepository(els_client.client)
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)
        # 2. service层持有repository
        meta_knowledge_service = MetaKnowledgeService(meta_mysql_repository=meta_mysql_repository,
                                                      dw_mysql_repository=dw_mysql_repository,
                                                      column_qdrant_repository=column_qdrant_repository,
                                                      embedding_model=emb_client.client,
                                                      es_repository=value_es_repository,
                                                      metric_qdrant_repository=metric_qdrant_repository)

        # 3. service层执行
        await meta_knowledge_service.build(config_path)

    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await els_client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-c','--conf')

    args = parser.parse_args()
    config_path = args.conf

    asyncio.run((build(Path(config_path))))