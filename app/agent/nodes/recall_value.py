"""
节点：字段值召回（recall_value）。

与字段/指标的向量召回不同，本节点针对“字段的具体取值”进行全文检索：
例如用户问“华北地区男生的销售额”，需要召回 region_name='华北'、gender='男'
这样的取值，以便后续 LLM 在生成 SQL 时使用正确的过滤值。

检索通过 Elasticsearch 的 ik 分词全文匹配完成。LLM 扩展关键词面向
“字段取值层面”生成（如枚举值、业务实体、时间语义词）。
"""
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.value_info import ValueInfo


async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段具体值", "status": "running"})

    try:
        query = state["query"]
        keywords = state["keywords"]
        es_value_repository = runtime.context.es_value_repository

        # 1. LLM 扩展关键词：面向“字段取值层面”生成候选值
        prompt_template = load_prompt(name="extend_keywords_for_value_recall")
        prompt = PromptTemplate(template=prompt_template, input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})
        keywords = set(keywords + result)

        # 2. 在 ES 中对每个关键词做全文检索，召回字段取值并按 id 去重
        value_infos_map: dict[str, ValueInfo] = {}
        for keyword in keywords:
            value_infos: list[ValueInfo] = await es_value_repository.search(keyword)
            for value_info in value_infos:
                if value_info.id not in value_infos_map:
                    value_infos_map[value_info.id] = value_info

        retrieved_value_infos: list[ValueInfo] = list(value_infos_map.values())
        logger.info(f"召回字段具体值成功: {[item.value for item in retrieved_value_infos]}")
        writer({"type": "progress", "step": "召回字段具体值", "status": "success"})
        return {"retrieved_value_infos": retrieved_value_infos}
    except Exception as e:
        logger.error(f"召回字段具体值失败: {e}")
        writer({"type": "progress", "step": "召回字段具体值", "status": "error"})
        raise
