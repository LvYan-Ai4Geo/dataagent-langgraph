"""
字段信息领域实体。

在仓储层与节点之间传递字段元信息。会被存入 Qdrant 的 payload、
MySQL 元数据库的 column_info 表，并参与工作流状态流转。
"""
from dataclasses import dataclass
from typing import Any

@dataclass
class ColumnInfo:
    id: str
    name: str
    type: str
    role: str
    examples: list[Any]      # 字段取值示例（运行时也会被召回的字段值填充）
    description: str         # 字段业务描述
    alias: list[str]         # 字段别名（用于向量召回扩展）
    table_id: str            # 所属表 id（表名）
