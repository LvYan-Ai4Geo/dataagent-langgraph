"""
指标信息领域实体。

描述一个业务度量概念（如 GMV、AOV），包含其关联字段（relevant_columns）
与别名。会被存入 Qdrant 指标集合与 MySQL 元数据库的 metric_info 表。
"""
from dataclasses import dataclass

@dataclass
class MetricInfo:
    id: str                       # 指标 id（通常等于指标名）
    name: str                     # 指标名称
    description: str              # 指标业务描述/口径
    relevant_columns: list[str]   # 该指标计算所依赖的字段 id 列表（形如 表名.字段名）
    alias: list[str]              # 指标别名

