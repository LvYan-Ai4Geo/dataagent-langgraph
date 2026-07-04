"""表信息领域实体。描述数仓中一张表的基本元信息（事实表/维度表等）。"""
from dataclasses import dataclass

@dataclass
class TableInfo:
    id: str           # 表 id（通常等于表名）
    name: str         # 表名
    role: str         # 表角色：fact（事实表）/ dim（维度表）
    description: str  # 表业务描述
