"""
字段值 Elasticsearch 仓储。

负责在 ES 中维护字段取值的全文索引（value_index），并提供：
    - ensure_index：确保索引存在（使用 ik_max_word 分词，支持中文）；
    - index：批量写入字段取值；
    - search：按关键词做全文匹配召回，返回 ValueInfo 列表。
"""
from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from app.entities.value_info import ValueInfo


class ValueEsRepository:

    index_name = 'value_index'
    # 索引映射：id/column_id 作为 keyword 精确匹配，value 使用 ik 最大分词
    index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "column_id": {"type": "keyword"}
        }
    }

    def __init__(self,client:AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """若索引不存在则创建（带 ik 分词映射）。"""
        if not await self.client.indices.exists(index=self.index_name):
            await self.client.indices.create(index=self.index_name,
                                             mappings=self.index_mappings)

    async def index(self, values:list[ValueInfo],batch_size=20):
        """
        批量写入字段取值。

        :param values: 待写入的 ValueInfo 列表
        :param batch_size: 每批写入数量
        采用 ES bulk API，每个文档由一个 index 操作头 + 文档本体组成。
        """
        for i in range(0,len(values),batch_size):
            batch_value = values[i:i+batch_size]
            # 获得batch_operation
            batch_operation = []
            for value in batch_value:
                batch_operation.append({
                    "index":{
                        '_index':self.index_name
                    }
                })
                batch_operation.append(asdict(value))

            await self.client.bulk(operations=batch_operation)

    async def search(self, keyword:str,score: float = 0.65, limit: int = 15) -> list[ValueInfo]:
        """
        按关键词在字段取值索引中做全文匹配召回。

        :param keyword: 检索关键词
        :param score: 最低相关性分数阈值
        :param limit: 返回数量上限
        :return: 命中的 ValueInfo 列表
        """
        # 查询数据
        result = await self.client.search(
            index=self.index_name,
            query={
                'match':{
                    'value':keyword
                }
            },
            size=limit,
            min_score=score
        )

        return [ValueInfo(**hit['_source']) for hit in result['hits']['hits']]
