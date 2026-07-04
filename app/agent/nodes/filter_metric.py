"""
节点：指标过滤（filter_metric）。

合并后的指标信息可能包含召回但实际回答该问题并不需要的指标。本节点让 LLM
根据用户问题，从候选指标集合中筛选出“真正用于度量/统计”的指标，剔除冗余，
保证后续生成 SQL 时指标口径清晰、最小化。

LLM 输出为指标名称列表（JSON 数组），据此对 metric_infos 做保留过滤。
"""
import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger


async def filter_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤指标信息", "status": "running"})

    try:
        query = state["query"]
        metric_infos = state["metric_infos"]

        # 让 LLM 从候选指标中筛选出回答该问题所必需的指标名称
        prompt = PromptTemplate(template=load_prompt("filter_metric_info"), input_variables=["query", "metric_infos"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        # 使用 yaml.dump 保留中文可读性、保持字段顺序，便于 LLM 理解
        result = await chain.ainvoke(
            {"query": query, "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)}
        )

        # 仅保留 LLM 选中的指标
        filter_metric_infos = [metric_info for metric_info in metric_infos if metric_info["name"] in result]
        logger.info(f"过滤指标信息成功: {[m['name'] for m in filter_metric_infos]}")
        writer({"type": "progress", "step": "过滤指标信息", "status": "success"})
        return {"metric_infos": filter_metric_infos}
    except Exception as e:
        logger.error(f"过滤指标信息失败: {e}")
        writer({"type": "progress", "step": "过滤指标信息", "status": "error"})
        raise
