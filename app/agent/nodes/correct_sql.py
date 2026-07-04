"""
节点：修正 SQL（correct_sql）。

当 validate_sql 节点校验失败时进入本节点。将原始 SQL、错误信息以及全部上下文
重新喂给 LLM，要求其在严格保持业务语义不变的前提下，根据错误信息进行最小必要
修复，生成一条可执行的 SQL。修正后的 SQL 会回到 run_sql 节点执行。

注意：当前实现为单次修正（无循环重试），即修正后直接执行。
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "修正SQL语句", "status": "running"})

    try:
        # 构造修正 SQL 的 prompt，额外输入原始 SQL 与错误信息
        prompt = PromptTemplate(
            template=load_prompt("correct_sql"),
            input_variables=["table_infos", "metric_infos", "date_info", "db_info", "query", "error", "sql"],
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        corrected_sql = await chain.ainvoke(
            {
                "table_infos": state["table_infos"],
                "metric_infos": state["metric_infos"],
                "date_info": state["date_info"],
                "db_info": state["db_info"],
                "query": state["query"],
                "error": state["error"],
                "sql": state["sql"],
            }
        )

        logger.info(f"修正SQL语句成功: {corrected_sql}")
        writer({"type": "progress", "step": "修正SQL语句", "status": "success"})
        return {"sql": corrected_sql}
    except Exception as e:
        logger.error(f"修正SQL语句失败: {e}")
        writer({"type": "progress", "step": "修正SQL语句", "status": "error"})
        raise
