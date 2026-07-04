"""
数仓库（dw）MySQL 仓储。

直接面向承载真实业务数据的数仓库，提供：
    - get_columns_types：查询某张表所有字段的数据类型（SHOW COLUMNS）；
    - get_columns_examples：取某字段的 distinct 取值（用于元信息构建时的示例/取值同步）；
    - get_db_info：获取数据库版本与方言（供生成 SQL 时约束语法）；
    - validate：用 EXPLAIN 校验 SQL 合法性（不真正执行）；
    - run_sql：真正执行查询 SQL 并返回结果行。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class DwMySqlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_columns_types(self, table_name) -> dict[str, str]:
        """查询指定表所有字段的名称->类型映射。"""
        sql = f'show columns from {table_name}'
        result = await self.session.execute(text(sql))
        result_dict = result.mappings().fetchall()

        # 字典推导式
        return {row['Field']: row['Type'] for row in result_dict}

    async def get_columns_examples(self, table_name, columns_name, limit_nums):
        """查询指定字段的 distinct 取值，limit_nums 控制数量（inf 表示全部）。"""
        sql = f'select distinct {columns_name} from {table_name} limit {limit_nums} '
        result = await self.session.execute(text(sql))
        return result.scalars().fetchall()

    async def get_db_info(self):
        """获取数据库版本与方言名称。"""
        sql = 'select version()'
        result = await self.session.execute(text(sql))
        version = result.scalar()
        dialect = self.session.bind.dialect.name
        return {'version': version,
                'dialect': dialect}

    async def validate(self, sql: str):
        """用 EXPLAIN 校验 SQL（仅解析执行计划，不真正执行）。校验失败会抛异常。"""
        sql = f'explain {sql}'
        await self.session.execute(text(sql))

    async def run_sql(self, sql: str) -> list[dict]:
        """真正执行查询 SQL，返回结果行（每行为 dict）。"""
        result = await self.session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]
