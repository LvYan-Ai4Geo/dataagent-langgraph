"""
MySQL 客户端管理器。

封装 SQLAlchemy 异步引擎与 async_sessionmaker 的初始化与关闭。
项目使用两个 MySQL 库：
    - meta 库：存储表/字段/指标的元信息（元数据库）；
    - dw 库：数仓，承载真实业务数据，用于 SQL 校验与执行、字段类型/示例抽取。
因此分别创建 meta_mysql_client_manager 与 dw_mysql_client_manager 两个单例。
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.app_config.config import DBConfig, object_config


class MySqlClientManager:
    def __init__(self, config: DBConfig):
        self.client: AsyncEngine | None = None
        self.config = config
        self.session_factory = None

    def init(self):
        """创建异步引擎与 session 工厂。pool_pre_ping 避免长连接断开后报错。"""
        self.client = create_async_engine(self._get_url(),
                                          pool_size=10,
                                          pool_pre_ping=True)

        self.session_factory = async_sessionmaker(self.client,
                                                  autoflush=True,
                                                  expire_on_commit=False,
                                                  autobegin=True)

    async def close(self):
        """释放连接池。"""
        await self.client.dispose()

    def _get_url(self):
        # 使用 asyncmy 异步驱动
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"

# 数仓库客户端单例
dw_mysql_client_manager = MySqlClientManager(config=object_config.db_dw)
# 元数据库客户端单例
meta_mysql_client_manager = MySqlClientManager(config=object_config.db_meta)

if __name__ == '__main__':
    # 连通性自测：查询 table_info 表
    meta_mysql_client_manager.init()


    async def test():
        async with meta_mysql_client_manager.session_factory as session:
            result = await session.execute(text("select * from table_info"))
            rows = result.fetchall()
            print(rows)


    asyncio.run(test())
