"""
节点：生成 SQL（generate_sql）。

将用户问题、过滤后的表/字段信息、指标信息、日期与数据库上下文一起喂给 LLM，
生成一条语法正确、可执行的 SQL 查询语句。Prompt 严格约束 LLM 只能使用提供的
表与字段，禁止编造，且只生成纯文本 SQL（不含 Markdown 代码块）。
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.prompt.prompt_loader import load_prompt
from app.agent.state import DataAgentState
from app.core.log import logger


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "生成SQL语句", "status": "running"})

    try:
        # 构造生成 SQL 的 prompt，输入变量为各类上下文信息
        prompt = PromptTemplate(
            template=load_prompt("generate_sql"),
            input_variables=["table_infos", "metric_infos", "date_info", "db_info", "query"],
        )
        # 输出为纯文本 SQL，使用 StrOutputParser
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        sql = await chain.ainvoke(
            {
                "table_infos": state["table_infos"],
                "metric_infos": state["metric_infos"],
                "date_info": state["date_info"],
                "db_info": state["db_info"],
                "query": state["query"],
            }
        )

        logger.info(f"生成SQL语句成功: {sql}")
        writer({"type": "progress", "step": "生成SQL语句", "status": "success"})
        return {"sql": sql}
    except Exception as e:
        logger.error(f"生成SQL语句失败: {e}")
        writer({"type": "progress", "step": "生成SQL语句", "status": "error"})
        raise
