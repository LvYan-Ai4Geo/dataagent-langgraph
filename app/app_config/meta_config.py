"""
元知识配置结构定义。

定义 conf/meta_config.yaml 对应的结构化 schema（表/字段/指标配置），
供 MetaKnowledgeService 在构建元知识库时解析使用。OmegaConf.structured
会据此校验并转换 yaml 内容为强类型对象。
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class ColumnConfig:
    """字段配置：名称、角色、描述、别名，以及是否同步取值到 ES。"""
    name: str
    role: str
    description: str
    alias: list[str]
    sync: bool

@dataclass
class TableConfig:
    """表配置：名称、角色（fact/dim）、描述及其包含的字段列表。"""
    name: str
    role: str
    description: str
    columns: list[ColumnConfig]

@dataclass
class MetricConfig:
    """指标配置：名称、描述、依赖字段、别名。"""
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]

@dataclass
class MetaConfig:
    """元知识配置根对象，包含待同步的表与指标列表（均可选）。"""
    tables: Optional[list[TableConfig]] = None
    metrics: Optional[list[MetricConfig]] = None
