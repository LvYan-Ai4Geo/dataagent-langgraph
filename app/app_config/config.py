"""
应用配置加载模块。

使用 OmegaConf 读取 conf/app_config.yaml，并通过 structured schema
将配置映射为带类型的 dataclass 对象 object_config，供全应用安全访问。
配置项涵盖：日志、元数据库、数仓库、Qdrant、Embedding、ES、LLM。
"""
# 完成读取yaml配置文件
from dataclasses import dataclass

# 日志配置
from dataclasses import dataclass
from pathlib import Path

from omegaconf import OmegaConf


@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console


# 数据库配置
@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    host: str
    port: int
    model: str
    batch_size:int


@dataclass
class ESConfig:
    host: str
    port: int
    index_name: str


@dataclass
class LLMConfig:
    model_name: str
    api_key: str
    base_url: str


@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    llm: LLMConfig


# 1. 拿到yaml文件路径
root = Path(__file__).parent.parent.parent  # 根目录
file_path = root / 'conf' / 'app_config.yaml'

# 2. 加载yaml文件
content = OmegaConf.load(file_path) # dictconfig
schema = OmegaConf.structured(AppConfig)

# 3. 将schema与content合并
object_config:AppConfig = OmegaConf.to_object(OmegaConf.merge(content,schema))


if __name__ == '__main__':
    print(object_config.llm.model_name)

