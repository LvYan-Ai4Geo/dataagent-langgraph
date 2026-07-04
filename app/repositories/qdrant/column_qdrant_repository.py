"""
字段信息 Qdrant 仓储。

管理 Qdrant 中字段向量索引（column_info_collection）的创建、写入与检索。
向量维度与距离度量来自 app_config.yaml 的 qdrant 段（BGE 模型为 1024 维，余弦距离）。
"""
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.app_config.config import object_config
from app.entities.column_info import ColumnInfo


class ColumnQdrantRepository:
    collection_name = 'column_info_collection'

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        """若集合不存在则创建（向量维度与距离度量来自配置）。"""
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(collection_name=self.collection_name,
                                                vectors_config=VectorParams(size=object_config.qdrant.embedding_size,
                                                                            distance=Distance.COSINE))

    async def upsert(self, ids: list[str], embeddings: list[list[float]], payloads: list[dict], batch_size: int = 20):
        """
        批量写入向量点。

        :param ids: 点 id 列表
        :param embeddings: 与 ids 一一对应的向量
        :param payloads: 与 ids 一一对应的负载（字段完整信息）
        :param batch_size: 每批写入数量
        借助 zip 将三者一一对应组装为 PointStruct，再分批 upsert。
        """
        points: list[PointStruct] = [PointStruct(id=id, vector=embedding, payload=payload) for id, embedding, payload in
                                     zip(ids, embeddings, payloads)]
        for i in range(0, len(points), batch_size):
            await self.client.upsert(collection_name=self.collection_name, points=points[i:i + batch_size])

    async def search(self, embedding:list[float], score:float=0.65, limit:int=15) -> list[ColumnInfo]:
        """
        基于向量做余弦相似度检索，返回命中的字段信息。

        :param embedding: 查询向量
        :param score: 相似度阈值
        :param limit: 返回数量上限
        """
        # 查询数据
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit = limit,
            score_threshold=score
        )

        return [ColumnInfo(**point.payload) for point in result.points]
