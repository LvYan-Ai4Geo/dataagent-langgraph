"""指标-字段关联关系实体，存于 MySQL 元数据库 column_metric 表，记录指标与字段的依赖。"""
from dataclasses import dataclass

@dataclass
class ColumnMetric:
    column_id: str  # 字段 id
    metric_id: str  # 指标 id
