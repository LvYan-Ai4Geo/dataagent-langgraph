"""ColumnInfo 领域实体与 ColumnInfoMySQL ORM 模型之间的双向转换。"""
from dataclasses import asdict

from app.entities.column_info import ColumnInfo
from app.models.column_info import ColumnInfoMySQL

class ColumnInfoMapper:
    @staticmethod
    def to_entity(column_info_mysql: ColumnInfoMySQL) -> ColumnInfo:
        return ColumnInfo(
            id=column_info_mysql.id,
            name=column_info_mysql.name,
            type=column_info_mysql.type,
            role=column_info_mysql.role,
            examples=column_info_mysql.examples,
            description=column_info_mysql.description,
            alias=column_info_mysql.alias,
            table_id=column_info_mysql.table_id,
        )

    @staticmethod
    def to_model(column_info: ColumnInfo) -> ColumnInfoMySQL:
        return ColumnInfoMySQL(id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            description=column_info.description,
            alias=column_info.alias,
            table_id=column_info.table_id,)
