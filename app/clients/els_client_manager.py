"""
Elasticsearch 客户端管理器。

封装 AsyncElasticsearch 客户端的初始化与关闭，以模块级单例 `els_client` 暴露。
配置来自 app_config.yaml 的 es 段。主要用于字段值的全文检索（IK 分词）。
"""
import asyncio

from elasticsearch import AsyncElasticsearch

from app.app_config.config import ESConfig, object_config


class ElsClient:
    def __init__(self, config: ESConfig):
        self.client: AsyncElasticsearch | None = None
        self.config: ESConfig = config

    def init(self):
        """初始化异步 ES 客户端。"""
        self.client = AsyncElasticsearch(hosts=self._get_url())

    async def close(self):
        """关闭 ES 客户端连接。"""
        await self.client.close()

    def _get_url(self):
        return f'http://{self.config.host}:{self.config.port}'


# 模块级单例
els_client  = ElsClient(config=object_config.es)

if __name__ == '__main__':
    # 连通性自测：创建索引、批量写入、搜索
    els_client.init()

    async def test():
        client = els_client.client

        # 创建索引
        await client.indices.create(
            index="my-books",
            mappings={
                "dynamic": False,
                "properties": {
                    "name": {
                        "type": "text"
                    },
                    "author": {
                        "type": "text"
                    },
                    "release_date": {
                        "type": "date",
                        "format": "yyyy-MM-dd"
                    },
                    "page_count": {
                        "type": "integer"
                    }
                }
            },
        )

        # 插入数据
        await client.bulk(
            operations=[
                {
                    "index": {
                        "_index": "my-books"
                    }
                },
                {
                    "name": "Revelation Space",
                    "author": "Alastair Reynolds",
                    "release_date": "2000-03-15",
                    "page_count": 585
                },
                {
                    "index": {
                        "_index": "my-books"
                    }
                },
                {
                    "name": "1984",
                    "author": "George Orwell",
                    "release_date": "1985-06-01",
                    "page_count": 328
                },
                {
                    "index": {
                        "_index": "my-books"
                    }
                },
                {
                    "name": "Fahrenheit 451",
                    "author": "Ray Bradbury",
                    "release_date": "1953-10-15",
                    "page_count": 227
                },
                {
                    "index": {
                        "_index": "my-books"
                    }
                },
                {
                    "name": "Brave New World",
                    "author": "Aldous Huxley",
                    "release_date": "1932-06-01",
                    "page_count": 268
                },
                {
                    "index": {
                        "_index": "my-books"
                    }
                },
                {
                    "name": "The Handmaids Tale",
                    "author": "Margaret Atwood",
                    "release_date": "1985-06-01",
                    "page_count": 311
                }
            ],
        )

        # 搜索
        resp = await client.search(
            index="my-books",
            query={
                "match": {
                    "name": "brave"
                }
            },
        )
        print(resp)
        await els_client.close()

    asyncio.run(test())
