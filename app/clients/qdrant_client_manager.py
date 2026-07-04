"""
Qdrant 客户端管理器。

封装 AsyncQdrantClient 的初始化与关闭，以模块级单例 `qdrant_client_manager` 暴露。
Qdrant 用于存储字段与指标的向量索引，支撑工作流中的字段/指标向量召回。
配置来自 app_config.yaml 的 qdrant 段。
"""
# qdrant客户端
import asyncio
import random

from qdrant_client import AsyncQdrantClient,models

from app.app_config.config import AppConfig, QdrantConfig, object_config


class QdrantClient:
    def __init__(self,config:AppConfig):
        self.client:AsyncQdrantClient | None = None
        self.config:AppConfig = config

    def init_client(self):
        """初始化异步 Qdrant 客户端。"""
        self.client = AsyncQdrantClient(url=self._get_url())

    def _get_url(self):
        return f'http://{self.config.qdrant.host}:{self.config.qdrant.port}'

    async def close(self):
        """关闭 Qdrant 客户端连接。"""
        await self.client.close()


# 模块级单例
qdrant_client_manager = QdrantClient(object_config)

if __name__ == '__main__':
    # 连通性自测：创建集合、插入随机向量、查询
    qdrant_client_manager.init_client()


    async def test():
        client = qdrant_client_manager.client
        if not await client.collection_exists("my_collection"):
            await client.create_collection(
                collection_name="my_collection",
                vectors_config=models.VectorParams(size=10, distance=models.Distance.COSINE),
            )

        await client.upsert(
            collection_name="my_collection",
            points=[
                models.PointStruct(
                    id=i,
                    vector=[random.random() for _ in range(10)],
                )
                for i in range(100)
            ],
        )

        res = await client.query_points(
            collection_name="my_collection",
            query=[random.random() for _ in range(10)],  # type: ignore
            limit=10,
            score_threshold=0.8
        )

        print(res)


    asyncio.run(test())
