"""MetricInfo 领域实体与 MetricInfoMySQL ORM 模型之间的双向转换。"""
from dataclasses import asdict

from app.entities.metric_info import MetricInfo
from app.models.metric_info import MetricInfoMySQL

class MetricInfoMapper:
    @staticmethod
    def to_entity(model: MetricInfoMySQL) -> MetricInfo:
        return MetricInfo(
            id=model.id,
            name=model.name,
            description=model.description,
            relevant_columns=model.relevant_columns,
            alias=model.alias
        )

    @staticmethod
    def to_model(entity: MetricInfo):
        return MetricInfoMySQL(id=entity.id,
            name=entity.name,
            description=entity.description,
            relevant_columns=entity.relevant_columns,
            alias=entity.alias)
