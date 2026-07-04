"""
元知识构建服务（MetaKnowledgeService）。

负责“离线”构建 Agent 检索所需的元知识库，是 Agent 在线查询的前提。主要工作：
    1. 读取 meta_config.yaml 中定义的表/字段/指标配置；
    2. 将表信息与字段信息写入 MySQL 元数据库（meta 库）；
    3. 为每个字段的 名称/描述/别名 生成向量，写入 Qdrant 的字段集合；
    4. 对配置中标记 sync=true 的字段，从数仓抽取其全部取值，写入 ES 全文索引；
    5. 将指标信息写入 MySQL 元数据库，并为指标的 名称/描述/别名 生成向量写入 Qdrant 的指标集合。

该服务由 app/scripts/build_meta_knowledge.py 脚本调用，一次性离线执行。
"""
import uuid
from dataclasses import asdict
from langchain_huggingface import HuggingFaceEmbeddings
from omegaconf import OmegaConf
from app.app_config.config import object_config
from app.app_config.meta_config import MetaConfig
from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DwMySqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.core.log import logger


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository: MetaMySqlRepository,
                 dw_mysql_repository: DwMySqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_model: HuggingFaceEmbeddings,
                 es_repository: ValueEsRepository,
                 metric_qdrant_repository:MetricQdrantRepository,
                 ):
        self.meta_mysql_repository: MetaMySqlRepository = meta_mysql_repository
        self.dw_mysql_repository: DwMySqlRepository = dw_mysql_repository
        self.column_qdrant_repository: ColumnQdrantRepository = column_qdrant_repository
        self.embedding_model: HuggingFaceEmbeddings = embedding_model
        self.value_es_repository: ValueEsRepository = es_repository
        self.metric_qdrant_repository:MetricQdrantRepository = metric_qdrant_repository

    async def _save_tables_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfo]:
        """
        同步表信息与字段信息到元数据库。

        字段类型从数仓 SHOW COLUMNS 查询，字段示例从数仓 distinct 取值获取。
        返回构造好的 ColumnInfo 列表，供后续建立向量索引使用。
        """
        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []
        # 2.1 同步表信息与字段信息
        for table in meta_config.tables:
            # table -> table_info
            table_info = TableInfo(id=table.name,
                                   name=table.name,
                                   role=table.role,
                                   description=table.description)
            table_infos.append(table_info)

            # 字段type需要从表中查询，放至repository层执行 &&&
            column_types = await self.dw_mysql_repository.get_columns_types(table.name)

            for column in table.columns:
                # 示例example是需要从表中的具体字段获取
                column_examples = await self.dw_mysql_repository.get_columns_examples(table_name=table.name,
                                                                                      columns_name=column.name,
                                                                                      limit_nums=10)
                # column -> column.info
                column_info = ColumnInfo(id=f"{table.name}.{column.name}",
                                         name=column.name,
                                         type=column_types[column.name],
                                         role=column.role,
                                         examples=column_examples,
                                         description=column.description,
                                         alias=column.alias,
                                         table_id=table.name)
                column_infos.append(column_info)

        # 把数据写入meta数据库,自动管理生命周期
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_table_infos(table_infos)
            await self.meta_mysql_repository.save_column_infos(column_infos)

        return column_infos

    async def _save_columns_to_qdrant(self, column_infos: list[ColumnInfo]):
        """
        为字段信息建立向量索引（Qdrant）。
        每个字段的 名称、描述、别名 各生成一条向量，payload 携带完整字段信息，
        这样后续无论用哪种表达检索都能命中同一字段。
        """
        # 2.2.1 创建qdrant中的collection，类似于mysql中的表
        await self.column_qdrant_repository.ensure_collection()

        # 2.2.2 创建points：字段名/描述/别名各作为一个待向量化文本
        points: list[dict] = []
        for column_info in column_infos:
            points.append({'id': uuid.uuid4(),
                           'embedding_text': column_info.name,
                           'payload': asdict(column_info)})

            points.append({'id': uuid.uuid4(),
                           'embedding_text': column_info.description,
                           'payload': asdict(column_info)})

            for alia in column_info.alias:
                points.append({'id': uuid.uuid4(),
                               'embedding_text': alia,
                               'payload': asdict(column_info)})

        # 2.2.3 对points进行向量编码 -> embedding模型（分批避免一次性编码过多）
        embeddings: list[list[float]] = []
        embedding_texts = [point['embedding_text'] for point in points]
        embedding_batch_size = object_config.embedding.batch_size  # 分批次大小进行向量化，避免一次性向量化
        for i in range(0, len(embedding_texts), embedding_batch_size):
            embedding_batch_texts = embedding_texts[i:i + embedding_batch_size]
            result = await self.embedding_model.aembed_documents(embedding_batch_texts)
            embeddings.extend(result)

        ids = [point['id'] for point in points]
        payloads = [point['payload'] for point in points]

        await self.column_qdrant_repository.upsert(ids, embeddings, payloads)

    async def _save_columns_to_es(self, meta_config: MetaConfig):
        """
        对配置中 sync=true 的字段，从数仓抽取其全部 distinct 取值，
        写入 ES 全文索引，供后续字段值召回使用。
        """
        await self.value_es_repository.ensure_index()

        values: list[ValueInfo] = []
        # 2.3.1 遍历元数据表中的所有字段
        for table in meta_config.tables:
            for column in table.columns:
                if column.sync:
                    # sync=true 的字段抽取全部取值（不限数量）
                    current_column_values = await self.dw_mysql_repository.get_columns_examples(
                        table_name=table.name,
                        columns_name=column.name,
                        limit_nums=float('inf'))

                    value = [ValueInfo(id=f'{table.name}.{column.name}.{current_column_value}',
                                       value=current_column_value,
                                       column_id=f'{column.name}') for current_column_value in current_column_values]
                    values.extend(value)

        await self.value_es_repository.index(values)

    async def build(self, config_path):
        """
        元知识库构建主入口。

        :param config_path: meta_config.yaml 配置文件路径
        流程：
            1. 加载并解析配置文件为 MetaConfig 结构化对象；
            2. 同步表/字段信息到元数据库，并为字段建立 Qdrant 向量索引与 ES 全文索引；
            3. 同步指标信息到元数据库，并为指标建立 Qdrant 向量索引。
        """
        # 1. 读取相应的配置文件
        context = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
        logger.info('Meta配置文件加载成功')

        # 2. 同步配置文件的表信息
        if meta_config.tables:
            # 2.1 同步表信息与字段信息
            columns_info = await self._save_tables_to_meta_db(meta_config=meta_config)
            logger.info('将表信息和字段信息保存到元数据库中成功')

            # 2.2 建立字段的向量索引
            await self._save_columns_to_qdrant(column_infos=columns_info)
            logger.info('将字段信息的向量索引保存到qdrant成功')
            # 2.3 对指定字段的取值进行全文索引
            await self._save_columns_to_es(meta_config=meta_config)
            logger.info('全文字段索引建立成功')
        # 3. 同步配置文件的指标信息
        # 3.1 将指标信息写入meta_mysql数据库
        if meta_config.metrics:
            # 步骤与2.1类似
            metric_infos: list[MetricInfo] = []
            column_metrics: list[ColumnMetric] = []

            for metric in meta_config.metrics:
                # 收集metric_info的信息
                metric_info = MetricInfo(id=metric.name,
                                         name=metric.name,
                                         description=metric.description,
                                         relevant_columns=metric.relevant_columns,
                                         alias=metric.alias)
                metric_infos.append(metric_info)

                # 收集 指标-字段 关联关系
                for column_metric in metric.relevant_columns:
                    column_metric = ColumnMetric(column_id=column_metric,
                                                 metric_id=metric.name)

                    column_metrics.append(column_metric)

            async with self.meta_mysql_repository.session.begin():
                await self.meta_mysql_repository.save_metric_infos(metric_infos)
                await self.meta_mysql_repository.save_column_metrics(column_metrics)

            # 3.2 为指标信息在qdrant中建立向量索引
            await self.metric_qdrant_repository.ensure_collection()

            # 2.2.2 创建points：指标名/描述/别名各作为一个待向量化文本
            points: list[dict] = []
            for metric_info in metric_infos:
                points.append({'id': uuid.uuid4(),
                               'embedding_text': metric_info.name,
                               'payload': asdict(metric_info)})

                points.append({'id': uuid.uuid4(),
                               'embedding_text': metric_info.description,
                               'payload': asdict(metric_info)})

                for alia in metric_info.alias:
                    points.append({'id': uuid.uuid4(),
                                   'embedding_text': alia,
                                   'payload': asdict(metric_info)})

            # 2.2.3 对points进行向量编码 -> embedding模型（分批避免一次性编码过多）
            embeddings: list[list[float]] = []
            embedding_texts = [point['embedding_text'] for point in points]
            embedding_batch_size = object_config.embedding.batch_size  # 分批次大小进行向量化，避免一次性向量化
            for i in range(0, len(embedding_texts), embedding_batch_size):
                embedding_batch_texts = embedding_texts[i:i + embedding_batch_size]
                result = await self.embedding_model.aembed_documents(embedding_batch_texts)
                embeddings.extend(result)

            ids = [point['id'] for point in points]
            payloads = [point['payload'] for point in points]

            await self.metric_qdrant_repository.upsert(ids, embeddings, payloads)
