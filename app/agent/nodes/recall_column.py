"""
节点：字段召回（recall_column）。

通过两路检索从 Qdrant 中召回与用户问题相关的字段信息：
    1. LLM 扩展关键词：让 LLM 根据用户问题推断“回答该问题所需的字段概念”，
       扩展检索词，弥补 jieba 抽取的关键词在语义覆盖上的不足；
    2. 向量检索：对每个关键词调用 Embedding 模型生成向量，在 Qdrant 的
       column_info_collection 中做余弦相似度检索。

最终对召回结果按字段 id 去重后返回。
"""
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.column_info import ColumnInfo


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段信息", "status": "running"})

    try:
        keywords = state["keywords"]
        query = state["query"]
        column_qdrant_repository = runtime.context.column_qdrant_repository
        embedding_model = runtime.context.embedding_model

        # 1. LLM 扩展关键词：推断回答该问题所需的字段概念
        prompt_template = load_prompt(name="extend_keywords_for_column_recall")
        prompt = PromptTemplate(template=prompt_template, input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})
        # 合并 jieba 关键词与 LLM 扩展关键词（set 去重）
        keywords = set(keywords + result)

        # 2. 对每个关键词做向量检索，汇总召回结果
        column_info_map: dict[str, ColumnInfo] = {}
        column_infos: list[ColumnInfo] = []
        for keyword in keywords:
            embedding = await embedding_model.aembed_query(keyword)
            column_info: list[ColumnInfo] = await column_qdrant_repository.search(embedding)
            column_infos.extend(column_info)
            # 按 id 去重，同一字段只保留一份
            for item in column_infos:
                if item.id not in column_info_map:
                    column_info_map[item.id] = item

        retrieved_column_infos: list[ColumnInfo] = list(column_info_map.values())
        logger.info(f"召回字段信息成功: {list(column_info_map.keys())}")
        writer({"type": "progress", "step": "召回字段信息", "status": "success"})
        return {"retrieved_column_infos": retrieved_column_infos}
    except Exception as e:
        logger.error(f"召回字段信息失败: {e}")
        writer({"type": "progress", "step": "召回字段信息", "status": "error"})
        raise
