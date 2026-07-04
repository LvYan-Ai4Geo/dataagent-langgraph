"""
字段取值领域实体。

表示某个字段的一个具体取值（如 region_name='华北'）。
存于 Elasticsearch 的 value_index 中，支撑字段值的全文召回。
"""
from dataclasses import dataclass

@dataclass
class ValueInfo:
    id: str         # 取值唯一 id（形如 表名.字段名.取值）
    value: str      # 字段的具体取值
    column_id: str  # 该取值所属字段 id（字段名）
