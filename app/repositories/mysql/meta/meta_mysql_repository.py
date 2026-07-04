"""
元数据库（meta）MySQL 仓储。

面向存储元信息的 meta 库，封装表/字段/指标的增删查操作。写入时通过 Mapper
将领域实体（entities）转换为 ORM 模型（models），读取时反向转换为实体。
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.models.column_info import ColumnInfoMySQL
from app.models.table_info import TableInfoMySQL
from app.repositories.mysql.meta.mappers.column_info_mapper import ColumnInfoMapper
from app.repositories.mysql.meta.mappers.column_metric_mapper import ColumnMetricMapper
from app.repositories.mysql.meta.mappers.metric_info_mapper import MetricInfoMapper
from app.repositories.mysql.meta.mappers.table_info_mapper import TableInfoMapper


class MetaMySqlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_table_infos(self, table_infos: list[TableInfo]):
        """批量保存表信息（实体->ORM 模型）。"""
        self.session.add_all([TableInfoMapper.to_model(table_info) for table_info in table_infos])

    async def save_column_infos(self, column_infos: [ColumnInfo]):
        """批量保存字段信息。"""
        self.session.add_all([ColumnInfoMapper.to_model(column_info) for column_info in column_infos])

    async def save_metric_infos(self, metric_infos: list[MetricInfo]):
        """批量保存指标信息。"""
        self.session.add_all([MetricInfoMapper.to_model(metric_info) for metric_info in metric_infos])

    async def save_column_metrics(self, column_metrics: list[ColumnMetric]):
        """批量保存 指标-字段 关联关系。"""
        self.session.add_all([ColumnMetricMapper.to_model(column_metric) for column_metric in column_metrics])

    async def get_column_info_by_id(self, id: str) -> ColumnInfo|None:
        """按 id 查询单个字段信息，返回实体（不存在返回 None）。"""
        column_info: ColumnInfoMySQL = await self.session.get(ColumnInfoMySQL, id)
        if not column_info:
            return None
        return ColumnInfoMapper.to_entity(column_info)

    async def get_table_info_by_id(self, id:str)->TableInfo|None:
        """按 id 查询单个表信息，返回实体（不存在返回 None）。"""
        table_info: TableInfoMySQL = await self.session.get(TableInfoMySQL, id)
        if not table_info:
            return None
        return TableInfoMapper.to_entity(table_info)

    async def get_key_info_by_id(self, table_id:str) -> list[ColumnInfo]:
        """查询指定表的主键与外键字段（用于保证多表 JOIN 关联键可用）。"""
        sql = "select * from column_info where table_id = :table_id and role in ('primary_key','foreign_key')"
        result = await self.session.execute(text(sql),params={'table_id':table_id})
        return [ColumnInfo(**dict(row)) for row in result.mappings().fetchall()]
