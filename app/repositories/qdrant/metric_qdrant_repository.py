"""
指标信息 Qdrant 仓储。

与 ColumnQdrantRepository 结构一致，但管理的是指标向量索引
（metric_info_collection），返回 MetricInfo 实体。用于指标向量召回。
"""
from qdrant_client import AsyncQdrantClient
from app.app_config.config import object_config
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.entities.metric_info import MetricInfo


class MetricQdrantRepository:

    collection_name = 'metric_info_collection'
    def __init__(self,client:AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        """若集合不存在则创建。"""
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=object_config.qdrant.embedding_size,distance=Distance.COSINE)
            )

    async def upsert(self, ids: list[str], embeddings: list[list[float]], payloads: list[dict], batch_size: int = 20):
        """
        批量写入指标向量点（字段名/描述/别名各一条向量，详见 MetaKnowledgeService）。
        """
        points: list[PointStruct] = [PointStruct(id=id, vector=embedding, payload=payload) for id, embedding, payload in
                                     zip(ids, embeddings, payloads)]
        for i in range(0, len(points), batch_size):
            await self.client.upsert(collection_name=self.collection_name, points=points[i:i + batch_size])

    async def search(self, embedding: list[float], score: float = 0.65, limit: int = 15) -> list[MetricInfo]:
        """基于向量做余弦相似度检索，返回命中的指标信息。"""
        # 查询数据
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit=limit,
            score_threshold=score
        )

        return [MetricInfo(**point.payload) for point in result.points]
