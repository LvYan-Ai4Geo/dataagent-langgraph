"""
节点：合并召回信息（merge_retrieved_info）。

将三路召回的结果（字段、指标、字段值）合并为后续 LLM 可直接使用的结构化信息：
    1. 以字段召回结果为基础，补全指标关联字段、字段值所属字段（若未召回则从
       元数据库按 id 查询补齐）；
    2. 将召回的字段值回填到对应字段的 examples 中，供 LLM 参考；
    3. 按字段所属表分组，并为每张表补全主外键字段（保证后续多表 JOIN 可行）；
    4. 查询每张表的元信息，组装成 TableInfoState 列表；
    5. 将召回的指标信息转换为 MetricInfoState 列表。

输出 table_infos 与 metric_infos，作为后续过滤节点的输入。
"""
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, MetricInfoState, ColumnInfoState
from app.core.log import logger
from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并召回信息", "status": "running"})

    try:
        retrieved_columns_infos: list[ColumnInfo] = state.get("retrieved_column_infos", [])
        retrieved_metric_infos: list[MetricInfo] = state.get("retrieved_metric_infos", [])
        retrieved_value_infos: list[ValueInfo] = state.get("retrieved_value_infos", [])
        meta_mysql_repository = runtime.context.meta_mysql_repository

        # 1. 以字段 id 为 key 建立映射，便于后续去重与补全
        retrieved_columns_infos_mapper: dict[str, ColumnInfo] = {
            col.id: col for col in retrieved_columns_infos if col is not None
        }

        # 2. 指标关联的字段若未在召回结果中，则从元数据库补齐
        for metric_info in retrieved_metric_infos:
            for relevant_column in metric_info.relevant_columns:
                if relevant_column not in retrieved_columns_infos_mapper:
                    column_info: ColumnInfo | None = await meta_mysql_repository.get_column_info_by_id(id=relevant_column)
                    if column_info:
                        retrieved_columns_infos_mapper[relevant_column] = column_info

        # 3. 字段值所属字段若未召回则补齐，并将召回的字段值回填到该字段的 examples 中
        for retrieved_value_info in retrieved_value_infos:
            values = retrieved_value_info.value
            column_id = retrieved_value_info.column_id

            if column_id not in retrieved_columns_infos_mapper:
                column_info: ColumnInfo | None = await meta_mysql_repository.get_column_info_by_id(id=column_id)
                if column_info:
                    retrieved_columns_infos_mapper[column_id] = column_info

            if column_id in retrieved_columns_infos_mapper:
                target_col = retrieved_columns_infos_mapper[column_id]
                if target_col.examples is None:
                    target_col.examples = []
                if values not in target_col.examples:
                    target_col.examples.append(values)

        # 4. 按字段所属表分组
        table_to_columns_map: dict[str, list[ColumnInfo]] = {}
        for column_info in retrieved_columns_infos_mapper.values():
            if not column_info:
                continue
            table_id = column_info.table_id
            if table_id not in table_to_columns_map:
                table_to_columns_map[table_id] = []
            table_to_columns_map[table_id].append(column_info)

        # 5. 为每张表补全主外键字段（多表 JOIN 时必须保证关联键存在）
        for table_id in table_to_columns_map.keys():
            key_columns: list[ColumnInfo] = await meta_mysql_repository.get_key_info_by_id(table_id=table_id)
            existing_column_ids = [col.id for col in table_to_columns_map[table_id]]
            for key_column in key_columns:
                if key_column.id not in existing_column_ids:
                    table_to_columns_map[table_id].append(key_column)

        # 6. 查询表的元信息，组装成传递给 LLM 的 TableInfoState
        table_infos: list[TableInfoState] = []
        for table_id, column_infos in table_to_columns_map.items():
            table_info: TableInfo | None = await meta_mysql_repository.get_table_info_by_id(id=table_id)
            if not table_info:
                continue

            columns: list[ColumnInfoState] = [
                ColumnInfoState(
                    name=column_info.name,
                    type=column_info.type,
                    role=column_info.role,
                    examples=column_info.examples or [],
                    description=column_info.description,
                    alias=column_info.alias,
                )
                for column_info in column_infos
            ]

            table_info_state = TableInfoState(
                name=table_info.name,
                role=table_info.role,
                description=table_info.description,
                columns=columns,
            )
            table_infos.append(table_info_state)

        # 7. 将召回的指标信息转换为传递给 LLM 的 MetricInfoState
        metric_infos: list[MetricInfoState] = [
            MetricInfoState(
                name=retrieved_metric_info.name,
                description=retrieved_metric_info.description,
                relevant_columns=retrieved_metric_info.relevant_columns,
                alias=retrieved_metric_info.alias,
            )
            for retrieved_metric_info in retrieved_metric_infos
        ]

        logger.info("合并召回信息成功")
        writer({"type": "progress", "step": "合并召回信息", "status": "success"})
        return {"table_infos": table_infos, "metric_infos": metric_infos}
    except Exception as e:
        logger.error(f"合并召回信息失败: {e}")
        writer({"type": "progress", "step": "合并召回信息", "status": "error"})
        raise
