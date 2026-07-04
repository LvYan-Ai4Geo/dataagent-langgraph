"""
节点：表/字段过滤（filter_table）。

与 filter_metric 对称，本节点让 LLM 从候选表与字段集合中裁剪出回答该问题
所必需的表和字段，剔除冗余字段，并保证多表 JOIN 所需的主外键被保留。

LLM 输出格式为：
    {"表名1": ["字段1","字段2"], "表名2": ["字段1"]}
据此对每张表的 columns 做保留过滤，并丢弃没有任何字段被选中的表。
"""
import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState, TableInfoState
from app.core.log import logger


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤表信息", "status": "running"})

    try:
        query = state["query"]
        table_infos = state["table_infos"]

        # 让 LLM 选择回答该问题所必需的表与字段
        prompt = PromptTemplate(template=load_prompt("filter_table_info"), input_variables=["query", "table_infos"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke(
            {"query": query, "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False)}
        )

        # 按表名过滤：仅保留被选中的表，并裁剪每张表内未被选中的字段
        filter_table_infos: list[TableInfoState] = []
        for table_info in table_infos:
            if table_info["name"] in result:
                table_info["columns"] = [
                    column_info
                    for column_info in table_info["columns"]
                    if column_info["name"] in result[table_info["name"]]
                ]
                filter_table_infos.append(table_info)

        logger.info(f"过滤表信息成功: {[t['name'] for t in filter_table_infos]}")
        writer({"type": "progress", "step": "过滤表信息", "status": "success"})
        return {"table_infos": filter_table_infos}
    except Exception as e:
        logger.error(f"过滤表信息失败: {e}")
        writer({"type": "progress", "step": "过滤表信息", "status": "error"})
        raise
