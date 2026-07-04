"""
节点：指标召回（recall_metric）。

逻辑与 recall_column 类似，但目标是从 Qdrant 的 metric_info_collection 中
召回与用户问题相关的“指标”（如 GMV、AOV 等业务度量概念）。LLM 扩展关键词
面向“指标概念”生成（如“转化率”“客单价”），用于提升指标向量召回的命中率。
"""
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.metric_info import MetricInfo


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回指标信息", "status": "running"})

    try:
        query = state["query"]
        keywords = state["keywords"]
        embedding_model = runtime.context.embedding_model
        metric_qdrant_repository = runtime.context.metric_qdrant_repository

        # 1. LLM 扩展关键词：面向“指标概念”生成检索词
        prompt_template = load_prompt(name="extend_keywords_for_metric_recall")
        prompt = PromptTemplate(template=prompt_template, input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})
        keywords = set(keywords + result)

        # 2. 向量检索召回指标，按 id 去重
        metric_info_map: dict[str, MetricInfo] = {}
        metric_infos: list[MetricInfo] = []
        for keyword in keywords:
            embedding = await embedding_model.aembed_query(keyword)
            metric_info: list[MetricInfo] = await metric_qdrant_repository.search(embedding)
            metric_infos.extend(metric_info)
            for item in metric_infos:
                if item.id not in metric_info_map:
                    metric_info_map[item.id] = item

        retrieved_metric_infos: list[MetricInfo] = list(metric_info_map.values())
        logger.info(f"召回指标信息成功: {list(metric_info_map.keys())}")
        writer({"type": "progress", "step": "召回指标信息", "status": "success"})
        return {"retrieved_metric_infos": retrieved_metric_infos}
    except Exception as e:
        logger.error(f"召回指标信息失败: {e}")
        writer({"type": "progress", "step": "召回指标信息", "status": "error"})
        raise
